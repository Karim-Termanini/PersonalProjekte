# How to Run HypeDevHome

This guide covers all the ways to run the application, from quick local testing to the full Docker development environment.

---

## 🚀 Quick Start (Recommended for Testing)

### Prerequisites

Before running the application, make sure you have these dependencies installed on your Linux system:

**For Fedora:**
```bash
sudo dnf install python3 python3-devel python3-gobject gtk4 libadwaita \
  gobject-introspection-devel gcc pkg-config python3-psutil
```

**For Ubuntu/Debian:**
```bash
sudo apt install python3 python3-dev python3-gi python3-gi-cairo \
  gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-girepository-2.0 gcc pkg-config \
  python3-psutil
```

**For Arch Linux:**
```bash
sudo pacman -S python python-gobject gtk4 libadwaita gobject-introspection \
  gcc pkg-config python-psutil
```

---

## 📦 Method 1: Run Locally (Fastest)

This is the quickest way to see the application in action:

```bash
# 1. Clone the repository (if you haven't already)
git clone https://github.com/Karim-Termanini/hypeHomeDev.git
cd hypeHomeDev

# 2. Install Python dependencies
pip install -e .

# 3. Run the application
python -m src.main
```

**Expected output:**
```
(main.py:XXXXX): Gtk-WARNING **: Theme parser error: gtk.css...  ← Safe to ignore (GTK theme warnings)
MESA-INTEL: warning...                                           ← Safe to ignore (GPU drivers)
```

The application window should appear with:
- ✅ Main dashboard with sidebar navigation
- ✅ System monitoring widgets (CPU, GPU, Memory, Network, SSH)
- ✅ GitHub integration widgets (requires token configuration)
- ✅ Settings dialog (accessible via hamburger menu)
- ✅ Beautiful Libadwaita dark/light theme support

### Running with Debug Logging

To see detailed logs in the terminal:

```bash
python -m src.main --debug
```

This will show:
- Configuration loading
- Widget initialization
- Event bus activity
- Error messages with full stack traces

---

## 🐳 Method 2: Run in Docker (Consistent Environment)

Docker provides an identical development environment for everyone, regardless of your Linux distribution.

### Step 1: Build and Start the Container

```bash
# Build and start the development container
docker compose up -d dev
```

### Step 2: Run the Application Inside the Container

**Option A: Run directly from your host terminal:**
```bash
docker compose exec dev python -m src.main
```

**Option B: Enter the container and run interactively:**
```bash
# Enter the container
docker compose exec dev bash

# Inside the container, run the app
python -m src.main
```

### Notes for Docker Users:

- **X11 Display:** The container automatically connects to your X11 display via `/tmp/.X11-unix`
- **Wayland Display:** If you're using Wayland, ensure `$WAYLAND_DISPLAY` is set
- **SSH Agent:** Your SSH agent socket is forwarded into the container automatically
- **Live Development:** Changes you make on your host are immediately reflected inside the container (thanks to volume mounting)

---

## 🛠 Method 3: Using the Dev Setup Script

If you have a `dev-setup.sh` script:

```bash
./scripts/dev-setup.sh
```

This will:
1. Check system dependencies
2. Install Python packages
3. Set up the environment
4. Launch the application

---

## 🧪 Running Tests

To verify everything is working correctly:

```bash
# Run the full test suite
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing

# Run only GitHub widget tests
python -m pytest tests/test_ui/test_github_widgets.py tests/test_ui/test_github_auth.py -v
```

**Expected result:** 127+ tests passing ✅

---

## 🔧 Common Issues & Solutions

### Issue: "No module named 'gi'"

**Solution:** Install PyGObject and its dependencies:
```bash
sudo dnf install python3-gobject gtk4-devel libadwaita-devel
pip install PyGObject
```

### Issue: "Gtk-WARNING: cannot open display"

**Solution for X11:**
```bash
export DISPLAY=:0
```

**Solution for Wayland:**
```bash
export WAYLAND_DISPLAY=wayland-0
export XDG_RUNTIME_DIR=/run/user/1000
```

### Issue: "ModuleNotFoundError: No module named 'core'" (or 'config', 'ui')

**Solution:** The application uses a "src layout". While `src/main.py` now includes an automated path-injection bootstrap, you can manually fix this by adding the `src/` directory to your `PYTHONPATH`:

```bash
export PYTHONPATH=$(pwd)/src
python -m main
```

Or install in development mode (recommended):
```bash
pip install -e .
```


### Issue: Application starts but widgets show "Not configured"

**Solution:** This is expected for GitHub widgets. You need to:
1. Open the hamburger menu (top-right)
2. Select **Settings**
3. Go to the **GitHub** section
4. Click **Configure** and enter your GitHub Personal Access Token (PAT)

System widgets (CPU, Memory, etc.) should work immediately.

---

## 🎨 Using the Application

### Navigation

The sidebar lists the main sections (order may evolve):

| Icon | Section | Description |
|------|---------|-------------|
| 🏠 | **Welcome** | Default entry: outcome wizards (incl. power mode + help), quick links, terminal/session reference, live servers overview |
| 📡 | **System Monitor** | Dedicated live view: host load, containers table, LAN neighbors (same engine as Servers → Overview) |
| 🧰 | **Tools** | Full hub: Apps, Servers, Services, AI, Config (incl. CLI ref), Install (incl. Neovim/Backend tips), Remove |
| 📊 | **Widgets** | Customizable grid: CPU, memory, GitHub, and other live widgets |
| ⚙️ | **Machine Setup** | Development environment configuration wizard |
| 🛡 | **Maintenance Hub** | Pulse health, Guardian snapshots, tasks |
| 🧩 | **Extensions** | Plugin management |
| 🛠 | **Utilities** | Hosts editor, environment variables, etc. |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+1` | Switch to Welcome |
| `Ctrl+2` | Switch to System Monitor |
| `Ctrl+3` | Switch to Tools |
| `Ctrl+4` | Switch to Widgets |
| `Ctrl+5` | Switch to Machine Setup |
| `Ctrl+6` | Switch to Maintenance Hub |
| `Ctrl+7` | Switch to Extensions |
| `Ctrl+8` | Switch to Utilities |
| `Ctrl+,` | Open Settings |
| `F11` | Toggle fullscreen |
| `Ctrl+Q` | Quit application |

### Adding GitHub Widgets

1. **Get a GitHub Personal Access Token (PAT):**
   - Go to [GitHub Settings → Developer Settings](https://github.com/settings/tokens)
   - Generate a new classic token
   - Required scopes: `repo`, `read:user`, `read:org`

2. **Configure the token in the app:**
   - Open Settings (hamburger menu → Settings)
   - Go to the **GitHub** tab
   - Click **Configure**
   - Paste your token and click **Save**

3. **Add widgets to your dashboard:**
   - Open the **Widgets** page (`Ctrl+4`)
   - Open the widget gallery (click the `+` button)
   - Browse available GitHub widgets
   - Click to add them to your dashboard

4. **Widgets will auto-refresh every 30 seconds** with live data from GitHub!

---

## 📸 What You'll See

### Widgets page (grid)
```
┌──────────────────────────────────────────────┐
│ ☰  HypeDevHome                    [⚙️] [─][□][✕]│
├─────────┬────────────────────────────────────┤
│ 🏠 Welc │  ┌────────────┐  ┌──────────────┐ │
│ 📡 Sys  │  │  CPU  42%  │  │ GitHub Issues│ │
│ 🧰 Tool │  │  2.4 GHz   │  │ #42 Fix bug  │ │
│ 📊 Widg │  │  Load: ... │  │ #38 Dark mode│ │
│ ⚙️ Mach │  └────────────┘  └──────────────┘ │
│ 🧩 Exte │  ┌────────────┐  ┌──────────────┐ │
│ 🛠 Util │  │ Memory 68% │  │Pull Requests │ │
│         │  │ 8GB / 16GB │  │ #156 Ready   │ │
│         │  │ Swap: 12%  │  │ #154 Draft   │ │
│         │  └────────────┘  └──────────────┘ │
└─────────┴────────────────────────────────────┘
```
*(Welcome is the default rail item; illustration shows the Widgets grid layout.)*

### Settings Dialog
```
┌──────────────────────────────────────────┐
│ Settings                          [✕]    │
├──────────────────────────────────────────┤
│ [Appearance] [Behavior] [Widgets] [GitHub] │
│                                          │
│ 🔐 Authentication                        │
│ GitHub Token         [Configure]         │
│ Token Permissions                        │
│                                          │
│ 📺 Display                               │
│ ☑ Issues            Show open issues    │
│ ☑ Pull Requests     Show open PRs       │
│ ☑ Review Requested  Show pending reviews │
│ ☑ Mentioned Me      Show mentions       │
│ ☑ Assigned to Me    Show assignments    │
│                                          │
│ 🔄 Refresh                               │
│ Refresh Interval:  [30 ▼] seconds        │
└──────────────────────────────────────────┘
```

---

## 🚀 Next Steps

Once you've run the application and explored the UI:

1. **Run the tests** to ensure everything is working: `python -m pytest tests/ -v`
2. **Check the code quality**: `ruff check src/ tests/`
3. **Explore the Phase 3 features**:
   - GitHub authentication
   - 5 GitHub widgets with real-time updates
   - Widget gallery
   - Settings integration
4. **Start Phase 4 development** (Machine Configuration Setup)

---

## 📚 Additional Resources

- [Phase 3 Completion Report](PHASE_3_AGENT_C_REPORT.md) - GitHub integration details
- [Development Plan](development-plan.md) - Complete roadmap
- [Project Structure](projectStructur.md) - Architecture overview
- [Contributing Guide](CONTRIBUTING.md) - How to contribute

---

**Happy coding! 🎉**
