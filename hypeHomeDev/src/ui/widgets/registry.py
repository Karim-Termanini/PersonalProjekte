"""HypeDevHome — Registry for dashboard widgets."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from ui.widgets.dashboard_widget import DashboardWidget

log = logging.getLogger(__name__)


class WidgetRegistry:
    """Registry for available dashboard widget types.

    Allows plugins and built-in modules to register widget classes.
    """

    _instance: WidgetRegistry | None = None
    _widgets: ClassVar[dict[str, type[DashboardWidget]]] = {}

    def __new__(cls) -> WidgetRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def instance(cls) -> WidgetRegistry:
        """Return the shared WidgetRegistry singleton instance."""
        return cls()

    @classmethod
    def register(cls, widget_id: str, widget_class: type[DashboardWidget]) -> None:
        """Register a new widget type.

        Args:
            widget_id: Unique identifier for the widget type.
            widget_class: The DashboardWidget subclass to register.
        """
        registry = cls.instance()
        if widget_id in registry._widgets:
            log.warning("Widget ID '%s' is already registered. Overwriting.", widget_id)

        registry._widgets[widget_id] = widget_class
        log.debug("Registered widget: %s (%s)", widget_id, widget_class.__name__)

    @classmethod
    def get_widget_class(cls, widget_id: str) -> type[DashboardWidget] | None:
        """Return the widget class for the given ID.

        Args:
            widget_id: Identifier of the widget type to retrieve.

        Returns:
            The widget class or None if not found.
        """
        return cls.instance()._widgets.get(widget_id)

    @classmethod
    def list_widgets(cls) -> list[str]:
        """Return a list of all registered widget IDs."""
        return list(cls.instance()._widgets.keys())

    @classmethod
    def unregister(cls, widget_id: str) -> None:
        """Remove a widget type from the registry."""
        registry = cls.instance()
        if widget_id in registry._widgets:
            del registry._widgets[widget_id]
            log.debug("Unregistered widget: %s", widget_id)

    @classmethod
    def is_registered(cls, widget_id: str) -> bool:
        """Return whether the widget ID is already registered."""
        return widget_id in cls.instance()._widgets


# Global instance
registry = WidgetRegistry()
