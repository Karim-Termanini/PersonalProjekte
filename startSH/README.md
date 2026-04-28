# Linux Dev Home (OSS)

100% open-source developer dashboard for Linux, inspired by Microsoft Dev Home and the VS Code visual language. **Install target: Flatpak.** **Dev/CI: Docker-friendly.**

## Features

- VS Code–style dark UI (Codicons, Inter + JetBrains Mono)
- Dashboard with Docker container overview and compose “profile” cards
- System metrics (CPU, memory, disk, network), sample systemd snapshot
- Git clone / recent repos with path validation in the main process
- Embedded terminal via `xterm.js` + `node-pty` with external-terminal fallback
- IPC surface guarded with Zod schemas in `@linux-dev-home/shared`

## Prerequisites

- Node **20+**
- **pnpm** 9 (`corepack enable` recommended)
- **Docker** (optional, for compose stacks and the Docker panel)
- Build toolchain for native addons: `build-essential`, `python3` (for `node-pty`)
- After install: rebuild native modules for your Electron version:
  ```bash
  cd apps/desktop && pnpm exec electron-rebuild -f -w node-pty
  ```

## Scripts

```bash
pnpm install
cd apps/desktop && pnpm exec electron-rebuild -f -w node-pty
pnpm dev          # electron-vite (main/preload bundle @linux-dev-home/shared from source)
pnpm test         # shared package unit tests (Zod)
pnpm typecheck
pnpm lint
pnpm build        # electron-vite build + copy compose profiles into out/
```

## Docker CI image

```bash
docker build -f docker/Dockerfile .
```

The image runs tests, typecheck, lint, and production build inside Node 20 (see `docker/Dockerfile`).

## Flatpak & Docker socket

See [docs/DOCKER_FLATPAK.md](docs/DOCKER_FLATPAK.md), [docs/INSTALL_TEST.md](docs/INSTALL_TEST.md), and [docs/FLATHUB_CHECKLIST.md](docs/FLATHUB_CHECKLIST.md).

## Branching

See [docs/BRANCHING.md](docs/BRANCHING.md).

## Monorepo layout

- `apps/desktop` — Electron + React UI
- `packages/shared` — shared types, IPC channel names, Zod schemas
- `docker/compose/*` — bundled `docker compose` profiles
- `flatpak/` — Flatpak manifest template + notes

## License

MIT — see [LICENSE](LICENSE).
