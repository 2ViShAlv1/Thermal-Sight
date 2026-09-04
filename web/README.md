# Web dashboard — React + FastAPI

Ye `app.py` (Streamlit) ka **doosra roop** hai, uski jagah nahi. Dono ek
hi files padhte hain aur ek hi jawab dete hain.

| | Streamlit (`app.py`) | React (`web/` + `api/`) |
|---|---|---|
| Kiske liye | jaldi check karne ke liye | demo / judges ke saamne |
| Chalana | `streamlit run app.py` | neeche dekho |
| Dark mode | nahi | haan, toggle ke saath |
| Data | seedha GeoPackage se | FastAPI se JSON |

---

## Chalane ka tareeka

### Ek command (demo ke liye — yahi use karo)

Pehle React build karo, phir FastAPI use khud serve kar degi:

```bash
cd web && npm install && npm run build && cd ..
venv/bin/uvicorn api.main:app --port 8000
```

Kholo: **http://127.0.0.1:8000**

### Do terminal (jab code badal rahe ho)

```bash
# terminal 1 - backend
venv/bin/uvicorn api.main:app --reload --port 8000

# terminal 2 - frontend (hot reload)
cd web && npm run dev
```

Kholo: **http://localhost:5173** (Vite `/api` ko 8000 pe bhej deta hai)

---

## Kya kahan hai

```
api/main.py                 saare JSON endpoints (koi calculation nahi -
                            sirf pipeline ki banayi files padhta hai)
web/src/App.jsx             shell: header, filters, tabs
web/src/styles.css          saare rang aur design tokens - light + dark
web/src/lib/theme.jsx       theme toggle + chart ke rang
web/src/lib/api.js          fetch hook + number formatting
web/src/components/         har tab ka apna file
```

## Endpoints

| Endpoint | Kya deta hai |
|---|---|
| `GET /api/meta` | regions, classes — UI shuru mein yahi maangta hai |
| `GET /api/summary` | upar ke bade numbers |
| `GET /api/sources` | map ke points (filter + limit ke saath) |
| `GET /api/priorities` | inspection wali ranked list |
| `GET /api/recovered` | wo sources jinpe AI ne photo dekh kar jawab diya |
| `GET /api/anomalies` | 3× baseline wale din |
| `GET /api/validation` | paanchon validation checks ka data |
| `GET /api/export` | GeoJSON download (QGIS ke liye) |

Swagger docs khud ban jaate hain: **http://127.0.0.1:8000/docs**

---

## Do cheezein jo jaan-boojh kar aisi hain

**1. Rang naape gaye hain, chune nahi gaye.**
Classes ke liye blue / aqua-green / orange hai — laal-hara jodi nahi.
Laal-hara sabse aam colour blindness (deuteranopia) mein bilkul ek jaisa
dikhta hai. Ye teen rang colour-blind simulation mein bhi alag rehte hain
(CVD ΔE 9.2 light / 9.4 dark, 8 ke target se upar). Har jagah rang ke
saath uska **naam bhi likha** hota hai — rang akela kabhi matlab nahi
batata.

**2. Map bhi theme badalta hai.**
Dark UI pe safed map chipka dena sabse aam galti hai. Light mode mein
Esri Light Gray Canvas, dark mein Dark Gray Canvas. (CartoDB isliye nahi
kyunki ab wo API key maangta hai aur bina key ke har tile pe
"API KEY REQUIRED" chhapa aata hai.)

---

## Theme

Toggle top-right pe hai. Choice `localStorage` mein yaad rehti hai; pehli
baar OS ki setting se chalti hai. `?theme=dark` URL mein daal do to link
seedha dark mein khulega — screenshot lene ke liye kaam ka.

Tab bhi URL mein rehta hai (`?tab=validation`), to link bhej kar seedha
us tab pe bheja ja sakta hai.
