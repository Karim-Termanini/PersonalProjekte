"""HypeDevHome — Setup Engine.

One-click development environment setup.
"""

from core.setup.config_backup import ConfigBackupManager
from core.setup.dev_folder import DevFolderCreator
from core.setup.dev_settings import DevSettingsApplier
from core.setup.distro_detector import DistroDetector, DistroInfo
from core.setup.environments import EnvironmentManager
from core.setup.git_ops import (
    GitOperations,
    GitRepoInfo,
    canonical_git_remote,
    remotes_equivalent,
)
from core.setup.host_executor import CommandResult, HostExecutor
from core.setup.models import (
    AppInfo,
    RepoInfo,
    SetupConfig,
    SetupStatus,
    SetupStepType,
)
from core.setup.package_catalog import PackageCatalog, PackageEntry
from core.setup.package_installer import PackageInstaller
from core.setup.package_manager import (
    ApkManager,
    AptManager,
    DnfManager,
    FlatpakManager,
    PackageInfo,
    PackageManager,
    PackageManagerFactory,
    PacmanManager,
    ZypperManager,
)
from core.setup.stack_manager import StackManager, StackTemplate
from core.setup.sync_manager import SyncManager

__all__ = [
    "AppInfo",
    "ApkManager",
    "AptManager",
    "CommandResult",
    "ConfigBackupManager",
    "DevFolderCreator",
    "DevSettingsApplier",
    "DistroDetector",
    "DistroInfo",
    "DnfManager",
    "EnvironmentManager",
    "FlatpakManager",
    "GitOperations",
    "GitRepoInfo",
    "HostExecutor",
    "PackageCatalog",
    "PackageEntry",
    "PackageInfo",
    "PackageInstaller",
    "PackageManager",
    "PackageManagerFactory",
    "PacmanManager",
    "ZypperManager",
    "RepoInfo",
    "SetupConfig",
    "SetupStatus",
    "SetupStepType",
    "StackManager",
    "StackTemplate",
    "SyncManager",
    "canonical_git_remote",
    "remotes_equivalent",
]
