# HypeDevHome - Phased Development Plan

> **⚠️ Important Project Strategy Note – Cross-Distribution Compatibility**
> 
> **This project is designed and built from the very beginning to the very end (from day one of development until the final release) based entirely on Flatpak + Docker.**
> 
> **Main Goal:** The application must run **natively and cleanly on all Linux distributions** without any modifications or dependency on a specific distro's native packages.
> 
> **This decision is non-negotiable** and must be respected in every folder, script, configuration, and technical decision moving forward.

---

## Overview

This document outlines the complete development plan for HypeDevHome, a 100% open-source Linux version of Microsoft Dev Home, built from scratch using **Python + GTK4 + Libadwaita**.

**Total Phases:** 12 (numbered 0–11)  
**Branch Strategy:** Each phase is developed in its own branch, then merged into `main` upon completion and review.

### Implementation progress (at a glance)

| # | Phase | Status |
|---|-------|--------|
| 0 | Project setup | ✅ Complete |
| 1 | Core UI shell | ✅ Complete |
| 2 | Dashboard & system widgets | ✅ Complete |
| 3 | GitHub widgets | ✅ Complete |
| 4 | Machine config & setup | ✅ Complete |
| 5 | Utilities & tools | ✅ Complete (MVP; stretch items optional) |
| 6 | Polish sprint | ✅ Complete |
| 7 | Workstation hub | ✅ Complete *(Apps / Home / Servers / Services / AI / Config / Install / Remove; cheatsheets contextual)* |
| 7.5 | Stability & Hardening | ✅ Complete |
| 8 | Maintenance & monitoring (Guardian) | ✅ Criteria met |
| 9 | Power-User System Builder | 🔲 In progress *(Welcome/System/Tools rail, profiles, power mode, contextual learn shipped; matrix install + live counters + backup TBD)* |
| 10 | Extensions system | 🔲 Not started |
| 11 | Polish & first release | 🔲 Not started |
| 12 | Cloud & edge | 🔲 Not started |

*Detailed acceptance checkboxes below match this summary. If a completed phase later gains new stretch goals, add sub-bullets rather than unchecking ship criteria.*

---

## Phase 0: `phase-0-project-setup`

**Branch:** `phase-0-project-setup`  
**Status:** ✅ COMPLETE  
**Completion report:** PHASE_0_COMPLETION_REPORT.md  
**Goal:** Establish the foundational project structure, development environment, and CI/CD pipeline.

### Deliverables

#### 1. Project Structure
- Create complete directory structure following the `projectStructur.md` specification
- Initialize Python package structure with proper `__init__.py` files
- Set up module organization: `src/`, `data/`, `ui/`, `extensions/`, `tests/`, `assets/`

#### 2. Development Environment (Docker)
- Create `Dockerfile` for development environment with all necessary dependencies:
  - Python 3.11+
  - GTK4 development libraries
  - Libadwaita
  - GObject introspection
  - Testing tools (pytest, coverage)
  - Linting tools (ruff, flake8, mypy)
- Create `docker-compose.yml` for dev environment with optional services
- Write `dev-setup.sh` script for one-command environment setup

#### 3. Flatpak Manifest
- Create initial Flatpak manifest (`com.github.hypedevhome.yml`)
- Define Flatpak permissions and sandbox requirements:
  - D-Bus access for system monitoring
  - Filesystem access for `~/Dev` and config directories
  - Network access for GitHub integration
  - SSH agent socket access
- Test basic Flatpak build and run

#### 4. CI/CD Pipeline
- GitHub Actions workflow for:
  - Linting (ruff, flake8)
  - Type checking (mypy)
  - Unit tests (pytest)
  - Flatpak build validation
  - Docker build validation
- Pre-commit hooks configuration

#### 5. Documentation
- Create comprehensive `README.md` with:
  - Project overview and strategic note
  - Quick start instructions
  - Development setup guide
  - Contributing guidelines
- Create `CONTRIBUTING.md`
- Create `CODE_OF_CONDUCT.md`
- Create initial `CHANGELOG.md`

#### 6. Basic Application Skeleton
- Minimal GTK4 application that launches successfully
- Main application window with Libadwaita styling
- Basic command-line interface
- Configuration management (`~/.config/dev-home/`)
- Logging setup

### Acceptance Criteria
- [x] Docker environment builds and runs successfully
- [x] Flatpak manifest builds without errors
- [x] CI/CD pipeline passes on all PRs
- [x] Application launches with empty window
- [x] All documentation is complete and accurate (*core docs; expand over time*)

---

## Phase 1: `phase-1-core-ui-shell`

**Branch:** `phase-1-core-ui-shell`  
**Status:** ✅ COMPLETE  
**Completion report:** PHASE_1_COMPLETION_REPORT.md  
**Goal:** Build the main application shell with navigation and core UI infrastructure.

### Deliverables

#### 1. Main Application Window
- Libadwaita `ApplicationWindow` with proper title and icon
- Responsive window sizing and state persistence (save/restore position and size)
- Wayland compatibility ensured
- Proper window close handling and cleanup

#### 2. Navigation System
- Sidebar navigation with main sections:
  - Dashboard
  - Machine Setup
  - Extensions
  - Utilities
- Hamburger menu for settings and about dialog
- Keyboard shortcuts support
- Smooth page transitions

#### 3. Settings & Configuration
- Settings panel accessible from header bar menu
- Configuration file management (JSON/YAML in `~/.config/dev-home/`)
- Basic settings:
  - Theme preference (light/dark/system)
  - Auto-start on login (Flatpak portal)
  - Refresh interval configuration
- About dialog with version, license, and contributors

#### 4. Global State Management
- Application state manager (singleton pattern)
- Configuration loader/saver
- Event bus for inter-component communication
- Error handling and user notification system (toast messages, dialogs)

#### 5. UI Components Library
- Reusable UI components:
  - Custom buttons with icons
  - Status indicators
  - Loading spinners
  - Empty state placeholders
  - Error banners
- Consistent spacing and styling following Libadwaita HIG

#### 6. Accessibility & Internationalization
- Basic accessibility labels and roles
- RTL support infrastructure
- Translation framework setup (gettext)
- Arabic and English locale files

### Acceptance Criteria
- [x] Application launches with full navigation
- [x] All pages switch correctly via sidebar
- [x] Settings save and persist across restarts
- [x] Theme switching works correctly
- [x] Keyboard shortcuts function properly
- [x] No visual glitches or layout issues (*report edge cases as bugs*)

---

## Phase 2: `phase-2-dashboard-system-widgets`

**Branch:** `phase-2-dashboard-system-widgets`  
**Status:** ✅ COMPLETE  
**Completion report:** walkthrough_phase_2.md  
**Goal:** Implement the customizable dashboard with all system monitoring widgets.


### Deliverables

#### 1. Dashboard Framework
- Dashboard page with grid layout
- Widget management system:
  - Add widgets from widget gallery
  - Remove widgets
  - Drag-and-drop repositioning
  - Resize widgets (1x1, 2x1, 2x2, etc.)
- Widget configuration dialogs
- Dashboard layout save/restore

#### 2. Widget Gallery
- Widget picker dialog with categories:
  - System
  - GitHub
  - Community (future)
- Search and filter widgets
- Preview of each widget before adding

#### 3. CPU Widget
- Real-time CPU usage percentage (overall and per-core)
- Current frequency display
- Load average (1, 5, 15 min)
- Temperature monitoring (via `lm-sensors` or `/sys/class/thermal/`)
- Live updating chart (using Gtk.DrawingArea or third-party chart library)
- Configurable refresh interval
- Color-coded warnings for high usage (>80%, >90%)

#### 4. GPU Widget
- GPU utilization percentage
- VRAM usage (used/total)
- Temperature monitoring
- Fan speed display
- Auto-detection for GPU vendors:
  - NVIDIA (via `nvidia-smi`)
  - AMD (via `radeontop` or sysfs)
  - Intel (via `intel_gpu_top` or sysfs)
- Fallback behavior when GPU info unavailable
- Multi-GPU support (show primary or allow selection)

#### 5. Memory Widget
- RAM usage display (used/available/total)
- Swap usage
- Live memory graph
- Percentage indicators
- Warnings when nearing limits (>85%, >95%)
- Color-coded usage bars

#### 6. Network Widget
- Real-time download/upload speeds
- Public IP address display (via external API)
- Local IP address (via network interfaces)
- Connection status (connected/disconnected)
- Live speed graph
- Network interface selector
- Historical data (peak speeds, total transferred)

#### 7. SSH Keychain Widget
- List of loaded SSH keys in ssh-agent
- Key status (active/inactive)
- Fingerprint display (truncated)
- Buttons:
  - Add new key (file picker)
  - Reload ssh-agent
  - Remove key from agent
- Auto-detect ssh-agent availability
- Error handling for agent communication

#### 8. System Monitoring Backend
- Background worker threads for data collection
- Efficient polling intervals (configurable, default 2s)
- Thread-safe data sharing with UI
- Graceful degradation when system info unavailable
- Cross-platform compatibility (handle different Linux subsystems)
- Minimal CPU/memory overhead

### Acceptance Criteria
- [x] All 5 system widgets display correct data (*where hardware exposes data; graceful fallbacks otherwise*)
- [x] Widgets update in real-time without UI freezing
- [x] Drag-and-drop works smoothly
- [x] Layout persists across app restarts
- [x] SSH widget interacts correctly with ssh-agent (*when agent present*)
- [x] CPU usage of monitoring stays below 5% (*typical idle load; spikes possible under stress*)

---

## Phase 3: `phase-3-dashboard-github-widgets`

**Branch:** `phase-3-dashboard-github-widgets`  
**Status:** ✅ COMPLETE  
**Completion report:** PHASE_3_COMPLETION_SUMMARY.md  
**Goal:** Implement GitHub integration with authentication and dashboard widgets.

### Deliverables

#### 1. GitHub Authentication
- GitHub Personal Access Token (PAT) setup flow
- Secure token storage (use libsecret/Secret Service via Flatpak portal)
- Token validation and permission checking
- OAuth flow alternative (future consideration)
- Token management UI (view, edit, remove)
- Clear error messages for authentication failures

#### 2. GitHub API Client
- Asynchronous GitHub API client
- Rate limit tracking and handling
- Pagination support
- Caching layer to reduce API calls
- Retry logic with exponential backoff
- Error handling (network, auth, rate limits)

#### 3. Issues Widget
- Display user's open issues
- Show issue title, repository, labels
- Time since creation/last update
- Click to open in browser
- Configurable filter (all repos, specific repos)
- Auto-refresh every 30 seconds
- Loading states and error handling

#### 4. Pull Requests Widget
- Display user's open PRs
- Show PR title, repository, status (draft, ready, blocked)
- Review status indicators
- Merge status (mergeable, conflicts)
- Click to open in browser
- Auto-refresh every 30 seconds

#### 5. Review Requested Widget
- Display PRs awaiting user's review
- Repository and PR details
- Time since review requested
- Priority indicators (overdue, recent)
- Quick actions (open in browser, mark as reviewed)
- Auto-refresh every 30 seconds

#### 6. Mentioned Me Widget
- Display issues/PRs where user was mentioned
- Show context (title, author, mention text snippet)
- Repository details
- Click to view full context
- Auto-refresh every 30 seconds

#### 7. Assigned to Me Widget
- Display issues assigned to user
- Show issue details and status
- Repository information
- Quick filters (by repo, by label)
- Auto-refresh every 30 seconds

#### 8. GitHub Settings Panel
- Configure refresh interval
- Select which widgets to display
- Filter by repositories
- Notification preferences
- Cache management (clear cache)
- API usage statistics

### Acceptance Criteria
- [x] GitHub authentication works correctly
- [x] Token stored securely and accessible only to app
- [x] All 5 GitHub widgets display correct data (*when authenticated and API available*)
- [x] Auto-refresh works without performance issues
- [x] Rate limiting handled gracefully
- [x] Widgets handle offline/no network scenarios
- [x] Click actions open correct URLs in browser

---

## Phase 4: `phase-4-machine-config-setup`

**Branch:** `phase-4-machine-config-setup`  
**Status:** ✅ COMPLETE  
**Completion report:** PHASE_4_COMPLETION_SUMMARY.md  
**Goal:** Build the Machine Configuration section for one-click development environment setup.

### Deliverables

#### 1. Machine Config Page Structure
- Tabbed or accordion layout:
  - Install Applications
  - Clone Repositories
  - Create Dev Folder
  - Apply Developer Settings
  - Environments Support
- Progress indicators for long-running operations
- Clear success/error feedback

#### 2. Application Installer
- **Package Catalog:**
  - Curated list of popular development tools:
    - neovim, git, docker/podman, vscode (Flatpak), nodejs, rust, go, python, lazygit, btop, etc.
  - Package metadata (name, description, icon, category)
  - Search and filter functionality
  - Category grouping (Editors, Languages, Tools, Terminal, etc.)

- **Installation Methods:**
  - Primary: Flatpak (Flathub)
  - Fallback: Distro-specific package managers
  - Smart detection of host distribution
  - Generate appropriate commands (`dnf`, `apt`, `pacman`, `zypper`, etc.)

- **UI Features:**
  - Checkbox selection for packages
  - "Install All Dev Tools" quick-select button
  - Installation progress bars
  - Batch installation
  - Show already-installed status
  - Installation history log

- **Distro Detection:**
  - Detect distribution (`/etc/os-release`)
  - Detect available package managers
  - Show compatibility notes
  - Fallback gracefully if Flatpak unavailable

#### 3. GitHub Repository Cloner
- URL input field with validation
- Authentication method selector:
  - HTTPS (with token/credential helper)
  - SSH (with key selection)
- Clone destination: default `~/Dev/`
- Progress display during clone
- Post-clone options:
  - Open in terminal
  - Open in VS Code
  - Open in Neovim
  - Open in default file manager
- Clone history and quick access list
- Handle existing repos (pull instead of clone)

#### 4. Dev Folder Creator
- Create `~/Dev` directory
- Performance optimizations:
  - Mount options suggestions (noatime, discard)
  - Btrfs subvolume creation (if filesystem supports it)
  - Compression settings
  - Snapshot configuration
- Clear explanations and warnings
- One-click creation with sudo/pkexec handling
- Verification after creation
- Rollback on failure

#### 5. Developer Settings Apply
- One-click configuration:
  - **File Manager Settings:**
    - Show hidden files
    - Show file extensions
    - Sort order preferences
  - **Git Global Configuration:**
    - user.name, user.email
    - Default editor (neovim, vscode, etc.)
    - Rebase behavior
    - Autocrlf settings
    - Credential helper setup
  - **Shell Enhancements:**
    - Useful aliases (ls, grep, git shortcuts)
    - Modern tools integration (eza, bat, delta, fzf, etc.)
    - Prompt customization (starship, oh-my-zsh detection)
  - **Environment Variables:**
    - EDITOR, VISUAL
    - PATH additions
    - Language/toolchain paths
  - **SSH Agent Auto-start:**
    - Desktop entry or shell rc modification
    - Systemd user service option

- Safe application of settings:
  - Backup existing configs before changes
  - Preview changes before applying
  - Rollback capability
  - Per-setting toggle (apply only what user wants)

#### 6. Environments Support
- **Dev Containers:**
  - Detection of Podman or Docker availability
  - Quick launch of devcontainer from repo
  - Basic devcontainer.json template generator
  - Integration with VS Code Dev Containers extension

- **Distrobox / Toolbx:**
  - Installation guidance
  - Create containers from templates
  - Quick launch commands
  - Integration with host filesystem

- **Cloud Environments (Future):**
  - GitHub Codespaces integration placeholder
  - Gitpod integration placeholder
  - UI prepared for future implementation

### Acceptance Criteria
- [x] Package catalog displays correctly
- [x] Installation works for multiple packages
- [x] Distro detection accurate on major distros
- [x] Repository clone completes successfully
- [x] Dev folder created with correct permissions
- [x] Developer settings apply safely with backups
- [x] All operations show clear progress and feedback

---

## Phase 5: `phase-5-utilities-tools`  
**Branch:** `phase-5-utilities-tools`  
**Status:** ✅ COMPLETE (MVP — see report for stretch items)  
**Completion report:** [walkthrough_phase_5.md](walkthrough_phase_5.md)  
**Goal:** Implement utility tools and additional features for developer productivity.


### Deliverables

#### 1. Hosts File Editor
- Safe GUI editor for `/etc/hosts`
- Features:
  - Load and parse current hosts file
  - Syntax highlighting for hosts entries
  - Add/edit/delete entries
  - Comment/uncomment lines
  - Validate entry format (IP + hostname)
  - Duplicate detection
- **Backup & Restore:**
  - Automatic backup before each edit
  - Backup history with timestamps
  - One-click restore from backup
  - Export current hosts file
  - Import hosts file (with validation)
- **Safety:**
  - Polkit authentication for writing to `/etc/hosts`
  - Confirmation dialogs for destructive actions
  - Lock file handling to prevent concurrent edits
  - Error recovery on write failures

#### 2. Environment Variables Editor
- View and edit user and system environment variables
- **Features:**
  - Load from `~/.profile`, `~/.bashrc`, `~/.zshrc`, `/etc/environment`
  - Add new variables (name, value, scope)
  - Edit existing variables
  - Delete variables
  - Toggle active/inactive (comment out)
  - Variable type hints (path, boolean, string, number)
- **Validation:**
  - Check for duplicate names
  - Validate PATH modifications
  - Warn about common mistakes
- **Apply Changes:**
  - Write to correct file based on scope
  - Reload shell environment
  - Notify running applications (where possible)
  - Backup before modifications

#### 3. Desktop Config Preview
- Quick view and basic editing for common desktop environment configs
- **Supported Environments:**
  - GNOME (dconf/gsettings)
  - KDE (kconfig)
  - Hyprland (config file)
  - Sway (config file)
  - Generic XDG settings
- **Features:**
  - Auto-detect current desktop environment
  - Show relevant settings only
  - Common configurations:
    - Keyboard shortcuts
    - Display scaling
    - Default applications
    - Power management
    - Workspace behavior
- **Safety:**
  - Read-only by default
  - Edit mode requires explicit toggle
  - Backup before changes
  - Preview changes before applying
  - Non-intrusive (never break user's setup)

#### 4. Environments Manager
- Create, save, and launch complete development environments
- **Features:**
  - Define environments with:
    - Name and description
    - Package list (auto-install on launch)
    - Environment variables
    - Mounted volumes
    - Startup commands
  - Launch environments via:
    - Podman/Docker containers
    - Distrobox instances
    - Local shell environment
  - Save environment templates
  - Quick launch from dashboard
  - Import/export environment configs
- **UI:**
  - Environment list with details
  - Create/edit environment dialog
  - Launch options panel
  - Status indicators (running/stopped)
  - Resource usage display for active environments

#### 5. Additional Utilities
- **Quick Settings Toggles:**
  - Dark mode system-wide toggle
  - SSH agent start/stop
  - Docker/Podman service toggle
  - Network proxy quick toggle
- **System Information Viewer:**
  - OS details (distro, version, kernel)
  - Hardware summary (CPU, RAM, GPU, disks)
  - Disk usage visualization
  - Network interfaces info
- **Quick Actions:**
  - Clear cache (app cache, thumbnail cache, package manager cache)
  - Clean old logs
  - Remove orphaned packages
  - Vacuum databases

### Acceptance Criteria
- [x] Hosts editor reads and writes correctly with polkit (host testing; Flatpak may vary)
- [x] Backups work as expected and restore is functional (timestamped + UI restore)
- [x] Environment variables: loads real profile files; writes managed snippet + `.bak`
- [x] Desktop config: GNOME-accurate when schemas present; read-only gate by default
- [x] Environments: detection in Utilities; full launch/templates via Machine Setup
- [x] Permission errors: logged; prefer toasts on failure where integrated


---

## Phase 6: `phase-6-polish-sprint` ✅ COMPLETE

**Branch:** `phase-6-polish-sprint`
**Status:** ✅ COMPLETE (Polish Sprint)
**Goal:** Harden the application through diagnostic profiling, robustness improvements, and multi-distribution validation.

### Deliverables

#### 1. Performance & Memory Optimization
- **Memory Leaks**: Run `investigate_memory_leak.py`.
    - Refactor `WidgetRegistry` into a true singleton.
    - Implement proper garbage collection/cleanup for destroyed widgets.
- **Performance**: Run `profile_github_performance.py`.
    - Implement lazy loading for the GitHub API client.
    - Optimize widget refresh cycles and data caching.
- **How to run (informational, not gated in CI):** From the repository root, with GTK/Libadwaita available and a display (or `xvfb-run -a`), run `python3 investigate_memory_leak.py` and `python3 profile_github_performance.py` (both add `src` to `PYTHONPATH` internally). On GitHub: **Actions** → workflow **Profile scripts (manual)** → **Run workflow**, and choose *both*, *memory*, or *performance*. Logs are for human review; numbers are not enforced as merge criteria.

#### 2. Reliability & Error Handling
- **Toast System**: Integrate `Adw.ToastOverlay` in the main window.
- **Robustness**: Wrap all `UtilityManagers` in `try/except` guards with user-friendly toast notifications.
- **Graceful Fallbacks**: Ensure `HostExecutor` handles missing privileged tools on non-Fedora distros.

#### 3. Multi-Distribution Validation
- **Containerized Labs**: Setup `Dockerfile.ubuntu` and `Dockerfile.arch`.
- **Validation Suite**: Verify full dashboard and utility functionality across Fedora, Ubuntu, and Arch.
- **CI split**: Default **Test** workflow runs the full suite on the **self-hosted** runner (one job, no per-PR Docker builds). **Cross-distro (Docker)** is **manual** (Actions → run workflow) for Ubuntu/Arch image builds + pytest when you need container coverage.

### Acceptance Criteria
- [x] Memory growth remains below 1KB after 100 widget cycles (Registry optimized).
- [x] GitHub component initialization time is under 100ms (Lazy init implemented).
- [x] Full unit test suite on default CI (self-hosted); optional Ubuntu/Arch checks via **Cross-distro (Docker)** workflow.

---

## Phase 7: `phase-7-workstation-hub` ✅ COMPLETE
**Branch:** `phase-7-workstation-hub`  
**Status:** ✅ COMPLETE
**Goal:** Workstation hub: Apps, Home, Servers, Services, AI, Config, Install, Remove — with cheatsheets and references surfaced contextually (Welcome, Servers **Docker Docs**, Install, Config **CLI**; standalone Learn hub removed later in Phase 9).

### Deliverables
- [x] **Hub Normalization**: Renamed "Setup" to "Config" (Personalization) and created "Servers" (Docker/Runtime).
- [x] **Unified Navigation**: Implemented the horizontal `Gtk.StackSwitcher` and Sidebar Icon-Rail patterns across all hubs.
- [x] **Apps**: Searchable catalog with automated configuration logic.
- [x] **Learn (original)**: Environment-aware cheatsheets (Bash, Neovim, FHS, …) — **superseded by Phase 9 contextual placement** (no separate Learn rail).
- [x] **Servers**: Centralized Docker management + Runtime diagnostics (ports, systemd, logs).
- [x] **Services**: Systemd daemon control (Tailscale, NordVPN, etc.).
- [x] **Config**: Ongoing personalization center (Git Identity, SSH Keys, Dotfiles).
- [x] **Install/Remove**: Data-driven package management via `workstation_catalog.json`.

---

## Phase 7.5: `phase-7-5-stability-hardening` 🔲 IN PROGRESS
**Branch:** `phase-7-5-stability-hardening`
**Status:** 🔲 IN PROGRESS
**Goal:** Address the 20 critical findings identified in the Phase 7 audit (Security, Reliability, UX, and Data Quality).

### 🛡️ 1. Security & Hardening
- [ ] **Command Injection**: Implement `shlex.quote` or `shutil.which` in `learn_factory.py` to prevent shell exploits.
- [ ] **Least Privilege**: Review Flatpak permissions; scope down `org.freedesktop.systemd1` access where possible.
- [ ] **Secure Data Extraction**: Implement robust error handling (FileNotFound, JSONDecodeError) in all `_load_json` helpers.

### 🧪 2. Reliability & Resource Management
- [ ] **Timer Cleanup (Memory Leaks)**: Implement `do_unrealize` and `destroy` handlers to stop GLib timeouts in `service_manager.py` and `apps_panel.py`.
- [ ] **Async Migration**: Move synchronous host checks in `learn_factory.py` to background threads to prevent UI freezing.
- [ ] **Debounce Safety**: Ensure search debounce sources are removed on widget destruction in `apps_panel.py`.

### 🎨 3. UI/UX & Transparency
- [ ] **Post-Install Feedback**: Update `docker_manager.py` to report `enable/start` service failures even if the installation succeeded.
- [ ] **Silent Failure Exposure**: Implement toast notifications for missing `start_cmd` / `stop_cmd` in the Services hub.
- [ ] **GTK Structural Robustness**: Refactor brittle `get_first_child()` traversal in `learn_factory.py` to use direct styling or custom widgets.
- [ ] **Rich Logs**: Wiring up the unused `Gtk.TextTag` system in `InstallDialog` for color-coded (Error/Warn) installation output.

### 🍱 4. Data Quality & Localization
- [ ] **Catalog Integrity**: Fix duplicate YAML keys (`dns`) and incorrect nesting (`args` under `build`) in `docker.json`.
- [ ] **Deprecated Cleaning**: Remove `version: '2'` from Docker Compose examples in the catalog.
- [ ] **Localization Sweep**: Populate German (`de`) and Arabic (`ar`) `nvim.json` and `bash.json` groups (currently empty).
- [ ] **Markup Safety**: Sanitize all catalog titles and subtitles to handle ampersands (`&`) without breaking Pango parsing.

---

## Phase 8: `phase-8-maintenance-monitoring` ✅ (acceptance criteria met)
logged.

---

## Phase 8: `phase-8-maintenance-monitoring` ✅ (acceptance criteria met)

**Branch:** `phase-8-maintenance-monitoring`  
**Status:** ✅ **Accepted as shipped** — Guardian snapshot pipeline, **local** pluggable storage, encryption + session key cache, retention engine, Pulse UI, container/stack health signals, HypeSync status, and snapshot management dialog are implemented under `src/core/maintenance/`, `src/ui/widgets/pulse_dashboard.py`, `src/ui/dialogs/snapshots.py`, etc., and exercised by automated tests.

**What “complete” does *not* mean:** The bullet list below is part **vision / architecture**. Not every line is a separate production guarantee (e.g. **remote object storage = Phase 11**; the **interface** is pluggable, **local** provider is what this phase ships). Older text mentioning “242+” tests was a snapshot in time—the **current** gate is `pytest tests/` passing on `main` (total test count grows with the repo).

*(Historically some work landed under older branch names; align new work with this phase number.)*

#### 1. Advanced Snapshot Manager (Guardian)
- **Snapshot Engine:**
  - Pluggable storage providers (Local storage implemented)
  - Async bytes-based snapshot I/O
  - Detailed metadata tracking per snapshot
- **Security & Integrity:**
  - AES-256 encryption with session-based key caching (PBKDF2)
  - SHA-256 integrity checksums per snapshot
  - Session-based key cache (memory-only, wiped on close)
- **Retention & Health:**
  - Automated retention policies (Daily/Weekly)
  - Pre-restore and post-restore health check runners

#### 2. Unified Monitoring System
- **System Monitoring:**
  - Real-time CPU, RAM, and Disk I/O tracking
  - Event-driven metrics broadcasting
- **Stack Monitoring:**
  - Container lifecycle tracking (Distrobox/Docker)
  - Real-time container resource usage (CPU/Mem/IO)
- **Status Integration:**
  - HypeSync drift and synchronization status tracking
  - Unified EventBus namespacing for maintenance events

#### 3. Dashboard Integration
- **Pulse Widgets:**
  - Throughput-focused I/O metrics (MB/s)
  - Cumulative totals in hover tooltips
- **Maintenance UI:**
  - Snapshots management dialog with encryption support
  - Health status indicators across the dashboard

### Acceptance Criteria
- [x] Snapshot Manager integrates with Guardian persistence
- [x] Encryption keys are cached in memory correctly
- [x] Full `tests/` suite passes on `main` (includes maintenance/snapshot/pulse/monitoring tests; **not** “N tests that are only maintenance-only”)
- [x] Monitoring background tasks are lifecycle-safe (RUF006)
- [x] Mypy and Ruff verify a clean production signal *(when run in CI / locally per project scripts)*

---

## Phase 9: `phase-9-outcome-driven-system-builder`

**Branch:** `phase-9-outcome-driven-system-builder`  
**Status:** 🔲 IN PROGRESS  
**Goal:** Transform the application from a "collection of tools" to an "outcome-driven system builder" that shows users what they can build, not just what tools they can use.

**Product target (power-user):** One place to **install the whole dev stack** (languages, tools, DBs, AI, terminal), **see everything running** on one screen (packages, services, containers, health), then **backup/restore** that state. Not “one small project wizard only,” but **system-wide setup**.

**Shipped (iteration 1):** Outcome cards from `outcome_profiles.json`, `PowerInstaller.run_profile` with progress + toasts, lightweight CPU/mem/disk sampling (throttled). `outcome_wizards.py` re-exports. `app.enqueue_task` waits for the background asyncio loop and **closes** coroutines if scheduling fails (fixes “coroutine was never awaited” warnings). **Front door:** **`welcome`** (`WelcomeDashboardPage`), **`system`** (`SystemMonitorPage` — overview + collapsible FHS tree), **`workstation`** (**Tools**); **Widgets** = `dashboard`; shortcuts **`Ctrl+1`–`Ctrl+8`** in `src/ui/window.py`; Machine Setup completion returns to **Welcome**. **Contextual learn:** standalone **Learn** tab removed; Docker docs under **Servers → Docker Docs**; Bash + session on **Welcome**; Neovim + Backend JVM tips under **Install**; desktop CLI reference under **Config → CLI** (`config:cli`). **Profiles / power mode:** `PowerInstaller.run_all_profiles` (sequential all profiles + mapped progress), Docker `run` argv supports `env`/`volumes`; extra profiles **Build Essentials** + **Git & Collaboration**; dashboard **help** icon + **Install all profiles** with `Adw.MessageDialog` confirmation.



**Shipped (iteration 2 — Nordic UX redesign):** Navigation consolidated to **4 sections** (Dashboard, Tools, Maintenance, Settings). Monitor page removed from sidebar — live data in **Tools → Servers → Overview** only. Dashboard rebuilt: health banner + metric cards (CPU/RAM/Disk/Uptime) + widget grid. CSS fully rewritten: Nordic dark palette (`#1a1d23` bg, `#5cb8b2` teal). Old phase .md files cleaned. `projectStructur.md` updated.
**Not done yet:** **Install everything** checkbox matrix (granular pick) vs current **sequential all profiles**; **first-run welcome** (Standard vs Custom); **live counters** (packages/services); **per-control hover help**; **backup/sync** slice; performance passes on full Workstation + Pulse + GitHub timers.

### 🎯 Core Insight: From Tools to Outcomes
**Current Problem:** Users see scattered tools (Install tab, Services tab, AI tab, etc.) and get overwhelmed. They think: "Which tab do I click? Install? Services? AI? Wait, where's Docker again?"

**New Vision:** Users see outcomes ("Set up a web app", "Start data science project", "See what's running"). They think: "I want to build a web app" → the app shows them exactly what they need.

**The Analogy:**
- **Current:** Amazing kitchen with every appliance (blender, oven, mixer, grill)
- **Problem:** When someone says "I want pizza," they have to figure out which appliances to use
- **Solution:** A "Make Pizza" button that uses the right appliances in the right order

### Deliverables

#### 1. The "Welcome Dashboard" - Your Dev Home Front Door
**Opening Screen That Says: "What do you want to do today?"**

```
┌─────────────────────────────────────────────────┐
│            WELCOME TO YOUR DEV HOME             │
│  What do you want to do today?                  │
│                                                 │
│  🚀 [ SET UP A NEW PROJECT ]                    │
│     • Python Data Science                       │
│     • Web Development                           │
│     • AI/ML Local                               │
│     • Custom...                                 │
│                                                 │
│  📊 [ SEE WHAT'S RUNNING ]                      │
│     • 8 services running                        │
│     • 3 Docker containers                       │
│     • 42 packages installed                     │
│                                                 │
│  🛠️ [ MANAGE TOOLS ]                            │
│     • Add a database                            │
│     • Install AI models                         │
│     • Configure services                        │
└─────────────────────────────────────────────────┘
```

**Features:**
- **Unified View:** Shows everything installed and running at a glance
- **Outcome-First Buttons:** "Set up a new project" not "Install packages"
- **Contextual Help:** Hover over anything → see relevant commands and tips
- **Quick Actions:** One-click access to common tasks

#### 2. Outcome Wizards - "Make Pizza" Buttons
**Magic Buttons That Say: "Set up Python Data Science"**

**Common Setup Wizards:**
- **Python Data Science:** Python + Jupyter + pandas + Docker + Postgres
- **Web Development:** Node.js + Docker + PostgreSQL + Redis + VS Code
- **AI/ML Local:** Ollama + Open WebUI + CUDA + Jupyter + Python
- **Full Stack:** All 42 packages (power-user mode)

**Wizard Flow:**
1. **Choose Outcome:** "I want to build a web app"
2. **See What's Needed:** Shows what will be installed (Python, Docker, Postgres, etc.)
3. **Watch Progress:** Real-time installation progress for each component
4. **Get Started:** "Your web app environment is ready! Open VS Code →"

**Technical Implementation:**
```python
# outcome_wizards.py
class OutcomeWizard:
    def setup_python_data_science(self):
        steps = [
            ("Install Python 3.11 + pip", self.package_installer.install_python),
            ("Install Jupyter + pandas", self.package_installer.install_jupyter),
            ("Install Docker", self.service_manager.install_docker),
            ("Start Postgres container", self.docker_manager.start_postgres),
            ("Configure VS Code", self.configure_vscode),
        ]
        return self.execute_steps(steps)
```

#### 3. The "Install Everything" Power Mode (For Power Users)
**For users who just want EVERYTHING:**

- **42+ Essential Tools:** One button installs Python, Rust, Docker, VS Code, Neovim, etc.
- **Parallel Installation:** Install multiple packages at once where safe
- **Progress Tracking:** Real-time progress bars for each category
- **Smart Recovery:** Continue from where it failed

#### 4. Contextual Help Everywhere
**NOT in a separate "Learn" tab - RIGHT THERE when you need it:**

- **Hover over "Postgres" → shows:**
  - `psql` commands
  - Backup/restore instructions
  - Connection strings
  - Common troubleshooting

- **Click "Docker" → shows:**
  - Running containers
  - Resource usage
  - Quick commands (start/stop/restart)
  - Log viewer

#### 5. The "System Dashboard" - See Everything At Once
**Unified view of your entire development system:**

- **"Everything Installed" counter** (42/42 packages)
- **"Running Services" panel** with status indicators
- **"Docker Containers" live view** with resource usage
- **"AI Models Loaded"** in Ollama
- **"System Health" metrics** (CPU, RAM, Disk, Network)

#### 6. Integration with Existing Codebase
**Reuse ALL Your Existing Components:**

- `package_installer.py` → Powers all installation wizards
- `service_manager.py` → Manages all running services  
- `docker_manager.py` → Handles container lifecycle
- `ai_manager.py` → Manages AI tools and models
- `workstation_catalog.json` → Extended with outcome-based packages

**New Orchestration Layer:**
- `outcome_wizards.py`: Outcome-driven setup flows
- `welcome_dashboard.py`: Unified front door to the app
- `context_help.py`: Inline contextual help system
- `system_orchestrator.py`: Coordinates across all subsystems

### Technical Implementation (3-Week Plan)

#### Week 1: The Welcome Dashboard
**Build the "front door" that shows everything at a glance:**

```python
# welcome_dashboard.py
class WelcomeDashboard:
    def show_welcome_screen(self):
        # Reuse ALL your existing code
        dashboard_data = {
            "packages": self.package_installer.get_all(),
            "services": self.service_manager.get_all(), 
            "containers": self.docker_manager.get_all(),
            "ai_tools": self.ai_manager.get_all(),
            "system_health": self.get_system_health(),
        }
        
        # Show in ONE beautiful grid
        return self.render_unified_view(dashboard_data)
    
    def get_quick_actions(self):
        return [
            ("🚀 Set up a new project", self.show_outcome_wizards),
            ("📊 See what's running", self.show_system_dashboard),
            ("🛠️ Manage tools", self.show_advanced_tools),
        ]
```

#### Week 2: Outcome Wizards
**Build the "Make Pizza" buttons that orchestrate everything:**

```python
# outcome_wizards.py
class OutcomeWizard:
    def setup_python_data_science(self):
        """Magic button: 'Set up Python Data Science'"""
        steps = [
            ("Install Python 3.11 + pip", self.package_installer.install_python),
            ("Install Jupyter + pandas", self.package_installer.install_jupyter),
            ("Install Docker", self.service_manager.install_docker),
            ("Start Postgres container", self.docker_manager.start_postgres),
            ("Configure VS Code", self.configure_vscode),
        ]
        
        # Show progress for each step
        for step_name, step_func in steps:
            self.show_progress(step_name)
            step_func()
        
        return "Your data science environment is ready! Open Jupyter →"
    
    def setup_web_development(self):
        """Magic button: 'Set up Web Development'"""
        steps = [
            ("Install Node.js + npm", self.package_installer.install_nodejs),
            ("Install Docker + Docker Compose", self.service_manager.install_docker),
            ("Start PostgreSQL container", self.docker_manager.start_postgres),
            ("Start Redis container", self.docker_manager.start_redis),
            ("Install VS Code", self.package_installer.install_vscode),
        ]
        return self.execute_steps(steps)
```

#### Week 3: Context Help & Polish
**Put help RIGHT THERE when you need it:**

```python
# context_help.py
class ContextHelp:
    def show_postgres_help(self):
        """Hover over 'Postgres' → shows relevant help"""
        return {
            "commands": [
                "psql -U postgres",
                "pg_dump mydb > backup.sql",
                "pg_restore -d mydb backup.sql",
            ],
            "connection": "postgresql://postgres:password@localhost:5432/mydb",
            "common_tasks": [
                "Create database: CREATE DATABASE mydb;",
                "List databases: \\l",
                "Backup: pg_dumpall > backup.sql",
            ]
        }
    
    def show_docker_help(self):
        """Click 'Docker' → shows running containers + commands"""
        containers = self.docker_manager.get_containers()
        return {
            "running": containers,
            "commands": [
                "docker ps",
                "docker logs <container>",
                "docker exec -it <container> bash",
            ],
            "quick_actions": [
                ("Start all", self.docker_manager.start_all),
                ("Stop all", self.docker_manager.stop_all),
                ("View logs", self.show_docker_logs),
            ]
        }
```

### User Experience Flow

#### First Launch (New User):
1. **Welcome Screen:** "Welcome to your Dev Home! What do you want to do today?"
2. **Outcome Choices:** "Set up a new project" → Choose: Python Data Science, Web Dev, AI/ML, etc.
3. **See What's Needed:** Shows exactly what will be installed (Python, Docker, Postgres, etc.)
4. **Watch Magic Happen:** Real-time progress as each component installs and configures
5. **Get Started:** "Your data science environment is ready! Open Jupyter →"

#### Daily Use (Developer):
1. **Open App → See Everything** running on your system
2. **Quick Actions:** One-click to start/stop services, view logs, open tools
3. **Context Help:** Hover over anything → see relevant commands and tips
4. **Add More:** "Need a database?" → Click → Choose PostgreSQL/Redis/MySQL

#### Power User Mode:
1. **"Install Everything"** → One button installs all 42+ tools
2. **Advanced Tools** → Click through to the full Workstation Hub (8 sections)
3. **System Backup** → One-click backup of entire environment

### Acceptance Criteria
- [ ] Welcome Dashboard shows unified view of everything installed/running
- [ ] Outcome wizards work (Python Data Science, Web Dev, AI/ML setups)
- [ ] Contextual help appears when hovering/clicking on components
- [ ] "Install Everything" installs 42+ packages successfully
- [ ] Performance: Dashboard loads in <2 seconds
- [ ] Memory: Unified view uses <50MB additional memory
- [ ] All existing functionality preserved and accessible
- [ ] Users can complete common setups in <5 minutes (vs hours manually)

---

## Phase 10: `phase-10-extensions-system`

**Branch:** `phase-10-extensions-system`  
**Status:** 🔲 NOT STARTED  
**Goal:** Build the extensible plugin system and ship the built-in GitHub integration as the first extension.

### Deliverables

#### 1. Extensions Framework
- **Extension Architecture:**
  - Plugin discovery system
  - Extension manifest format (YAML/JSON)
  - Sandboxed execution where possible
  - Lifecycle management (load, enable, disable, unload)

#### 2. Built-in GitHub Extension
- Refactor Phase 3 GitHub integration into proper extension format
- Serve as reference implementation for extension developers

### Acceptance Criteria
- [ ] Extension framework loads extensions correctly
- [ ] GitHub extension works when refactored as extension
- [ ] Extensions can be enabled/disabled without restart
- [ ] Extension errors don't crash the main app

---

## Phase 11: `phase-11-polish-release`

**Branch:** `phase-11-polish-release`  
**Status:** 🔲 NOT STARTED  
**Goal:** Polish the application, optimize performance, prepare for first public release.

### Deliverables

#### 1. Performance Optimization
- **Startup Time:**
  - Lazy loading of pages and widgets
  - Async initialization of background tasks
  - Profile and optimize import times
  - Target: <3s cold start on average hardware

- **Runtime Performance:**
  - Profile widget refresh impact on CPU/memory
  - Optimize chart rendering
  - Reduce unnecessary API calls
  - Implement smart caching strategy
  - Target: <10% CPU usage during normal operation

- **Memory Management:**
  - Detect and fix memory leaks
  - Proper cleanup of destroyed widgets
  - GC optimization
  - Target: <200MB RSS during normal usage

#### 2. UI/UX Polish
- **Visual Consistency:**
  - Review all pages for consistent spacing, colors, typography
  - Ensure Libadwaita HIG compliance
  - Dark theme testing
  - High contrast mode accessibility
  - Test on different screen sizes and resolutions

- **Micro-interactions:**
  - Smooth animations for page transitions
  - Loading states everywhere data is fetched
  - Empty states with helpful messages
  - Error states with actionable guidance
  - Success confirmations for user actions

- **Accessibility:**
  - Screen reader testing and fixes
  - Keyboard navigation complete coverage
  - Focus indicators visible and clear
  - Color contrast meets WCAG AA standards
  - ARIA labels on all interactive elements

#### 3. Testing & Quality Assurance
- **Unit Tests:**
  - Achieve >80% code coverage
  - Test all business logic
  - Test all API clients
  - Test configuration management
  - Test utility functions

- **Integration Tests:**
  - Test widget data flows
  - Test GitHub API integration
  - Test file operations (hosts, env vars)
  - Test package installation flows

- **Manual Testing:**
  - Test on multiple distributions (Ubuntu, Fedora, Arch at minimum)
  - Test on Wayland and X11
  - Test with different GTK themes
  - Test with screen readers
  - Test with keyboard-only navigation
  - Test with slow network connections
  - Test with low disk space
  - Test with many dashboard widgets
  - Stress test long-running sessions

#### 4. Flatpak Packaging for Release
- **Finalize Flatpak Manifest:**
  - All dependencies properly bundled
  - Permissions minimized (principle of least privilege)
  - Finish-args reviewed and documented
  - Portal usage verified for:
    - File access
    - Secret storage
    - Notifications
    - Inhibit (prevent sleep during operations)

- **Flathub Submission Preparation:**
  - Meet all Flathub submission guidelines
  - AppData/metainfo XML with:
    - Screenshots
    - Description
    - Categories
    - Release notes
    - Content rating
  - Icon in multiple sizes
  - Proper app ID and naming

- **Testing Flatpak Build:**
  - Build from clean state
  - Install on multiple distros
  - Verify all features work in sandboxed environment
  - Test portal prompts are user-friendly
  - Verify no host filesystem access beyond permissions

#### 5. Documentation
- **User Documentation:**
  - Complete user guide (in-app help or external docs)
  - Screenshots of all features
  - FAQ and troubleshooting guide
  - Getting started tutorial
  - Video walkthrough (optional)

- **Developer Documentation:**
  - Architecture overview
  - Code structure explanation
  - How to contribute guide
  - Extension development guide
  - API documentation (Sphinx or MkDocs)

- **Release Notes:**
  - Comprehensive first release notes
  - Known issues documented
  - Future roadmap shared publicly

#### 6. Release Preparation
- **Version Tagging:**
  - Semantic versioning (v0.1.0 for first release)
  - Git tag creation
  - Release artifacts generation

- **Distribution Channels:**
  - Flathub submission
  - GitHub release with Flatpak bundle
  - Docker image publication
  - README installation instructions for all methods

- **Community Setup:**
  - Discussion forum enabled (GitHub Discussions)
  - Issue templates created
  - Bug report template
  - Feature request template
  - Community channels announced (Matrix, Discord, etc.)

### Acceptance Criteria
- [ ] App starts in <3s on average hardware
- [ ] Memory usage stays below 200MB
- [ ] All tests pass with >80% coverage
- [ ] No critical or high severity bugs open
- [ ] Flatpak builds and runs on 3+ different distros
- [ ] All UI/UX issues resolved
- [ ] Accessibility audit passed
- [ ] Documentation complete and accurate
- [ ] Flathub submission ready or submitted

---

## Phase 12: `phase-12-cloud-edge`

**Branch:** `phase-12-cloud-edge`  
**Status:** 🔲 NOT STARTED  
**Goal:** Implement cloud-scale persistence and p2p fleet synchronization.

### Deliverables

#### 1. Pluggable Cloud Storage
- **S3 & Backblaze B2 Providers:**
  - Implement `SnapshotStorageProvider` for object storage
  - Multipart upload support for large snapshots
  - Server-side encryption options
- **Cloud Management UI:**
  - Remote storage browser
  - Transfer status monitor

#### 2. Fleet Synchronization (HypeLink)
- **P2P Sync:**
  - Secure P2P container synchronization using `HypeLink`
  - Zero-config local discovery
  - Conflict resolution for concurrent edits
- **Fleet Dashboard:**
  - View status of all devices in the fleet
  - Remote maintenance triggers

### Acceptance Criteria
- [ ] S3 provider passes retention and integrity tests
- [ ] Remote snapshots appear in the management dialog
- [ ] HypeLink successfully syncs a container between two instances
- [ ] Conflict resolution handles divergent states gracefully

---

## Branch Management Strategy

### Workflow

```
main
├── phase-0-project-setup → merge to main
├── phase-1-core-ui-shell → branch from main, merge to main
├── phase-2-dashboard-system-widgets → branch from main, merge to main
├── phase-3-dashboard-github-widgets → branch from main, merge to main
├── phase-4-machine-config-setup → branch from main, merge to main
├── phase-5-utilities-tools → branch from main, merge to main
├── phase-6-polish-sprint → branch from main, merge to main
├── phase-7-workstation-hub → branch from main, merge to main
├── phase-7-5-stability-hardening → branch from main, merge to main
├── phase-8-maintenance-monitoring → branch from main, merge to main
├── phase-9-power-user-system-builder → branch from main, merge to main
├── phase-10-extensions-system → branch from main, merge to main
├── phase-11-polish-release → branch from main, merge to main
└── phase-12-cloud-edge → branch from main, merge to main
```

### Branching Rules

1. **Each phase branch starts from `main`** (not from previous phase branch)
2. **Sequential development** - phases are developed in order (0 → 1 → 2 → … → 11)
3. **Merge to main only after:**
   - All deliverables for that phase are complete
   - All acceptance criteria are met
   - Code review is approved
   - CI/CD pipeline passes
4. **No direct commits to `main`** - all changes go through phase branches
5. **Phase branches are never rebased** - only merged to preserve history
6. **Feature branches within phases** (optional):
   - For large phases, create sub-branches: `phase-X/feature-name`
   - Merge sub-branches into phase branch via PRs

### Git Commands for Each Phase

```bash
# Start new phase branch from main
git checkout main
git pull origin main
git checkout -b phase-X-branch-name

# Work on the phase...

# Before merging to main, ensure everything is tested
git push origin phase-X-branch-name
# Create Pull Request
# Wait for review and CI/CD pass
# Merge to main (squash merge or merge commit)

# Clean up after merge
git checkout main
git pull origin main
git branch -d phase-X-branch-name
```

### Version Tags

Suggested tags (adjust to your release cadence):

- `v0.0.1` – After Phase 0 (project setup)
- `v0.1.0` – After Phase 1 (core UI shell)
- `v0.2.0` – After Phase 2 (system widgets)
- `v0.3.0` – After Phase 3 (GitHub widgets)
- `v0.4.0` – After Phase 4 (machine config)
- `v0.5.0` – After Phase 5 (utilities)
- `v0.6.0` – After Phase 6 (polish sprint)
- `v0.7.0` – After Phase 7 (workstation hub) — *optional*
- `v0.7.5` – After Phase 7.5 (stability hardening) — *optional*
- `v0.8.0` – After Phase 8 (maintenance / Guardian milestone) — *optional*
- `v0.9.0` – After Phase 9 (power-user system builder) — *optional*
- `v0.10.0` – After Phase 10 (extensions system) — *optional*
- `v1.0.0` – After Phase 11 (polish release — first public release target)
- `v1.1.0` – After Phase 12 (cloud / fleet)

---

## Risk Management

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| GTK4/Libadwaita API changes | Medium | Pin dependency versions, track upstream |
| Flatpak sandbox blocking required features | High | Use portals correctly, test early |
| System monitoring not working on some distros | Medium | Graceful degradation, test on multiple distros |
| GitHub API rate limits | Low | Caching, user authentication, fallback data |
| Performance issues with many widgets | Medium | Lazy loading, optimized rendering, profiling |
| Extension system security vulnerabilities | High | Sandboxing, permission model, code review |

### Schedule Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Underestimating phase complexity | High | Buffer time between phases, MVP approach |
| Blocker bugs in dependencies | Medium | Track upstream issues, have workarounds |
| Contributor availability | Medium | Clear documentation, async-friendly workflow |
| Scope creep | High | Strict adherence to phase deliverables, defer nice-to-haves |

---

## Milestones Summary

| Phase | Branch | Version (suggested) | Key Outcome |
|-------|--------|---------------------|-------------|
| 0 | `phase-0-project-setup` | v0.0.1 | Project infrastructure ready |
| 1 | `phase-1-core-ui-shell` | v0.1.0 | Navigatable app shell |
| 2 | `phase-2-dashboard-system-widgets` | v0.2.0 | System monitoring dashboard |
| 3 | `phase-3-dashboard-github-widgets` | v0.3.0 | GitHub integration complete |
| 4 | `phase-4-machine-config-setup` | v0.4.0 | Machine configuration working |
| 5 | `phase-5-utilities-tools` | v0.5.0 | Utilities & tools |
| 6 | `phase-6-polish-sprint` | v0.6.0 | Polish sprint (CI, toasts, Docker hygiene) |
| 7 | `phase-7-workstation-hub` | v0.7.0 | **Workstation hub** (Apps / Learn / Setup / Install / Remove) |
| 7.5 | `phase-7-5-stability-hardening` | v0.7.5 | Stability & security hardening |
| 8 | `phase-8-maintenance-monitoring` | v0.8.0 | Maintenance & Guardian (snapshots, monitoring) |
| 9 | `phase-9-power-user-system-builder` | v0.9.0 | **Power-User System Builder** (Install everything, see everything, backup everything) |
| 10 | `phase-10-extensions-system` | v0.10.0 | Extension system operational |
| 11 | `phase-11-polish-release` | v1.0.0 | **First public release** |
| 12 | `phase-12-cloud-edge` | v1.1.0 | Cloud & fleet synchronization |

---

## Next Steps

1. **Review and approve this plan** with all stakeholders.
2. **Confirm verified completed phases** against `main`: **0–8** are marked complete in this plan; **7.5** is in progress; **9–12** are not started.
3. **Choose the next implementation focus:**
   - **Phase 7.5 — stability hardening** (current priority)
   - **Phase 9 — power-user system builder** (transformational feature)
   - **Phase 10 — extensions** / **11 — release polish** / **12 — cloud** per roadmap priority
4. **Open a branch** from `main` for the chosen phase and track acceptance criteria in this file.



---

*Last updated: 14 April 2026 (Phase 7 workstation hub marked complete; tests + UI aligned)*

