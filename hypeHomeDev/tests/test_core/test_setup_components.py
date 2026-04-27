"""Tests for Phase 4 Core Setup components (Agent B)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.setup.distro_detector import DistroDetector, DistroInfo
from core.setup.git_ops import (
    GitOperations,
    canonical_git_remote,
    remotes_equivalent,
)
from core.setup.host_executor import CommandResult, HostExecutor
from core.setup.models import RepoInfo
from core.setup.package_catalog import PackageCatalog, PackageEntry
from core.setup.package_installer import PackageInstaller
from core.setup.package_manager import (
    AptManager,
    DnfManager,
    FlatpakManager,
    PackageManagerFactory,
    PacmanManager,
)


@pytest.fixture
def mock_executor():
    with patch(
        "core.setup.host_executor.HostExecutor.run_async", new_callable=AsyncMock
    ) as m_async:
        yield m_async


@pytest.fixture
def sample_os_release():
    return """NAME="Fedora Linux"
VERSION="43 (Workstation Edition)"
ID=fedora
VERSION_ID=43
VERSION_CODENAME=""
PLATFORM_ID="platform:f43"
PRETTY_NAME="Fedora Linux 43 (Workstation Edition)"
ANSI_COLOR="0;38;2;60;110;180"
LOGO=fedora-logo-icon
CPE_NAME="cpe:/o:fedoraproject:fedora:43"
HOME_URL="https://fedoraproject.org/"
DOCUMENTATION_URL="https://docs.fedoraproject.org/en-US/fedora/f43/system-administrators-guide/"
SUPPORT_URL="https://ask.fedoraproject.org/"
BUG_REPORT_URL="https://bugzilla.redhat.com/"
REDHAT_BUGZILLA_PRODUCT="Fedora"
REDHAT_BUGZILLA_PRODUCT_VERSION=43
REDHAT_SUPPORT_PRODUCT="Fedora"
REDHAT_SUPPORT_PRODUCT_VERSION=43
SUPPORT_END=2026-05-26
VARIANT="Workstation Edition"
VARIANT_ID=workstation
ID_LIKE="rhel fedora"
"""


class TestDistroDetector:
    def test_distro_info_str(self):
        info = DistroInfo(
            distro="fedora",
            version="43",
            package_manager="dnf",
            has_flatpak=True,
            has_snap=False,
            id_like=["rhel", "fedora"],
            pretty_name="Fedora Linux 43",
        )
        assert str(info) == "Fedora Linux 43 (fedora 43)"

    @pytest.mark.asyncio
    async def test_detect(self, mock_executor, sample_os_release):
        m_async = mock_executor

        # Mock responses
        async def mock_run_async(cmd, root=False):
            if cmd == ["cat", "/etc/os-release"]:
                return CommandResult(
                    stdout=sample_os_release,
                    stderr="",
                    returncode=0,
                    command=cmd,
                )
            elif cmd[0] == "which":
                # Mock which responses
                command = cmd[1]
                if command in ["dnf", "flatpak"]:
                    return CommandResult(
                        stdout="/usr/bin/dnf", stderr="", returncode=0, command=cmd
                    )
                else:
                    return CommandResult(stdout="", stderr="", returncode=1, command=cmd)
            return CommandResult(stdout="", stderr="", returncode=0, command=cmd)

        m_async.side_effect = mock_run_async

        executor = HostExecutor()
        detector = DistroDetector(executor)

        info = await detector.detect()

        assert info.distro == "fedora"
        assert info.version == "43"
        assert info.package_manager == "dnf"
        assert info.has_flatpak is True
        assert info.pretty_name == "Fedora Linux 43 (Workstation Edition)"
        assert "rhel" in info.id_like
        assert "fedora" in info.id_like

    @pytest.mark.asyncio
    async def test_is_supported_distro(self, mock_executor):
        m_async = mock_executor

        # Mock a supported distro (Ubuntu)
        async def mock_run_async(cmd, root=False):
            if cmd == ["cat", "/etc/os-release"]:
                return CommandResult(
                    stdout='ID=ubuntu\nVERSION_ID="22.04"\nID_LIKE=debian\nPRETTY_NAME="Ubuntu 22.04"',
                    stderr="",
                    returncode=0,
                    command=cmd,
                )
            elif cmd[0] == "which":
                return CommandResult(stdout="/usr/bin/apt", stderr="", returncode=0, command=cmd)
            return CommandResult(stdout="", stderr="", returncode=0, command=cmd)

        m_async.side_effect = mock_run_async

        executor = HostExecutor()
        detector = DistroDetector(executor)

        supported = await detector.is_supported_distro()
        assert supported is True

    @pytest.mark.asyncio
    async def test_get_supported_package_managers(self, mock_executor):
        m_async = mock_executor

        async def mock_run_async(cmd, root=False):
            if cmd == ["cat", "/etc/os-release"]:
                return CommandResult(
                    stdout='ID=fedora\nVERSION_ID="43"',
                    stderr="",
                    returncode=0,
                    command=cmd,
                )
            elif cmd[0] == "which":
                command = cmd[1]
                if command in ["dnf", "flatpak"]:
                    return CommandResult(
                        stdout=f"/usr/bin/{command}", stderr="", returncode=0, command=cmd
                    )
                return CommandResult(stdout="", stderr="", returncode=1, command=cmd)
            return CommandResult(stdout="", stderr="", returncode=0, command=cmd)

        m_async.side_effect = mock_run_async

        executor = HostExecutor()
        detector = DistroDetector(executor)

        managers = await detector.get_supported_package_managers()
        assert "dnf" in managers
        assert "flatpak" in managers
        assert len(managers) == 2


class TestPackageCatalog:
    def test_package_entry(self):
        entry = PackageEntry(
            id="neovim",
            name="Neovim",
            description="Hyperextensible Vim-based text editor",
            category="editors",
            icon="nvim-symbolic",
            flatpak_id="io.neovim.nvim",
            apt_package="neovim",
            dnf_package="neovim",
            popularity=95,
        )

        assert entry.id == "neovim"
        assert entry.name == "Neovim"
        assert entry.category == "editors"
        assert entry.flatpak_id == "io.neovim.nvim"
        assert entry.popularity == 95

    @pytest.mark.asyncio
    async def test_load_catalog(self, tmp_path):
        # Create a temporary catalog file
        catalog_data = {
            "packages": [
                {
                    "id": "test-app",
                    "name": "Test App",
                    "description": "A test application",
                    "category": "test",
                    "icon": "test-symbolic",
                    "flatpak_id": "org.test.App",
                    "apt_package": "test-app",
                    "dnf_package": "test-app",
                    "popularity": 50,
                }
            ]
        }

        catalog_file = tmp_path / "package_catalog_data.json"
        catalog_file.write_text(json.dumps(catalog_data))

        # Mock the file path
        with patch("core.setup.package_catalog.os.path.join") as mock_join:
            mock_join.return_value = str(catalog_file)

            catalog = PackageCatalog()
            loaded = await catalog.load()

            assert loaded is True
            assert catalog._loaded is True
            assert len(catalog.get_all_packages()) == 1

            package = catalog.get_package("test-app")
            assert package is not None
            assert package.name == "Test App"
            assert package.category == "test"

    def test_search(self):
        catalog = PackageCatalog()
        catalog._packages = [
            PackageEntry(
                id="neovim",
                name="Neovim",
                description="Vim-based editor",
                category="editors",
                icon="",
            ),
            PackageEntry(
                id="vscode",
                name="VS Code",
                description="Microsoft editor",
                category="editors",
                icon="",
            ),
        ]
        catalog._loaded = True

        results = catalog.search("vim")
        assert len(results) == 1
        assert results[0].id == "neovim"

        results = catalog.search("code")
        assert len(results) == 1
        assert results[0].id == "vscode"

    def test_get_package_for_distro(self):
        catalog = PackageCatalog()
        catalog._packages = [
            PackageEntry(
                id="test-app",
                name="Test App",
                description="Test",
                category="test",
                icon="test-symbolic",
                flatpak_id="org.test.App",
                apt_package="test-app-apt",
                dnf_package="test-app-dnf",
                pacman_package="test-app-pacman",
            )
        ]
        catalog._loaded = True

        # Test Ubuntu
        ubuntu_info = DistroInfo(
            distro="ubuntu",
            version="22.04",
            package_manager="apt",
            has_flatpak=True,
            has_snap=False,
            id_like=["debian"],
            pretty_name="Ubuntu 22.04",
        )

        app_info = catalog.get_package_for_distro("test-app", ubuntu_info)
        assert app_info is not None
        assert app_info.package_name == "test-app-apt"
        assert app_info.flatpak_id == "org.test.App"

        # Test Fedora
        fedora_info = DistroInfo(
            distro="fedora",
            version="43",
            package_manager="dnf",
            has_flatpak=True,
            has_snap=False,
            id_like=["rhel", "fedora"],
            pretty_name="Fedora 43",
        )

        app_info = catalog.get_package_for_distro("test-app", fedora_info)
        assert app_info is not None
        assert app_info.package_name == "test-app-dnf"

        # Test Arch
        arch_info = DistroInfo(
            distro="arch",
            version="rolling",
            package_manager="pacman",
            has_flatpak=True,
            has_snap=False,
            id_like=[],
            pretty_name="Arch Linux",
        )

        app_info = catalog.get_package_for_distro("test-app", arch_info)
        assert app_info is not None
        assert app_info.package_name == "test-app-pacman"


class TestPackageManagerFactory:
    def test_create_managers(self, mock_executor):
        executor = MagicMock()

        # Test creating each manager
        managers = ["flatpak", "apt", "dnf", "pacman"]
        for manager_name in managers:
            manager = PackageManagerFactory.create(manager_name, executor)
            assert manager is not None
            assert manager.name == manager_name

        # Test invalid manager
        with pytest.raises(ValueError, match="Unsupported package manager"):
            PackageManagerFactory.create("invalid", executor)

    def test_manager_properties(self, mock_executor):
        executor = MagicMock()

        flatpak = FlatpakManager(executor)
        assert flatpak.name == "flatpak"
        assert flatpak.requires_root is False

        apt = AptManager(executor)
        assert apt.name == "apt"
        assert apt.requires_root is True

        dnf = DnfManager(executor)
        assert dnf.name == "dnf"
        assert dnf.requires_root is True

        pacman = PacmanManager(executor)
        assert pacman.name == "pacman"
        assert pacman.requires_root is True


class TestCanonicalGitRemote:
    def test_https_matches_git_at(self):
        a = "https://github.com/acme/widget.git"
        b = "git@github.com:acme/widget"
        assert canonical_git_remote(a) == canonical_git_remote(b)
        assert remotes_equivalent(a, b)

    def test_remotes_equivalent_false_on_different_repos(self):
        assert not remotes_equivalent(
            "https://github.com/a/x",
            "https://github.com/b/y",
        )


class TestGitOperations:
    @pytest.mark.asyncio
    async def test_validate_git_url(self, mock_executor):
        executor = MagicMock()
        git_ops = GitOperations(executor)

        # Valid URLs
        assert await git_ops._validate_git_url("https://github.com/user/repo.git") is True
        assert await git_ops._validate_git_url("git@github.com:user/repo.git") is True
        assert await git_ops._validate_git_url("git@github.com:user/repo") is True
        assert await git_ops._validate_git_url("ssh://git@github.com:user/repo") is True

        # Invalid URLs
        assert await git_ops._validate_git_url("invalid-url") is False
        assert await git_ops._validate_git_url("") is False
        assert await git_ops._validate_git_url("http://") is False

    @pytest.mark.asyncio
    async def test_setup_git_config(self, mock_executor):
        m_async = mock_executor
        m_async.return_value = CommandResult(stdout="", stderr="", returncode=0, command=[])

        executor = HostExecutor()
        git_ops = GitOperations(executor)

        success = await git_ops.setup_git_config(
            name="Test User", email="test@example.com", editor="nvim"
        )

        assert success is True
        # Should have been called multiple times for different configs
        assert m_async.call_count >= 5

    @pytest.mark.asyncio
    async def test_get_repo_info(self, mock_executor):
        m_async = mock_executor

        responses = [
            # test -d /tmp/test (exists)
            CommandResult(stdout="", stderr="", returncode=0, command=[]),
            # test -d /tmp/test/.git (is git repo)
            CommandResult(stdout="", stderr="", returncode=0, command=[]),
            # git branch --show-current
            CommandResult(stdout="main\n", stderr="", returncode=0, command=[]),
            # git config --get remote.origin.url
            CommandResult(
                stdout="https://github.com/user/repo.git\n", stderr="", returncode=0, command=[]
            ),
            # git status --porcelain
            CommandResult(stdout="", stderr="", returncode=0, command=[]),
        ]

        m_async.side_effect = responses

        executor = HostExecutor()
        git_ops = GitOperations(executor)

        info = await git_ops.get_repo_info("/tmp/test")

        assert info.exists is True
        assert info.is_git_repo is True
        assert info.current_branch == "main"
        assert info.remote_url == "https://github.com/user/repo.git"
        assert info.status == "clean"

    @pytest.mark.asyncio
    async def test_clone_or_update_pulls_when_same_remote(self, mock_executor):
        """Existing clone with matching origin runs git pull instead of failing."""
        m_async = mock_executor
        target = "/home/test/Dev/foo"

        async def mock_run_async(cmd, root=False):
            if cmd[:3] == ["test", "-d", target]:
                return CommandResult(stdout="", stderr="", returncode=0, command=cmd)
            if cmd[:3] == ["test", "-d", f"{target}/.git"]:
                return CommandResult(stdout="", stderr="", returncode=0, command=cmd)
            if cmd[:4] == ["git", "-C", target, "branch"]:
                return CommandResult(stdout="main\n", stderr="", returncode=0, command=cmd)
            if cmd[:6] == ["git", "-C", target, "config", "--get", "remote.origin.url"]:
                return CommandResult(
                    stdout="https://github.com/u/r.git\n", stderr="", returncode=0, command=cmd
                )
            if cmd[:4] == ["git", "-C", target, "status", "--porcelain"]:
                return CommandResult(stdout="", stderr="", returncode=0, command=cmd)
            if cmd[:5] == ["git", "-C", target, "pull", "--rebase"]:
                return CommandResult(stdout="", stderr="", returncode=0, command=cmd)
            return CommandResult(stdout="", stderr="", returncode=1, command=cmd)

        m_async.side_effect = mock_run_async

        executor = HostExecutor()
        git_ops = GitOperations(executor)
        ok = await git_ops.clone_or_update(
            "git@github.com:u/r.git",
            target,
            progress_callback=None,
        )
        assert ok is True

    @pytest.mark.asyncio
    async def test_sync_repository_delegates_to_clone_or_update(self, mock_executor):
        m_async = mock_executor

        calls: list[list[str]] = []

        async def mock_run_async(cmd, root=False):
            calls.append(list(cmd))
            if cmd[:3] == ["test", "-d", "/tmp/newrepo"]:
                return CommandResult(stdout="", stderr="", returncode=1, command=cmd)
            if cmd[:2] == ["mkdir", "-p"]:
                return CommandResult(stdout="", stderr="", returncode=0, command=cmd)
            if cmd[0] == "git" and cmd[1] == "clone":
                return CommandResult(stdout="", stderr="", returncode=0, command=cmd)
            return CommandResult(stdout="", stderr="", returncode=0, command=cmd)

        m_async.side_effect = mock_run_async

        executor = HostExecutor()
        git_ops = GitOperations(executor)
        repo = RepoInfo(
            url="https://github.com/x/y.git",
            target_path="/tmp/newrepo",
            name="y",
            branch="develop",
        )
        ok = await git_ops.sync_repository(repo)
        assert ok is True
        clone_cmds = [c for c in calls if len(c) >= 2 and c[0] == "git" and c[1] == "clone"]
        assert clone_cmds, "expected git clone"
        assert "-b" in clone_cmds[0]
        assert "develop" in clone_cmds[0]


class TestPackageInstaller:
    @pytest.mark.asyncio
    async def test_initialize(self, mock_executor):
        m_async = mock_executor

        # Mock responses for initialization
        async def mock_run_async(cmd, root=False):
            if cmd == ["cat", "/etc/os-release"]:
                return CommandResult(
                    stdout='ID=fedora\nVERSION_ID="43"',
                    stderr="",
                    returncode=0,
                    command=cmd,
                )
            elif cmd[0] == "which":
                command = cmd[1]
                if command in ["dnf", "flatpak"]:
                    return CommandResult(
                        stdout=f"/usr/bin/{command}", stderr="", returncode=0, command=cmd
                    )
                return CommandResult(stdout="", stderr="", returncode=1, command=cmd)
            return CommandResult(stdout="", stderr="", returncode=0, command=cmd)

        m_async.side_effect = mock_run_async

        # Mock package catalog load
        with patch("core.setup.package_catalog.PackageCatalog.load") as mock_load:
            mock_load.return_value = True

            executor = HostExecutor()
            installer = PackageInstaller(executor)

            initialized = await installer.initialize()

            assert initialized is True
            assert installer._initialized is True
            assert "dnf" in installer._package_managers
            assert "flatpak" in installer._package_managers
