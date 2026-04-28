import type { ReactElement } from 'react'

export function DashboardKernelsPage(): ReactElement {
  return (
    <div style={{ maxWidth: 720 }}>
      <div className="mono" style={{ color: 'var(--accent)', fontSize: 12, marginBottom: 8 }}>
        DASHBOARD.KERNELS
      </div>
      <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700 }}>Kernels &amp; toolchains</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: 15, lineHeight: 1.55, marginTop: 12 }}>
        This section is reserved for compiler defaults, WSL-style environment hints, and kernel-related shortcuts. Not
        implemented yet—use your distro packages or host tools for now.
      </p>
    </div>
  )
}
