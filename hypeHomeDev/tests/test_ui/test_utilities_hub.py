"""Tests for Utilities Hub and sub-widgets."""

from __future__ import annotations

import gi
import pytest

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from ui.pages.utilities import UtilitiesPage  # noqa: E402
from ui.widgets.env_editor import EnvEditor  # noqa: E402
from ui.widgets.hosts_editor import HostsEditor  # noqa: E402
from ui.widgets.pulse_dashboard import PulseDashboard  # noqa: E402


class TestUtilitiesHub:
    """Verify Utilities Hub navigation and content."""

    def test_utilities_hub_navigation(self):
        """Test stack navigation in UtilitiesPage."""
        page = UtilitiesPage()
        page.on_shown()

        assert page._current_view == "hub"

        # Navigate to hosts
        page.navigate_to("hosts")
        assert page._current_view == "hosts"
        assert page._stack.get_visible_child_name() == "hosts"

        # Navigate back
        page.navigate_to("hub")
        assert page._current_view == "hub"
        assert page._stack.get_visible_child_name() == "hub"

    def test_hosts_editor_init(self):
        """Test HostsEditor instantiation."""
        editor = HostsEditor()
        # Initial group should be created
        assert editor._group is not None

    def test_env_editor_init(self):
        """Test EnvEditor instantiation."""
        editor = EnvEditor()
        assert editor._group is not None

    def test_pulse_dashboard_init(self):
        """Test PulseDashboard instantiation."""
        dashboard = PulseDashboard()
        assert dashboard._manager is not None


@pytest.mark.asyncio
async def test_hosts_manager_actual():
    """Verify the actual HostsManager works with a mock executor."""
    from unittest.mock import AsyncMock, MagicMock

    from core.setup.host_executor import HostExecutor
    from core.utils.hosts import HostsManager

    mock_executor = MagicMock(spec=HostExecutor)
    mock_executor.run_async = AsyncMock()

    # Mock result
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.stdout = "127.0.0.1 localhost\n127.0.1.1 hype-home\n"
    mock_executor.run_async.return_value = mock_result

    manager = HostsManager(mock_executor)
    await manager.initialize()
    entries = manager.get_entries()
    assert len(entries) >= 2
    assert entries[0].ip == "127.0.0.1"


@pytest.mark.asyncio
async def test_env_manager_mock():
    """Verify the placeholder EnvVarManager works."""
    from core.utils.env_manager import EnvVarManager

    manager = EnvVarManager()
    await manager.initialize()
    vars = manager.get_variables()
    assert len(vars) > 0
    assert any(v.key == "PATH" for v in vars)
