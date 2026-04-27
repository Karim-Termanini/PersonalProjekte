"""HypeDevHome — Built-in widget registration."""

from __future__ import annotations

import logging

from ui.widgets.clock_widget import ClockWidget
from ui.widgets.cpu_widget import CPUWidget
from ui.widgets.github_registry import register_github_widgets
from ui.widgets.gpu_widget import GPUWidget
from ui.widgets.hypesync_status_widget import HypeSyncStatusWidget
from ui.widgets.memory_widget import MemoryWidget
from ui.widgets.network_widget import NetworkWidget
from ui.widgets.registry import registry
from ui.widgets.ssh_widget import SSHWidget
from ui.widgets.stack_monitor_widget import StackMonitorWidget

log = logging.getLogger(__name__)


def register_built_in_widgets() -> None:
    """Register all standard widgets with the WidgetRegistry."""
    registered_widgets = set(registry.list_widgets())

    def _register_if_missing(widget_id: str, widget_class: type) -> None:
        if widget_id not in registered_widgets:
            registry.register(widget_id, widget_class)
            registered_widgets.add(widget_id)

    _register_if_missing("clock", ClockWidget)
    _register_if_missing("cpu", CPUWidget)
    _register_if_missing("gpu", GPUWidget)
    _register_if_missing("memory", MemoryWidget)
    _register_if_missing("network", NetworkWidget)
    _register_if_missing("ssh", SSHWidget)
    _register_if_missing("stack_monitor", StackMonitorWidget)
    _register_if_missing("hypesync_status", HypeSyncStatusWidget)

    # Register GitHub widgets (they check internally)
    register_github_widgets(registry)

    log.info("Built-in widgets registered")
