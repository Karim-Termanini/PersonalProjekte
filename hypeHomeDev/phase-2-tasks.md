# Phase 2: `phase-2-dashboard-system-widgets` — Task Breakdown

> **Branch:** `phase-2-dashboard-widgets`
> **Goal:** Implement the customizable dashboard with all system monitoring widgets.
> **Agents:** 3 (Agent A, Agent B, Agent C)

---

## Agent Assignment Overview

| Agent | Focus Area | Deliverables |
|-------|-----------|--------------|
| **A** | Dashboard Framework & Widget Management | Dashboard page, grid layout, widget registry, add/remove/reorder, layout persistence, widget gallery |
| **B** | CPU + GPU + SSH Widgets & Monitoring Backend | System monitor backend (threads, polling), CPU widget, GPU widget, SSH Keychain widget |
| **C** | Memory + Network Widgets & Widget Config | Memory widget, Network widget, widget config dialogs, widget base class enhancements, tests |

---

## Agent A — Dashboard Framework & Widget Management

### Task A.1: Widget Base Class
**Priority:** High
**Dependencies:** Phase 1 C.2

Create `src/ui/widgets/base_widget.py`:
- Abstract `WidgetBase` class extending `Gtk.Box`
- Properties: `widget_id`, `title`, `icon_name`, `size_hint` (1x1, 2x1, 2x2)
- Methods: `refresh()`, `configure()`, `serialize()`, `deserialize()`
- Header bar with widget title, menu button, close button
- Loading state handling
- Error state handling

### Task A.2: Widget Registry
**Priority:** High
**Dependencies:** A.1

Create `src/core/widget_registry.py`:
- Registry of all available widgets
- Widget metadata: id, name, description, icon, category, default_size
- Built-in system widgets registration
- Query widgets by category
- Thread-safe access

### Task A.3: Dashboard Page
**Priority:** High
**Dependencies:** A.2

Create `src/ui/pages/dashboard.py`:
- Replace placeholder dashboard from Phase 1
- `Adw.ToolbarView` with header bar
- Grid/flow layout for widgets (`Gtk.FlowBox` or custom grid)
- "Add Widget" button in header
- Edit mode toggle (show close handles, drag grips)
- Empty state when no widgets added

### Task A.4: Widget Gallery Dialog
**Priority:** High
**Dependencies:** A.2

Create `src/ui/dialogs/widget_gallery.py`:
- Modal dialog showing available widgets
- Categories: System, GitHub (disabled/placeholder), Community (disabled/placeholder)
- Grid preview of widget cards
- Search bar to filter widgets
- Click to add widget to dashboard
- Close/cancel button

### Task A.5: Layout Persistence
**Priority:** Medium
**Dependencies:** A.3

Dashboard layout save/restore:
- Save layout to JSON in `~/.config/dev-home/dashboard.json`
- Schema: widget id, position (row, col), size (width, height), config
- Load layout on dashboard page creation
- Migrate layout on version changes
- Reset to default layout option

### Task A.6: Drag-and-Drop Reordering
**Priority:** Low
**Dependencies:** A.3

- `Gtk.DropDown` or drag gestures for reordering
- Visual feedback during drag
- Save new order to layout config
- Placeholder if full DnD is too complex for Phase 2

### Acceptance Criteria (Agent A)
- [ ] Dashboard page loads with saved layout
- [ ] Widget gallery opens and displays widgets
- [ ] Adding widget from gallery appears on dashboard
- [ ] Removing widget updates dashboard and saves layout
- [ ] Layout persists across app restarts
- [ ] Empty state shows when no widgets present

---

## Agent B — CPU + GPU + SSH Widgets & Monitoring Backend

### Task B.1: System Monitor Backend
**Priority:** High
**Dependencies:** Phase 1 C.6 (EventBus)

Create `src/core/system_monitor.py`:
- `SystemMonitor` class with background worker thread
- Polling loop with configurable interval (default 2s)
- Data models (dataclasses):
  - `CPUData`: usage_percent, per_core_usage[], frequency_mhz, load_avg[], temp_celsius
  - `MemoryData`: used_mb, available_mb, total_mb, swap_used_mb, swap_total_mb, used_percent
  - `NetworkData`: download_bytes, upload_bytes, download_speed, upload_speed, interface_name
  - `GPUData`: vendor, utilization_percent, vram_used_mb, vram_total_mb, temp_celsius, fan_percent
  - `SSHKeyData`: key_path, fingerprint, comment, loaded_timestamp
- Thread-safe data access with `threading.Lock`
- `subscribe()` / `unsubscribe()` for data consumers
- Emit data via EventBus events
- Graceful degradation when data unavailable
- Minimal CPU/memory overhead

### Task B.2: CPU Widget
**Priority:** High
**Dependencies:** B.1, A.1

Create `src/ui/widgets/cpu_widget.py`:
- Overall CPU usage percentage (large number + progress ring)
- Per-core usage bars (mini sparklines)
- Current frequency display
- Load average (1, 5, 15 min)
- Temperature (when available via `/sys/class/thermal/` or `sensors`)
- Live updating chart (simple `Gtk.DrawingArea` line chart)
- Color-coded warnings: >80% orange, >90% red
- Configurable refresh interval

### Task B.3: GPU Widget
**Priority:** High
**Dependencies:** B.1, A.1

Create `src/ui/widgets/gpu_widget.py`:
- GPU utilization percentage
- VRAM usage (used/total bar)
- Temperature (when available)
- Fan speed (when available)
- Auto-detection for GPU vendors:
  - NVIDIA: `nvidia-smi` or `/proc/driver/nvidia/gpus/`
  - AMD: `/sys/class/drm/` or `radeontop`
  - Intel: `/sys/class/drm/` or `intel_gpu_top`
- Fallback: show "No GPU detected" or "GPU info unavailable"
- Multi-GPU: show primary, allow selection in config

### Task B.4: SSH Keychain Widget
**Priority:** Medium
**Dependencies:** A.1

Create `src/ui/widgets/ssh_widget.py`:
- List loaded SSH keys from `ssh-add -l`
- Show fingerprint (truncated), comment
- Status indicator (loaded/unloaded)
- Buttons:
  - Add key (file picker → `ssh-add`)
  - Reload ssh-agent
  - Remove selected key (`ssh-add -d`)
- Auto-detect ssh-agent availability (`$SSH_AUTH_SOCK`)
- Error handling for agent communication failures
- Parse output safely (no command injection)

### Acceptance Criteria (Agent B)
- [ ] System monitor polls data without blocking UI
- [ ] CPU widget shows correct data and updates live
- [ ] GPU widget detects vendor and shows info
- [ ] SSH widget lists loaded keys and can add/remove
- [ ] All widgets handle missing data gracefully
- [ ] Monitor thread CPU usage stays below 2%

---

## Agent C — Memory + Network Widgets & Tests

### Task C.1: Memory Widget
**Priority:** High
**Dependencies:** B.1, A.1

Create `src/ui/widgets/memory_widget.py`:
- RAM usage: used/available/total
- Large circular progress indicator
- Swap usage bar
- Live memory graph (sparkline)
- Percentage indicators
- Color-coded warnings: >85% orange, >95% red
- Used/available breakdown with color-coded bars

### Task C.2: Network Widget
**Priority:** High
**Dependencies:** B.1, A.1

Create `src/ui/widgets/network_widget.py`:
- Real-time download/upload speeds (large numbers)
- Speed unit auto-formatting (B/s, KB/s, MB/s)
- Live speed graph (sparkline)
- Local IP address (from `psutil.net_if_addrs()` or `ip addr`)
- Connection status indicator
- Network interface selector dropdown
- Peak speeds display
- Total transferred (session)

### Task C.3: Widget Configuration Dialogs
**Priority:** Medium
**Dependencies:** A.1

Create `src/ui/dialogs/widget_config.py`:
- Generic widget config dialog base class
- Per-widget config panels:
  - CPU: refresh interval, show/hide temperature, per-core view toggle
  - GPU: GPU selection (multi-GPU), show/hide fan speed
  - Memory: refresh interval, show/hide swap
  - Network: interface selection, show/hide peak speeds
- Save config to widget instance metadata
- Apply config triggers widget refresh

### Task C.4: Simple Chart Component
**Priority:** Medium
**Dependencies:** None

Create `src/ui/widgets/chart.py`:
- `LineChart` — simple `Gtk.DrawingArea` based line chart
- Configurable data window (last N points)
- Configurable colors, line width
- Grid lines (optional)
- Y-axis labels
- Smooth anti-aliased rendering
- Auto-scaling Y axis
- Used by CPU, Memory, Network widgets

### Task C.5: Phase 2 Tests
**Priority:** High
**Dependencies:** B.1, C.1, C.2, C.4

- `tests/test_core/test_system_monitor.py` — Monitor lifecycle, data models, thread safety
- `tests/test_core/test_widget_registry.py` — Registration, querying, serialization
- `tests/test_ui/test_cpu_widget.py` — Instantiation, data display
- `tests/test_ui/test_memory_widget.py` — Instantiation, data display
- `tests/test_ui/test_network_widget.py` — Instantiation, data display
- `tests/test_ui/test_chart.py` — Chart rendering (non-visual)
- `tests/test_ui/test_dashboard_page.py` — Page creation, layout load/save

### Acceptance Criteria (Agent C)
- [ ] Memory widget shows correct data and updates live
- [ ] Network widget shows correct speeds and interface
- [ ] Chart component renders correctly
- [ ] Widget config dialogs save and apply settings
- [ ] All Phase 2 tests pass
- [ ] Total test count increases (target: 120+)

---

## Integration Points

1. **Agent A ↔ Agent B:** Widget base class used by CPU/GPU/SSH widgets; registry knows all widgets
2. **Agent A ↔ Agent C:** Widget base class used by Memory/Network widgets; chart used by multiple widgets
3. **Agent B ↔ Agent C:** Both depend on `SystemMonitor` backend; share data models

---

## Execution Order

```
Phase 2 Execution Timeline:

┌───────────────────────────────────────────────────────┐
│                    PARALLEL START                     │
├─────────────┬──────────────────┬──────────────────────┤
│  Agent A    │     Agent B      │       Agent C        │
│             │                  │                      │
│  A.1 Base   │  B.1 Monitor     │  C.1 Memory Widget   │
│  A.2 Reg    │  B.2 CPU Widget  │  C.2 Network Widget  │
│  A.3 Page   │  B.3 GPU Widget  │  C.4 Chart Component │
│  A.4 Gallery│  B.4 SSH Widget  │  C.3 Widget Config   │
│  A.5 Layout │                  │                      │
│  A.6 DnD    │                  │                      │
├─────────────┴──────────────────┴──────────────────────┤
│                     INTEGRATION                        │
│                                                        │
│  C.5 Tests (all components)                           │
│  Full dashboard with all 5 system widgets              │
├────────────────────────────────────────────────────────┤
│                     FINAL TESTING                      │
│                                                        │
│  All widgets update in real-time                       │
│  Layout persists across restarts                       │
│  Target: 120+ tests passing                            │
└────────────────────────────────────────────────────────┘
```

---

## Deliverables Summary

| Agent | Key Files Created |
|-------|------------------|
| **A** | `src/ui/widgets/base_widget.py`, `src/core/widget_registry.py`, `src/ui/pages/dashboard.py`, `src/ui/dialogs/widget_gallery.py` |
| **B** | `src/core/system_monitor.py`, `src/ui/widgets/cpu_widget.py`, `src/ui/widgets/gpu_widget.py`, `src/ui/widgets/ssh_widget.py` |
| **C** | `src/ui/widgets/memory_widget.py`, `src/ui/widgets/network_widget.py`, `src/ui/dialogs/widget_config.py`, `src/ui/widgets/chart.py` |
