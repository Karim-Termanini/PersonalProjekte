"""HypeDevHome — GitHub Review Requested widget.

Displays pull requests awaiting user's review with priority indicators.
"""

from __future__ import annotations

import datetime
import logging

from gi.repository import Gtk, Pango

from core.github.client import get_client
from core.github.models import GitHubPullRequest
from ui.widgets.github_widget import GitHubWidget

log = logging.getLogger(__name__)


class GitHubReviewsWidget(GitHubWidget):
    """Widget displaying pull requests awaiting user's review."""

    # Metadata for widget gallery
    widget_title = "Review Requests"
    widget_icon = "user-available-symbolic"
    widget_description = "Shows PRs awaiting your review"

    def __init__(self, **kwargs) -> None:
        """Initialize the GitHub Review Requested widget."""
        kwargs.setdefault("widget_id", "github_reviews")
        super().__init__(
            title="Review Requests",
            icon_name="user-available-symbolic",
            **kwargs,
        )

        # Show loading state initially
        self.show_loading()

    async def fetch_github_data(self) -> list[GitHubPullRequest]:
        """Fetch PRs awaiting user's review from GitHub."""
        client = await get_client()
        prs = await client.get_review_requests()
        return prs

    def update_content(self, prs: list[GitHubPullRequest]) -> None:
        """Update widget content with review requests."""
        # Clear content container
        for child in self._content_container:
            self._content_container.remove(child)

        if not prs:
            self._show_empty_state()
            return

        # Sort by priority (older requests first)
        prs.sort(key=lambda x: x.created_at or datetime.datetime.min)

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
            row = self._create_review_row(pr)
            list_box.append(row)

        scrolled.set_child(list_box)
        self._content_container.append(scrolled)

        # Show count with priority indicator
        overdue_count = self._count_overdue_reviews(prs)
        count_text = f"Showing {len(prs[:8])} of {len(prs)} PRs awaiting review"
        if overdue_count > 0:
            count_text += f" ({overdue_count} overdue)"

        count_label = Gtk.Label(label=count_text)
        count_label.add_css_class("dim-label")
        count_label.set_halign(Gtk.Align.START)
        count_label.set_margin_start(6)
        count_label.set_margin_top(6)
        self._content_container.append(count_label)

    def _create_review_row(self, pr: GitHubPullRequest) -> Gtk.ListBoxRow:
        """Create a list box row for a review request."""
        row = Gtk.ListBoxRow()
        row.set_activatable(True)
        row.connect("activate", self._on_pr_clicked, pr.html_url)

        # Determine priority
        priority = self._get_review_priority(pr)

        # Main container
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Add priority indicator
        if priority == "high":
            box.add_css_class("error")
        elif priority == "medium":
            box.add_css_class("warning")

        # Title row
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Review icon with priority
        if priority == "high":
            icon_name = "dialog-warning-symbolic"
        elif priority == "medium":
            icon_name = "dialog-information-symbolic"
        else:
            icon_name = "user-available-symbolic"

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(16)

        # Title label
        title_label = Gtk.Label(label=pr.title)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_max_width_chars(40)
        title_label.set_tooltip_text(pr.title)

        # Priority badge
        if priority != "low":
            priority_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            priority_box.add_css_class("tag")

            if priority == "high":
                priority_text = "Overdue"
                priority_class = "error"
            else:
                priority_text = "Pending"
                priority_class = "warning"

            priority_box.add_css_class(priority_class)
            priority_label = Gtk.Label(label=priority_text)
            priority_label.add_css_class("caption")
            priority_box.append(priority_label)

        title_box.append(icon)
        title_box.append(title_label)
        if priority != "low":
            title_box.append(priority_box)

        # Repository and author row
        meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Repository
        repo_name = pr.repository.name if pr.repository else "Unknown"
        repo_label = Gtk.Label(label=repo_name)
        repo_label.add_css_class("dim-label")
        repo_label.set_halign(Gtk.Align.START)

        # Author
        author_label = Gtk.Label(label=f"by {pr.user.login}")
        author_label.add_css_class("dim-label")

        # Time since creation
        time_text = self._format_time(pr.created_at)
        time_label = Gtk.Label(label=time_text)
        time_label.add_css_class("dim-label")
        time_label.set_halign(Gtk.Align.END)
        time_label.set_hexpand(True)

        meta_box.append(repo_label)
        meta_box.append(author_label)
        meta_box.append(time_label)

        # Reviewers row
        if pr.requested_reviewers:
            reviewers_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            reviewers_box.set_margin_top(4)

            reviewers_label = Gtk.Label(label="Reviewers:")
            reviewers_label.add_css_class("dim-label")
            reviewers_label.add_css_class("caption")

            reviewers_box.append(reviewers_label)

            # Show first 3 reviewers
            for reviewer in pr.requested_reviewers[:3]:
                reviewer_label = Gtk.Label(label=reviewer.login)
                reviewer_label.add_css_class("dim-label")
                reviewer_label.add_css_class("caption")
                reviewers_box.append(reviewer_label)

            if len(pr.requested_reviewers) > 3:
                more_label = Gtk.Label(label=f"+{len(pr.requested_reviewers) - 3}")
                more_label.add_css_class("dim-label")
                more_label.add_css_class("caption")
                reviewers_box.append(more_label)

            box.append(reviewers_box)

        # Stats row
        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        stats_box.set_margin_top(4)

        # Comments
        if pr.comments > 0:
            comments_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            comments_icon = Gtk.Image.new_from_icon_name("chat-symbolic")
            comments_icon.set_pixel_size(12)
            comments_icon.add_css_class("dim-label")
            comments_label = Gtk.Label(label=str(pr.comments))
            comments_label.add_css_class("dim-label")
            comments_box.append(comments_icon)
            comments_box.append(comments_label)
            stats_box.append(comments_box)

        # Review comments
        if pr.review_comments > 0:
            review_comments_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            review_icon = Gtk.Image.new_from_icon_name("edit-find-replace-symbolic")
            review_icon.set_pixel_size(12)
            review_icon.add_css_class("dim-label")
            review_label = Gtk.Label(label=str(pr.review_comments))
            review_label.add_css_class("dim-label")
            review_comments_box.append(review_icon)
            review_comments_box.append(review_label)
            stats_box.append(review_comments_box)

        box.append(title_box)
        box.append(meta_box)
        box.append(stats_box)

        row.set_child(box)
        return row

    def _get_review_priority(self, pr: GitHubPullRequest) -> str:
        """Determine review priority based on age."""
        if not pr.created_at:
            return "low"

        now = datetime.datetime.now(datetime.UTC)
        if pr.created_at.tzinfo is None:
            created_at = pr.created_at.replace(tzinfo=datetime.UTC)
        else:
            created_at = pr.created_at

        age_days = (now - created_at).days

        if age_days > 7:
            return "high"  # Overdue (more than 7 days)
        elif age_days > 3:
            return "medium"  # Pending (3-7 days)
        else:
            return "low"  # Recent (0-3 days)

    def _count_overdue_reviews(self, prs: list[GitHubPullRequest]) -> int:
        """Count overdue review requests."""
        count = 0
        for pr in prs:
            if self._get_review_priority(pr) == "high":
                count += 1
        return count

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
        """Show empty state when no review requests."""
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
        message = Gtk.Label(label="No review requests")
        message.add_css_class("heading")

        # Subtitle
        subtitle = Gtk.Label(label="You're all caught up on reviews!")
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
