# Phase 2: `phase-2-dashboard-system-widgets` — Task Breakdown

> **Branch:** `phase-2-dashboard-widgets`
> **Goal:** Implement the customizable dashboard with real-time system monitoring widgets.
> **Agents:** 3 (Agent A, Agent B, Agent C)

---

## Agent Assignment Overview

| Agent | Focus Area | Deliverables |
|-------|-----------|--------------|
| **Agent A** | Dashboard Framework & Management | Widget grid, base classes, widget gallery, layout persistence |
| **Agent B** | System Monitoring & Backend Data | psutil integration, GPU detection, network monitoring, SSH agent bridge |
| **Agent C** | Widget Visualization & UI Components | Charting, specific system widgets (CPU, GPU, RAM, Net), SSH widget |

---

## Agent A — Dashboard Framework & Management

### Task A.1: Dashboard Widget Foundation
**Priority:** High
**Dependencies:** Phase 1 A.4 (Page Framework)

Define the core widget architecture in `src/ui/widgets/dashboard_widget.py`:
- `DashboardWidget` base class inheriting from `Card`.
- Standard lifecycle hooks: `on_activate`, `on_deactivate`, `refresh`.
- Configuration schema for widgets.
- Loading/Error states specifically for dashboard cards.

### Task A.2: Responsive Dashboard Grid
**Priority:** High
**Dependencies:** A.1

Refactor `src/ui/pages/dashboard.py`:
- Replace placeholder with `Gtk.FlowBox` wrapped in `Adw.Clamp`.
- Implement a `DashboardGrid` manager to handle widget instances.
- Support for responsive reflowing (adjusting columns based on width).

### Task A.3: Widget Gallery UI
**Priority:** Medium
**Dependencies:** A.2

Create a widget picker/installer:
- `WidgetGalleryDialog` to browse available widgets.
- Search and category filtering.
- Preview cards for widgets before adding.

### Task A.4: Layout Persistence
**Priority:** High
**Dependencies:** Phase 1 B.4 (Config Manager)

Implement dashboard state saving:
- Save active widget list and ordering to `config.json`.
- Automatic restoration of dashboard state on startup.
- Basic reordering support (Drag-and-Drop or "Move" actions).

### Acceptance Criteria (Agent A)
- [ ] Dashbord grid reflows correctly on window resize
- [ ] Widgets can be added/removed dynamically
- [ ] Dashboard layout persists across restarts
- [ ] Base widget class provides clean API for other agents

---

## Agent B — System Monitoring & Backend Data

### Task B.1: System Monitoring Service
**Priority:** High

Implement `src/core/monitoring/system.py`:
- Thread-safe background collector using `psutil`.
- Real-time CPU usage (per-core), RAM, and Swap data.
- Event-driven updates to notify UI components.

### Task B.2: GPU Monitoring Backend
**Priority:** High

Implement GPU detection logic:
- NVIDIA support via `nvidia-smi` parser.
- AMD/Intel support via `sysfs` or specialized tools.
- Unified GPU data structure (utilization, VRAM, temp).

### Task B.3: Network & IP Service
**Priority:** Medium

Implement network status monitoring:
- Link speed (Up/Down).
- Local IP detection.
- Public IP detection (with caching and error handling).

### Task B.4: SSH Agent Bridge
**Priority:** Medium

Implement `src/core/monitoring/ssh.py`:
- Interface with `ssh-agent` via UNIX socket.
- List loaded keys and fingerprints.
- Signal when keys are added or removed.

---

## Agent C — Widget Visualization & UI Components

### Task C.1: Professional Charting Library
**Priority:** High

Implement reusable charting components:
- `LiveChart` widget using `Gtk.DrawingArea` or `Cairo`.
- Smooth line graphs for CPU/Network activity.
- Efficient rendering to stay below 5% total CPU usage.

### Task C.2: System Resource Widgets
**Priority:** High
**Dependencies:** B.1, C.1

Implement specific widgets:
- **CPU Widget**: Overall load + per-core sparklines.
- **Memory Widget**: Detailed RAM/Swap bars and percentage.
- **Network Widget**: Live speed graph + IP info.

### Task C.3: GPU & SSH Widgets
**Priority:** Medium
**Dependencies:** B.2, B.4

- **GPU Widget**: Utilization gauge, VRAM usage, and vendor icon.
- **SSH Widget**: List of active keys with "Add/Remove" quick actions.

---

## Phase 2 Acceptance Criteria (Global)
- [ ] All 5 system widgets display accurate real-time data.
- [ ] CPU usage of the entire monitoring system is < 5% during idle.
- [ ] Dashboard layout is fully responsive and persists.
- [ ] No UI freezing during background data collection.
