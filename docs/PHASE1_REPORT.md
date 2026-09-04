# Phase 1 (Day 1) — Data Collection

**Status: ✅ COMPLETE — verified**
Date: 2026-08-27

---

# Part A — Pehle ye samjho

## A1. Problem kya hai?

NASA ke satellites din-raat dharti ko scan karte rehte hain aur har us jagah
ko note karte hain jo **aas-paas se zyada garam** hai. Ek saal mein bharat mein
aise lakhon points aate hain.

Problem ye hai — **satellite ko sirf garmi dikhti hai, wajah nahi.**

Ek hi jaisa laal dot ho sakta hai:
- ek refinery ka flare jo 24 ghante jal raha hai
- jungle ki aag
- kisan ka parali jalana
- ya bas ek bahut garam chhat

Data mein sab **bilkul ek jaise** dikhte hain. Ek analyst ko agar poochho
"is mahine kaunsi factories chal rahi thi?", to use hazaaron dots mein se
haath se dhoondhna padega. Ye impossible hai.

## A2. Hum kya bana rahe hain?

Ek system jo har garam point ko **khud batata hai ki wo kya hai** —
INDUSTRIAL, FOREST_FIRE, ya AGRI_BURN.

Poora project 4 lines mein:

```
1. NASA se garam points ka data download karo
2. Pata karo har point ke aas-paas kya hai (factory? jungle? khet?)
3. Rules + AI se label lagao
4. Model train karke map pe colour ke saath dikhao
```

Jab bhi confuse lago, in 4 lines pe wapas aana.

## A3. Idea kaam kyun karega?

Do observations pe pura project khada hai:

**Observation 1 — Aas-paas se pata chalta hai.**
Agar garam point ek refinery ke **upar** hai, to wo refinery ka flare hai.
Agar jungle ke beech mein hai, to jungle ki aag hai. Isliye humein har point
ke aas-paas kya hai, ye pata karna hoga. Yahi Phase 1 ka kaam hai.

**Observation 2 — Time se pata chalta hai.** *(Ye Phase 2 mein aayega)*
Factory **roz** jalti hai — 6 mahine tak wahi ek jagah baar-baar garam
dikhegi. Jungle ki aag 3 din chalti hai aur khatam. Yani agar ek hi jagah
mahinon tak repeat ho rahi hai → wo chalti hui factory hai.

Ye doosra idea hi tumhara asli **innovation** hai. Zyadatar teams sirf
observation 1 karti hain.

## A4. To Phase 1 ka aim kya tha?

> **Do cheezein download karna — garam points, aur unke aas-paas ka naksha.**

Bas itna. Na koi model, na koi AI, na koi label. Sirf raw material jama karna.

Kyunki agar ye data hi galat aaya, to aage sab kuch galat hoga. Isliye Phase 1
ka aadha kaam **data laana** hai aur aadha **check karna ki wo sahi hai.**

**Phase 1 tab poora mana jayega jab:** teeno files ban jayein, aur unhe map pe
dekhne par Jamnagar ke dots factory ke upar dikhein aur Uttarakhand ke dots
jungle ke andar.

---

# Part B — Shabdkosh (mushkil shabdon ka matlab)

Aage padhne se pehle ye tables dekh lo. Finale mein judges yahi terms poochenge.

## B1. Satellite data ke shabd

| Shabd | Matlab |
|---|---|
| **FIRMS** | NASA ki free service jo garam points ka data deti hai. Pura naam: Fire Information for Resource Management System |
| **VIIRS** | Wo camera/sensor jo satellite pe laga hai aur garmi naapta hai. Ek pixel = lagbhag 375 metre × 375 metre zameen |
| **Hotspot / detection** | Ek row jo kehti hai "is lat-long pe, is date-time pe, garmi mili thi". **Ye aag ka saboot nahi hai** — bas garmi ka |
| **FRP** | Fire Radiative Power, MegaWatt mein. Wo garmi kitni tez thi. Hamare data mein median 4.2 MW, max 118.9 MW |
| **bright_ti4 / bright_ti5** | Do alag wavelengths pe naapa gaya temperature (Kelvin mein) |
| **daynight** | `D` = din ka detection, `N` = raat ka. **Raat ka detection zyada bharosemand hai** kyunki dhoop se garam hui chhat wagairah confuse nahi karti. Hamare data mein 19% raat ke hain |
| **confidence** | NASA ka apna bharosa — `l` (low), `n` (nominal), `h` (high) |
| **SP vs NRT** | `SP` = Standard Processing, purana par saaf data. `NRT` = Near Real Time, taaza par kam saaf. NRT sirf pichhle ~2 mahine rakhta hai |

## B2. Naksha (map) ke shabd

| Shabd | Matlab |
|---|---|
| **Latitude / Longitude** | Zameen pe kisi jagah ka pata. Latitude = upar-neeche (uttar-dakshin), Longitude = daayein-baayein (poorab-pashchim) |
| **bbox** | Bounding box — ek chaukor dabba jo kisi ilaake ko gher leta hai. 4 numbers se banta hai: `(west, south, east, north)`. **Longitude pehle aata hai** |
| **Point** | Naksha pe ek dot. Har hotspot ek Point hai |
| **Polygon** | Naksha pe ek band aakriti (shape). Ek factory ka ahaata, ek jungle ka ilaaka — sab polygons hain |
| **CRS** | Coordinate Reference System. Naksha ki "bhaasha" — kis unit mein numbers likhe hain |
| **EPSG:4326** | CRS jo **degrees** mein hai. Naksha dikhane aur file save karne ke liye. Yahan distance naapna bekaar hai |
| **EPSG:32643** | CRS jo **metres** mein hai (UTM zone 43N). Distance naapne se pehle isme convert karna **zaroori** hai |
| **GeoPackage (.gpkg)** | Ek file jisme naksha ka data hota hai. Ek hi file, QGIS mein drag karke khul jati hai. Database jaisa kaam, bina database ke |
| **QGIS** | Free software jisme naksha kholke dekh sakte ho |

### CRS ki baat sabse zaroori hai — isse 10 log fasten hain

**Problem:** EPSG:4326 mein numbers degrees mein hote hain. Agar tum usme
distance naapo, to jawab "0.004" aayega — 0.004 **kya**? Degrees. Wo kitne
metre hue? Ye latitude pe depend karta hai, kyunki poles ke paas longitude
ki lines paas aa jati hain.

**Solution:** distance naapne se pehle `gdf.to_crs(32643)`. Ab har number
**metre** mein hai. `500` ka matlab seedha 500 metre.

**Rule:** naksha dikhana ho → 4326. Distance/area naapna ho → 32643.

## B3. OpenStreetMap ke shabd

| Shabd | Matlab |
|---|---|
| **OSM** | OpenStreetMap — Wikipedia jaisa naksha, jise duniya bhar ke log banate hain. Free hai |
| **.osm.pbf** | OSM ka data file format. Compressed hota hai, isliye India ki poori file bhi sirf 1.4 GB hai |
| **Geofabrik** | Website jo OSM ka data tukdon mein baant kar deti hai (state-wise, zone-wise) |
| **Tag** | OSM mein har cheez pe labels lage hote hain, `key=value` ke roop mein. Jaise `landuse=industrial`, `natural=wood`, `power=plant` |
| **multipolygons layer** | OSM file ka wo hissa jisme saare polygons hain (buildings, forests, factories) |

## B4. Kaam ke shabd

| Shabd | Matlab |
|---|---|
| **Pipeline** | Scripts ki ek line jahan har script ka output agli ka input banta hai |
| **Idempotent** | Ek script jo dobara chalane pe **wahi** jawab de, aur nuksaan na kare |
| **Cache** | Downloaded cheez ko save kar lena, taaki dobara download na karna pade |
| **Rate limit** | Server ka niyam — "itni tez requests mat bhejo". Isliye beech mein `sleep` lagana padta hai |
| **CSV** | Comma Separated Values — simple table file, Excel mein khul jati hai |
| **Schema** | File mein kaun-kaun se columns hain aur kis type ke |

---

# Part C — Phase 1 mein kya banaya

## C1. Pipeline — ek nazar mein

```
   INTERNET
      |
      |  step1_download.py       "garam points laao"
      v
  hotspots.gpkg                   8,415 points
      |
      |
   INTERNET (Geofabrik)
      |
      |  step2_context.py        "aas-paas ka naksha laao"
      v
  industry.gpkg + landuse.gpkg    820 + 21,170 polygons
      |
      |  preview_map.py          "aankhon se check karo"
      v
  outputs/preview_*.png

  [ PHASE 1 YAHAN KHATAM ]
      |
      |  Phase 2 mein: in dono ko jodkar features banana
      v
```

## C2. Result — ek line mein

| Cheez | Count |
|---|---|
| FIRMS hotspots (2025, 3 regions) | **8,415** |
| OSM industry polygons | **820** |
| OSM landuse polygons | **21,170** |
| Code likha | 868 lines (5 files) |
| Data download | 758 MB raw → 21 MB processed |

Aur sabse badi baat — Jamnagar ke hotspots ka nearest factory nikala to top pe
**Reliance Refinery** aur **Vadinar Refinery** aaye. Yani idea kaam kar raha hai.

---

# Part D — Har step: kya, kyun, kaise

## Step 0 — Setup

### Kya kiya
Ek `venv` banaya aur 14 libraries install kin.

### Kyun
**`venv` kya hai:** ek alag dabba jisme is project ki libraries rehti hain.
System ke Python ko chhua nahi jata.

**Kyun zaroori:** agar kal koi doosra project alag version maange, to dono
aapas mein nahi ladenge. Aur Day 6 pe doosre laptop pe chalane ke liye bas
`requirements.lock.txt` bhejna hoga.

```bash
cd /home/vank/SIH
source venv/bin/activate      # har baar kaam se pehle
```

### Folder structure

```
SIH/
  data/
    raw/          # jo download kiya - 3 pbf + 219 CSV  (gitignored)
    processed/    # jo humne banaya - 3 .gpkg files
    chips/        # khaali (Phase 3 ke satellite images ke liye)
  src/            # saara code
  models/         # khaali (Phase 4)
  outputs/        # preview maps, aage charts bhi
  venv/
  .env            # FIRMS key (gitignored, chmod 600)
  .env.example    # template - isme asli key kabhi mat daalna
```

**Raw aur processed alag kyun:** raw ko kabhi haath nahi lagate. Agar processing
mein galti ho jaye, to dobara download nahi karna padta — raw se phir se bana
sakte ho.

---

## Step 1 — `config.py`: saari settings ek jagah

### Kya kiya
Ek file jisme **saare numbers** hain — bbox, dates, CRS, classes.

### Kyun
Ye sabse important design decision hai. Agar bbox teen alag files mein likha
hota, aur tumhe use badalna pade, to teen jagah badalna padta — aur ek jagah
bhoolne pe **ghanton** debug karte.

Ab bbox badalna ho → **sirf ek line**.

### Isme kya hai

```python
REGIONS = {
    "jamnagar":    (69.4, 21.8, 70.6, 22.9),   # Gujarat - refineries
    "uttarakhand": (78.8, 29.2, 80.2, 30.4),   # Kumaon - jungle
    "punjab":      (75.2, 30.2, 76.4, 31.0),   # Ludhiana - khet
}
```

**Teen regions hi kyun chune?** Kyunki humein teeno classes ka data chahiye,
aur ye teen jagah har class ka **saaf udaharan** deti hain:
- Jamnagar mein Asia ki sabse badi refinery hai → INDUSTRIAL milega
- Kumaon mein har saal jungle ki aag lagti hai → FOREST_FIRE milega
- Ludhiana mein Oct-Nov mein parali jalti hai → AGRI_BURN milega

**Bbox ka order `(west, south, east, north)` hai — LONGITUDE PEHLE.**
Ye ulta ho gaya to points samundar mein ya duniya ke doosre kone mein dikhenge.
Ye sabse common bug hai.

Aur:
```python
START = "2025-01-01";  END = "2025-12-31"   # pura saal
CRS_LATLON = 4326      # degrees - dikhane ke liye
CRS_METRES = 32643     # metres - naapne ke liye
```

**Pura saal kyun?** Kyunki seasons matter karte hain. Parali sirf Oct-Nov mein
jalti hai, jungle ki aag Apr-Jun mein. Agar sirf 1 mahina lete, to ek class ka
data hi na milta.

---

## Step 2 — `step1_download.py`: garam points laana

### Kya kiya
NASA FIRMS se 2025 ka pura data, teeno regions ke liye, download karke ek
GeoPackage banaya.

### Kyun
Ye project ka **kaccha maal** hai. Har cheez isi pe khadi hogi.

### Kaise — 5-5 din ke tukde

FIRMS ek request mein pura saal nahi deta. Isliye saal ko tukdon mein todte hain:

```
2025-01-01 se 5 din  →  ek CSV
2025-01-06 se 5 din  →  ek CSV
...  73 tukde ...
```

73 tukde × 3 regions = **219 requests**.

### 🔴 Plan mein ek cheez purani thi

Plan kehta tha "maximum 10 days per request". Test kiya to API ne bola:

```
HTTP 400 — Invalid day range. Expects [1..5].
```

To limit ab **5 din** hai, 10 nahi. `CHUNK_DAYS = 5` kar diya.

> **Finale mein pooch sakte hain:** "API limit kaise handle ki?"
> **Jawab:** chunking + rate-limit sleep + resume-safe caching.

### Teen design decisions — aur unke peeche ki soch

**a) Error content se pakadte hain, status code se nahi.**

Normally server galti pe HTTP 400/500 bhejta hai. Par FIRMS kabhi-kabhi
**HTTP 200 (sab theek hai)** bhejta hai, aur body mein CSV ki jagah error
text daal deta hai.

To humne check kiya: response ki pehli line `latitude` se shuru hoti hai ya
nahi (CSV ka header). Nahi → error hai.

**b) Source chunne ke liye rows ginte hain.**

Plan kehta hai "SP try karo, fail ho to NRT". Par yahan ek jaal hai —
**NRT fail hota hi nahi.** 2025 maangne pe wo khaali CSV bhejta hai
(sirf header, 0 rows), kyunki NRT sirf pichhle ~2 mahine rakhta hai.
Technically "success" hai.

Agar humne sirf "error to nahi aaya" check kiya hota, to NRT select ho jata
aur **poora project 0 rows pe khada hota**.

Isliye code rows ginta hai:
```
VIIRS_SNPP_SP  -> 11 rows  ✓ ye select hua
VIIRS_SNPP_NRT -> 0 rows   (sirf header - reject)
```

**c) Resume-safe caching.**

Har tukda apni CSV file mein save hota hai. Agli baar chalane pe, file exist
kare to download skip.

**Kyun:** 219 requests mein 7 minute lagte hain. Agar 200th pe internet gaya,
to dobara shuru se? Nahi — 199 cached hain, wo 7 second mein nikal jayenge.

### Result

```
Total rows      : 8,415
  punjab          5,113
  uttarakhand     2,475
  jamnagar          827
Date range      : 2025-01-01 se 2025-12-31
FRP median      : 4.22 MW    max: 118.88 MW
Night detections: 19%
```

**Punjab mein itne zyada kyun?** Kyunki Oct-Nov mein poore Punjab mein ek
saath parali jalti hai — hazaaron chhoti aag. Jamnagar mein sirf kuch
factories hain, isliye kam.

Output: **`data/processed/hotspots.gpkg`** — 8,415 points, 17 columns

---

## Step 3 — `step2_context.py`: aas-paas ka naksha laana

### Kya kiya
OSM se har region ke polygons nikale, aur do buckets mein daale —
**industry** aur **landuse**.

### Kyun
Yahi "context" hai — jiske bina hotspot bekaar hai.

Ek hotspot akela kuch nahi batata. Par agar pata chal jaye ki wo hotspot
ek **refinery ke ahaate ke andar** hai, to jawab saaf hai. Aur agar wo
**jungle ke beech** hai, to wo jungle ki aag hai.

To humein chahiye:
- **industry.gpkg** — saare factories/refineries/plants ke polygons
- **landuse.gpkg** — kaunsi zameen jungle hai, kaunsi khet, kaunsi shehar

### Kaise — pehle chhota karo, phir padho

Zone file 335 MB ki hai, usme lakhon polygons hain. Poori file memory mein
lene ki koshish karoge to laptop hang ho jayega.

Isliye **bbox filter GDAL ke level pe** lagta hai — yani file padhte waqt hi,
disk pe. Sirf hamare ilaake ke polygons memory mein aate hain:

```python
pyogrio.read_dataframe(pbf_path, layer="multipolygons", bbox=bbox)
```

Result: 7,186 / 35,082 / 40,552 polygons — lakhon nahi.

### 🔴 Plan se ek zaroori deviation — `other_tags` parser

Plan kehta hai industry filter mein `power == 'plant'` use karo.
Problem: **GDAL ye tag normal column mein deta hi nahi.**

GDAL ke multipolygons layer mein kuch hi tags ke proper columns bante hain
(`landuse`, `man_made`, `natural`, `name`). Baaki **sab ek single string
mein thuse** hote hain:

```
"power"=>"plant","operator"=>"NTPC","plant:source"=>"coal"
```

Isliye ek chhota parser likha (`parse_other_tags`) jo isse Python dict bana
deta hai.

**Iske bina akele Jamnagar mein 42 power plants miss ho jate.**

### Result

| Region | Industry polygons | Landuse polygons |
|---|---|---|
| Jamnagar | **327** — storage 147, other 125, power_plant 42, mine 7, **refinery 4**, chemical 2 | 569 — urban 324, cropland 196, forest 49 |
| Uttarakhand | **59** — other 41, mine 11, power_plant 7 | 17,773 — urban 12721, **forest 4541**, cropland 511 |
| Punjab | **434** — other 431, mine 1, steel 1, power_plant 1 | 2,828 — urban 1619, **cropland 963**, forest 246 |

Expected pattern bilkul mil raha hai — Jamnagar mein refineries, Uttarakhand
mein forest ka dher, Punjab mein cropland.

---

# Part E — Jo galtiyan pakdi

## E1. 🔴 Sabse bada bug — galat OSM zone file

### Kya hua
Pehli baar chalane pe **Uttarakhand mein 0 industry, 0 landuse** aaye.

### Wajah
Geofabrik apne data ko "zones" mein baantta hai. Maine socha "northern zone"
mein Uttarakhand hoga (naam se to yahi lagta hai).

**Hai hi nahi.** Uttarakhand `central-zone` mein hai.

### Kaise pakda
Geofabrik har zone ki `.poly` file deti hai — usme us zone ki asli boundary
hoti hai. Wo download karke shapely se check kiya ki hamara bbox kis zone ke
andar aata hai:

| Region | Sahi zone | Coverage |
|---|---|---|
| Jamnagar (Gujarat) | `western-zone` | 100% |
| Uttarakhand (Kumaon) | **`central-zone`** | 100% |
| Punjab (Ludhiana) | `northern-zone` | 100% |

Geofabrik ka "northern zone" = J&K, Ladakh, HP, Punjab, Haryana, Delhi,
Rajasthan. Uttarakhand central-zone mein hai (UP/MP ke saath).

### Fix
Ye mapping `config.py` mein `REGION_PBF` dict ke roop mein **hardcode kar di**,
comment ke saath ki "dobara mat guess karna".

Bonus: ab har region sirf apni ek file padhta hai — 3 guna tez bhi ho gaya.

### Ek shortcut jo plan mein nahi tha
Plan bolta hai poori India ki file (1.4 GB) download karo. Zaroorat nahi —
teen zone files kaafi hain:

```
central-zone-latest.osm.pbf    335 MB   (Uttarakhand)
northern-zone-latest.osm.pbf   213 MB   (Punjab)
western-zone-latest.osm.pbf    210 MB   (Jamnagar)
```

## E2. 🔴 Bug — cached rerun pe bekaar sleep

Verification ke waqt mila. Maine report mein pehle likha tha "rerun 2 second
mein". Measure kiya to **3 min 50 sec** nikla.

**Wajah:** rate-limit wali `sleep(1)` cached chunks pe bhi chal rahi thi —
219 chunks × 1 sec = 3m39s bekaar wait.

**Fix:** `download_chunk` ab batata hai ki network use hua ya nahi, aur sleep
sirf tab hoti hai. **3m50s → 7 second.** Output bilkul same 8,415 rows.

## E3. 🔴 Bug — ek tooti geometry

### Kya hua
Uttarakhand mein ek forest polygon (`osm_id 20022414`) **self-intersecting**
tha — kisi ne OSM pe map karte waqt line cross kar di thi (bow-tie shape).

### Kyun matter karta hai
Aisi geometry pe `sjoin` / distance operations **galat jawab de sakte hain
ya crash kar sakte hain**. Aaj chal gaya, par ye bharosemand nahi hai.

### Fix — aur meri ek galti
`fix_geometries()` add kiya. **Pehla attempt galat tha:** `make_valid()` ne
us polygon ko GeometryCollection bana diya (polygon + wo lines jahan ring
cut kar raha tha), aur mera code use **gira** raha tha — 21,170 se 21,169.

Wo galat hai. Us jungle ka area **asli** hai, bas uski drawing tooti thi.
Row girana matlab data khona.

Ab code collection mein se sirf polygon wala hissa nikaal leta hai.
**Result: 21,170 polygons, 0 invalid.**

---

# Part F — Verification: sach mein chal raha hai?

Sirf "error nahi aaya" kaafi nahi hai. Har script rerun kiya aur har output
check kiya.

## F1. Reruns deterministic hain

| Script | Time | Output |
|---|---|---|
| `step1_download.py` | 7 sec (cached) | 8,415 rows — pehle jaisa hi |
| `step2_context.py` | 2 min 10 sec | 820 + 21,170 — pehle jaisa hi |
| `preview_map.py` | 3 sec | 3 PNG |

**Kyun matter karta hai:** dobara chalane pe alag jawab aaye to kahin randomness
ya bug hai. Same jawab = bharosemand pipeline.

## F2. Data integrity — 24/24 checks pass

```
hotspots.gpkg   8,415 rows | EPSG:4326 | 0 null | 0 invalid | sab Point
industry.gpkg     820 rows | EPSG:4326 | 0 null | 0 invalid
landuse.gpkg   21,170 rows | EPSG:4326 | 0 null | 0 invalid

saari geometries apne region ke bbox ke andar   (0 bahar)
frp sab positive (min 0.15)      daynight sirf D/N
saare dates 2025 mein            0 duplicate detections
lc_class = forest/cropland/urban industry_type mein 7 types
```

**"Bbox ke andar" wala check khaas hai** — agar longitude/latitude ulte ho gaye
hote, to points bbox se bahar dikhte. Ye check us bug ko pakad leta.

## F3. ⭐ Asli acceptance test — dots sahi jagah baithe hain?

Ye Phase 1 ka **actual goal** hai. Numbers se check kiya (CRS 32643, metres mein):

```
JAMNAGAR      n=  827   median dist_to_industry =  1,703 m
UTTARAKHAND   n= 2475   median dist_to_industry = 18,048 m
              land cover: forest 57%
PUNJAB        n= 5113   median dist_to_industry =  5,639 m
```

**Kaise padhein:** Jamnagar ke hotspots factory se **1.7 km** door hain,
Uttarakhand ke **18 km**. Yani Jamnagar wale industrial hain, Uttarakhand
wale nahi. Bilkul waisa hi jaisa hona chahiye.

**Aur teeno numbers alag hain** — iska matlab CRS sahi hai. (Plan warn karta
hai: teeno ek jaise aayein to CRS ki galti hai.)

### Ye — pure project ka proof

Jamnagar ke hotspots ka nearest factory ka **naam**:

| Industry | Detections |
|---|---|
| **Reliance Refinery** | 198 |
| **Vadinar Refinery** | 54 |
| SHREE DIGVIJAY CEMENT | 52 |
| Jodiya Harbour | 12 |
| Coastal Gujarat Power Ltd | 7 |
| Essar Power | 7 |

Ye Phase 2 ka expected result tha, Phase 1 pe hi dikh gaya.
**Screenshot le lo — PPT mein jayega.**

## F4. Visual check — 3 preview maps

`preview_map.py` banaya (QGIS ka wait na karna pade). `outputs/` mein 3 PNG:

- **Jamnagar ✅** — bade laal industry blob pe dots ka ghana jhund. Wo Reliance
  refinery hai
- **Uttarakhand ✅** — textbook. Lagbhag saare 2,475 dots hare forest polygons
  ke andar
- **Punjab ⚠️** — dots poore ilaake pe chhaye hue, par peele cropland polygons
  dhoondhne pe bhi nahi milte (neeche section G dekho)

## F5. Environment hygiene

```
PASS  .env chmod 600, gitignored, .env.example mein sirf placeholder
PASS  saare 5 scripts bina error import ho jaate hain
PASS  venv mein 75 packages
WARN  git repo abhi nahi hai
```

**Ek fix:** `requirements.txt` mein koi version pinned nahi tha. Doosre laptop
pe alag version aa sakta tha (Day 6 ka checkpoint yahi hai).
`requirements.lock.txt` bana diya — exact 75 versions.

---

# Part G — ⚠️ Ek risk jo Phase 3 pe problem karega

## Punjab mein cropland polygons hain hi nahi

Notice karo Punjab mein land cover **99% "unknown"** nikla. Investigate kiya:

```
Punjab bbox ka kitna area OSM cropland polygons se covered:  1.3%

Punjab hotspots ka nearest khet se distance:
  median  12,320 m
  1 km ke andar :  2%
  5 km ke andar : 16%

5,113 hotspots kis land cover pe baithe hain:
  KUCH NAHI (OSM pe mapped hi nahi)    5,067   <- 99.1%
  urban                                    37
  cropland                                  5   <- PAANCH. 5,113 mein se.
  forest                                    4
```

**Matlab:** OSM pe Punjab ke khet mapped hi nahi hain. India mein farmland
tagging bahut kam hai — log sadak aur building to map karte hain, khet nahi.

## Ye kyun problem hai

Phase 3 ka AGRI_BURN rule ye hai:
```
lc_class == "cropland"  AND  dist_to_industry_m > 3000  AND ...
```

Ye rule **kabhi fire hi nahi karega**. Punjab ke 5,113 hotspots
(pure dataset ka **61%**) UNSURE reh jayenge.

### QGIS mein aankhon se bhi dikh gaya

Punjab ko QGIS mein basemap ke saath khola to poora bbox dots se bhara mila —
5,113 detections, ek-saman chhaye hue — aur peele cropland polygons dhoondhne
pe bhi nahi milte. Screenshot slide 9 ke liye rakh liya.

**Ek baat presentation mein honestly bata dena:** dots ka tez chaukor kinaara
asli nahi hai, wo hamara bbox hai. Parali poore Punjab mein jalti hai, hamari
chuni hui chaukor pe rukti nahi. Judges ye poochenge — pehle hi bol dena behtar.

## 🔴 Aur ek finding — burning season expected se ulta nikla

Punjab ke detections mahine ke hisaab se:

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

**May akela 77% hai. Oct+Nov milkar sirf 14%.**

Ye ulta lagta hai kyunki news mein hamesha Oct-Nov ki parali aur Delhi ke smog
ki baat hoti hai. Par Punjab mein **do** burning season hote hain:

- **April-May** — gehun (wheat) ki katai ke baad
- **Oct-Nov** — dhaan (paddy) ki katai ke baad  ← ye famous wala

2025 mein gehun wala season kahin bada tha.

### Verify kiya ki ye asli agri signal hai, artifact nahi

| | May (gehun) | Oct-Nov (dhaan) |
|---|---|---|
| detections | 3,940 | 712 |
| kitne alag din | 30 (poora mahina) | — |
| **night detections** | **2%** | **3%** |
| FRP median | 5.5 MW | 4.1 MW |

Peak May 11-18 pe, ek din mein 458 detections. Classic agricultural burning
signature — **din mein hoti hai** aur FRP chhota hota hai.

### Isse do faayde

**1. Plan ka month rule already sahi hai.** Plan mein `month in (4, 5, 10, 11)`
likha hai — dono season cover ho rahe hain. Agar sirf 10, 11 hota to **77%
data chhoot jata**.

**2. `night_ratio` bahut strong feature hai.** Agri burning 2% raat mein hoti
hai. Refinery ka flare 24 ghante jalta hai — uska night_ratio ~50% hoga.
Phase 2 mein ye feature dono classes ko alag karne mein sabse kaam aayega.

## Phase 3 pe teen options honge

1. **Rule badlo (recommended)** — `lc_class == "cropland"` hatao, uski jagah
   "not forest + not near industry + episodic + month in (4,5,10,11) +
   night_ratio kam" use karo.

   Upar wale seasonality analysis se pata chala ki ye akela hi kaam kar
   jayega: Punjab ke 93% detections in mahinon mein hain, aur 97% din ke
   hain. Dono milkar bahut strong signal hain — cropland polygon ki
   zaroorat hi nahi
2. **ESA WorldCover raster** laao — 10 m ka global landcover, OSM se kahin
   behtar coverage. Thoda extra kaam
3. **VLM step pe zyada bharosa** — satellite image mein khet saaf dikhte hain

## Ye actually achhi baat hai

Plan khud kehta hai slide 9 (Limitations) tumhe alag dikhayegi. "OSM gaps" ka
ye ek **concrete, numbers-backed** udaharan hai — 1.3% coverage, aur uska
visual proof `preview_punjab.png` mein.

Zyadatar teams sirf accuracy dikhati hain. Ye tumhe alag dikhayega.

**Phase 1 ke liye ye blocker nahi hai** — polygons extract ho gaye, kaam ho gaya.

---

# Part H — Files ab kya hain

| File | Size | Kya hai |
|---|---|---|
| `data/processed/hotspots.gpkg` | 1.7 MB | 8,415 points, 17 columns |
| `data/processed/industry.gpkg` | 0.4 MB | 820 polygons — osm_id, name, industry_type, region |
| `data/processed/landuse.gpkg` | 19 MB | 21,170 polygons — osm_id, name, lc_class, region |
| `outputs/preview_*.png` | 1.2 MB | 3 verification maps |
| `data/raw/*.csv` | — | 219 FIRMS chunks (cache) |
| `data/raw/*.osm.pbf` | 758 MB | 3 zone files |

## Code

| File | Lines | Kaam |
|---|---|---|
| `src/config.py` | 70 | saari settings |
| `src/step1_download.py` | 246 | FIRMS download |
| `src/step2_context.py` | 328 | OSM polygons |
| `src/preview_map.py` | 68 | visual check |
| `src/check_region.py` | 156 | naya region add karne se pehle |

## Chalane ka tareeka

```bash
cd /home/vank/SIH
source venv/bin/activate

python src/step1_download.py     # 7 sec (cached) / 7 min (fresh)
python src/step2_context.py      # 2 min
python src/preview_map.py        # 3 sec
```

---

# Part I — 🔴 Ab tumhe ye karna hai

## I1. Screenshot sambhalo (2 min)

`outputs/preview_punjab.png` PPT ke slide 9 ke liye rakh lo.
`outputs/preview_jamnagar.png` slide 1 ke liye.

## I2. QGIS install karo (optional, ~10 min)

```bash
sudo apt install qgis qgis-plugin-grass
```

Phase 1 ke liye **zaroori nahi** — check preview PNGs se ho chuka hai.
Par Phase 2 ke baad clusters pe click karke "ye kaunsi factory hai" dekhna
QGIS mein bahut aasan hai.

## I3. Git init — ek decision (tumhara)

Repo abhi bana hi nahi hai. Day 6 ka "doosre laptop pe clone karke chalao"
iske bina possible nahi. `.gitignore` ready hai.

## I4. Phase 2 se pehle 20 min padhna — ye zaroori hai

Phase 2 ka **pura** code teen cheezon se bana hai:

**1. `sjoin_nearest`** — har hotspot ke liye sabse nazdeeki factory dhoondhta
hai aur doori bhar deta hai. Tumhara sabse important feature yahi banata hai

**2. `sjoin` with `predicate="within"`** — point kis polygon ke **andar** hai.
Isse `lc_class` (forest/cropland/urban) aata hai
https://geopandas.org/en/stable/docs/user_guide/mergingdata.html

**3. DBSCAN ke do parameters** — bas itna:
- `eps=500` → 500 metre ke andar ke points ek hi source maane jayenge
- `min_samples=3` → kam se kam 3 points ho to hi cluster banega

Ye isliye kaam karta hai kyunki refinery ka flare **hamesha wahi jagah** pe
jalta hai, jabki jungle ki aag ghoomti hai.

**Yaad rakhna:** ye saare operations `to_crs(32643)` ke **baad** hote hain.
4326 mein `eps=500` ka matlab "500 degree" hoga — bekaar.

---

# Part J — Naya region kaise add karein

Pipeline sirf in 3 jagah ke liye nahi hai — region ke naam kahin bhi hardcoded
nahi hain, sab kuch `config.REGIONS` pe loop karta hai.

**Pehle check chalao:**
```bash
python src/check_region.py 82.4 22.2 82.9 22.5    # west south east north
```

Batata hai: kaunsi zone file chahiye, `CRS_METRES` yahan kitna galat hai,
aur bbox ulta to nahi.

**Phir `config.py` mein do lines:**
```python
REGIONS["korba"]    = (82.4, 22.2, 82.9, 22.5)
REGION_PBF["korba"] = "central-zone-latest.osm.pbf"
```

Zone ki pbf download karke `data/raw/` mein rakho, phir step1 aur step2
dobara chalao. Baaki kuch nahi badalna.

## Limit 1 — CRS 32643 lagbhag 82°E tak

Ye UTM zone 43N hai, center 75°E pe. Jitna door jaoge, distance utni galat.
1 km ki asli galti (measure ki hui):

| Jagah | Galti |
|---|---|
| Punjab (75.8°E) | -0.03% |
| Mumbai (72.8°E) | +0.03% |
| Uttarakhand (79.5°E) | +0.19% |
| Jamnagar (69.9°E) | +0.30% |
| Chennai (80.3°E) | +0.37% |
| **Kolkata (88.4°E)** | **+2.35%** |
| **Assam (92.9°E)** | **+4.02%** |

North/West/Central India ke liye 0.4% se kam — ignore kar do.
Northeast ke liye `CRS_METRES = 32646` chahiye, warna 1000 m ka rule asal
mein 1040 m ka ban jayega.

## Limit 2 — OSM coverage har jagah barabar nahi

Punjab wala cropland gap (1.3%) yaad rakho. Isliye step2 har region ka polygon
count print karta hai aur zero pe **loud warning** deta hai — chup-chaap
fail nahi hota.

---

# Part K — Phase 2 ke liye ready

## Inputs maujood hain ✅

```
hotspots.gpkg   ✅  8,415 points
industry.gpkg   ✅    820 polygons
landuse.gpkg    ✅ 21,170 polygons
```

## Dono spatial joins test kar liye — chal rahe hain

```
sjoin_nearest(hotspots, industry)  -> 8,418 rows
sjoin(hotspots, landuse, within)   -> 8,417 rows
```

## ⚠️ Phase 2 pe ek gotcha (abhi pakda)

Dono joins input se **zyada rows** de rahe hain — 8,415 se 8,418 / 8,417.

**Wajah:** ek hotspot do overlapping polygons ke andar ho sakta hai (jaise
forest aur urban dono), aur `sjoin_nearest` mein distance tie ho sakti hai.
Aise mein join **do rows** bana deta hai.

**Agar dedup nahi kiya** to features file mein duplicate hotspots aa jayenge,
aur baad mein saare counts galat honge — aur ye chup-chaap hoga, koi error
nahi aayega.

**Phase 2A likhte waqt join ke baad ye lagana hai:**
```python
joined = joined[~joined.index.duplicated()]
```

## Phase 2 mein kya banega

```
step2_context.py part 2   -> features.gpkg    (har hotspot pe distance + landcover)
step3_persistence.py      -> sources.gpkg     (DBSCAN clusters + PERSISTENT/EPISODIC)
```

Aur wahin pe "Reliance Refinery — 198 detections — PERSISTENT" wali table
banegi, jo PPT mein jayegi.
