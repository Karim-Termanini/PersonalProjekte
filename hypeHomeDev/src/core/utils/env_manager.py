"""HypeDevHome — Environment Variable Manager.

Loads assignments from system and user shell startup files, merges them, and
persists edits from the UI to a dedicated managed snippet under ~/.config/hypedevhome/.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.utils import BaseUtilityManager

log = logging.getLogger(__name__)

_MANAGED_DIR = Path.home() / ".config/hypedevhome"
_MANAGED_FILE = _MANAGED_DIR / "env_managed.sh"

# Files scanned in order (later overrides earlier for duplicate keys).
_USER_FILES: list[Path] = [
    Path.home() / ".profile",
    Path.home() / ".bashrc",
    Path.home() / ".zshrc",
]
_SYSTEM_ENV = Path("/etc/environment")


def _strip_value_quotes(raw: str) -> str:
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    return s


def _parse_env_file(text: str, *, exports_only: bool) -> list[tuple[str, str]]:
    """Parse KEY=value and export KEY=value lines; skip comments and blanks."""
    out: list[tuple[str, str]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            rest = s[7:].lstrip()
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", rest)
            if m:
                out.append((m.group(1), _strip_value_quotes(m.group(2))))
            continue
        if exports_only:
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", s)
        if m:
            out.append((m.group(1), _strip_value_quotes(m.group(2))))
    return out


def parse_etc_environment(text: str) -> list[tuple[str, str]]:
    """Parse /etc/environment (KEY=value per line, no export keyword)."""
    return _parse_env_file(text, exports_only=False)


def parse_shell_file(text: str) -> list[tuple[str, str]]:
    """Parse shell rc/profile: export and bare assignments."""
    return _parse_env_file(text, exports_only=False)


def path_value_warnings(value: str) -> list[str]:
    """Return warnings for PATH-like values (Phase 5 validation)."""
    warnings: list[str] = []
    if not value.strip():
        return warnings
    parts = value.split(":")
    if "/usr/bin" not in parts and "/bin" not in parts:
        warnings.append("PATH does not include /usr/bin or /bin — your shell may break.")
    return warnings


@dataclass
class EnvVarEntry:
    """A single environment variable entry."""

    key: str
    value: str
    scope: str = "User"  # "User" or "System"
    description: str = ""
    source_file: str | None = None
    managed: bool = field(default=False, repr=False)


class EnvVarManager(BaseUtilityManager):
    """Loads env vars from profile files; saves edits to a managed snippet file."""

    def __init__(self) -> None:
        super().__init__()
        self._vars: list[EnvVarEntry] = []

    async def initialize(self) -> bool:
        """Load variables from /etc/environment, user shell files, and managed snippet."""
        if self._initialized:
            return True

        merged: dict[str, EnvVarEntry] = {}

        if _SYSTEM_ENV.is_file():
            try:

                def _read() -> str:
                    return _SYSTEM_ENV.read_text(encoding="utf-8", errors="replace")

                text = await asyncio.to_thread(_read)
                for key, val in parse_etc_environment(text):
                    merged[key] = EnvVarEntry(
                        key=key,
                        value=val,
                        scope="System",
                        description=f"from {_SYSTEM_ENV}",
                        source_file=str(_SYSTEM_ENV),
                    )
            except OSError as e:
                log.debug("Could not read %s: %s", _SYSTEM_ENV, e)

        for uf in _USER_FILES:
            if not uf.is_file():
                continue
            try:

                def _read_u(p: Path = uf) -> str:
                    return p.read_text(encoding="utf-8", errors="replace")

                text = await asyncio.to_thread(_read_u)
                for key, val in parse_shell_file(text):
                    merged[key] = EnvVarEntry(
                        key=key,
                        value=val,
                        scope="User",
                        description=f"from {uf.name}",
                        source_file=str(uf),
                    )
            except OSError as e:
                log.debug("Could not read %s: %s", uf, e)

        if _MANAGED_FILE.is_file():
            try:

                def _read_m() -> str:
                    return _MANAGED_FILE.read_text(encoding="utf-8", errors="replace")

                text = await asyncio.to_thread(_read_m)
                for key, val in parse_shell_file(text):
                    merged[key] = EnvVarEntry(
                        key=key,
                        value=val,
                        scope="User",
                        description="saved by HypeDevHome",
                        source_file=str(_MANAGED_FILE),
                        managed=True,
                    )
            except OSError as e:
                log.warning("Could not read managed env file: %s", e)

        # Ensure common keys visible when files were sparse (tests / minimal home).
        for key in ("PATH", "HOME", "USER", "SHELL", "EDITOR"):
            if key not in merged and key in os.environ:
                merged[key] = EnvVarEntry(
                    key=key,
                    value=os.environ[key],
                    scope="User",
                    description="current process environment",
                    source_file=None,
                )

        self._vars = sorted(merged.values(), key=lambda e: e.key.upper())
        self._initialized = True
        return True

    def get_variables(self) -> list[EnvVarEntry]:
        """Return all merged environment variables."""
        return self._vars

    def _mask_for_display(self, entry: EnvVarEntry) -> str:
        k = entry.key.upper()
        if any(x in k for x in ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "PRIVATE_KEY")):
            return "(hidden)"
        return entry.value

    def get_display_variables(self) -> list[EnvVarEntry]:
        """Entries with sensitive values masked for UI listing."""
        return [
            EnvVarEntry(
                key=e.key,
                value=self._mask_for_display(e),
                scope=e.scope,
                description=e.description,
                source_file=e.source_file,
                managed=e.managed,
            )
            for e in self._vars
        ]

    async def add_variable(self, key: str, value: str, scope: str = "User") -> bool:
        """Append a variable to the managed snippet (User scope only for writes)."""
        key = key.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            return False
        if any(v.key == key for v in self._vars):
            log.warning("Duplicate key: %s", key)
            return False
        await self._write_managed_merge({key: value})
        await self._reload_from_disk()
        return True

    async def update_variable(self, index: int, key: str, value: str) -> bool:
        """Update by index: writes an override for this key into the managed file."""
        if not (0 <= index < len(self._vars)):
            return False
        prev = self._vars[index]
        key = key.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            return False
        drop = prev.key if prev.key != key else None
        await self._write_managed_merge({key: value}, drop_key=drop)
        await self._reload_from_disk()
        return True

    async def remove_variable(self, index: int) -> bool:
        """Remove a key from the managed file if present; otherwise drop override."""
        if not (0 <= index < len(self._vars)):
            return False
        prev = self._vars[index]
        await self._write_managed_merge({}, drop_key=prev.key)
        await self._reload_from_disk()
        return True

    async def _reload_from_disk(self) -> None:
        self._initialized = False
        self._vars = []
        await self.initialize()

    async def _write_managed_merge(
        self,
        upsert: dict[str, str],
        drop_key: str | None = None,
    ) -> None:
        """Read managed file, apply removals/updates, write exports."""
        await asyncio.to_thread(_MANAGED_DIR.mkdir, parents=True, exist_ok=True)

        existing: dict[str, str] = {}
        if _MANAGED_FILE.is_file():

            def _backup_existing() -> None:
                bak = _MANAGED_FILE.with_suffix(_MANAGED_FILE.suffix + ".bak")
                shutil.copy2(_MANAGED_FILE, bak)

            await asyncio.to_thread(_backup_existing)

            def _read() -> str:
                return _MANAGED_FILE.read_text(encoding="utf-8", errors="replace")

            text = await asyncio.to_thread(_read)
            for k, v in parse_shell_file(text):
                existing[k] = v

        if drop_key and drop_key in existing:
            del existing[drop_key]
        existing.update(upsert)

        if not existing:

            def _unlink() -> None:
                if _MANAGED_FILE.exists():
                    _MANAGED_FILE.unlink()

            await asyncio.to_thread(_unlink)
            log.info("Removed empty managed environment file: %s", _MANAGED_FILE)
            return

        header = f"# Generated by HypeDevHome — add to your shell: source '{_MANAGED_FILE}'\n"
        lines = [header] + [
            "export " + k + "=" + _shell_quote(v) for k, v in sorted(existing.items())
        ]
        body = "\n".join(lines) + "\n"

        def _write() -> None:
            _MANAGED_FILE.write_text(body, encoding="utf-8")

        await asyncio.to_thread(_write)
        log.info("Wrote managed environment file: %s", _MANAGED_FILE)

    def get_status(self) -> dict[str, Any]:
        return {
            "var_count": len(self._vars),
            "initialized": self._initialized,
            "managed_file": str(_MANAGED_FILE),
        }


def _shell_quote(val: str) -> str:
    if re.match(r"^[a-zA-Z0-9_@%+=:,./-]+$", val):
        return val
    return "'" + val.replace("'", "'\"'\"'") + "'"
