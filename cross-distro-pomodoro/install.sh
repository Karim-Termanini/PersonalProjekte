#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────
# 🍅 Pomodoro Timer Installer
# ───────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POMO_SOURCE="$SCRIPT_DIR/pomodoro.sh"
HYPR_DIR="$HOME/.config/hypr/scripts"
WAYBAR_DIR="$HOME/.config/waybar"
HYPR_CONFIG_DIR="$HOME/.config/hypr/UserConfigs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🍅 Installing Pomodoro Timer...${NC}"

# ── Install main script ──
echo "Installing pomodoro.sh..."
mkdir -p "$HYPR_DIR"
cp "$POMO_SOURCE" "$HYPR_DIR/pomodoro.sh"
chmod +x "$HYPR_DIR/pomodoro.sh"
echo -e "${GREEN}✓${NC} Installed to $HYPR_DIR/pomodoro.sh"

# ── Install Hyprland keybindings ──
echo "Installing Hyprland keybindings..."
mkdir -p "$HYPR_CONFIG_DIR"
cp "$SCRIPT_DIR/hyprland/keybindings.conf" "$HYPR_CONFIG_DIR/pomodoro-keybinds.conf"

# Add source line to main Hyprland config if not present
HYPR_CONF="$HOME/.config/hypr/hyprland.conf"
if [[ -f "$HYPR_CONF" ]]; then
    if ! grep -q "pomodoro-keybinds.conf" "$HYPR_CONF" 2>/dev/null; then
        echo "" >> "$HYPR_CONF"
        echo "# Pomodoro Timer" >> "$HYPR_CONF"
        echo "source = $HYPR_CONFIG_DIR/pomodoro-keybinds.conf" >> "$HYPR_CONF"
        echo -e "${GREEN}✓${NC} Added keybindings to Hyprland config"
    else
        echo -e "${YELLOW}✓${NC} Keybindings already in Hyprland config"
    fi
else
    echo -e "${YELLOW}⚠${NC} Hyprland config not found, skipping keybindings"
fi

# ── Install Waybar config ──
echo "Installing Waybar module..."
mkdir -p "$WAYBAR_DIR"
cp "$SCRIPT_DIR/waybar/module.json" "$WAYBAR_bar/config"

# Add CSS to existing waybar style if available
WAYBAR_CSS="$HOME/.config/waybar/style.css"
if [[ -f "$WAYBAR_CSS" ]]; then
    if ! grep -q "#custom-pomodoro" "$WAYBAR_CSS" 2>/dev/null; then
        echo "" >> "$WAYBAR_CSS"
        echo "/* Pomodoro Timer */" >> "$WAYBAR_CSS"
        cat "$SCRIPT_DIR/waybar/style.css" >> "$WAYBAR_CSS"
        echo -e "${GREEN}✓${NC} Added styles to Waybar"
    else
        echo -e "${YELLOW}✓${NC} Styles already in Waybar config"
    fi
else
    cp "$SCRIPT_DIR/waybar/style.css" "$WAYBAR_DIR/style.css"
    echo -e "${GREEN}✓${NC} Created Waybar style file"
fi

echo ""
echo -e "${GREEN}✅ Installation complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Restart Waybar: killall waybar && waybar &"
echo "  2. Restart Hyprland: hyprctl reload"
echo ""
echo "Usage:"
echo "  • Click on pomodoro in Waybar to start/pause"
echo "  • $mainMod+Alt+P to toggle (Hyprland)"
echo "  • $mainMod+Alt+R to reset (Hyprland)"