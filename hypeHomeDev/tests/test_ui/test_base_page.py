"""Tests for src.ui.pages.base_page -- BasePage lifecycle."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from ui.pages.base_page import BasePage  # noqa: E402


class StubPage(BasePage):
    """Concrete subclass for testing."""

    page_title = "Stub"
    page_icon = "test-symbolic"
    build_called = False

    def build_content(self) -> None:
        self.build_called = True


class TestBasePage:
    def test_lazy_build(self):
        page = StubPage()
        assert not page._built
        assert not page.build_called

    def test_ensure_built_calls_build_content(self):
        page = StubPage()
        page.ensure_built()
        assert page._built
        assert page.build_called

    def test_ensure_built_idempotent(self):
        page = StubPage()
        page.ensure_built()
        page.build_called = False  # reset
        page.ensure_built()
        assert not page.build_called  # should NOT call again

    def test_on_shown_triggers_build(self):
        page = StubPage()
        page.on_shown()
        assert page._built

    def test_get_header_actions_default_empty(self):
        page = StubPage()
        assert page.get_header_actions() == []

    def test_abstract_build_content_raises(self):
        """BasePage.build_content should raise NotImplementedError."""

        class Bare(BasePage):
            page_title = "Bare"

        page = Bare()
        try:
            page.build_content()
            raise AssertionError("Expected NotImplementedError")
        except NotImplementedError:
            pass
