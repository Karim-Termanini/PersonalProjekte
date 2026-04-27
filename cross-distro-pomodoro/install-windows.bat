@echo off
REM 🍅 Pomodoro Timer Installer for Windows (WSL2)
REM Run this in Command Prompt or PowerShell

echo 🍅 Installing Pomodoro Timer...

REM Check if WSL2 is available
where wsl.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ WSL2 is required for this installer
    exit /b 1
)

set "scriptDir=%~dp0"
set "wslHome=\\wsl$\Ubuntu\home\%USERNAME%"
set "hyprDir=%wslHome%\.config\hypr\scripts"

echo Installing pomodoro.sh to WSL2...
wsl mkdir -p "%hyprDir%"
wsl cp "%scriptDir%pomodoro.sh" "%hyprDir%pomodoro.sh"
wsl chmod +x "%hyprDir%pomodoro.sh"
echo ✓ Installed to WSL2: %hyprDir%pomodoro.sh

echo.
echo ✅ Installation complete!
echo.
echo Usage in WSL2:
echo   • wsl ~/.config/hypr/scripts/pomodoro.sh status
echo   • wsl ~/.config/hypr/scripts/pomodoro.sh toggle
echo.
echo Note: This timer is designed for Linux/Wayland.
echo       On Windows, run it inside WSL2.

pause