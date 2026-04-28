import type { ReactElement } from 'react'
import { useState } from 'react'

type ProfileData = {
  name: string
  baseTemplate: string
}

export function CustomProfileWizardModal(props: {
  open: boolean
  onClose: () => void
  onSave: (data: ProfileData) => void
}): ReactElement | null {
  const [name, setName] = useState('')
  const [template, setTemplate] = useState('web-dev')

  if (!props.open) return null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        backdropFilter: 'blur(4px)',
      }}
    >
      <div
        style={{
          background: 'var(--bg-widget)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: 24,
          width: '100%',
          maxWidth: 480,
          boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
        }}
      >
        <h2 style={{ margin: 0, fontSize: 20 }}>Create Custom Profile</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 20 }}>
          Define a new custom profile by selecting a base template.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 600 }}>
              Profile Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My Next.js Setup"
              style={{
                width: '100%',
                padding: '10px 12px',
                background: 'var(--bg-input)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                color: 'var(--text)',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 600 }}>
              Base Template
            </label>
            <select
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 12px',
                background: 'var(--bg-input)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                color: 'var(--text)',
              }}
            >
              <option value="web-dev">Web Development</option>
              <option value="data-science">Python Data Science</option>
              <option value="ai-ml">AI/ML Local</option>
              <option value="mobile">Mobile App Dev</option>
              <option value="game-dev">Game Development</option>
              <option value="infra">Infra / K8s</option>
              <option value="desktop-gui">Desktop Qt/GTK</option>
              <option value="docs">Docs / Writing</option>
              <option value="empty">Empty Minimal</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24 }}>
          <button
            type="button"
            onClick={props.onClose}
            style={{
              padding: '8px 16px',
              background: 'transparent',
              border: 'none',
              color: 'var(--text)',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!name.trim()}
            onClick={() => {
              props.onSave({ name: name.trim(), baseTemplate: template })
              setName('')
            }}
            style={{
              padding: '8px 16px',
              background: 'var(--accent)',
              border: 'none',
              borderRadius: 6,
              color: '#fff',
              cursor: name.trim() ? 'pointer' : 'not-allowed',
              opacity: name.trim() ? 1 : 0.5,
              fontWeight: 600,
            }}
          >
            Create
          </button>
        </div>
      </div>
    </div>
  )
}
