import type { CSSProperties, ReactElement } from 'react'
import { useEffect, useState } from 'react'

const titles: Record<string, string> = {
  '/dashboard': 'HYPEDEVHOME',
  '/system': 'System',
  '/workstation': 'Workstation',
  '/registry': 'Registry',
  '/terminal': 'Terminal',
}

export function TopBar({ path }: { path: string }): ReactElement {
  const [q, setQ] = useState('')

  useEffect(() => {
    setQ('')
  }, [path])

  return (
    <header
      style={{
        height: 'var(--top-height)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        gap: 16,
        background: 'var(--bg-panel)',
        flexShrink: 0,
      }}
    >
      <div style={{ fontWeight: 700, letterSpacing: '0.04em', minWidth: 140 }}>
        {titles[path] ?? 'Linux Dev Home'}
      </div>
      <div style={{ display: 'flex', gap: 8, flex: 1, justifyContent: 'center' }}>
        {path === '/dashboard' ? (
          <>
            <Tab label="Main" active />
            <Tab label="Kernels" />
            <Tab label="Logs" />
          </>
        ) : (
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Overview</span>
        )}
      </div>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search workstation..."
        style={{
          width: 220,
          background: 'var(--bg-input)',
          border: '1px solid var(--border)',
          borderRadius: 6,
          padding: '6px 10px',
          color: 'var(--text)',
          fontSize: 13,
        }}
      />
      <button
        type="button"
        aria-label="Notifications"
        style={btnIcon}
      >
        <span className="codicon codicon-bell" />
      </button>
      <button type="button" aria-label="Console" style={btnIcon}>
        <span className="codicon codicon-terminal" />
      </button>
      <button type="button" aria-label="Settings" style={btnIcon}>
        <span className="codicon codicon-gear" />
      </button>
    </header>
  )
}

function Tab({ label, active }: { label: string; active?: boolean }): ReactElement {
  return (
    <button
      type="button"
      style={{
        border: 'none',
        background: 'none',
        color: active ? 'var(--text)' : 'var(--text-muted)',
        fontWeight: active ? 600 : 500,
        borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
        padding: '10px 4px',
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  )
}

const btnIcon: CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  cursor: 'pointer',
  padding: 6,
  borderRadius: 6,
}
