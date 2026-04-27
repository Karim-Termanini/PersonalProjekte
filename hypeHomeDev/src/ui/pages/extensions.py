"""HypeDevHome - Extensions page (placeholder for Phase 6)."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw  # noqa: E402

from ui.pages.base_page import BasePage  # noqa: E402


class ExtensionsPage(BasePage):
    """Manage and browse extensions.

    Extension framework will be implemented in Phase 6.
    """

    page_title = "Extensions"
    page_icon = "application-x-addon-symbolic"

    def build_content(self) -> None:
        status = Adw.StatusPage(
            title="Extensions",
            description="Browse and manage extensions to add new features.\nComing in Phase 6.",
            icon_name="application-x-addon-symbolic",
            vexpand=True,
        )
        self.append(status)
