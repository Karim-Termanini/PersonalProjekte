"""HypeDevHome — Base utility manager class."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

log = logging.getLogger(__name__)


class BaseUtilityManager(ABC):
    """Abstract base class for utility managers (Hosts, Env Vars, etc)."""

    def __init__(self) -> None:
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the manager."""
        pass

    async def dispose(self) -> None:
        """Dispose resources held by the manager."""
        log.debug("Disposing %s", self.__class__.__name__)

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """Get the current status of the utility."""
        return {}
