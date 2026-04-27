"""HypeDevHome — GitHub Repositories widget.

Lists repositories you own, collaborate on, or access via organization membership.
"""

from __future__ import annotations

import logging

from gi.repository import Gtk, Pango

from core.github.client import get_client
from core.github.models import GitHubRepository
from ui.widgets.github_widget import GitHubWidget

log = logging.getLogger(__name__)


class GitHubReposWidget(GitHubWidget):
    """Widget listing the user's GitHub repositories."""

    widget_title = "GitHub Repositories"
    widget_icon = "folder-git-symbolic"
    widget_description = "Lists your repositories (owned, collaborator, and org)"

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("widget_id", "github_repos")
        super().__init__(
            title="GitHub Repos",
            icon_name="folder-git-symbolic",
            **kwargs,
        )
        self.show_loading()

    async def fetch_github_data(self) -> list[GitHubRepository]:
        """Fetch repositories visible to the authenticated user."""
        client = await get_client()
        return await client.get_repositories(
            affiliation="owner,collaborator,organization_member",
            sort="updated",
            direction="desc",
            per_page=40,
            page=1,
        )

    def update_content(self, repos: list[GitHubRepository]) -> None:
        for child in self._content_container:
            self._content_container.remove(child)

        if not repos:
            self._show_empty_state()
            return

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_min_content_height(200)

        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.add_css_class("boxed-list")
        list_box.add_css_class("github-repos-list")

        shown = repos[:20]
        for repo in shown:
            list_box.append(self._create_repo_row(repo))

        scrolled.set_child(list_box)
        self._content_container.append(scrolled)

        count_label = Gtk.Label(
            label=f"Showing {len(shown)} of {len(repos)} repositories",
        )
        count_label.add_css_class("dim-label")
        count_label.set_halign(Gtk.Align.START)
        count_label.set_margin_start(6)
        count_label.set_margin_top(6)
        self._content_container.append(count_label)

    def _create_repo_row(self, repo: GitHubRepository) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_activatable(False)
        row.add_css_class("github-repo-row")
        row._github_html_url = repo.html_url  # type: ignore[attr-defined]  # used by click handler

        tip = f"Open in browser — {repo.html_url}"
        if repo.description and repo.description.strip():
            tip = f"{repo.description.strip()}\n\n{tip}"
        row.set_tooltip_text(tip)

        click = Gtk.GestureClick()
        click.set_button(1)  # GDK_BUTTON_PRIMARY — single left click opens URL
        click.connect("released", self._on_repo_row_released)
        row.add_controller(click)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._on_repo_row_hover_enter)
        motion.connect("leave", self._on_repo_row_hover_leave)
        row.add_controller(motion)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name(
            "emblem-locked-symbolic" if repo.private else "folder-git-symbolic"
        )
        icon.set_pixel_size(16)

        title_label = Gtk.Label(label=repo.full_name)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_max_width_chars(42)
        meta = []
        if repo.fork:
            meta.append("fork")
        if repo.private:
            meta.append("private")
        if repo.stargazers_count:
            meta.append(f"★ {repo.stargazers_count}")
        meta_label = Gtk.Label(label=" · ".join(meta) if meta else "")
        meta_label.add_css_class("caption")
        meta_label.add_css_class("dim-label")
        meta_label.set_halign(Gtk.Align.START)

        title_row.append(icon)
        title_row.append(title_label)

        box.append(title_row)

        desc = (repo.description or "").strip()
        if desc:
            desc_label = Gtk.Label(label=desc)
            desc_label.set_halign(Gtk.Align.START)
            desc_label.set_ellipsize(Pango.EllipsizeMode.END)
            desc_label.set_lines(2)
            desc_label.set_max_width_chars(48)
            desc_label.add_css_class("dim-label")
            box.append(desc_label)

        if meta:
            box.append(meta_label)

        row.set_child(box)
        return row

    def _on_repo_row_released(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
    ) -> None:
        """Single primary click opens the repo in the default browser."""
        if n_press != 1:
            return
        row = gesture.get_widget()
        if not isinstance(row, Gtk.ListBoxRow):
            return
        url = getattr(row, "_github_html_url", None)
        if url:
            self._open_in_browser(url)

    def _on_repo_row_hover_enter(
        self,
        _motion: Gtk.EventControllerMotion,
        _x: float,
        _y: float,
    ) -> None:
        row = _motion.get_widget()
        if isinstance(row, Gtk.Widget):
            row.set_cursor_from_name("pointer")

    def _on_repo_row_hover_leave(self, _motion: Gtk.EventControllerMotion) -> None:
        row = _motion.get_widget()
        if isinstance(row, Gtk.Widget):
            row.set_cursor(None)

    def _show_empty_state(self) -> None:
        for child in self._content_container:
            self._content_container.remove(child)
        empty = Gtk.Label(label="No repositories found")
        empty.add_css_class("dim-label")
        self._content_container.append(empty)
