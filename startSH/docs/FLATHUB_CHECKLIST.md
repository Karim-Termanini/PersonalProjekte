# Flathub submission checklist

Use this when you’re ready to publish on [Flathub](https://flathub.org). The app id used in-tree is **`io.github.karimodora.LinuxDevHome`** — change it everywhere (manifest, `.desktop`, metainfo, icon path) if you pick another id.

## Identity and legal

- [ ] **Application id** finalized (e.g. `io.github.<user>.LinuxDevHome`) and consistent across manifest, desktop, metainfo, and icon names.
- [ ] **Verified** developer/app URL or publisher expectations per [Flathub policies](https://docs.flathub.org/).
- [ ] No **Microsoft**, **VS Code**, or other **third-party trademarks** in name, summary, or icon (we use original assets under `data/icons/`).

## AppStream and desktop

- [ ] **Metainfo:** [`data/io.github.karimodora.LinuxDevHome.metainfo.xml`](../data/io.github.karimodora.LinuxDevHome.metainfo.xml) — summary, description, `<releases>` with accurate versions/dates.
- [ ] **Screenshots:** add at least one `<screenshot type="default">` with a real PNG (often stored in repo or CDN; Flathub docs show recommended sizes). Place assets under something like `data/metainfo/screenshots/` and reference HTTPS URLs after you host them or use Flathub’s asset flow.
- [ ] **OARS:** `content_rating` present (already `oars-1.1`).
- [ ] **Desktop file:** [`data/io.github.karimodora.LinuxDevHome.desktop`](../data/io.github.karimodora.LinuxDevHome.desktop) — `Exec`, `Icon`, `StartupWMClass` match the shipped app.

## Technical / build

- [ ] **Reproducible Flatpak build:** manifest builds with `flatpak-builder` (see [flatpak/README.md](../flatpak/README.md)).
- [ ] **Network during build:** Flathub often expects **offline** npm/pnpm installs. Plan to generate **`generated-sources.json`** with [flatpak-builder-tools](https://github.com/flatpak/flatpak-builder-tools) (Node/pnpm generator) and drop `--share=network` from the manifest for submission.
- [ ] **Electron BaseApp / runtime:** `base` / `runtime-version` / Node **SDK extension** branches pinned and match what Flathub ships (e.g. `24.08` today — bump when maintainers recommend).
- [ ] **Zypak launcher:** wrapper in [`packaging/linux-dev-home.sh`](../packaging/linux-dev-home.sh) tested inside the Flatpak.

## Permissions (`finish-args`)

- [ ] Every permission **documented** in the PR and in user-facing docs (see [DOCKER_FLATPAK.md](DOCKER_FLATPAK.md) for Docker socket).
- [ ] Use **narrow** filesystem and device access; add **talk-name** / portals only when required.

## QA before submission

- [ ] **Smoke-tested** on an **immutable** distro (e.g. Fedora Silverblue) and a traditional distro, **Flatpak only**.
- [ ] Docker panel, metrics, Git paths, and terminal fallbacks behave as documented under sandboxing.

## Submission mechanics

- [ ] Fork [flathub/flathub](https://github.com/flathub/flathub) or use the new submission workflow Flathub documents.
- [ ] Open a PR with the manifest + metainfo + desktop + screenshots; respond to **review bot** (`flathub.json`) and human review.

This repo’s current manifest is oriented to **local/CI network builds**; treat Flathub’s offline requirement as the main **next engineering step** after you’re happy with the app on `main`.
