"""Tests for StackManager validation and rollback features."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.setup.stack_manager import StackManager


class TestContainerNameValidation:
    """Test container name validation."""

    def test_valid_container_names(self):
        """Test valid container names."""
        executor = AsyncMock()
        env_manager = MagicMock()
        manager = StackManager(executor, env_manager)

        valid_names = [
            "python-dev",
            "nodejs-20",
            "rust-backend",
            "go123",
            "test_container",
            "a",
            "valid-name-with-dashes",
            "valid_name_with_underscores",
            "mixed-name_with_123",
        ]

        for name in valid_names:
            is_valid, message = manager.validate_container_name(name)
            assert is_valid is True, f"Name '{name}' should be valid: {message}"
            assert message == ""

    def test_invalid_container_names(self):
        """Test invalid container names."""
        executor = AsyncMock()
        env_manager = MagicMock()
        manager = StackManager(executor, env_manager)

        test_cases = [
            ("", "Container name cannot be empty"),
            ("Invalid", "must contain only lowercase letters"),
            ("name with spaces", "must contain only lowercase letters"),
            ("name@special", "must contain only lowercase letters"),
            ("-startswithdash", "Must start and end with alphanumeric character"),
            ("endswithdash-", "Must start and end with alphanumeric character"),
            ("_startswithunderscore", "Must start and end with alphanumeric character"),
            ("endswithunderscore_", "Must start and end with alphanumeric character"),
            ("a" * 65, "Container name too long"),
        ]

        for name, expected_error in test_cases:
            is_valid, message = manager.validate_container_name(name)
            assert is_valid is False, f"Name '{name}' should be invalid"
            assert expected_error.lower() in message.lower(), (
                f"Expected error about '{expected_error}' for '{name}', got: {message}"
            )

    def test_reserved_names(self):
        """Test reserved container names."""
        executor = AsyncMock()
        env_manager = MagicMock()
        manager = StackManager(executor, env_manager)

        reserved_names = ["distrobox", "toolbox", "docker", "podman", "root"]

        for name in reserved_names:
            is_valid, message = manager.validate_container_name(name)
            assert is_valid is False
            assert f"'{name}' is reserved" in message

            # Test case insensitive (lowercase version)
            is_valid, message = manager.validate_container_name(name.lower())
            assert is_valid is False
            assert "reserved" in message.lower()


class TestResourceEstimation:
    """Test resource estimation."""

    @pytest.mark.asyncio
    async def test_estimate_stack_resources(self):
        """Test resource estimation for stacks."""
        executor = AsyncMock()
        env_manager = MagicMock()
        manager = StackManager(executor, env_manager)

        # Create a simple mock with proper attributes
        class MockTemplate:
            def __init__(self):
                self.id = "python_ds"
                self.name = "Python Data Science"
                self.packages = ["python3", "pip", "numpy", "pandas", "matplotlib"]
                self.init_commands = ["pip install scikit-learn"]
                self.exports = ["python3", "jupyter"]
                self.env_vars = {}
                self.volumes = []
                self.init_script = None

        # Mock catalog loading
        manager._stacks = {"python_ds": MockTemplate()}

        result = await manager.estimate_stack_resources("python_ds")

        assert result["stack_id"] == "python_ds"
        assert result["stack_name"] == "Python Data Science"
        assert result["package_count"] == 5
        assert result["init_command_count"] == 1
        assert result["exports_count"] == 2
        assert "estimated_disk_mb" in result
        assert "estimated_disk_gb" in result
        assert "estimated_time_seconds" in result
        assert "estimated_memory_mb" in result

    @pytest.mark.asyncio
    async def test_estimate_stack_resources_not_found(self):
        """Test resource estimation for non-existent stack."""
        executor = AsyncMock()
        env_manager = MagicMock()
        manager = StackManager(executor, env_manager)

        result = await manager.estimate_stack_resources("non_existent")
        assert "error" in result
        assert "Stack not found" in result["error"]


class TestPrerequisiteChecks:
    """Test prerequisite checking."""

    @pytest.mark.asyncio
    async def test_check_prerequisites(self):
        """Test prerequisite checks."""
        executor = AsyncMock()
        env_manager = MagicMock()
        env_manager.initialize = AsyncMock()
        env_manager.has_podman = True
        env_manager.has_docker = False

        manager = StackManager(executor, env_manager)

        # Mock imports
        from unittest.mock import patch

        with patch("shutil.disk_usage") as mock_disk:
            mock_disk.return_value = (1000000000, 300000000, 700000000)  # 0.7GB free

            with patch("socket.create_connection"), patch("os.geteuid", return_value=1000):
                checks = await manager.check_prerequisites()

        assert "container_engine" in checks
        assert "disk_space" in checks
        assert "network" in checks
        assert "permissions" in checks

        # Check container engine
        assert checks["container_engine"]["status"] == "ok"
        assert "available" in checks["container_engine"]["message"]

        # Check disk space (0.7GB is less than 10GB threshold)
        assert checks["disk_space"]["status"] == "warning"
        assert "Low disk space" in checks["disk_space"]["message"]

        # Check network
        assert checks["network"]["status"] == "ok"

        # Check permissions
        assert checks["permissions"]["status"] == "ok"
        assert "regular user" in checks["permissions"]["message"]

    @pytest.mark.asyncio
    async def test_check_prerequisites_no_container_engine(self):
        """Test prerequisite checks with no container engine."""
        executor = AsyncMock()
        env_manager = MagicMock()
        env_manager.initialize = AsyncMock()
        env_manager.has_podman = False
        env_manager.has_docker = False

        manager = StackManager(executor, env_manager)

        checks = await manager.check_prerequisites()

        assert checks["container_engine"]["status"] == "warning"
        assert "No container engine found" in checks["container_engine"]["message"]

    @pytest.mark.asyncio
    async def test_check_prerequisites_root_user(self):
        """Test prerequisite checks as root user."""
        executor = AsyncMock()
        env_manager = MagicMock()
        env_manager.initialize = AsyncMock()
        env_manager.has_podman = True

        manager = StackManager(executor, env_manager)

        with patch("os.geteuid", return_value=0):
            checks = await manager.check_prerequisites()

        assert checks["permissions"]["status"] == "warning"
        assert "root" in checks["permissions"]["message"]


class TestRollbackLogic:
    """Test rollback functionality."""

    @pytest.mark.asyncio
    async def test_rollback_distrobox(self):
        """Test rollback for Distrobox container."""
        executor = AsyncMock()
        executor.run_async = AsyncMock()
        executor.run_async.return_value.success = True

        env_manager = MagicMock()

        manager = StackManager(executor, env_manager)

        await manager._rollback_stack("test-container", use_distrobox=True)

        # Should call stop and rm
        assert executor.run_async.call_count >= 2

        calls = [call[0][0] for call in executor.run_async.call_args_list]
        assert ["distrobox", "stop", "test-container", "-Y"] in calls
        assert ["distrobox", "rm", "-f", "test-container"] in calls

    @pytest.mark.asyncio
    async def test_rollback_toolbx(self):
        """Test rollback for Toolbx container."""
        executor = AsyncMock()
        executor.run_async = AsyncMock()
        executor.run_async.return_value.success = True

        env_manager = MagicMock()

        manager = StackManager(executor, env_manager)

        await manager._rollback_stack("test-container", use_distrobox=False)

        # Should call rm for toolbox
        executor.run_async.assert_called_once_with(["toolbox", "rm", "-f", "test-container"])

    @pytest.mark.asyncio
    async def test_rollback_exception_handling(self):
        """Test rollback exception handling."""
        executor = AsyncMock()
        executor.run_async = AsyncMock(side_effect=Exception("Test error"))

        env_manager = MagicMock()

        manager = StackManager(executor, env_manager)

        # Should not raise exception
        await manager._rollback_stack("test-container", use_distrobox=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
