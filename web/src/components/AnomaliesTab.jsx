import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Card, ChartTip, Empty, Loading, Stat } from './ui'
import { fmt, qs, useApi } from '../lib/api'
import { useColors } from '../lib/theme'

export default function AnomaliesTab({ filters }) {
  const q = qs({ regions: filters.regions, limit: 30 })
  const { data, loading } = useApi(`/anomalies${q}`, [q])
  const colors = useColors()

  if (loading && !data) return <Loading label="Loading anomalies…" />
  if (!data || !data.n) return <Card><Empty>No anomalies in the selected regions.</Empty></Card>

  return (
    <>
      <div className="grid g4">
        <Stat label="Anomalies" value={fmt.int(data.n)} />
        <Stat label="Distinct sites" value={fmt.int(data.n_sites)} />
        <Stat label="Largest spike" value={`${fmt.dec(data.max_ratio, 0)}×`} />
        <Stat label="Detection threshold" value="3×" delta="of the site's own baseline" />
      </div>

      <Card
        style={{ marginTop: 16 }}
        title="Anomalies by month"
        sub="A site burning far hotter than its own normal is the strongest actionable signal in the dataset."
      >
        <ResponsiveContainer width="100%" height={230}>
          <BarChart data={data.by_month} margin={{ top: 4, right: 8, left: -14, bottom: 0 }}>
            <CartesianGrid stroke={colors.grid} vertical={false} />
            <XAxis dataKey="month" tickLine={false} axisLine={{ stroke: colors.axis }} />
            <YAxis tickLine={false} axisLine={false} width={44} />
            <Tooltip
              cursor={{ fill: colors.grid, fillOpacity: 0.45 }}
              content={<ChartTip unit=" anomalies" />}
            />
            {/* ek hi series hai - legend ki zaroorat nahi, title hi naam hai */}
            <Bar dataKey="count" fill={colors.accent} radius={[4, 4, 0, 0]}
                 maxBarSize={46} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card style={{ marginTop: 16 }} title="Largest spikes">
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Site (OSM)</th>
                <th>Region</th>
                <th className="n">FRP (MW)</th>
                <th className="n">Baseline</th>
                <th className="n">Ratio</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((r, i) => (
                <tr key={`${r.source_id}-${r.date}-${i}`}>
                  <td className="num">{r.date}</td>
                  <td>{r.industry_name || <span className="dim">unmapped</span>}</td>
                  <td>{fmt.title(r.region)}</td>
                  <td className="n">{fmt.dec(r.frp)}</td>
                  <td className="n">{fmt.dec(r.normal_frp)}</td>
                  <td className="n" style={{ fontWeight: 620 }}>
                    {fmt.dec(r.ratio)}×
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}
