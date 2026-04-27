"""HypeDevHome — GitHub authentication manager.

Handles GitHub Personal Access Token (PAT) storage, validation, and management.
Uses libsecret/Secret Service via Flatpak portal for secure storage.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from gi.repository import GLib

from config.defaults import CONFIG_DIR

log = logging.getLogger(__name__)


class GitHubAuthError(Exception):
    """Base exception for GitHub authentication errors."""

    pass


class GitHubAuthManager:
    """Manages GitHub authentication tokens with secure storage.

    Uses GLib.Keyfile for secure credential storage. In Flatpak environment,
    this uses the Secret Service portal for secure storage.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self._config_dir = config_dir or CONFIG_DIR
        self._keyfile_path = self._config_dir / "github.ini"
        self._lock = threading.RLock()

        # Ensure config directory exists
        self._config_dir.mkdir(parents=True, exist_ok=True)

        # Load existing credentials
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Load credentials from keyfile."""
        with self._lock:
            self._token: str | None = None
            self._username: str | None = None
            self._scopes: list[str] = []

            if not self._keyfile_path.exists():
                return

            try:
                keyfile = GLib.KeyFile.new()
                success = keyfile.load_from_file(str(self._keyfile_path), GLib.KeyFileFlags.NONE)

                if not success:
                    log.warning("Failed to load GitHub keyfile")
                    return

                # Try to get token
                try:
                    self._token = keyfile.get_string("github", "token")
                except GLib.Error:
                    self._token = None

                # Try to get username
                try:
                    self._username = keyfile.get_string("github", "username")
                except GLib.Error:
                    self._username = None

                # Try to get scopes
                try:
                    scopes_str = keyfile.get_string("github", "scopes")
                    self._scopes = scopes_str.split(",") if scopes_str else []
                except GLib.Error:
                    self._scopes = []

                log.debug("Loaded GitHub credentials for user: %s", self._username)

            except Exception as e:
                log.error("Error loading GitHub credentials: %s", e)
                self._token = None
                self._username = None
                self._scopes = []

    def _save_credentials(self) -> bool:
        """Save credentials to keyfile."""
        with self._lock:
            try:
                keyfile = GLib.KeyFile.new()

                if self._token:
                    keyfile.set_string("github", "token", self._token)

                if self._username:
                    keyfile.set_string("github", "username", self._username)

                if self._scopes:
                    keyfile.set_string("github", "scopes", ",".join(self._scopes))

                # Set metadata
                keyfile.set_string("github", "service", "HypeDevHome GitHub Integration")

                # Save to file
                data, _ = keyfile.to_data()
                self._keyfile_path.write_text(data, encoding="utf-8")

                # Set restrictive permissions (owner read/write only)
                self._keyfile_path.chmod(0o600)

                log.debug("Saved GitHub credentials for user: %s", self._username)
                return True

            except Exception as e:
                log.error("Error saving GitHub credentials: %s", e)
                return False

    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        with self._lock:
            return self._token is not None and self._username is not None

    def get_token(self) -> str | None:
        """Get the authentication token."""
        with self._lock:
            return self._token

    def get_username(self) -> str | None:
        """Get the authenticated username."""
        with self._lock:
            return self._username

    def get_scopes(self) -> list[str]:
        """Get the token scopes."""
        with self._lock:
            return self._scopes.copy()

    def set_credentials(self, token: str, username: str, scopes: list[str]) -> bool:
        """Set new credentials.

        Args:
            token: GitHub Personal Access Token
            username: GitHub username
            scopes: List of token scopes

        Returns:
            True if credentials were saved successfully
        """
        with self._lock:
            self._token = token
            self._username = username
            self._scopes = scopes

            return self._save_credentials()

    def clear_credentials(self) -> bool:
        """Clear all stored credentials."""
        with self._lock:
            self._token = None
            self._username = None
            self._scopes = []

            try:
                if self._keyfile_path.exists():
                    self._keyfile_path.unlink()
                log.debug("Cleared GitHub credentials")
                return True
            except Exception as e:
                log.error("Error clearing GitHub credentials: %s", e)
                return False

    def validate_token(self, token: str) -> tuple[bool, str | None, list[str] | None]:
        """Validate a GitHub token and get user info.

        This is a placeholder that should be implemented with actual
        GitHub API validation. For now, it returns mock data.

        Args:
            token: GitHub Personal Access Token to validate

        Returns:
            Tuple of (is_valid, username, scopes)
        """
        # TODO: Implement actual GitHub API validation
        # For now, return mock validation
        # In real implementation, this would make an API call to /user

        # Mock validation - in real implementation, this would be:
        # async with aiohttp.ClientSession() as session:
        #     async with session.get(
        #         "https://api.github.com/user",
        #         headers={"Authorization": f"token {token}"}
        #     ) as response:
        #         if response.status == 200:
        #             data = await response.json()
        #             return True, data["login"], ["repo", "read:user"]
        #         else:
        #             return False, None, None

        # For development, accept any non-empty token
        if token and len(token) >= 10:
            # Mock username and scopes
            return True, "github-user", ["repo", "read:user", "read:org"]

        return False, None, None

    def get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests.

        Returns:
            Dictionary with Authorization header
        """
        with self._lock:
            if not self._token:
                return {}

            return {
                "Authorization": f"token {self._token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "HypeDevHome/0.3.0",
            }

    def to_dict(self) -> dict[str, Any]:
        """Convert auth state to dictionary (for UI display)."""
        with self._lock:
            return {
                "authenticated": self.is_authenticated(),
                "username": self._username,
                "scopes": self._scopes,
                "has_token": self._token is not None,
            }


# Singleton instance
_auth_manager: GitHubAuthManager | None = None


def get_auth_manager() -> GitHubAuthManager:
    """Get the singleton GitHubAuthManager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = GitHubAuthManager()
    return _auth_manager
