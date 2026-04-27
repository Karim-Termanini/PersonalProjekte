"""HypeDevHome — GitHub Issues widget.

Displays user's open GitHub issues with repository, labels, and time information.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from gi.repository import Gtk, Pango

from core.github.client import get_client
from core.github.models import GitHubIssue
from ui.widgets.github_widget import GitHubWidget

log = logging.getLogger(__name__)


class GitHubIssuesWidget(GitHubWidget):
    """Widget displaying user's open GitHub issues."""

    # Metadata for widget gallery
    widget_title = "GitHub Issues"
    widget_icon = "github-symbolic"
    widget_description = "Shows your open GitHub issues"

    def __init__(self, **kwargs) -> None:
        """Initialize the GitHub Issues widget."""
        kwargs.setdefault("widget_id", "github_issues")
        super().__init__(
            title="GitHub Issues",
            icon_name="github-symbolic",
            **kwargs,
        )

        # Show loading state initially
        self.show_loading()

    async def fetch_github_data(self) -> list[GitHubIssue]:
        """Fetch user's open issues from GitHub."""
        client = await get_client()
        issues = await client.get_issues(
            filter_type="assigned",
            state="open",
            sort="updated",
            direction="desc",
            per_page=10,
        )
        return issues

    def update_content(self, issues: list[GitHubIssue]) -> None:
        """Update widget content with issues."""
        # Clear content container
        for child in self._content_container:
            self._content_container.remove(child)

        if not issues:
            self._show_empty_state()
            return

        # Create scrollable container
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_min_content_height(200)

        # Create list box for issues
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.add_css_class("boxed-list")

        for issue in issues[:8]:  # Show max 8 issues
            row = self._create_issue_row(issue)
            list_box.append(row)

        scrolled.set_child(list_box)
        self._content_container.append(scrolled)

        # Show count
        count_label = Gtk.Label(
            label=f"Showing {len(issues[:8])} of {len(issues)} open issues",
        )
        count_label.add_css_class("dim-label")
        count_label.set_halign(Gtk.Align.START)
        count_label.set_margin_start(6)
        count_label.set_margin_top(6)
        self._content_container.append(count_label)

    def _create_issue_row(self, issue: GitHubIssue) -> Gtk.ListBoxRow:
        """Create a list box row for an issue."""
        row = Gtk.ListBoxRow()
        row.set_activatable(True)
        row.connect("activate", self._on_issue_clicked, issue.html_url)

        # Main container
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Title row
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Issue icon
        icon = Gtk.Image.new_from_icon_name("mail-unread-symbolic")
        icon.set_pixel_size(16)

        # Title label
        title_label = Gtk.Label(label=issue.title)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_max_width_chars(40)
        title_label.set_tooltip_text(issue.title)

        title_box.append(icon)
        title_box.append(title_label)

        # Repository and metadata row
        meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Repository
        repo_name = issue.repository.name if issue.repository else "Unknown"
        repo_label = Gtk.Label(label=repo_name)
        repo_label.add_css_class("dim-label")
        repo_label.set_halign(Gtk.Align.START)

        # Issue number
        number_label = Gtk.Label(label=f"#{issue.number}")
        number_label.add_css_class("dim-label")

        # Time since update
        time_text = self._format_time(issue.updated_at or issue.created_at)
        time_label = Gtk.Label(label=time_text)
        time_label.add_css_class("dim-label")
        time_label.set_halign(Gtk.Align.END)
        time_label.set_hexpand(True)

        meta_box.append(repo_label)
        meta_box.append(number_label)
        meta_box.append(time_label)

        # Labels (if any)
        if issue.labels:
            labels_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            labels_box.set_margin_top(4)

            for label in issue.labels[:3]:  # Show max 3 labels
                label_widget = self._create_label_widget(label)
                labels_box.append(label_widget)

            if len(issue.labels) > 3:
                more_label = Gtk.Label(label=f"+{len(issue.labels) - 3} more")
                more_label.add_css_class("dim-label")
                labels_box.append(more_label)

            box.append(labels_box)

        box.append(title_box)
        box.append(meta_box)

        row.set_child(box)
        return row

    def _create_label_widget(self, label: Any) -> Gtk.Widget:
        """Create a widget for a GitHub label."""
        # Create a box with background color
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.add_css_class("tag")

        # Set background color if available
        if hasattr(label, "color") and label.color:
            try:
                # Convert hex color to RGB
                color = label.color
                if len(color) == 6:
                    r = int(color[0:2], 16) / 255.0
                    g = int(color[2:4], 16) / 255.0
                    b = int(color[4:6], 16) / 255.0

                    # Create background color
                    from gi.repository import Gdk

                    rgba = Gdk.RGBA(red=r, green=g, blue=b, alpha=0.2)

                    # Create custom CSS
                    css = f"""
                    .label-{label.id} {{
                        background-color: {rgba.to_string()};
                        border: 1px solid alpha(@theme_fg_color, 0.35);
                    }}
                    """
                    css_provider = Gtk.CssProvider()
                    css_provider.load_from_data(css.encode())
                    box.get_style_context().add_provider(
                        css_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                    )
                    box.get_style_context().add_class(f"label-{label.id}")
            except Exception:
                pass

        # Label text
        label_text = Gtk.Label(label=label.name)
        label_text.add_css_class("caption")
        box.append(label_text)

        return box

    def _format_time(self, dt: datetime.datetime | None) -> str:
        """Format time relative to now."""
        if not dt:
            return "Unknown"

        now = datetime.datetime.now(datetime.UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.UTC)

        diff = now - dt

        if diff.days > 365:
            years = diff.days // 365
            return f"{years}y ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months}mo ago"
        elif diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "Just now"

    def _show_empty_state(self) -> None:
        """Show empty state when no issues."""
        empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        empty_box.set_valign(Gtk.Align.CENTER)
        empty_box.set_halign(Gtk.Align.CENTER)
        empty_box.set_margin_top(24)
        empty_box.set_margin_bottom(24)

        # Icon
        icon = Gtk.Image.new_from_icon_name("check-round-outline-symbolic")
        icon.set_pixel_size(48)
        icon.add_css_class("dim-label")

        # Message
        message = Gtk.Label(label="No open issues assigned to you")
        message.add_css_class("heading")

        # Subtitle
        subtitle = Gtk.Label(label="Great job! All issues are resolved.")
        subtitle.add_css_class("dim-label")

        empty_box.append(icon)
        empty_box.append(message)
        empty_box.append(subtitle)

        self._content_container.append(empty_box)

    def _on_issue_clicked(self, row: Gtk.ListBoxRow, url: str) -> None:
        """Handle issue click - open in browser."""
        log.info("Opening issue in browser: %s", url)
        # TODO: Implement browser opening with Gtk.UriLauncher
        # For now, just log
        from gi.repository import Gio

        Gio.AppInfo.launch_default_for_uri(url, None)
