"""Integration tests for the complete Machine Setup system."""

from unittest.mock import AsyncMock, patch

import pytest

from core.setup.config_backup import ConfigBackupManager
from core.setup.dev_folder import DevFolderCreator
from core.setup.dev_settings import DevSettingsApplier
from core.setup.distro_detector import DistroInfo
from core.setup.environments import EnvironmentManager
from core.setup.git_ops import GitOperations
from core.setup.host_executor import CommandResult, HostExecutor
from core.setup.models import AppInfo, SetupStatus
from core.setup.package_installer import PackageInstaller


@pytest.fixture
def mock_executor():
    with patch(
        "core.setup.host_executor.HostExecutor.run_async", new_callable=AsyncMock
    ) as m_async:
        yield m_async


@pytest.fixture
def sample_distro_info():
    return DistroInfo(
        distro="fedora",
        version="43",
        package_manager="dnf",
        has_flatpak=True,
        has_snap=False,
        id_like=["rhel", "fedora"],
        pretty_name="Fedora Linux 43",
        is_flatpak=False,
    )


class TestCompleteIntegration:
    """Test the complete integration of all Phase 4 components."""

    @pytest.mark.asyncio
    async def test_package_installer_with_catalog(self, mock_executor, sample_distro_info):
        """Test that PackageInstaller integrates with PackageCatalog."""
        m_async = mock_executor

        # Mock distro detection
        with patch("core.setup.distro_detector.DistroDetector.detect") as mock_detect:
            mock_detect.return_value = sample_distro_info

            # Mock package catalog
            with (
                patch("core.setup.package_catalog.PackageCatalog.load") as mock_load,
                patch(
                    "core.setup.package_catalog.PackageCatalog.get_all_packages"
                ) as mock_get_all,
                patch(
                    "core.setup.package_catalog.PackageCatalog.get_package_for_distro"
                ) as mock_get_for_distro,
            ):
                mock_load.return_value = True
                # Return some sample packages
                from core.setup.package_catalog import PackageEntry

                mock_packages = [
                    PackageEntry(
                        id="git",
                        name="Git",
                        description="Version control",
                        category="tools",
                        icon="git-symbolic",
                        flatpak_id=None,
                        apt_package="git",
                        dnf_package="git",
                        pacman_package="git",
                    ),
                    PackageEntry(
                        id="neovim",
                        name="Neovim",
                        description="Editor",
                        category="editors",
                        icon="nvim-symbolic",
                        flatpak_id="io.neovim.nvim",
                        apt_package="neovim",
                        dnf_package="neovim",
                        pacman_package="neovim",
                    ),
                ]
                mock_get_all.return_value = mock_packages
                # Mock getting package for distro
                mock_app = AppInfo(
                    id="git",
                    name="Git",
                    description="Version control",
                    icon="git-symbolic",
                    package_name="git",
                )
                mock_get_for_distro.return_value = mock_app

                # Mock which commands for package manager detection
                async def mock_run_async(cmd, root=False):
                    if cmd[0] == "which":
                        command = cmd[1]
                        if command in ["dnf", "flatpak"]:
                            return CommandResult(
                                stdout=f"/usr/bin/{command}", stderr="", returncode=0, command=cmd
                            )
                        return CommandResult(stdout="", stderr="", returncode=1, command=cmd)
                    return CommandResult(stdout="", stderr="", returncode=0, command=cmd)

                m_async.side_effect = mock_run_async

                executor = HostExecutor()
                installer = PackageInstaller(executor)

                # Initialize
                initialized = await installer.initialize()
                assert initialized is True
                assert installer._initialized is True

                # Get available packages
                packages = await installer.get_available_packages()
                assert isinstance(packages, list)
                # Should have packages from catalog
                assert len(packages) > 0

                # Test getting a specific package
                git_app = await installer.get_app_from_catalog("git")
                assert git_app is not None
                assert git_app.name == "Git"
                assert git_app.package_name == "git"  # Should use dnf_package for fedora

    @pytest.mark.asyncio
    async def test_git_operations_integration(self, mock_executor):
        """Test GitOperations integration."""
        m_async = mock_executor
        m_async.return_value = CommandResult(stdout="", stderr="", returncode=0, command=[])

        executor = HostExecutor()
        git_ops = GitOperations(executor)

        # Test URL validation
        valid = await git_ops._validate_git_url("https://github.com/user/repo.git")
        assert valid is True

        # Test clone (mocked)
        success = await git_ops.clone(
            url="https://github.com/user/repo.git",
            target_path="/tmp/test/repo",
            progress_callback=None,
        )
        assert success is True

    @pytest.mark.asyncio
    async def test_agent_c_components_integration(self, mock_executor):
        """Test Agent C components integration."""
        m_async = mock_executor
        m_async.return_value = CommandResult(stdout="", stderr="", returncode=0, command=[])

        executor = HostExecutor()

        # Test DevFolderCreator
        dev_creator = DevFolderCreator(executor)
        result = await dev_creator.create_dev_folder("/tmp/Dev", use_btrfs=False)
        assert result.success is True

        # Test DevSettingsApplier
        settings_applier = DevSettingsApplier(executor)
        result = await settings_applier.apply_settings(
            git_name="Test User",
            git_email="test@example.com",
            git_editor="nvim",
            enable_aliases=True,
            enable_hidden_files=True,
            enable_file_extensions=True,
            enable_ssh_agent=True,
        )
        assert result.success is True

        # Test ConfigBackupManager
        backup_manager = ConfigBackupManager(executor)
        result = await backup_manager.create_backup("Test backup")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_environment_manager_integration(self, mock_executor):
        """Test EnvironmentManager integration."""
        m_async = mock_executor

        async def mock_run_async(cmd, root=False, **_kwargs):
            if cmd[0] == "which":
                command = cmd[1]
                if command in ["distrobox", "podman", "docker"]:
                    return CommandResult(
                        stdout=f"/usr/bin/{command}", stderr="", returncode=0, command=cmd
                    )
                return CommandResult(stdout="", stderr="", returncode=1, command=cmd)
            return CommandResult(stdout="", stderr="", returncode=0, command=cmd)

        m_async.side_effect = mock_run_async

        executor = HostExecutor()
        env_manager = EnvironmentManager(executor)

        await env_manager.initialize()

        # Should detect distrobox and podman
        assert env_manager.has_distrobox is True
        assert env_manager.has_podman is True

    @pytest.mark.asyncio
    async def test_complete_setup_flow(self, mock_executor, sample_distro_info):
        """Test a complete setup flow with all components."""
        m_async = mock_executor

        # Mock all the necessary responses
        async def mock_run_async(cmd, root=False, **_kwargs):
            # Package manager detection
            if cmd[0] == "which":
                command = cmd[1]
                if command in ["dnf", "flatpak", "git"]:
                    return CommandResult(
                        stdout=f"/usr/bin/{command}", stderr="", returncode=0, command=cmd
                    )
                return CommandResult(stdout="", stderr="", returncode=1, command=cmd)

            # Git clone
            if cmd[0] == "git" and cmd[1] == "clone":
                return CommandResult(stdout="", stderr="", returncode=0, command=cmd)

            # Directory creation
            if cmd[0] == "mkdir":
                return CommandResult(stdout="", stderr="", returncode=0, command=cmd)

            # Default success
            return CommandResult(stdout="", stderr="", returncode=0, command=cmd)

        m_async.side_effect = mock_run_async

        # Mock distro detection
        with patch("core.setup.distro_detector.DistroDetector.detect") as mock_detect:
            mock_detect.return_value = sample_distro_info

            # Mock package catalog
            with (
                patch("core.setup.package_catalog.PackageCatalog.load") as mock_load,
                patch(
                    "core.setup.package_catalog.PackageCatalog.get_all_packages"
                ) as mock_get_all,
                patch(
                    "core.setup.package_catalog.PackageCatalog.get_package_for_distro"
                ) as mock_get_for_distro,
            ):
                mock_load.return_value = True
                # Return some sample packages
                from core.setup.package_catalog import PackageEntry

                mock_packages = [
                    PackageEntry(
                        id="git",
                        name="Git",
                        description="Version control",
                        category="tools",
                        icon="git-symbolic",
                        flatpak_id=None,
                        apt_package="git",
                        dnf_package="git",
                        pacman_package="git",
                    ),
                    PackageEntry(
                        id="neovim",
                        name="Neovim",
                        description="Editor",
                        category="editors",
                        icon="nvim-symbolic",
                        flatpak_id="io.neovim.nvim",
                        apt_package="neovim",
                        dnf_package="neovim",
                        pacman_package="neovim",
                    ),
                ]
                mock_get_all.return_value = mock_packages
                # Mock getting package for distro
                mock_app = AppInfo(
                    id="git",
                    name="Git",
                    description="Version control",
                    icon="git-symbolic",
                    package_name="git",
                )
                mock_get_for_distro.return_value = mock_app

                executor = HostExecutor()

                # Create all components
                installer = PackageInstaller(executor)
                git_ops = GitOperations(executor)
                dev_creator = DevFolderCreator(executor)
                settings_applier = DevSettingsApplier(executor)
                backup_manager = ConfigBackupManager(executor)
                env_manager = EnvironmentManager(executor)

                # Initialize installer
                await installer.initialize()

                # Get apps
                apps = await installer.get_available_packages()
                assert len(apps) > 0

                # Select some apps
                for app in apps[:3]:  # Select first 3 apps
                    app.selected = True

                # Install apps
                success = await installer.install_apps(apps[:3])
                assert success is True

                # Check app status
                for app in apps[:3]:
                    assert app.status == SetupStatus.COMPLETED

                # Create dev folder
                dev_result = await dev_creator.create_dev_folder("/tmp/Dev", use_btrfs=False)
                assert dev_result.success is True

                # Create backup
                backup_result = await backup_manager.create_backup("Integration test backup")
                assert backup_result.success is True

                # Apply settings
                settings_result = await settings_applier.apply_settings(
                    git_name="Integration Test",
                    git_email="test@integration.example.com",
                    enable_aliases=True,
                )
                assert settings_result.success is True

                # Clone repo
                clone_success = await git_ops.clone(
                    url="https://github.com/test/repo.git",
                    target_path="/tmp/Dev/repo",
                )
                assert clone_success is True

                # Initialize environment manager
                await env_manager.initialize()
                # Should have initialized without error

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, mock_executor):
        """Test error handling across components."""
        m_async = mock_executor

        # Mock a failing command
        async def mock_run_async(cmd, root=False):
            # Simulate a failure for package installation
            if cmd[0] == "dnf" and cmd[1] == "install":
                return CommandResult(
                    stdout="",
                    stderr="Package not found",
                    returncode=1,
                    command=cmd,
                )
            # Default success for other commands
            return CommandResult(stdout="", stderr="", returncode=0, command=cmd)

        m_async.side_effect = mock_run_async

        executor = HostExecutor()

        # Create a package manager that will fail
        with patch("core.setup.package_manager.DnfManager.install") as mock_install:
            mock_install.return_value = False

            # Create installer
            with patch("core.setup.distro_detector.DistroDetector.detect") as mock_detect:
                mock_detect.return_value = DistroInfo(
                    distro="fedora",
                    version="43",
                    package_manager="dnf",
                    has_flatpak=True,
                    has_snap=False,
                    id_like=[],
                    pretty_name="Fedora",
                    is_flatpak=False,
                )

                with patch("core.setup.package_catalog.PackageCatalog.load") as mock_load:
                    mock_load.return_value = True

                    installer = PackageInstaller(executor)
                    await installer.initialize()

                    # Create an app that will fail to install
                    app = AppInfo(
                        id="test-fail",
                        name="Test Fail",
                        description="Test",
                        icon="test",
                        package_name="test-fail-package",
                    )
                    app.selected = True

                    # Install should fail gracefully
                    success = await installer.install_app(app)
                    assert success is False
                    assert app.status == SetupStatus.FAILED

    @pytest.mark.asyncio
    async def test_install_app_one_click_success_mocked(self, mock_executor, sample_distro_info):
        """Single-app install path (Workstation Apps) succeeds when DnfManager.install succeeds."""
        m_async = mock_executor

        async def mock_run_async(cmd, root=False):
            if cmd[0] == "which" and len(cmd) > 1 and cmd[1] in ("dnf", "flatpak"):
                return CommandResult(
                    stdout=f"/usr/bin/{cmd[1]}",
                    stderr="",
                    returncode=0,
                    command=cmd,
                )
            return CommandResult(stdout="", stderr="", returncode=0, command=cmd)

        m_async.side_effect = mock_run_async

        executor = HostExecutor()
        with (
            patch("core.setup.distro_detector.DistroDetector.detect") as mock_detect,
            patch("core.setup.package_catalog.PackageCatalog.load") as mock_load,
            patch(
                "core.setup.package_manager.DnfManager.install",
                new_callable=AsyncMock,
            ) as mock_dnf_install,
        ):
            mock_detect.return_value = sample_distro_info
            mock_load.return_value = True
            mock_dnf_install.return_value = True

            installer = PackageInstaller(executor)
            await installer.initialize()

            app = AppInfo(
                id="ripgrep",
                name="ripgrep",
                description="line search",
                icon="text-x-generic-symbolic",
                package_name="ripgrep",
            )
            ok = await installer.install_app(app)
            assert ok is True
            assert app.status == SetupStatus.COMPLETED
