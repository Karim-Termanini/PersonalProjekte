# Phase 2 — Dashboard & system widgets — status

**Branch reference:** `phase-2-dashboard-system-widgets`  
**Last reviewed:** 2026-04-14 (codebase audit; Agent 2 memory/GPU items verified)

This document replaces a missing “✅ COMPLETE” report with an evidence-based checklist against the original deliverables.

---

## Summary


| Area                                                                     | Status                     | Notes                                                                                                                          |
| ------------------------------------------------------------------------ | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Dashboard shell (page, layout persistence, gallery, DnD, resize, remove) | **Mostly done**            | FlowBox layout (responsive), not a rigid CSS grid; resize/menu wired                                                           |
| Widget gallery (search, categories, preview)                             | **Mostly done**            | Categories come from `widget_category` on classes; no separate “Community” stub row                                            |
| CPU widget                                                               | **Largely done**           | Per-core, load, freq, temp, chart, 80/90% styling; refresh driven by `SystemMonitor` interval                                  |
| GPU widget + backend                                                     | **Largely done**           | `sysmon.gpu` emits `gpus` + `gpu_count`; flat fields = selected/first GPU; `gpu_widget` DropDown + `gpu_index` in `get_config` |
| Memory widget                                                            | **Largely done**           | RAM/swap + chart; **warning** ≥85% / **error** ≥95% on labels + bar; swap label tiers when swap in use                         |
| Network widget + backend                                                 | **Largely done (Agent 1)** | Public IP (cached HTTP); iface dropdown; link state; peaks + since-boot totals; per-NIC speeds                                 |
| SSH widget                                                               | **Largely done**           | `ssh-add -l`, add/remove, agent checks; implementation is substantial                                                          |
| Monitoring backend                                                       | **Largely done**           | Daemon thread + psutil + EventBus; **not** proven “<5% CPU”                                                                    |


**Conclusion:** Phase 2 is **not** fully complete against the written spec. Remaining gaps include **<5% monitor CPU** verification and miscellaneous polish. **Network** (Agent 1) and **memory tiers + multi-GPU** (Agent 2) are implemented.

---

## 1. Dashboard framework


| Requirement                     | Status      | Where / notes                                                                       |
| ------------------------------- | ----------- | ----------------------------------------------------------------------------------- |
| Dashboard page with grid layout | **Partial** | `DashboardPage` + `DashboardGrid` use `Gtk.FlowBox` (reflow), not a fixed cell grid |
| Add widgets from gallery        | **Yes**     | `WidgetGalleryDialog` + `add_widget_by_id`                                          |
| Remove widgets                  | **Yes**     | Menu action → `remove_widget`                                                       |
| Drag-and-drop repositioning     | **Yes**     | `DashboardWidget` drag source + `FlowBox` drop                                      |
| Resize (1×1, 2×1, 2×2)          | **Yes**     | `set_size_request` from spans; menu actions                                         |
| Widget configuration dialogs    | **Partial** | Base `PreferencesDialog` + some widgets extend                                      |
| Layout save/restore             | **Yes**     | `dashboard_layout` in config via `_update_state_from_layout`                        |


---

## 2. Widget gallery


| Requirement                    | Status  | Where / notes                                      |
| ------------------------------ | ------- | -------------------------------------------------- |
| Categories (System, GitHub, …) | **Yes** | Populated from `widget_category` on widget classes |
| Community (future)             | **No**  | No placeholder category unless a widget sets it    |
| Search / filter                | **Yes** | `Gtk.SearchEntry` + dropdown                       |
| Preview before adding          | **Yes** | Right-hand preview pane                            |
| Double-click / Add button      | **Yes** | Implemented                                        |


---

## 3. CPU widget


| Requirement                | Status      | Where / notes                                             |
| -------------------------- | ----------- | --------------------------------------------------------- |
| Overall + per-core         | **Yes**     | `sysmon.cpu` + bars in `cpu_widget.py`                    |
| Frequency                  | **Yes**     | From `psutil.cpu_freq()`                                  |
| Load (1, 5, 15)            | **Yes**     | `getloadavg()`                                            |
| Temperature                | **Yes**     | `_get_cpu_temperature()` in `system.py`                   |
| Live chart                 | **Yes**     | `LineChart`                                               |
| Configurable refresh       | **Partial** | Global monitor interval; per-widget spin in base settings |
| Color warnings >80% / >90% | **Yes**     | CSS classes on label / per-core                           |


---

## 4. GPU widget


| Requirement                                   | Status  | Where / notes                                                                                |
| --------------------------------------------- | ------- | -------------------------------------------------------------------------------------------- |
| Utilization, VRAM, temp, fan (when available) | **Yes** | `gpu_widget.py` + `sysmon.gpu`                                                               |
| NVIDIA / AMD / Intel                          | **Yes** | `_collect_*_gpu` in `system.py` (nvidia-smi + sysfs)                                         |
| radeontop / intel_gpu_top                     | **No**  | Not used; sysfs-first                                                                        |
| Fallback when unavailable                     | **Yes** | `detected=False` path                                                                        |
| Multi-GPU                                     | **Yes** | `system.py` emits `gpus` / `gpu_count`; `gpu_widget` DropDown when >1; `gpu_index` persisted |


---

## 5. Memory widget


| Requirement          | Status  | Where / notes                                                       |
| -------------------- | ------- | ------------------------------------------------------------------- |
| RAM used/total, swap | **Yes** |                                                                     |
| Live graph           | **Yes** |                                                                     |
| Percentage           | **Yes** |                                                                     |
| Warnings >85% / >95% | **Yes** | CSS `warning` / `error` on bar + percent + RAM label                |
| Color-coded bars     | **Yes** | Same tiers on `Gtk.ProgressBar`; swap label warned when swap in use |


---

## 6. Network widget


| Requirement              | Status  | Where / notes                                                               |
| ------------------------ | ------- | --------------------------------------------------------------------------- |
| Real-time up/down speeds | **Yes** |                                                                             |
| Public IP                | **Yes** | Cached HTTPS fetch (ipify / icanhazip / ifconfig.me) in `SystemMonitor`     |
| Local IP                 | **Yes** | Default route + per-interface IPv4 in `per_nic`                             |
| Connection status        | **Yes** | `connected` = carrier + non-local IPv4 on a non-loopback iface              |
| Live graph               | **Yes** |                                                                             |
| Interface selector       | **Yes** | `Gtk.DropDown` in `network_widget.py`; `network_interface` in `get_config`  |
| Peaks / totals           | **Yes** | Peaks (session, reset on iface change); totals = kernel counters since boot |


---

## 7. SSH keychain widget


| Requirement                                | Status  | Where / notes   |
| ------------------------------------------ | ------- | --------------- |
| List keys, fingerprints, add/remove/reload | **Yes** | `ssh_widget.py` |
| Agent detection / errors                   | **Yes** |                 |


---

## 8. System monitoring backend


| Requirement                   | Status           | Where / notes                         |
| ----------------------------- | ---------------- | ------------------------------------- |
| Background worker             | **Yes**          | `threading.Thread` in `SystemMonitor` |
| Polling interval (default 2s) | **Yes**          | Constructor + `start()`               |
| Thread-safe path to UI        | **Yes**          | EventBus + `GLib.idle_add` in widgets |
| Degradation on errors         | **Yes**          | try/emit defaults                     |
| CPU overhead <5%              | **Not verified** | No benchmark in repo                  |


---

## Recommended next steps (to match spec)

1. **Network (polish):** Optional UI for “reset session peaks”; VPN users may want to exclude `tun` from “All” aggregate.
2. **Docs / CI:** Add a short script or note on measuring monitor CPU overhead.
3. **Gallery:** Add an empty “Community” section or registry flag for future widgets.

---

## Files of interest

- `src/ui/pages/dashboard.py`, `src/ui/widgets/dashboard_grid.py`, `src/ui/widgets/dashboard_widget.py`
- `src/ui/widgets/widget_gallery.py`, `src/ui/widgets/registry.py`, `src/ui/widgets/init_registry.py`
- `src/core/monitoring/system.py`
- `src/ui/widgets/cpu_widget.py`, `memory_widget.py`, `network_widget.py`, `gpu_widget.py`, `ssh_widget.py`
- `src/config/defaults.py` (`DEFAULT_DASHBOARD_LAYOUT`)

