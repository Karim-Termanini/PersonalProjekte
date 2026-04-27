"""HypeDevHome — Hosts file manager.

Provides safe parsing, validation, and privileged writing of the system hosts file.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.utils.base import BaseUtilityManager

if TYPE_CHECKING:
    from core.setup.host_executor import HostExecutor

log = logging.getLogger(__name__)

# First column must look like an IP — otherwise # comment lines become fake "entries"
# (e.g. "# Loopback entries..." was parsed as IP "Loopback").
_IPV4_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
_IPV6_START = re.compile(r"^[0-9a-fA-F:.]+")  # loose: ::1, fe80::, etc.


def _first_field_looks_like_ip(token: str) -> bool:
    if not token:
        return False
    if _IPV4_RE.match(token):
        return True
    return bool(":" in token and _IPV6_START.match(token))


@dataclass
class HostsEntry:
    """Represents a single entry in the hosts file."""

    ip: str
    hostnames: list[str]
    comment: str | None = None
    original_line: str | None = None
    is_commented_out: bool = False

    def to_line(self) -> str:
        """Convert entry back to a hosts file line."""
        if self.is_commented_out and not self.original_line:
            # If manually commented out and no original line, format it
            comment_prefix = "# " if self.is_commented_out else ""
            line = f"{comment_prefix}{self.ip:15} {' '.join(self.hostnames)}"
            if self.comment:
                line += f"  # {self.comment}"
            return line

        if self.original_line and self.is_commented_out:
            return (
                self.original_line
                if self.original_line.startswith("#")
                else f"# {self.original_line}"
            )

        line = f"{self.ip:15} {' '.join(self.hostnames)}"
        if self.comment:
            line += f"  # {self.comment}"
        return line


def parse_hosts_entries_from_lines(lines: list[str]) -> list[HostsEntry]:
    """Parse hosts file lines into structured entries (ignores non-entry comments)."""
    entries: list[HostsEntry] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        is_commented = stripped.startswith("#")
        content = stripped[1:].strip() if is_commented else stripped

        first_tok = content.split(None, 1)[0] if content else ""
        if not _first_field_looks_like_ip(first_tok):
            continue

        match = re.match(r"^([^\s#]+)\s+([^#]+)(?:\s*#\s*(.*))?$", content)
        if match:
            ip_addr = match.group(1)
            hostnames = match.group(2).split()
            comment = match.group(3)
            entries.append(
                HostsEntry(
                    ip=ip_addr,
                    hostnames=hostnames,
                    comment=comment,
                    original_line=line,
                    is_commented_out=is_commented,
                )
            )
    return entries


def duplicate_hostname_conflicts(entries: list[HostsEntry]) -> list[str]:
    """Return human-readable conflicts when the same hostname maps to different IPs (active rows)."""
    host_to_ip: dict[str, str] = {}
    conflicts: list[str] = []
    for e in entries:
        if e.is_commented_out:
            continue
        for h in e.hostnames:
            h = h.strip().lower()
            if not h:
                continue
            if h in host_to_ip and host_to_ip[h] != e.ip:
                conflicts.append(f"Hostname {h!r} maps to both {host_to_ip[h]} and {e.ip}")
            else:
                host_to_ip.setdefault(h, e.ip)
    return conflicts


class HostsManager(BaseUtilityManager):
    """Manages the system /etc/hosts file with backup and privileged write support."""

    HOSTS_PATH = "/etc/hosts"
    _BACKUP_ROOT = Path.home() / ".local/share/hypedevhome/hosts-backups"

    def __init__(self, executor: HostExecutor) -> None:
        super().__init__()
        self._executor = executor
        self._entries: list[HostsEntry] = []
        self._raw_lines: list[str] = []
        self._lock_fp: Any = None

    async def initialize(self) -> bool:
        """Load and parse the current hosts file."""
        try:
            # Read /etc/hosts (usually world-readable, but we use executor for consistency)
            result = await self._executor.run_async(["cat", self.HOSTS_PATH])
            if not result.success:
                log.error("Failed to read %s: %s", self.HOSTS_PATH, result.stderr)
                return False

            self._raw_lines = result.stdout.splitlines()
            self._entries = parse_hosts_entries_from_lines(self._raw_lines)
            self._initialized = True
            return True
        except Exception as e:
            log.exception("Error initializing HostsManager: %s", e)
            return False

    def get_entries(self) -> list[HostsEntry]:
        """Return the list of parsed entries."""
        return self._entries

    async def add_entry(self, ip: str, hostnames: list[str]) -> bool:
        """Append a new hosts mapping after validation; persists via :meth:`save`."""
        ip = ip.strip()
        hn = [h.strip() for h in hostnames if h.strip()]
        if not ip or not hn:
            return False
        if not _first_field_looks_like_ip(ip):
            return False
        for h in hn:
            if not self.validate_entry(ip, h):
                return False
        self._entries.append(HostsEntry(ip=ip, hostnames=hn))
        dup = duplicate_hostname_conflicts(self._entries)
        if dup:
            self._entries.pop()
            log.warning("Duplicate hostname conflict: %s", dup)
            return False
        return await self.save()

    def export_content(self) -> str:
        """Return current entries as hosts file text."""
        return "\n".join(e.to_line() for e in self._entries) + "\n"

    def import_replace_from_lines(self, lines: list[str]) -> tuple[bool, str]:
        """Replace in-memory entries from parsed lines. Caller should :meth:`save` to apply."""
        new_entries = parse_hosts_entries_from_lines(lines)
        conflicts = duplicate_hostname_conflicts(new_entries)
        if conflicts:
            return False, "; ".join(conflicts[:5])
        self._entries = new_entries
        return True, ""

    def _acquire_lock(self) -> bool:
        """Prevent concurrent hosts edits from this user (advisory lock file)."""
        import fcntl

        self._BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
        lock_p = self._BACKUP_ROOT / "hosts.lock"
        try:
            fp = open(lock_p, "w", encoding="utf-8")  # noqa: SIM115 — held for flock lifetime
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fp.write(str(os.getpid()))
            fp.flush()
            self._lock_fp = fp
            return True
        except (BlockingIOError, OSError) as e:
            log.warning("Hosts lock busy: %s", e)
            if getattr(self, "_lock_fp", None):
                with contextlib.suppress(Exception):
                    self._lock_fp.close()
                self._lock_fp = None
            return False

    def _release_lock(self) -> None:
        import fcntl

        if self._lock_fp is not None:
            try:
                fcntl.flock(self._lock_fp.fileno(), fcntl.LOCK_UN)
                self._lock_fp.close()
            except Exception:
                pass
            self._lock_fp = None

    def get_status(self) -> dict[str, Any]:
        """Return status information for the UI."""
        return {
            "initialized": self._initialized,
            "path": self.HOSTS_PATH,
            "entry_count": len(self._entries),
            "active_count": len([e for e in self._entries if not e.is_commented_out]),
            "backup_dir": str(self._BACKUP_ROOT),
        }

    def list_backups(self) -> list[tuple[str, str]]:
        """Return up to 25 backups as ``(absolute_path, label)`` newest first."""
        if not self._BACKUP_ROOT.is_dir():
            return []
        paths = sorted(
            self._BACKUP_ROOT.glob("hosts-*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:25]
        out: list[tuple[str, str]] = []
        for p in paths:
            if p.is_file():
                label = p.name
                try:
                    mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    label = f"{p.name} ({mtime})"
                except OSError:
                    pass
                out.append((str(p.resolve()), label))
        return out

    async def restore_backup(self, backup_path: str) -> bool:
        """Copy a backup file to ``/etc/hosts`` using elevated privileges."""
        resolved = Path(backup_path).resolve()
        root = self._BACKUP_ROOT.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            log.error("Invalid backup path (outside backup dir): %s", backup_path)
            return False
        if not resolved.is_file():
            return False
        result = await self._executor.run_async(
            ["cp", str(resolved), self.HOSTS_PATH],
            root=True,
        )
        if result.success:
            await self.initialize()
        return result.success

    async def _backup_current_hosts_file(self) -> str | None:
        """Save a copy of the current on-disk ``/etc/hosts`` into the user backup dir."""
        result = await self._executor.run_async(["cat", self.HOSTS_PATH])
        if not result.success:
            return None
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = self._BACKUP_ROOT / f"hosts-{ts}"

        def _write() -> None:
            self._BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
            dest.write_text(result.stdout, encoding="utf-8")

        await asyncio.to_thread(_write)
        log.info("Hosts backup written: %s", dest)
        return str(dest.resolve())

    async def save(self, entries: list[HostsEntry] | None = None) -> bool:
        """Save the hosts file with a timestamped backup under ~/.local/share/....

        Args:
            entries: Optional new list of entries. If None, uses current _entries.

        Returns:
            True if successful.
        """
        if entries is not None:
            self._entries = entries

        conflicts = duplicate_hostname_conflicts(self._entries)
        if conflicts:
            log.error("Refusing save: duplicate hostname mappings: %s", conflicts)
            return False

        if not self._acquire_lock():
            log.error("Another hosts edit may be in progress (lock file).")
            return False

        try:
            # 1. Generate new content
            new_content = "\n".join([e.to_line() for e in self._entries]) + "\n"

            # 2. Snapshot current /etc/hosts before overwrite (user-writable dir; no root).
            await self._backup_current_hosts_file()

            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
                tmp.write(new_content)
                tmp_path = tmp.name

            # 3. Write back using pkexec
            log.info("Requesting privileged write to %s", self.HOSTS_PATH)
            sh_cmd = f"cat {tmp_path} | tee {self.HOSTS_PATH} > /dev/null"
            result = await self._executor.run_async(["sh", "-c", sh_cmd], root=True)

            if os.path.exists(tmp_path):
                os.remove(tmp_path)

            return result.success
        except Exception as e:
            log.exception("Failed to save hosts file: %s", e)
            return False
        finally:
            self._release_lock()

    def validate_entry(self, ip: str, hostname: str) -> bool:
        """Basic validation for IP and hostname."""
        # Simple IP validation
        ipv4_regex = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
        _ipv6_regex = r"^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"

        if not (re.match(ipv4_regex, ip) or ":" in ip):  # Simple IPv6 check
            return False

        # Hostname validation (RFC 1123)
        if len(hostname) > 255:
            return False
        if hostname.endswith("."):
            hostname = hostname[:-1]
        allowed = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
        return all(allowed.match(x) for x in hostname.split("."))
