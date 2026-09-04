# Data Audit — kya adhoora tha aur kaise theek kiya

**Kab:** Phase 4 shuru karne se pehle
**Natija:** data galat nahi tha, par **adhoora** tha. Teen gap mile, teeno free mein bhare.

---

## Ek nazar mein

Do daur mein kaam hua — pehle data ke gap bhare, phir class imbalance ka.

| | shuruaat | gap bharne ke baad | naye regions ke baad | **abhi** |
|---|---|---|---|---|
| regions | 3 | 3 | 5 | **5** |
| detections | 8,415 | 20,340 | 83,152 | **88,434** |
| sources | 6,010 | 9,677 | 16,820 | **17,615** |
| PERSISTENT (factory) | 5 | 14 | 245 | **275** |
| anomalies | 1 | 18 | 956 | **999** |
| `lc_class` "unknown" | 82% | 0% | 0% | **0%** |
| **INDUSTRIAL labels** | **17** | 40 | 115 | **136** |
| training rows | 3,858 | 6,063 | 8,822 | **16,474** |
| **imbalance** | **177×** | 102× | 38× | **83×** |
| rules ka score | 76% | 79% | — | **76.2%** |

Aakhri column current data hai (`python verify.py` se milta-julta). Pehli
teen column purane daur hain — wo history hai, unhe mat badlo.

Training rows 8,822 se 16,474 kyun ho gaye: rules ke thresholds dheele
kiye gaye (detail `src/step4_labels.py` mein), isliye hazaaron sources
UNSURE se nikal kar training mein aa gaye. Isi wajah se imbalance 38x se
83x ho gaya — AGRI_BURN sabse zyada badha.

---

## Gap 1 🔴 — Hum 3 mein se sirf 1 satellite use kar rahe the

### Kya mila

FIRMS se poocha ki 2025 ke liye kya-kya available hai. Jawab: **teen alag
satellite** hain jo **bilkul ek jaisa VIIRS sensor** laad kar ghoom rahe hain —
Suomi-NPP, NOAA-20, NOAA-21. Hum sirf pehla use kar rahe the.

Test kiya (2 windows × 3 regions):

```
VIIRS_SNPP_SP      244 detections   <- sirf ye use ho raha tha
VIIRS_NOAA20_SP    264
VIIRS_NOAA21_NRT   240
                   ─────
teeno milakar      748  =  3.1x
```

### Kyun ye sirf "zyada data" se badi baat hai

Phase 2 mein ek problem mili thi — `activity_ratio` isliye kaam nahi kar
raha tha ki **satellite roz dekh hi nahi pata**. Reliance ka flare saal
bhar jalta hai par sirf 91 alag dinon pe dikha tha.

**Teen satellite = teen guna zyada chakkar.**

```
Reliance ka n_days:   91  ->  185
```

Ab wo lagbhag har doosre din dikh raha hai.

### MODIS kyun nahi liya

MODIS bhi available tha, par wo **1 kilometre** ka hai — bahut mota.
Usme chhoti aagein aur factory ka flare ghul-mil jate. VIIRS 375 metre
ka hai. Isliye sirf teeno VIIRS liye.

---

## Gap 2 🔴 — Zameen ka type 82% "unknown" tha

### Problem

`lc_class` OpenStreetMap se aa raha tha. Par OSM par log sadak aur
building to map karte hain, **khet aur jungle nahi**.

Aur ye sirf shak nahi tha — **tumhare 50 gold labels ne isse saabit kiya**:
rules ki sabse badi galti (4 mein se 4) bilkul isi wajah se hui thi.
OSM par wo jungle mapped hi nahi tha, isliye *"jungle pe nahi hai"* wali
shart pass ho gayi aur khet wala rule chal pada.

### Solution — ESA WorldCover

Ek satellite se bani hui tasveer, jisme poori duniya ki **har 10×10 metre**
ki jagah pe likha hai wahan kya hai. Kisi insaan ne nahi banaya — satellite
ne dekha aur likh diya. Isliye usme "unknown" hota hi nahi.

**Free hai, bina login ke.** Chaar tiles chahiye thi (~390 MB):

```
N21E069  (Jamnagar)      N30E075  (Punjab)
N27E078  (Uttarakhand)   N30E078  (Uttarakhand ka upar ka hissa)
```

### Natija

```
'unknown':  82%  ->  0%

cropland     27  ->  11,212
forest    4,357  ->   6,084
urban        86  ->   1,016
```

Aur ab har region ka sach dikh raha hai:

| region | pehle | ab |
|---|---|---|
| **Punjab** | 99% unknown | **cropland 94%** |
| **Uttarakhand** | 43% unknown | **forest 74%** |
| Jamnagar | 99% unknown | cropland 50%, urban 30% |

> Ye Phase 1 wali limitation ab **theek ho gayi**. Par slide 9 pe usse
> hatana mat — ulta wo ab aur achhi kahani hai: *"humne problem pakdi,
> naapi (1.3% coverage), aur ek behtar data source se theek ki."*

---

## Gap 3 🟠 — OSM ki aadhi file (jaan-boojh kar chhoda)

Hum sirf `multipolygons` layer padh rahe the. Check kiya, akele Jamnagar mein:

| layer | industry-jaisi cheezein | padh rahe? |
|---|---|---|
| multipolygons | 327 | ✅ |
| lines | 298 | ❌ |
| points | 17 | ❌ |

Aur `Sikka Thermal Power Station`, `Essar Power Limited` jaise **asli naam**
chhoot rahe hain.

**Phir bhi nahi jodi.** Wajah: un 298 "lines" mein zyadatar pipelines aur
deewarein hain. 2-3 naam ke liye itna shor badhana theek nahi.

*Ye ek jaan-boojh kar liya faisla hai, bhool nahi. Agar judge poochhe to
yahi jawab hai.*

---

## 🔴 Ek cheez toot gayi thi — aur uska sabak

### Kya hua

Naya data aane ke baad **50 gold labels galat jagah point karne lage**.
50 mein se 47 ab bilkul alag jagah pe the — **median 60 kilometre door**.

### Wajah

`source_id` sirf ek **ginti** thi:

```
jamnagar_c0   = "Jamnagar ka pehla cluster"
jamnagar_n335 = "Jamnagar ka 335va akela point"
```

Data badla → clusters naye sire se bane → poori ginti hil gayi.
**Naam bacha raha, par uska matlab badal gaya.**

### Do fix

**1. Naam ab JAGAH se banta hai:**
```
purana:  jamnagar_n335
naya  :  jamnagar_21.8032_69.8659
```
Ye data badalne pe bhi wahi rehta hai, kyunki jagah wahi rehti hai.
Aur padhne mein bhi matlab rakhta hai.

**2. `gold_labels.csv` mein ab lat/lon bhi save hota hai.**
`rescue_gold_labels.py` har purani jagah ka sabse nazdeek naya source
dhoondh kar label chipka deta hai.

### Bacha kitna

```
47 / 50 labels bach gaye     (median fasla sirf 46 metre = wahi jagah)
 3 nahi bach paye            (naye data mein wahan koi source bana hi nahi)
```

Balance ab bhi theek hai: **18 AGRI / 17 FOREST / 12 INDUSTRIAL**.

### Sabak

> **ID kabhi ginti se mat banao. Jo cheez badal sakti hai, usse naam mat
> banao.** Naam kisi aisi cheez se bane jo cheez ke saath hi judi ho —
> yahan wo uski jagah thi.

Aur: **gold labels sirf ID se mat jodo, jagah se jodo.** Ab agar kabhi
naya region ya naya saal add karoge, ye kaam dobara nahi karna padega.

---

## Ab data ka haal

### Rules ka score behtar hua

| | pehle | ab |
|---|---|---|
| coverage (rules ne jawab diya) | 33/50 | 29/47 |
| **accuracy (jawab sahi tha)** | **76%** | **79%** |
| `lc_class = unknown` in gold set | 41/50 | **0/47** |

Aur wo sabse badi galti — "AGRI kaha, asal mein FOREST tha" — **4 se
ghatkar 2** reh gayi.

### Naye PERSISTENT sources

14 mile (pehle 5). Naye naam bhi mile — **Sohal Steel Works** (Punjab).

```
Reliance Refinery      292 detections, 185 din, night 1.00
Reliance Refinery      207 detections, 150 din, night 0.96
SHREE DIGVIJAY CEMENT  173 detections, 108 din, night 1.00
Vadinar Refinery       110 detections,  73 din, night 0.90
```

### 18 anomalies (pehle 1)

Sabse badi: **Vadinar Refinery, 21 April 2025** — normal se **16 guna**
zyada garmi (26.2 MW vs normal 1.64 MW).

### Ab bhi ek problem baaki hai

```
AGRI_BURN    4,073
FOREST_FIRE  1,950
INDUSTRIAL      40   <- ab bhi kam
```

Imbalance 177× se ghatkar **102×** hua, par ab bhi bahut hai. Phase 4 mein
class weights aur macro-F1 se sambhalna padega.

---

## Verification — sab pass

```
detections                                20,340
CONSERVATION: sources ke n_detections ka total = 20,340  (ek bhi na kho, na dohra)
har source_id unique
source_id apni hi jagah batata hai        (300 sample, 0 galat)
lc_class mein 'unknown' zero
geometry sab valid
saare gold source_id maujood
```

---

## Chalane ka naya order

```bash
python src/step1_download.py       # 3 satellites  (~20 min pehli baar)
python src/step2_context.py        # OSM polygons + context
python src/step2c_landcover.py     # ESA WorldCover  <- NAYA
python src/step3_persistence.py    # clustering
python src/step4_labels.py         # rules se labels
python src/rescue_gold_labels.py   # gold labels dobara jodo  <- NAYA
```

**`step2c_landcover.py` ko `step2_context.py` ke BAAD hi chalana** — warna
`features.gpkg` naye sire se banti hai aur landcover mit jata hai.


---

# Daur 2 — Class imbalance

## Problem

```
AGRI_BURN    4,073
FOREST_FIRE  1,950
INDUSTRIAL      40   <- 102 guna kam
```

Itne imbalance pe model INDUSTRIAL theek se seekh hi nahi paata. Aur
INDUSTRIAL hi to project ka asli target hai.

## Wajah — teen, aur pehli sabse badi hai

**1. Ginne ka tarika**

```
sources ginne pe    : 102x imbalance
detections ginne pe :   5x imbalance
```

Ek kisan ek baar aag lagata hai = 1 detection = **1 source**.
Ek refinery 292 baar dikhti hai = 292 detections = **1 source**.

86% AGRI sources sirf ek detection ke hain; INDUSTRIAL ka **ek bhi nahi**
(unka median 6 hai). To imbalance kaafi had tak **ginne ka natija** hai,
asliyat ka nahi.

**2. Region ka chunav** — 3 mein se sirf **ek** industrial region tha.

**3. Asliyat** — India mein refineries se kahin zyada khet ki aagein
lagti hain. Ye poori tarah "problem" nahi hai.

---

## Dataset dhoondha — WRI Global Power Plant Database

Free, bina login. **1,589 India plants** coordinates + fuel type +
capacity ke saath. Inme **388 thermal**.

### Fuel type sabse kaam ki cheez hai

Solar aur wind plants **bilkul garmi nahi dete** — satellite unhe kabhi
nahi dekhega. Coal, gas, oil, biomass dete hain.

OSM sirf `power=plant` likhta hai — ye nahi batata ki solar hai ya coal.
Agar hum solar farm ko bhi "industry" maan lete, to uske paas wali khet
ki aag galti se INDUSTRIAL ban jaati.

```
Coal      253 plants  (183,000 MW)
Gas        68
Biomass    50
Oil        17
```

### Ek aur cheez — point ko ghera banana

Database mein sirf **ek point** hota hai (plant ka beech). Par 4,000 MW
ka plant zameen pe 2-3 km faila hota hai! Uske kone pe hui detection ka
distance "0" nahi aayega agar sirf point rakhein.

Isliye capacity ke hisaab se ghera banaya:
`radius = 300 + 15 × √(capacity_mw)` — 100 MW pe 450 m, 4,600 MW pe 1,320 m.

---

## Naye regions — guess nahi, data se chune

WRI database se nikala ki India ke sabse bade thermal cluster kahan hain
(70 km ke andar wale plants ek saath ginke):

| # | jagah | plants | capacity |
|---|---|---|---|
| **1** | **Korba/Sipat, Chhattisgarh** | 28 | **24,056 MW** |
| **2** | **Singrauli, MP** | 9 | **21,164 MW** |
| 3 | Chandrapur, Maharashtra | 33 | 16,903 MW |
| 5 | *Jamnagar (hamara)* | 5 | 10,476 MW |

Korba akela Jamnagar se **2.3 guna** bada hai.

Dono **central-zone** pbf mein aate hain — jo pehle se download tha.
Sirf FIRMS data aur 2 WorldCover tiles chahiye thi.

---

## ⭐ Natija

```
INDUSTRIAL     40  ->  115
imbalance    102x  ->   38x
PERSISTENT     14  ->  245
```

Aur naye PERSISTENT sources mein **asli, bade naam**:

| region | naam | detections | alag din | raat ka % |
|---|---|---|---|---|
| korba | **Jindal Steel Works** | 3,968 | 288 | 79% |
| korba | **Dipka Open Cast Mine** | 2,567 | 247 | 96% |
| singrauli | **Block-B coal mine** | 2,148 | 272 | 78% |
| korba | **Gevra Open Cast Mine** | 1,775 | 255 | 85% |
| korba | **Prakash Industries Steel Plant** | 1,529 | 265 | 94% |
| singrauli | **Nigahi Mine** | 1,143 | 164 | 84% |
| korba | **RAIGARH TPP** | 1,058 | 248 | 96% |

**Gevra** India ki sabse badi coal mine hai. **Jindal Steel Works** aur
**Prakash Industries** asli steel plants hain. **Nigahi / Jayant /
Dudhichua** NCL ki bade coal mines hain.

99/245 PERSISTENT sources ke paas asli naam hai.

Sabse badi anomaly: **Block-B coal mine, 30 May 2025** — normal se
**64 guna** zyada garmi.

---

## Jo abhi bhi problem hain (imaandari se)

**1. Gold labels sirf purane 3 regions ke hain.**
45 gold labels Jamnagar/Punjab/Uttarakhand se hain. Korba aur Singrauli
ka ek bhi nahi. Yani evaluation un naye regions ko cover nahi karta.

*Ye actually ek MAUKA bhi hai:* Phase 4 mein model ko purane regions pe
train karke naye pe test kar sakte ho — "kabhi na dekhe hue region" wala
imtihaan. Wo bahut strong slide hai.

**2. Imbalance ab bhi 38x hai.** Behtar hai (177x se), par class weights
aur macro-F1 ab bhi zaroori hain.

**3. 956 anomalies bahut zyada hain** dashboard pe dikhane ke liye.
Phase 5 mein threshold ya top-N filter lagana padega.

**4. Korba/Singrauli mein coal MINES zyada hain, refineries nahi.**
Open cast mine ka thermal pattern refinery se alag hota hai. Ye achhi
baat hai (variety badhi), par model ko "industrial" ke do alag roop
seekhne padenge.
