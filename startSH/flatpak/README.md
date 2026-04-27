# Flatpak packaging

The manifest [`io.github.karimodora.LinuxDevHome.yml`](io.github.karimodora.LinuxDevHome.yml) builds the app **inside** the Flatpak sandbox (Node 20 SDK, network for `pnpm install`, then `pnpm --filter desktop pack:linux`). It ships the **electron-builder** `linux-unpacked` bundle and a **Zypak** launcher from Electron BaseApp.

Prerequisites: `flatpak`, `flatpak-builder`, and Flathub remote for runtimes/BaseApp.

From the **repository root** (`startSH/`):

```bash
flatpak-builder --user --install --force-clean flatpak-build-dir \
  flatpak/io.github.karimodora.LinuxDevHome.yml \
  --install-deps-from=flathub
```

Run the app:

```bash
flatpak run io.github.karimodora.LinuxDevHome
```

Flathub submission still needs offline/npm-generated sources or policy review for `--share=network` builds; see [`docs/FLATHUB_CHECKLIST.md`](../docs/FLATHUB_CHECKLIST.md).

For Docker socket access after install, see [`docs/DOCKER_FLATPAK.md`](../docs/DOCKER_FLATPAK.md).
