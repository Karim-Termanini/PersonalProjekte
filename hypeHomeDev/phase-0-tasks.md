# Phase 0: `phase-0-project-setup` — Task Breakdown

> **Branch:** `phase-0-project-setup`
> **Goal:** Establish the foundational project structure, development environment, and CI/CD pipeline.
> **Agents:** 3 (Agent A, Agent B, Agent C)
> **Strategic Note:** Every artifact created in this phase must respect the Flatpak + Docker-first approach for cross-distribution compatibility.

---

## Agent Assignment Overview

| Agent | Focus Area | Deliverables |
|-------|-----------|--------------|
| **Agent A** | Project Structure & Application Skeleton | Directory layout, Python packages, GTK4 app skeleton, config management, logging |
| **Agent B** | Development Environment & Flatpak | Dockerfile, docker-compose.yml, dev-setup.sh, Flatpak manifest |
| **Agent C** | CI/CD Pipeline & Documentation | GitHub Actions workflows, pre-commit hooks, README, CONTRIBUTING, CODE_OF_CONDUCT, CHANGELOG |

---

## Agent A — Project Structure & Application Skeleton

### Task A.1: Create Directory Structure
**Priority:** High
**Dependencies:** None

Create the complete directory structure following `projectStructur.md`:

```
hypeHomeDev/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── app.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   └── defaults.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── events.py
│   │   └── logger.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── window.py
│   │   └── widgets/
│   │       └── __init__.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── data/
│   ├── __init__.py
│   └── schemas/
├── ui/
│   └── resources/
│       └── window.ui
├── extensions/
│   ├── __init__.py
│   └── builtin/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── test_config/
│   │   └── __init__.py
│   ├── test_core/
│   │   └── __init__.py
│   ├── test_ui/
│   │   └── __init__.py
│   └── test_utils/
│       └── __init__.py
├── assets/
│   ├── icons/
│   ├── images/
│   └── styles/
├── docs/
├── scripts/
├── .github/
├── Dockerfile
├── docker-compose.yml
├── dev-setup.sh
├── com.github.hypedevhome.yml
├── pyproject.toml
├── .pre-commit-config.yaml
├── .gitignore
├── README.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
└── CHANGELOG.md
```

### Task A.2: Initialize Python Packages
**Priority:** High
**Dependencies:** A.1

- Create `__init__.py` files in all Python directories
- Create `pyproject.toml` with project metadata:
  - Project name: `hypedevhome`
  - Python version: >=3.11
  - Dependencies: `PyGObject`, `PyGObject-stubs` (type hints)
  - Dev dependencies: `pytest`, `pytest-cov`, `ruff`, `mypy`
  - Entry point for CLI

### Task A.3: Basic GTK4 Application Skeleton
**Priority:** High
**Dependencies:** A.2

- `src/main.py` — Entry point with CLI argument handling
- `src/app.py` — `Gtk.Application` subclass that:
  - Initializes the application
  - Creates the main window
  - Sets application ID: `com.github.hypedevhome`
  - Registers D-Bus name
- `src/ui/window.py` — `Adw.ApplicationWindow` subclass:
  - Basic window with title "HypeDevHome"
  - Default size: 1200x800
  - Empty header bar
  - Placeholder content area

### Task A.4: Configuration Management
**Priority:** Medium
**Dependencies:** A.2

- `src/config/defaults.py` — Default configuration constants:
  - Config directory: `~/.config/dev-home/`
  - Default refresh interval: 2s
  - Default theme: "system"
  - Data directory: `~/.local/share/dev-home/`
- `src/config/manager.py` — `ConfigManager` class:
  - Load config from JSON file
  - Save config to JSON file
  - Get/set individual settings with defaults
  - Create config directory if it doesn't exist
  - Thread-safe read/write

### Task A.5: Logging Setup
**Priority:** Medium
**Dependencies:** A.2

- `src/core/logger.py` — Configure Python logging:
  - Log to file: `~/.local/share/dev-home/dev-home.log`
  - Log to stderr for debug mode
  - Log format: timestamp, level, module, message
  - Log rotation (max 10MB, keep 5 backups)
- `src/core/state.py` — `AppState` singleton:
  - Hold application-wide state
  - Hold config reference
  - Hold logger reference
  - Thread-safe access

### Task A.6: Event Bus
**Priority:** Medium
**Dependencies:** A.5

- `src/core/events.py` — Simple event bus:
  - `subscribe(event_name, callback)`
  - `emit(event_name, **kwargs)`
  - `unsubscribe(event_name, callback)`
  - Thread-safe event dispatching

### Task A.7: Utility Helpers
**Priority:** Low
**Dependencies:** A.2

- `src/utils/helpers.py` — Common utilities:
  - Path expansion helpers
  - Safe JSON loading
  - Human-readable file size formatting
  - Timestamp formatting

### Task A.8: Application Launch Verification
**Priority:** High
**Dependencies:** A.3, A.4, A.5

- Ensure application launches successfully with `python -m src.main`
- Verify empty window displays correctly
- Verify configuration directory is created on first launch
- Verify logging works (check log file after launch)

### Acceptance Criteria (Agent A)
- [ ] Complete directory structure exists
- [ ] All `__init__.py` files in place
- [ ] `pyproject.toml` is valid and installable
- [ ] Application launches with empty Libadwaita window
- [ ] Config directory created at `~/.config/dev-home/` on first launch
- [ ] Config save/load works across restarts
- [ ] Log file created and written to correctly
- [ ] Event bus delivers events to subscribers
- [ ] No import errors or circular dependencies

---

## Agent B — Development Environment & Flatpak

### Task B.1: Create Dockerfile
**Priority:** High
**Dependencies:** None

Create `Dockerfile` for the development environment:

**Base Image:** Fedora (latest) or Ubuntu (latest LTS) — choose one and document why

**Install Dependencies:**
- Python 3.11+
- GTK4 development libraries (`gtk4-devel` or `libgtk-4-dev`)
- Libadwaita (`libadwaita-devel` or `libadwaita-1-dev`)
- GObject introspection (`gobject-introspection-devel` or `gir1.2-gtk-4.0`)
- Build tools (`gcc`, `make`, `pkg-config`)
- Python build dependencies for PyGObject
- Testing tools: `pytest`, `pytest-cov`, `ruff`, `mypy`
- Flatpak build tools: `flatpak-builder`

**Configuration:**
- Working directory: `/app`
- User: non-root user `dev`
- Expose: none (GUI app, will use X11/Wayland socket)
- Environment variables for GTK4 and Libadwaita

**Docker run instructions:** Document how to run with Wayland/X11 display access

### Task B.2: Create docker-compose.yml
**Priority:** Medium
**Dependencies:** B.1

Create `docker-compose.yml`:
- Service: `dev` (main development environment)
- Volume mounts:
  - Project root: `/app`
  - X11 socket (optional): for display
  - Wayland socket (optional): for display
- Environment variables for display
- Optional services (future): database, mock servers
- Network: bridge

### Task B.3: Create dev-setup.sh Script
**Priority:** High
**Dependencies:** B.1, B.2

Create executable `scripts/dev-setup.sh`:
- Detect host OS and package manager
- Install Docker if not present
- Install docker-compose if not present
- Install Flatpak and flatpak-builder if not present
- Add Flathub remote if not present
- Build Docker image from Dockerfile
- Verify Docker build succeeded
- Verify Flatpak tools available
- Create `~/.config/dev-home/` directory
- Print success message with next steps

Make script:
- Idempotent (safe to run multiple times)
- Non-interactive where possible
- Clear error messages on failure
- Exit codes for automation

### Task B.4: Create Flatpak Manifest
**Priority:** High
**Dependencies:** None

Create `com.github.hypedevhome.yml`:

**App ID:** `com.github.hypedevhome`
**Runtime:** `org.gnome.Platform`
**Runtime Version:** `45` (or latest stable)
**SDK:** `org.gnome.Sdk`
**Command:** `hypedevhome`

**Modules:**
1. Python 3 (use SDK Python)
2. PyGObject
3. Libadwaita (from SDK)
4. Application source (from git or local)

**Finish-args (permissions):**
- `--socket=wayland`
- `--socket=fallback-x11`
- `--share=ipc`
- `--talk-name=org.freedesktop.Flatpak.*` (portals)
- `--talk-name=org.freedesktop.secrets` (secret storage)
- `--talk-name=org.freedesktop.Notifications`
- `--filesystem=~/.config/dev-home:create`
- `--filesystem=~/Dev`
- `--talk-name=org.freedesktop.DBus`
- `--socket=ssh-auth` (SSH agent)
- `--share=network`
- `--device=dri` (GPU access)

### Task B.5: Test Flatpak Build
**Priority:** High
**Dependencies:** B.4

- Run `flatpak-builder` to build the Flatpak
- Verify build completes without errors
- Install the built Flatpak locally
- Run the Flatpak and verify basic launch
- Verify permissions are correct (check sandbox)
- Document any build issues and fixes

### Task B.6: Create .gitignore
**Priority:** Medium
**Dependencies:** None

Create `.gitignore`:
- Python: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `dist/`, `build/`, `*.egg-info/`
- Docker: `.env`
- Flatpak: `.flatpak-builder/`, `repo/`, `builddir/`
- IDE: `.vscode/`, `.idea/`, `*.swp`, `*.swo`
- OS: `.DS_Store`, `Thumbs.db`
- Config: `~/.config/dev-home/` (don't commit user configs)
- Logs: `*.log`
- Coverage: `htmlcov/`, `.coverage`

### Task B.7: Create Desktop Entry & Icons
**Priority:** Medium
**Dependencies:** None

- `assets/icons/com.github.hypedevhome.svg` — Application icon (scalable)
- `assets/icons/com.github.hypedevhome-symbolic.svg` — Symbolic icon
- `data/com.github.hypedevhome.desktop` — Desktop entry file:
  - Name: HypeDevHome
  - Comment: Developer dashboard for Linux
  - Exec: hypedevhome
  - Icon: com.github.hypedevhome
  - Categories: Development;Utility;
  - Terminal: false
- `data/com.github.hypedevhome.metainfo.xml` — AppData for Flatpak:
  - Name, summary, description
  - Screenshots placeholder
  - Release info placeholder
  - Content rating

### Acceptance Criteria (Agent B)
- [ ] Dockerfile builds successfully with `docker build`
- [ ] Docker container runs and can execute Python
- [ ] docker-compose.yml is valid (passes `docker-compose config`)
- [ ] dev-setup.sh runs without errors on a clean system
- [ ] Flatpak manifest builds without errors
- [ ] Flatpak application launches in sandbox
- [ ] Flatpak permissions are correct and minimal
- [ ] .gitignore covers all common artifacts
- [ ] Desktop entry and icon files are valid

---

## Agent C — CI/CD Pipeline & Documentation

### Task C.1: GitHub Actions — Linting Workflow
**Priority:** High
**Dependencies:** None

Create `.github/workflows/lint.yml`:
- Triggers: `push`, `pull_request` to `main` and `phase-*` branches
- Steps:
  1. Checkout code
  2. Set up Python 3.11
  3. Install dependencies from `pyproject.toml`
  4. Run `ruff check src/ tests/`
  5. Run `ruff format --check src/ tests/`
  6. Run `flake8 src/ tests/`
- Fail on any linting errors

### Task C.2: GitHub Actions — Type Checking Workflow
**Priority:** High
**Dependencies:** None

Create `.github/workflows/type-check.yml`:
- Triggers: `push`, `pull_request`
- Steps:
  1. Checkout code
  2. Set up Python 3.11
  3. Install dependencies
  4. Run `mypy src/` with strict mode
- Allow warnings initially, but fail on critical errors
- Plan: tighten mypy config in later phases

### Task C.3: GitHub Actions — Testing Workflow
**Priority:** High
**Dependencies:** None

Create `.github/workflows/test.yml`:
- Triggers: `push`, `pull_request`
- Steps:
  1. Checkout code
  2. Set up Python 3.11
  3. Install dependencies
  4. Run `pytest tests/ --cov=src --cov-report=xml`
  5. Upload coverage report
- Matrix testing: Python 3.11, 3.12
- Fail if any tests fail

### Task C.4: GitHub Actions — Docker Build Validation
**Priority:** Medium
**Dependencies:** Task B.1 (Dockerfile must exist)

Create `.github/workflows/docker-build.yml`:
- Triggers: `push` to `main`, `pull_request`
- Steps:
  1. Checkout code
  2. Set up Docker
  3. Build Docker image
  4. Run container and verify basic commands
- Fail if Docker build fails

### Task C.5: GitHub Actions — Flatpak Build Validation
**Priority:** Medium
**Dependencies:** Task B.4 (Flatpak manifest must exist)

Create `.github/workflows/flatpak-build.yml`:
- Triggers: `push` to `main`, `pull_request`
- Steps:
  1. Checkout code
  2. Set up Flatpak tools
  3. Add Flathub remote
  4. Run `flatpak-builder` on manifest
  5. Verify build artifacts
- Fail if Flatpak build fails

### Task C.6: Pre-commit Hooks
**Priority:** High
**Dependencies:** C.1, C.2

Create `.pre-commit-config.yaml`:
- Hooks:
  - `ruff` (linting)
  - `ruff-format` (formatting)
  - `mypy` (type checking)
  - Check for merge conflicts
  - Check for trailing whitespace
  - Check for added large files
  - Validate YAML files
  - Validate TOML files
- Configure to run on: `*.py`, `*.yml`, `*.yaml`, `*.toml`, `*.json`

### Task C.7: Create README.md
**Priority:** High
**Dependencies:** None

Create comprehensive `README.md`:

**Sections:**
1. Project banner/logo placeholder
2. **Strategic Note** (Flatpak + Docker cross-distro commitment) — prominent placement
3. Brief project description
4. Technology stack
5. Features overview (Dashboard, Machine Setup, Extensions, Utilities)
6. **Quick Start:**
   - Prerequisites (Docker, Flatpak)
   - Clone repository
   - Run `dev-setup.sh`
   - Launch application
7. **Development Setup:**
   - Docker instructions
   - Local development (without Docker)
   - Running tests
   - Running linters
8. **Project Structure** (link to `projectStructur.md`)
9. **Contributing** (link to `CONTRIBUTING.md`)
10. **License** badge
11. **Badges:** CI status, license, version (placeholder)

### Task C.8: Create CONTRIBUTING.md
**Priority:** High
**Dependencies:** None

Create `CONTRIBUTING.md`:

**Sections:**
1. Welcome message
2. Code of Conduct reference
3. How to contribute:
   - Reporting bugs
   - Suggesting features
   - Submitting pull requests
4. Development workflow:
   - Branch naming convention (`phase-X-description`)
   - Commit message style (conventional commits)
   - PR review process
5. Setup development environment
6. Running tests and linters
7. Code style guidelines
8. Extension development (placeholder link)

### Task C.9: Create CODE_OF_CONDUCT.md
**Priority:** Medium
**Dependencies:** None

Create `CODE_OF_CONDUCT.md`:
- Use Contributor Covenant v2.1 as base
- Adapt for this project
- Include:
  - Our pledge
  - Our standards
  - Enforcement responsibilities
  - Scope
  - Contact info (maintainers)

### Task C.10: Create CHANGELOG.md
**Priority:** Medium
**Dependencies:** None

Create `CHANGELOG.md`:
- Keep a Changelog format (https://keepachangelog.com)
- Sections: Unreleased, [0.1.0] - Initial Release (placeholder)
- Categories: Added, Changed, Deprecated, Removed, Fixed, Security
- Add note that all future releases will follow SemVer

### Task C.11: Create GitHub Issue Templates
**Priority:** Low
**Dependencies:** None

Create `.github/ISSUE_TEMPLATE/`:
- `bug_report.yml` — Bug report template with environment, steps, expected/actual behavior
- `feature_request.yml` — Feature request template with problem, solution, alternatives
- `documentation.yml` — Documentation improvement template

### Acceptance Criteria (Agent C)
- [ ] All 5 GitHub Actions workflows exist and are valid YAML
- [ ] Linting workflow runs successfully on PR
- [ ] Type checking workflow runs successfully on PR
- [ ] Testing workflow runs successfully on PR (even with 0 tests)
- [ ] Docker build workflow validates Dockerfile
- [ ] Flatpak build workflow validates manifest
- [ ] Pre-commit config is valid and runs without errors
- [ ] README.md is complete and accurate
- [ ] CONTRIBUTING.md provides clear guidance
- [ ] CODE_OF_CONDUCT.md is present and appropriate
- [ ] CHANGELOG.md follows Keep a Changelog format
- [ ] Issue templates are valid YAML

---

## Execution Order & Dependencies

```
Phase 0 Execution Timeline:

┌─────────────────────────────────────────────────────────────┐
│                    PARALLEL START                           │
├───────────────┬──────────────────┬──────────────────────────┤
│  Agent A      │     Agent B      │       Agent C            │
│               │                  │                          │
│  A.1 Dir Str. │  B.1 Dockerfile  │  C.1 Lint Workflow       │
│  A.2 Pkg Init │  B.2 Comp. YAML  │  C.2 Type Check Workflow │
│  A.3 App Skel │  B.3 dev-setup   │  C.3 Test Workflow       │
│  A.4 Config   │  B.4 Manifest    │  C.4 Docker Workflow     │
│  A.5 Logging  │  B.5 Test FP     │  C.5 FP Workflow         │
│  A.6 Events   │  B.6 gitignore   │  C.6 Pre-commit          │
│  A.7 Helpers  │  B.7 Icons/Desk  │  C.7 README              │
│               │                  │  C.8 CONTRIBUTING        │
│               │                  │  C.9 CoC                 │
│               │                  │  C.10 Changelog          │
│               │                  │  C.11 Issue Templates    │
├───────────────┴──────────────────┴──────────────────────────┤
│                     INTEGRATION                             │
│                                                             │
│  A.8 Launch Verification ← depends on A.3, A.4, A.5        │
│                                                             │
│  All agents verify their acceptance criteria                │
├─────────────────────────────────────────────────────────────┤
│                     FINAL REVIEW                            │
│                                                             │
│  - Cross-agent integration testing                          │
│  - All acceptance criteria verified                         │
│  - Merge into main branch                                   │
└─────────────────────────────────────────────────────────────┘
```

### Critical Integration Points

1. **Agent A ↔ Agent B:**
   - Application skeleton (A.3) must run inside Docker container (B.1)
   - Application must work inside Flatpak sandbox (B.4, B.5)

2. **Agent A ↔ Agent C:**
   - Linting (C.1) must pass on all Python code (A.2-A.7)
   - Type checking (C.2) must pass on all Python code
   - Tests (C.3) must pass on application code

3. **Agent B ↔ Agent C:**
   - Docker workflow (C.4) validates B.1
   - Flatpak workflow (C.5) validates B.4

---

## Coordination Notes

- **Agent A** should frequently sync with Agent B to ensure the application runs correctly in both Docker and Flatpak environments.
- **Agent C** should run linting/type checking against Agent A's code early to catch style issues before they accumulate.
- **All agents** should commit to the `phase-0-project-setup` branch.
- **Code reviews:** Each agent's PRs should be reviewed by at least one other agent (or maintainer) before merge.

---

## Deliverables Summary

| Agent | Key Files Created |
|-------|------------------|
| **A** | `src/main.py`, `src/app.py`, `src/ui/window.py`, `src/config/manager.py`, `src/config/defaults.py`, `src/core/logger.py`, `src/core/state.py`, `src/core/events.py`, `src/utils/helpers.py`, `pyproject.toml`, directory structure |
| **B** | `Dockerfile`, `docker-compose.yml`, `scripts/dev-setup.sh`, `com.github.hypedevhome.yml`, `.gitignore`, `assets/icons/*.svg`, `data/*.desktop`, `data/*.metainfo.xml` |
| **C** | `.github/workflows/*.yml` (5 files), `.pre-commit-config.yaml`, `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `.github/ISSUE_TEMPLATE/*.yml` (3 files) |
