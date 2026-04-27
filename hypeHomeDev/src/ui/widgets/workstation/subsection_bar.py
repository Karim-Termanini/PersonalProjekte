"""Horizontal subsection bar (Gtk.StackSwitcher + Gtk.Stack) for Workstation hub areas."""

from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402


class WorkstationSubsectionBar(Gtk.Box):
    """Top bar of short titles switching stacked subsection panes (scrollable each)."""

    def __init__(
        self,
        sections: list[tuple[str, str, Gtk.Widget]],
        **kwargs: Any,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)
        if not sections:
            raise ValueError("WorkstationSubsectionBar requires at least one section")

        self._first_id = sections[0][0]
        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
            transition_duration=180,
            hexpand=True,
            vexpand=True,
        )

        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self._stack)
        switcher.set_margin_top(6)
        switcher.set_margin_bottom(10)
        switcher.set_margin_start(16)
        switcher.set_margin_end(16)
        switcher.set_halign(Gtk.Align.CENTER)
        switcher.add_css_class("workstation-subsection-switcher")

        for sid, title, child in sections:
            scroll = Gtk.ScrolledWindow(
                hexpand=True,
                vexpand=True,
                hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            )
            try:
                scroll.set_overlay_scrolling(False)
            except (AttributeError, TypeError):
                pass
            scroll.set_child(child)
            self._stack.add_titled(scroll, sid, title)

        self.append(switcher)
        self.append(self._stack)

    def reset_to_first(self) -> None:
        """Show the first subsection (e.g. when leaving Workstation)."""
        self._stack.set_visible_child_name(self._first_id)

    def switch_to_id(self, sid: str) -> bool:
        """Switch horizontally to a specific tab by its identifier."""
        if self._stack.get_child_by_name(sid):
            self._stack.set_visible_child_name(sid)
            return True
        return False
