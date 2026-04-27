"""HypeDevHome — GitHub Assigned to Me widget.

Displays issues assigned to the user.
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


class GitHubAssignedWidget(GitHubWidget):
    """Widget displaying issues assigned to user."""

    # Metadata for widget gallery
    widget_title = "Assigned to Me"
    widget_icon = "task-due-symbolic"
    widget_description = "Shows issues assigned to you"

    def __init__(self, **kwargs) -> None:
        """Initialize the GitHub Assigned to Me widget."""
        kwargs.setdefault("widget_id", "github_assigned")
        super().__init__(
            title="Assigned to Me",
            icon_name="task-due-symbolic",
            **kwargs,
        )

        # Show loading state initially
        self.show_loading()

    async def fetch_github_data(self) -> list[GitHubIssue]:
        """Fetch issues assigned to user."""
        client = await get_client()
        issues = await client.get_issues(
            filter_type="assigned",
            state="open",
            sort="updated",
            direction="desc",
            per_page=10,
        )

        # Filter to only issues (not PRs)
        issues_only = [
            issue
            for issue in issues
            if not isinstance(issue, type) or not hasattr(issue, "pull_request")
        ]
        return issues_only

    def update_content(self, issues: list[GitHubIssue]) -> None:
        """Update widget content with assigned issues."""
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
            row = self._create_assigned_row(issue)
            list_box.append(row)

        scrolled.set_child(list_box)
        self._content_container.append(scrolled)

        # Show count
        count_label = Gtk.Label(
            label=f"Showing {len(issues[:8])} of {len(issues)} assigned issues",
        )
        count_label.add_css_class("dim-label")
        count_label.set_halign(Gtk.Align.START)
        count_label.set_margin_start(6)
        count_label.set_margin_top(6)
        self._content_container.append(count_label)

    def _create_assigned_row(self, issue: GitHubIssue) -> Gtk.ListBoxRow:
        """Create a list box row for an assigned issue."""
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
        icon = Gtk.Image.new_from_icon_name("task-due-symbolic")
        icon.set_pixel_size(16)

        # Title label
        title_label = Gtk.Label(label=issue.title)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_max_width_chars(40)
        title_label.set_tooltip_text(issue.title)

        # Priority indicator based on labels
        priority = self._get_issue_priority(issue)
        if priority != "normal":
            priority_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            priority_box.add_css_class("tag")

            if priority == "high":
                priority_text = "High"
                priority_class = "error"
            elif priority == "medium":
                priority_text = "Medium"
                priority_class = "warning"
            else:
                priority_text = "Low"
                priority_class = "accent"

            priority_box.add_css_class(priority_class)
            priority_label = Gtk.Label(label=priority_text)
            priority_label.add_css_class("caption")
            priority_box.append(priority_label)

        title_box.append(icon)
        title_box.append(title_label)
        if priority != "normal":
            title_box.append(priority_box)

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
                more_label = Gtk.Label(label=f"+{len(issue.labels) - 3}")
                more_label.add_css_class("dim-label")
                labels_box.append(more_label)

            box.append(labels_box)

        # Comments count
        if issue.comments > 0:
            comments_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            comments_box.set_margin_top(4)

            comments_icon = Gtk.Image.new_from_icon_name("chat-symbolic")
            comments_icon.set_pixel_size(12)
            comments_icon.add_css_class("dim-label")

            comments_label = Gtk.Label(label=str(issue.comments))
            comments_label.add_css_class("dim-label")

            comments_box.append(comments_icon)
            comments_box.append(comments_label)

            box.append(comments_box)

        box.append(title_box)
        box.append(meta_box)

        row.set_child(box)
        return row

    def _get_issue_priority(self, issue: GitHubIssue) -> str:
        """Determine issue priority based on labels and age."""
        # Check for priority labels
        priority_labels = {
            "high": ["priority: high", "high priority", "urgent", "critical", "blocker"],
            "medium": ["priority: medium", "medium priority", "important"],
            "low": ["priority: low", "low priority", "minor"],
        }

        for label in issue.labels:
            label_name = label.name.lower()
            for priority, keywords in priority_labels.items():
                if any(keyword in label_name for keyword in keywords):
                    return priority

        # Determine by age
        if not issue.created_at:
            return "normal"

        now = datetime.datetime.now(datetime.UTC)
        if issue.created_at.tzinfo is None:
            created_at = issue.created_at.replace(tzinfo=datetime.UTC)
        else:
            created_at = issue.created_at

        age_days = (now - created_at).days

        if age_days > 30:
            return "high"  # Very old issue
        elif age_days > 14:
            return "medium"  # Old issue
        else:
            return "normal"  # Recent issue

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
        """Show empty state when no assigned issues."""
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
        message = Gtk.Label(label="No assigned issues")
        message.add_css_class("heading")

        # Subtitle
        subtitle = Gtk.Label(label="You have no open issues assigned to you")
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
