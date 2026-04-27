"""HypeDevHome — Caching layer for GitHub API data."""

from __future__ import annotations

import contextlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from cachetools import TTLCache

log = logging.getLogger(__name__)


class GitHubCacheManager:
    """Manages in-memory and on-disk caching for GitHub data.

    Uses TTLCache for in-memory caching and JSON files for persistence.
    """

    def __init__(self, cache_dir: str | None = None) -> None:
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.cache/dev-home/github")

        self.cache_dir = cache_dir
        self._ensure_cache_dir()

        # In-memory caches
        # Dynamic data: issues, PRs (short TTL)
        self._dynamic_cache: TTLCache[str, Any] = TTLCache(maxsize=100, ttl=30)
        # Static data: user profiles, repo info (longer TTL)
        self._static_cache: TTLCache[str, Any] = TTLCache(maxsize=500, ttl=300)

    def _ensure_cache_dir(self) -> None:
        """Create the cache directory if it doesn't exist."""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception as e:
            log.error("Failed to create cache directory %s: %s", self.cache_dir, e)

    def get(self, key: str, is_static: bool = False) -> Any | None:
        """Get an item from the cache.

        Checks in-memory cache first, then disk cache.
        """
        # 1. Check in-memory
        cache = self._static_cache if is_static else self._dynamic_cache
        if key in cache:
            log.debug("Cache hit (memory): %s", key)
            return cache[key]

        # 2. Check disk
        data = self._load_from_disk(key)
        if data:
            log.debug("Cache hit (disk): %s", key)
            # Populate in-memory cache
            cache[key] = data
            return data

        return None

    def set(self, key: str, value: Any, is_static: bool = False) -> None:
        """Set an item in the cache (memory and disk)."""
        # 1. Update in-memory
        cache = self._static_cache if is_static else self._dynamic_cache
        cache[key] = value

        # 2. Update disk
        self._save_to_disk(key, value)

    def _get_cache_path(self, key: str) -> str:
        """Generate a safe filename for a cache key."""
        import hashlib

        hashed_key = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{hashed_key}.json")

    def _save_to_disk(self, key: str, value: Any) -> None:
        """Persist a cache item to disk."""
        path = self._get_cache_path(key)
        try:
            with open(path, "w") as f:
                json.dump(
                    {
                        "key": key,
                        "timestamp": datetime.now().isoformat(),
                        "data": value,
                    },
                    f,
                )
        except Exception as e:
            log.warning("Failed to save cache to disk: %s", e)

    def _load_from_disk(self, key: str, max_age_days: int = 7) -> Any | None:
        """Load a cache item from disk if it's not too old."""
        path = self._get_cache_path(key)
        if not os.path.exists(path):
            return None

        try:
            with open(path) as f:
                item = json.load(f)

            timestamp = datetime.fromisoformat(item["timestamp"])
            if datetime.now() - timestamp > timedelta(days=max_age_days):
                # Too old, remove it
                os.remove(path)
                return None

            return item["data"]
        except Exception as e:
            log.warning("Failed to load cache from disk: %s", e)
            return None

    def clear(self) -> None:
        """Clear all in-memory and on-disk caches."""
        self._dynamic_cache.clear()
        self._static_cache.clear()

        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith(".json"):
                    with contextlib.suppress(Exception):
                        os.remove(os.path.join(self.cache_dir, filename))
        log.info("GitHub cache cleared")


_default_disk_cache: GitHubCacheManager | None = None


def get_github_disk_cache() -> GitHubCacheManager:
    """Shared on-disk + in-memory cache used by GitHub tooling."""
    global _default_disk_cache
    if _default_disk_cache is None:
        _default_disk_cache = GitHubCacheManager()
    return _default_disk_cache
