"""Desktop session detection for Workstation Learn (no GTK imports)."""

from __future__ import annotations

import os

from core.setup.host_executor import HostExecutor


def session_is_hyprland(environ: dict[str, str] | None = None) -> bool:
    """Return True when the current environment looks like a Hyprland session."""
    env = os.environ if environ is None else environ
    if env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return True
    parts = (
        env.get("XDG_CURRENT_DESKTOP", ""),
        env.get("XDG_SESSION_DESKTOP", ""),
        env.get("WAYLAND_DISPLAY", ""),
    )
    return "hyprland" in " ".join(parts).lower()


def desktop_session_lines(environ: dict[str, str] | None = None) -> str:
    """Human-readable snapshot of variables that identify the desktop session."""
    env = os.environ if environ is None else environ
    keys = (
        "XDG_CURRENT_DESKTOP",
        "XDG_SESSION_DESKTOP",
        "DESKTOP_SESSION",
        "XDG_SESSION_TYPE",
        "WAYLAND_DISPLAY",
        "DISPLAY",
    )
    lines = []
    for key in keys:
        val = env.get(key)
        lines.append(f"{key}={val if val else '(unset)'}")
    return "\n".join(lines)


def neovim_user_config_hint() -> str:
    """Note whether user Neovim config exists on the HOST (read-only check).

    Flatpak sandbox may not see host ~/.config, so checks must run via HostExecutor.
    """
    executor = HostExecutor()

    # NOTE: use host-side $HOME expansion (HostExecutor will run via flatpak-spawn --host).

    init_lua_res = executor.run_sync(["sh", "-c", 'test -f "$HOME/.config/nvim/init.lua" && echo yes || echo no'])
    init_vim_res = executor.run_sync(["sh", "-c", 'test -f "$HOME/.config/nvim/init.vim" && echo yes || echo no'])

    found: list[str] = []
    if init_lua_res.success and init_lua_res.stdout.strip().lower() == "yes":
        found.append("$HOME/.config/nvim/init.lua")
    if init_vim_res.success and init_vim_res.stdout.strip().lower() == "yes":
        found.append("$HOME/.config/nvim/init.vim")

    if found:
        return "User config found on host (read-only check): " + "; ".join(found)
    return "No host ~/.config/nvim/init.lua or init.vim detected — cheatsheet shows defaults only."
