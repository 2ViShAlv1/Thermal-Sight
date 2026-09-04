import { useEffect, useRef, useState } from 'react'
import { Card, ClassPill, Empty, Loading, Note } from './ui'
import { fmt, get } from '../lib/api'
import { useColors } from '../lib/theme'
import LiveMap from './LiveMap'

const HOUR_OPTIONS = [3, 6, 12, 24]

// Poll interval yahan 45s hai - backend ka apna cache 60s ka hai, to
// isse zyada tez poll karne ka koi fayda nahi, NASA ko extra load bhi
// nahi padta (backend cache hi absorb kar leta hai).
const POLL_MS = 45_000

function timeAgo(iso) {
  if (!iso) return '—'
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  return `${Math.round(s / 3600)}h ago`
}

/** Compass arrow, north-up, rotated by bearing (0deg = north = pointing up). */
function DirectionCell({ r }) {
  if (r.model_pred !== 'FOREST_FIRE') return <span className="dim">—</span>
  if (r.spread_direction == null) {
    return <span className="dim" title="Not enough spatial spread to estimate a direction yet">insufficient movement</span>
  }
  return (
    <span title={`${r.spread_bearing_deg}° · moved ${fmt.int(r.spread_m)} m`}>
      <span
        style={{ display: 'inline-block', transform: `rotate(${r.spread_bearing_deg}deg)`, marginRight: 4 }}
      >
        ↑
      </span>
      {r.spread_direction}
    </span>
  )
}

/** Current wind at that location, and whether it agrees with the
 *  satellite-derived spread direction (independent cross-check). */
function WindCell({ r }) {
  if (r.model_pred !== 'FOREST_FIRE' || r.wind_speed_kmh == null) {
    return <span className="dim">—</span>
  }
  return (
    <span>
      {fmt.dec(r.wind_speed_kmh, 0)} km/h → {r.wind_push_compass}
      {r.wind_agrees === true && (
        <span className="tag ai" style={{ marginLeft: 6 }} title="Wind direction matches the satellite-observed spread direction">
          AGREES
        </span>
      )}
      {r.wind_agrees === false && (
        <span className="dim" style={{ marginLeft: 6 }} title="Current wind doesn't match the observed spread - direction may be shifting">
          differs
        </span>
      )}
    </span>
  )
}

/** Ek hi table dono jagah (asli live + demo) use hoti hai - taaki demo
 *  bilkul wahi dikhe jo asli data dikhta, sirf banner alag ho. */
function DetectionsTable({ items }) {
  return (
    <div className="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th>Region</th>
            <th>Rule (history)</th>
            <th>Model (live, fresh)</th>
            <th className="n">Confidence</th>
            <th className="n">FRP</th>
            <th>Spread direction</th>
            <th>Wind</th>
            <th>Site</th>
            <th>Time (UTC)</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r, i) => (
            <tr key={`${r.source_id || 'new'}-${i}`}>
              <td>{fmt.title(r.region)}</td>
              <td><ClassPill k={r.status_key} /></td>
              <td>
                {r.model_pred
                  ? <ClassPill k={r.model_pred} />
                  : <span className="dim">building history…</span>}
                {r.model_pred && r.model_pred !== r.status_key && (
                  <span className="tag ai" style={{ marginLeft: 7 }}>DIFFERS</span>
                )}
              </td>
              <td className="n">
                {r.model_confidence ? fmt.pct(r.model_confidence) : '—'}
              </td>
              <td className="n">{fmt.dec(r.frp)} MW</td>
              <td><DirectionCell r={r} /></td>
              <td><WindCell r={r} /></td>
              <td>{r.industry_name || <span className="dim">—</span>}</td>
              <td className="num">
                {r.timestamp_utc ? r.timestamp_utc.slice(11, 16) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function LiveTab() {
  // 24h default (3h nahi) - Jharia jaisi kam-frequency reference jagah
  // (~2 detections/din) ek chhoti 3h window mein aksar miss ho jaati
  // thi, demo mein khaali dikhta tha bina kisi wajah ke.
  const [hours, setHours] = useState(24)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [tick, setTick] = useState(0)   // "refresh now" button ke liye
  const colors = useColors()

  // Demo alag state mein - asli live polling ko disturb nahi karta.
  const [demo, setDemo] = useState(null)
  const [demoLoading, setDemoLoading] = useState(false)

  // inFlight ek REF hai, state nahi - state hota to uska update ek
  // aur render trigger karta aur poll effect dobara chal jata.
  const inFlight = useRef(false)

  useEffect(() => {
    let alive = true
    inFlight.current = true
    setLoading(true)
    get(`/live?hours=${hours}`)
      .then((d) => alive && (setData(d), setError(null)))
      .catch((e) => alive && setError(e.message))
      .finally(() => {
        inFlight.current = false
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [hours, tick])

  useEffect(() => {
    // Agar pichhli request abhi bhi chal rahi hai to naya poll SKIP
    // karo - warna dheemi request ke waqt requests server pe dher lag
    // jaati hain (ek live check = 18 NASA calls).
    const id = setInterval(() => {
      if (!inFlight.current) setTick((t) => t + 1)
    }, POLL_MS)
    return () => clearInterval(id)
  }, [])

  const runDemo = () => {
    setDemoLoading(true)
    get('/live/demo')
      .then(setDemo)
      .catch((e) => setDemo({ error: e.message }))
      .finally(() => setDemoLoading(false))
  }

  if (loading && !data) return <Loading label="Requesting live data from NASA FIRMS…" />

  if (error) {
    return (
      <Card title="Live monitor">
        <Note kind="warn">
          Live feed unavailable right now: {error}. This is likely a
          network/API-key issue - the rest of the dashboard is unaffected.
        </Note>
      </Card>
    )
  }

  const items = data?.items || []
  const disasters = data?.disasters || []

  return (
    <>
      {demo && !demo.error && (
        <Card
          style={{ marginBottom: 16, borderColor: colors.accent }}
          title="⚠ DEMO — simulated, not real NASA data"
          sub={demo.note}
          right={
            <button className="icon-btn" onClick={() => setDemo(null)}>
              Hide demo
            </button>
          }
        >
          <LiveMap items={demo.items} />
          <DetectionsTable items={demo.items} />
        </Card>
      )}

      <Card
        title="Live monitor"
        sub="NASA FIRMS' near-real-time feed - when a new detection lands on a known source, the model reclassifies it right now."
        right={
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
            {HOUR_OPTIONS.map((h) => (
              <button
                key={h}
                className="icon-btn"
                style={h === hours ? { borderColor: colors.accent, color: colors.accent } : {}}
                onClick={() => setHours(h)}
              >
                {h}h
              </button>
            ))}
            <button className="icon-btn" onClick={() => setTick((t) => t + 1)}>
              Refresh
            </button>
            <button className="icon-btn" onClick={runDemo} disabled={demoLoading}>
              {demoLoading ? 'Simulating…' : 'Simulate (demo)'}
            </button>
          </div>
        }
      >
        <div className="dim" style={{ marginBottom: 12 }}>
          Checked: {timeAgo(data?.checked_at)}
          {data?.cached && ` (cached, ${data.cache_age_s}s old)`}
          {' · '}
          {data?.regions_checked?.length || 0} regions (5 trained + 1
          reference region, Jharia-Dhanbad coalfield - included purely to
          help confirm this feed is genuinely live. Its activity is bursty
          (some days many detections, some days none), so an empty result
          here doesn't mean the feed is broken)
        </div>

        {items.length === 0 ? (
          <Empty>
            No new hotspots anywhere in the last {hours}h, including the
            reference region - the satellite feed itself is still active
            (see "Checked" above); this specific area's activity is bursty
            by nature. Click
            "Simulate (demo)" above to see how the system reacts when a
            detection does arrive.
          </Empty>
        ) : (
          <>
            {disasters.length > 0 && (
              <Note kind="warn" style={{ marginBottom: 12 }}>
                <div>
                  <b>{disasters.length} disaster-level spike(s)</b> detected -
                  either above the absolute FRP floor (50 MW), or {'>'}1.5×
                  hotter than that site's own historical record.
                </div>
                {!data.email_configured ? (
                  <div className="dim" style={{ marginTop: 6 }}>
                    Email alerts are not configured - the background monitor
                    (<code>--loop</code>) would only log these to console and
                    <code>outputs/disaster_alerts.log</code>.
                  </div>
                ) : (
                  <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
                    {disasters.map((d, i) => (
                      <li key={`${d.source_id || i}`}>
                        {fmt.title(d.region)} · {d.status} · {fmt.dec(d.frp)} MW —{' '}
                        {d.last_emailed
                          ? `emailed ${timeAgo(d.last_emailed)}`
                          : 'not yet emailed (background monitor must be running with --loop)'}
                      </li>
                    ))}
                  </ul>
                )}
              </Note>
            )}
            <LiveMap items={items} />
            <DetectionsTable items={items} />
          </>
        )}

        <div className="dim" style={{ marginTop: 14, lineHeight: 1.55 }}>
          This is <b>not forecasting</b> - it does not predict a fire
          tomorrow or the day after. It reports: <i>right now, this location
          is hot, and here is what our model (history + the new detection,
          combined into fresh features) says about it.</i> For a location
          with no match at all, the model is deliberately not run - too
          little history to give a confident answer honestly.
          <br /><br />
          <b>Spread direction</b> (forest fires only) compares the centroid
          of a source's earlier detections against its more recent ones -
          shown only once the fire has genuinely moved at least 200m, so
          satellite pixel noise doesn't get reported as a direction.
          <b>Wind</b> is live data from Open-Meteo for that exact location -
          "AGREES" means the current wind is blowing toward the same
          direction the fire has been observed spreading, an independent
          cross-check that the satellite-derived direction is real.
        </div>
      </Card>
    </>
  )
}
