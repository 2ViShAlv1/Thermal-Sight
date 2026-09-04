import { Card, Empty, Loading, Meter, Note, Stat } from './ui'
import { fmt, qs, useApi } from '../lib/api'
import { useColors } from '../lib/theme'

export default function PrioritiesTab({ filters, summary }) {
  const { regions } = filters
  const q = qs({ regions, limit: 25 })
  const { data, loading } = useApi(`/priorities${q}`, [q])
  const rq = qs({ regions, limit: 20 })
  const rec = useApi(`/recovered${rq}`, [rq])
  const colors = useColors()

  if (loading && !data) return <Loading label="Ranking sources…" />

  const rows = data?.items || []
  const recovered = rec.data

  return (
    <>
      <Card
        title="Industrial sources ranked for inspection"
        sub="This is the operational output — the list a pollution control board would act on."
      >
        {rows.length === 0 ? (
          <Empty>No industrial sources in the selected regions.</Empty>
        ) : (
          <div className="tbl-wrap">
            <table>
              <thead>
                <tr>
                  <th>Site (OSM)</th>
                  <th>Region</th>
                  <th className="n">Detections</th>
                  <th className="n">Active days</th>
                  <th>Night share</th>
                  <th className="n">Peak FRP</th>
                  <th className="n">Anomaly days</th>
                  <th className="n">Worst spike</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.source_id}>
                    <td>
                      {r.site || <span className="dim">unmapped</span>}
                      {r.label_source === 'vlm' && (
                        <span className="tag ai" style={{ marginLeft: 7 }}>AI</span>
                      )}
                    </td>
                    <td>{fmt.title(r.region)}</td>
                    <td className="n">{fmt.int(r.n_detections)}</td>
                    <td className="n">{fmt.int(r.n_days)}</td>
                    <td><Meter value={r.night_ratio} /></td>
                    <td className="n">{fmt.dec(r.frp_max)}</td>
                    <td className="n">{fmt.int(r.n_anomalies)}</td>
                    <td className="n">
                      {r.worst_anomaly_ratio
                        ? `${fmt.dec(r.worst_anomaly_ratio)}×`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="dim" style={{ marginTop: 10, lineHeight: 1.55 }}>
          Anomaly days count dates where a site's radiative power exceeded
          three times its own baseline. Ranking uses observed behaviour,
          not model confidence — on a task this deterministic the model
          reports ~1.00 confidence for 99% of sources, which carries no
          information.
        </div>
      </Card>

      <div className="grid g3" style={{ marginTop: 16 }}>
        <Stat label="Review queue" value={fmt.int(summary?.n_review)} />
        <Stat
          label="Resolved by vision model"
          value={fmt.int(summary?.n_from_vlm || 0)}
          delta={
            summary?.n_from_vlm
              ? `−${Math.round(
                  (100 * summary.n_from_vlm) /
                    (summary.n_review + summary.n_from_vlm)
                )}% queue`
              : 'not run yet'
          }
          good={!!summary?.n_from_vlm}
        />
        <div className="stat" style={{ display: 'flex', alignItems: 'center' }}>
          <div className="muted" style={{ lineHeight: 1.55 }}>
            No rule matched these sources. They are left unclassified on
            purpose: when the model was allowed to answer here it was
            correct <b style={{ color: 'var(--text-primary)' }}>39%</b> of
            the time, against a{' '}
            <b style={{ color: 'var(--text-primary)' }}>33%</b> baseline for
            three classes.
          </div>
        </div>
      </div>

      {recovered?.n_total_recovered > 0 && (
        <Card
          style={{ marginTop: 16 }}
          title="Recovered from the review queue by satellite imagery"
          sub="The rules read numbers — distance, month, night share. They cannot see a kiln hidden inside a field."
        >
          <Note kind="info">
            These sources had <strong>no rule match at all</strong>. A vision
            model was shown the satellite chip with the detection marked and
            asked what is physically there. Its answer is quoted verbatim so
            a reviewer can overrule it.
          </Note>

          {recovered.items.length === 0 ? (
            <Empty>No recovered industrial sources in the selected regions.</Empty>
          ) : (
            <div className="tbl-wrap" style={{ marginTop: 12 }}>
              <table>
                <thead>
                  <tr>
                    <th>Region</th>
                    <th className="n">Detections</th>
                    <th>Night share</th>
                    <th>Seen as</th>
                    <th className="n">Model conf.</th>
                    <th>Stated reason</th>
                  </tr>
                </thead>
                <tbody>
                  {recovered.items.map((r) => (
                    <tr key={r.source_id}>
                      <td>{fmt.title(r.region)}</td>
                      <td className="n">{fmt.int(r.n_detections)}</td>
                      <td><Meter value={r.night_ratio} /></td>
                      <td>
                        <span className="tag ai">{r.vlm_landuse}</span>
                      </td>
                      <td className="n">{fmt.dec(r.vlm_confidence, 2)}</td>
                      <td className="wrap">{r.vlm_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="dim" style={{ marginTop: 10, lineHeight: 1.55 }}>
            Model confidence is the vision model's own estimate of itself and
            averages 0.90 across answers that include its mistakes — read it
            as commentary, not as a probability. The measured accuracy is in
            the Validation tab.
          </div>
        </Card>
      )}
    </>
  )
}
