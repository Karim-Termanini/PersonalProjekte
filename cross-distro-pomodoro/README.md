# 🍅 Cross-Distro Pomodoro Timer for Waybar

A portable, cross-distro Pomodoro timer that integrates with [Waybar](https://github.com/Alexays/Waybar) and [Hyprland](https://hyprland.org/).

Works on **any Linux distro** with just `bash`, `coreutils`, and `notify-send`.

## Features

- ⏱️ 25-minute work sessions
- ☕ 5-minute breaks
- 🌴 15-minute long breaks (after 4 sessions)
- 🔔 Desktop notifications for phase transitions
- 🎨 Color-coded states in Waybar
- ⏯️ Start/Pause/Resume/Reset functionality
- ⌨️ Keyboard shortcuts (Hyprland)

## Installation

### Prerequisites

Ensure you have the following installed:
- **bash** (v4.0+)
- **coreutils** (for `date`, `sleep`, etc.)
- **libnotify** / **notify-send** (for desktop notifications)
- **jq** (optional, for enhanced JSON handling)
- **Waybar** (for status bar integration)
- **Hyprland** (optional, for keybindings)

Most of these are pre-installed on modern Linux distributions.

### Distro-Specific Setup

#### Debian / Ubuntu / Linux Mint

```bash
# Install dependencies
sudo apt update
sudo apt install bash coreutils libnotify-bin jq

# Create config directory and install script
mkdir -p ~/.config/hypr/scripts
cp pomodoro.sh ~/.config/hypr/scripts/pomodoro.sh
chmod +x ~/.config/hypr/scripts/pomodoro.sh
```

#### Fedora

```bash
# Install dependencies
sudo dnf install bash coreutils libnotify jq

# Create config directory and install script
mkdir -p ~/.config/hypr/scripts
cp pomodoro.sh ~/.config/hypr/scripts/pomodoro.sh
chmod +x ~/.config/hypr/scripts/pomodoro.sh
```

#### Arch Linux / Manjaro / EndeavourOS

```bash
# Install dependencies
sudo pacman -S bash coreutils libnotify jq

# Create config directory and install script
mkdir -p ~/.config/hypr/scripts
cp pomodoro.sh ~/.config/hypr/scripts/pomodoro.sh
chmod +x ~/.config/hypr/scripts/pomodoro.sh
```

#### openSUSE (Tumbleweed / Leap)

```bash
# Install dependencies
sudo zypper install bash coreutils libnotify-tools jq

# Create config directory and install script
mkdir -p ~/.config/hypr/scripts
cp pomodoro.sh ~/.config/hypr/scripts/pomodoro.sh
chmod +x ~/.config/hypr/scripts/pomodoro.sh
```

#### Cosmic (Pop!_OS with COSMIC Desktop)

```bash
# Install dependencies
sudo apt update
sudo apt install bash coreutils libnotify-bin jq

# Create config directory and install script
mkdir -p ~/.config/cosmic/scripts
cp pomodoro.sh ~/.config/cosmic/scripts/pomodoro.sh
chmod +x ~/.config/cosmic/scripts/pomodoro.sh
```

> **Note:** On COSMIC, you may need to adapt the Waybar panel config path accordingly.

#### NixOS

```nix
# Add to your configuration.nix
environment.systemPackages = with pkgs; [
  bash
  coreutils
  libnotify
  jq
];
```

Then rebuild your system:
```bash
sudo nixos-rebuild switch
```

Install the script:
```bash
mkdir -p ~/.config/hypr/scripts
cp pomodoro.sh ~/.config/hypr/scripts/pomodoro.sh
chmod +x ~/.config/hypr/scripts/pomodoro.sh
```

#### Alpine Linux

```bash
# Install dependencies
sudo apk add bash coreutils libnotify jq

# Create config directory and install script
mkdir -p ~/.config/hypr/scripts
cp pomodoro.sh ~/.config/hypr/scripts/pomodoro.sh
chmod +x ~/.config/hypr/scripts/pomodoro.sh
```

#### Void Linux

```bash
# Install dependencies
sudo xbps-install -S bash coreutils libnotify jq

# Create config directory and install script
mkdir -p ~/.config/hypr/scripts
cp pomodoro.sh ~/.config/hypr/scripts/pomodoro.sh
chmod +x ~/.config/hypr/scripts/pomodoro.sh
```

#### Gentoo

```bash
# Install dependencies
sudo emerge --ask app-misc/jq xfce-base/libnotify

# Create config directory and install script
mkdir -p ~/.config/hypr/scripts
cp pomodoro.sh ~/.config/hypr/scripts/pomodoro.sh
chmod +x ~/.config/hypr/scripts/pomodoro.sh
```

---

### Configure Waybar Module

Add the module definition to your Waybar config (usually `~/.config/waybar/config.jsonc` or an included file):

```json
"custom/pomodoro": {
    "format": "{}",
    "return-type": "json",
    "interval": 1,
    "exec": "$HOME/.config/hypr/scripts/pomodoro.sh status",
    "on-click": "$HOME/.config/hypr/scripts/pomodoro.sh toggle",
    "on-click-right": "$HOME/.config/hypr/scripts/pomodoro.sh reset",
    "on-click-middle": "$HOME/.config/hypr/scripts/pomodoro.sh start",
    "tooltip": true
}
```

Then add `"custom/pomodoro"` to your `modules-left`, `modules-center`, or `modules-right` array.

### Add CSS Styling

Append the styles from `waybar/style.css` to your Waybar theme file (usually `~/.config/waybar/style.css`):

```bash
cat waybar/style.css >> ~/.config/waybar/style.css
```

### Add Keybindings (Hyprland)

Source the keybindings file in your `hyprland.conf` (`~/.config/hypr/hyprland.conf`):

```ini
source = ~/.config/hypr/UserConfigs/pomodoro-keybinds.conf
```

Or copy the bindings from `hyprland/keybindings.conf` directly into your config:

```bash
cp hyprland/keybindings.conf ~/.config/hypr/UserConfigs/pomodoro-keybinds.conf
```

### Restart Waybar

```bash
pkill waybar && waybar &
```

Or on some distros:
```bash
waybar --reload &
```

## Usage

### Waybar Interaction

| Action | Result |
|--------|--------|
| Left-click | Toggle (Start/Pause) |
| Right-click | Reset |
| Middle-click | Force Start |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `SUPER + ALT + P` | Toggle (Start/Pause) |
| `SUPER + ALT + R` | Reset |

### CLI Commands

```bash
pomodoro.sh start     # Start/resume timer
pomodoro.sh pause     # Pause timer
pomodoro.sh toggle    # Toggle start/pause
pomodoro.sh reset     # Reset timer
pomodoro.sh status    # Output Waybar JSON format
```

## Configuration

Override default durations via environment variables:

```bash
export POMO_WORK=1800      # 30 min work
export POMO_BREAK=600      # 10 min break
export POMO_LONG_BREAK=1200 # 20 min long break
export POMO_SESSIONS=3     # Long break after 3 sessions
```

## Color Coding

| State | Color | Meaning |
|-------|-------|---------|
| 🍅 Idle | Default | Ready to start |
| 🔴 Work | Red | Focus session active |
| 🟢 Break | Green | Short break |
| 🔵 Long Break | Blue | Extended break |
| 🟡 Paused | Yellow | Timer paused |

## License

MIT
