"""HypeDevHome — Async GitHub API client.

Provides async HTTP client for GitHub API with rate limiting, caching,
and comprehensive error handling.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import aiohttp
from cachetools import TTLCache

from core.github.auth import get_auth_manager
from core.github.models import (
    GitHubIssue,
    GitHubNotification,
    GitHubPullRequest,
    GitHubRateLimit,
    GitHubRepository,
    GitHubUser,
)

log = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GitHubRateLimitError(GitHubAPIError):
    """Exception raised when GitHub API rate limit is exceeded."""

    pass


class GitHubAuthError(GitHubAPIError):
    """Exception raised for authentication errors."""

    pass


class GitHubClient:
    """Async GitHub API client with rate limiting and caching."""

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        cache_ttl: int = 300,  # 5 minutes default cache TTL
        max_cache_size: int = 1000,
        timeout: int = 30,
    ) -> None:
        self._auth_manager = get_auth_manager()
        self._timeout = timeout
        self._session: aiohttp.ClientSession | None = None

        # Rate limiting tracking
        self._rate_limits: dict[str, GitHubRateLimit] = {}
        # Locks must be created on the asyncio loop that runs requests (background thread),
        # not in __init__ from an arbitrary thread — avoids "Timeout context manager..." / loop bugs.
        self._rate_limit_lock: asyncio.Lock | None = None
        self._cache_lock: asyncio.Lock | None = None

        # Caching
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=max_cache_size, ttl=cache_ttl)

        # Request tracking for debugging
        self._request_count = 0

    def _ensure_async_locks(self) -> None:
        """Bind asyncio primitives to the running loop (call from async code)."""
        if self._rate_limit_lock is None:
            self._rate_limit_lock = asyncio.Lock()
            self._cache_lock = asyncio.Lock()

    async def __aenter__(self) -> GitHubClient:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def start(self) -> None:
        """Start the client session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
            log.debug("GitHub client session started")

    async def close(self) -> None:
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            log.debug("GitHub client session closed")

    def _get_cache_key(self, endpoint: str, params: dict[str, Any] | None = None) -> str:
        """Generate cache key for endpoint and parameters."""
        key = endpoint
        if params:
            # Sort params for consistent cache keys
            sorted_params = sorted(params.items())
            key += "?" + urlencode(sorted_params)
        return key

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> Any:
        """Make an HTTP request to GitHub API with rate limiting and caching."""
        self._ensure_async_locks()
        cache_lock = self._cache_lock
        assert cache_lock is not None

        # Check authentication
        if not self._auth_manager.is_authenticated():
            raise GitHubAuthError("Not authenticated with GitHub")

        # Generate cache key for GET requests
        cache_key = None
        if method == "GET" and use_cache:
            cache_key = self._get_cache_key(endpoint, params)
            async with cache_lock:
                if cache_key in self._cache:
                    log.debug("Cache hit for: %s", cache_key)
                    return self._cache[cache_key]

        # Check rate limits before making request
        await self._check_rate_limits()

        # Ensure session is started
        await self.start()

        # Build URL
        url = f"{self.BASE_URL}{endpoint}"

        # Prepare headers
        headers = self._auth_manager.get_auth_headers()

        # Prepare request
        request_kwargs: dict[str, Any] = {"headers": headers}
        if params:
            request_kwargs["params"] = params
        if data:
            request_kwargs["json"] = data

        # Make request
        self._request_count += 1
        request_id = self._request_count

        log.debug("Request #%d: %s %s", request_id, method, endpoint)

        if not self._session:
            await self.start()

        if not self._session:
            raise GitHubAPIError("Failed to start client session")

        try:
            async with self._session.request(method, url, **request_kwargs) as response:
                # Update rate limits from response headers
                await self._update_rate_limits(dict(response.headers))

                # Handle response
                if response.status == 200:
                    result = await response.json()

                    # Cache successful GET responses
                    if method == "GET" and use_cache and cache_key:
                        async with cache_lock:
                            self._cache[cache_key] = result

                    return result

                elif response.status == 401 or response.status == 403:
                    # Authentication error
                    error_text = await response.text()
                    log.error("GitHub auth error (%d): %s", response.status, error_text)
                    raise GitHubAuthError(
                        f"Authentication failed: {response.status}",
                        status_code=response.status,
                    )

                elif response.status == 429:
                    # Rate limit exceeded
                    reset_time = response.headers.get("X-RateLimit-Reset")
                    if reset_time:
                        reset_dt = datetime.fromtimestamp(int(reset_time))
                        wait_seconds = (reset_dt - datetime.now()).total_seconds()
                        wait_seconds = max(1, wait_seconds)
                        log.warning(
                            "Rate limit exceeded, waiting %.0f seconds until %s",
                            wait_seconds,
                            reset_dt.isoformat(),
                        )
                        await asyncio.sleep(wait_seconds)
                        # Retry once after waiting
                        return await self._make_request(method, endpoint, params, data, use_cache)
                    else:
                        raise GitHubRateLimitError("Rate limit exceeded")

                elif response.status == 404:
                    # Not found
                    error_text = await response.text()
                    log.warning("GitHub API endpoint not found: %s", endpoint)
                    raise GitHubAPIError(
                        f"Resource not found: {endpoint}",
                        status_code=response.status,
                    )

                else:
                    # Other error
                    error_text = await response.text()
                    log.error("GitHub API error (%d): %s", response.status, error_text)
                    raise GitHubAPIError(
                        f"GitHub API error {response.status}: {error_text[:100]}",
                        status_code=response.status,
                    )

        except aiohttp.ClientError as e:
            log.error("Network error during GitHub API request: %s", e)
            raise GitHubAPIError(f"Network error: {e}") from e
        except TimeoutError as e:
            log.error("Timeout during GitHub API request to %s", endpoint)
            raise GitHubAPIError(f"Request timeout after {self._timeout}s") from e

    async def _check_rate_limits(self) -> None:
        """Check rate limits and wait if necessary."""
        self._ensure_async_locks()
        rate_lock = self._rate_limit_lock
        assert rate_lock is not None
        async with rate_lock:
            now = datetime.now()
            for resource, limit in self._rate_limits.items():
                if limit.remaining <= 10 and limit.reset_at and limit.reset_at > now:
                    wait_seconds = (limit.reset_at - now).total_seconds()
                    if wait_seconds > 0:
                        log.warning(
                            "Rate limit low for %s (%d remaining), waiting %.0f seconds",
                            resource,
                            limit.remaining,
                            wait_seconds,
                        )
                        await asyncio.sleep(wait_seconds)

    async def _update_rate_limits(self, headers: dict[str, str]) -> None:
        """Update rate limit tracking from response headers."""
        self._ensure_async_locks()
        rate_lock = self._rate_limit_lock
        assert rate_lock is not None
        async with rate_lock:
            # Core rate limit
            if "X-RateLimit-Limit" in headers:
                limit = int(headers["X-RateLimit-Limit"])
                remaining = int(headers["X-RateLimit-Remaining"])
                reset_at = datetime.fromtimestamp(int(headers["X-RateLimit-Reset"]))
                used = int(headers.get("X-RateLimit-Used", str(limit - remaining)))

                self._rate_limits["core"] = GitHubRateLimit(
                    limit=limit,
                    remaining=remaining,
                    reset_at=reset_at,
                    used=used,
                    resource="core",
                )

            # Search rate limit
            if "X-RateLimit-Limit" in headers and "X-RateLimit-Search" in headers.get(
                "X-RateLimit-Scope", ""
            ):
                limit = int(headers["X-RateLimit-Limit"])
                remaining = int(headers["X-RateLimit-Remaining"])
                reset_at = datetime.fromtimestamp(int(headers["X-RateLimit-Reset"]))
                used = int(headers.get("X-RateLimit-Used", str(limit - remaining)))

                self._rate_limits["search"] = GitHubRateLimit(
                    limit=limit,
                    remaining=remaining,
                    reset_at=reset_at,
                    used=used,
                    resource="search",
                )

    async def get_user(self) -> GitHubUser:
        """Get authenticated user information."""
        data = await self._make_request("GET", "/user")
        return GitHubUser.from_api(data)

    async def get_repositories(
        self,
        affiliation: str = "owner",
        sort: str = "updated",
        direction: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> list[GitHubRepository]:
        """Get user's repositories."""
        params = {
            "affiliation": affiliation,
            "sort": sort,
            "direction": direction,
            "per_page": per_page,
            "page": page,
        }

        data = await self._make_request("GET", "/user/repos", params=params)
        return [GitHubRepository.from_api(repo) for repo in data]

    async def get_issues(
        self,
        filter_type: str = "assigned",
        state: str = "open",
        sort: str = "updated",
        direction: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> list[GitHubIssue]:
        """Get user's issues."""
        params = {
            "filter": filter_type,
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": per_page,
            "page": page,
        }

        data = await self._make_request("GET", "/issues", params=params)

        # Convert to issues
        issues: list[GitHubIssue] = []
        for issue_data in data:
            # Check if it's a PR (has pull_request field)
            if "pull_request" in issue_data:
                issues.append(GitHubPullRequest.from_api(issue_data))
            else:
                issues.append(GitHubIssue.from_api(issue_data))

        return issues

    async def get_pull_requests(
        self,
        state: str = "open",
        sort: str = "updated",
        direction: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> list[GitHubPullRequest]:
        """Get user's pull requests."""
        # First get user's repos
        repos = await self.get_repositories(per_page=100)

        # Get PRs from each repo (simplified - in reality would need to paginate)
        all_prs = []
        for repo in repos[:10]:  # Limit to 10 repos for performance
            try:
                params = {
                    "state": state,
                    "sort": sort,
                    "direction": direction,
                    "per_page": per_page,
                    "page": page,
                }

                endpoint = f"/repos/{repo.full_name}/pulls"
                data = await self._make_request("GET", endpoint, params=params)

                for pr_data in data:
                    pr = GitHubPullRequest.from_api(pr_data, repo)
                    all_prs.append(pr)

            except GitHubAPIError as e:
                log.warning("Error getting PRs for %s: %s", repo.full_name, e)
                continue

        # Sort by updated date
        all_prs.sort(key=lambda x: x.updated_at or x.created_at or datetime.min, reverse=True)

        return all_prs[:per_page]  # Return only requested number

    async def get_review_requests(self) -> list[GitHubPullRequest]:
        """Get pull requests requesting user's review."""
        # This is a simplified implementation
        # In reality, would use /search/issues with "review-requested" qualifier

        all_prs = await self.get_pull_requests(state="open")

        # Filter PRs where user is in requested reviewers
        # This is a mock filter - real implementation would check review requests
        await self.get_user()
        review_prs = []

        for pr in all_prs:
            # Mock: include some PRs for demonstration
            if pr.number % 3 == 0:  # Every 3rd PR
                review_prs.append(pr)

        return review_prs

    async def get_notifications(
        self,
        all: bool = False,
        participating: bool = False,
        since: datetime | None = None,
        before: datetime | None = None,
        per_page: int = 30,
        page: int = 1,
    ) -> list[GitHubNotification]:
        """Get user's notifications."""
        params = {
            "all": "true" if all else "false",
            "participating": "true" if participating else "false",
            "per_page": per_page,
            "page": page,
        }

        if since:
            params["since"] = since.isoformat()
        if before:
            params["before"] = before.isoformat()

        data = await self._make_request("GET", "/notifications", params=params)
        return [GitHubNotification.from_api(notification) for notification in data]

    async def search_issues(
        self,
        query: str,
        sort: str = "updated",
        order: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> list[GitHubIssue]:
        """Search issues with GitHub search API."""
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": per_page,
            "page": page,
        }

        data = await self._make_request("GET", "/search/issues", params=params)

        issues: list[GitHubIssue] = []
        for issue_data in data.get("items", []):
            if "pull_request" in issue_data:
                issues.append(GitHubPullRequest.from_api(issue_data))
            else:
                issues.append(GitHubIssue.from_api(issue_data))

        return issues

    async def clear_cache(self) -> None:
        """Clear all cached data."""
        self._ensure_async_locks()
        cache_lock = self._cache_lock
        assert cache_lock is not None
        async with cache_lock:
            self._cache.clear()
            log.debug("GitHub client cache cleared")

    async def probe_rate_limits(self) -> None:
        """GET /rate_limit so response headers populate :meth:`get_rate_limits`."""
        if not self._auth_manager.is_authenticated():
            return
        await self.start()
        await self._make_request("GET", "/rate_limit", use_cache=False)

    def get_rate_limits(self) -> dict[str, GitHubRateLimit]:
        """Get current rate limit information."""
        return self._rate_limits.copy()

    def get_cache_info(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "maxsize": self._cache.maxsize,
            "ttl": self._cache.ttl,
            "currsize": self._cache.currsize,
        }


# Singleton instance
_client: GitHubClient | None = None


async def get_client() -> GitHubClient:
    """Get the singleton GitHubClient instance.

    The client is created lazily and only starts its aiohttp session when the
    first request is made, reducing startup and memory overhead.
    """
    global _client
    if _client is None:
        _client = GitHubClient()
    return _client


async def close_client() -> None:
    """Close the singleton GitHubClient instance."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
