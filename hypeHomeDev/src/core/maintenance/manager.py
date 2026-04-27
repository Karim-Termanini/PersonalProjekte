"""HypeHomeDev — Advanced Snapshot & Persistence Engine (Guardian Layer).

Consolidates pluggable storage, AES-256 encryption with session-based key caching,
integrity verification, retention policies, and health checks.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, cast

if TYPE_CHECKING:
    from core.events import EventBus
    from core.maintenance.sync_tracker import HypeSyncStatusTracker
    from core.setup.environments import EnvironmentManager
    from core.setup.host_executor import HostExecutor

from .storage import LocalStorageProvider, SnapshotMetadata, SnapshotStorageProvider, SnapshotType


class PassphraseStrengthResult(TypedDict):
    valid: bool
    score: int
    length_ok: bool
    has_upper: bool
    has_lower: bool
    has_digit: bool
    has_special: bool
    suggestions: list[str]


class BenchmarkResult(TypedDict):
    encryption_time: float
    decryption_time: float
    encryption_speed_mbps: float
    decryption_speed_mbps: float
    integrity_verified: bool
    total_size_mb: float


class ReliabilityTestResult(TypedDict):
    overall: str
    tests: dict[str, Any]
    recommendations: list[str]
    timestamp: float


class AuditResult(TypedDict):
    total: int
    passed: int
    failed: int
    tampered_ids: list[str]
    details: dict[str, str]


log = logging.getLogger(__name__)


# ─── Enums & Models ──────────────────────────────────────────────────


class HealthStatus(Enum):
    """Health check result status."""

    HEALTHY = auto()
    DEGRADED = auto()
    FAILED = auto()
    UNKNOWN = auto()


# ─── Data Classes ────────────────────────────────────────────────────


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    check_name: str
    status: HealthStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ─── Maintenance Logic ──────────────────────────────────────────────
# ─── Encryption & Security ───────────────────────────────────────────


class EncryptionHandler:
    """Handles AES-256 encryption using PBKDF2 key derivation."""

    @staticmethod
    def generate_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def verify_sha256(data: bytes, expected_checksum: str) -> bool:
        return hashlib.sha256(data).hexdigest() == expected_checksum

    @staticmethod
    async def derive_key(passphrase: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
        """Derive an AES key from a passphrase.

        Args:
            passphrase: User provided secret.
            salt: Existing salt for decryption, or None to generate new one.

        Returns:
            Tuple of (derived_key, salt).
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        if salt is None:
            salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(passphrase.encode())
        return key, salt

    @staticmethod
    async def benchmark_encryption(data_size_kb: int = 1024) -> BenchmarkResult:
        """Benchmark encryption/decryption performance.

        Args:
            data_size_kb: Size of test data in KB.

        Returns:
            Dictionary with performance metrics.
        """
        import time

        # Generate test data
        test_data = os.urandom(data_size_kb * 1024)
        test_passphrase = "test_passphrase_" + str(time.time())

        metrics = {}

        # Benchmark key derivation
        start = time.time()
        key, salt = await EncryptionHandler.derive_key(test_passphrase)
        metrics["key_derivation_ms"] = (time.time() - start) * 1000

        # Benchmark encryption
        start = time.time()
        encrypted = await EncryptionHandler.encrypt_data(test_data, key, salt)
        metrics["encryption_ms"] = (time.time() - start) * 1000
        metrics["encryption_speed_mbps"] = (data_size_kb / 1024) / (
            metrics["encryption_ms"] / 1000
        )

        # Benchmark decryption
        start = time.time()
        decrypted = await EncryptionHandler.decrypt_data(encrypted, key)
        metrics["decryption_ms"] = (time.time() - start) * 1000
        metrics["decryption_speed_mbps"] = (data_size_kb / 1024) / (
            metrics["decryption_ms"] / 1000
        )

        # Verify integrity
        metrics["integrity_verified"] = test_data == decrypted

        return cast(BenchmarkResult, metrics)

    @staticmethod
    def validate_passphrase_strength(passphrase: str) -> PassphraseStrengthResult:
        """Validate passphrase strength for encryption.

        Returns:
            Dictionary with validation results and suggestions.
        """
        import re

        result: PassphraseStrengthResult = {
            "valid": False,
            "score": 0,
            "length_ok": False,
            "has_upper": False,
            "has_lower": False,
            "has_digit": False,
            "has_special": False,
            "suggestions": [],
        }

        # Check length
        if len(passphrase) >= 12:
            result["length_ok"] = True
            result["score"] += 2
        else:
            result["suggestions"].append("Use at least 12 characters")

        # Check character variety
        if re.search(r"[A-Z]", passphrase):
            result["has_upper"] = True
            result["score"] += 1

        if re.search(r"[a-z]", passphrase):
            result["has_lower"] = True
            result["score"] += 1

        if re.search(r"\d", passphrase):
            result["has_digit"] = True
            result["score"] += 1

        if re.search(r'[!@#$%^&*(),.?":{}|<>]', passphrase):
            result["has_special"] = True
            result["score"] += 2

        # Determine if valid
        result["valid"] = result["score"] >= 6 and result["length_ok"]

        if not result["valid"] and not result["suggestions"]:
            result["suggestions"].append(
                "Use a mix of uppercase, lowercase, numbers, and special characters"
            )

        return result

    @staticmethod
    async def encrypt_data(data: bytes, key: bytes, salt: bytes) -> bytes:
        """Encrypt binary data using a pre-derived key and salt."""
        from cryptography.fernet import Fernet

        fernet = Fernet(base64.urlsafe_b64encode(key))
        encrypted = fernet.encrypt(data)
        return salt + encrypted

    @staticmethod
    async def decrypt_data(encrypted_data: bytes, key: bytes) -> bytes:
        """Decrypt binary data using a pre-derived key."""
        from cryptography.fernet import Fernet

        actual_encrypted = encrypted_data[16:]
        fernet = Fernet(base64.urlsafe_b64encode(key))
        return fernet.decrypt(actual_encrypted)

    @staticmethod
    async def verify_reliability() -> ReliabilityTestResult:
        """Run comprehensive reliability tests on the encryption system.

        Returns:
            Dictionary with test results and recommendations.
        """
        import time

        results: ReliabilityTestResult = {
            "overall": "PASS",
            "tests": {},
            "recommendations": [],
            "timestamp": time.time(),
        }

        # Test 1: Small data (1KB)
        try:
            small_test = await EncryptionHandler.benchmark_encryption(1)
            results["tests"]["small_data"] = {
                "status": "PASS" if small_test["integrity_verified"] else "FAIL",
                "metrics": small_test,
            }
            if not small_test["integrity_verified"]:
                results["overall"] = "FAIL"
                results["recommendations"].append("Small data encryption integrity check failed")
        except Exception as e:
            results["tests"]["small_data"] = {"status": "ERROR", "error": str(e)}
            results["overall"] = "FAIL"

        # Test 2: Medium data (10MB)
        try:
            medium_test = await EncryptionHandler.benchmark_encryption(10240)  # 10MB
            results["tests"]["medium_data"] = {
                "status": "PASS" if medium_test["integrity_verified"] else "FAIL",
                "metrics": medium_test,
            }
            if not medium_test["integrity_verified"]:
                results["overall"] = "FAIL"
                results["recommendations"].append("Medium data encryption integrity check failed")

            # Check performance
            if medium_test["encryption_speed_mbps"] < 10:  # Less than 10 MB/s
                results["recommendations"].append(
                    f"Encryption speed is slow: {medium_test['encryption_speed_mbps']:.2f} MB/s"
                )
        except Exception as e:
            results["tests"]["medium_data"] = {"status": "ERROR", "error": str(e)}
            results["overall"] = "FAIL"

        # Test 3: Passphrase validation
        try:
            weak_pass = "weak"
            strong_pass = "StrongPass123!@#"

            weak_result = EncryptionHandler.validate_passphrase_strength(weak_pass)
            strong_result = EncryptionHandler.validate_passphrase_strength(strong_pass)

            results["tests"]["passphrase_validation"] = {
                "status": "PASS"
                if not weak_result["valid"] and strong_result["valid"]
                else "FAIL",
                "weak_pass_result": weak_result,
                "strong_pass_result": strong_result,
            }

            if weak_result["valid"] or not strong_result["valid"]:
                results["overall"] = "FAIL"
                results["recommendations"].append("Passphrase validation logic needs review")
        except Exception as e:
            results["tests"]["passphrase_validation"] = {"status": "ERROR", "error": str(e)}
            results["overall"] = "FAIL"

        # Test 4: Key derivation consistency
        try:
            passphrase = "TestPassphrase123!@#"
            key1, salt1 = await EncryptionHandler.derive_key(passphrase, salt=b"test_salt_12345")
            key2, salt2 = await EncryptionHandler.derive_key(passphrase, salt=b"test_salt_12345")

            consistent = key1 == key2 and salt1 == salt2
            results["tests"]["key_derivation_consistency"] = {
                "status": "PASS" if consistent else "FAIL",
                "keys_match": key1 == key2,
                "salts_match": salt1 == salt2,
            }

            if not consistent:
                results["overall"] = "FAIL"
                results["recommendations"].append(
                    "Key derivation is not consistent with same inputs"
                )
        except Exception as e:
            results["tests"]["key_derivation_consistency"] = {"status": "ERROR", "error": str(e)}
            results["overall"] = "FAIL"

        return results


# ─── Retention & Health ───────────────────────────────────────────────


class RetentionPolicyEngine:
    """Manages automated cleanup of old snapshots (7-daily, 4-weekly)."""

    def __init__(
        self,
        storage_provider: SnapshotStorageProvider,
        keep_daily: int = 7,
        keep_weekly: int = 4,
        warn_disk_bytes: int = 5 * 1024 * 1024 * 1024,
    ) -> None:
        self._storage = storage_provider
        self._keep_daily = keep_daily
        self._keep_weekly = keep_weekly
        self._warn_disk_bytes = warn_disk_bytes

    async def enforce_retention(self, stack_name: str) -> int:
        snapshots = await self._storage.list_snapshots(stack_name)
        if not snapshots:
            return 0

        now = datetime.now()
        daily_cutoff = now - timedelta(days=self._keep_daily)
        weekly_cutoff = now - timedelta(weeks=self._keep_weekly)

        to_delete = []
        to_keep = []

        for snapshot in snapshots:
            snapshot_time = datetime.fromisoformat(snapshot.timestamp)
            if snapshot_time >= weekly_cutoff:
                to_keep.append(snapshot)
            elif snapshot_time >= daily_cutoff:
                day_key = snapshot_time.date().isoformat()
                if not any(
                    datetime.fromisoformat(s.timestamp).date().isoformat() == day_key
                    for s in to_keep
                ):
                    to_keep.append(snapshot)
                else:
                    to_delete.append(snapshot)
            else:
                to_delete.append(snapshot)

        deleted = 0
        for snapshot in to_delete:
            if await self._storage.delete(snapshot.snapshot_id):
                deleted += 1
        return deleted

    async def check_disk_usage_warning(self) -> bool:
        disk_usage = await self._storage.get_disk_usage()
        return disk_usage >= self._warn_disk_bytes


class HealthCheckRunner:
    """Executes post-restore health checks to verify environment integrity."""

    def __init__(self, executor: HostExecutor | None = None) -> None:
        self._executor = executor

    async def run_full_check(self, container_name: str | None = None) -> list[HealthCheckResult]:
        results: list[HealthCheckResult] = []
        if not self._executor:
            return results

        # 1. Container engine check
        engine_check = HealthCheckResult(
            "Container Engine", HealthStatus.FAILED, "No engine found"
        )
        for engine in ["podman", "docker"]:
            if (await self._executor.run_async(["which", engine])).success:
                engine_check = HealthCheckResult(
                    "Container Engine",
                    HealthStatus.HEALTHY,
                    f"{engine.capitalize()} available",
                    {"engine": engine},
                )
                break
        results.append(engine_check)

        # 2. Container specific checks
        if container_name:
            status_res = await self._executor.run_async(["podman", "inspect", container_name])
            results.append(
                HealthCheckResult(
                    "Container Status",
                    HealthStatus.HEALTHY if status_res.success else HealthStatus.FAILED,
                    f"Container {container_name} is "
                    + ("running" if status_res.success else "missing"),
                )
            )

            mount_res = await self._executor.run_async(
                ["distrobox", "enter", container_name, "--", "ls", "-d", "$HOME"]
            )
            results.append(
                HealthCheckResult(
                    "Container Mounts",
                    HealthStatus.HEALTHY if mount_res.success else HealthStatus.DEGRADED,
                    "Mounts operational" if mount_res.success else "Home mount issue",
                )
            )

        return results


# ─── Snapshot Manager (Facade) ───────────────────────────────────────


class SnapshotManager:
    """High-level coordinator for snapshot operations with session-based key caching."""

    def __init__(
        self,
        env_manager: EnvironmentManager,
        storage_provider: SnapshotStorageProvider | None = None,
        sync_tracker: HypeSyncStatusTracker | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._env_manager = env_manager
        self._storage = storage_provider or LocalStorageProvider()
        self._sync_tracker = sync_tracker
        self._event_bus = event_bus
        self._encryption = EncryptionHandler()
        self._retention = RetentionPolicyEngine(self._storage)
        self._health = HealthCheckRunner(env_manager._executor)

        # Session-based key cache (Derived Key Material)
        # Maps salt_hash -> derived_key
        # We Hash the salt as the key to prevent direct association with metadata if memory is leaked
        self._key_cache: dict[str, bytes] = {}

    def _emit(self, event_name: str, **kwargs) -> None:
        """Emit an event to the EventBus if available."""
        if self._event_bus:
            # Standard namespace: maint.<event>
            self._event_bus.emit(f"maint.{event_name}", **kwargs)

    async def create_snapshot(
        self,
        container_name: str | None = None,
        name: str | None = None,
        encrypt: bool = False,
        passphrase: str | None = None,
        stack_name: str | None = None,
        snapshot_type: SnapshotType = SnapshotType.CONTAINER,
    ) -> str:
        """Create a new snapshot with optional encryption."""
        if not name:
            name = container_name or snapshot_type.name

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_id = f"{name}_{timestamp_str}"
        log.info("Creating snapshot: %s (%s)", snapshot_id, snapshot_type)
        self._emit(
            "snapshot.creating", snapshot_id=snapshot_id, name=name, type=snapshot_type.name
        )

        data = b""
        metadata_extra: dict[str, Any] = {}

        # 1. Capture Data based on Type
        if snapshot_type == SnapshotType.CONTAINER and container_name:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".tar") as tmp:
                success = await self._env_manager.backup_distrobox_container(
                    container_name, tmp.name
                )
                if not success:
                    log.error("Failed to backup container %s", container_name)
                    self._emit("snapshot.failed", snapshot_id=snapshot_id, error="Backup failed")
                    return ""
                data = Path(tmp.name).read_bytes()
        elif snapshot_type == SnapshotType.SYSTEM_HOSTS:
            from core.setup.hosts import HostFileManager

            hosts_mgr = HostFileManager(self._env_manager._executor)
            data = hosts_mgr.read_hosts().encode("utf-8")
            metadata_extra["component"] = "hosts"
        elif snapshot_type == SnapshotType.CONFIG:
            from core.setup.env_vars import EnvVarEngine

            env_engine = EnvVarEngine(self._env_manager._executor)
            data = env_engine.read_env_file().encode("utf-8")
            metadata_extra["component"] = "env_vars"
        elif snapshot_type == SnapshotType.DOTFILES:
            import tarfile
            import tempfile

            dotfiles = [".bashrc", ".zshrc", ".profile", ".config"]
            with tempfile.NamedTemporaryFile(suffix=".tar") as tmp:
                with tarfile.open(tmp.name, "w") as archive:
                    for relative_path in dotfiles:
                        source_path = Path.home() / relative_path
                        if source_path.exists():
                            archive.add(source_path, arcname=relative_path)
                data = Path(tmp.name).read_bytes()
            metadata_extra["component"] = "dotfiles"
            metadata_extra["files"] = dotfiles
        elif snapshot_type == SnapshotType.FULL_ENVIRONMENT:
            import tarfile
            import tempfile

            temp_paths: list[Path] = []
            try:
                with tempfile.NamedTemporaryFile(suffix=".tar") as tmp:
                    with tarfile.open(tmp.name, "w") as archive:
                        from core.setup.env_vars import EnvVarEngine
                        from core.setup.hosts import HostFileManager

                        hosts_mgr = HostFileManager(self._env_manager._executor)
                        env_engine = EnvVarEngine(self._env_manager._executor)

                        hosts_content = hosts_mgr.read_hosts().encode("utf-8")
                        env_content = env_engine.read_env_file().encode("utf-8")

                        if hosts_content:
                            with tempfile.NamedTemporaryFile(
                                prefix="hosts_", delete=False
                            ) as hosts_tmp:
                                hosts_tmp.write(hosts_content)
                                hosts_tmp.flush()
                                temp_paths.append(Path(hosts_tmp.name))
                                archive.add(hosts_tmp.name, arcname="etc_hosts_backup.txt")
                        if env_content:
                            with tempfile.NamedTemporaryFile(
                                prefix="env_", delete=False
                            ) as env_tmp:
                                env_tmp.write(env_content)
                                env_tmp.flush()
                                temp_paths.append(Path(env_tmp.name))
                                archive.add(env_tmp.name, arcname="global_env_vars.sh")

                        for relative_path in [".bashrc", ".zshrc", ".profile", ".config"]:
                            source_path = Path.home() / relative_path
                            if source_path.exists():
                                archive.add(source_path, arcname=f"home/{relative_path}")
                    data = Path(tmp.name).read_bytes()
                metadata_extra["component"] = "full_environment"
            finally:
                for p in temp_paths:
                    with contextlib.suppress(OSError):
                        p.unlink()
        else:
            log.error("Unsupported snapshot type for creation: %s", snapshot_type)
            return ""

        if not data:
            log.error("Snapshot data is empty for %s", snapshot_id)
            return ""

        # 2. Handle Encryption
        checksum = self._encryption.generate_sha256(data)
        salt = None

        if encrypt and passphrase:
            key, salt = await self._encryption.derive_key(passphrase)
            # Store in cache
            salt_hash = self._encryption.generate_sha256(salt)
            self._key_cache[salt_hash] = key
            data = await self._encryption.encrypt_data(data, key, salt)

        # 3. Save Metadata
        meta = SnapshotMetadata(
            snapshot_id=snapshot_id,
            name=name,
            snapshot_type=snapshot_type,
            timestamp=datetime.now().isoformat(),
            container_name=container_name,
            encrypted=encrypt,
            sha256_checksum=checksum,
            size_bytes=len(data),
            stack_name=stack_name or container_name or "system",
            metadata=metadata_extra,
        )

        if await self._storage.save(snapshot_id, data, meta):
            await self._retention.enforce_retention(stack_name or container_name or "system")
            log.info("Snapshot created successfully: %s", snapshot_id)
            self._emit("snapshot.created", snapshot_id=snapshot_id, encrypted=encrypt)
            return snapshot_id

        log.error("Failed to save snapshot %s", snapshot_id)
        self._emit("snapshot.failed", snapshot_id=snapshot_id, error="Save failed")
        return ""

    async def backup_hosts_snapshot(
        self,
        encrypt: bool = False,
        passphrase: str | None = None,
        stack_name: str | None = None,
    ) -> str:
        """Create a snapshot of /etc/hosts with optional encryption."""
        return await self.create_snapshot(
            name="hosts_snapshot",
            encrypt=encrypt,
            passphrase=passphrase,
            stack_name=stack_name,
            snapshot_type=SnapshotType.SYSTEM_HOSTS,
        )

    async def backup_env_vars_snapshot(
        self,
        encrypt: bool = False,
        passphrase: str | None = None,
        stack_name: str | None = None,
    ) -> str:
        """Create a snapshot of managed global environment vars."""
        return await self.create_snapshot(
            name="env_vars_snapshot",
            encrypt=encrypt,
            passphrase=passphrase,
            stack_name=stack_name,
            snapshot_type=SnapshotType.CONFIG,
        )

    async def create_dotfiles_snapshot(
        self,
        encrypt: bool = False,
        passphrase: str | None = None,
        stack_name: str | None = None,
    ) -> str:
        """Create a snapshot of common dotfiles from the user home directory."""
        return await self.create_snapshot(
            name="dotfiles_snapshot",
            encrypt=encrypt,
            passphrase=passphrase,
            stack_name=stack_name,
            snapshot_type=SnapshotType.DOTFILES,
        )

    async def verify_encryption(self) -> ReliabilityTestResult:
        """Run a reliability verification pass for the encryption subsystem."""
        return await EncryptionHandler.verify_reliability()

    async def restore_snapshot(
        self,
        snapshot_id: str,
        passphrase: str | None = None,
    ) -> bool:
        """Restore a snapshot with auto-decryption and health checks."""
        log.info("Restoring snapshot: %s", snapshot_id)
        self._emit("snapshot.restoring", snapshot_id=snapshot_id)

        result = await self._storage.load(snapshot_id)
        if not result:
            log.error("Snapshot not found: %s", snapshot_id)
            self._emit("snapshot.restore_failed", snapshot_id=snapshot_id, error="Not found")
            return False

        data, meta = result

        # 1. Decrypt if needed
        if meta.encrypted:
            # Try to find key in cache first (if salt matches)
            salt = data[:16]
            salt_hash = self._encryption.generate_sha256(salt)
            cached_key = self._key_cache.get(salt_hash)

            if cached_key:
                log.debug("Using cached session key for decryption")
                data = await self._encryption.decrypt_data(data, cached_key)
            elif passphrase:
                log.debug("Deriving key from provided passphrase")
                key, _ = await self._encryption.derive_key(passphrase, salt)
                self._key_cache[salt_hash] = key
                data = await self._encryption.decrypt_data(data, key)
            else:
                log.error("Snapshot is encrypted but no passphrase or cached key available")
                self._emit("snapshot.restore_failed", snapshot_id=snapshot_id, error="No key")
                return False

        # 2. Verify Integrity
        if not self._encryption.verify_sha256(data, meta.sha256_checksum):
            log.error("Integrity check failed for snapshot %s", snapshot_id)
            self._emit(
                "snapshot.restore_failed", snapshot_id=snapshot_id, error="Checksum mismatch"
            )
            return False

        # 3. Restore to environment based on Type
        if meta.snapshot_type == SnapshotType.CONTAINER:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".tar") as tmp:
                Path(tmp.name).write_bytes(data)
                success = await self._env_manager.restore_distrobox_container(
                    tmp.name, meta.container_name
                )
                if not success:
                    log.error("Failed to restore container %s", meta.container_name)
                    self._emit(
                        "snapshot.restore_failed", snapshot_id=snapshot_id, error="Restore failed"
                    )
                    return False
        elif meta.snapshot_type == SnapshotType.SYSTEM_HOSTS:
            from core.setup.hosts import HostFileManager

            hosts_mgr = HostFileManager(self._env_manager._executor)
            if not hosts_mgr.write_hosts(data.decode("utf-8")):
                return False
        elif meta.snapshot_type == SnapshotType.CONFIG:
            from core.setup.env_vars import EnvVarEngine

            env_engine = EnvVarEngine(self._env_manager._executor)
            if not env_engine.write_env_file(data.decode("utf-8")):
                return False
        elif meta.snapshot_type in (SnapshotType.DOTFILES, SnapshotType.FULL_ENVIRONMENT):
            import tarfile
            import tempfile

            def _extract_to_home(
                archive: tarfile.TarFile, member: tarfile.TarInfo, target_path: Path
            ) -> None:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                source_io = archive.extractfile(member)
                if source_io is not None:
                    with source_io as source:
                        target_path.write_bytes(source.read())

            restore_hosts = None
            restore_env = None

            with tempfile.NamedTemporaryFile(suffix=".tar") as tmp:
                tmp.write(data)
                tmp.flush()
                with tarfile.open(tmp.name, "r") as archive:
                    for member in archive.getmembers():
                        if member.isdir():
                            continue
                        name = member.name
                        if (
                            meta.snapshot_type == SnapshotType.FULL_ENVIRONMENT
                            and name == "etc_hosts_backup.txt"
                        ):
                            source_io = archive.extractfile(member)
                            if source_io is not None:
                                with source_io as source:
                                    restore_hosts = source.read().decode("utf-8")
                            continue
                        if (
                            meta.snapshot_type == SnapshotType.FULL_ENVIRONMENT
                            and name == "global_env_vars.sh"
                        ):
                            source_io = archive.extractfile(member)
                            if source_io is not None:
                                with source_io as source:
                                    restore_env = source.read().decode("utf-8")
                            continue
                        if name.startswith("home/"):
                            relative = Path(name).relative_to("home")
                            _extract_to_home(archive, member, Path.home() / relative)
                        elif meta.snapshot_type == SnapshotType.DOTFILES:
                            _extract_to_home(archive, member, Path.home() / Path(name))

            if restore_hosts is not None:
                from core.setup.hosts import HostFileManager

                hosts_mgr = HostFileManager(self._env_manager._executor)
                if not hosts_mgr.write_hosts(restore_hosts):
                    return False
            if restore_env is not None:
                from core.setup.env_vars import EnvVarEngine

                env_engine = EnvVarEngine(self._env_manager._executor)
                if not env_engine.write_env_file(restore_env):
                    return False

        # 4. Post-restore Health Check
        health_results = []
        if meta.container_name:
            health_results = await self._health.run_full_check(meta.container_name)
            # Use dedicated health namespace
            if self._event_bus:
                self._event_bus.emit(
                    "maint.snapshot.health_check", snapshot_id=snapshot_id, results=health_results
                )

        log.info("Snapshot restored successfully: %s", snapshot_id)
        self._emit("snapshot.restored", snapshot_id=snapshot_id, healthy=len(health_results) > 0)
        return True

    async def list_snapshots(self, stack_name: str | None = None) -> list[SnapshotMetadata]:
        return await self._storage.list_snapshots(stack_name)

    async def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        self._emit("snapshot.deleting", snapshot_id=snapshot_id)
        success = await self._storage.delete(snapshot_id)
        if success:
            log.info("Snapshot deleted: %s", snapshot_id)
            self._emit("snapshot.deleted", snapshot_id=snapshot_id)
        return success

    def clear_key_cache(self) -> None:
        """Clear all cached encryption keys (call on app close)."""
        self._key_cache.clear()
        log.info("Session key cache cleared")

    def get_sync_status(self):
        if self._sync_tracker:
            return self._sync_tracker.get_status()
        return None

    async def check_retention(self) -> bool:
        return await self._retention.check_disk_usage_warning()

    async def audit_all_snapshots(self) -> AuditResult:
        """Scan and verify the integrity of all stored snapshots.

        Returns:
            Dictionary with audit statistics and findings.
        """
        log.info("Starting global snapshot audit...")
        self._emit("audit.started")

        snapshots = await self._storage.list_snapshots()
        result: AuditResult = {
            "total": len(snapshots),
            "passed": 0,
            "failed": 0,
            "tampered_ids": [],
            "details": {},
        }

        for meta in snapshots:
            try:
                # 1. Load Data
                loaded = await self._storage.load(meta.snapshot_id)
                if not loaded:
                    log.error("Snapshot %s data missing during audit", meta.snapshot_id)
                    result["failed"] += 1
                    result["details"][meta.snapshot_id] = "Missing data"
                    self._emit(
                        "snapshot.audit_failed", snapshot_id=meta.snapshot_id, name=meta.name
                    )
                    continue

                data, _ = loaded

                # 2. Verify Checksum
                # If encrypted, we verify the encrypted data checksum stored in metadata
                actual_checksum = self._encryption.generate_sha256(data)

                if actual_checksum == meta.sha256_checksum:
                    result["passed"] += 1
                    result["details"][meta.snapshot_id] = "OK"
                    self._emit(
                        "snapshot.audit_passed", snapshot_id=meta.snapshot_id, name=meta.name
                    )
                else:
                    log.warning("Snapshot %s tampered! Checksum mismatch", meta.snapshot_id)
                    result["failed"] += 1
                    result["tampered_ids"].append(meta.snapshot_id)
                    result["details"][meta.snapshot_id] = "Checksum mismatch"
                    self._emit(
                        "snapshot.audit_failed", snapshot_id=meta.snapshot_id, name=meta.name
                    )

            except Exception as e:
                log.exception("Error auditing snapshot %s: %s", meta.snapshot_id, e)
                result["failed"] += 1
                result["details"][meta.snapshot_id] = f"Error: {e}"
                self._emit("snapshot.audit_failed", snapshot_id=meta.snapshot_id, name=meta.name)

        log.info("Snapshot audit complete: %d/%d passed", result["passed"], result["total"])
        self._emit("audit.complete", **cast(dict[str, Any], result))
        return result
