import { useEffect, useMemo } from 'react'
import {
  AttributionControl, CircleMarker, MapContainer, Popup, ScaleControl,
  TileLayer, useMap,
} from 'react-leaflet'
import { classColor, CLASS_LABEL, useColors, useTheme } from '../lib/theme'
import { fmt } from '../lib/api'

// Light mein OSM - roads, town names, sab detailed. QGIS project bhi
// yahi tiles use karta hai, to web aur QGIS ek jaisa dikhte hain.
//
// Dark mein OSM nahi chalta - OSM ke paas koi free dark variant hai hi
// nahi, aur safed OSM tile ko dark UI pe chipka dena sabse aam galti
// hai. Esri Dark Gray Canvas wahan istemal hota hai (bina API key ke
// chalta hai - CartoDB ab key maangta hai).
const TILES = {
  light: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  dark: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/'
      + 'World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
}
const ATTR = {
  light: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  dark: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
}

// Raw view ka rang. Har point ek hi grey - kyunki raw feed mein
// class hoti hi nahi. Ye theme ke saath badalta hai warna dark map pe
// grey markers gayab ho jaate hain.
const RAW_COLOR = { light: '#8a929c', dark: '#7d8792' }

/**
 * Do kaam karta hai, dono Leaflet khud nahi karta:
 *
 *  1. FIT - map ko un points pe le jaata hai jo abhi dikh rahe hain.
 *     Pehle center = saare points ka average tha aur zoom fix 5. Ek
 *     hi region chuno to wo average kahin beech mein padta tha aur
 *     data screen ke kone mein chala jata tha. Ab frame hamesha data
 *     ke hisaab se banta hai.
 *
 *  2. RESIZE - map ki height ab screen ke saath badalti hai (CSS clamp).
 *     Leaflet ko container ka naya size khud pata nahi chalta; bina
 *     invalidateSize ke aadha map grey reh jata hai.
 */
function MapFrame({ bounds }) {
  const map = useMap()

  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [34, 34], maxZoom: 11 })
  }, [map, bounds])

  useEffect(() => {
    const ro = new ResizeObserver(() => map.invalidateSize())
    ro.observe(map.getContainer())
    return () => ro.disconnect()
  }, [map])

  return null
}

export default function MapView({ items, raw = false }) {
  const colors = useColors()
  const { theme } = useTheme()

  // Marker ka size detections ke saath badhta hai, par ^0.35 pe -
  // seedha proportional rakhoge to 3,968 detection wala point poori
  // screen kha jayega aur 1 wala dikhega hi nahi.
  const points = useMemo(
    () =>
      items.map((d) => ({
        ...d,
        // Raw view mein size bhi ek jaisa. Size detections dikhata hai,
        // aur wahi ek cheez hai jo raw feed mein sach mein hoti hai -
        // par yahan poora point yeh hai ki har record EK JAISA lagta
        // hai, isliye us farq ko bhi nahi dikhate.
        r: raw ? 3 : 3 + Math.min(8, Math.pow(d.n_detections || 1, 0.35)),
        color: raw ? RAW_COLOR[theme] : classColor(d.klass, colors),
      })),
    [items, colors, raw, theme]
  )

  // Bounding box SIRF items pe memo hai, points pe nahi. points theme
  // aur colours pe bhi banta hai - us par rakhte to dark mode toggle
  // karte hi map wapas fit ho kar user ka pan/zoom uda deta.
  const bounds = useMemo(() => {
    if (!items.length) return null
    let [s, w, n, e] = [90, 180, -90, -180]
    for (const p of items) {
      if (p.lat < s) s = p.lat
      if (p.lat > n) n = p.lat
      if (p.lon < w) w = p.lon
      if (p.lon > e) e = p.lon
    }
    return [[s, w], [n, e]]
  }, [items])

  return (
    <div className="map-shell">
      <MapContainer
        center={[23.5, 79]}
        zoom={5}
        scrollWheelZoom
        zoomControl
        attributionControl={false}
        style={{ height: '100%' }}
      >
        <TileLayer key={theme} url={TILES[theme]} attribution={ATTR[theme]} />
        {/* Default Leaflet attribution sits bottom-right - hamare
            floating chat button ka wahi corner hai, isliye dono
            controls (attribution + scale) ko bottom-left pe rakha hai. */}
        <AttributionControl position="bottomleft" />
        <ScaleControl position="bottomleft" imperial={false} />
        <MapFrame bounds={bounds} />
        {points.map((p) => (
          <CircleMarker
            key={p.source_id}
            center={[p.lat, p.lon]}
            radius={p.r}
            pathOptions={{
              color: p.color,
              // 2px surface ring - overlapping markers alag dikhte rahein
              weight: raw ? 0 : 1.4,
              fillColor: p.color,
              fillOpacity: raw ? 0.5 : 0.72,
            }}
          >
            {raw ? (
              // Raw point pe click karne ko kuch hai hi nahi - naam,
              // class, land cover, kuch bhi nahi. Sirf ek garam jagah
              // aur uske detections. Popup mein khaali dabbe dikhane se
              // behtar hai ki popup ho hi na.
              <Popup>
                <div style={{ minWidth: 180 }}>
                  <div style={{ fontWeight: 600, marginBottom: 6 }}>
                    Thermal detection
                  </div>
                  <div className="pop-row">
                    <span>Detections</span><b>{fmt.int(p.n_detections)}</b>
                  </div>
                  <div className="pop-row">
                    <span>Active days</span><span>{fmt.int(p.n_days)}</span>
                  </div>
                  <div className="pop-row">
                    <span>Location</span>
                    <span>{p.lat.toFixed(3)}, {p.lon.toFixed(3)}</span>
                  </div>
                  <div className="dim" style={{ marginTop: 8, lineHeight: 1.45 }}>
                    That is everything the satellite reports. No cause,
                    no site name.
                  </div>
                </div>
              </Popup>
            ) : (
            <Popup>
              <div style={{ minWidth: 218 }}>
                <div style={{ fontWeight: 660, color: p.color, marginBottom: 2 }}>
                  {CLASS_LABEL[p.klass] || p.klass}
                </div>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>
                  {p.site || fmt.title(p.region)}
                </div>
                <div className="pop-row"><span>Detections</span><b>{fmt.int(p.n_detections)}</b></div>
                <div className="pop-row"><span>Active days</span><span>{fmt.int(p.n_days)}</span></div>
                <div className="pop-row"><span>Night share</span><b>{fmt.pct(p.night_ratio)}</b></div>
                <div className="pop-row"><span>Peak FRP</span><span>{fmt.dec(p.frp_max)} MW</span></div>
                <div className="pop-row"><span>To industry</span><span>{fmt.m(p.dist_to_industry_m)}</span></div>
                <div className="pop-row"><span>Land cover</span><span>{p.lc_class}</span></div>
                {p.vlm_landuse && (
                  <div className="pop-ai">
                    <b>
                      {p.label_source === 'vlm'
                        ? 'Classified by vision model'
                        : 'Also checked by vision model'}
                    </b>
                    : saw <b>{p.vlm_landuse}</b>
                    {p.vlm_reason && (
                      <div style={{ marginTop: 4, fontStyle: 'italic' }}>
                        “{p.vlm_reason}”
                      </div>
                    )}
                  </div>
                )}
              </div>
            </Popup>
            )}
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  )
}
