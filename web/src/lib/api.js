import { useEffect, useState } from 'react'

/** regions/classes arrays ko ?regions=a&regions=b mein badalta hai. */
export function qs(params) {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    if (Array.isArray(v)) v.forEach((x) => p.append(k, x))
    else p.append(k, v)
  }
  const s = p.toString()
  return s ? `?${s}` : ''
}

export async function get(path) {
  const r = await fetch(`/api${path}`)
  if (!r.ok) throw new Error(`${r.status} ${path}`)
  return r.json()
}

/**
 * Ek chhota data-fetching hook.
 *
 * `deps` badalte hi dobara fetch hota hai. `stale` isliye rakha hai ki
 * naya data aane tak PURANA dikhta rahe - warna har filter click pe
 * poori screen khaali ho jati hai aur bahut kharab lagta hai.
 */
export function useApi(path, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    get(path)
      .then((d) => alive && (setData(d), setError(null)))
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, loading, error, stale: data !== null && loading }
}

// ---------------------------------------------------------------
// Formatting - ek hi jagah, taaki har table mein number ek jaisa dikhe
// ---------------------------------------------------------------
// Number(n) yahan isliye hai: ek baar backend se ek numeric column
// STRING bankar aaya tha (GPKG ki apni ek quirk - dekho api/main.py
// ka comment). .toFixed() sirf number pe hota hai, string pe nahi -
// aur bina Error Boundary ke wo crash poori React tree ko khaali kar
// deta hai, sirf us ek table cell ko nahi. Isliye har formatter yahan
// pehle Number() se guzarta hai - "0.95" aur 0.95 dono ab ek jaisa
// chalte hain, aur sach mein kharab value NaN ban kar "—" dikhati hai.
const num = (n) => {
  if (n === null || n === undefined || n === '') return null
  const v = Number(n)
  return Number.isFinite(v) ? v : null
}

export const fmt = {
  int: (n) => { const v = num(n); return v === null ? '—' : Math.round(v).toLocaleString('en-IN') },
  pct: (n, d = 0) => { const v = num(n); return v === null ? '—' : `${(v * 100).toFixed(d)}%` },
  dec: (n, d = 1) => { const v = num(n); return v === null ? '—' : v.toFixed(d) },
  m: (n) => { const v = num(n); return v === null ? '—' : `${Math.round(v).toLocaleString('en-IN')} m` },
  title: (s) => (s ? s[0].toUpperCase() + s.slice(1) : '—'),
}
