# SIH26162 — 7-Day Plan (beginner-friendly)

**The whole project in 4 lines:**
1. Download a CSV of hot points from NASA FIRMS
2. Use OSM to find out what's around each point (factory? forest? farmland?)
3. Label with rules + AI (industrial / forest / agri)
4. Train a model and show it on a map with color

Whenever you feel confused, come back to these 4 lines.

---

## Two big changes (that will make your life easier)

### 1. The database is now optional

Before: everything in PostGIS. If Docker got stuck → the whole day was wasted.

**Now:** all the work happens on **normal files** — CSV and GeoPackage (`.gpkg`). A GeoPackage is just a file containing map data, and QGIS opens it directly.

PostGIS will be added on Day 6 as a final step — a script that loads the final tables into a DB. That way the "GIS based storage" deliverable gets ticked too, and if Docker doesn't work the project won't stall.

**Benefit:** every step's output is a file you can open and look at in QGIS. Debugging becomes 10× easier.

### 2. The dashboard is now in Streamlit

Before: a FastAPI backend + a separate HTML frontend + fetch calls.

**Now:** just **Streamlit** — a single Python file. Map, filters, charts, all in Python.

```python
import streamlit as st, geopandas as gpd, folium
from streamlit_folium import st_folium
```

No API, no JavaScript, no CORS errors. You know Python — use that.

**Being honest about the trade-off:** a custom HTML dashboard looks a bit more polished. But a Streamlit app that **works** always beats a fancy demo that doesn't.

---

## Final tech stack

```
Python + Pandas + GeoPandas     — data
Scikit-learn + XGBoost          — model
Anthropic API                   — VLM verification
Streamlit                       — dashboard
QGIS                            — for viewing
PostGIS (Day 6, optional)       — final storage
```

That's it. 6 things. Docker is needed for only one day, and even that's optional.

## Scope (locked, don't change this)

**3 regions:**
| Region | Bbox (W, S, E, N) | What it gives us |
|---|---|---|
| Jamnagar, Gujarat | 69.4, 21.8, 70.6, 22.9 | Industrial (refineries) |
| Kumaon, Uttarakhand | 78.8, 29.2, 80.2, 30.4 | Forest fires |
| Ludhiana, Punjab | 75.2, 30.2, 76.4, 31.0 | Agri burning |

⚠️ The FIRMS API order is **west, south, east, north** — meaning longitude first. The numbers above are already in that order, just copy them directly.

**Time:** all of 2025
**3 classes:** `INDUSTRIAL`, `FOREST_FIRE`, `AGRI_BURN`
*(anomaly detection will be a separate flag, not a class — this keeps things simple)*

---

## Folder structure (keep it exactly like this)

```
sih26162/
  data/
    raw/          # downloaded CSVs and pbf
    processed/    # your generated .gpkg files
    chips/        # satellite images (for VLM)
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

Each file does exactly one job. One file's output is the next file's input. **Every step produces a `.gpkg` file you can open in QGIS.**

---

# Day 1 — Data download

**Today's only goal: get FIRMS's CSV and OSM's polygons.**

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

**Check for yourself after running it:**
1. Was `data/processed/hotspots.gpkg` created? Not size 0?
2. Open QGIS → drag `hotspots.gpkg` in
3. Add a basemap: Browser panel → XYZ Tiles → OpenStreetMap (double-click)
4. Zoom into Jamnagar → you should see a dense cluster of dots over the refinery

**If the dots are in the wrong place (in the ocean, or on the other side of the world):** the bbox order got flipped. Longitude should come first.

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

**Day 1 is done when:** all three files show up together in QGIS, correctly, with Jamnagar's dots sitting on industry polygons and Uttarakhand's dots inside forest polygons.

**Seeing this = your whole idea is confirmed.** Take a screenshot.

---

# Day 2 — Context features + Persistence ⭐

**The most important day. This is your "innovation".**

### Prompt 2A (morning, ~1 hour)

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

**Check — these are the numbers you should see:**
- Jamnagar: small median distance (a few hundred metres)
- Uttarakhand: large median distance (several kilometres), `lc_class` mostly forest
- Punjab: `lc_class` mostly cropland

**If all three regions come out with similar numbers → the CRS is wrong. Stop here and fix it, don't move on.**

### Prompt 2B (afternoon) — the heart of the project

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

**This is the most important check:** does the top-20 list show **real refinery/plant names**? If yes — your project is working. Take a screenshot, it'll go in the PPT.

Uttarakhand's clusters should come out EPISODIC, Jamnagar's PERSISTENT.

---

# Day 3 — Labels

### Prompt 3A (morning, ~1 hour)

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

### Prompt 3B (leave it running in the background)

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

### Prompt 3C (afternoon, ~30 min)

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

### 🔴 Day 3 evening — you do this (~1 hour)

50 sources, ~1 minute each. Grab a cup of tea and sit down.

**Don't skip this.** The 3-4 mistakes you'll catch yourself — like a plant missing from OSM, or a spot that looks like it could be either thing — are exactly what will make your best slide and save you in the finals.

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

**What to expect:** a gold-set F1 of **0.75–0.85** is normal. If it comes out at 0.97, something's wrong somewhere (probably a lat/long feature leaking in).

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

**If short on time, this is the priority order:** before/after toggle → layers → popups → charts → download.

---

# Day 6 — Wiring it together and fixing bugs

**Don't build anything new. The whole day is for integration.**

- [ ] Run every step from scratch, start to end, once
- [ ] Build `run_all.py` that runs step1 through step5
- [ ] Open the Streamlit app, click through every filter — make sure nothing crashes
- [ ] **The PostGIS step (for the deliverable):** a small `src/step6_postgis.py` that loads the final `.gpkg` files into PostGIS (`geopandas.to_postgis`). One Docker command: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgis/postgis:16-3.4`. If it doesn't work, that's fine — GeoPackage is also a GIS format, just say so in the PPT
- [ ] Write the README: what was built, how to run it, screenshots
- [ ] Collect all screenshots into `outputs/`
- [ ] **Clone onto a different laptop and run it there** — "it worked on my laptop" is the biggest fear on demo day

---

# Day 7 — PPT + video

### PPT (10 slides)

| # | Slide |
|---|---|
| 1 | Problem — screenshot of the raw FIRMS map, thousands of identical-looking dots |
| 2 | Solution — a simple architecture diagram (4 boxes) |
| 3 | Approach — context → persistence → classification |
| 4 | **Labelling — how the labels were made** (rules + VLM + 50 human checks) |
| 5 | **Evaluation — all three numbers** and why they drop |
| 6 | Results — confusion matrix, SHAP, the reduction number |
| 7 | Dashboard — before/after screenshot |
| 8 | Impact — NTRO, critical infrastructure monitoring |
| 9 | **Limitations** — OSM gaps, coal fires, cloud cover, what's next |
| 10 | Tech stack + team |

**Slides 4, 5, and 9 are what will set you apart.** Most teams skip these and only show accuracy.

### Video (3 min)
Problem (20s) → before/after toggle (30s) → clicking the Jamnagar refinery (40s) → anomaly (30s) → Uttarakhand forest fire (25s) → export (15s)

---

## Download list — only 2 things

| What | Link |
|---|---|
| FIRMS MAP_KEY | https://firms.modaps.eosdis.nasa.gov/api/map_key/ ✅ obtained |
| OSM India pbf | https://download.geofabrik.de/asia/india.html |

FIRMS data downloads itself via the script. Satellite images come in at runtime. That's all.

---

## Reading — 1 hour total

**Before Day 1 (30 min):**

**CRS — the most essential 10 minutes**
https://geopandas.org/en/stable/docs/user_guide/projections.html
Just this much: EPSG:4326 = degrees (for displaying on a map), EPSG:32643 = metres (for distance). Always `to_crs(32643)` before computing distance.

**What FIRMS data actually is — 20 min**
https://www.earthdata.nasa.gov/data/tools/firms/faq
What `bright_ti4`, `frp`, `confidence`, `daynight` mean. These will come up in the finals.

**Before Day 2 (20 min):**
- GeoPandas's `sjoin_nearest` and `sjoin` docs — your entire feature engineering is just these 2 functions
- DBSCAN — just understand what `eps` and `min_samples` mean

**Before Day 4 (10 min):**
- Spatial leakage — https://www.mdpi.com/2624-795X/7/3/90 — just read the Abstract. This is what will build your slide 5

**QGIS — 15 min:** dragging a file in, adding an OpenStreetMap basemap via XYZ Tiles, looking at the attribute table, coloring by a column. That's enough.

---

## Each day's checkpoint

| Day | Done when |
|---|---|
| 1 | All three layers show up correctly in QGIS |
| 2 | Real plant names appear among the top persistent sources ⭐ |
| 3 | 3 classes labelled + 50 gold labels |
| 4 | Three evaluation numbers + confusion matrix |
| 5 | Before/after toggle working |
| 6 | Runs on a different laptop |
| 7 | PPT + video ready |

---

## When you get stuck — do this

**Can't understand Claude Code's code:**
Just ask it — *"explain this file line by line, I'm a 3rd year student"*. It'll explain it in plain language. Read at least one whole file every day, so you can explain your own code in the finals.

**Something isn't working:**
First, open the output in QGIS. 80% of bugs become visible to the eye right there.

**Falling behind on some day:**
Cut that day's scope, don't drag it into the next day. A small working system always beats a large, incomplete one.

**Starting to feel too complex:**
Recall the 4 lines above. Download → context → label → classify. Everything else is just details on top of that.

---

## One last thing

This plan is deliberately kept boring. There's nothing in it you can't debug or explain yourself. That's exactly how a 3rd-year project should be.

Your real edge isn't in fancy tech — it's in **Day 2's persistence idea** and **Day 3's honest labelling**. Most teams won't do either of these two things. Everything else is just plumbing, and plumbing should stay simple.
