"""HypeDevHome — About dialog."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

if TYPE_CHECKING:
    from config.manager import ConfigManager

log = logging.getLogger(__name__)


class AboutDialog:
    """About dialog for HypeDevHome."""

    def __init__(self, config_manager: ConfigManager, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.config = config_manager
        self.kwargs = kwargs
        log.debug("About dialog initialized")

    def show(self) -> None:
        """Show the about dialog."""
        try:
            # Try to get version from package metadata
            import importlib.metadata

            version = importlib.metadata.version("hypedevhome")
        except (importlib.metadata.PackageNotFoundError, ImportError):
            # Fallback to hardcoded version
            version = "0.1.0"

        # Create the about window
        about_window = Adw.AboutWindow(
            application_name="HypeDevHome",
            application_icon="com.github.hypedevhome",
            version=version,
            developer_name="The HypeDevHome Team",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/hypedevhome/hypeHomeDev",
            issue_url="https://github.com/hypedevhome/hypeHomeDev/issues",
            **self.kwargs,
        )

        # Set comments
        about_window.set_comments(
            "A 100% open-source Linux developer dashboard\nBuilt with Python, GTK4 & Libadwaita"
        )

        # Add developers (placeholder for now)
        developers = ["HypeDevHome Contributors"]
        about_window.set_developers(developers)

        # Add designers (placeholder)
        designers = ["HypeDevHome Design Team"]
        about_window.set_designers(designers)

        # Add artists (placeholder)
        artists = ["HypeDevHome Art Team"]
        about_window.set_artists(artists)

        # Add documenters (placeholder)
        documenters = ["HypeDevHome Documentation Team"]
        about_window.set_documenters(documenters)

        # Add translator credits (placeholder)
        translator_credits = "Translators: English, Arabic (placeholder)"
        about_window.set_translator_credits(translator_credits)

        # Add copyright
        about_window.set_copyright("© 2024 The HypeDevHome Team")

        # Add release notes (placeholder for future releases)
        release_notes = """<p>Version 0.1.0 - Initial Release</p>
        <ul>
            <li>Basic application skeleton</li>
            <li>GTK4/Libadwaita interface</li>
            <li>Configuration management</li>
            <li>Docker development environment</li>
            <li>Flatpak packaging</li>
        </ul>"""
        about_window.set_release_notes(release_notes)

        # Add special thanks (placeholder)
        special_thanks = [
            "All our contributors and testers",
            "The GTK and Libadwaita teams",
            "The Flatpak community",
            "The open-source community",
        ]
        about_window.add_acknowledgement_section("Special Thanks", special_thanks)

        # Present the window
        about_window.present()
        log.debug("About dialog presented")
