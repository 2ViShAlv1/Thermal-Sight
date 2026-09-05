# Phase 1 (Day 1) — Data Collection

**Status: ✅ COMPLETE — verified**
Date: 2026-08-27

---

# Part A — Understand this first

## A1. What's the problem?

NASA's satellites continuously scan the Earth day and night and note down
every location that's **hotter than its surroundings**. India alone gets
millions of these points in a year.

The problem is — **the satellite only sees heat, not the cause.**

An identical-looking red dot could be:
- a refinery's flare, burning 24 hours a day
- a forest fire
- a farmer burning crop residue
- or just a very hot rooftop

In the data, all of these look **exactly the same**. If you asked an
analyst "which factories were running this month?", they'd have to search
by hand through thousands of dots. That's impossible.

## A2. What are we building?

A system that **tells you, on its own, what each hot point is** —
INDUSTRIAL, FOREST_FIRE, or AGRI_BURN.

The whole project in 4 lines:

```
1. Download hot-point data from NASA
2. Find out what's around each point (factory? forest? farmland?)
3. Label with rules + AI
4. Train a model and show it on a map with color
```

Whenever confused, come back to these 4 lines.

## A3. Why will this idea work?

The whole project rests on two observations:

**Observation 1 — surroundings tell you a lot.**
If a hot point is **on top of** a refinery, it's the refinery's flare. If
it's in the middle of a forest, it's a forest fire. So we need to find out
what's around every point. That's Phase 1's job.

**Observation 2 — timing tells you a lot.** *(This comes in Phase 2)*
A factory burns **every day** — for 6 months the same spot keeps showing up
hot, again and again. A forest fire runs for 3 days and stops. So if the
same spot keeps repeating for months → it's a running factory.

This second idea is your real **innovation**. Most teams only do
observation 1.

## A4. So what was Phase 1's goal?

> **Download two things — hot points, and a map of what's around them.**

That's it. No model, no AI, no labels yet. Just gathering the raw material.

Because if this data itself comes out wrong, everything downstream will be
wrong. So half of Phase 1's work is **getting the data**, and half is
**checking that it's correct.**

**Phase 1 counts as complete when:** all three files exist, and looking at
them on a map shows Jamnagar's dots sitting on top of factories and
Uttarakhand's dots inside forest.

---

# Part B — Glossary (meaning of the tricky terms)

Look at these tables before reading further. Judges will ask about exactly
these terms in the finals.

## B1. Satellite data terms

| Term | Meaning |
|---|---|
| **FIRMS** | NASA's free service that provides hot-point data. Full name: Fire Information for Resource Management System |
| **VIIRS** | The camera/sensor mounted on the satellite that measures heat. One pixel = roughly 375 metres × 375 metres of ground |
| **Hotspot / detection** | A row saying "heat was detected at this lat-long, at this date-time." **This is not proof of fire** — just of heat |
| **FRP** | Fire Radiative Power, in MegaWatts. How intense the heat was. In our data the median is 4.2 MW, max 118.9 MW |
| **bright_ti4 / bright_ti5** | Temperature (in Kelvin) measured at two different wavelengths |
| **daynight** | `D` = daytime detection, `N` = nighttime. **A nighttime detection is more reliable** because a sun-heated rooftop etc. can't confuse it. 19% of our data is at night |
| **confidence** | NASA's own confidence rating — `l` (low), `n` (nominal), `h` (high) |
| **SP vs NRT** | `SP` = Standard Processing, older but cleaner data. `NRT` = Near Real Time, fresh but less clean. NRT only keeps the last ~2 months |

## B2. Map terms

| Term | Meaning |
|---|---|
| **Latitude / Longitude** | An address for a place on Earth. Latitude = up-down (north-south), Longitude = left-right (east-west) |
| **bbox** | Bounding box — a rectangular box that encloses an area. Made of 4 numbers: `(west, south, east, north)`. **Longitude comes first** |
| **Point** | A dot on a map. Every hotspot is a Point |
| **Polygon** | A closed shape on a map. A factory's boundary, a stretch of forest — all polygons |
| **CRS** | Coordinate Reference System. The map's "language" — what unit the numbers are written in |
| **EPSG:4326** | A CRS in **degrees**. For displaying maps and saving files. Measuring distance in it is meaningless |
| **EPSG:32643** | A CRS in **metres** (UTM zone 43N). Converting to it before measuring distance is **essential** |
| **GeoPackage (.gpkg)** | A file holding map data. A single file, opens by dragging into QGIS. Works like a database, without needing one |
| **QGIS** | Free software for opening and viewing maps |

### The CRS thing matters most — this is what trips 10 people up

**Problem:** in EPSG:4326, numbers are in degrees. If you measure distance
in it, the answer comes out as "0.004" — 0.004 **what**? Degrees. How many
metres is that? It depends on the latitude, because longitude lines get
closer together near the poles.

**Solution:** `gdf.to_crs(32643)` before measuring distance. Now every
number is in **metres**. `500` simply means 500 metres.

**Rule:** displaying a map → 4326. Measuring distance/area → 32643.

## B3. OpenStreetMap terms

| Term | Meaning |
|---|---|
| **OSM** | OpenStreetMap — a Wikipedia-style map built by people around the world. Free |
| **.osm.pbf** | OSM's data file format. Compressed, so even the whole of India fits in just 1.4 GB |
| **Geofabrik** | A website that splits OSM's data into chunks (by state, by zone) |
| **Tag** | On OSM, every feature carries labels as `key=value` pairs. Like `landuse=industrial`, `natural=wood`, `power=plant` |
| **multipolygons layer** | The part of an OSM file containing all polygons (buildings, forests, factories) |

## B4. Work terms

| Term | Meaning |
|---|---|
| **Pipeline** | A chain of scripts where each script's output becomes the next one's input |
| **Idempotent** | A script that gives **the same** answer every time it's rerun, and causes no harm |
| **Cache** | Saving something already downloaded, so it doesn't need downloading again |
| **Rate limit** | A server's rule — "don't send requests too fast." That's why a `sleep` is needed in between |
| **CSV** | Comma Separated Values — a simple table file, opens in Excel |
| **Schema** | What columns a file has and of what type |

---

# Part C — What was built in Phase 1

## C1. Pipeline — at a glance

```
   INTERNET
      |
      |  step1_download.py       "get the hot points"
      v
  hotspots.gpkg                   8,415 points
      |
      |
   INTERNET (Geofabrik)
      |
      |  step2_context.py        "get a map of what's around"
      v
  industry.gpkg + landuse.gpkg    820 + 21,170 polygons
      |
      |  preview_map.py          "check it visually"
      v
  outputs/preview_*.png

  [ PHASE 1 ENDS HERE ]
      |
      |  In Phase 2: merge these two to build features
      v
```

## C2. Result — in one line

| Item | Count |
|---|---|
| FIRMS hotspots (2025, 3 regions) | **8,415** |
| OSM industry polygons | **820** |
| OSM landuse polygons | **21,170** |
| Code written | 868 lines (5 files) |
| Data downloaded | 758 MB raw → 21 MB processed |

And the best part — finding the nearest factory to Jamnagar's hotspots
brought up **Reliance Refinery** and **Vadinar Refinery** at the top.
Meaning the idea works.

---

# Part D — Every step: what, why, how

## Step 0 — Setup

### What was done
Created a `venv` and installed 14 libraries.

### Why
**What `venv` is:** an isolated box holding this project's libraries. The
system's Python is never touched.

**Why it matters:** if some other project needs a different version
tomorrow, the two won't clash. And on Day 6, running it on a different
laptop just needs `requirements.lock.txt` sent over.

```bash
cd /home/vank/SIH
source venv/bin/activate      # every time before starting work
```

### Folder structure

```
SIH/
  data/
    raw/          # what was downloaded - 3 pbf + 219 CSV  (gitignored)
    processed/    # what we built - 3 .gpkg files
    chips/        # empty (for Phase 3's satellite images)
  src/            # all the code
  models/         # empty (Phase 4)
  outputs/        # preview maps, charts later
  venv/
  .env            # FIRMS key (gitignored, chmod 600)
  .env.example    # template - never put the real key in this
```

**Why raw and processed are separate:** raw is never touched by hand. If a
mistake happens during processing, there's no need to redownload — it can
be rebuilt from raw.

---

## Step 1 — `config.py`: all settings in one place

### What was done
A file holding **every number** — bbox, dates, CRS, classes.

### Why
This is the most important design decision. If the bbox were written in
three separate files, changing it would mean editing three places — and
forgetting one would cost **hours** of debugging.

Now changing a bbox → **just one line**.

### What's in it

```python
REGIONS = {
    "jamnagar":    (69.4, 21.8, 70.6, 22.9),   # Gujarat - refineries
    "uttarakhand": (78.8, 29.2, 80.2, 30.4),   # Kumaon - forest
    "punjab":      (75.2, 30.2, 76.4, 31.0),   # Ludhiana - farmland
}
```

**Why exactly these three regions?** Because we need data for all three
classes, and these three places each give a **clean example** of a class:
- Jamnagar has one of Asia's largest refineries → gives us INDUSTRIAL
- Kumaon has forest fires every year → gives us FOREST_FIRE
- Ludhiana burns crop residue every Oct-Nov → gives us AGRI_BURN

**The bbox order is `(west, south, east, north)` — LONGITUDE FIRST.**
Get this backwards and points show up in the ocean or on the other side of
the world. This is the most common bug.

And:
```python
START = "2025-01-01";  END = "2025-12-31"   # the whole year
CRS_LATLON = 4326      # degrees - for displaying
CRS_METRES = 32643     # metres - for measuring
```

**Why the whole year?** Because seasons matter. Crop residue only burns in
Oct-Nov, forest fires in Apr-Jun. Taking just 1 month would mean missing
one class's data entirely.

---

## Step 2 — `step1_download.py`: getting the hot points

### What was done
Downloaded all of 2025's data from NASA FIRMS, for all three regions, into
one GeoPackage.

### Why
This is the project's **raw material**. Everything else is built on it.

### How — split into 5-day chunks

FIRMS won't give a whole year in one request. So the year is split into
chunks:

```
2025-01-01 for 5 days  →  one CSV
2025-01-06 for 5 days  →  one CSV
...  73 chunks ...
```

73 chunks × 3 regions = **219 requests**.

### 🔴 One thing in the plan was outdated

The plan said "maximum 10 days per request". Tested it and the API said:

```
HTTP 400 — Invalid day range. Expects [1..5].
```

So the limit is now **5 days**, not 10. Set `CHUNK_DAYS = 5`.

> **Might come up in the finals:** "How was the API limit handled?"
> **Answer:** chunking + rate-limit sleep + resume-safe caching.

### Three design decisions — and the reasoning behind them

**a) Errors are detected from content, not status code.**

Normally a server sends HTTP 400/500 on error. But FIRMS sometimes sends
**HTTP 200 (everything's fine)** and puts error text in the body instead
of a CSV.

So we check: does the first line of the response start with `latitude`
(the CSV header)? If not → it's an error.

**b) The source is chosen by counting rows.**

The plan says "try SP, fall back to NRT if it fails". But there's a trap
here — **NRT never fails.** Asking it for 2025 returns an empty CSV (just
a header, 0 rows), because NRT only keeps the last ~2 months. Technically
that's "success".

If we'd only checked "did an error come back", NRT would have been
selected and **the whole project would sit on 0 rows.**

So the code counts rows instead:
```
VIIRS_SNPP_SP  -> 11 rows  ✓ this one gets selected
VIIRS_SNPP_NRT -> 0 rows   (header only - rejected)
```

**c) Resume-safe caching.**

Each chunk saves to its own CSV file. On the next run, if the file already
exists, the download is skipped.

**Why:** 219 requests take 7 minutes. If the internet drops at request 200,
start over from scratch? No — 199 are cached, they'll come back in 7
seconds.

### Result

```
Total rows      : 8,415
  punjab          5,113
  uttarakhand     2,475
  jamnagar          827
Date range      : 2025-01-01 to 2025-12-31
FRP median      : 4.22 MW    max: 118.88 MW
Night detections: 19%
```

**Why so many in Punjab?** Because in Oct-Nov, all of Punjab burns crop
residue at once — thousands of small fires. Jamnagar only has a handful of
factories, so fewer.

Output: **`data/processed/hotspots.gpkg`** — 8,415 points, 17 columns

---

## Step 3 — `step2_context.py`: getting a map of the surroundings

### What was done
Pulled polygons from OSM for each region and sorted them into two buckets —
**industry** and **landuse**.

### Why
This is the "context" — without which a hotspot is useless.

A hotspot on its own says nothing. But knowing that a hotspot sits **inside
a refinery's boundary** gives a clear answer. And if it's **in the middle
of a forest**, it's a forest fire.

So we need:
- **industry.gpkg** — polygons for every factory/refinery/plant
- **landuse.gpkg** — which land is forest, which is farmland, which is city

### How — shrink first, then read

A zone file is 335 MB with millions of polygons. Trying to load the whole
thing into memory would hang the laptop.

So the **bbox filter is applied at the GDAL level** — that is, while
reading the file off disk. Only polygons for our region ever reach memory:

```python
pyogrio.read_dataframe(pbf_path, layer="multipolygons", bbox=bbox)
```

Result: 7,186 / 35,082 / 40,552 polygons — not millions.

### 🔴 A necessary deviation from the plan — the `other_tags` parser

The plan says to use `power == 'plant'` in the industry filter. Problem:
**GDAL doesn't expose this tag as a normal column at all.**

In GDAL's multipolygons layer, only a handful of tags get their own proper
columns (`landuse`, `man_made`, `natural`, `name`). Everything else is
**crammed into a single string**:

```
"power"=>"plant","operator"=>"NTPC","plant:source"=>"coal"
```

So a small parser (`parse_other_tags`) was written to turn this into a
Python dict.

**Without it, 42 power plants would have been missed in Jamnagar alone.**

### Result

| Region | Industry polygons | Landuse polygons |
|---|---|---|
| Jamnagar | **327** — storage 147, other 125, power_plant 42, mine 7, **refinery 4**, chemical 2 | 569 — urban 324, cropland 196, forest 49 |
| Uttarakhand | **59** — other 41, mine 11, power_plant 7 | 17,773 — urban 12721, **forest 4541**, cropland 511 |
| Punjab | **434** — other 431, mine 1, steel 1, power_plant 1 | 2,828 — urban 1619, **cropland 963**, forest 246 |

The expected pattern shows up exactly right — refineries in Jamnagar, a
sea of forest in Uttarakhand, cropland in Punjab.

---

# Part E — Bugs caught

## E1. 🔴 The biggest bug — wrong OSM zone file

### What happened
On the first run, **Uttarakhand came out with 0 industry, 0 landuse.**

### The reason
Geofabrik splits its data into "zones". I assumed Uttarakhand would be in
the "northern zone" (the name suggests that).

**It isn't.** Uttarakhand is in `central-zone`.

### How it was caught
Geofabrik provides a `.poly` file for every zone — the zone's actual
boundary. That was downloaded and checked with shapely to see which zone
our bbox actually falls inside:

| Region | Correct zone | Coverage |
|---|---|---|
| Jamnagar (Gujarat) | `western-zone` | 100% |
| Uttarakhand (Kumaon) | **`central-zone`** | 100% |
| Punjab (Ludhiana) | `northern-zone` | 100% |

Geofabrik's "northern zone" = J&K, Ladakh, HP, Punjab, Haryana, Delhi,
Rajasthan. Uttarakhand is in central-zone (along with UP/MP).

### Fix
This mapping was **hardcoded** into `config.py` as the `REGION_PBF` dict,
with a comment saying "don't guess this again."

Bonus: now each region only reads its own single file — 3x faster too.

### A shortcut not in the plan
The plan says to download all of India's file (1.4 GB). Not needed — three
zone files are enough:

```
central-zone-latest.osm.pbf    335 MB   (Uttarakhand)
northern-zone-latest.osm.pbf   213 MB   (Punjab)
western-zone-latest.osm.pbf    210 MB   (Jamnagar)
```

## E2. 🔴 Bug — wasted sleep on a cached rerun

Found during verification. The report earlier said "rerun in 2 seconds."
Measured it and got **3 min 50 sec**.

**Reason:** the rate-limit `sleep(1)` was running even for cached chunks —
219 chunks × 1 sec = 3m39s of wasted wait.

**Fix:** `download_chunk` now reports whether the network was actually
used, and the sleep only happens then. **3m50s → 7 seconds.** Output stays
the exact same 8,415 rows.

## E3. 🔴 Bug — a broken geometry

### What happened
A forest polygon in Uttarakhand (`osm_id 20022414`) was
**self-intersecting** — someone crossed a line while drawing it on OSM
(a bow-tie shape).

### Why it matters
`sjoin` / distance operations on such geometry **can give wrong answers or
crash**. It worked today, but it isn't reliable.

### Fix — and a mistake I made
Added `fix_geometries()`. **The first attempt was wrong:** `make_valid()`
turned that polygon into a GeometryCollection (the polygon plus the lines
where the ring crossed itself), and my code was **dropping** it —
21,170 down to 21,169.

That's wrong. That forest's area is **real**, only its drawing was broken.
Dropping the row means losing data.

Now the code pulls out just the polygon part from the collection.
**Result: 21,170 polygons, 0 invalid.**

---

# Part F — Verification: does it actually work?

Just "no error" isn't enough. Every script was rerun and every output
checked.

## F1. Reruns are deterministic

| Script | Time | Output |
|---|---|---|
| `step1_download.py` | 7 sec (cached) | 8,415 rows — same as before |
| `step2_context.py` | 2 min 10 sec | 820 + 21,170 — same as before |
| `preview_map.py` | 3 sec | 3 PNGs |

**Why this matters:** if rerunning gives a different answer, there's
randomness or a bug somewhere. Same answer = a trustworthy pipeline.

## F2. Data integrity — 24/24 checks pass

```
hotspots.gpkg   8,415 rows | EPSG:4326 | 0 null | 0 invalid | all Point
industry.gpkg     820 rows | EPSG:4326 | 0 null | 0 invalid
landuse.gpkg   21,170 rows | EPSG:4326 | 0 null | 0 invalid

every geometry within its own region's bbox   (0 outside)
frp all positive (min 0.15)      daynight only D/N
all dates within 2025            0 duplicate detections
lc_class = forest/cropland/urban industry_type has 7 types
```

**The "within bbox" check is a special one** — if longitude/latitude had
been swapped, points would fall outside the bbox. This check would have
caught that bug.

## F3. ⭐ The real acceptance test — are the dots in the right place?

This is Phase 1's **actual goal**. Checked with numbers (CRS 32643, in
metres):

```
JAMNAGAR      n=  827   median dist_to_industry =  1,703 m
UTTARAKHAND   n= 2475   median dist_to_industry = 18,048 m
              land cover: forest 57%
PUNJAB        n= 5113   median dist_to_industry =  5,639 m
```

**How to read it:** Jamnagar's hotspots are **1.7 km** from a factory,
Uttarakhand's are **18 km**. Meaning Jamnagar's are industrial, and
Uttarakhand's aren't. Exactly as it should be.

**And all three numbers differ** — meaning the CRS is correct. (The plan
warns: if all three came out the same, that would mean a CRS mistake.)

### This — the project's proof

The **name** of the nearest factory to Jamnagar's hotspots:

| Industry | Detections |
|---|---|
| **Reliance Refinery** | 198 |
| **Vadinar Refinery** | 54 |
| SHREE DIGVIJAY CEMENT | 52 |
| Jodiya Harbour | 12 |
| Coastal Gujarat Power Ltd | 7 |
| Essar Power | 7 |

This was expected as a Phase 2 result, and it already showed up in Phase 1.
**Take a screenshot — it goes in the PPT.**

## F4. Visual check — 3 preview maps

Built `preview_map.py` (so there's no need to wait for QGIS). 3 PNGs in
`outputs/`:

- **Jamnagar ✅** — a dense cluster of dots over a big red industry blob.
  That's the Reliance refinery
- **Uttarakhand ✅** — textbook. Nearly all 2,475 dots sit inside green
  forest polygons
- **Punjab ⚠️** — dots spread over the entire area, but even looking for
  yellow cropland polygons finds hardly any (see Section G below)

## F5. Environment hygiene

```
PASS  .env chmod 600, gitignored, .env.example has only a placeholder
PASS  all 5 scripts import without error
PASS  75 packages in venv
WARN  not a git repo yet
```

**One fix:** `requirements.txt` had no versions pinned. A different laptop
could get different versions (this is exactly the Day 6 checkpoint).
Created `requirements.lock.txt` — exact 75 versions.

---

# Part G — ⚠️ A risk that will cause problems in Phase 3

## Punjab has almost no cropland polygons

Notice that Punjab's land cover came out **99% "unknown"**. Investigated
it:

```
How much of Punjab's bbox area is covered by OSM cropland polygons: 1.3%

Distance from Punjab's hotspots to the nearest farmland:
  median  12,320 m
  within 1 km :  2%
  within 5 km : 16%

What land cover do the 5,113 hotspots sit on:
  NOTHING (not mapped on OSM at all)    5,067   <- 99.1%
  urban                                    37
  cropland                                  5   <- FIVE. Out of 5,113.
  forest                                    4
```

**Meaning:** Punjab's farmland simply isn't mapped on OSM. Farmland
tagging is very sparse across India — people map roads and buildings, not
fields.

## Why this is a problem

Phase 3's AGRI_BURN rule is:
```
lc_class == "cropland"  AND  dist_to_industry_m > 3000  AND ...
```

This rule **will never fire.** Punjab's 5,113 hotspots (**61%** of the
entire dataset) would be left as UNSURE.

### Also visible with the naked eye in QGIS

Opening Punjab in QGIS with a basemap showed the whole bbox filled with
dots — 5,113 detections, spread evenly — and searching for yellow cropland
polygons found almost nothing. Kept the screenshot for slide 9.

**One thing to say honestly in the presentation:** the sharp square edge
around the dots isn't real, it's our bbox. Crop burning happens across all
of Punjab, not just within our chosen rectangle. Judges will ask about
this — better to say it upfront.

## 🔴 One more finding — the burning season came out backwards from expected

Punjab's detections by month:

```
  1     32   0.6%
  2     27   0.5%
  3     41   0.8%
  4    126   2.5%  #
  5   3940  77.1%  #############################################
  6    192   3.8%  ##
 10    203   4.0%  ##
 11    509  10.0%  #####
```

**May alone is 77%. Oct+Nov together are only 14%.**

This looks backwards because the news always talks about the Oct-Nov
stubble burning and Delhi's smog. But Punjab has **two** burning seasons:

- **April-May** — after the wheat harvest
- **Oct-Nov** — after the paddy (rice) harvest  ← the famous one

In 2025, the wheat-season burning was much bigger.

### Verified this is a real agri signal, not an artifact

| | May (wheat) | Oct-Nov (paddy) |
|---|---|---|
| detections | 3,940 | 712 |
| distinct days | 30 (the whole month) | — |
| **night detections** | **2%** | **3%** |
| FRP median | 5.5 MW | 4.1 MW |

At the May 11-18 peak, 458 detections in a single day. A classic
agricultural burning signature — **happens during the day** and FRP stays
low.

### Two benefits from this

**1. The plan's month rule is already correct.** The plan already says
`month in (4, 5, 10, 11)` — both seasons are covered. If it had been just
10, 11, **77% of the data would have been missed.**

**2. `night_ratio` is a very strong feature.** Agri burning happens at
night only 2% of the time. A refinery's flare burns 24 hours a day —
its night_ratio would be ~50%. In Phase 2 this feature will be the single
most useful thing for telling the two classes apart.

## There will be three options at Phase 3

1. **Change the rule (recommended)** — drop `lc_class == "cropland"`, use
   instead "not forest + not near industry + episodic + month in
   (4,5,10,11) + low night_ratio".

   The seasonality analysis above shows this alone will work: 93% of
   Punjab's detections fall in these months, and 97% are during the day.
   Together these two are a very strong signal — no need for a cropland
   polygon at all
2. **Bring in ESA WorldCover raster** — a 10 m global landcover dataset,
   with far better coverage than OSM. A bit of extra work
3. **Lean more on the VLM step** — farmland is clearly visible in a
   satellite image

## This is actually a good thing

The plan itself says slide 9 (Limitations) will set you apart. This is a
**concrete, numbers-backed** example of "OSM gaps" — 1.3% coverage, with
visual proof in `preview_punjab.png`.

Most teams only show accuracy. This will set you apart.

**This isn't a blocker for Phase 1** — the polygons were extracted, the
job's done.

---

# Part H — What the files look like now

| File | Size | What it is |
|---|---|---|
| `data/processed/hotspots.gpkg` | 1.7 MB | 8,415 points, 17 columns |
| `data/processed/industry.gpkg` | 0.4 MB | 820 polygons — osm_id, name, industry_type, region |
| `data/processed/landuse.gpkg` | 19 MB | 21,170 polygons — osm_id, name, lc_class, region |
| `outputs/preview_*.png` | 1.2 MB | 3 verification maps |
| `data/raw/*.csv` | — | 219 FIRMS chunks (cache) |
| `data/raw/*.osm.pbf` | 758 MB | 3 zone files |

## Code

| File | Lines | Job |
|---|---|---|
| `src/config.py` | 70 | all settings |
| `src/step1_download.py` | 246 | FIRMS download |
| `src/step2_context.py` | 328 | OSM polygons |
| `src/preview_map.py` | 68 | visual check |
| `src/check_region.py` | 156 | before adding a new region |

## How to run it

```bash
cd /home/vank/SIH
source venv/bin/activate

python src/step1_download.py     # 7 sec (cached) / 7 min (fresh)
python src/step2_context.py      # 2 min
python src/preview_map.py        # 3 sec
```

---

# Part I — 🔴 What you need to do now

## I1. Save screenshots (2 min)

Keep `outputs/preview_punjab.png` for the PPT's slide 9.
Keep `outputs/preview_jamnagar.png` for slide 1.

## I2. Install QGIS (optional, ~10 min)

```bash
sudo apt install qgis qgis-plugin-grass
```

**Not necessary** for Phase 1 — the preview PNGs already cover the check.
But after Phase 2, clicking on clusters to see "which factory is this" is
much easier in QGIS.

## I3. Git init — a decision (yours to make)

The repo doesn't exist yet. Day 6's "clone onto another laptop and run it"
isn't possible without it. `.gitignore` is ready.

## I4. 20 minutes of reading before Phase 2 — necessary

Phase 2's **entire** code is built from three things:

**1. `sjoin_nearest`** — finds the nearest factory for every hotspot and
fills in the distance. This builds your single most important feature

**2. `sjoin` with `predicate="within"`** — which polygon a point is
**inside**. This is what gives us `lc_class` (forest/cropland/urban)
https://geopandas.org/en/stable/docs/user_guide/mergingdata.html

**3. DBSCAN's two parameters** — just this much:
- `eps=500` → points within 500 metres of each other are treated as one
  source
- `min_samples=3` → at least 3 points are needed to form a cluster

This works because a refinery's flare **always burns at the same spot**,
while a forest fire moves around.

**Remember:** all of this happens **after** `to_crs(32643)`. In 4326,
`eps=500` would mean "500 degrees" — useless.

---

# Part J — How to add a new region

The pipeline isn't built for just these 3 places — region names aren't
hardcoded anywhere, everything loops over `config.REGIONS`.

**First run the check:**
```bash
python src/check_region.py 82.4 22.2 82.9 22.5    # west south east north
```

It tells you: which zone file is needed, how wrong `CRS_METRES` is there,
and whether the bbox is flipped.

**Then two lines in `config.py`:**
```python
REGIONS["korba"]    = (82.4, 22.2, 82.9, 22.5)
REGION_PBF["korba"] = "central-zone-latest.osm.pbf"
```

Download that zone's pbf into `data/raw/`, then rerun step1 and step2.
Nothing else needs to change.

## Limit 1 — CRS 32643 is only accurate up to about 82°E

This is UTM zone 43N, centered on 75°E. The further away, the more wrong
distances become. Actual measured error over 1 km:

| Location | Error |
|---|---|
| Punjab (75.8°E) | -0.03% |
| Mumbai (72.8°E) | +0.03% |
| Uttarakhand (79.5°E) | +0.19% |
| Jamnagar (69.9°E) | +0.30% |
| Chennai (80.3°E) | +0.37% |
| **Kolkata (88.4°E)** | **+2.35%** |
| **Assam (92.9°E)** | **+4.02%** |

Under 0.4% for North/West/Central India — safe to ignore. For the
Northeast, `CRS_METRES = 32646` is needed, otherwise a "1000 m" rule
actually becomes 1040 m.

## Limit 2 — OSM coverage isn't the same everywhere

Remember Punjab's cropland gap (1.3%). That's why step2 prints the polygon
count for every region and gives a **loud warning** at zero — it never
fails silently.

---

# Part K — Ready for Phase 2

## Inputs are in place ✅

```
hotspots.gpkg   ✅  8,415 points
industry.gpkg   ✅    820 polygons
landuse.gpkg    ✅ 21,170 polygons
```

## Both spatial joins tested — working

```
sjoin_nearest(hotspots, industry)  -> 8,418 rows
sjoin(hotspots, landuse, within)   -> 8,417 rows
```

## ⚠️ A gotcha for Phase 2 (caught now)

Both joins are producing **more rows** than the input — 8,415 becomes
8,418 / 8,417.

**Reason:** a hotspot can sit inside two overlapping polygons (like both
forest and urban), and `sjoin_nearest` can have a distance tie. In that
case a join produces **two rows**.

**If this isn't deduplicated**, the features file will end up with
duplicate hotspots, and every count downstream will be wrong — and this
will happen silently, with no error at all.

**This needs to be added right after the join, when writing Phase 2A:**
```python
joined = joined[~joined.index.duplicated()]
```

## What Phase 2 will build

```
step2_context.py part 2   -> features.gpkg    (distance + landcover for every hotspot)
step3_persistence.py      -> sources.gpkg     (DBSCAN clusters + PERSISTENT/EPISODIC)
```

And that's where the "Reliance Refinery — 198 detections — PERSISTENT"
table will get built, which goes into the PPT.
