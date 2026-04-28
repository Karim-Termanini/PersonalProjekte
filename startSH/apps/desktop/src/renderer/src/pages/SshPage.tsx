import type { ReactElement } from 'react'
import { useEffect, useRef, useState } from 'react'
import type { SshBookmark } from '@linux-dev-home/shared'
import { FitAddon } from '@xterm/addon-fit'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'

type Target = 'sandbox' | 'host'

type Session = {
  id: string
  termId?: string
  bmId: string
  bmName: string
  user: string
  host: string
  port: number
  status: 'connecting' | 'connected' | 'disconnected'
  startTime: number
}

export function SshPage(): ReactElement {
  const [target] = useState<Target>('host')
  const [busy, setBusy] = useState(false)
  const [email, setEmail] = useState('')
  const [pubKey, setPubKey] = useState('')
  const [testOk, setTestOk] = useState<boolean | null>(null)
  const [testResult, setTestResult] = useState('')
  const [status, setStatus] = useState('')

  const [bookmarks, setBookmarks] = useState<SshBookmark[]>([])
  const [newBmName, setNewBmName] = useState('')
  const [newBmUser, setNewBmUser] = useState('')
  const [newBmHost, setNewBmHost] = useState('')
  const [newBmPort, setNewBmPort] = useState('22')

  const [sessions, setSessions] = useState<Session[]>([])
  const [activeTermSession, setActiveTermSession] = useState<Session | null>(null)

  const termWrapRef = useRef<HTMLDivElement | null>(null)
  const xtermRef = useRef<Terminal | null>(null)
  const fitRef = useRef<FitAddon | null>(null)

  useEffect(() => {
    void loadBookmarks()
  }, [])

  async function loadBookmarks(): Promise<void> {
    try {
      const res = (await window.dh.storeGet({ key: 'ssh_bookmarks' })) as SshBookmark[] | null
      if (res) setBookmarks(res)
    } catch (e) {
      console.error('Failed to load ssh bookmarks', e)
    }
  }

  async function saveBookmarks(next: SshBookmark[]): Promise<void> {
    setBookmarks(next)
    try {
      await window.dh.storeSet({ key: 'ssh_bookmarks', data: next })
    } catch (e) {
      console.error('Failed to save ssh bookmarks', e)
    }
  }

  async function generate(): Promise<void> {
    setBusy(true)
    setStatus('Generating key...')
    try {
      await window.dh.sshGenerate({ target, email })
      setStatus('SSH key generated successfully!')
      await loadPub()
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function loadPub(): Promise<void> {
    setBusy(true)
    setStatus('')
    try {
      const res = (await window.dh.sshGetPub({ target })) as string | null
      setPubKey(res?.trim() ?? '')
      if (!res) setStatus('No public key found yet.')
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function copyPub(): Promise<void> {
    if (!pubKey.trim()) {
      setStatus('No public key to copy.')
      return
    }
    try {
      await navigator.clipboard.writeText(pubKey)
      setStatus('✅ Public key copied to clipboard!')
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e))
    }
  }

  async function testGithub(): Promise<void> {
    setBusy(true)
    setStatus('Testing connection to GitHub...')
    setTestOk(null)
    setTestResult('')
    try {
      const res = (await window.dh.sshTestGithub({ target })) as {
        ok: boolean
        output: string
        code: number | null
      }
      setTestResult(res.output)
      setTestOk(res.ok)
      setStatus(res.ok ? '✅ Connected to GitHub successfully!' : `❌ Test failed (code ${res.code ?? 'n/a'}).`)
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e))
      setTestOk(false)
    } finally {
      setBusy(false)
    }
  }

  function addBookmark(): void {
    if (!newBmName || !newBmHost) return
    const bm: SshBookmark = {
      id: Date.now().toString(),
      name: newBmName.trim(),
      user: newBmUser.trim() || 'root',
      host: newBmHost.trim(),
      port: Number(newBmPort) || 22,
    }
    const next = [...bookmarks, bm]
    void saveBookmarks(next)
    setNewBmName('')
    setNewBmUser('')
    setNewBmHost('')
    setNewBmPort('22')
  }

  function deleteBookmark(id: string): void {
    const next = bookmarks.filter((b) => b.id !== id)
    void saveBookmarks(next)
  }

  // --- Embedded Terminal Logic ---
  
  // Cleanup terminal when unmounting modal
  useEffect(() => {
    if (!activeTermSession || !termWrapRef.current) return
    const el = termWrapRef.current

    const term = new Terminal({
      cursorBlink: true,
      fontFamily: 'JetBrains Mono, monospace',
      fontSize: 13,
      theme: { background: '#0a0a0a', foreground: '#e8e8e8', cursor: '#7c4dff' },
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(el)
    fit.fit()
    xtermRef.current = term
    fitRef.current = fit

    let tid: string | undefined = undefined

    void (async () => {
      const res = (await window.dh.terminalCreate({ cols: term.cols, rows: term.rows })) as
        | { ok: true; id: string }
        | { ok: false; error: string }
      if (!res.ok) {
        term.writeln(`\r\nError creating terminal: ${res.error}`)
        return
      }
      tid = res.id
      // Update session with termId
      setSessions((prev) => prev.map(s => s.id === activeTermSession.id ? { ...s, termId: tid, status: 'connected' } : s))

      // Execute SSH command
      const cmd = `ssh -p ${activeTermSession.port} ${activeTermSession.user}@${activeTermSession.host}\r`
      window.dh.terminalWrite(tid, cmd)
    })()

    const onData = (d: string): void => {
      if (tid) window.dh.terminalWrite(tid, d)
    }
    term.onData(onData)

    const offOut = window.dh.onTerminalData(({ id, data }) => {
      if (id === tid) term.write(data)
    })
    
    const offExit = window.dh.onTerminalExit(({ id }) => {
      if (id === tid) {
        term.writeln('\r\n[session ended]')
        setSessions((prev) => prev.map(s => s.id === activeTermSession.id ? { ...s, status: 'disconnected', termId: undefined } : s))
      }
    })

    const ro = new ResizeObserver(() => {
      fit.fit()
      if (tid) window.dh.terminalResize(tid, term.cols, term.rows)
    })
    ro.observe(el)

    return () => {
      ro.disconnect()
      offOut()
      offExit()
      term.dispose()
      xtermRef.current = null
      fitRef.current = null
    }
  }, [activeTermSession]) // Re-run if we open a new modal for a specific session

  function handleConnect(bm: SshBookmark): void {
    const sId = Date.now().toString()
    const newSession: Session = {
      id: sId,
      bmId: bm.id,
      bmName: bm.name,
      user: bm.user,
      host: bm.host,
      port: bm.port,
      status: 'connecting',
      startTime: Date.now(),
    }
    setSessions((prev) => [newSession, ...prev])
    setActiveTermSession(newSession) // Open modal
  }

  function handleDisconnect(sess: Session): void {
    if (sess.termId) {
      // Send exit sequence and then exit shell to forcefully kill it
      window.dh.terminalWrite(sess.termId, '\r~.\rexit\r')
    }
    setSessions((prev) => prev.map((s) => s.id === sess.id ? { ...s, status: 'disconnected', termId: undefined } : s))
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 32, paddingBottom: 40, alignItems: 'start' }}>
      
      {/* LEFT COLUMN: Setup & Bookmarks */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <header>
          <div className="mono" style={{ color: 'var(--accent)', fontSize: 12, marginBottom: 8 }}>SETTINGS.SSH</div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700 }}>SSH Wizard & Servers</h1>
          <p style={{ color: 'var(--text-muted)', marginTop: 10 }}>
            Set up GitHub securely without terminal commands, and save your remote servers.
          </p>
        </header>

        {/* GitHub SSH Wizard Section */}
        <section>
          <h2 style={{ fontSize: 18, marginBottom: 16 }}>GitHub Setup Wizard</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            
            <div style={card}>
              <div style={stepCircle}>1</div>
              <div>
                <h3 style={stepTitle}>Create Digital ID</h3>
                <p style={stepText}>Generate a secure SSH key to identify your computer to GitHub.</p>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input type="text" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Your GitHub Email (Optional)" style={{ ...inputStyle, flex: 1 }} />
                  <button type="button" style={btnPrimary} onClick={() => void generate()} disabled={busy}>Generate Key</button>
                </div>
              </div>
            </div>

            <div style={card}>
              <div style={stepCircle}>2</div>
              <div style={{ flex: 1 }}>
                <h3 style={stepTitle}>Add to GitHub</h3>
                <p style={stepText}>Copy your public key and paste it into GitHub's SSH settings.</p>
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <button type="button" style={btn} onClick={() => { void loadPub().then(copyPub) }} disabled={busy}>Load & Copy Key</button>
                  <button type="button" style={btn} onClick={() => void window.dh.openExternal('https://github.com/settings/ssh/new')}>Open GitHub Settings</button>
                </div>
                {pubKey && <textarea readOnly value={pubKey} style={{ ...area, marginTop: 12 }} />}
              </div>
            </div>

            <div style={card}>
              <div style={stepCircle}>3</div>
              <div style={{ flex: 1 }}>
                <h3 style={stepTitle}>Test Connection</h3>
                <p style={stepText}>Verify that GitHub recognizes your new key.</p>
                <button type="button" style={btnPrimary} onClick={() => void testGithub()} disabled={busy}>Test Connection</button>
                {testOk !== null && (
                  <div style={{ marginTop: 12, padding: 8, borderRadius: 8, background: testOk ? 'rgba(0,255,0,0.1)' : 'rgba(255,0,0,0.1)', color: testOk ? 'var(--green)' : 'var(--orange)' }}>
                    {testOk ? '✅ Success! You can now use git.' : '❌ Failed. Check the output below.'}
                  </div>
                )}
                {testResult && <pre className="mono" style={{ ...pre, marginTop: 8 }}>{testResult}</pre>}
              </div>
            </div>

          </div>
          {status && <div style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 12 }}>{status}</div>}
        </section>

        <hr style={{ border: 0, borderTop: '1px solid var(--border)' }} />

        {/* Bookmarks Section */}
        <section>
          <h2 style={{ fontSize: 18, marginBottom: 16 }}>Saved Servers</h2>
          <div style={{ ...card, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 16, padding: 16 }}>
            <div style={{ flex: 1, minWidth: 150 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Label</div>
              <input value={newBmName} onChange={(e) => setNewBmName(e.target.value)} placeholder="e.g. My VPS" style={inputStyle} />
            </div>
            <div style={{ width: 100 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>User</div>
              <input value={newBmUser} onChange={(e) => setNewBmUser(e.target.value)} placeholder="root" style={inputStyle} />
            </div>
            <div style={{ flex: 1, minWidth: 150 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Host (IP / Domain)</div>
              <input value={newBmHost} onChange={(e) => setNewBmHost(e.target.value)} placeholder="192.168.1.10" style={inputStyle} />
            </div>
            <div style={{ width: 60 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Port</div>
              <input value={newBmPort} onChange={(e) => setNewBmPort(e.target.value)} placeholder="22" style={inputStyle} />
            </div>
            <button type="button" style={btnPrimary} onClick={addBookmark}>Add</button>
          </div>

          {bookmarks.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>No saved servers yet.</div>
          ) : (
            <div style={{ display: 'grid', gap: 8 }}>
              {bookmarks.map((bm) => (
                <div key={bm.id} style={{ ...card, padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 15 }}>{bm.name}</div>
                    <div className="mono" style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>
                      {bm.user}@{bm.host}:{bm.port}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button type="button" style={btn} onClick={() => handleConnect(bm)}>Connect</button>
                    <button type="button" style={btnDanger} onClick={() => deleteBookmark(bm.id)}>Remove</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* RIGHT COLUMN: Connection History & Active Sessions */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <h2 style={{ fontSize: 18, margin: 0, paddingBottom: 8, borderBottom: '1px solid var(--border)' }}>Connection History</h2>
        
        {sessions.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 16, background: 'var(--bg-widget)', borderRadius: 8 }}>
            No connections yet. Click "Connect" on a saved server.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {sessions.map((sess) => (
              <div key={sess.id} style={{ ...card, padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ fontWeight: 600 }}>{sess.bmName}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                    <div style={{
                      width: 8, height: 8, borderRadius: 4,
                      background: sess.status === 'connected' ? 'var(--green)' : sess.status === 'disconnected' ? 'var(--text-muted)' : 'var(--orange)',
                      boxShadow: sess.status === 'connected' ? '0 0 8px var(--green)' : 'none'
                    }} />
                    <span style={{ textTransform: 'capitalize', color: sess.status === 'connected' ? 'var(--green)' : 'var(--text-muted)' }}>
                      {sess.status}
                    </span>
                  </div>
                </div>
                
                <div className="mono" style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                  {sess.user}@{sess.host}:{sess.port}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  Started: {new Date(sess.startTime).toLocaleTimeString()}
                </div>

                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  {sess.status === 'connected' && (
                    <button type="button" style={{ ...btnDanger, padding: '4px 8px', fontSize: 11, flex: 1 }} onClick={() => handleDisconnect(sess)}>
                      Disconnect
                    </button>
                  )}
                  {sess.status === 'connected' && (
                    <button type="button" style={{ ...btn, padding: '4px 8px', fontSize: 11, flex: 1 }} onClick={() => setActiveTermSession(sess)}>
                      Show Terminal
                    </button>
                  )}
                  {sess.status === 'disconnected' && (
                    <button type="button" style={{ ...btn, padding: '4px 8px', fontSize: 11, flex: 1 }} onClick={() => setSessions(prev => prev.filter(s => s.id !== sess.id))}>
                      Clear
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Terminal Modal overlay */}
      {activeTermSession && (
        <div style={modalOverlay}>
          <div style={modalContent}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ fontWeight: 600 }}>SSH Session: {activeTermSession.bmName}</div>
              <button type="button" style={{ background: 'transparent', border: 'none', color: 'var(--text)', cursor: 'pointer', fontSize: 20 }} onClick={() => setActiveTermSession(null)}>
                ×
              </button>
            </div>
            <div style={{ flex: 1, minHeight: 400, background: '#0a0a0a', borderRadius: 8, padding: 8, overflow: 'hidden' }}>
              <div ref={termWrapRef} style={{ width: '100%', height: '100%' }} />
            </div>
          </div>
        </div>
      )}

    </div>
  )
}

const card = {
  background: 'var(--bg-widget)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius)',
  display: 'flex',
  alignItems: 'flex-start',
  gap: 16,
  padding: 16,
}

const stepCircle = {
  width: 28,
  height: 28,
  borderRadius: 14,
  background: 'var(--accent)',
  color: '#000',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontWeight: 700,
  fontSize: 14,
  flexShrink: 0,
}

const stepTitle = {
  margin: '0 0 4px 0',
  fontSize: 15,
  fontWeight: 600,
}

const stepText = {
  margin: '0 0 12px 0',
  fontSize: 13,
  color: 'var(--text-muted)',
  lineHeight: 1.4,
}

const inputStyle = {
  width: '100%',
  background: 'var(--bg-input)',
  border: '1px solid var(--border)',
  color: 'var(--text)',
  padding: '8px 12px',
  borderRadius: 6,
  fontSize: 13,
}

const btn = {
  border: '1px solid var(--border)',
  background: 'var(--bg-input)',
  color: 'var(--text)',
  borderRadius: 6,
  padding: '8px 16px',
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 500,
}

const btnPrimary = {
  ...btn,
  background: 'var(--accent)',
  color: '#000',
  border: '1px solid var(--accent)',
}

const btnDanger = {
  ...btn,
  color: 'var(--orange)',
  borderColor: 'rgba(255, 69, 58, 0.3)',
}

const area = {
  ...inputStyle,
  minHeight: 60,
  fontFamily: 'monospace',
  fontSize: 12,
}

const pre = {
  margin: 0,
  whiteSpace: 'pre-wrap' as const,
  fontSize: 12,
  maxHeight: 150,
  overflow: 'auto' as const,
  background: 'var(--bg-input)',
  padding: 8,
  borderRadius: 6,
  border: '1px solid var(--border)',
}

const modalOverlay: React.CSSProperties = {
  position: 'fixed',
  top: 0, left: 0, right: 0, bottom: 0,
  background: 'rgba(0,0,0,0.6)',
  backdropFilter: 'blur(4px)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 9999,
  padding: 40,
}

const modalContent: React.CSSProperties = {
  width: '100%',
  maxWidth: 900,
  height: '100%',
  maxHeight: 600,
  background: 'var(--bg-widget)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: 20,
  display: 'flex',
  flexDirection: 'column',
  boxShadow: '0 20px 40px rgba(0,0,0,0.4)',
}
