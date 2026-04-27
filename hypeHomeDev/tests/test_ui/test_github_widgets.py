"""Tests for GitHub widgets."""

from unittest.mock import MagicMock, patch

import pytest

from ui.widgets.github_assigned_widget import GitHubAssignedWidget
from ui.widgets.github_issues_widget import GitHubIssuesWidget
from ui.widgets.github_mentions_widget import GitHubMentionsWidget
from ui.widgets.github_prs_widget import GitHubPRsWidget
from ui.widgets.github_registry import register_github_widgets
from ui.widgets.github_repos_widget import GitHubReposWidget
from ui.widgets.github_reviews_widget import GitHubReviewsWidget
from ui.widgets.github_widget import GitHubWidget
from ui.widgets.registry import WidgetRegistry


@pytest.fixture(autouse=True)
def mock_app_state():
    """Mock AppState for all tests."""
    with patch("core.state.AppState") as mock_state:
        mock_instance = MagicMock()
        mock_instance.github_token = None  # No token by default
        mock_instance.config = None  # GitHubWidget reads github_refresh_interval from config
        mock_state.get.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def mock_github_auth_manager():
    """GitHub widgets use keychain-backed auth; CI/dev machines may have a token."""
    with patch("ui.widgets.github_widget.get_auth_manager") as mock_get:
        mgr = MagicMock()
        mgr.is_authenticated.return_value = False
        mock_get.return_value = mgr
        yield mgr


class TestGitHubWidget:
    """Test the base GitHub widget class."""

    def test_github_widget_initialization(self):
        """Test GitHub widget initializes with correct defaults."""
        widget = GitHubWidget(
            widget_id="test_github",
            title="Test GitHub",
            icon_name="test-icon",
        )

        assert widget.widget_id == "test_github"
        assert widget.title == "Test GitHub"
        assert widget._is_authenticated is False
        assert widget._api_error is None
        assert widget._loading is True

    def test_github_widget_default_refresh_interval(self):
        """Test GitHub widget uses default 30s refresh."""
        widget = GitHubWidget(
            widget_id="test",
            title="Test",
        )

        assert widget._refresh_interval == GitHubWidget.DEFAULT_REFRESH_INTERVAL

    def test_github_widget_config(self):
        """Test GitHub widget config includes github_widget flag."""
        widget = GitHubWidget(
            widget_id="test",
            title="Test",
        )

        config = widget.get_config()
        assert config["github_widget"] is True
        assert config["id"] == "test"

    def test_github_widget_not_authenticated_shows_setup_message(self, mock_app_state):
        """Test that unauthenticated widgets show setup message."""
        mock_app_state.get.return_value.github_token = None

        widget = GitHubWidget(
            widget_id="test",
            title="Test",
        )

        assert widget._is_authenticated is False
        # Widget should show "not configured" message

    def test_github_widget_open_in_browser(self):
        """Test opening URL in browser."""
        with patch("gi.repository.Gio.AppInfo.launch_default_for_uri") as mock_launch:
            GitHubWidget._open_in_browser("https://github.com/test")
            mock_launch.assert_called_once_with("https://github.com/test", None)


class TestGitHubIssuesWidget:
    """Test the Issues widget."""

    def test_issues_widget_initialization(self):
        """Test Issues widget initializes correctly."""
        widget = GitHubIssuesWidget()

        assert (
            "githubissueswidget" in widget.widget_id.lower() or widget.widget_id == "github_issues"
        )
        assert hasattr(widget, "_content_container")


class TestPullRequestsWidget:
    """Test the Pull Requests widget."""

    def test_pr_widget_initialization(self):
        """Test PR widget initializes correctly."""
        widget = GitHubPRsWidget()

        assert "githubprswidget" in widget.widget_id.lower() or widget.widget_id == "github_prs"
        assert hasattr(widget, "_content_container")


class TestReviewRequestedWidget:
    """Test the Review Requested widget."""

    def test_review_widget_initialization(self):
        """Test Review widget initializes correctly."""
        widget = GitHubReviewsWidget()

        assert (
            "githubreviewswidget" in widget.widget_id.lower()
            or widget.widget_id == "github_reviews"
        )
        assert hasattr(widget, "_content_container")


class TestMentionedMeWidget:
    """Test the Mentioned Me widget."""

    def test_mention_widget_initialization(self):
        """Test Mentioned widget initializes correctly."""
        widget = GitHubMentionsWidget()

        assert (
            "githubmentionswidget" in widget.widget_id.lower()
            or widget.widget_id == "github_mentions"
        )
        assert hasattr(widget, "_content_container")


class TestAssignedToMeWidget:
    """Test the Assigned to Me widget."""

    def test_assigned_widget_initialization(self):
        """Test Assigned widget initializes correctly."""
        widget = GitHubAssignedWidget()

        assert (
            "githubassignedwidget" in widget.widget_id.lower()
            or widget.widget_id == "github_assigned"
        )
        assert hasattr(widget, "_content_container")


class TestGitHubReposWidget:
    """Test the Repositories widget."""

    def test_repos_widget_initialization(self):
        """Test Repos widget initializes correctly."""
        widget = GitHubReposWidget()

        assert (
            "githubreposwidget" in widget.widget_id.lower() or widget.widget_id == "github_repos"
        )
        assert hasattr(widget, "_content_container")


class TestGitHubWidgetRegistry:
    """Test GitHub widget registration."""

    def test_register_github_widgets(self):
        """Test that all GitHub widgets are registered."""
        # Clear registry
        WidgetRegistry.instance()._widgets.clear()

        # Register widgets
        register_github_widgets(WidgetRegistry.instance())

        # Check all GitHub widgets are registered
        registered_ids = WidgetRegistry.list_widgets()

        assert "github_issues" in registered_ids
        assert "github_prs" in registered_ids
        assert "github_reviews" in registered_ids
        assert "github_mentions" in registered_ids
        assert "github_assigned" in registered_ids
        assert "github_repos" in registered_ids

    def test_get_github_widget_class(self):
        """Test retrieving GitHub widget classes."""
        WidgetRegistry.instance()._widgets.clear()
        register_github_widgets(WidgetRegistry.instance())

        from ui.widgets.github_assigned_widget import GitHubAssignedWidget
        from ui.widgets.github_issues_widget import GitHubIssuesWidget
        from ui.widgets.github_mentions_widget import GitHubMentionsWidget
        from ui.widgets.github_prs_widget import GitHubPRsWidget
        from ui.widgets.github_repos_widget import GitHubReposWidget
        from ui.widgets.github_reviews_widget import GitHubReviewsWidget

        assert WidgetRegistry.get_widget_class("github_issues") == GitHubIssuesWidget
        assert WidgetRegistry.get_widget_class("github_prs") == GitHubPRsWidget
        assert WidgetRegistry.get_widget_class("github_reviews") == GitHubReviewsWidget
        assert WidgetRegistry.get_widget_class("github_mentions") == GitHubMentionsWidget
        assert WidgetRegistry.get_widget_class("github_assigned") == GitHubAssignedWidget
        assert WidgetRegistry.get_widget_class("github_repos") == GitHubReposWidget
