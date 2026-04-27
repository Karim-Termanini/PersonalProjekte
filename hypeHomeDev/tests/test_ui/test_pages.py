"""Tests for page registry and page classes."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from ui.pages.dashboard import DashboardPage  # noqa: E402
from ui.pages.extensions import ExtensionsPage  # noqa: E402
from ui.pages.machine_setup import MachineSetupPage  # noqa: E402
from ui.pages.system_monitor import SystemMonitorPage  # noqa: E402
from ui.pages.utilities import UtilitiesPage  # noqa: E402
from ui.pages.welcome_dashboard import WelcomeDashboardPage  # noqa: E402
from ui.pages.workstation import WorkstationPage  # noqa: E402


class TestPageClasses:
    """Verify each page can be instantiated and built without error."""

    def test_dashboard_page(self):
        page = DashboardPage()
        assert page.page_title == "Widgets"
        page.on_shown()
        assert page._built

    def test_machine_setup_page(self):
        page = MachineSetupPage()
        assert page.page_title == "Machine Setup"
        page.on_shown()
        assert page._built

    def test_extensions_page(self):
        page = ExtensionsPage()
        assert page.page_title == "Extensions"
        page.on_shown()
        assert page._built

    def test_utilities_page(self):
        page = UtilitiesPage()
        assert page.page_title == "Utilities"
        page.on_shown()
        assert page._built

    def test_workstation_page(self):
        page = WorkstationPage()
        assert page.page_title == "Tools"
        page.on_shown()
        assert page._built

    def test_welcome_dashboard_page(self):
        page = WelcomeDashboardPage()
        assert page.page_title == "Welcome"
        page.on_shown()
        assert page._built

    def test_system_monitor_page(self):
        page = SystemMonitorPage()
        assert page.page_title == "System Monitor"
        page.on_shown()
        assert page._built

    def test_all_pages_have_icon(self):
        for page_class in [
            WelcomeDashboardPage,
            SystemMonitorPage,
            DashboardPage,
            MachineSetupPage,
            ExtensionsPage,
            UtilitiesPage,
            WorkstationPage,
        ]:
            page = page_class()
            assert page.page_icon, f"{page_class.__name__} missing icon"

    def test_hidden_callback(self):
        page = DashboardPage()
        page.on_shown()
        page.on_hidden()  # should not raise
