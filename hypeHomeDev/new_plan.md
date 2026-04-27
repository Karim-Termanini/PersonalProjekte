 PARTNER TALK - PERFECT! NOW I GET IT!

  🎯 YOU'RE 100% RIGHT! Phase 7.5 is done, and you want CONTEXTUAL LEARNING - docs WITH the tools, not in a separate graveyard!

  💡 THE VISION: "LEARN WHERE YOU WORK"

  Instead of:
  Workstation → Learn → Docker Cheatsheet
  Workstation → Servers → Docker Manager

  We want:
  Servers → Docker Manager
  ├── Containers (running/stopped)
  ├── Images (available/pulled)  
  ├── **Docker Docs** (right there!)
  │   • docker ps, docker logs, docker exec
  │   • Common commands with examples
  │   • Troubleshooting tips
  └── Quick Actions (start/stop/restart)

  **🔧 REORGANIZATION PLAN:**

  1. KILL THE "LEARN" TAB - Move content to where it's used
  2. PROMOTE IMPORTANT SECTIONS to main sidebar
  3. MAKE DASHBOARD SHOW SERVERS OVERVIEW always visible
  4. CONTEXTUAL DOCS right next to the tools

  **📊 PROPOSED NEW STRUCTURE:**

  MAIN SIDEBAR (Logical, Not Dumpsite)
  ├── 🏠 Welcome Dashboard (Default - Outcome wizards + System overview)
  ├── 📊 System Monitor (CPU/GPU/Memory/Network - Always visible)
  ├── 🐳 Servers Hub (Docker + Runtime + Docs)
  │   ├── Containers (list, start/stop, logs)
  │   ├── Images (manage, pull, remove)
  │   ├── Compose (stacks, up/down)
  │   ├── **Docker Docs** (commands, examples, troubleshooting)
  │   └── Ports & Networking
  ├── ⚙️ Services Manager (Systemd + Docs)
  │   ├── Active Services (Tailscale, NordVPN, etc.)
  │   ├── Startup Control (enable/disable)
  │   ├── Log Viewer
  │   ├── **Service Docs** (systemctl commands, journalctl)
  │   └── Health Checks
  ├── 🤖 AI Tools (Ollama + Models + Docs)
  │   ├── Models (list, pull, remove)
  │   ├── Open WebUI (manage)
  │   ├── **AI Docs** (ollama commands, model info)
  │   └── Local Chat
  ├── 📦 Package Manager (Install/Remove + Docs)
  │   ├── Browse Catalog (search, categories)
  │   ├── Installed (view, update, remove)
  │   ├── **Package Docs** (apt/dnf/pacman commands)
  │   └── Dependency Checker
  ├── ⚡ Quick Setup (Outcome wizards - moved from dashboard)
  │   ├── Python Data Science
  │   ├── Web Development
  │   ├── AI/ML Local
  │   ├── Full Stack (Everything)
  │   └── Custom...
  ├── 🔧 Config Center (Git, SSH, Dotfiles + Docs)
  │   ├── Git Identity
  │   ├── SSH Keys
  │   ├── Dotfiles
  │   ├── Environment Variables
  │   └── **Config Docs** (git commands, ssh setup)
  ├── 🛡️ Maintenance (Snapshots, Backups, Logs)
  └── ⚙️ Settings

  **🎯 WHAT MOVES WHERE:**

  FROM "Learn" Section → TO Contextual Locations:

  1. Docker Cheatsheet → Servers Hub (as Docker Docs tab)
  2. Bash Cheatsheet → Welcome Dashboard (as "Terminal Tips" popup)
  3. Neovim Cheatsheet → Package Manager (when installing Neovim)
  4. Linux FHS → System Monitor (as "Filesystem" info panel)
  5. Session Info → Welcome Dashboard (as system summary)

  **📊 DASHBOARD WITH SERVERS OVERVIEW:**

  Welcome Dashboard (Default View)
  ┌─────────────────────────────────────────────────┐
  │            WELCOME TO YOUR DEV HOME             │
  │                                                 │
  │  🚀 [ QUICK SETUP WIZARDS ]                     │
  │     • Python Data Science                       │
  │     • Web Development                           │
  │     • AI/ML Local                               │
  │     • Full Stack (Everything)                   │
  │                                                 │
  │  📊 [ SYSTEM OVERVIEW - ALWAYS VISIBLE ]        │
  │  ┌─────────────────────────────────────────┐   │
  │  │  CPU: 12%  |  RAM: 4.2/16GB (26%)       │   │
  │  │  Disk: 128GB SSD (78% free)             │   │
  │  │                                         │   │
  │  │  🐳 SERVERS STATUS:                     │   │
  │  │  • Docker: 3 containers running         │   │
  │  │    - postgres (5432) ✓                  │   │
  │  │    - redis (6379) ✓                     │   │
  │  │    - nginx (8080) ⚠️ (high CPU)         │   │
  │  │  • Ports in use: 5432, 6379, 8080, 3000 │   │
  │  │  • Systemd: 8 services active           │   │
  │  └─────────────────────────────────────────┘   │
  │                                                 │
  │  🛠️ [ QUICK ACTIONS ]                           │
  │     • Add database (PostgreSQL/Redis/MySQL)     │
  │     • Install AI model                          │
  │     • View Docker logs                          │
  │     • Open terminal                             │
  └─────────────────────────────────────────────────┘

  **🔧 TECHNICAL IMPLEMENTATION:**

  Week 1: Reorganize Sidebar & Dashboard
  # New _PAGE_REGISTRY in window.py
  _PAGE_REGISTRY = [
      ("welcome", "Welcome", "user-home-symbolic", WelcomeDashboardPage),
      ("system", "System Monitor", "utilities-system-monitor-symbolic", SystemMonitorPage),
      ("servers", "Servers", "network-server-symbolic", ServersHubPage),
      ("services", "Services", "application-x-firmware-symbolic", ServicesManagerPage),
      ("ai", "AI Tools", "preferences-desktop-accessibility-symbolic", AIToolsPage),
      ("packages", "Package Manager", "folder-download-symbolic", PackageManagerPage),
      ("setup", "Quick Setup", "system-run-symbolic", QuickSetupPage),
      ("config", "Config", "emblem-synchronizing-symbolic", ConfigCenterPage),
      ("maintenance", "Maintenance", "security-high-symbolic", MaintenancePage),
      ("settings", "Settings", "preferences-system-symbolic", SettingsPage),
  ]

  Week 2: Move Learn Content to Contextual Locations
  # ServersHubPage with integrated docs
  class ServersHubPage:
      def build_content(self):
          # Tabs: Containers, Images, Compose, Docs, Networking
          self._stack = Gtk.Stack()
          self._stack.add_titled(DockerContainersPanel(), "containers", "Containers")
          self._stack.add_titled(DockerImagesPanel(), "images", "Images")
          self._stack.add_title(DockerComposePanel(), "compose", "Compose")
          self._stack.add_titled(DockerDocsPanel(), "docs", "Docker Docs")  # ← LEARN CONTENT HERE!
          
          # Docs panel shows cheatsheet + examples
          # docker ps, docker logs, docker exec, common workflows

  Week 3: Dashboard with Servers Overview
  # WelcomeDashboardPage - shows servers status
  class WelcomeDashboardPage:
      def build_content(self):
          # Quick setup wizards
          self._wizards_section = OutcomeWizardsSection()
          
          # System overview with servers
          self._overview_section = SystemOverviewSection()
          self._overview_section.add_server_status(
              docker_containers=get_docker_containers(),
              ports_in_use=get_open_ports(),
              systemd_services=get_active_services()
          )
          
          # Quick actions
          self._quick_actions = QuickActionsSection()

  **🎯 THE RESULT:**

  For a user managing Docker:
  1. Opens app → Sees servers status on dashboard ("3 containers running")
  2. Clicks "Servers" in sidebar → Goes to Servers Hub
  3. Sees containers list + Docker Docs tab right there
  4. Can manage containers AND learn commands in same place

  For a new user:
  1. Opens app → Sees Welcome Dashboard with wizards
  2. Clicks "Python Data Science" → Gets everything installed
  3. Dashboard shows "PostgreSQL container running on port 5432"
  4. Can click to view logs or see Docker commands




  🔧 **Detailed Workflow Implementation**

  **Phase 1: Reorganize Sidebar & Dashboard (Week 1)**

  **Task 1.1: Create New WelcomeDashboardPage**
  - Location: src/ui/pages/welcome_dashboard.py
  - Components:
    1. Outcome Wizards Section: Move from WorkstationSystemDashboardPanel
    2. System Health Widget: Integrate WorkstationServersOverviewPanel (always visible)
    3. Quick Actions Panel: Terminal tips, power installer, config shortcuts
    4. Recent Activity: Last installed packages, system changes

  **Task 1.2: Update `window.py` `_PAGE_REGISTRY`**
  - Make welcome the default page
  - Remove redundant pages (merge functionality)
  - Update keyboard shortcuts (Ctrl+1 = Welcome)

  **Task 1.3: Create SystemMonitorPage**
  - Location: src/ui/pages/system_monitor.py
  - Purpose: Dedicated real-time monitoring (CPU/GPU/Memory/Network)
  - Reuse: WorkstationServersOverviewPanel + enhanced charts

  **Phase 2: Move Learn Content to Contextual Locations (Week 2)**

  **Task 2.1: Integrate Docker Docs into Servers Hub**
  - Current: DockerCheatsheetPage in Learn tab
  - New: Add "Docs" tab in ServersHubPage with:
    - Docker cheatsheet
    - Docker Compose examples
    - Port management guide
    - Volume management

  **Task 2.2: Move Bash/Neovim Cheatsheets**
  - Bash Cheatsheet: Add to Welcome Dashboard as "Terminal Tips" quick action
  - Neovim Cheatsheet: Add to Package Manager when installing Neovim
  - CLI Reference: Move to Config Center → Terminal section

  **Task 2.3: Remove Standalone "Learn" Tab**
  - Delete WorkstationLearnPanel and related files
  - Update imports and references

  **Phase 3: Polish & Context Help (Week 3)**

  **Task 3.1: Add Hover/Click Contextual Help**
  - Every section: Add "?" icon with contextual documentation
  - Outcome wizards: Add "What you'll get" tooltips
  - Install buttons: Show "This will install X, Y, Z"

  **Task 3.2: Expand Outcome Profiles**
  - Current: 3 profiles (Python DS, Web Dev, AI Local)
  - Add:
    - Full Stack DevOps: Docker, Kubernetes, Terraform, Ansible
    - Game Development: Godot, Unity, Blender
    - Scientific Computing: Julia, R, MATLAB alternatives
    - Creative Suite: GIMP, Inkscape, Krita, Blender
    - costum

  **Task 3.3: Add "Install Everything" Power Mode**
  - Button: In Welcome Dashboard Quick Actions
  - Function: Install ALL outcome profiles (with progress tracking)
  - Warning: Show disk space requirements, estimated time

  📁 **File Structure Changes**

  **New Files to Create**
  src/ui/pages/welcome_dashboard.py          # New default view
  src/ui/pages/system_monitor.py             # Dedicated monitoring
  src/ui/pages/servers_hub.py               # Enhanced servers page
  src/ui/pages/package_manager.py           # Unified install/remove
  src/ui/pages/quick_setup.py               # Outcome wizards + power mode
  src/ui/pages/config_center.py             # Git, SSH, dotfiles, system

  **Files to Modify**
  src/ui/window.py                          # Update _PAGE_REGISTRY
  src/ui/pages/workstation.py               # Deprecate (or keep as legacy)
  src/ui/widgets/workstation/__init__.py    # Update exports

  **Files to Delete/Merge** *(revised: keep `learn_factory` + cheatsheet modules — they back Servers/Welcome/Install/Config; only the **Learn hub widget** was removed.)*
  ~~src/ui/widgets/workstation/learn_factory.py~~ *(retained)*
  ~~WorkstationLearnPanel~~ *(removed from `panels.py` + hub)*
  ~~bash/docker/nvim cheatsheet modules~~ *(retained, re-wired)*

  🔄 **Migration Strategy**

  **Step 1: Create New Pages (Backward Compatible)**
  1. Create new pages alongside existing ones
  2. Test navigation between old and new
  3. Update deep links (navigate_workstation_section)

  **Step 2: Move Content Gradually**
  1. First move Docker docs to Servers Hub
  2. Then move Bash cheatsheet to Welcome
  3. Finally remove Learn tab

  **Step 3: Update All References**
  1. Update imports in window.py
  2. Update keyboard shortcuts
  3. Update config persistence (last_page)

  🎨 **UI/UX Improvements**

  **Visual Hierarchy**
  1. Primary Actions (Outcome wizards): Large cards, prominent
  2. System Status: Always visible, top-right corner
  3. Quick Actions: Contextual to current section
  4. Learning Content: Integrated, not separate

  **Contextual Learning Pattern**
  # Example: When user clicks "Install Docker" in Servers Hub
  if user_clicks_install_docker:
      show_modal_with({
          "title": "Installing Docker",
          "steps": ["1. Install package", "2. Start service", "3. Test with hello-world"],
          "learn_more": "Docker cheatsheet (opens in Docs tab)",
          "related": ["Docker Compose", "Port Management", "Volume Guide"]
      })

  **Progressive Disclosure**
  - Beginner: Outcome wizards (click and go)
  - Intermediate: Individual sections with docs
  - Advanced: Power installer, batch operations

  📊 **Success Metrics**

  **Phase 1 Complete When**
  - [x] Welcome Dashboard is default view (`WelcomeDashboardPage`, `welcome` in `_PAGE_REGISTRY`, default `last_page`)
  - [x] Servers overview on Welcome (embedded `WorkstationServersOverviewPanel` + wizards via `WorkstationSystemDashboardPanel`)
  - [x] Dedicated **System Monitor** page (`SystemMonitorPage`, `system` in `_PAGE_REGISTRY`, Ctrl+2)
  - [x] Outcome wizards + **Quick links** on Welcome (same `WorkstationSystemDashboardPanel`; jump row to System / Servers / Install / Widgets)
  - [ ] Sidebar matches full **new_plan** rail (dedicated top-level Servers/Services/… pages — deferred)

  **Phase 2 Complete When**
  - [x] No standalone "Learn" tab (`WorkstationLearnPanel` removed; cheatsheets relocated)
  - [x] Docker docs integrated in Servers Hub (**Docker Docs** tab → `DockerCheatsheetPage`; deep-link `servers:docs`)
  - [x] Bash + session on Welcome (collapsible); Neovim + Backend under **Install**; CLI under **Config → CLI**; FHS tree on **System Monitor**
  - [x] Contextual help baseline (dashboard **?** + power-mode confirm; per-widget hover optional)

  **Phase 3 Complete When**
  - [x] Outcome wizards contextual help (help icon + `Adw.MessageDialog` on dashboard)
  - [ ] Hover/click help everywhere *(other hubs — optional follow-up)*
  - [x] 6+ outcome profiles in `outcome_profiles.json` *(base 3 + Build Essentials + Git & Collaboration + Terminal essentials)*
  - [x] "Install Everything" power mode (`PowerInstaller.run_all_profiles` + confirm dialog + progress on `WorkstationSystemDashboardPanel`)
  - [ ] Zero redundant sections *(top-level rail refactor still open)*