"""HypeDevHome — Register GitHub dashboard widgets."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ui.widgets.registry import WidgetRegistry

from ui.widgets.github_assigned_widget import GitHubAssignedWidget
from ui.widgets.github_issues_widget import GitHubIssuesWidget
from ui.widgets.github_mentions_widget import GitHubMentionsWidget
from ui.widgets.github_prs_widget import GitHubPRsWidget
from ui.widgets.github_repos_widget import GitHubReposWidget
from ui.widgets.github_reviews_widget import GitHubReviewsWidget
from ui.widgets.registry import WidgetRegistry, registry

log = logging.getLogger(__name__)


def register_github_widgets(reg: WidgetRegistry | None = None) -> None:
    """Register all GitHub widgets with the WidgetRegistry.

    Args:
        reg: The WidgetRegistry instance to register widgets with.
             Defaults to the global registry instance.
    """
    target_registry = reg or registry

    registered_widgets = set(target_registry.list_widgets())

    github_widgets = [
        ("github_issues", GitHubIssuesWidget),
        ("github_prs", GitHubPRsWidget),
        ("github_reviews", GitHubReviewsWidget),
        ("github_mentions", GitHubMentionsWidget),
        ("github_assigned", GitHubAssignedWidget),
        ("github_repos", GitHubReposWidget),
    ]

    for widget_id, widget_class in github_widgets:
        if widget_id not in registered_widgets:
            target_registry.register(widget_id, widget_class)

    log.info("GitHub widgets registered: Issues, PRs, Reviews, Mentions, Assigned, Repositories")
