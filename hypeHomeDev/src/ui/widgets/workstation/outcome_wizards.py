"""Outcome-driven setup flows (Phase 9).

Orchestration lives in :class:`core.setup.power_installer.PowerInstaller` (including
:meth:`~PowerInstaller.run_all_profiles` power mode) and profiles in
``src/core/setup/outcome_profiles.json``. The **Welcome** / **Home** dashboards host the UI
(:class:`WorkstationSystemDashboardPanel` in ``system_dashboard.py``).
"""

from __future__ import annotations

from core.setup.power_installer import OutcomeProfile, PowerInstaller

__all__ = ["OutcomeProfile", "PowerInstaller"]
