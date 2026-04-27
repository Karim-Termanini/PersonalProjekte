"""HypeDevHome — GitHub Mentioned Me widget.

Displays issues and PRs where the user was mentioned.
"""

from __future__ import annotations

import datetime
import logging

from gi.repository import Gtk, Pango

from core.github.client import get_client
from core.github.models import GitHubIssue, GitHubPullRequest
from ui.widgets.github_widget import GitHubWidget

log = logging.getLogger(__name__)


class GitHubMentionsWidget(GitHubWidget):
    """Widget displaying issues/PRs where user was mentioned."""

    # Metadata for widget gallery
    widget_title = "Mentioned Me"
    widget_icon = "chat-symbolic"
    widget_description = "Shows issues/PRs where you were mentioned"

    def __init__(self, **kwargs) -> None:
        """Initialize the GitHub Mentioned Me widget."""
        kwargs.setdefault("widget_id", "github_mentions")
        super().__init__(
            title="Mentioned Me",
            icon_name="chat-symbolic",
            **kwargs,
        )

        # Show loading state initially
        self.show_loading()

    async def fetch_github_data(self) -> list[GitHubIssue | GitHubPullRequest]:
        """Fetch issues/PRs where user was mentioned."""
        client = await get_client()

        # Get user info
        user = await client.get_user()

        # Search for mentions
        query = f"mentions:{user.login} is:open archived:false"
        items = await client.search_issues(
            query=query,
            sort="updated",
            order="desc",
            per_page=10,
        )

        return items

    def update_content(self, items: list[GitHubIssue | GitHubPullRequest]) -> None:
        """Update widget content with mentioned items."""
        # Clear content container
        for child in self._content_container:
            self._content_container.remove(child)

        if not items:
            self._show_empty_state()
            return

        # Create scrollable container
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_min_content_height(200)

        # Create list box for items
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.add_css_class("boxed-list")

        for item in items[:8]:  # Show max 8 items
            row = self._create_mention_row(item)
            list_box.append(row)

        scrolled.set_child(list_box)
        self._content_container.append(scrolled)

        # Show count
        count_label = Gtk.Label(
            label=f"Showing {len(items[:8])} of {len(items)} mentions",
        )
        count_label.add_css_class("dim-label")
        count_label.set_halign(Gtk.Align.START)
        count_label.set_margin_start(6)
        count_label.set_margin_top(6)
        self._content_container.append(count_label)

    def _create_mention_row(self, item: GitHubIssue | GitHubPullRequest) -> Gtk.ListBoxRow:
        """Create a list box row for a mention."""
        row = Gtk.ListBoxRow()
        row.set_activatable(True)
        row.connect("activate", self._on_item_clicked, item.html_url)

        # Main container
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Title row
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Icon based on type
        if isinstance(item, GitHubPullRequest):
            icon_name = "git-pull-request-symbolic"
            type_text = "PR"
        else:
            icon_name = "mail-unread-symbolic"
            type_text = "Issue"

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(16)

        # Title label
        title_label = Gtk.Label(label=item.title)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_max_width_chars(40)
        title_label.set_tooltip_text(item.title)

        # Type badge
        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        type_box.add_css_class("tag")
        type_box.add_css_class("accent")

        type_label = Gtk.Label(label=type_text)
        type_label.add_css_class("caption")
        type_box.append(type_label)

        title_box.append(icon)
        title_box.append(title_label)
        title_box.append(type_box)

        # Repository and author row
        meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Repository
        repo_name = item.repository.name if item.repository else "Unknown"
        repo_label = Gtk.Label(label=repo_name)
        repo_label.add_css_class("dim-label")
        repo_label.set_halign(Gtk.Align.START)

        # Author
        author_label = Gtk.Label(label=f"by {item.user.login}")
        author_label.add_css_class("dim-label")

        # Time since update
        time_text = self._format_time(item.updated_at or item.created_at)
        time_label = Gtk.Label(label=time_text)
        time_label.add_css_class("dim-label")
        time_label.set_halign(Gtk.Align.END)
        time_label.set_hexpand(True)

        meta_box.append(repo_label)
        meta_box.append(author_label)
        meta_box.append(time_label)

        box.append(title_box)
        box.append(meta_box)

        row.set_child(box)
        return row

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
        """Show empty state when no mentions."""
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
        message = Gtk.Label(label="No recent mentions")
        message.add_css_class("heading")

        # Subtitle
        subtitle = Gtk.Label(label="No one has mentioned you recently")
        subtitle.add_css_class("dim-label")

        empty_box.append(icon)
        empty_box.append(message)
        empty_box.append(subtitle)

        self._content_container.append(empty_box)

    def _on_item_clicked(self, row: Gtk.ListBoxRow, url: str) -> None:
        """Handle item click - open in browser."""
        log.info("Opening mention in browser: %s", url)
        # TODO: Implement browser opening with Gtk.UriLauncher
        # For now, just log
        from gi.repository import Gio

        Gio.AppInfo.launch_default_for_uri(url, None)
