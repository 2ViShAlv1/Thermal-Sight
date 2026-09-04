# SIH26162 — 7-Day Plan (beginner-friendly)

**Pura project 4 lines mein:**
1. NASA FIRMS se garam points ka CSV download karo
2. OSM se pata karo har point ke aas-paas kya hai (factory? jungle? khet?)
3. Rules + AI se label lagao (industrial / forest / agri)
4. Model train karke map pe colour ke saath dikhao

Jab bhi confuse lago, in 4 lines pe wapas aa jana.

---

## Do bade changes (jo tumhari life aasan karenge)

### 1. Database ab optional hai

Pehle: sab kuch PostGIS mein. Agar Docker atka → poora din barbaad.

**Ab:** saara kaam **normal files** pe hoga — CSV aur GeoPackage (`.gpkg`). GeoPackage bas ek file hai jisme map data hota hai, QGIS use seedha khol leta hai.

PostGIS ko Day 6 pe last step ki tarah add karenge — ek script jo final tables DB mein daal de. Tab "GIS based storage" wala deliverable bhi tick ho jayega, aur agar Docker na chale to project rukega nahi.

**Faayda:** har step ka output ek file hai jo tum QGIS mein khol ke dekh sakte ho. Debugging 10× aasan.

### 2. Dashboard ab Streamlit mein

Pehle: FastAPI backend + alag HTML frontend + fetch calls.

**Ab:** sirf **Streamlit** — ek Python file. Map, filters, charts sab Python mein.

```python
import streamlit as st, geopandas as gpd, folium
from streamlit_folium import st_folium
```

Na API, na JavaScript, na CORS errors. Tum Python jaante ho, wahi use karo.

**Trade-off honest:** custom HTML dashboard thoda zyada polished dikhta. Par Streamlit app **chalta hai**, aur chalta hua demo hamesha na-chalne wale fancy demo se better hai.

---

## Final tech stack

```
Python + Pandas + GeoPandas     — data
Scikit-learn + XGBoost          — model
Anthropic API                   — VLM verification
Streamlit                       — dashboard
QGIS                            — dekhne ke liye
PostGIS (Day 6, optional)       — final storage
```

Bas. 6 cheezein. Docker sirf ek din chahiye, wo bhi optional.

## Scope (locked, isko mat badalna)

**3 regions:**
| Region | Bbox (W, S, E, N) | Kya milega |
|---|---|---|
| Jamnagar, Gujarat | 69.4, 21.8, 70.6, 22.9 | Industrial (refineries) |
| Kumaon, Uttarakhand | 78.8, 29.2, 80.2, 30.4 | Forest fires |
| Ludhiana, Punjab | 75.2, 30.2, 76.4, 31.0 | Agri burning |

⚠️ FIRMS API mein order **west, south, east, north** hota hai — yani longitude pehle. Upar wale numbers usi order mein likhe hain, seedha copy kar lena.

**Time:** 2025 ka poora saal
**3 classes:** `INDUSTRIAL`, `FOREST_FIRE`, `AGRI_BURN`
*(anomaly detection ek alag flag hoga, class nahi — usse cheezein simple rehti hain)*

---

## Folder structure (aisa hi rakhna)

```
sih26162/
  data/
    raw/          # downloaded CSVs aur pbf
    processed/    # tumhare banaye .gpkg files
    chips/        # satellite images (VLM ke liye)
  src/
    step1_download.py
    step2_context.py
    step3_persistence.py
    step4_labels.py
    step5_train.py
    app.py            # streamlit dashboard
  models/
  outputs/          # charts, screenshots
  .env
  requirements.txt
  README.md
```

Har file ka ek hi kaam hai. Ek file ka output agli file ka input. **Har step ke baad ek `.gpkg` file banti hai jo tum QGIS mein khol sakte ho.**

---

# Day 1 — Data download

**Aaj sirf itna: FIRMS ka CSV aur OSM ke polygons mil jayein.**

### Prompt 1A

```
Project SIH26162 (student hackathon project — keep the code SIMPLE and
well commented, this is for a 3rd year student to understand and
explain).

Rules for all code you write in this project:
- Plain Python functions only. No classes, no async, no frameworks.
- Comment every non-obvious line explaining WHY.
- Save intermediate outputs as files so each step can be checked.
- Print clear progress messages.

Create the project structure (folders as below) and requirements.txt:
  geopandas, pandas, requests, pyogrio, scikit-learn, xgboost, shap,
  matplotlib, streamlit, streamlit-folium, folium, anthropic,
  python-dotenv, tqdm

Create src/config.py with:
  REGIONS = {
    "jamnagar":    (69.4, 21.8, 70.6, 22.9),
    "uttarakhand": (78.8, 29.2, 80.2, 30.4),
    "punjab":      (75.2, 30.2, 76.4, 31.0),
  }   # order is west, south, east, north
  START = "2025-01-01"; END = "2025-12-31"
  CLASSES = ["INDUSTRIAL", "FOREST_FIRE", "AGRI_BURN"]

Create src/step1_download.py:
  Download NASA FIRMS VIIRS data for each region for all of 2025.
  IMPORTANT: the FIRMS API allows a maximum of 10 days per request,
  so loop over the year in 10-day chunks. Sleep 1 second between
  requests.
  URL format:
  https://firms.modaps.eosdis.nasa.gov/api/area/csv/{KEY}/{SOURCE}/{west},{south},{east},{north}/{days}/{start_date}
  Try SOURCE = "VIIRS_SNPP_SP" first. If the response is empty or an
  error, print a clear message and try "VIIRS_SNPP_NRT".
  Save each chunk's CSV to data/raw/ and SKIP the download if the file
  already exists (so reruns are fast).
  Then combine everything into one GeoDataFrame with a 'region' column
  and save to data/processed/hotspots.gpkg

  At the end print: total rows, rows per region, date range, FRP stats.

Read FIRMS_MAP_KEY from a .env file.
```

**Chalne ke baad khud check karo:**
1. `data/processed/hotspots.gpkg` bana? Size 0 to nahi?
2. QGIS kholo → drag karke `hotspots.gpkg` daalo
3. Basemap add karo: Browser panel → XYZ Tiles → OpenStreetMap (double click)
4. Jamnagar pe zoom karo → refinery ke upar dots ka ghana jhund dikhna chahiye

**Agar dots galat jagah (samundar mein, ya duniya ke doosre kone mein):** bbox ka order ulta ho gaya hai. Longitude pehle hona chahiye.

### Prompt 1B

```
Day 1B: get context polygons from OpenStreetMap.

src/step2_context.py — part 1 only (extracting polygons):

We already have data/raw/india-latest.osm.pbf

1. Clip the pbf to the 3 region bboxes FIRST — never read the whole
   India file, it will take hours. Use osmium-tool if available,
   otherwise read with pyogrio and filter by bbox.

2. Extract two GeoDataFrames from the 'multipolygons' layer:

   INDUSTRY — keep rows where any of these are true:
     landuse == 'industrial'  or  landuse == 'quarry'
     man_made in ('works','petroleum_well','flare','storage_tank')
     power == 'plant'
     'industrial' tag is present
   Add a column industry_type, simplified to one of:
     refinery, power_plant, steel, chemical, mine, storage, other
   Save to data/processed/industry.gpkg

   LANDUSE — keep rows where:
     natural=='wood' or landuse=='forest'      -> lc_class = 'forest'
     landuse in ('farmland','orchard')          -> lc_class = 'cropland'
     landuse in ('residential','commercial')    -> lc_class = 'urban'
   Save to data/processed/landuse.gpkg

3. Print how many polygons of each type were found per region.
   If a region has zero industry polygons, print a loud warning.
```

**Day 1 done tab jab:** QGIS mein teeno files ek saath dikhein, aur Jamnagar ke dots industry polygons ke upar baithe hon, Uttarakhand ke dots forest polygons ke andar.

**Ye dikh gaya = tumhara pura idea confirm ho gaya.** Screenshot le lo.

---

# Day 2 — Context features + Persistence ⭐

**Sabse important din. Yahi tumhara "innovation" hai.**

### Prompt 2A (subah, ~1 ghanta)

```
Day 2A: add context to every hotspot.

src/step2_context.py — part 2:

1. Load hotspots.gpkg, industry.gpkg, landuse.gpkg

2. VERY IMPORTANT — convert all three to a metre-based CRS before any
   distance calculation:
       gdf = gdf.to_crs(32643)
   EPSG:4326 is in degrees, distances there are meaningless.
   Add a comment explaining this clearly.

3. Distance to nearest industry — one GeoPandas call:
       feat = gpd.sjoin_nearest(hotspots, industry,
                                how="left",
                                distance_col="dist_to_industry_m")
   Keep: dist_to_industry_m, industry_type, name (as industry_name)

4. What land use is the point on:
       gpd.sjoin(hotspots, landuse, how="left", predicate="within")
   -> lc_class column. Fill blanks with "unknown".

5. Add simple columns: month, is_night (from the daynight column)

6. Save data/processed/features.gpkg

7. Print a small summary table: for each region, the median
   dist_to_industry_m and the count of each lc_class.
```

**Check karo — ye numbers aane chahiye:**
- Jamnagar: median distance chhoti (sau-do sau metre)
- Uttarakhand: median distance badi (kai kilometre), `lc_class` mostly forest
- Punjab: `lc_class` mostly cropland

**Agar teeno regions ke numbers ek jaise hain → CRS ki galti hai. Yahin ruk ke fix karo, aage mat badho.**

### Prompt 2B (dopahar) — project ka dil

```
Day 2B: find persistent thermal sources.

The idea in one line: if the same spot is detected as hot again and
again for months, it is a running factory. If it appears for 3 days and
disappears, it was a fire event.

src/step3_persistence.py:

1. For each region separately, cluster the hotspots using
   sklearn DBSCAN on the projected (metre) coordinates:
       DBSCAN(eps=500, min_samples=3)
   500 = points within 500 metres belong to the same source.
   Add a comment explaining eps and min_samples in plain terms.

2. Group by cluster and compute for each cluster:
       n_detections        how many times detected
       n_days              on how many distinct dates
       first_seen, last_seen
       lifespan_days       last_seen - first_seen
       activity_ratio      n_days / lifespan_days
       night_ratio         fraction of night detections
       frp_mean, frp_median, frp_max, frp_std
       dist_to_industry_m  median of its members
       industry_type, industry_name
       lc_class            most common among members
       centroid latitude and longitude

3. Add a column persistence_tier:
       "PERSISTENT" if lifespan_days > 150 and activity_ratio > 0.25
       "EPISODIC"   if lifespan_days <= 30
       "OTHER"      otherwise

4. Save data/processed/sources.gpkg

5. Print the top 20 PERSISTENT sources sorted by n_detections, showing
   industry_name, n_detections, lifespan_days, night_ratio.
```

**Ye check sabse zaroori hai:** top 20 ki list mein **asli refinery/plant ke naam** dikh rahe hain? Agar haan — tumhara project kaam kar raha hai. Screenshot lo, PPT mein jayega.

Uttarakhand ke clusters EPISODIC hone chahiye, Jamnagar ke PERSISTENT.

---

# Day 3 — Labels

### Prompt 3A (subah, ~1 ghanta)

```
Day 3A: create labels using simple rules.

src/step4_labels.py — part 1:

Give each source in sources.gpkg a label:

  INDUSTRIAL:
      dist_to_industry_m < 1000  AND  persistence_tier != "EPISODIC"

  FOREST_FIRE:
      lc_class == "forest"  AND  dist_to_industry_m > 5000
      AND persistence_tier == "EPISODIC"

  AGRI_BURN:
      lc_class == "cropland"  AND  dist_to_industry_m > 3000
      AND persistence_tier == "EPISODIC"
      AND month in (4, 5, 10, 11)

  UNSURE: if no rule matches, or more than one matches

Add a column needs_review = True when label is UNSURE, or when
dist_to_industry_m is between 500 and 3000 (the confusing zone).

Also add a simple anomaly flag (not a class):
  For each PERSISTENT source, find days where that day's max FRP is
  more than 3x the source's normal frp_median. Save these to
  data/processed/anomalies.csv with source id, date, frp, ratio.

Save data/processed/sources_labelled.gpkg
Print how many got each label and how many need review.
```

### Prompt 3B (background mein chhod do)

```
Day 3B: use a vision AI to check the confusing cases.

src/step4_labels.py — part 2:

For sources where needs_review is True (take at most 100):

1. Download ONE satellite image tile centred on the source, zoom 15,
   from Esri World Imagery:
   https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}
   Write a small lat/lon -> tile x/y helper with comments.
   Save to data/chips/{source_id}.jpg and skip if it already exists.

2. Send the image to the Anthropic API (model claude-sonnet-4-6) and
   ask it to look at the IMAGE and reply with JSON only:
   {"landuse": one of [industrial, mine, forest, cropland, urban,
    water, barren, unclear], "confidence": 0-1, "reason": "..."}
   You may mention the nearby OSM industry name as a hint, but tell
   the model to trust the image over the hint.

3. Convert the answer into a final label:
     industrial or mine -> INDUSTRIAL
     forest             -> FOREST_FIRE
     cropland           -> AGRI_BURN
     anything else      -> leave as UNSURE
   Store vlm_landuse, vlm_confidence, vlm_reason in the file.

4. Simple for-loop with tqdm is fine. Save progress every 10 images so
   a crash does not lose work.
```

### Prompt 3C (dopahar, ~30 min)

```
Day 3C: a small tool so I can label 50 sources by hand.

src/gold_ui.py — Streamlit app showing ONE source at a time:
  - the satellite image chip
  - a line chart of that source's FRP over time
  - its stats (detections, lifespan, distance to industry, nearest
    industry name, land cover)
  - a link that opens the coordinates in Google Maps satellite view
  - three buttons: INDUSTRIAL / FOREST_FIRE / AGRI_BURN, plus UNCLEAR
  - a notes text box
  - progress counter, and it should skip sources already labelled

Pick 50 sources spread across the 3 regions and across rule labels.
Save answers to data/processed/gold_labels.csv
```

### 🔴 Day 3 shaam — ye tum karo (~1 ghanta)

50 sources, har ek pe ~1 minute. Chai leke baitho.

**Skip mat karna.** Jo 3-4 galtiyan tum khud pakdoge — jaise koi plant OSM pe missing hai, ya koi jagah dono jaisi lagti hai — wahi tumhari best slide banegi aur finale mein tumhe bachayegi.

---

# Day 4 — Model

### Prompt 4

```
Day 4: train a classifier. ONE simple script.

src/step5_train.py:

1. Load sources_labelled.gpkg. Drop rows still labelled UNSURE.

2. Features to use:
     dist_to_industry_m, night_ratio, activity_ratio, lifespan_days,
     n_detections, n_days, frp_mean, frp_median, frp_max, frp_std,
     lc_class (one-hot), persistence_tier (one-hot)

   DO NOT use latitude or longitude as features. Add a comment saying
   why: the model would just memorise "Jamnagar = industrial" instead
   of learning what industrial looks like.

3. Train XGBoost (multi-class). Use class weights for imbalance.

4. Evaluate THREE ways and print all three in one table:
     a) normal random 5-fold cross-validation
     b) GroupKFold grouped by source_id, so the same physical source
        never appears in both train and test
     c) accuracy on the 50 human gold labels (held out completely)
   Report macro-F1 for each. The score WILL drop from (a) to (c) —
   that is expected and honest, print a short note saying so.

5. Save to outputs/:
     confusion_matrix.png
     shap_summary.png     (use shap.summary_plot)
     metrics.json
   and models/classifier.pkl

6. Print the headline number in big letters:
     "X raw FIRMS detections  ->  Y industrial sources identified"
     reduction percentage
```

**Kya expect karo:** gold-set F1 **0.75–0.85** normal hai. Agar 0.97 aaya, kahin galti hai (shayad lat/long feature mein reh gaya).

---

# Day 5 — Dashboard (Streamlit)

### Prompt 5

```
Day 5: the dashboard. Single Streamlit file, src/app.py.

Use streamlit + folium + streamlit_folium. Read directly from the
.gpkg files — no API, no database needed.

Layout:
  Sidebar: region selector, class checkboxes, persistence tier
           selector, minimum FRP slider
  Main area: a folium map, full width

BUILD THIS FIRST — it is the whole pitch:
  A toggle at the top: "Raw FIRMS data"  <->  "After AI classification"
  Raw view    : all hotspots as small grey dots, all looking identical
  After view  : same points coloured by predicted class
  Above the map show a big metric:
      "12,847 raw detections  ->  43 industrial sources"
  Use st.metric for this.

Then add, in this order:
  - Layer checkboxes: raw hotspots / classified / sources / industry
    polygons / anomaly markers
  - Click a source marker -> popup with its stats
  - A tab showing the anomalies table (date, source, FRP, ratio)
  - A tab showing charts: count per class, count per month
  - A download button that exports the current filtered view as GeoJSON

Keep it under 300 lines. Comment the sections. Simple beats clever.
```

**Time kam pade to priority:** before/after toggle → layers → popups → charts → download.

---

# Day 6 — Jodna aur theek karna

**Naya kuch mat banao. Poora din integration ke liye hai.**

- [ ] Saare steps ek baar shuru se end tak chala ke dekho
- [ ] `run_all.py` banao jo step1 se step5 tak sab chala de
- [ ] Streamlit app kholo, har filter click karke dekho — kuch crash to nahi karta
- [ ] **PostGIS wala step (deliverable ke liye):** ek chhota `src/step6_postgis.py` jo final `.gpkg` files ko PostGIS mein daal de (`geopandas.to_postgis`). Docker ek command: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgis/postgis:16-3.4`. Agar na chale, koi baat nahi — GeoPackage bhi ek GIS format hai, PPT mein wahi likh dena
- [ ] README likho: kya banaya, kaise chalana hai, screenshots
- [ ] Saare screenshots `outputs/` mein collect karo
- [ ] **Doosre laptop pe clone karke chala ke dekho** — demo ke din "mere laptop pe to chal raha tha" sabse bada dar hai

---

# Day 7 — PPT + video

### PPT (10 slides)

| # | Slide |
|---|---|
| 1 | Problem — raw FIRMS map ka screenshot, hazaaron ek jaise dots |
| 2 | Solution — simple architecture diagram (4 boxes) |
| 3 | Approach — context → persistence → classification |
| 4 | **Labelling — kaise labels banaye** (rules + VLM + 50 human checks) |
| 5 | **Evaluation — teeno numbers** aur wo kyun girte hain |
| 6 | Results — confusion matrix, SHAP, reduction number |
| 7 | Dashboard — before/after screenshot |
| 8 | Impact — NTRO, critical infrastructure monitoring |
| 9 | **Limitations** — OSM gaps, coal fires, cloud cover, aage kya |
| 10 | Tech stack + team |

**Slide 4, 5, 9 hi tumhe alag dikhayenge.** Zyadatar teams inhe skip kar deti hain aur sirf accuracy dikhati hain.

### Video (3 min)
Problem (20s) → before/after toggle (30s) → Jamnagar refinery click (40s) → anomaly (30s) → Uttarakhand forest fire (25s) → export (15s)

---

## Download list — sirf 2 cheezein

| Kya | Link |
|---|---|
| FIRMS MAP_KEY | https://firms.modaps.eosdis.nasa.gov/api/map_key/ ✅ mil gaya |
| OSM India pbf | https://download.geofabrik.de/asia/india.html |

FIRMS ka data script khud download karega. Satellite images runtime pe aa jaati hain. Bas.

---

## Padhna — total 1 ghanta

**Day 1 se pehle (30 min):**

**CRS — sabse zaroori 10 minute**
https://geopandas.org/en/stable/docs/user_guide/projections.html
Bas itna: EPSG:4326 = degrees (map dikhane ke liye), EPSG:32643 = metres (distance ke liye). Distance nikalne se pehle hamesha `to_crs(32643)`.

**FIRMS ka data kya hai — 20 min**
https://www.earthdata.nasa.gov/data/tools/firms/faq
`bright_ti4`, `frp`, `confidence`, `daynight` ka matlab. Finale mein ye pooche jayenge.

**Day 2 se pehle (20 min):**
- GeoPandas ke `sjoin_nearest` aur `sjoin` docs — tumhara pura feature engineering yahi 2 functions hain
- DBSCAN — sirf `eps` aur `min_samples` ka matlab samajh lo

**Day 4 se pehle (10 min):**
- Spatial leakage — https://www.mdpi.com/2624-795X/7/3/90 — sirf Abstract padho. Isse tumhari slide 5 banegi

**QGIS — 15 min:** file drag karke daalna, XYZ Tiles se OpenStreetMap basemap add karna, attribute table dekhna, ek column ke hisaab se colour karna. Bas itna kaafi hai.

---

## Har din ka checkpoint

| Din | Ho gaya jab |
|---|---|
| 1 | QGIS mein teeno layers sahi jagah dikh rahe |
| 2 | Top persistent sources mein asli plant ke naam ⭐ |
| 3 | 3 classes labelled + 50 gold labels |
| 4 | Teen evaluation numbers + confusion matrix |
| 5 | Before/after toggle chal raha |
| 6 | Doosre laptop pe chal gaya |
| 7 | PPT + video ready |

---

## Jab atak jao — ye karo

**Claude Code ka code samajh na aaye:**
Usi se pooch lo — *"is file ko line by line samjhao, main 3rd year student hun"*. Wo simple bhasha mein explain kar dega. Har din kam se kam ek file poori padhna, taaki finale mein apna code explain kar sako.

**Kuch chal nahi raha:**
Sabse pehle QGIS mein output kholo. 80% bugs wahin aankhon se dikh jaate hain.

**Kisi din piche pad jao:**
Us din ka scope kaato, agle din pe mat kheencho. Ek chhota chalta hua system, bade adhoore system se hamesha better hai.

**Zyada complex lagne lage:**
Upar wali 4 lines yaad karo. Download → context → label → classify. Baaki sab uske details hain.

---

## Aakhri baat

Ye plan jaan-boojh kar boring rakha hai. Isme koi aisi cheez nahi hai jo tum debug na kar sako ya explain na kar sako. Yahi 3rd year mein hona chahiye.

Tumhara asli edge fancy tech mein nahi hai — wo **Day 2 ke persistence idea** mein aur **Day 3 ki honest labelling** mein hai. Ye do cheezein zyadatar teams nahi karengi. Baaki sab bas plumbing hai, aur plumbing ko simple hi rehna chahiye.
