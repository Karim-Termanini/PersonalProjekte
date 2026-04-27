# 🍅 Pomodoro Timer Installer for Windows (WSL2)
# Run this in PowerShell or WSL2

Write-Host "🍅 Installing Pomodoro Timer..." -ForegroundColor Green

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$wslHome = "\\wsl$\Ubuntu\home\$env:USER"
$hyprDir = "$wslHome\.config\hypr\scripts"

# Check if running in WSL2
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    Write-Host "❌ WSL2 is required for this installer" -ForegroundColor Red
    exit 1
}

Write-Host "Installing pomodoro.sh to WSL2..."
wsl mkdir -p "$hyprDir"
wsl cp "$scriptDir/pomodoro.sh" "$hyprDir/pomodoro.sh"
wsl chmod +x "$hyprDir/pomodoro.sh"
Write-Host "✓ Installed to WSL2: $hyprDir/pomodoro.sh" -ForegroundColor Green

Write-Host ""
Write-Host "✅ Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Usage in WSL2:"
Write-Host "  • wsl ~/.config/hypr/scripts/pomodoro.sh status"
Write-Host "  • wsl ~/.config/hypr/scripts/pomodoro.sh toggle"
Write-Host ""
Write-Host "Note: This timer is designed for Linux/Wayland (Hyprland)."
Write-Host "      On Windows, you can run it inside WSL2."