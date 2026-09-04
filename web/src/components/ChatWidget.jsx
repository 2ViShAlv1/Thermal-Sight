import { useEffect, useRef, useState } from 'react'
import { useColors } from '../lib/theme'

// Groq (primary) usually answers in 1-3s. Timeout generous rakha hai
// kyunki agar Groq fail ho to backend Gemini pe girta hai, jo free
// tier ki wajah se kabhi 30-50s bhi le sakta hai (high-demand 503).
const REQUEST_TIMEOUT_MS = 60_000

function SparkleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  )
}

const SUGGESTIONS = [
  'Which region has the most industrial sites?',
  'How accurate is the model?',
  'Why do sources go to the review queue?',
]

export default function ChatWidget() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const colors = useColors()
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, loading])

  const send = async (question) => {
    const q = (question ?? input).trim()
    if (!q || loading) return

    setMessages((m) => [...m, { role: 'user', text: q }])
    setInput('')
    setLoading(true)

    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
        signal: controller.signal,
      })
      const data = await r.json()
      if (!r.ok) throw new Error(data.error || `${r.status}`)
      setMessages((m) => [...m, { role: 'bot', text: data.answer }])
    } catch (e) {
      const msg = e.name === 'AbortError'
        ? "That took too long to answer - the free-tier model may be under heavy load. Try again in a moment."
        : `Couldn't get an answer: ${e.message}`
      setMessages((m) => [...m, { role: 'error', text: msg }])
    } finally {
      clearTimeout(timer)
      setLoading(false)
    }
  }

  return (
    <>
      <button
        className="icon-btn"
        onClick={() => setOpen((o) => !o)}
        title="Ask a question about this dashboard's data"
        style={{
          position: 'fixed', right: 20, bottom: 20, zIndex: 1200,
          borderRadius: 999, width: 52, height: 52, padding: 0,
          justifyContent: 'center', background: colors.accent, color: '#fff',
          border: 'none', boxShadow: '0 4px 16px rgba(0,0,0,.25)',
        }}
      >
        {open ? <CloseIcon /> : <SparkleIcon />}
      </button>

      {open && (
        <div
          style={{
            position: 'fixed', right: 20, bottom: 82, zIndex: 1200,
            width: 360, maxWidth: 'calc(100vw - 40px)', maxHeight: '70vh',
            display: 'flex', flexDirection: 'column',
            background: colors.surface, border: `1px solid ${colors.grid}`,
            borderRadius: 14, boxShadow: '0 8px 32px rgba(0,0,0,.3)', overflow: 'hidden',
          }}
        >
          <div style={{ padding: '12px 14px', borderBottom: `1px solid ${colors.grid}` }}>
            <div style={{ fontWeight: 650 }}>Ask about this data</div>
            <div className="dim" style={{ fontSize: 12 }}>
              Answers only from this dashboard's real numbers - no guessing.
            </div>
          </div>

          <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 10, minHeight: 160 }}>
            {messages.length === 0 && (
              <div>
                <div className="dim" style={{ fontSize: 13, marginBottom: 8 }}>
                  Try asking:
                </div>
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    className="icon-btn"
                    style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: 6, whiteSpace: 'normal' }}
                    onClick={() => send(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                style={{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%',
                  padding: '8px 11px',
                  borderRadius: 10,
                  fontSize: 13.5,
                  lineHeight: 1.5,
                  background: m.role === 'user' ? colors.accent
                            : m.role === 'error' ? 'transparent' : colors.grid,
                  color: m.role === 'user' ? '#fff'
                       : m.role === 'error' ? colors.critical : colors.text,
                  border: m.role === 'error' ? `1px solid ${colors.critical}` : 'none',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {m.text}
              </div>
            ))}
            {loading && (
              <div className="dim" style={{ fontSize: 13, alignSelf: 'flex-start' }}>
                Thinking…
              </div>
            )}
          </div>

          <form
            style={{ display: 'flex', gap: 6, padding: 10, borderTop: `1px solid ${colors.grid}` }}
            onSubmit={(e) => { e.preventDefault(); send() }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question…"
              disabled={loading}
              style={{
                flex: 1, padding: '8px 10px', borderRadius: 8,
                border: `1px solid ${colors.grid}`, background: 'transparent',
                color: colors.text, fontSize: 13.5,
              }}
            />
            <button className="icon-btn" type="submit" disabled={loading || !input.trim()}>
              Send
            </button>
          </form>
        </div>
      )}
    </>
  )
}
