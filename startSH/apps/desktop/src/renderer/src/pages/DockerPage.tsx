import type { ContainerRow } from '@linux-dev-home/shared'
import type { ReactElement } from 'react'
import { useCallback, useEffect, useState } from 'react'

export function DockerPage(): ReactElement {
  const [docker, setDocker] = useState<
    { ok: true; rows: ContainerRow[] } | { ok: false; error: string } | null
  >(null)
  const [selected, setSelected] = useState<ContainerRow | null>(null)
  const [logText, setLogText] = useState<string>('')
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const d = (await window.dh.dockerList()) as
        | { ok: true; rows: ContainerRow[] }
        | { ok: false; error: string }
      setDocker(d)
    } catch (e) {
      setDocker({ ok: false, error: e instanceof Error ? e.message : String(e) })
    }
  }, [])

  useEffect(() => {
    void refresh()
    const id = setInterval(() => void refresh(), 4000)
    return () => clearInterval(id)
  }, [refresh])

  async function runAction(id: string, action: 'start' | 'stop' | 'restart'): Promise<void> {
    setBusy(true)
    try {
      await window.dh.dockerAction({ id, action })
      await refresh()
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

  const rows = docker?.ok ? docker.rows : []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1200 }}>
      <header>
        <div className="mono" style={{ color: 'var(--accent)', fontSize: 12, marginBottom: 8 }}>
          DOCKER.SURFACE
        </div>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700 }}>Docker</h1>
        <p style={{ color: 'var(--text-muted)', marginTop: 10, maxWidth: 860 }}>
          Start/stop/restart containers and inspect logs without terminal commands. This is the first Phase 2 surface.
        </p>
      </header>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <button type="button" style={btn} onClick={() => void refresh()} disabled={busy}>
          Refresh
        </button>
        <button
          type="button"
          style={btn}
          onClick={() => void window.dh.openExternal('https://docs.docker.com/engine/install/')}
        >
          Install docs
        </button>
        <span className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {docker?.ok ? `${rows.length} containers` : 'docker unavailable'}
        </span>
      </div>

      <section style={card}>
        {!docker ? (
          <div style={{ color: 'var(--text-muted)' }}>Checking Docker daemon…</div>
        ) : !docker.ok ? (
          <div style={{ color: 'var(--orange)' }}>{docker.error}</div>
        ) : rows.length === 0 ? (
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
        )}
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

const btnSmall = {
  ...btn,
  padding: '5px 10px',
  fontSize: 12,
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
