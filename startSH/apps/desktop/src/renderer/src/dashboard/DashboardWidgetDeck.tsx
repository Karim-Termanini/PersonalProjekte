import type { DashboardLayoutFile, DashboardPlacement } from '@linux-dev-home/shared'
import { getWidgetDefinition } from '@linux-dev-home/shared'
import type { ReactElement } from 'react'
import { Link } from 'react-router-dom'

export function DashboardWidgetDeck(props: {
  layout: DashboardLayoutFile
  onRemove: (instanceId: string) => void
}): ReactElement {
  return (
    <section style={{ marginTop: 8 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: 12,
        }}
      >
        <h2 style={{ margin: 0, fontSize: 16 }}>Your widgets</h2>
        <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {props.layout.placements.length} / 24
        </span>
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 260px), 1fr))',
          gap: 14,
        }}
      >
        {props.layout.placements.map((p) => (
          <WidgetTile key={p.instanceId} placement={p} onRemove={() => props.onRemove(p.instanceId)} />
        ))}
      </div>
    </section>
  )
}

function WidgetTile(props: { placement: DashboardPlacement; onRemove: () => void }): ReactElement {
  const def = getWidgetDefinition(props.placement.widgetTypeId)
  const title = def?.title ?? props.placement.widgetTypeId
  const desc = def?.description ?? 'Unknown widget type'

  let body: ReactElement
  switch (props.placement.widgetTypeId) {
    case 'link.workstation':
      body = (
        <Link to="/workstation" style={{ color: 'var(--accent)', fontWeight: 600, fontSize: 13 }}>
          Open workstation →
        </Link>
      )
      break
    case 'link.system':
      body = (
        <Link to="/system" style={{ color: 'var(--accent)', fontWeight: 600, fontSize: 13 }}>
          Open system →
        </Link>
      )
      break
    case 'static.docker-permission-hint':
      body = (
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)' }}>
          Grant Docker socket access for your Flatpak build, or run natively for full engine access. See the banner
          link for details.
        </p>
      )
      break
    case 'static.host-trust-hint':
      body = (
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)' }}>
          Prefer user-level installers (rustup, nvm, pipx) when sandboxed. System packages need a trusted host session
          or elevated installer flows (planned).
        </p>
      )
      break
    case 'custom.placeholder':
      body = (
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)' }}>
          Placeholder for Phase 1 custom profiles and user-defined widget packs.
        </p>
      )
      break
    default:
      body = (
        <p style={{ margin: 0, fontSize: 13, color: 'var(--orange)' }}>
          Unregistered widget type. Remove and add again from the registry.
        </p>
      )
  }

  return (
    <article
      style={{
        background: 'var(--bg-widget)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        padding: 14,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        minHeight: 120,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start' }}>
        <div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>
            {props.placement.instanceId}
          </div>
          <div style={{ fontWeight: 600, fontSize: 15 }}>{title}</div>
        </div>
        <button
          type="button"
          onClick={props.onRemove}
          title="Remove widget"
          style={{
            border: 'none',
            background: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            fontSize: 12,
          }}
        >
          Remove
        </button>
      </div>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)', flex: 1 }}>{desc}</p>
      {body}
    </article>
  )
}
