# Web dashboard — React + FastAPI

This is a **second form** of `app.py` (Streamlit), not a replacement for it. Both
read the same files and give the same answers.

| | Streamlit (`app.py`) | React (`web/` + `api/`) |
|---|---|---|
| For | quick checks | demo / in front of judges |
| Run | `streamlit run app.py` | see below |
| Dark mode | no | yes, with a toggle |
| Data | straight from GeoPackage | JSON from FastAPI |

---

## How to run it

### One command (for a demo — use this)

Build React first, then FastAPI serves it itself:

```bash
cd web && npm install && npm run build && cd ..
venv/bin/uvicorn api.main:app --port 8000
```

Open: **http://127.0.0.1:8000**

### Two terminals (while changing code)

```bash
# terminal 1 - backend
venv/bin/uvicorn api.main:app --reload --port 8000

# terminal 2 - frontend (hot reload)
cd web && npm run dev
```

Open: **http://localhost:5173** (Vite forwards `/api` to port 8000)

---

## What's where

```
api/main.py                 all JSON endpoints (no calculation -
                            just reads the files the pipeline builds)
web/src/App.jsx             shell: header, filters, tabs
web/src/styles.css          all colors and design tokens - light + dark
web/src/lib/theme.jsx       theme toggle + chart colors
web/src/lib/api.js          fetch hook + number formatting
web/src/components/         one file per tab
```

## Endpoints

| Endpoint | What it returns |
|---|---|
| `GET /api/meta` | regions, classes — what the UI asks for first |
| `GET /api/summary` | the big numbers at the top |
| `GET /api/sources` | map points (with filter + limit) |
| `GET /api/priorities` | the ranked inspection list |
| `GET /api/recovered` | sources the AI answered by looking at the photo |
| `GET /api/anomalies` | days at 3× baseline |
| `GET /api/validation` | data for all five validation checks |
| `GET /api/export` | GeoJSON download (for QGIS) |

Swagger docs are generated automatically: **http://127.0.0.1:8000/docs**

---

## Two things that are deliberately this way

**1. Colors were measured, not picked.**
Blue / aqua-green / orange for the classes — not a red-green pair.
Red-green looks identical under the most common form of color blindness
(deuteranopia). These three colors stay distinct even under a color-blind
simulation (CVD ΔE 9.2 light / 9.4 dark, above the target of 8). Every
color is also **labelled by name** wherever it appears — color alone
never carries the meaning.

**2. The map switches theme too.**
Sticking a white map on a dark UI is the most common mistake. Esri Light
Gray Canvas in light mode, Dark Gray Canvas in dark mode. (Not CartoDB,
because it now requires an API key and prints "API KEY REQUIRED" on
every tile without one.)

---

## Theme

The toggle is top-right. The choice is remembered in `localStorage`; the
first run follows the OS setting. Add `?theme=dark` to the URL and the
link opens straight into dark mode — useful for screenshots.

The tab is also kept in the URL (`?tab=validation`), so a link can be
shared that opens directly to that tab.
