"""Reusable widgets for the Workstation hub (Phase 7)."""

from ui.widgets.workstation.ai_manager import WorkstationAIPanel
from ui.widgets.workstation.apps_panel import WorkstationAppsPanel
from ui.widgets.workstation.panels import (
    WorkstationConfigPanel,
    WorkstationInstallPanel,
    WorkstationRemovePanel,
)
from ui.widgets.workstation.servers_manager import WorkstationServersPanel
from ui.widgets.workstation.service_manager import WorkstationServicesPanel
from ui.widgets.workstation.system_dashboard import WorkstationSystemDashboardPanel

__all__ = [
    "WorkstationAIPanel",
    "WorkstationAppsPanel",
    "WorkstationConfigPanel",
    "WorkstationInstallPanel",
    "WorkstationRemovePanel",
    "WorkstationServersPanel",
    "WorkstationServicesPanel",
    "WorkstationSystemDashboardPanel",
]
