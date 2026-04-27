#!/bin/sh
# Launcher for Flatpak: run the bundled Electron binary under Zypak (provided by Electron BaseApp).
exec zypak-wrapper /app/lib/linux-dev-home/linux-dev-home "$@"
