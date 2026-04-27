import { readFileSync, statfsSync } from 'node:fs'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { execFile, spawn } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { cpus, freemem, homedir, loadavg, tmpdir, totalmem, uptime } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { app, BrowserWindow, dialog, ipcMain, nativeTheme, shell } from 'electron'
import Docker from 'dockerode'
import pty from 'node-pty'
import simpleGit from 'simple-git'

import {
  ComposeUpRequestSchema,
  DockerContainerActionSchema,
  DockerLogsRequestSchema,
  GitCloneRequestSchema,
  GitRecentAddSchema,
  GitStatusRequestSchema,
  HostExecRequestSchema,
  IPC,
  type ContainerRow,
  type DockerActionPayload,
  type GitRepoEntry,
  type HostMetrics,
  type HostMetricsResponse,
  type SystemdRow,
} from '@linux-dev-home/shared'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

nativeTheme.themeSource = 'dark'

let mainWindow: BrowserWindow | null = null
let docker: Docker | null = null
const terminals = new Map<string, pty.IPty>()
const SYSTEMD_UNITS = ['nginx', 'ssh', 'ufw', 'docker'] as const

let lastCpuIdle = 0
let lastCpuTotal = 0

function dockerSocketCandidates(): string[] {
  const run = process.env.XDG_RUNTIME_DIR
  return ['/var/run/docker.sock', ...(run ? [path.join(run, 'docker.sock')] : [])]
}

function getDocker(): Docker | null {
  if (docker) return docker
  for (const socketPath of dockerSocketCandidates()) {
    try {
      docker = new Docker({ socketPath })
      return docker
    } catch {
      /* next */
    }
  }
  return null
}

function profileComposeDir(profile: string): string {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'docker-profiles', 'compose', profile)
  }
  return path.resolve(app.getAppPath(), '..', '..', 'docker', 'compose', profile)
}

function recentReposPath(): string {
  return path.join(app.getPath('userData'), 'recent-repos.json')
}

async function loadRecentRepos(): Promise<GitRepoEntry[]> {
  try {
    const raw = await readFile(recentReposPath(), 'utf8')
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((x): x is GitRepoEntry => {
        return (
          x !== null &&
          typeof x === 'object' &&
          'path' in x &&
          typeof (x as GitRepoEntry).path === 'string' &&
          'lastOpened' in x &&
          typeof (x as GitRepoEntry).lastOpened === 'number'
        )
      })
      .sort((a, b) => b.lastOpened - a.lastOpened)
  } catch {
    return []
  }
}

async function saveRecentRepos(entries: GitRepoEntry[]): Promise<void> {
  await mkdir(app.getPath('userData'), { recursive: true })
  await writeFile(recentReposPath(), JSON.stringify(entries.slice(0, 20), null, 2))
}

function assertAllowedWritePath(target: string): string {
  const resolved = path.resolve(target)
  const home = homedir()
  const safe =
    resolved === home ||
    resolved.startsWith(home + path.sep) ||
    resolved.startsWith(tmpdir() + path.sep)
  if (!safe) {
    throw new Error('Path must resolve under your home directory or temp.')
  }
  return resolved
}

function sampleCpuUsage(): number {
  let idle = 0
  let tot = 0
  for (const c of cpus()) {
    idle += c.times.idle
    tot +=
      c.times.user +
      c.times.nice +
      c.times.sys +
      c.times.idle +
      c.times.irq +
      ('softirq' in c.times ? (c.times as { softirq: number }).softirq : 0)
  }
  const di = idle - lastCpuIdle
  const dt = tot - lastCpuTotal
  lastCpuIdle = idle
  lastCpuTotal = tot
  if (dt <= 0) return 0
  return Math.min(100, Math.max(0, Math.round(100 * (1 - di / dt))))
}

let netPrev: { t: number; rx: number; tx: number } | null = null

function readNetAgg(): { rx: number; tx: number } {
  try {
    const lines = readFileSync('/proc/net/dev', 'utf8').split('\n')
    let rx = 0
    let tx = 0
    for (const line of lines) {
      if (!line.includes(':')) continue
      const [iface, rest] = line.split(':')
      const name = iface.trim()
      if (name === 'lo') continue
      const parts = rest.trim().split(/\s+/).map(Number)
      if (parts.length < 9) continue
      rx += parts[0] ?? 0
      tx += parts[8] ?? 0
    }
    return { rx, tx }
  } catch {
    return { rx: 0, tx: 0 }
  }
}

function netMbps(): { rx: number; tx: number } {
  const cur = readNetAgg()
  const t = Date.now()
  if (!netPrev) {
    netPrev = { t, ...cur }
    return { rx: 0, tx: 0 }
  }
  const dt = (t - netPrev.t) / 1000
  if (dt <= 0.2) return { rx: 0, tx: 0 }
  const rxBytes = cur.rx - netPrev.rx
  const txBytes = cur.tx - netPrev.tx
  netPrev = { t, ...cur }
  const toMbps = (b: number) => Math.max(0, (b * 8) / (dt * 1_000_000))
  return { rx: toMbps(rxBytes), tx: toMbps(txBytes) }
}

async function systemdRow(unitBase: string): Promise<SystemdRow> {
  const name = `${unitBase}.service`
  return await new Promise((resolveRow) => {
    execFile('systemctl', ['is-active', name], { timeout: 2000 }, (err, stdout) => {
      const out = (stdout ?? '').trim()
      if (!err && out === 'active') {
        resolveRow({ name, state: 'active' })
        return
      }
      if (out === 'failed') {
        resolveRow({ name, state: 'failed' })
        return
      }
      if (out === 'inactive' || out === 'deactivated') {
        resolveRow({ name, state: 'inactive' })
        return
      }
      resolveRow({ name, state: 'unknown' })
    })
  })
}

async function collectMetrics(): Promise<HostMetricsResponse> {
  const freeMb = Math.round(freemem() / (1024 * 1024))
  const totalMb = Math.round(totalmem() / (1024 * 1024))
  let diskTotalGb = 0
  let diskFreeGb = 0
  try {
    const s = statfsSync('/')
    const bs = Number(s.bsize)
    diskTotalGb = Math.round(((s.blocks * bs) / 1024 ** 3) * 10) / 10
    diskFreeGb = Math.round(((s.bfree * bs) / 1024 ** 3) * 10) / 10
  } catch {
    /* sandbox */
  }
  const { rx, tx } = netMbps()
  const model = cpus()[0]?.model ?? 'CPU'
  const metrics: HostMetrics = {
    cpuUsagePercent: sampleCpuUsage(),
    cpuModel: model,
    loadAvg: loadavg(),
    totalMemMb: totalMb,
    freeMemMb: freeMb,
    uptimeSec: Math.round(uptime()),
    diskTotalGb,
    diskFreeGb,
    netRxMbps: rx,
    netTxMbps: tx,
  }
  const systemd = await Promise.all(SYSTEMD_UNITS.map((u) => systemdRow(u)))
  return { metrics, systemd }
}

function formatPorts(ports: Docker.Port[]): string {
  if (!ports?.length) return '—'
  return ports
    .map((p) => {
      const pub = p.PublicPort
      const priv = p.PrivatePort
      if (pub) return `${pub}:${priv}/${p.Type}`
      return `${priv}/${p.Type}`
    })
    .slice(0, 4)
    .join(', ')
}

async function listContainers(): Promise<
  { ok: true; rows: ContainerRow[] } | { ok: false; error: string }
> {
  const d = getDocker()
  if (!d) {
    return {
      ok: false,
      error:
        'Docker socket not available. See docs/DOCKER_FLATPAK.md for Flatpak permissions.',
    }
  }
  try {
    const list = await d.listContainers({ all: true })
    const rows: ContainerRow[] = list.map((c) => {
      const name = (c.Names?.[0] ?? '').replace(/^\//, '') || c.Id.slice(0, 8)
      return {
        id: c.Id,
        name,
        image: c.Image,
        state: c.State,
        status: c.Status,
        ports: formatPorts(c.Ports ?? []),
      }
    })
    return { ok: true, rows }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    return { ok: false, error: msg }
  }
}

function broadcast(channel: string, payload: unknown): void {
  mainWindow?.webContents.send(channel, payload)
}

function registerIpc(): void {
  ipcMain.handle(IPC.dockerList, async () => await listContainers())

  ipcMain.handle(IPC.dockerAction, async (_e, raw: unknown) => {
    const body = raw as DockerActionPayload
    const act = DockerContainerActionSchema.safeParse(body?.action)
    const id = typeof body?.id === 'string' ? body.id : ''
    if (!id || !act.success) throw new Error('Invalid docker action')
    const d = getDocker()
    if (!d) throw new Error('Docker unavailable')
    const container = d.getContainer(id)
    if (act.data === 'start') await container.start()
    else if (act.data === 'stop') await container.stop()
    else await container.restart()
    return { ok: true }
  })

  ipcMain.handle(IPC.dockerLogs, async (_e, raw: unknown) => {
    const req = DockerLogsRequestSchema.parse(raw)
    const d = getDocker()
    if (!d) throw new Error('Docker unavailable')
    const container = d.getContainer(req.id)
    const stream = await container.logs({
      stdout: true,
      stderr: true,
      tail: req.tail ?? 200,
      timestamps: false,
    })
    const buf = Buffer.isBuffer(stream) ? stream : Buffer.from(stream as ArrayBuffer)
    return buf.toString('utf8')
  })

  ipcMain.handle(IPC.metrics, async () => await collectMetrics())

  ipcMain.handle(IPC.hostExec, async (_e, raw: unknown) => {
    const req = HostExecRequestSchema.parse(raw)
    if (req.command === 'nvidia_smi_short') {
      return await new Promise<string>((res) => {
        execFile(
          'nvidia-smi',
          ['--query-gpu=name', '--format=csv,noheader'],
          { timeout: 5000 },
          (err, stdout) => {
            if (err) res('GPU: unavailable')
            else res(stdout.trim() || 'GPU')
          }
        )
      })
    }
    if (req.command === 'flatpak_spawn_echo') {
      return 'flatpak-spawn: configure host helper for sandboxed metrics'
    }
    if (req.command === 'systemctl_is_active' && req.unit) {
      const row = await systemdRow(req.unit.replace(/\.service$/, ''))
      return row.state
    }
    throw new Error('Unsupported host command')
  })

  ipcMain.handle(IPC.composeUp, async (_e, raw: unknown) => {
    const { profile } = ComposeUpRequestSchema.parse(raw)
    const dir = profileComposeDir(profile)
    return await new Promise<{ ok: boolean; log: string }>((resolveCompose) => {
      const child = spawn('docker', ['compose', 'up', '-d'], {
        cwd: dir,
        env: { ...process.env },
      })
      let log = ''
      child.stdout?.on('data', (d) => {
        log += d.toString()
      })
      child.stderr?.on('data', (d) => {
        log += d.toString()
      })
      child.on('error', (err) => {
        resolveCompose({ ok: false, log: String(err) })
      })
      child.on('close', (code) => {
        resolveCompose({ ok: code === 0, log: log || `exit ${code}` })
      })
    })
  })

  ipcMain.handle(IPC.composeLogs, async (_e, raw: unknown) => {
    const { profile } = ComposeUpRequestSchema.parse(raw)
    const dir = profileComposeDir(profile)
    return await new Promise<string>((res) => {
      execFile(
        'docker',
        ['compose', 'logs', '--no-color', '--tail', '80'],
        { cwd: dir, maxBuffer: 1024 * 1024 },
        (err, stdout) => {
          if (err) res(String(err))
          else res(stdout ?? '')
        }
      )
    })
  })

  ipcMain.handle(IPC.terminalCreate, (_e, payload: { cols: number; rows: number }) => {
    const { cols, rows } = payload
    const shellBin = process.env.SHELL || '/bin/bash'
    const id = randomUUID()
    try {
      const term = pty.spawn(shellBin, [], {
        name: 'xterm-color',
        cols: Math.max(2, cols),
        rows: Math.max(2, rows),
        cwd: homedir(),
        env: process.env as { [key: string]: string },
      })
      terminals.set(id, term)
      term.onData((data) => {
        broadcast(IPC.terminalData, { id, data })
      })
      term.onExit(() => {
        terminals.delete(id)
        broadcast(IPC.terminalExit, { id })
      })
      return { ok: true as const, id }
    } catch (e) {
      return { ok: false as const, error: e instanceof Error ? e.message : String(e) }
    }
  })

  ipcMain.on(IPC.terminalWrite, (_e, payload: { id: string; data: string }) => {
    terminals.get(payload.id)?.write(payload.data)
  })

  ipcMain.on(IPC.terminalResize, (_e, payload: { id: string; cols: number; rows: number }) => {
    terminals.get(payload.id)?.resize(payload.cols, payload.rows)
  })

  ipcMain.handle(IPC.openExternalTerminal, async () => {
    const trySpawn = (cmd: string, args: string[] = []) =>
      new Promise<boolean>((res) => {
        const child = spawn(cmd, args, { detached: true, stdio: 'ignore' })
        child.on('error', () => res(false))
        child.unref()
        res(true)
      })
    const order: [string, ...string[]][] = [
      ['xdg-terminal-emulator'],
      ['kitty'],
      ['alacritty'],
      ['gnome-terminal'],
      ['konsole'],
    ]
    for (const [cmd, ...rest] of order) {
      if (await trySpawn(cmd, [...rest])) return { ok: true }
    }
    return { ok: false }
  })

  ipcMain.handle(IPC.gitClone, async (_e, raw: unknown) => {
    const req = GitCloneRequestSchema.parse(raw)
    const dir = assertAllowedWritePath(req.targetDir)
    await simpleGit().clone(req.url, dir)
    const recent = await loadRecentRepos()
    const next: GitRepoEntry[] = [
      { path: dir, lastOpened: Date.now() },
      ...recent.filter((r) => r.path !== dir),
    ]
    await saveRecentRepos(next)
    return { ok: true }
  })

  ipcMain.handle(IPC.gitStatus, async (_e, raw: unknown) => {
    const req = GitStatusRequestSchema.parse(raw)
    const repoPath = assertAllowedWritePath(req.repoPath)
    const st = await simpleGit(repoPath).status()
    return {
      branch: st.current ?? 'unknown',
      tracking: st.tracking,
      ahead: st.ahead,
      behind: st.behind,
      modified: st.modified.length,
      created: st.created.length,
      deleted: st.deleted.length,
    }
  })

  ipcMain.handle(IPC.gitRecentList, async () => await loadRecentRepos())

  ipcMain.handle(IPC.gitRecentAdd, async (_e, raw: unknown) => {
    const req = GitRecentAddSchema.parse(raw)
    const repoPath = assertAllowedWritePath(req.path)
    const recent = await loadRecentRepos()
    const next = [{ path: repoPath, lastOpened: Date.now() }, ...recent.filter((r) => r.path !== repoPath)]
    await saveRecentRepos(next)
    return { ok: true }
  })

  ipcMain.handle(IPC.selectFolder, async () => {
    const r = await dialog.showOpenDialog(mainWindow!, { properties: ['openDirectory'] })
    if (r.canceled || !r.filePaths[0]) return null
    return r.filePaths[0]
  })

  ipcMain.handle('dh:openExternal', async (_e, url: string) => {
    if (typeof url === 'string' && /^https?:\/\//.test(url)) {
      await shell.openExternal(url)
      return { ok: true }
    }
    return { ok: false }
  })
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 960,
    minHeight: 640,
    show: false,
    title: 'Linux Dev Home',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.mjs'),
      contextIsolation: true,
      sandbox: false,
      nodeIntegration: false,
    },
  })
  mainWindow.on('closed', () => {
    mainWindow = null
  })
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  if (process.env.ELECTRON_RENDERER_URL) {
    void mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL)
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    void mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(() => {
  registerIpc()
  createWindow()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
