"""Tests for Distrobox stack functionality."""

from unittest.mock import AsyncMock

import pytest

from core.setup.environments import EnvironmentManager
from core.setup.stack_manager import StackManager, StackTemplate


@pytest.fixture
def mock_executor():
    """Mock HostExecutor."""
    executor = AsyncMock()
    executor.run_async = AsyncMock()
    return executor


@pytest.fixture
def mock_env_manager(mock_executor):
    """Mock EnvironmentManager."""
    env_manager = EnvironmentManager(mock_executor)
    env_manager.has_distrobox = True
    env_manager.has_podman = True
    env_manager.create_distrobox = AsyncMock(return_value=True)
    env_manager.list_environments = AsyncMock(return_value=[])
    return env_manager


@pytest.fixture
def stack_manager(mock_executor, mock_env_manager):
    """Create StackManager with mocks."""
    return StackManager(mock_executor, mock_env_manager)


class TestStackManager:
    """Test StackManager functionality."""

    def test_load_catalog(self, stack_manager):
        """Test that stack catalog loads correctly."""
        stacks = stack_manager.get_available_stacks()
        assert len(stacks) > 0
        assert all(isinstance(stack, StackTemplate) for stack in stacks)

        # Check specific stacks
        stack_ids = [stack.id for stack in stacks]
        assert "python_ds" in stack_ids
        assert "node_web" in stack_ids
        assert "rust_backend" in stack_ids
        assert "go_services" in stack_ids

    def test_get_stack(self, stack_manager):
        """Test retrieving specific stack by ID."""
        python_stack = stack_manager.get_stack("python_ds")
        assert python_stack is not None
        assert python_stack.id == "python_ds"
        assert python_stack.name == "Python Data Science"
        assert len(python_stack.packages) > 0

        # Test non-existent stack
        assert stack_manager.get_stack("non_existent") is None

    @pytest.mark.asyncio
    async def test_instantiate_stack_success(self, stack_manager, mock_executor, mock_env_manager):
        """Test successful stack instantiation."""
        # Mock successful package installation
        mock_executor.run_async.return_value.success = True

        # Test instantiation
        success = await stack_manager.instantiate_stack("python_ds", container_name="test-python")

        assert success is True
        mock_env_manager.create_distrobox.assert_called_once()

        # Verify create_distrobox was called with correct arguments
        call_args = mock_env_manager.create_distrobox.call_args
        # The first positional argument should be the name
        assert call_args.args[0] == "test-python"
        # Check kwargs for image
        assert "fedora:latest" in call_args.kwargs.get("image", "")

    @pytest.mark.asyncio
    async def test_instantiate_stack_not_found(self, stack_manager):
        """Test stack instantiation with non-existent stack ID."""
        success = await stack_manager.instantiate_stack("non_existent")
        assert success is False

    @pytest.mark.asyncio
    async def test_instantiate_stack_container_failure(self, stack_manager, mock_env_manager):
        """Test stack instantiation when container creation fails."""
        mock_env_manager.create_distrobox.return_value = False

        success = await stack_manager.instantiate_stack("python_ds")
        assert success is False

    @pytest.mark.asyncio
    async def test_install_packages_in_container(self, stack_manager, mock_executor):
        """Test package installation in container."""
        template = stack_manager.get_stack("python_ds")

        # Mock successful execution
        mock_executor.run_async.return_value.success = True

        success = await stack_manager._install_packages_in_container("test-container", template)
        assert success is True

        # Verify command was executed
        mock_executor.run_async.assert_called_once()
        cmd = mock_executor.run_async.call_args[0][0]
        assert "distrobox" in cmd[0]
        assert "enter" in cmd[1]
        assert "test-container" in cmd[2]

    @pytest.mark.asyncio
    async def test_run_command_in_container(self, stack_manager, mock_executor):
        """Test running command in container."""
        mock_executor.run_async.return_value.success = True

        success = await stack_manager._run_command_in_container("test-container", "echo hello")
        assert success is True

        cmd = mock_executor.run_async.call_args[0][0]
        assert "distrobox" in cmd[0]
        assert "enter" in cmd[1]
        assert "bash" in cmd
        assert "-c" in cmd

    @pytest.mark.asyncio
    async def test_export_tools_from_container(self, stack_manager, mock_executor):
        """Test exporting tools from container."""
        mock_executor.run_async.return_value.success = True

        tools = ["python3", "pip"]
        await stack_manager._export_tools_from_container("test-container", tools)

        # Should be called twice (once per tool)
        assert mock_executor.run_async.call_count == 2

        # Verify export commands
        calls = mock_executor.run_async.call_args_list
        for i, tool in enumerate(tools):
            cmd = calls[i][0][0]
            assert "distrobox-export" in cmd
            assert f"/usr/bin/{tool}" in cmd

    @pytest.mark.asyncio
    async def test_list_running_stacks(self, stack_manager, mock_env_manager):
        """Test listing running stacks."""
        # Mock existing environments
        mock_env_manager.list_environments.return_value = ["python_ds", "node_web"]

        stacks = await stack_manager.list_running_stacks()

        assert len(stacks) == 2
        assert stacks[0]["name"] == "python_ds"
        assert stacks[0]["template"] == "Python Data Science"
        assert stacks[0]["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_stack_status(self, stack_manager, mock_executor):
        """Test getting stack status."""
        # Mock distrobox list output
        mock_output = "python_ds  fedora:latest  Up 2 weeks  1.2GB"
        mock_executor.run_async.return_value.success = True
        mock_executor.run_async.return_value.stdout = mock_output

        status = await stack_manager.get_stack_status("python_ds")

        assert status["name"] == "python_ds"
        assert status["exists"] is True
        assert status["running"] is True


class TestStackTemplate:
    """Test StackTemplate dataclass."""

    def test_stack_template_creation(self):
        """Test StackTemplate instantiation."""
        template = StackTemplate(
            id="test",
            name="Test Stack",
            description="Test description",
            icon="test-icon",
            image="test:latest",
            packages=["pkg1", "pkg2"],
            init_commands=["cmd1", "cmd2"],
            exports=["tool1"],
            env_vars={"KEY": "value"},
            volumes=["/host:/container"],
            init_script="echo hello",
        )

        assert template.id == "test"
        assert template.name == "Test Stack"
        assert len(template.packages) == 2
        assert len(template.init_commands) == 2
        assert len(template.exports) == 1
        assert template.env_vars["KEY"] == "value"
        assert len(template.volumes) == 1
        assert template.init_script == "echo hello"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
