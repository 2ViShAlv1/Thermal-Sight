import { useEffect, useMemo } from 'react'
import {
  AttributionControl, CircleMarker, MapContainer, Popup, TileLayer, useMap,
} from 'react-leaflet'
import { classColor, CLASS_LABEL, useColors, useTheme } from '../lib/theme'
import { fmt } from '../lib/api'

// Same tiles jo main MapView use karta hai - ek hi jagah rakhna behtar
// hota, par ye chhota standalone component hai isliye duplicate rakha
// (LiveTab kabhi MapTab ke saath nahi khulta, koi bundle-size farak
// nahi padta).
const TILES = {
  light: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  dark: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/'
      + 'World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
}
const ATTR = {
  light: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  dark: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
}

function MapFrame({ bounds }) {
  const map = useMap()
  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 9 })
  }, [map, bounds])
  useEffect(() => {
    const ro = new ResizeObserver(() => map.invalidateSize())
    ro.observe(map.getContainer())
    return () => ro.disconnect()
  }, [map])
  return null
}

/**
 * Live tab ke detections ko spatially dikhata hai - jaise "yahan hai
 * Jharia" turant nazar aa jaye, table scroll karke dhoondhna na pade.
 *
 * Rang MODEL ka fresh jawab se aata hai jab hai (jaani-pehchani
 * source), warna rule status se (jo NEW ke liye "NEW" hi rehta hai) -
 * yehi table mein bhi dikhta hai, dono jagah ek hi kahani honi chahiye.
 */
export default function LiveMap({ items }) {
  const colors = useColors()
  const { theme } = useTheme()

  const points = useMemo(
    () => items.map((d) => ({
      ...d,
      klass: d.model_pred || d.status_key,
      color: classColor(d.model_pred || d.status_key, colors),
    })),
    [items, colors]
  )

  const bounds = useMemo(() => {
    if (!items.length) return null
    let [s, w, n, e] = [90, 180, -90, -180]
    for (const p of items) {
      if (p.latitude < s) s = p.latitude
      if (p.latitude > n) n = p.latitude
      if (p.longitude < w) w = p.longitude
      if (p.longitude > e) e = p.longitude
    }
    // ek hi point ho to bounds shoonya-size hota hai, fitBounds crash
    // karta - thoda paddding jod do
    if (s === n && w === e) return [[s - 0.3, w - 0.3], [n + 0.3, e + 0.3]]
    return [[s, w], [n, e]]
  }, [items])

  if (!items.length) return null

  return (
    <div className="map-shell" style={{ height: 320, marginBottom: 16 }}>
      <MapContainer center={[23.5, 82]} zoom={5} scrollWheelZoom zoomControl
                    attributionControl={false} style={{ height: '100%' }}>
        <TileLayer key={theme} url={TILES[theme]} attribution={ATTR[theme]} />
        <AttributionControl position="bottomleft" />
        <MapFrame bounds={bounds} />
        {points.map((p, i) => (
          <CircleMarker
            key={`${p.source_id || 'new'}-${i}`}
            center={[p.latitude, p.longitude]}
            radius={9}
            pathOptions={{ color: p.color, weight: 2, fillColor: p.color, fillOpacity: 0.7 }}
          >
            <Popup>
              <div style={{ minWidth: 200 }}>
                <div style={{ fontWeight: 660, color: p.color, marginBottom: 6 }}>
                  {CLASS_LABEL[p.klass] || p.klass}
                  {p.model_pred && p.model_pred !== p.status_key && (
                    <span className="dim" style={{ fontWeight: 400 }}>
                      {' '}(rule said {CLASS_LABEL[p.status_key] || p.status_key})
                    </span>
                  )}
                </div>
                <div className="pop-row"><span>Region</span><b>{fmt.title(p.region)}</b></div>
                <div className="pop-row"><span>FRP</span><span>{fmt.dec(p.frp)} MW</span></div>
                {p.model_confidence != null && (
                  <div className="pop-row"><span>Confidence</span><span>{fmt.pct(p.model_confidence)}</span></div>
                )}
                {p.spread_direction && (
                  <div className="pop-row"><span>Spreading</span><span>{p.spread_direction}</span></div>
                )}
                <div className="pop-row">
                  <span>Time</span>
                  <span>{p.timestamp_utc ? p.timestamp_utc.slice(11, 16) : '—'} UTC</span>
                </div>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  )
}
