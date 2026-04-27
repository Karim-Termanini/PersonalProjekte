# Flatpak packaging

End-user distribution is intended to be **Flatpak-only**. Electron on Flathub typically uses `org.electronjs.Electron2.BaseApp` and a two-stage build (bundle your `asar`, ship launcher script).

The file `io.github.karimodora.LinuxDevHome.yml` in this directory is a **starting point**, not a drop-in Flathub submission:

- Replace placeholders with your verified app id.
- Wire `build-commands` to your real artifacts (`electron-vite build` output in `apps/desktop/out`).
- Add the Node SDK extension and any extra `finish-args` required for Docker (see `docs/DOCKER_FLATPAK.md`).

Use `docs/FLATHUB_CHECKLIST.md` before opening a Flathub PR.

Recommended local command once the manifest is complete:

```bash
flatpak-builder --user --install --force-clean ../flatpak-out io.github.karimodora.LinuxDevHome.yml
```

Run through `docs/INSTALL_TEST.md` after installing the bundle.
