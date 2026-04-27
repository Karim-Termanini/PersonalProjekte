# Phase 4: `phase-4-machine-config-setup` — Task Breakdown

> **Branch:** `phase-4-machine-config-setup`
> **Goal:** Build the Machine Configuration section for one-click development environment setup.
> **Agents:** 3 (Agent A, Agent B, Agent C)

---

## Overview

Phase 4 focuses on building the **Machine Setup** page — a powerful one-click configuration system that helps developers set up their complete development environment. This includes package installation, repository cloning, dev folder creation, and developer settings application.

---

## Agent Assignment Overview

| Agent | Focus Area | Deliverables |
|-------|-----------|--------------|
| **Agent A** | Machine Setup Framework & UI | Page structure, package catalog UI, repository cloner UI, progress tracking |
| **Agent B** | Backend Services & Package Management | Distro detection, package managers, Flatpak integration, Git operations, host executor |
| **Agent C** | Dev Settings & Configuration Automation | Dev folder creator, developer settings applier, environment templates, backup/restore system |

---

## Agent A — Machine Setup Framework & UI

### Task A.1: Machine Setup Page Structure
**Priority:** High
**Dependencies:** Phase 1 A.4 (Page Framework)

Create the main Machine Setup page in `src/ui/pages/machine_setup.py`:
- Tabbed/accordion layout with 5 sections:
  1. Install Applications
  2. Clone Repositories
  3. Create Dev Folder
  4. Apply Developer Settings
  5. Environments Support
- Use `Gtk.Notebook` or `Adw.ViewStack` for tab navigation
- Progress indicators for long-running operations
- Clear success/error feedback with toast notifications
- Integrate with existing `BasePage` lifecycle

### Task A.2: Package Catalog UI
**Priority:** High
**Dependencies:** A.1, B.2

Implement the application installer interface:
- `PackageCatalogWidget` with search and filter
- Category grouping (Editors, Languages, Tools, Terminal, etc.)
- Checkbox selection for packages
- "Install All Dev Tools" quick-select button
- Installation progress bars (per-package and overall)
- Show already-installed status
- Package metadata display (name, description, icon, category)
- Handle empty states and loading states

### Task A.3: Repository Cloner UI
**Priority:** High
**Dependencies:** A.1, B.4

Build the Git repository cloning interface:
- URL input field with validation
- Authentication method selector (HTTPS/SSH)
- Clone destination picker (default `~/Dev/`)
- Real-time progress display during clone
- Post-clone action buttons:
  - Open in terminal
  - Open in VS Code
  - Open in Neovim
  - Open in file manager
- Clone history list with quick access
- Handle existing repos (detect and show pull option)

### Task A.4: Progress & Feedback System
**Priority:** High
**Dependencies:** Phase 1 C.3 (Error Handling)

Create reusable progress tracking components:
- `OperationProgressDialog` for modal operations
- `InlineProgressBar` for in-page progress
- Toast notifications for completion
- Error dialogs with retry options
- Operation history/log viewer
- Cancel button for long-running operations

### Acceptance Criteria (Agent A)
- [ ] Machine Setup page loads with all 5 tabs
- [ ] Package catalog displays with search and categories
- [ ] Repository cloner validates URLs and shows progress
- [ ] Progress indicators work for all operations
- [ ] No UI freezing during background operations
- [ ] All states handled (loading, success, error, empty)

---

## Agent B — Backend Services & Package Management

### Task B.1: Distribution Detection Service
**Priority:** High

Implement `src/core/setup/distro_detector.py`:
- Parse `/etc/os-release` for distribution info
- Detect available package managers (flatpak, dnf, apt, pacman, zypper)
- Return structured distro information:
  ```python
  {
      "distro": "fedora",
      "version": "39",
      "package_manager": "dnf",
      "has_flatpak": True,
      "has_snap": False,
  }
  ```
- Fallback detection for edge cases
- Cache detection results

### Task B.2: Package Manager Abstraction
**Priority:** High
**Dependencies:** B.1

Create `src/core/setup/package_manager.py`:
- Abstract `PackageManager` base class
- Implementations for:
  - `FlatpakManager` (primary)
  - `DnfManager` (Fedora/RHEL)
  - `AptManager` (Debian/Ubuntu)
  - `PacmanManager` (Arch)
  - `ZypperManager` (openSUSE)
- Common interface:
  - `install(package_id)`
  - `remove(package_id)`
  - `is_installed(package_id)`
  - `search(query)`
  - `list_installed()`
- Async operations with progress callbacks
- Error handling and retry logic

### Task B.3: Package Catalog Data
**Priority:** High
**Dependencies:** B.2

Create `src/core/setup/package_catalog.py`:
- Curated list of development tools:
  ```python
  {
      "id": "com.github.neovim",
      "name": "Neovim",
      "description": "Hyperextensible Vim-based text editor",
      "category": "editors",
      "flatpak_id": "io.neovim.nvim",
      "apt_package": "neovim",
      "dnf_package": "neovim",
      "pacman_package": "neovim",
  }
  ```
- Categories: editors, languages, tools, terminal, databases, containers
- Search and filter functionality
- Metadata: icon, homepage, description, popularity
- Load from JSON file for easy updates

### Task B.4: Git Operations Service
**Priority:** High

Implement `src/core/setup/git_ops.py`:
- Clone repository with progress callbacks
- Detect existing repositories
- Pull latest changes
- Branch information
- Remote URL parsing and validation
- SSH vs HTTPS detection
- Handle authentication (git credential helper)
- Async operations with cancellation support

### Task B.5: Host Command Executor
**Priority:** Medium

Create `src/core/setup/host_executor.py`:
- Execute commands with elevated privileges (polkit/pkexec)
- Flatpak portal for sandboxed execution
- Command output streaming
- Timeout handling
- Error capture and reporting
- Safe command construction (prevent injection)

### Acceptance Criteria (Agent B)
- [ ] Distro detection accurate on Fedora, Ubuntu, Arch
- [ ] Package managers install/remove packages correctly
- [ ] Package catalog has 20+ curated dev tools
- [ ] Git clone works with HTTPS and SSH
- [ ] All operations are async with progress callbacks
- [ ] Error handling is comprehensive and user-friendly

---

## Agent C — Dev Settings & Configuration Automation

### Task C.1: Dev Folder Creator
**Priority:** High

Implement `src/core/setup/dev_folder.py`:
- Create `~/Dev` directory
- Performance optimizations:
  - Detect Btrfs filesystem
  - Create Btrfs subvolume (if supported)
  - Suggest mount options (noatime, discard)
  - Set correct permissions
- One-click creation with polkit authentication
- Verification after creation
- Rollback on failure
- UI feedback with explanations

### Task C.2: Developer Settings Applier
**Priority:** High
**Dependencies:** B.1, B.5

Implement `src/core/setup/dev_settings.py`:
- **File Manager Settings:**
  - Show hidden files
  - Show file extensions
  - Sort order preferences
  - Support: Nautilus, Dolphin, Thunar, Nemo

- **Git Global Configuration:**
  - user.name, user.email
  - Default editor (neovim, vscode, etc.)
  - Rebase behavior
  - Autocrlf settings
  - Credential helper setup

- **Shell Enhancements:**
  - Useful aliases (ls, grep, git shortcuts)
  - Detect shell (bash, zsh, fish)
  - Modern tools integration (eza, bat, delta, fzf)
  - Prompt customization (starship, oh-my-zsh detection)

- **Environment Variables:**
  - EDITOR, VISUAL
  - PATH additions
  - Language/toolchain paths

- **SSH Agent Auto-start:**
  - Desktop entry creation
  - Systemd user service option
  - Shell rc modification

### Task C.3: Backup & Restore System
**Priority:** High
**Dependencies:** C.2

Implement `src/core/setup/config_backup.py`:
- Backup existing configs before changes:
  - Git config (`~/.gitconfig`)
  - Shell configs (`.bashrc`, `.zshrc`, `.config/fish`)
  - File manager configs
  - Desktop entries
- Automatic backup with timestamps
- Backup history with metadata
- One-click restore from backup
- Export/import backup archives
- Preview changes before applying
- Safe defaults (never delete originals without backup)

### Task C.4: Settings Apply UI
**Priority:** High
**Dependencies:** A.1, C.2, C.3

Build the developer settings application interface:
- Checklist of available settings with toggles
- Per-setting preview of what will change
- "Apply All" and "Apply Selected" buttons
- Progress display during application
- Success summary with details
- Error handling with partial rollback info
- Link to view backups

### Task C.5: Environments Support (Foundation)
**Priority:** Medium

Implement `src/core/setup/environments.py`:
- **Dev Containers:**
  - Detect Podman or Docker availability
  - Basic devcontainer.json template generator
  - Integration placeholders for VS Code Dev Containers

- **Distrobox / Toolbx:**
  - Installation guidance
  - Create containers from templates
  - Quick launch commands
  - Integration with host filesystem

- **Cloud Environments (Placeholder):**
  - GitHub Codespaces UI placeholder
  - Gitpod UI placeholder
  - Marked as "coming soon"

### Acceptance Criteria (Agent C)
- [ ] Dev folder creates with correct permissions
- [ ] Developer settings apply safely with backups
- [ ] Backup/restore works for all config types
- [ ] Settings UI shows clear previews and progress
- [ ] Partial failures handled gracefully with rollback info
- [ ] Environments support detects available tools

---

## Phase 4 Acceptance Criteria (Global)

### Functional Requirements
- [ ] Package catalog displays 20+ development tools
- [ ] Installation works for at least 3 different package managers
- [ ] Distro detection accurate on Fedora, Ubuntu, Arch Linux
- [ ] Repository clone completes successfully (HTTPS and SSH)
- [ ] Dev folder created with optional Btrfs optimization
- [ ] Developer settings apply safely with automatic backups
- [ ] All operations show clear progress and feedback
- [ ] No UI freezing during any operation

### Quality Requirements
- [ ] 90%+ test coverage for new code
- [ ] All async operations have cancellation support
- [ ] Comprehensive error handling with user-friendly messages
- [ ] Polkit integration works for privileged operations
- [ ] Flatpak compatibility verified
- [ ] Documentation complete (setup guide, troubleshooting)

### Performance Requirements
- [ ] Package catalog loads in <500ms
- [ ] Distro detection completes in <100ms
- [ ] UI remains responsive during installations
- [ ] Memory usage <200MB during operations

---

## Technical Architecture

```
src/core/setup/
├── distro_detector.py        # Agent B
├── package_manager.py        # Agent B
├── package_catalog.py        # Agent B
├── package_catalog_data.json # Agent B
├── git_ops.py                # Agent B
├── host_executor.py          # Agent B
├── dev_folder.py             # Agent C
├── dev_settings.py           # Agent C
├── config_backup.py          # Agent C
└── environments.py           # Agent C

src/ui/pages/
└── machine_setup.py          # Agent A

src/ui/widgets/
├── package_catalog.py         # Agent A
├── repo_cloner.py            # Agent A
└── progress_dialog.py         # Agent A
```

---

## Integration Points

### With Existing Code
- Uses `BasePage` from Phase 1 (A.4)
- Uses `AppState` for configuration
- Uses `EventBus` for progress notifications
- Uses error handling from Phase 1 (C.3)
- Integrates with Settings dialog for config management

### Cross-Agent Dependencies
- **Agent A** needs Agent B's package catalog data and package manager implementations
- **Agent A** needs Agent C's dev folder and settings logic for UI feedback
- **Agent C** needs Agent B's distro detection and host executor
- **Agent B** is mostly independent (core services only)

---

## Suggested Development Order

1. **Week 1:** Agent B starts distro detection + package manager abstraction
2. **Week 1:** Agent A starts Machine Setup page structure
3. **Week 1:** Agent C starts dev folder creator + backup system
4. **Week 2:** Agent B completes package catalog + git ops
5. **Week 2:** Agent A builds package catalog UI + repo cloner UI
6. **Week 2:** Agent C completes developer settings applier
7. **Week 3:** Integration testing and bug fixes
8. **Week 3:** Performance optimization and documentation
9. **Week 3:** Final review and merge to main

---

## Notes

- All privileged operations must use polkit/pkexec for security
- Flatpak compatibility is mandatory — test in sandboxed environment
- Backup everything before modifying user configs
- Provide clear explanations for every action
- Never break user's setup — safety first
