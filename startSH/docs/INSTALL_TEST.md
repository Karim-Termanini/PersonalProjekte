# Install test (Flatpak)

Build and install from the **repository root**:

```bash
flatpak-builder --user --install --force-clean flatpak-build-dir \
  flatpak/io.github.karimodora.LinuxDevHome.yml \
  --install-deps-from=flathub
```

Run:

```bash
flatpak run io.github.karimodora.LinuxDevHome
```

Smoke checklist:

1. App launches under Wayland (fallback X11) or X11.
2. Dashboard renders and host metrics update (or degrade gracefully if `/proc` is limited).
3. Docker panel shows a clear error if the socket is missing until overrides are applied.
4. Embedded terminal falls back when `node-pty` cannot start inside the sandbox.
5. Git clone refuses paths outside the home/temp allowlist.

See [DOCKER_FLATPAK.md](DOCKER_FLATPAK.md) for socket overrides.

## Install test (unpackaged binary)

After `pnpm pack:linux`, run:

```bash
./apps/desktop/pack-staging/release/linux-unpacked/linux-dev-home
```

Confirm compose profiles exist under `resources/docker-profiles/compose/` inside `resources/` (electron-builder `extraResources`).
