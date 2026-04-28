import type { ReactElement } from 'react'

export function DashboardLogsPage(): ReactElement {
  return (
    <div style={{ maxWidth: 720 }}>
      <div className="mono" style={{ color: 'var(--accent)', fontSize: 12, marginBottom: 8 }}>
        DASHBOARD.LOGS
      </div>
      <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700 }}>Logs</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: 15, lineHeight: 1.55, marginTop: 12 }}>
        Live tails for compose jobs and background tasks will appear here. Until then, open{' '}
        <span style={{ fontWeight: 600, color: 'var(--text)' }}>Workstation</span> and use the profile log buttons.
      </p>
    </div>
  )
}
