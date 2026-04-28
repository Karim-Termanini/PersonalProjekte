import type { ContainerRow, ImageRow, NetworkRow, VolumeRow } from '@linux-dev-home/shared'
import type { ReactElement } from 'react'
import { useCallback, useEffect, useState } from 'react'

import { DockerSchemeView } from '../components/DockerSchemeView'

type TabId = 'scheme' | 'create' | 'containers' | 'images' | 'volumes' | 'networks' | 'ports'

type CreateExample = {
  title: string
  image: string
  command?: string
  ports?: string
  volumes?: string
  env?: string
}

const CREATE_EXAMPLES: CreateExample[] = [
  { title: 'Nginx web server', image: 'nginx:latest', ports: '8080:80', volumes: './:/usr/share/nginx/html' },
  { title: 'PostgreSQL database', image: 'postgres:16', ports: '5432:5432', env: 'POSTGRES_PASSWORD=postgres\nPOSTGRES_DB=app' },
  { title: 'Redis cache', image: 'redis:7-alpine', ports: '6379:6379' },
  { title: 'MySQL database', image: 'mysql:8', ports: '3306:3306', env: 'MYSQL_ROOT_PASSWORD=root\nMYSQL_DATABASE=app' },
  { title: 'MongoDB', image: 'mongo:7', ports: '27017:27017', env: 'MONGO_INITDB_ROOT_USERNAME=admin\nMONGO_INITDB_ROOT_PASSWORD=admin' },
  { title: 'Ubuntu shell (interactive)', image: 'ubuntu:24.04', command: 'bash' },
  {
    title: 'Python dev container',
    image: 'python:3.12-slim',
    ports: '8000:8000',
    volumes: './:/app',
    env: 'PYTHONDONTWRITEBYTECODE=1',
  },
  {
    title: 'Node.js app',
    image: 'node:20-alpine',
    ports: '3000:3000',
    volumes: './:/app',
    env: 'NODE_ENV=development',
  },
]

const RECOMMENDED_IMAGES = [
  { name: 'nginx', tag: 'latest', description: 'Official build of Nginx.', color: '#009639' },
  { name: 'redis', tag: 'alpine', description: 'Redis is an open source key-value store.', color: '#dc382d' },
  { name: 'postgres', tag: '16', description: 'The World\'s Most Advanced Open Source Relational Database', color: '#336791' },
  { name: 'node', tag: '20-alpine', description: 'Node.js is a JavaScript-based platform for server-side and networking applications.', color: '#339933' },
  { name: 'python', tag: '3.12-slim', description: 'Python is an interpreted, interactive, object-oriented, open-source programming language.', color: '#3776ab' },
  { name: 'mongo', tag: '7', description: 'MongoDB document databases provide high availability and easy scalability.', color: '#47A248' },
]

export function DockerPage(): ReactElement {
  const [tab, setTab] = useState<TabId>('scheme')
  const [docker, setDocker] = useState<
    { ok: true; rows: ContainerRow[] } | { ok: false; error: string } | null
  >(null)
  const [images, setImages] = useState<ImageRow[]>([])
  const [volumes, setVolumes] = useState<VolumeRow[]>([])
  const [networks, setNetworks] = useState<NetworkRow[]>([])
  const [err, setErr] = useState<string>('')
  const [selected, setSelected] = useState<ContainerRow | null>(null)
  const [logText, setLogText] = useState<string>('')
  const [pruneInfo, setPruneInfo] = useState<string>('')
  const [busy, setBusy] = useState(false)
  const [createdInfo, setCreatedInfo] = useState<string>('')
  const [customNames, setCustomNames] = useState<Record<string, string>>({})
  const [pullImage, setPullImage] = useState('')
  const [customImage, setCustomImage] = useState('nginx:latest')
  const [customName, setCustomName] = useState('')
  const [customPortsText, setCustomPortsText] = useState('8080:80')
  const [customVolumesText, setCustomVolumesText] = useState('')
  const [customEnvText, setCustomEnvText] = useState('')
  const [autoStart, setAutoStart] = useState(true)
  const [remapContainerId, setRemapContainerId] = useState('')
  const [oldHostPort, setOldHostPort] = useState('')
  const [newHostPort, setNewHostPort] = useState('')
  const [createVolumeName, setCreateVolumeName] = useState('')
  const [createNetworkName, setCreateNetworkName] = useState('')

  const refreshAll = useCallback(async () => {
    try {
      setErr('')
      const d = (await window.dh.dockerList()) as
        | { ok: true; rows: ContainerRow[] }
        | { ok: false; error: string }
      setDocker(d)
      if (!d.ok) {
        setImages([])
        setVolumes([])
        setNetworks([])
        return
      }
      const img = (await window.dh.dockerImagesList()) as { ok: true; rows: ImageRow[] }
      const vol = (await window.dh.dockerVolumesList()) as { ok: true; rows: VolumeRow[] }
      const net = (await window.dh.dockerNetworksList()) as { ok: true; rows: NetworkRow[] }
      setImages(img.rows)
      setVolumes(vol.rows)
      setNetworks(net.rows)
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      setDocker({ ok: false, error: message })
      setErr(message)
    }
  }, [])

  useEffect(() => {
    void refreshAll()
    const id = setInterval(() => void refreshAll(), 5000)
    return () => clearInterval(id)
  }, [refreshAll])

  async function runAction(id: string, action: 'start' | 'stop' | 'restart' | 'remove'): Promise<void> {
    if (action === 'remove') {
      const yes = window.confirm('Remove this stopped container? This cannot be undone.')
      if (!yes) return
    }
    setBusy(true)
    try {
      await window.dh.dockerAction({ id, action })
      await refreshAll()
    } finally {
      setBusy(false)
    }
  }

  async function openLogs(row: ContainerRow): Promise<void> {
    setSelected(row)
    setLogText('Loading logs…')
    const text = (await window.dh.dockerLogs({ id: row.id, tail: 200 })) as string
    setLogText(text || 'No logs')
  }

  async function removeImage(id: string): Promise<void> {
    setBusy(true)
    try {
      await window.dh.dockerImageAction({ id, action: 'remove' })
      await refreshAll()
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      const canForce = /must be forced|being used by stopped container|conflict/i.test(message)
      if (canForce) {
        const yes = window.confirm(
          'This image is referenced by stopped containers. Force remove it anyway?'
        )
        if (yes) {
          try {
            await window.dh.dockerImageAction({ id, action: 'remove', force: true })
            await refreshAll()
            setErr('')
          } catch (forceErr) {
            setErr(forceErr instanceof Error ? forceErr.message : String(forceErr))
          }
        } else {
          setErr('Image removal cancelled.')
        }
      } else {
        setErr(message)
      }
    } finally {
      setBusy(false)
    }
  }

  async function removeVolume(name: string): Promise<void> {
    setBusy(true)
    try {
      await window.dh.dockerVolumeAction({ name, action: 'remove' })
      await refreshAll()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function removeNetwork(id: string): Promise<void> {
    setBusy(true)
    try {
      await window.dh.dockerNetworkAction({ id, action: 'remove' })
      await refreshAll()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function runPrune(): Promise<void> {
    setBusy(true)
    try {
      const res = (await window.dh.dockerPrune()) as { ok: true; reclaimedBytes: number }
      const mb = Math.round((res.reclaimedBytes / (1024 * 1024)) * 10) / 10
      setPruneInfo(`Cleanup finished. Reclaimed ~${mb} MB.`)
      await refreshAll()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function createCustomVolume(): Promise<void> {
    if (!createVolumeName.trim()) return
    setBusy(true)
    setErr('')
    setCreatedInfo('')
    try {
      await window.dh.dockerVolumeCreate({ name: createVolumeName.trim() })
      setCreatedInfo(`Created volume: ${createVolumeName.trim()}`)
      setCreateVolumeName('')
      await refreshAll()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function createCustomNetwork(): Promise<void> {
    if (!createNetworkName.trim()) return
    setBusy(true)
    setErr('')
    setCreatedInfo('')
    try {
      await window.dh.dockerNetworkCreate({ name: createNetworkName.trim() })
      setCreatedInfo(`Created network: ${createNetworkName.trim()}`)
      setCreateNetworkName('')
      await refreshAll()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  function applyExampleToForm(example: CreateExample): void {
    const key = `${example.title}-${example.image}`
    const typedName = (customNames[key] ?? '').trim()
    setCustomImage(example.image)
    setCustomName(typedName)
    setCustomPortsText(example.ports ?? '')
    setCustomVolumesText(example.volumes ?? '')
    setCustomEnvText(example.env ?? '')
    setCreatedInfo(`Filled form from example: ${example.title}`)
  }

  async function pullCustomImage(forceImage?: string): Promise<void> {
    const img = forceImage || pullImage.trim()
    if (!img) return
    setBusy(true)
    setErr('')
    setCreatedInfo(`Pulling image: ${img} (this may take a minute)...`)
    try {
      await window.dh.dockerPull({ image: img })
      setCreatedInfo(`Pulled image: ${img}`)
      await refreshAll()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function createCustomContainer(): Promise<void> {
    setBusy(true)
    setErr('')
    setCreatedInfo('Creating container (this may take a while to pull the image)...')
    try {
      const image = customImage.trim()
      if (!image) throw new Error('Image is required')
      const generated = `hype-${image.replace(/[^a-zA-Z0-9_.:-]/g, '-').replace(/[:/]/g, '-')}-${Date.now().toString().slice(-6)}`
      const ports = parsePortMappings(customPortsText)
      const volumes = parseVolumeMappings(customVolumesText)
      const env = parseEnvLines(customEnvText)
      const res = (await window.dh.dockerCreate({
        image,
        name: customName.trim() || generated,
        ports,
        volumes,
        env,
        autoStart,
      })) as { ok: true; id: string }
      setCreatedInfo(`Created container ${res.id.slice(0, 12)} from ${image}`)
      await refreshAll()
      setTab('containers')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function remapPort(): Promise<void> {
    setBusy(true)
    setErr('')
    setCreatedInfo('')
    try {
      if (!remapContainerId) throw new Error('Select container first')
      const oldP = Number(oldHostPort)
      const newP = Number(newHostPort)
      if (!Number.isInteger(oldP) || !Number.isInteger(newP)) {
        throw new Error('Old/New host port must be valid numbers')
      }
      const res = (await window.dh.dockerRemapPort({
        id: remapContainerId,
        oldHostPort: oldP,
        newHostPort: newP,
      })) as { ok: true; name: string }
      setCreatedInfo(`Port remap done. New cloned container: ${res.name}`)
      await refreshAll()
      setTab('containers')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const rows = docker?.ok ? docker.rows : []
  const runningRows = rows.filter((r) => {
    const state = r.state.toLowerCase()
    const status = r.status.toLowerCase()
    return state === 'running' || status.startsWith('up ')
  })
  const stoppedRows = rows.filter((r) => !runningRows.some((x) => x.id === r.id))
  const rowsWithPorts = rows.filter((r) => r.ports !== '—')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1200 }}>
      <header>
        <div className="mono" style={{ color: 'var(--accent)', fontSize: 12, marginBottom: 8 }}>
          DOCKER.SURFACE
        </div>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700 }}>Docker</h1>
        <p style={{ color: 'var(--text-muted)', marginTop: 10, maxWidth: 860 }}>
          Full Docker surface from one click UI: containers, images, volumes, networks, and cleanup.
        </p>
      </header>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <button type="button" style={btn} onClick={() => void refreshAll()} disabled={busy}>
          Refresh
        </button>
        <button type="button" style={btnWarn} onClick={() => void runPrune()} disabled={busy}>
          Cleanup unused (prune)
        </button>
        <button
          type="button"
          style={btn}
          onClick={() => void window.dh.openExternal('https://docs.docker.com/engine/install/')}
        >
          Install docs
        </button>
        <span className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {docker?.ok
            ? `${rows.length} containers • ${images.length} images • ${volumes.length} volumes • ${networks.length} networks`
            : 'docker unavailable'}
        </span>
      </div>

      {pruneInfo ? <div style={{ color: 'var(--green)' }}>{pruneInfo}</div> : null}
      {createdInfo ? <div style={{ color: 'var(--green)' }}>{createdInfo}</div> : null}
      {err ? <div style={{ color: 'var(--orange)' }}>{err}</div> : null}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {(['scheme', 'create', 'containers', 'images', 'volumes', 'networks', 'ports'] as const).map((t) => (
          <button
            key={t}
            type="button"
            style={tab === t ? tabBtnActive : tabBtn}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      <section style={card}>
        {!docker ? <div style={{ color: 'var(--text-muted)' }}>Checking Docker daemon…</div> : null}
        {docker && !docker.ok ? <div style={{ color: 'var(--orange)' }}>{docker.error}</div> : null}
        {docker?.ok && tab === 'create' ? (
          <div style={{ display: 'grid', gap: 8 }}>
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              Create from examples. Click <span className="mono">Use</span> to create a new container template.
            </div>
            <div style={sectionBox}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Pull custom image</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <input
                  value={pullImage}
                  onChange={(e) => setPullImage(e.target.value)}
                  placeholder="e.g. ghcr.io/owner/app:latest"
                  style={{ ...nameInput, marginTop: 0, maxWidth: 420 }}
                  disabled={busy}
                />
                <button type="button" style={btnSmallPrimary} onClick={() => void pullCustomImage()} disabled={busy}>
                  Pull
                </button>
              </div>
            </div>
            <div style={sectionBox}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Custom create (ports/env/volumes)</div>
              <div style={formGrid}>
                <input value={customImage} onChange={(e) => setCustomImage(e.target.value)} placeholder="Image" style={nameInput} disabled={busy} />
                <input value={customName} onChange={(e) => setCustomName(e.target.value)} placeholder="Container name (optional)" style={nameInput} disabled={busy} />
                <textarea value={customPortsText} onChange={(e) => setCustomPortsText(e.target.value)} placeholder="Ports: host:container per line (e.g. 8080:80)" style={areaInput} />
                <textarea value={customVolumesText} onChange={(e) => setCustomVolumesText(e.target.value)} placeholder="Volumes: /host/path:/container/path per line" style={areaInput} />
                <textarea value={customEnvText} onChange={(e) => setCustomEnvText(e.target.value)} placeholder="Env: KEY=VALUE per line" style={areaInput} />
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <input type="checkbox" checked={autoStart} onChange={(e) => setAutoStart(e.target.checked)} />
                  Auto start after create
                </label>
                <button type="button" style={btnSmallPrimary} onClick={() => void createCustomContainer()} disabled={busy}>
                  Create custom container
                </button>
              </div>
            </div>
            {CREATE_EXAMPLES.map((ex) => (
              <div
                key={`${ex.title}-${ex.image}`}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 8,
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '8px 10px',
                  background: 'var(--bg-input)',
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600 }}>{ex.title}</div>
                  <div className="mono" style={{ ...monoCell, maxWidth: 620 }} title={ex.image}>
                    {ex.image}
                    {ex.command ? ` • ${ex.command}` : ''}
                  </div>
                  <input
                    value={customNames[`${ex.title}-${ex.image}`] ?? ''}
                    onChange={(e) =>
                      setCustomNames((prev) => ({
                        ...prev,
                        [`${ex.title}-${ex.image}`]: e.target.value,
                      }))
                    }
                    placeholder="Container name (optional)"
                    style={nameInput}
                    disabled={busy}
                  />
                </div>
                <button
                  type="button"
                  style={btnSmallPrimary}
                  onClick={() => applyExampleToForm(ex)}
                  disabled={busy}
                >
                  Use
                </button>
              </div>
            ))}
          </div>
        ) : null}
        {docker?.ok && tab === 'containers' ? (
          rows.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>No containers found.</div>
          ) : (
            <div style={{ display: 'grid', gap: 16 }}>
              <ContainerTable
                title={`Running now (${runningRows.length})`}
                rows={runningRows}
                busy={busy}
                onAction={runAction}
                onLogs={openLogs}
              />
              <ContainerTable
                title={`Not running (${stoppedRows.length})`}
                rows={stoppedRows}
                busy={busy}
                onAction={runAction}
                onLogs={openLogs}
              />
              {stoppedRows.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                  No stopped containers from current Docker daemon/context.
                </div>
              ) : null}
            </div>
          )
        ) : null}
        {docker?.ok && tab === 'images' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 12 }}>Recommended Images</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 12 }}>
                {RECOMMENDED_IMAGES.map((rec) => (
                  <div key={rec.name} style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border)',
                    borderRadius: 12,
                    padding: 16,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 12,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ 
                        width: 32, height: 32, borderRadius: 8, background: rec.color,
                        display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 'bold', fontSize: 16
                      }}>
                        {rec.name[0].toUpperCase()}
                      </div>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: 15 }}>{rec.name}</div>
                        <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{rec.tag}</div>
                      </div>
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.4, flex: 1 }}>
                      {rec.description}
                    </div>
                    <button type="button" style={{ ...btnSmallPrimary, width: '100%', marginTop: 'auto' }} onClick={() => {
                        const img = `${rec.name}:${rec.tag}`
                        setPullImage(img)
                        void pullCustomImage(img)
                      }} disabled={busy}>
                      PULL
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div style={{ fontWeight: 600, marginBottom: 12 }}>Downloaded Images</div>
              {images.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No images found.</div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 12 }}>
                  {images.map((img) => (
                    <div key={img.id} style={{
                      background: 'var(--bg-input)',
                      border: '1px solid var(--border)',
                      borderRadius: 12,
                      padding: 16,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                    }}>
                      <div className="mono" style={{ fontWeight: 600, fontSize: 13, wordBreak: 'break-all' }} title={img.repoTags.join(', ')}>
                        {img.repoTags.join(', ') || '<none>'}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        {img.sizeMb} MB • {new Date(img.createdAt).toLocaleDateString()}
                      </div>
                      <button type="button" style={{ ...btnSmallDanger, marginTop: 8 }} onClick={() => void removeImage(img.id)} disabled={busy}>
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}
        {docker?.ok && tab === 'volumes' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div style={sectionBox}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Create Volume</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <input
                  value={createVolumeName}
                  onChange={(e) => setCreateVolumeName(e.target.value)}
                  placeholder="e.g. my_database_data"
                  style={{ ...nameInput, marginTop: 0, maxWidth: 320 }}
                  disabled={busy}
                />
                <button type="button" style={btnSmallPrimary} onClick={() => void createCustomVolume()} disabled={busy}>
                  Create Volume
                </button>
              </div>
            </div>

            <div>
              <div style={{ fontWeight: 600, marginBottom: 12 }}>Local Volumes</div>
              {volumes.length === 0 ? (
                <div style={{ color: 'var(--text-muted)' }}>No volumes found.</div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                  {volumes.map((v) => (
                    <div key={v.name} style={{
                      background: 'var(--bg-input)',
                      border: '1px solid var(--border)',
                      borderRadius: 12,
                      padding: 16,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                    }}>
                      <div className="mono" style={{ fontWeight: 600, fontSize: 13, wordBreak: 'break-all', color: 'var(--accent)' }} title={v.name}>
                        {v.name}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', gap: 8 }}>
                        <span>Driver: <span className="mono">{v.driver}</span></span>
                        <span>Scope: <span className="mono">{v.scope}</span></span>
                      </div>
                      <div className="mono" style={{ fontSize: 11, background: 'var(--bg)', padding: '6px 8px', borderRadius: 6, wordBreak: 'break-all' }} title={v.mountpoint}>
                        {truncateMiddle(v.mountpoint, 60)}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        Used by:{' '}
                        <span className="mono" style={{ fontSize: 11 }}>
                          {v.usedBy && v.usedBy.length > 0 ? v.usedBy.join(', ') : 'unused'}
                        </span>
                      </div>
                      <button type="button" style={{ ...btnSmallDanger, marginTop: 8 }} onClick={() => void removeVolume(v.name)} disabled={busy}>
                        Remove Volume
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}
        {docker?.ok && tab === 'scheme' ? (
          <div style={{ display: 'grid', gap: 12 }}>
            <DockerSchemeView containers={rows} networks={networks} />
            <div style={sectionBox}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Relationship details</div>
              {rows.length === 0 ? (
                <div style={{ color: 'var(--text-muted)' }}>No containers found.</div>
              ) : (
                <div style={tableWrap}>
                  <table style={table}>
                    <thead>
                      <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
                        <th style={{ padding: '8px 6px' }}>Container</th>
                        <th>Image</th>
                        <th>Networks</th>
                        <th>Volumes</th>
                        <th>Ports</th>
                        <th>State</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr key={r.id} style={{ borderTop: '1px solid var(--border)' }}>
                          <td style={{ padding: '9px 6px', fontWeight: 600 }}>{r.name}</td>
                          <td className="mono" style={monoCell} title={r.image}>
                            {r.image}
                          </td>
                          <td className="mono" style={monoCell} title={(r.networks ?? []).join(', ')}>
                            {(r.networks ?? []).length > 0 ? (r.networks ?? []).join(', ') : '—'}
                          </td>
                          <td className="mono" style={monoCell} title={(r.volumes ?? []).join(', ')}>
                            {(r.volumes ?? []).length > 0 ? (r.volumes ?? []).join(', ') : '—'}
                          </td>
                          <td className="mono" style={monoCell} title={r.ports}>{r.ports}</td>
                          <td>{r.state}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        ) : null}
        {docker?.ok && tab === 'networks' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div style={sectionBox}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Create Network</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <input
                  value={createNetworkName}
                  onChange={(e) => setCreateNetworkName(e.target.value)}
                  placeholder="e.g. my_custom_network"
                  style={{ ...nameInput, marginTop: 0, maxWidth: 320 }}
                  disabled={busy}
                />
                <button type="button" style={btnSmallPrimary} onClick={() => void createCustomNetwork()} disabled={busy}>
                  Create Network
                </button>
              </div>
            </div>

            <div>
              <div style={{ fontWeight: 600, marginBottom: 12 }}>Local Networks</div>
              {networks.length === 0 ? (
                <div style={{ color: 'var(--text-muted)' }}>No networks found.</div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                  {networks.map((n) => (
                    <div key={n.id} style={{
                      background: 'var(--bg-input)',
                      border: '1px solid var(--border)',
                      borderRadius: 12,
                      padding: 16,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                    }}>
                      <div style={{ fontWeight: 600, fontSize: 15, wordBreak: 'break-all' }}>
                        {n.name}
                      </div>
                      <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }} title={n.id}>
                        {n.id.slice(0, 12)}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', gap: 8, marginTop: 4 }}>
                        <span>Driver: <span className="mono">{n.driver}</span></span>
                        <span>Scope: <span className="mono">{n.scope}</span></span>
                      </div>
                      <button
                        type="button"
                        style={{ ...btnSmallDanger, marginTop: 8 }}
                        onClick={() => void removeNetwork(n.id)}
                        disabled={busy || n.name === 'bridge' || n.name === 'host' || n.name === 'none'}
                      >
                        {n.name === 'bridge' || n.name === 'host' || n.name === 'none' ? 'System Network' : 'Remove Network'}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}
        {docker?.ok && tab === 'ports' ? (
          <div style={{ display: 'grid', gap: 12 }}>
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              Port manager for conflicts: clone container with remapped host port.
            </div>
            <div style={sectionBox}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Current published ports</div>
              {rowsWithPorts.length === 0 ? (
                <div style={{ color: 'var(--text-muted)' }}>No containers with published ports.</div>
              ) : (
                <div style={tableWrap}>
                  <table style={table}>
                    <thead>
                      <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
                        <th style={{ padding: '8px 6px' }}>Container</th>
                        <th>State</th>
                        <th>Ports</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rowsWithPorts.map((r) => (
                        <tr key={r.id} style={{ borderTop: '1px solid var(--border)' }}>
                          <td style={{ padding: '9px 6px', fontWeight: 600 }}>{r.name}</td>
                          <td>{r.state}</td>
                          <td className="mono" style={monoCell} title={r.ports}>{r.ports}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div style={sectionBox}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Remap host port</div>
              <div style={formGrid}>
                <select
                  value={remapContainerId}
                  onChange={(e) => setRemapContainerId(e.target.value)}
                  style={nameInput}
                >
                  <option value="">Select container</option>
                  {rowsWithPorts.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name} ({r.ports})
                    </option>
                  ))}
                </select>
                <input value={oldHostPort} onChange={(e) => setOldHostPort(e.target.value)} placeholder="Old host port (e.g. 8080)" style={nameInput} />
                <input value={newHostPort} onChange={(e) => setNewHostPort(e.target.value)} placeholder="New host port (e.g. 8081)" style={nameInput} />
                <button type="button" style={btnSmallPrimary} onClick={() => void remapPort()} disabled={busy}>
                  Remap (clone + start)
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      {selected ? (
        <section style={card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontWeight: 600 }}>Logs: {selected.name}</div>
            <button type="button" style={btnSmall} onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
          <pre className="mono" style={pre}>{logText}</pre>
        </section>
      ) : null}
    </div>
  )
}

const card = {
  background: 'var(--bg-widget)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius)',
  padding: 14,
}

const btn = {
  border: '1px solid var(--border)',
  background: 'var(--bg-input)',
  color: 'var(--text)',
  borderRadius: 8,
  padding: '8px 12px',
  cursor: 'pointer',
}

const btnWarn = {
  ...btn,
  border: '1px solid var(--orange)',
}

const btnSmall = {
  ...btn,
  padding: '5px 10px',
  fontSize: 12,
}

const btnSmallPrimary = {
  ...btnSmall,
  border: '1px solid var(--accent)',
  color: 'var(--accent)',
}

const btnSmallDanger = {
  ...btnSmall,
  border: '1px solid var(--orange)',
  color: 'var(--orange)',
}

const tabBtn = {
  ...btnSmall,
  textTransform: 'capitalize' as const,
}

const tabBtnActive = {
  ...tabBtn,
  border: '1px solid var(--accent)',
  color: 'var(--accent)',
}

const tableWrap = {
  width: '100%',
  overflowX: 'auto' as const,
}

const table = {
  width: '100%',
  minWidth: 760,
  borderCollapse: 'collapse' as const,
  fontSize: 13,
  tableLayout: 'fixed' as const,
}

const monoCell = {
  fontSize: 11,
  whiteSpace: 'nowrap' as const,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
}

const nameInput = {
  marginTop: 6,
  width: '100%',
  maxWidth: 320,
  border: '1px solid var(--border)',
  background: 'var(--bg)',
  color: 'var(--text)',
  borderRadius: 8,
  padding: '6px 8px',
  fontSize: 12,
}

const areaInput = {
  ...nameInput,
  minHeight: 72,
  resize: 'vertical' as const,
  fontFamily: 'inherit',
}

const sectionBox = {
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: 10,
  background: 'var(--bg-input)',
}

const formGrid = {
  display: 'grid',
  gap: 8,
}

const pre = {
  margin: '12px 0 0 0',
  padding: 12,
  background: '#0a0a0a',
  border: '1px solid var(--border)',
  borderRadius: 8,
  maxHeight: 420,
  overflow: 'auto' as const,
  whiteSpace: 'pre-wrap' as const,
  fontSize: 12,
}

function truncateMiddle(input: string, maxLen: number): string {
  if (input.length <= maxLen) return input
  const side = Math.max(8, Math.floor((maxLen - 1) / 2))
  return `${input.slice(0, side)}…${input.slice(-side)}`
}

function parsePortMappings(text: string): Array<{ hostPort: number; containerPort: number; protocol?: 'tcp' | 'udp' }> {
  const lines = text
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
  const out: Array<{ hostPort: number; containerPort: number; protocol?: 'tcp' | 'udp' }> = []
  for (const line of lines) {
    const [pair, protoRaw] = line.split('/')
    const [hostRaw, containerRaw] = pair.split(':')
    const hostPort = Number(hostRaw)
    const containerPort = Number(containerRaw)
    if (!Number.isInteger(hostPort) || !Number.isInteger(containerPort)) {
      throw new Error(`Invalid port mapping: ${line}. Use host:container, e.g. 8080:80`)
    }
    const protocol = protoRaw === 'udp' ? 'udp' : 'tcp'
    out.push({ hostPort, containerPort, protocol })
  }
  return out
}

function parseVolumeMappings(text: string): Array<{ hostPath: string; containerPath: string }> {
  const lines = text
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
  return lines.map((line) => {
    const idx = line.indexOf(':')
    if (idx <= 0 || idx >= line.length - 1) {
      throw new Error(`Invalid volume mapping: ${line}. Use /host/path:/container/path`)
    }
    return { hostPath: line.slice(0, idx), containerPath: line.slice(idx + 1) }
  })
}

function parseEnvLines(text: string): string[] {
  return text
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
}

type ContainerTableProps = {
  title: string
  rows: ContainerRow[]
  busy: boolean
  onAction: (id: string, action: 'start' | 'stop' | 'restart' | 'remove') => Promise<void>
  onLogs: (row: ContainerRow) => Promise<void>
}

function ContainerTable(props: ContainerTableProps): ReactElement {
  const { title, rows, busy, onAction, onLogs } = props
  return (
    <div>
      <div style={{ fontWeight: 600, marginBottom: 12 }}>{title}</div>
      {rows.length === 0 ? (
        <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No containers in this group.</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
          {rows.map((r) => {
            const isRunning = r.state.toLowerCase() === 'running'
            return (
              <div key={r.id} style={{
                background: 'var(--bg-input)',
                border: '1px solid var(--border)',
                borderRadius: 12,
                padding: 16,
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <div style={{ 
                    width: 10, height: 10, borderRadius: '50%', flexShrink: 0, marginTop: 4,
                    background: isRunning ? 'var(--green)' : 'var(--text-muted)' 
                  }} title={r.state} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={r.name}>{r.name}</div>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={r.image}>{r.image}</div>
                  </div>
                </div>
                
                {r.ports !== '—' && (
                  <div className="mono" style={{ fontSize: 11, background: 'var(--bg)', padding: '6px 8px', borderRadius: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={r.ports}>
                    {r.ports}
                  </div>
                )}
                
                <div style={{ marginTop: 'auto', display: 'flex', gap: 8, paddingTop: 4 }}>
                  <button type="button" style={btnSmall} onClick={() => void onAction(r.id, isRunning ? 'stop' : 'start')} disabled={busy}>
                    {isRunning ? 'Stop' : 'Start'}
                  </button>
                  {isRunning && (
                    <button type="button" style={btnSmall} onClick={() => void onAction(r.id, 'restart')} disabled={busy}>
                      Restart
                    </button>
                  )}
                  <button type="button" style={btnSmall} onClick={() => void onLogs(r)} disabled={busy}>
                    Logs
                  </button>
                  {!isRunning ? (
                    <button type="button" style={btnSmallDanger} onClick={() => void onAction(r.id, 'remove')} disabled={busy}>
                      Remove
                    </button>
                  ) : null}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
