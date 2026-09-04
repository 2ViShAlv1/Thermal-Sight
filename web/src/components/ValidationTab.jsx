import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Card, ChartTip, Empty, Loading, Note, Stat } from './ui'
import { fmt, useApi } from '../lib/api'
import { classColor, CLASS_LABEL, useColors } from '../lib/theme'

/**
 * metrics.json pipeline ki apni bhasha mein likhi hai ("sab features").
 * UI angrezi mein hai, to yahan naam badal dete hain. Jo naam list mein
 * na ho wo jaisa hai waisa dikh jayega - naya feature set jodne pe UI
 * toota nahi.
 */
const ABLATION_LABEL = {
  'sab features': 'All features',
  'bina lc_class': 'Without land cover',
  'bina lc + dist': 'Without land cover + distance',
  'sirf FIRMS (koi naksha nahi)': 'Satellite data only (no map layers)',
}

/** Har check ka apna sirnaam - "1 · ..." wala. */
function Check({ n, title, children }) {
  return (
    <Card style={{ marginTop: 16 }}>
      <div className="card-head">
        <h3>
          <span style={{ color: 'var(--muted)', marginRight: 8 }}>{n}</span>
          {title}
        </h3>
      </div>
      {children}
    </Card>
  )
}

export default function ValidationTab() {
  const { data, loading } = useApi('/validation', [])
  const colors = useColors()

  if (loading && !data) return <Loading label="Loading evidence…" />
  if (!data) return <Empty>No metrics yet — run the pipeline.</Empty>

  const gold = data.gold || {}
  const na = data.nasa_agreement || {}
  const nm = data.nasa_model || {}
  const vlm = data.vlm || {}
  const vint = data.vlm_integration || {}
  const report = gold.report || {}

  const shap = Object.entries(data.shap_importance || {})
    .slice(0, 8)
    .map(([k, v]) => ({ name: k, value: v }))

  const night = Object.entries(data.night_ratio_by_class || {}).map(([k, v]) => ({
    key: k,
    name: CLASS_LABEL[k] || k,
    value: v,
  }))

  return (
    <>
      <div className="muted" style={{ marginBottom: 4 }}>
        Five checks, each with a different failure mode. None of them reuses
        the rules that produced the labels.
      </div>

      {/* ---------------------------------------------------- 1 */}
      <Check n="1" title="Human-verified labels">
        <div className="grid g4" style={{ marginBottom: 14 }}>
          <Stat label="Accuracy" value={fmt.pct(gold.accuracy, 1)} />
          <Stat label="Macro F1" value={fmt.dec(gold.macro_f1, 3)} />
          <Stat label="Test set" value={`${fmt.int(gold.n)} sources`} />
          <Stat label="Random baseline" value="33%" />
        </div>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Class</th>
                <th className="n">Precision</th>
                <th className="n">Recall</th>
                <th className="n">F1</th>
                <th className="n">n</th>
              </tr>
            </thead>
            <tbody>
              {['INDUSTRIAL', 'FOREST_FIRE', 'AGRI_BURN'].map((k) =>
                report[k] ? (
                  <tr key={k}>
                    <td>
                      <span
                        className="dot"
                        style={{
                          display: 'inline-block', width: 8, height: 8,
                          borderRadius: '50%', marginRight: 8,
                          background: classColor(k, colors),
                        }}
                      />
                      {CLASS_LABEL[k]}
                    </td>
                    <td className="n">{fmt.dec(report[k].precision, 2)}</td>
                    <td className="n">{fmt.dec(report[k].recall, 2)}</td>
                    <td className="n">{fmt.dec(report[k]['f1-score'], 2)}</td>
                    <td className="n">{fmt.int(report[k].support)}</td>
                  </tr>
                ) : null
              )}
            </tbody>
          </table>
        </div>
        <div className="dim" style={{ marginTop: 10, lineHeight: 1.55 }}>
          Labelled by hand from satellite imagery, held out entirely from
          training. With {fmt.int(gold.n)} samples the 95% confidence interval
          is roughly ±14 points — the headline number is honest but not precise.
        </div>
      </Check>

      {/* ---------------------------------------------------- 2 */}
      <Check n="2" title="Agreement with NASA's own classification">
        <div className="grid g4" style={{ marginBottom: 14 }}>
          <Stat label="Flagged static by FIRMS" value={fmt.int(na.n_flagged_static)} />
          <Stat label="We called industrial" value={fmt.int(na.n_we_called_industrial)} />
          <Stat label="Agreement" value={fmt.pct(na.agreement)} />
          <Stat
            label="Detections covered"
            value={fmt.int(na.detections_covered)}
            delta={
              na.detections_total
                ? `${fmt.pct(na.detections_covered / na.detections_total)} of all`
                : null
            }
          />
        </div>
        <Note kind="good">
          FIRMS assigns every detection a type, where <strong>type 2</strong> means
          “other static land source” — NASA's own term for an industrial heat
          source. <strong>Our rules never read that field.</strong> They use
          distance to mapped industry, night-time share and persistence. The two
          systems agree on <strong>{fmt.pct(na.agreement)}</strong> of cases. This
          is stronger evidence than our own label set, because it comes from
          outside the project.
        </Note>
      </Check>

      {/* ---------------------------------------------------- 3 */}
      <Check n="3" title="Is the model learning, or repeating the rules?">
        {data.ablation?.length ? (
          <>
            <div className="tbl-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Feature set</th>
                    <th className="n">Features</th>
                    <th className="n">Region hold-out F1</th>
                    <th className="n">Gold accuracy</th>
                  </tr>
                </thead>
                <tbody>
                  {data.ablation.map((a) => (
                    <tr key={a.features}>
                      <td>{ABLATION_LABEL[a.features] || a.features}</td>
                      <td className="n">{a.n_features}</td>
                      <td className="n">{fmt.dec(a.region_f1, 3)}</td>
                      <td className="n">{fmt.pct(a.gold_accuracy, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Note kind="warn">
              Our labels come from rules, and the model is given the same
              features those rules use — so a high score may only mean the model
              memorised the rules. We tested it: removing those features
              collapses the region hold-out score from{' '}
              <strong>{fmt.dec(data.ablation[0].region_f1, 3)}</strong> to{' '}
              <strong>
                {fmt.dec(data.ablation[data.ablation.length - 1].region_f1, 3)}
              </strong>
              . That score was reproduction, not understanding, and we do not
              report it as a result. Against human labels the picture is
              different and more useful:{' '}
              <strong>{fmt.pct(data.ablation[0].gold_accuracy, 1)}</strong> with
              map context,{' '}
              <strong>
                {fmt.pct(data.ablation[data.ablation.length - 1].gold_accuracy, 1)}
              </strong>{' '}
              on satellite behaviour alone — still well clear of the 33%
              three-class baseline.
            </Note>
          </>
        ) : (
          <Empty>Run <code>python src/step5_train.py</code>.</Empty>
        )}
      </Check>

      {/* ---------------------------------------------------- 4 */}
      <Check n="4" title="A model trained without any of our rules">
        {nm.vs_human_labels ? (
          <>
            <div className="grid g4" style={{ marginBottom: 14 }}>
              <Stat
                label="Training labels"
                value={fmt.int(nm.n_detections)}
                delta="NASA FIRMS, not ours"
              />
              <Stat label="Rule-derived features" value="0" />
              <Stat
                label="Agreement with human labels"
                value={fmt.pct(nm.vs_human_labels.accuracy, 1)}
              />
              <Stat label="AUC" value={fmt.dec(nm.vs_human_labels.auc, 3)} />
            </div>
            <Note kind="good">
              The ablation above shows our main model partly reproduces its own
              rules. This model is built so it cannot: it trains on NASA's own
              detection types using only per-detection satellite measurements —
              radiative power, the two brightness bands, pixel geometry, day or
              night, month. No land cover, no distance to industry, no
              persistence tier. <strong>None of our rules can leak into it.</strong>{' '}
              Measured against <em>our human</em> labels — two label sets produced
              independently of each other — it reaches{' '}
              <strong>{fmt.pct(nm.vs_human_labels.accuracy, 1)}</strong> accuracy.
            </Note>

            {nm.region_holdout?.length > 0 && (
              <div className="tbl-wrap" style={{ marginTop: 12 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Held-out region</th>
                      <th className="n">Detections</th>
                      <th className="n">Static (type 2)</th>
                      <th className="n">F1</th>
                      <th className="n">AUC</th>
                    </tr>
                  </thead>
                  <tbody>
                    {nm.region_holdout.map((r) => (
                      <tr key={r.held_out}>
                        <td>{fmt.title(r.held_out)}</td>
                        <td className="n">{fmt.int(r.n_test)}</td>
                        <td className="n">{fmt.int(r.n_static)}</td>
                        <td className="n">{r.f1 == null ? '—' : fmt.dec(r.f1, 3)}</td>
                        <td className="n">{r.auc == null ? '—' : fmt.dec(r.auc, 3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="dim" style={{ marginTop: 10, lineHeight: 1.55 }}>
              Reported in full, including where it fails. NASA marks almost no
              static sources outside the thermal belt — one detection in Punjab,
              none in Uttarakhand — so those folds have essentially no positive
              class and their scores are undefined or meaningless. This is a
              limitation of the label coverage, not a result we are hiding.
            </div>
          </>
        ) : (
          <Empty>Run <code>python src/step7_nasa_model.py</code>.</Empty>
        )}
      </Check>

      {/* ---------------------------------------------------- 5 */}
      <Check n="5" title="An independent look at the imagery">
        {vlm.gemini_accuracy ? (
          <>
            <div className="grid g4" style={{ marginBottom: 14 }}>
              <Stat
                label="Vision model vs human labels"
                value={fmt.pct(vlm.gemini_accuracy, 1)}
              />
              <Stat label="Rules on the same sources" value={fmt.pct(vlm.rule_accuracy, 1)} />
              <Stat
                label="Answered"
                value={`${fmt.int(vlm.n_answered)}/${fmt.int(vlm.n)}`}
                delta="declined the rest"
              />
              <Stat label="Queue sources resolved" value={fmt.int(vint.n_labelled || 0)} />
            </div>
            <Note kind="good">
              Every check above reasons over the same tabular features: distance,
              night share, persistence, land cover. This one does not. A
              vision-language model is shown the{' '}
              <strong>satellite image itself</strong>, with the detection marked,
              and asked what is physically at that point. It never sees a single
              one of our features, thresholds or labels. On the human-labelled set
              it agrees <strong>{fmt.pct(vlm.gemini_accuracy, 1)}</strong> of the
              time against <strong>{fmt.pct(vlm.rule_accuracy, 1)}</strong> for the
              rules — and, more usefully, it answers where the rules produce
              nothing at all.
            </Note>
            {vint.n_conflicts > 0 && (
              <Note kind="warn">
                <strong>
                  {fmt.int(vint.n_conflicts)} sources where the rules and the
                  vision model disagree outright.
                </strong>{' '}
                The rule label is kept — the vision model is not authoritative
                enough to overturn a matched rule — but these are flagged, because
                a disagreement between two independent methods is the single most
                informative thing a human reviewer can spend time on.
              </Note>
            )}
            <div className="dim" style={{ marginTop: 10, lineHeight: 1.55 }}>
              Measured on {fmt.int(vlm.n_answered)} answered sources, so the
              interval is wide — roughly ±12 points. The honest reading is{' '}
              <em>beats the rules and covers cases they cannot</em>, not a precise
              figure. Answers of <em>water</em>, <em>barren</em>, <em>urban</em> or{' '}
              <em>unclear</em> map to no class and are left in the queue rather
              than forced into one.
            </div>
          </>
        ) : (
          <Empty>
            Run <code>python src/step4d_gemini.py --validate</code>.
          </Empty>
        )}
      </Check>

      {/* ------------------------------------------------ charts */}
      <div className="grid g2" style={{ marginTop: 16 }}>
        <Card
          title="The discriminating signal"
          sub="Industrial plant runs around the clock; agricultural burning does not happen at night."
        >
          <ResponsiveContainer width="100%" height={215}>
            <BarChart
              data={night}
              layout="vertical"
              margin={{ top: 4, right: 40, left: 4, bottom: 0 }}
            >
              <CartesianGrid stroke={colors.grid} horizontal={false} />
              <XAxis
                type="number"
                domain={[0, 1]}
                tickFormatter={(v) => `${Math.round(v * 100)}%`}
                tickLine={false}
                axisLine={{ stroke: colors.axis }}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={132}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                cursor={{ fill: colors.grid, fillOpacity: 0.45 }}
                content={<ChartTip fmtVal={(v) => `${(v * 100).toFixed(0)}% at night`} />}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={26} isAnimationActive={false}>
                {night.map((d) => (
                  <Cell key={d.key} fill={classColor(d.key, colors)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="dim" style={{ lineHeight: 1.55 }}>
            Mean night-time share of detections, by class. Each bar is
            labelled — colour is never the only cue.
          </div>
        </Card>

        <Card
          title="What the model actually relies on"
          sub="Mean absolute SHAP value — how much each feature moved the answer."
        >
          <ResponsiveContainer width="100%" height={215}>
            <BarChart
              data={shap}
              layout="vertical"
              margin={{ top: 4, right: 20, left: 4, bottom: 0 }}
            >
              <CartesianGrid stroke={colors.grid} horizontal={false} />
              <XAxis type="number" tickLine={false} axisLine={{ stroke: colors.axis }} />
              <YAxis
                type="category"
                dataKey="name"
                width={132}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                cursor={{ fill: colors.grid, fillOpacity: 0.45 }}
                content={<ChartTip fmtVal={(v) => v.toFixed(3)} />}
              />
              <Bar dataKey="value" fill={colors.accent} radius={[0, 4, 4, 0]}
                 maxBarSize={16} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
          <div className="dim" style={{ lineHeight: 1.55 }}>
            Land cover and distance to industry dominate — which is exactly
            what check 3 above is about.
          </div>
        </Card>
      </div>
    </>
  )
}
