import type { ReactElement } from 'react'
import { useCallback, useEffect, useState } from 'react'

type Target = 'sandbox' | 'host'

type GitConfigRow = {
  key: string
  value: string
}

const SENSITIVE_KEYS = new Set([
  'user.password',
  'user.signingkey',
  'credential.helper',
  'http.proxy',
  'https.proxy',
  'core.askpass',
  'http.cookiefile',
  'http.extraheader',
])

export function GitConfigPage(): ReactElement {
  const [target, setTarget] = useState<Target>('sandbox')
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [defaultBranch, setDefaultBranch] = useState('')
  const [defaultEditor, setDefaultEditor] = useState('')
  const [rows, setRows] = useState<GitConfigRow[]>([])
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [maskedKeys, setMaskedKeys] = useState<Set<string>>(
    () => new Set(SENSITIVE_KEYS)
  )

  const loadConfig = useCallback(async () => {
    setBusy(true)
    setStatus('')
    try {
      const res = (await window.dh.gitConfigList({ target })) as {
        ok: boolean
        rows: GitConfigRow[]
      }
      const nextRows = res.rows ?? []
      setRows(nextRows)
      const byKey = new Map(nextRows.map((r) => [r.key.toLowerCase(), r.value]))
      setName(byKey.get('user.name') ?? '')
      setEmail(byKey.get('user.email') ?? '')
      setDefaultBranch(byKey.get('init.defaultbranch') ?? '')
      setDefaultEditor(byKey.get('core.editor') ?? '')
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e))
      setRows([])
    } finally {
      setBusy(false)
    }
  }, [target])

  useEffect(() => {
    void loadConfig()
  }, [loadConfig])

  async function applyConfig(): Promise<void> {
    if (!name.trim() || !email.trim()) {
      setStatus('Name and email are required.')
      return
    }
    setBusy(true)
    setStatus('')
    try {
      await window.dh.gitConfigSet({
        name: name.trim(),
        email: email.trim(),
        defaultBranch: defaultBranch.trim() || undefined,
        defaultEditor: defaultEditor.trim() || undefined,
        target,
      })
      setStatus('Git config saved.')
      await loadConfig()
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  function toggleMask(key: string): void {
    setMaskedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  function isSensitive(key: string): boolean {
    return SENSITIVE_KEYS.has(key) || /password|secret|token|key$/i.test(key)
  }

  function maskValue(key: string, value: string): string {
    if (!maskedKeys.has(key) && isSensitive(key)) {
      if (value.length <= 4) return '●●●●'
      return value.slice(0, 2) + '●●●●' + value.slice(-2)
    }
    if (maskedKeys.has(key) && isSensitive(key)) return value
    return value
  }

  const filtered = rows.filter((r) => {
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return r.key.toLowerCase().includes(q) || r.value.toLowerCase().includes(q)
  })

  return (
    <div style={{ maxWidth: 980, display: 'grid', gap: 16 }}>
      <header>
        <h1 style={{ margin: 0 }}>Git Configuration</h1>
        <p style={{ color: 'var(--text-muted)' }}>
          Set user identity and default settings, then review all global config entries.
        </p>
      </header>

      <section style={card}>
        <div style={{ fontWeight: 600, marginBottom: 10 }}>Target</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            style={target === 'sandbox' ? btnActive : btn}
            onClick={() => setTarget('sandbox')}
          >
            Sandbox
          </button>
          <button
            type="button"
            style={target === 'host' ? btnActive : btn}
            onClick={() => setTarget('host')}
          >
            Host
          </button>
        </div>
      </section>

      <section style={card}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <div style={{ fontWeight: 600, marginBottom: 12 }}>User Identity</div>
            <div style={{ display: 'grid', gap: 8 }}>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your full name (e.g. Jane Doe)"
                style={input}
                disabled={busy}
              />
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Your email (e.g. jane@example.com)"
                style={input}
                disabled={busy}
              />
            </div>
          </div>
          <div>
            <div style={{ fontWeight: 600, marginBottom: 12 }}>Defaults</div>
            <div style={{ display: 'grid', gap: 8 }}>
              <input
                value={defaultBranch}
                onChange={(e) => setDefaultBranch(e.target.value)}
                placeholder="Default branch (e.g. main)"
                style={input}
                disabled={busy}
              />
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" style={btnSmall} onClick={() => setDefaultBranch('main')} disabled={busy}>
                  main
                </button>
                <button type="button" style={btnSmall} onClick={() => setDefaultBranch('master')} disabled={busy}>
                  master
                </button>
              </div>
              <input
                value={defaultEditor}
                onChange={(e) => setDefaultEditor(e.target.value)}
                placeholder="Default editor (e.g. code --wait, vim, nano)"
                style={input}
                disabled={busy}
              />
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" style={btnSmall} onClick={() => setDefaultEditor('code --wait')} disabled={busy}>
                  VS Code
                </button>
                <button type="button" style={btnSmall} onClick={() => setDefaultEditor('vim')} disabled={busy}>
                  vim
                </button>
                <button type="button" style={btnSmall} onClick={() => setDefaultEditor('nano')} disabled={busy}>
                  nano
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section style={card}>
        <button
          type="button"
          style={btnPrimary}
          onClick={() => void applyConfig()}
          disabled={busy}
        >
          Apply Configuration
        </button>
      </section>

      <section style={card}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
            flexWrap: 'wrap',
            gap: 8,
          }}
        >
          <div style={{ fontWeight: 600 }}>
            Global Config ({rows.length} entries)
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter entries…"
              style={{ ...input, marginBottom: 0, width: 200 }}
              disabled={busy}
            />
            <button type="button" style={btnSmall} onClick={() => void loadConfig()} disabled={busy}>
              Refresh
            </button>
          </div>
        </div>
        {filtered.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            {rows.length === 0
              ? 'No global git config entries found. Run `git config --global --list` in a terminal to verify.'
              : 'No entries match your filter.'}
          </div>
        ) : (
          <div style={{ width: '100%', overflowX: 'auto' }}>
            <table style={table}>
              <thead>
                <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: '8px 6px', width: '45%' }}>Key</th>
                  <th style={{ padding: '8px 6px', width: '45%' }}>Value</th>
                  <th style={{ padding: '8px 6px', width: '10%' }}></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => {
                  const sensitive = isSensitive(r.key)
                  const masked = maskValue(r.key, r.value)
                  return (
                    <tr
                      key={r.key}
                      style={{ borderTop: '1px solid var(--border)' }}
                    >
                      <td
                        className="mono"
                        style={{ padding: '9px 6px', fontSize: 12, wordBreak: 'break-all' }}
                      >
                        {r.key}
                      </td>
                      <td
                        className="mono"
                        style={{ padding: '9px 6px', fontSize: 12, wordBreak: 'break-all' }}
                      >
                        {masked}
                      </td>
                      <td style={{ padding: '9px 6px', textAlign: 'center' }}>
                        {sensitive ? (
                          <button
                            type="button"
                            style={btnSmall}
                            onClick={() => toggleMask(r.key)}
                            title={
                              maskedKeys.has(r.key) && sensitive
                                ? 'Mask'
                                : 'Reveal'
                            }
                          >
                            {maskedKeys.has(r.key) && sensitive ? '👁' : '🙈'}
                          </button>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>—</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {status ? (
        <div
          style={{
            color: 'var(--text-muted)',
            fontSize: 13,
            padding: '8px 0',
          }}
        >
          {status}
        </div>
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

const btnActive = {
  ...btn,
  border: '1px solid var(--accent)',
  color: 'var(--accent)',
}

const btnPrimary = {
  ...btn,
  border: '1px solid var(--accent)',
  color: 'var(--accent)',
  fontWeight: 600,
}

const btnSmall = {
  ...btn,
  padding: '5px 10px',
  fontSize: 12,
}

const input = {
  marginBottom: 4,
  width: '100%',
  border: '1px solid var(--border)',
  background: 'var(--bg-input)',
  color: 'var(--text)',
  borderRadius: 8,
  padding: '8px 10px',
  fontSize: 13,
}

const table = {
  width: '100%',
  minWidth: 600,
  borderCollapse: 'collapse' as const,
  fontSize: 13,
}