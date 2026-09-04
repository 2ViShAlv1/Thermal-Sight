import { classColor, CLASS_LABEL, useColors } from '../lib/theme'
import { fmt } from '../lib/api'

export function Card({ title, sub, right, children, style }) {
  return (
    <section className="card" style={style}>
      {(title || right) && (
        <header className="card-head" style={{ display: 'flex', gap: 16 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            {title && <h3>{title}</h3>}
            {sub && <div className="muted">{sub}</div>}
          </div>
          {right}
        </header>
      )}
      {children}
    </section>
  )
}

export function Stat({ label, value, delta, good }) {
  return (
    <div className="stat">
      <div className="k">{label}</div>
      <div className="v num">{value}</div>
      {delta && <div className={good ? 'd good' : 'd'}>{delta}</div>}
    </div>
  )
}

export function Note({ kind = 'info', children, style }) {
  return <div className={`note ${kind}`} style={style}>{children}</div>
}

/** Class ka naam + uska rang. Rang akela kabhi matlab nahi bataata -
 *  har jagah uske saath likha hua naam bhi hota hai. */
export function ClassPill({ k }) {
  const colors = useColors()
  return (
    <span className="pill">
      <span className="dot" style={{ background: classColor(k, colors) }} />
      {CLASS_LABEL[k] || k}
    </span>
  )
}

/** 0..1 wale hisse ke liye - number ke saath ek patli patti. */
export function Meter({ value, color }) {
  const colors = useColors()
  const v = Math.max(0, Math.min(1, value ?? 0))
  return (
    <div className="meter">
      <div className="track">
        <div
          className="fill"
          style={{ width: `${v * 100}%`, background: color || colors.accent }}
        />
      </div>
      <span className="lbl">{fmt.pct(v)}</span>
    </div>
  )
}

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="center">
      <div className="spin" />
      <div>{label}</div>
    </div>
  )
}

export function Empty({ children }) {
  return (
    <div style={{ padding: '28px 8px', textAlign: 'center' }} className="muted">
      {children}
    </div>
  )
}

/** Recharts ka apna tooltip theme nahi maanta - apna bana lete hain. */
export function ChartTip({ active, payload, label, unit = '', fmtVal }) {
  if (!active || !payload?.length) return null
  return (
    <div className="tip">
      <div className="tip-k">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="tip-v" style={{ color: p.color }}>
          {fmtVal ? fmtVal(p.value) : `${fmt.int(p.value)}${unit}`}
        </div>
      ))}
    </div>
  )
}
