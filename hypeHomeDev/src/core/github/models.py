"""HypeDevHome — Data models for GitHub entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from dateutil.parser import parse


class GitHubPRState(Enum):
    """GitHub pull request state."""

    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


@dataclass
class GitHubUser:
    """Represents a GitHub user profile."""

    login: str
    id: int
    avatar_url: str
    html_url: str
    name: str | None = None
    bio: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> GitHubUser:
        return cls(
            login=data["login"],
            id=data["id"],
            avatar_url=data["avatar_url"],
            html_url=data["html_url"],
            name=data.get("name"),
            bio=data.get("bio"),
        )


@dataclass
class GitHubLabel:
    """Represents a GitHub issue/PR label."""

    name: str
    color: str
    description: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> GitHubLabel:
        return cls(
            name=data["name"],
            color=data.get("color", ""),
            description=data.get("description"),
        )


@dataclass
class GitHubRepo:
    """Represents a GitHub repository."""

    id: int
    name: str
    full_name: str
    html_url: str
    description: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> GitHubRepo:
        return cls(
            id=data["id"],
            name=data["name"],
            full_name=data["full_name"],
            html_url=data["html_url"],
            description=data.get("description"),
        )


@dataclass
class GitHubIssue:
    """Represents a GitHub issue or pull request (shared fields)."""

    id: int
    number: int
    title: str
    html_url: str
    state: str
    created_at: datetime
    updated_at: datetime
    user: GitHubUser
    repository: GitHubRepo | None = None
    labels: list[GitHubLabel] = field(default_factory=list)
    is_pr: bool = False
    comments: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> GitHubIssue:
        return cls(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            html_url=data["html_url"],
            state=data["state"],
            created_at=parse(data["created_at"]),
            updated_at=parse(data["updated_at"]),
            user=GitHubUser.from_api(data["user"]),
            repository=GitHubRepo.from_api(data["repository"]) if "repository" in data else None,
            labels=[GitHubLabel.from_api(label_data) for label_data in data.get("labels", [])],
            is_pr="pull_request" in data,
            comments=data.get("comments", 0),
        )


@dataclass
class GitHubNotification:
    """Represents a GitHub notification."""

    id: str
    unread: bool
    reason: str
    subject_title: str
    subject_type: str
    subject_url: str
    repository: GitHubRepo | None = None
    last_read_at: datetime | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> GitHubNotification:
        return cls(
            id=data["id"],
            unread=data["unread"],
            reason=data["reason"],
            subject_title=data["subject"]["title"],
            subject_type=data["subject"]["type"],
            subject_url=data["subject"]["url"],
            repository=GitHubRepo.from_api(data["repository"]) if "repository" in data else None,
            last_read_at=parse(data["last_read_at"]) if data.get("last_read_at") else None,
        )


@dataclass
class GitHubPullRequest(GitHubIssue):
    """Represents a GitHub Pull Request with PR-specific fields."""

    draft: bool = False
    mergeable: bool | None = None
    merged: bool = False
    head_branch: str | None = None
    base_branch: str | None = None
    review_status: str = "pending"  # pending, approved, changes_requested
    requested_reviewers: list[GitHubUser] = field(default_factory=list)
    commits: int = 0
    changed_files: int = 0
    review_comments: int = 0

    @classmethod
    def from_api(
        cls, data: dict[str, Any], repository: GitHubRepo | None = None
    ) -> GitHubPullRequest:
        return cls(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            html_url=data["html_url"],
            state=data["state"],
            created_at=parse(data["created_at"]),
            updated_at=parse(data["updated_at"]),
            user=GitHubUser.from_api(data["user"]),
            repository=repository
            or (GitHubRepo.from_api(data["repository"]) if "repository" in data else None),
            labels=[GitHubLabel.from_api(label_data) for label_data in data.get("labels", [])],
            is_pr=True,
            draft=data.get("draft", False),
            mergeable=data.get("mergeable"),
            merged=data.get("merged", False),
            head_branch=data.get("head", {}).get("ref"),
            base_branch=data.get("base", {}).get("ref"),
            requested_reviewers=[
                GitHubUser.from_api(u) for u in data.get("requested_reviewers", [])
            ],
            commits=data.get("commits", 0),
            changed_files=data.get("changed_files", 0),
            review_comments=data.get("review_comments", 0),
        )


@dataclass
class GitHubRateLimit:
    """Represents GitHub API rate limit information."""

    limit: int = 5000
    remaining: int = 5000
    reset_at: datetime | None = None
    used: int = 0
    resource: str = "core"

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> GitHubRateLimit:
        return cls(
            limit=data.get("limit", 5000),
            remaining=data.get("remaining", 5000),
            reset_at=parse(data["reset"]) if data.get("reset") else None,
        )


@dataclass
class GitHubRepository(GitHubRepo):
    """Extends GitHubRepo with additional repository information."""

    default_branch: str = "main"
    private: bool = False
    fork: bool = False
    stargazers_count: int = 0
    forks_count: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> GitHubRepository:
        return cls(
            id=data["id"],
            name=data["name"],
            full_name=data["full_name"],
            html_url=data["html_url"],
            description=data.get("description"),
            default_branch=data.get("default_branch", "main"),
            private=data.get("private", False),
            fork=data.get("fork", False),
            stargazers_count=data.get("stargazers_count", 0),
            forks_count=data.get("forks_count", 0),
        )
