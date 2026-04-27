# HypeDevHome — Project Structure

> **⚠️ Strategic Note:** Built on **Flatpak + Docker** for cross-distribution compatibility. Runs natively on any Linux distro without modifications.

---

## Navigation (current)

4 top-level sections — clean, no duplicates:

| # | Section | Shortcut | Description |
|---|---------|----------|-------------|
| 1 | **Dashboard** | `Ctrl+1` | Health status + metric cards + customisable widget grid |
| 2 | **Tools** | `Ctrl+2` | Apps, Servers, Services, AI, Config, Install, Remove, Extensions |
| 3 | **Maintenance** | `Ctrl+3` | Guardian snapshots + Pulse + active tasks |
| 4 | **Settings** | `Ctrl+4` | Hosts editor, Env vars, Desktop config, System info |

**Monitor data lives in Tools → Servers → Overview** (no separate Monitor page).  
**Machine Setup wizard lives in Tools → Install** (no separate sidebar item).  
**Widget grid lives in Dashboard** (no separate Widgets page).

---

## Technology Stack

- **Language:** Python 3.11+
- **UI:** GTK4 + Libadwaita (GNOME HIG)
- **Theme:** Nordic dark (`#1a1d23` bg, `#5cb8b2` accent)
- **Distribution:** Flatpak (primary)
- **Dev env:** Docker

---

## Directory Structure

```
hypeHomeDev/
├── src/
│   ├── main.py                     # App entry point
│   ├── app.py                      # Adw.Application + task queue
│   ├── core/
│   │   ├── config.py               # Config manager (~/.config/dev-home/)
│   │   ├── state.py                # AppState singleton
│   │   ├── maintenance/            # Guardian: snapshots, pulse, retention
│   │   │   ├── guardian.py
│   │   │   ├── pulse_manager.py
│   │   │   └── snapshot_manager.py
│   │   ├── monitoring/             # System metrics background workers
│   │   │   ├── system.py
│   │   │   └── github_monitor.py
│   │   └── setup/                  # HostExecutor, PowerInstaller, profiles
│   │       ├── host_executor.py
│   │       ├── power_installer.py
│   │       └── outcome_profiles.json
│   └── ui/
│       ├── window.py               # Main window + 4-page registry
│       ├── app.py                  # Application bootstrap
│       ├── style/
│       │   └── gtk.css             # Nordic theme (single source of truth)
│       ├── pages/                  # Top-level pages (4 active)
│       │   ├── base_page.py        # BasePage ABC (lazy build, on_shown/hidden)
│       │   ├── dashboard.py        # ★ Dashboard: health + widgets (ACTIVE)
│       │   ├── workstation.py      # ★ Tools hub (ACTIVE)
│       │   ├── maintenance_hub.py  # ★ Maintenance (ACTIVE)
│       │   ├── utilities.py        # ★ Settings (ACTIVE)
│       │   ├── machine_setup.py    # Machine setup wizard (standalone, not in rail)
│       │   ├── system_monitor.py   # (not in rail — FHS reference only)
│       │   ├── welcome_dashboard.py# (legacy — not in rail)
│       │   ├── extensions.py       # (legacy — merged into Tools)
│       │   └── setup_views.py      # Sub-views for machine setup
│       ├── widgets/
│       │   ├── dashboard_grid.py   # Customisable widget grid
│       │   ├── widget_gallery.py   # Widget picker dialog
│       │   ├── pulse_dashboard.py  # Maintenance pulse UI
│       │   ├── hosts_editor.py
│       │   ├── env_editor.py
│       │   ├── desktop_config.py
│       │   ├── utilities_system_info.py
│       │   └── workstation/        # All Tools sub-panels
│       │       ├── apps_panel.py
│       │       ├── servers_manager.py
│       │       ├── servers_overview.py   # Live system overview (monitor data)
│       │       ├── docker_manager.py
│       │       ├── service_manager.py
│       │       ├── ai_manager.py
│       │       ├── panels.py             # Config, Install, Remove panels
│       │       ├── bash_cheatsheet.py    # In Tools → Config
│       │       ├── linux_filesystem_page.py  # FHS reference
│       │       ├── system_dashboard.py   # System health in Tools hub
│       │       └── learn_factory.py      # Contextual docs loader
│       ├── dialogs/                # Reusable dialogs
│       ├── about.py
│       ├── settings.py
│       └── toast_manager.py
├── tests/                          # pytest test suite (80%+ coverage required)
├── data/                           # JSON catalogs, configs
├── assets/                         # Icons, images
├── development-plan.md             # Phase progress tracker
├── projectStructur.md              # ← this file
├── README.md
├── RUNNING.md
├── CONTRIBUTING.md
└── CODE_OF_CONDUCT.md
```

---

## Design System (gtk.css tokens)

| Token | Value | Usage |
|-------|-------|-------|
| `--bg-0` | `#1a1d23` | Window background |
| `--bg-1` | `#20232b` | Sidebar |
| `--bg-2` | `#262a35` | Cards |
| `--bg-3` | `#2e3340` | Elevated / header strips |
| `--text-1` | `#d0d4e0` | Primary text |
| `--text-2` | `#8b92a9` | Secondary/dim |
| `--text-3` | `#55607e` | Very dim / section labels |
| `--accent` | `#5cb8b2` | Nordic teal (links, selected, banner) |
| `--green` | `#22c55e` | Running / healthy |
| `--red` | `#ef4444` | Stopped / error |
| `--amber` | `#f59e0b` | Warning / starting |

---

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 0 | Project setup | ✅ Complete |
| 1 | Core UI shell | ✅ Complete |
| 2 | Dashboard & system widgets | ✅ Complete |
| 3 | GitHub widgets | ✅ Complete |
| 4 | Machine config & setup | ✅ Complete |
| 5 | Utilities & tools | ✅ Complete |
| 6 | Polish sprint | ✅ Complete |
| 7 | Workstation hub | ✅ Complete |
| 7.5 | Stability & hardening | ✅ Complete |
| 8 | Guardian / Maintenance | ✅ Complete |
| 9 | Nordic redesign + UX consolidation | ✅ **Current** — 4-section nav, no duplication |
| 10 | Extensions system | 🔲 Not started |
| 11 | Polish & first release | 🔲 Not started |

---

## Key Architectural Rules

1. **No duplicate content** — each feature lives in exactly one place
2. **Lazy page loading** — `BasePage.ensure_built()` called on first navigation
3. **Background threads** — all system calls use `threading.Thread(daemon=True)` + `GLib.idle_add` for UI updates
4. **Nordic CSS** — all styles in `src/ui/style/gtk.css`, no inline styles
5. **4 nav sections** — Dashboard / Tools / Maintenance / Settings (immutable for Phase 9)