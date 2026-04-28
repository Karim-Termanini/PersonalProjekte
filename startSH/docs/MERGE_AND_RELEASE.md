# After you push: merge and what’s next

Use this once your phase branch (for example `phase-0-foundations`) is pushed to `origin`.

## 1. Open the PR

- **Base:** `main`  
- **Compare:** your phase branch  
- Confirm CI is green on the latest commit.

## 2. Review checklist (quick)

- [ ] No secrets or tokens in the diff  
- [ ] `pnpm test`, `pnpm typecheck`, `pnpm lint`, and `pnpm build` pass locally if CI is noisy  
- [ ] Optional: `pnpm pack:linux` still produces `apps/desktop/pack-staging/release/linux-unpacked/`

## 3. Merge

Per [BRANCHING.md](BRANCHING.md): merge only after review and CI pass (squash or merge commit, as your team prefers). Do not rebase the phase branch for integration.

## 4. On `main` after merge

```bash
git checkout main
git pull origin main
# optional: delete local phase branch
git branch -d phase-0-foundations
```

## 5. Next work item (suggested order)

1. **Start the next phase from a fresh `main`:**  
   `git checkout main && git pull && git checkout -b phase-1-short-name`
2. **Flathub prep:** work through [FLATHUB_CHECKLIST.md](FLATHUB_CHECKLIST.md) — especially screenshots in AppStream and (when you target Flathub) offline/npm `generated-sources` instead of network builds.
3. **Releases:** tag versions that match `<release>` entries in `data/io.github.karimodora.LinuxDevHome.metainfo.xml`.

## 6. Installing your own Flatpak build (smoke test)

See [INSTALL_TEST.md](INSTALL_TEST.md) and [flatpak/README.md](../flatpak/README.md).
