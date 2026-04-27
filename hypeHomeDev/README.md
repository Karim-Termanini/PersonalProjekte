# HypeDevHome 80% Vibe Coding

> **⚠️ Important Project Strategy Note – Cross-Distribution Compatibility**
>
> **This project is designed and built from the very beginning to the very end (from day one of development until the final release) based entirely on Flatpak + Docker.**
>
> **Main Goal:** The application must run **natively and cleanly on all Linux distributions** (Ubuntu, Fedora, Arch Linux, Debian, Linux Mint, Pop!\_OS, openSUSE, Manjaro, and more) **without any modifications or dependency on a specific distro's native packages**.
>
> **Why we are committing to this approach from the start:**
> - We want to completely avoid the common problem of *"it only works on Fedora"* (or any other single distribution).
> - Flatpak ensures a **universal, sandboxed, and consistent distribution** with all dependencies bundled inside the package.
> - Docker ensures a **100% identical development environment** for all developers, CI/CD pipelines, and testing.
>
> **This decision is non-negotiable** and must be respected in every folder, script, configuration, and technical decision moving forward.

---

![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)
![Python 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)
![GTK4](https://img.shields.io/badge/GTK-4-purple.svg)
![Libadwaita](https://img.shields.io/badge/Libadwaita-1.4-orange.svg)

**HypeDevHome** is a 100% open-source Linux version of Microsoft Dev Home, built completely from scratch using **Python + GTK4 + Libadwaita**. It provides developers with a beautiful, native Linux dashboard for system monitoring, GitHub integration, machine setup, and developer productivity tools.

> *"We are building for Linux as a whole… not for a single distribution."*

## ✨ Features

### 📊 Dashboard
A fully customizable dashboard with live widgets that update in real time. Add, remove, rearrange, and resize widgets using drag-and-drop — no coding required.

**System Widgets:**
- **CPU** — Usage per core, frequency, load average, temperature, live chart
- **GPU** — Utilization, VRAM, temperature, fan speed (NVIDIA, AMD, Intel auto-detection)
- **Memory** — RAM/Swap usage, live graph, warnings
- **Network** — Download/upload speeds, IP addresses, connection status, live graph
- **SSH Keychain** — Loaded SSH keys, status, management controls

**GitHub Widgets** (requires GitHub Personal Access Token):
- Issues, Pull Requests, Review Requested, Mentioned Me, Assigned to Me

### 🔧 Machine Configuration
One-click setup for a complete development environment:

- **Install Applications** — Curated dev tools via Flatpak + distro-specific fallbacks
- **Clone Repositories** — Paste URL → clone to `~/Dev/` → open in editor
- **Create Dev Folder** — `~/Dev` with performance optimizations (Btrfs subvolume, noatime)
- **Developer Settings** — Git config, shell aliases, environment variables, hidden files
- **Environments Support** — Dev Containers, Distrobox, Toolbx integration

### 🧩 Extensions
A fully extensible plugin system. The app ships with a built-in GitHub integration as the first extension, with room for community-contributed extensions.

### 🛠 Utilities
- **Hosts File Editor** — Safe GUI editor with backup/restore
- **Environment Variables Editor** — Manage user and system variables
- **Desktop Config Preview** — GNOME, KDE, Hyprland, Sway settings
- **Environments Manager** — Create and launch dev environments with one click

## 🚀 Quick Start

### Prerequisites
- **Docker** (for development environment)
- **Flatpak** (for running the application)
- **Git**

### Installation (Coming Soon)
Once published on Flathub:
```bash
flatpak install flathub com.github.hypedevhome
flatpak run com.github.hypedevhome
```

### Development Setup

**Option 1: One-command setup (Recommended)**
```bash
git clone https://github.com/hypedevhome/hypedevhome.git
cd hypedevhome
./scripts/dev-setup.sh
```

**Option 2: Manual Docker setup**
```bash
git clone https://github.com/hypedevhome/hypedevhome.git
cd hypedevhome
docker compose up -d dev
docker compose exec dev bash
```

**Option 3: Local development**
```bash
# Install dependencies (Fedora example)
sudo dnf install python3 python3-devel gtk4-devel libadwaita \
  gobject-introspection-devel gcc pkg-config

# Install Python dependencies
pip install -e .

# Run the application
python -m src.main
```

## 🧪 Development

### Running tests
```bash
pytest tests/ --cov=src --cov-report=term-missing
```

### Running linters
```bash
ruff check src/ tests/
ruff format src/ tests/
mypy src/
```

### Installing pre-commit hooks
```bash
pip install pre-commit
pre-commit install
```

### Running in Docker
```bash
docker compose up -d dev
docker compose exec dev python -m src.main
```

### Building the Flatpak
```bash
flatpak-builder --user --force-clean --install-deps-from=flathub builddir com.github.hypedevhome.yml
flatpak run com.github.hypedevhome
```

## 📁 Project Structure

See [projectStructur.md](projectStructur.md) for the complete directory layout and architecture documentation.

## 📖 Documentation

- [Contributing Guidelines](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)
- [Development Plan](development-plan.md)

## 🤝 Contributing

We welcome contributions! Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting a pull request. All contributions should follow the Flatpak-first approach outlined above.

## 📄 License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.
