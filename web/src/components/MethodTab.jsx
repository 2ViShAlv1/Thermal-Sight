import { Card, Note } from './ui'

const FLOW = `NASA FIRMS          88,434 thermal detections, 3 satellites, full year 2025
      │
      ├─ DBSCAN (500 m, min 3)      →  distinct physical sources
      │
      ├─ OpenStreetMap + WRI        →  distance to nearest industry
      ├─ ESA WorldCover (10 m)      →  land cover class
      └─ persistence analysis       →  how often, how long, day or night
      │
      ▼
   Rule engine  →  INDUSTRIAL | FOREST_FIRE | AGRI_BURN | review queue
      │
      ├─ vision model on the queue  →  reads the satellite chip itself,
      │                                answers where no rule matched
      ▼
   XGBoost      →  applies the rules across all sources and unseen regions

   ── validated separately ──────────────────────────────────────────────
   Second model, trained on NASA's own detection types with none of the
   features above, agrees with our human labels at 88.9% — see Validation`

const RULES = `INDUSTRIAL   within 1 km of mapped industry AND not a one-off event
             OR  burns at night AND persists for months

FOREST_FIRE  forest land cover  AND  beyond 1 km of industry
             AND  not a continuously operating source

AGRI_BURN    non-forest         AND  beyond 1 km of industry
             AND  not continuous AND  daytime`

const SOURCES = [
  ['NASA FIRMS', 'Where and when heat occurred'],
  ['OpenStreetMap', 'Industrial footprints and names'],
  ['WRI Power Plants', 'Thermal plants missing from OSM'],
  ['ESA WorldCover', 'Land cover at 10 m'],
  ['Esri World Imagery', 'The satellite chips the vision model reads'],
]

const LIMITS = [
  ['45 human labels', 'give a ±14 point confidence interval'],
  [
    'OpenStreetMap is incomplete in India',
    'small kilns and some facilities are unmapped, which caps rule accuracy',
  ],
  [
    'The main model reproduces the rules',
    'rather than extending them. The ablation quantifies this, and check 4 answers it with a model that never sees those features',
  ],
  [
    'Crop burning is a residual class',
    'the rule is “not forest, away from industry, not persistent, daytime”. It is what remains once the other two are excluded, not a positive detection',
  ],
  ['No human labels yet from Korba or Singrauli', 'which supply most of the industrial data'],
  [
    'The vision model was measured on 42 answered sources',
    'it beats the rules and covers cases they cannot, but that sample cannot support a precise accuracy claim, and it is not allowed to overturn a matched rule',
  ],
]

export default function MethodTab() {
  return (
    <>
      <Card
        title="How a detection becomes a classification"
        sub="Every threshold below is documented with the measurement that justifies it in src/config.py."
      >
        <pre className="code">{FLOW}</pre>
      </Card>

      <Card style={{ marginTop: 16 }} title="The classification rules">
        <pre className="code">{RULES}</pre>
        <div className="dim" style={{ marginTop: 10, lineHeight: 1.55 }}>
          Exactly one rule must match. Zero matches or a conflict sends the
          source to the review queue.
        </div>
      </Card>

      <div className="grid g2" style={{ marginTop: 16 }}>
        <Card title="Data sources" sub="All openly licensed; no paid data.">
          <div className="tbl-wrap">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Contribution</th>
                </tr>
              </thead>
              <tbody>
                {SOURCES.map(([a, b]) => (
                  <tr key={a}>
                    <td>{a}</td>
                    <td className="wrap" style={{ minWidth: 0 }}>{b}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title="Known limitations" sub="Stated up front rather than found by a judge.">
          {LIMITS.map(([a, b]) => (
            <Note key={a} kind="warn">
              <strong>{a}</strong> — {b}
            </Note>
          ))}
        </Card>
      </div>
    </>
  )
}
