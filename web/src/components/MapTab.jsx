import MapView from './MapView'
import { Card, Empty, Loading, Note } from './ui'
import { classColor, CLASS_LABEL, useColors } from '../lib/theme'
import { fmt, qs, useApi } from '../lib/api'

export default function MapTab({ filters, nMap, raw = false }) {
  const { regions, classes, minDet } = filters
  // raw ke waqt classes bheje hi nahi jaate - backend wahan class
  // filter lagata hi nahi, aur query string mein rakhna sirf yeh
  // jhooth bolega ki filter kaam kar raha hai.
  const query = qs({ regions, classes: raw ? null : classes,
                     min_det: minDet, limit: nMap, raw: raw || null })
  const { data, loading } = useApi(`/sources${query}`, [query])
  const colors = useColors()

  if (loading && !data) return <Loading label="Loading sources…" />
  if (!data) return <Empty>No data.</Empty>

  const counts = {}
  for (const c of Object.keys(CLASS_LABEL)) counts[c] = 0
  for (const it of data.items) counts[it.klass] = (counts[it.klass] || 0) + 1

  return (
    <div className="map-layout">
      <div>
        <div className="muted" style={{ marginBottom: 11 }}>
          <b className="num" style={{ color: 'var(--text-primary)' }}>
            {fmt.int(data.total_matching)}
          </b>{' '}
          sources match the current filters — drawing the{' '}
          <b className="num" style={{ color: 'var(--text-primary)' }}>
            {fmt.int(data.returned)}
          </b>{' '}
          largest.
        </div>
        {data.items.length ? (
          <MapView items={data.items} raw={raw} />
        ) : (
          <Card><Empty>Nothing matches these filters.</Empty></Card>
        )}
      </div>

      <div>
        <Card title="Legend">
          {raw ? (
            <>
              <div style={{ display: 'flex', gap: 9, alignItems: 'baseline' }}>
                <span
                  className="dot"
                  style={{
                    width: 10, height: 10, borderRadius: '50%', flex: 'none',
                    background: 'var(--muted)', transform: 'translateY(1px)',
                  }}
                />
                <div style={{ fontSize: '0.87rem' }}>Thermal detection</div>
              </div>
              <div className="dim" style={{ marginTop: 12, lineHeight: 1.5 }}>
                Every point is identical. No class information exists in
                the raw feed.
              </div>
            </>
          ) : (
            Object.entries(CLASS_LABEL).map(([k, label]) => (
            <div key={k} style={{ display: 'flex', gap: 9, alignItems: 'baseline',
                                  marginBottom: 9 }}>
              <span
                className="dot"
                style={{
                  width: 10, height: 10, borderRadius: '50%', flex: 'none',
                  background: classColor(k, colors), transform: 'translateY(1px)',
                }}
              />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: '0.87rem' }}>{label}</div>
                <div className="dim num">{fmt.int(counts[k] || 0)} drawn</div>
              </div>
            </div>
            ))
          )}
          {!raw && (
            <div className="dim" style={{ marginTop: 12, lineHeight: 1.5 }}>
              Marker size scales with detection count.
            </div>
          )}
        </Card>

        <Card style={{ marginTop: 14 }}>
          <a
            className="icon-btn"
            style={{ width: '100%', textDecoration: 'none' }}
            href={`/api/export${qs({ regions, classes: raw ? null : classes,
                                     min_det: minDet, raw: raw || null })}`}
          >
            Export view (GeoJSON)
          </a>
          <div className="dim" style={{ marginTop: 9, lineHeight: 1.5 }}>
            Opens in QGIS. Exports every matching source, not just the
            ones drawn.
          </div>
        </Card>

        <Note kind="info" style={{ marginTop: 14 }}>
          {raw
            ? 'This is the feed as it arrives. Switch to “After classification” to see what the system resolves it into.'
            : 'Grey markers are sources no rule matched. The system leaves them unclassified on purpose.'}
        </Note>
      </div>
    </div>
  )
}
