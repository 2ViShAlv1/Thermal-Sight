import { useMemo, useState } from 'react'
import { fmt, qs, useApi } from './lib/api'
import { classColor, CLASS_LABEL, useColors, useTheme } from './lib/theme'
import { Loading, Note, Stat } from './components/ui'
import MapTab from './components/MapTab'
import PrioritiesTab from './components/PrioritiesTab'
import AnomaliesTab from './components/AnomaliesTab'
import ValidationTab from './components/ValidationTab'
import MethodTab from './components/MethodTab'
import LiveTab from './components/LiveTab'
import ChatWidget from './components/ChatWidget'

const TABS = [
  ['map', 'Map'],
  ['priorities', 'Inspection priorities'],
  ['live', 'Live'],
  ['anomalies', 'Anomalies'],
  ['validation', 'Validation'],
  ['method', 'Method'],
]

function SunIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round"
         strokeLinejoin="round">
      <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a6.8 6.8 0 0 0 10.5 10.5z" />
    </svg>
  )
}

function FilterIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M3 5h18M6 12h12M10 19h4" />
    </svg>
  )
}

function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      className="icon-btn"
      onClick={toggle}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
    >
      {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
      <span style={{ textTransform: 'capitalize' }}>{next}</span>
    </button>
  )
}

/** Filters. Sirf teen hain, jaan-boojh kar - har extra filter demo mein
 *  ek aur cheez hai jo galat set ho sakti hai. */
function Sidebar({ meta, filters, set, nMap, setNMap, summary, raw, open, close }) {
  const colors = useColors()
  const { regions, classes, minDet } = filters

  const toggleIn = (key, value) => {
    const cur = filters[key]
    set({ ...filters, [key]: cur.includes(value)
      ? cur.filter((x) => x !== value)
      : [...cur, value] })
  }

  return (
    <aside className={open ? 'sidebar open' : 'sidebar'}>
      {/* Sirf chhoti screen pe dikhta hai - wahan sidebar ek drawer hai */}
      <button className="icon-btn only-narrow drawer-close" onClick={close}>
        Done
      </button>

      <div className="side-group">
        <h4>Region</h4>
        {meta.regions.map((r) => (
          <label className="check" key={r}>
            <input
              type="checkbox"
              checked={regions.includes(r)}
              onChange={() => toggleIn('regions', r)}
            />
            {fmt.title(r)}
          </label>
        ))}
      </div>

      <div className={raw ? 'side-group off' : 'side-group'}>
        <h4>Class</h4>
        {Object.keys(CLASS_LABEL).map((c) => (
          <label className="check" key={c}>
            <input
              type="checkbox"
              checked={classes.includes(c)}
              disabled={raw}
              onChange={() => toggleIn('classes', c)}
            />
            <span className="dot" style={{ background: classColor(c, colors) }} />
            {CLASS_LABEL[c]}
            <span className="cnt">{fmt.int(summary?.by_class?.[c] ?? 0)}</span>
          </label>
        ))}
        {raw && (
          <div className="dim" style={{ marginTop: 8, lineHeight: 1.5 }}>
            Raw detections carry no class, so there is nothing to filter
            on here.
          </div>
        )}
      </div>

      <div className="side-group">
        <h4>Minimum detections</h4>
        <input
          className="slider"
          type="range"
          min="1"
          max="200"
          value={minDet}
          onChange={(e) => set({ ...filters, minDet: +e.target.value })}
        />
        <div className="dim num">
          {minDet === 1 ? 'all sources' : `${minDet}+ detections per source`}
        </div>
      </div>

      <div className="side-group">
        <h4>Markers to draw</h4>
        <input
          className="slider"
          type="range"
          min="100"
          max="3000"
          step="100"
          value={nMap}
          onChange={(e) => setNMap(+e.target.value)}
        />
        <div className="dim num">{fmt.int(nMap)} largest</div>
        <div className="dim" style={{ marginTop: 6, lineHeight: 1.5 }}>
          Drawing every source freezes the browser. The largest are
          drawn first.
        </div>
      </div>

      <div className="dim" style={{ lineHeight: 1.55, borderTop: '1px solid var(--border)',
                                    paddingTop: 14 }}>
        Data: NASA FIRMS · OpenStreetMap · WRI Global Power Plant Database ·
        ESA WorldCover. All openly licensed.
      </div>
    </aside>
  )
}

/** Tab URL mein rehta hai (?tab=validation) - refresh pe wahi tab
 *  khulta hai, aur link bhej kar seedha us tab pe bheja ja sakta hai. */
/** Raw ya classified - ye bhi URL mein rehta hai (?view=raw), taaki
 *  demo ke beech refresh ho jaye to wahi nazara wapas aaye. */
function useViewParam() {
  const [raw, setRawState] = useState(
    () => new URLSearchParams(location.search).get('view') === 'raw')
  const setRaw = (v) => {
    setRawState(v)
    const u = new URL(location.href)
    if (v) u.searchParams.set('view', 'raw')
    else u.searchParams.delete('view')
    history.replaceState(null, '', u)
  }
  return [raw, setRaw]
}

function useTabParam() {
  const [tab, setTabState] = useState(() => {
    const t = new URLSearchParams(location.search).get('tab')
    return TABS.some(([k]) => k === t) ? t : 'map'
  })
  const setTab = (t) => {
    setTabState(t)
    const u = new URL(location.href)
    if (t === 'map') u.searchParams.delete('tab')
    else u.searchParams.set('tab', t)
    history.replaceState(null, '', u)
  }
  return [tab, setTab]
}

export default function App() {
  const [tab, setTab] = useTabParam()
  const [raw, setRaw] = useViewParam()
  const [nMap, setNMap] = useState(600)
  // Chhoti screen pe sidebar hamesha chhupa hua tha - yani filters the
  // hi nahi. Ab wo ek drawer hai jo is state se khulta hai.
  const [drawer, setDrawer] = useState(false)
  const [filters, setFilters] = useState(null)

  const meta = useApi('/meta', [])
  const ready = meta.data && filters

  // meta aane ke baad filters ko "sab select" pe set karo - ek hi baar
  if (meta.data && !filters) {
    setFilters({
      regions: meta.data.regions,
      classes: ['INDUSTRIAL', 'FOREST_FIRE', 'AGRI_BURN'],
      minDet: 1,
    })
  }

  const sq = qs({ regions: filters?.regions })
  const { data: summary } = useApi(`/summary${sq}`, [sq, !!filters])

  // Raw view mein sirf Map ka matlab banta hai. Priorities, anomalies
  // aur validation - teeno classification ke BAAD hi wajood mein aate
  // hain. Unhe khula chhodna ye jhooth bolta ki wo raw feed se aaye
  // hain, isliye raw mein wo band rehte hain.
  const shown = raw ? 'map' : tab
  const showRaw = (v) => {
    setRaw(v)
    if (v) setTab('map')
  }

  const content = useMemo(() => {
    if (!ready) return null
    switch (shown) {
      case 'map': return <MapTab filters={filters} nMap={nMap} raw={raw} />
      case 'priorities': return <PrioritiesTab filters={filters} summary={summary} />
      case 'live': return <LiveTab />
      case 'anomalies': return <AnomaliesTab filters={filters} />
      case 'validation': return <ValidationTab />
      default: return <MethodTab />
    }
  }, [shown, raw, filters, nMap, summary, ready])

  if (meta.error)
    return (
      <div className="center">
        <div>Cannot reach the API.</div>
        <code className="dim">uvicorn api.main:app --port 8000</code>
      </div>
    )

  if (!ready) return <Loading label="Starting up…" />

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">🛰️</div>
          <div className="brand-text">
            <div className="t">Thermal Source Classifier</div>
            <div className="s">SIH 26162</div>
          </div>
        </div>
        <div className="topbar-spacer" />
        <div className="dim topbar-meta" style={{ textAlign: 'right', lineHeight: 1.35 }}>
          Calendar year {meta.data.year}
          <br />
          {meta.data.regions.length} regions · {meta.data.n_satellites} VIIRS satellites
        </div>
        <button
          className="icon-btn only-narrow"
          onClick={() => setDrawer(true)}
          aria-label="Open filters"
        >
          <FilterIcon />
          Filters
        </button>
        <ThemeToggle />
      </header>

      <div className="body">
        {drawer && <div className="backdrop" onClick={() => setDrawer(false)} />}
        <Sidebar
          meta={meta.data}
          filters={filters}
          set={setFilters}
          nMap={nMap}
          setNMap={setNMap}
          summary={summary}
          raw={raw}
          open={drawer}
          close={() => setDrawer(false)}
        />

        <main className="main">
          {/* Headline aur view-switch EK hi row mein hain, upar-neeche
              nahi. 1366x768 wale laptop pe (yani zyadatar demo screens)
              alag row rakhne se map fold ke neeche chala jata tha. */}
          <div className="hero">
            <div className="hero-text">
              <h1>Satellites detect heat, not its cause.</h1>
              <p className="lede">
                A refinery flare, a forest fire and a burning field produce the
                same kind of record. This system separates them using
                persistence, night-time behaviour, land context — and, where
                those fall silent, the satellite image itself.
              </p>
            </div>

            {/* Poori pitch ek click mein: pehle kya tha, ab kya hai. */}
            <div className="segmented" role="group" aria-label="View">
              <button
                className="seg"
                aria-pressed={raw}
                onClick={() => showRaw(true)}
              >
                Raw satellite data
              </button>
              <button
                className="seg"
                aria-pressed={!raw}
                onClick={() => showRaw(false)}
              >
                After classification
              </button>
            </div>
          </div>

          <div className="grid g4" style={{ marginBottom: 18 }}>
            {raw ? (
              <>
                <Stat
                  label="Thermal detections"
                  value={fmt.int(summary?.total_detections)}
                  delta="NASA FIRMS"
                />
                <Stat label="Distinguishable" value="None"
                      delta="every point looks identical" />
                <Stat label="Industrial sites" value="Unknown" />
                <Stat label="Actionable output" value="None" />
              </>
            ) : (
              <>
                <Stat
                  label="Thermal detections"
                  value={fmt.int(summary?.total_detections)}
                  delta="NASA FIRMS"
                />
                <Stat
                  label="Distinct sources"
                  value={fmt.int(summary?.n_sources)}
                  delta="after clustering"
                />
                <Stat
                  label="Industrial sites"
                  value={fmt.int(summary?.n_industrial)}
                  delta={
                    summary ? `−${summary.reduction_pct.toFixed(2)}% of raw volume` : null
                  }
                  good
                />
                <Stat
                  label="Flagged for review"
                  value={fmt.int(summary?.n_review)}
                  delta="system declines to guess"
                />
              </>
            )}
          </div>

          {raw && (
            <Note kind="warn" style={{ marginBottom: 18 }}>
              A satellite sees only <strong>temperature</strong>. A refinery
              flare, a forest fire and a burning field produce the same kind
              of record. Switch to <strong>After classification</strong> to
              see what the system resolves them into.
            </Note>
          )}

          <div className="tabs" role="tablist">
            {TABS.map(([k, label]) => (
              <button
                key={k}
                className="tab"
                role="tab"
                aria-selected={shown === k}
                disabled={raw && k !== 'map'}
                title={raw && k !== 'map'
                  ? 'Exists only after classification'
                  : undefined}
                onClick={() => setTab(k)}
              >
                {label}
              </button>
            ))}
          </div>

          {content}
        </main>
      </div>
      <ChatWidget />
    </div>
  )
}
