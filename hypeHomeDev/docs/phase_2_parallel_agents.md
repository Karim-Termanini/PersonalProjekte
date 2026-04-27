# Phase 2 — parallel agent split

Two agents can work **at the same time** if they respect the **file/section boundaries** below. Merge conflicts happen if both edit the same region of `src/core/monitoring/system.py` — the split avoids that.

---

## Agent 1 — Network & connectivity

**Goal:** Close the network gaps in `walkthrough_phase_2.md` (public IP, interface awareness, richer status, show peaks/totals).

### Owns (edit freely)
| File | Scope |
|------|--------|
| `src/ui/widgets/network_widget.py` | Full file: UI for iface selector, public IP line, peak/total labels, charts |
| `src/core/monitoring/system.py` | **Only** the **network** branch inside `_collect_and_emit` and **network-only** helpers (e.g. `_get_local_ip`, per-interface counters, optional public-IP fetch). **Do not change** `_collect_gpu_data`, `_collect_nvidia_gpu`, CPU, memory, or GPU sysfs helpers. |

### Optional (if you want zero `system.py` growth)
- Add `src/core/monitoring/network_details.py` (or similar) for public IP + iface listing; call it from `system.py` in the network block only.

### Acceptance (Agent 1)
- [x] Public IP shown (cached HTTP in monitor thread; ~5 min TTL; falls back to empty).
- [x] User can choose a **network interface** (or “All”); speeds/totals follow selection; `network_interface` persisted in `get_config`.
- [x] **Peak** (per session; resets when iface changes) and **since-boot totals** (kernel byte counters) visible.
- [x] **Connected** = at least one non-loopback iface up with a non-local IPv4.

### Do **not** touch
- `memory_widget.py`, `gpu_widget.py`, GPU-related functions in `system.py`.

---

## Agent 2 — Memory thresholds & GPU depth

**Goal:** Memory warning tiers per spec; GPU multi-device or clearer primary/secondary handling.

### Owns (edit freely)
| File | Scope |
|------|--------|
| `src/ui/widgets/memory_widget.py` | Full file: 85% / 95% warnings, color classes, optional swap warnings |
| `src/ui/widgets/gpu_widget.py` | Full file: multi-GPU picker or tabs, settings persistence via `get_config` |
| `src/core/monitoring/system.py` | **Only** `_collect_gpu_data`, `_collect_nvidia_gpu`, `_collect_amd_gpu`, `_collect_intel_gpu`, and GPU sysfs helpers. **Do not change** the network block, `_get_local_ip`, or net I/O emission. |

### Optional
- `src/ui/style/gtk.css` — only for memory/GPU warning classes if needed.
- Registry / `get_config` keys for selected GPU index.

### Acceptance (Agent 2)
- [x] RAM usage applies **warning styling** at **≥85%** and **stronger** at **≥95%** (labels and/or progress).
- [x] Swap near-full optionally warned (if trivial).
- [x] **Multi-GPU:** either emit a **list** of GPUs and let the widget select, or document “primary only” + implement **selection** for NVIDIA multi-card at minimum.

### Do **not** touch
- `network_widget.py`, network section of `system.py`.

---

## Shared rules (both agents)

1. **`system.py`:** If you must add imports or a small shared helper used by both, **coordinate** or put shared code in a **new module** (e.g. `monitoring/utils.py`) to reduce conflict.
2. **EventBus payloads:** Extend `sysmon.network` / `sysmon.gpu` with **optional** keys so old widgets keep working until updated.
3. **Update** `walkthrough_phase_2.md` checkboxes for your scope when done.
4. Run **format/lint** on touched files before PR.

---

## Dependency order (only if something breaks)

- If Agent 2 changes `sysmon.gpu` shape **before** Agent 1 finishes, Agent 1 is unaffected (different events).
- If both need a new dependency in `pyproject.toml`, **one** agent adds it or merge carefully.

---

## Quick reference — who edits what in `system.py`

```
Agent 1:  lines / functions dealing with net_io_counters, network emit, _get_local_ip, public IP
Agent 2:  lines / functions dealing with _collect_gpu_data, _collect_*_gpu, GPU sysfs
```

When in doubt, **search** for `sysmon.network` vs `sysmon.gpu` and stay on your side.
