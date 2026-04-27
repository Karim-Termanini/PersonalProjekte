"""HypeDevHome — Setup Engine Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class SetupStepType(Enum):
    """Types of setup steps."""

    APPS = auto()
    REPOS = auto()
    ENVIRONMENTS = auto()
    SYNC = auto()
    CONFIG = auto()
    EXECUTION = auto()


class SetupStatus(Enum):
    """Status of a setup task."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class AppInfo:
    """Information about an application to install."""

    id: str
    name: str
    description: str
    icon: str
    package_name: str  # Default package name
    flatpak_id: str | None = None
    desktop_path: str | None = None  # If from .desktop scan; used to resolve RPM/DEB name
    category: str = "Development"
    ui_category: str = "all apps"
    selected: bool = False
    force_system_pkg: bool = False  # Prefer system pkg over flatpak
    status: SetupStatus = SetupStatus.PENDING


@dataclass
class RepoInfo:
    """Information about a repository to clone."""

    url: str
    target_path: str
    name: str | None = None
    branch: str = "main"
    status: SetupStatus = SetupStatus.PENDING


@dataclass
class SetupConfig:
    """Configuration for the setup process."""

    apps: list[AppInfo] = field(default_factory=list)
    repos: list[RepoInfo] = field(default_factory=list)
    dev_folder: str = "~/Dev"
    setup_git: bool = True
    setup_aliases: bool = True
    setup_ssh_agent: bool = True
    btrfs_subvolume: bool = False
    git_user_name: str | None = None
    git_user_email: str | None = None
    env_vars: dict[str, str] = field(default_factory=dict)

    # Phase 5 Isolation & Sync
    selected_stacks: list[str] = field(default_factory=list)
    stack_names: dict[str, str] = field(default_factory=dict)  # ID -> Custom Name
    use_distrobox: bool = True
    sync_dotfiles: bool = False
    dotfiles_url: str | None = None
    sync_secrets: bool = False
    sync_ssh_keys: bool = False
    ssh_key_whitelist: list[str] = field(default_factory=lambda: ["id_rsa", "id_ed25519"])
    token_whitelist: list[str] = field(default_factory=lambda: ["GITHUB_TOKEN", "HYPE_SECRET"])
