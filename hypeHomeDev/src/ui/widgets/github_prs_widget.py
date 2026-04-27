"""HypeDevHome — GitHub Pull Requests widget.

Displays user's open GitHub pull requests with status, reviews, and mergeability.
"""

from __future__ import annotations

import datetime
import logging

from gi.repository import Gtk, Pango

from core.github.client import get_client
from core.github.models import GitHubPRState, GitHubPullRequest
from ui.widgets.github_widget import GitHubWidget

log = logging.getLogger(__name__)


class GitHubPRsWidget(GitHubWidget):
    """Widget displaying user's open GitHub pull requests."""

    # Metadata for widget gallery
    widget_title = "GitHub Pull Requests"
    widget_icon = "git-pull-request-symbolic"
    widget_description = "Shows your open GitHub pull requests"

    def __init__(self, **kwargs) -> None:
        """Initialize the GitHub PRs widget."""
        kwargs.setdefault("widget_id", "github_prs")
        super().__init__(
            title="GitHub Pull Requests",
            icon_name="git-pull-request-symbolic",
            **kwargs,
        )

        # Show loading state initially
        self.show_loading()

    async def fetch_github_data(self) -> list[GitHubPullRequest]:
        """Fetch user's open pull requests from GitHub."""
        client = await get_client()
        prs = await client.get_pull_requests(
            state="open",
            sort="updated",
            direction="desc",
            per_page=10,
        )
        return prs

    def update_content(self, prs: list[GitHubPullRequest]) -> None:
        """Update widget content with pull requests."""
        # Clear content container
        for child in self._content_container:
            self._content_container.remove(child)

        if not prs:
            self._show_empty_state()
            return

        # Create scrollable container
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_min_content_height(200)

        # Create list box for PRs
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.add_css_class("boxed-list")

        for pr in prs[:8]:  # Show max 8 PRs
            row = self._create_pr_row(pr)
            list_box.append(row)

        scrolled.set_child(list_box)
        self._content_container.append(scrolled)

        # Show count
        count_label = Gtk.Label(
            label=f"Showing {len(prs[:8])} of {len(prs)} open PRs",
        )
        count_label.add_css_class("dim-label")
        count_label.set_halign(Gtk.Align.START)
        count_label.set_margin_start(6)
        count_label.set_margin_top(6)
        self._content_container.append(count_label)

    def _create_pr_row(self, pr: GitHubPullRequest) -> Gtk.ListBoxRow:
        """Create a list box row for a pull request."""
        row = Gtk.ListBoxRow()
        row.set_activatable(True)
        row.connect("activate", self._on_pr_clicked, pr.html_url)

        # Main container
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Title and status row
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # PR icon with status
        if pr.draft:
            icon_name = "edit-draft-symbolic"
            status_text = "Draft"
            status_class = "warning"
        elif pr.state == GitHubPRState.MERGED:
            icon_name = "git-merge-symbolic"
            status_text = "Merged"
            status_class = "success"
        elif pr.state == GitHubPRState.CLOSED:
            icon_name = "window-close-symbolic"
            status_text = "Closed"
            status_class = "error"
        else:
            icon_name = "git-pull-request-symbolic"
            status_text = "Open"
            status_class = "accent"

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(16)

        # Title label
        title_label = Gtk.Label(label=pr.title)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_max_width_chars(40)
        title_label.set_tooltip_text(pr.title)

        # Status badge
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        status_box.add_css_class("tag")
        status_box.add_css_class(status_class)

        status_label = Gtk.Label(label=status_text)
        status_label.add_css_class("caption")
        status_box.append(status_label)

        title_box.append(icon)
        title_box.append(title_label)
        title_box.append(status_box)

        # Repository and metadata row
        meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Repository
        repo_name = pr.repository.name if pr.repository else "Unknown"
        repo_label = Gtk.Label(label=repo_name)
        repo_label.add_css_class("dim-label")
        repo_label.set_halign(Gtk.Align.START)

        # PR number
        number_label = Gtk.Label(label=f"#{pr.number}")
        number_label.add_css_class("dim-label")

        # Time since update
        time_text = self._format_time(pr.updated_at or pr.created_at)
        time_label = Gtk.Label(label=time_text)
        time_label.add_css_class("dim-label")
        time_label.set_halign(Gtk.Align.END)
        time_label.set_hexpand(True)

        meta_box.append(repo_label)
        meta_box.append(number_label)
        meta_box.append(time_label)

        # Stats row
        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        stats_box.set_margin_top(4)

        # Commits
        commits_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        commits_icon = Gtk.Image.new_from_icon_name("git-commit-symbolic")
        commits_icon.set_pixel_size(12)
        commits_icon.add_css_class("dim-label")
        commits_label = Gtk.Label(label=str(pr.commits))
        commits_label.add_css_class("dim-label")
        commits_box.append(commits_icon)
        commits_box.append(commits_label)

        # Changed files
        files_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        files_icon = Gtk.Image.new_from_icon_name("document-symbolic")
        files_icon.set_pixel_size(12)
        files_icon.add_css_class("dim-label")
        files_label = Gtk.Label(label=str(pr.changed_files))
        files_label.add_css_class("dim-label")
        files_box.append(files_icon)
        files_box.append(files_label)

        # Comments
        comments_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        comments_icon = Gtk.Image.new_from_icon_name("chat-symbolic")
        comments_icon.set_pixel_size(12)
        comments_icon.add_css_class("dim-label")
        comments_label = Gtk.Label(label=str(pr.comments))
        comments_label.add_css_class("dim-label")
        comments_box.append(comments_icon)
        comments_box.append(comments_label)

        # Review status
        if pr.requested_reviewers:
            reviews_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            reviews_icon = Gtk.Image.new_from_icon_name("user-available-symbolic")
            reviews_icon.set_pixel_size(12)
            reviews_icon.add_css_class("dim-label")
            reviews_label = Gtk.Label(label=str(len(pr.requested_reviewers)))
            reviews_label.add_css_class("dim-label")
            reviews_box.append(reviews_icon)
            reviews_box.append(reviews_label)
            stats_box.append(reviews_box)

        stats_box.append(commits_box)
        stats_box.append(files_box)
        stats_box.append(comments_box)

        # Mergeability indicator
        if pr.mergeable is not None:
            merge_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            if pr.mergeable:
                merge_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
                merge_icon.add_css_class("success")
                merge_label = Gtk.Label(label="Mergeable")
                merge_label.add_css_class("success")
            else:
                merge_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
                merge_icon.add_css_class("error")
                merge_label = Gtk.Label(label="Conflict")
                merge_label.add_css_class("error")

            merge_box.append(merge_icon)
            merge_box.append(merge_label)
            stats_box.append(merge_box)

        box.append(title_box)
        box.append(meta_box)
        box.append(stats_box)

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
        """Show empty state when no PRs."""
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
        message = Gtk.Label(label="No open pull requests")
        message.add_css_class("heading")

        # Subtitle
        subtitle = Gtk.Label(label="All your PRs are merged or closed!")
        subtitle.add_css_class("dim-label")

        empty_box.append(icon)
        empty_box.append(message)
        empty_box.append(subtitle)

        self._content_container.append(empty_box)

    def _on_pr_clicked(self, row: Gtk.ListBoxRow, url: str) -> None:
        """Handle PR click - open in browser."""
        log.info("Opening PR in browser: %s", url)
        # TODO: Implement browser opening with Gtk.UriLauncher
        # For now, just log
        from gi.repository import Gio

        Gio.AppInfo.launch_default_for_uri(url, None)
