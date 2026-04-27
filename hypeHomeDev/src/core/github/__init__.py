"""HypeDevHome — GitHub integration module.

Provides GitHub API integration for HypeDevHome.
"""

from core.github.auth import GitHubAuthManager, get_auth_manager
from core.github.client import GitHubClient, get_client
from core.github.models import (
    GitHubIssue,
    GitHubLabel,
    GitHubNotification,
    GitHubPullRequest,
    GitHubRateLimit,
    GitHubRepository,
    GitHubUser,
)

__all__ = [
    "GitHubAuthManager",
    "GitHubClient",
    "GitHubIssue",
    "GitHubLabel",
    "GitHubNotification",
    "GitHubPullRequest",
    "GitHubRateLimit",
    "GitHubRepository",
    "GitHubUser",
    "get_auth_manager",
    "get_client",
]
