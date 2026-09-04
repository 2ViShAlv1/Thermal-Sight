import { createContext, useCallback, useContext, useEffect, useState } from 'react'

const ThemeCtx = createContext({ theme: 'light', toggle: () => {} })

/**
 * Theme <html data-theme="..."> pe rehta hai, CSS wahin se padhti hai.
 *
 * Pehli baar theme index.html ke chhote script se lag chuka hota hai
 * (flash rokne ke liye) - yahan sirf usse padh kar aage chalate hain.
 */
export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(
    () => document.documentElement.getAttribute('data-theme') || 'light'
  )

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try {
      localStorage.setItem('tsc-theme', theme)
    } catch (e) {
      /* private mode - theme sirf is tab tak rahega, koi baat nahi */
    }
  }, [theme])

  const toggle = useCallback(
    () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')),
    []
  )

  return <ThemeCtx.Provider value={{ theme, toggle }}>{children}</ThemeCtx.Provider>
}

export const useTheme = () => useContext(ThemeCtx)

/**
 * Charts ko asli hex chahiye (SVG CSS variable inherit nahi karta jahan
 * hum use karte hain), isliye dono mode ke rang yahan bhi likhe hain.
 * Ye styles.css ke tokens se BILKUL milne chahiye.
 */
const LIGHT = {
  industrial: '#2a78d6',
  forest: '#1baf7a',
  agri: '#eb6834',
  review: '#898781',
  accent: '#2a78d6',
  good: '#0ca30c',
  warning: '#fab219',
  critical: '#d03b3b',
  grid: '#e1e0d9',
  axis: '#c3c2b7',
  // styles.css ke --muted ke saath badla gaya - chart ke axis labels
  // wahi grey pehnte hain jo baaki UI ka secondary text
  muted: '#6d6b64',
  text: '#0b0b0b',
  surface: '#fcfcfb',
}

const DARK = {
  industrial: '#3987e5',
  forest: '#199e70',
  agri: '#d95926',
  review: '#898781',
  accent: '#3987e5',
  good: '#0ca30c',
  warning: '#fab219',
  critical: '#d03b3b',
  grid: '#2c2c2a',
  axis: '#383835',
  muted: '#9b9990',
  text: '#ffffff',
  surface: '#1a1a19',
}

export function useColors() {
  const { theme } = useTheme()
  return theme === 'dark' ? DARK : LIGHT
}

/** class key -> colour. Ek hi jagah, warna map aur legend alag ho jayenge. */
export function classColor(c, colors) {
  return (
    {
      INDUSTRIAL: colors.industrial,
      FOREST_FIRE: colors.forest,
      AGRI_BURN: colors.agri,
      REVIEW: colors.review,
    }[c] || colors.muted
  )
}

export const CLASS_LABEL = {
  INDUSTRIAL: 'Industrial / Mining',
  FOREST_FIRE: 'Forest fire',
  AGRI_BURN: 'Crop residue burning',
  REVIEW: 'Needs review',
}
