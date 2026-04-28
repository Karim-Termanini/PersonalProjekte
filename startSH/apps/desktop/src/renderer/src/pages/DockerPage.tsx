import type { ContainerRow, ImageRow, NetworkRow, VolumeRow } from '@linux-dev-home/shared'
import type { ReactElement } from 'react'
import { useCallback, useEffect, useState } from 'react'

type TabId = 'containers' | 'images' | 'volumes' | 'networks'

export function DockerPage(): ReactElement {
  const [tab, setTab] = useState<TabId>('containers')
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

  async function runAction(id: string, action: 'start' | 'stop' | 'restart'): Promise<void> {
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
      setErr(e instanceof Error ? e.message : String(e))
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

  const rows = docker?.ok ? docker.rows : []

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
      {err ? <div style={{ color: 'var(--orange)' }}>{err}</div> : null}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {(['containers', 'images', 'volumes', 'networks'] as const).map((t) => (
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
        {docker?.ok && tab === 'containers' ? (
          rows.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>No containers found.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: '8px 6px' }}>Name</th>
                  <th>Image</th>
                  <th>State</th>
                  <th>Ports</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: '9px 6px', fontWeight: 600 }}>{r.name}</td>
                    <td className="mono" style={{ fontSize: 11 }}>{r.image}</td>
                    <td>{r.state}</td>
                    <td className="mono" style={{ fontSize: 11 }}>{r.ports}</td>
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button type="button" style={btnSmall} onClick={() => void runAction(r.id, 'start')}>start</button>{' '}
                      <button type="button" style={btnSmall} onClick={() => void runAction(r.id, 'restart')}>restart</button>{' '}
                      <button type="button" style={btnSmall} onClick={() => void runAction(r.id, 'stop')}>stop</button>{' '}
                      <button type="button" style={btnSmall} onClick={() => void openLogs(r)}>logs</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : null}
        {docker?.ok && tab === 'images' ? (
          images.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>No images found.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: '8px 6px' }}>Repository:Tag</th>
                  <th>Size</th>
                  <th>Created</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {images.map((img) => (
                  <tr key={img.id} style={{ borderTop: '1px solid var(--border)' }}>
                    <td className="mono" style={{ padding: '9px 6px', fontSize: 11 }}>{img.repoTags.join(', ')}</td>
                    <td>{img.sizeMb} MB</td>
                    <td>{new Date(img.createdAt).toLocaleString()}</td>
                    <td style={{ textAlign: 'right' }}>
                      <button type="button" style={btnSmallDanger} onClick={() => void removeImage(img.id)}>
                        remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : null}
        {docker?.ok && tab === 'volumes' ? (
          volumes.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>No volumes found.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: '8px 6px' }}>Name</th>
                  <th>Driver</th>
                  <th>Scope</th>
                  <th>Mountpoint</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {volumes.map((v) => (
                  <tr key={v.name} style={{ borderTop: '1px solid var(--border)' }}>
                    <td className="mono" style={{ padding: '9px 6px', fontSize: 11 }}>{v.name}</td>
                    <td>{v.driver}</td>
                    <td>{v.scope}</td>
                    <td className="mono" style={{ fontSize: 11 }}>{v.mountpoint}</td>
                    <td style={{ textAlign: 'right' }}>
                      <button type="button" style={btnSmallDanger} onClick={() => void removeVolume(v.name)}>
                        remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : null}
        {docker?.ok && tab === 'networks' ? (
          networks.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>No networks found.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: '8px 6px' }}>Name</th>
                  <th>ID</th>
                  <th>Driver</th>
                  <th>Scope</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {networks.map((n) => (
                  <tr key={n.id} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: '9px 6px', fontWeight: 600 }}>{n.name}</td>
                    <td className="mono" style={{ fontSize: 11 }}>{n.id.slice(0, 12)}</td>
                    <td>{n.driver}</td>
                    <td>{n.scope}</td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        type="button"
                        style={btnSmallDanger}
                        onClick={() => void removeNetwork(n.id)}
                        disabled={n.name === 'bridge' || n.name === 'host' || n.name === 'none'}
                      >
                        remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
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
