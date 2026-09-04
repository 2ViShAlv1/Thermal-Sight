# Phase 3 — Har source ko naam dena (labelling)

**Status: ✅ COMPLETE** | 20/20 checks pass | **50 gold labels ho gaye** ✅
**Baaki hai:** sirf AI wala step (API key chahiye — Part 7)

---

## 1. Ek kahani se shuru

Socho tumhare paas 6,010 photos hain — sab mein ek chamakta hua dhabba.
Tumhe har photo pe likhna hai ki wo dhabba kya hai: **factory**, **jungle
ki aag**, ya **khet ki aag**.

Ek-ek karke likhne baitho to 6,010 minute = **100 ghante** lag jayenge.

To hum teen tarike milakar kaam karte hain:

| Tarika | Kitne sources | Kaun karta hai |
|---|---|---|
| **1. Rules** — seedhi shartein | 3,858 (64%) | code, 1 second mein |
| **2. AI** — satellite photo dekhkar | 100 | Claude |
| **3. Insaan** — tum khud | 50 | **tum, ~1 ghanta** |

Pehla tarika **sasta aur tez** hai par kachcha. Doosra **mehenga par smart**.
Teesra **sabse mehenga par sabse sacha**.

---

## 2. ⭐ Result — rules chal gaye

```
6,010 sources
  INDUSTRIAL      17   ( 0.3%)
  FOREST_FIRE    824   (13.7%)
  AGRI_BURN    3,017   (50.2%)
  ─────────────────────────────
  UNSURE       2,152   (35.8%)   <- inpe koi rule fit nahi baitha
```

Region ke hisaab se:

| | AGRI_BURN | FOREST_FIRE | INDUSTRIAL | UNSURE |
|---|---|---|---|---|
| **Jamnagar** | 140 | 0 | **10** | 321 |
| **Punjab** | **2,593** | 3 | 6 | 1,174 |
| **Uttarakhand** | 284 | **821** | 1 | 657 |

Dekho — har region mein wahi label sabse zyada hai jo hona chahiye tha.
Punjab mein khet, Uttarakhand mein jungle, Jamnagar mein factory.
**Rules kaam kar rahe hain.**

---

## 3. Teen rules — poora "gyaan" bas itna hai

### INDUSTRIAL — factory ka flare

```
factory se 1 km ke andar  AND  ek baar ki ghatna nahi hai
```

**Doosri shart kyun:** factory ke bagal mein bhi koi ek baar aag laga
sakta hai (kachra jalana waghairah). Wo factory ka flare nahi hai.

### FOREST_FIRE — jungle ki aag

```
jungle wale ilaake pe hai  AND  factory se 5 km door  AND  ek baar ki ghatna hai
```

### AGRI_BURN — khet ki aag

Ye rule **plan se alag hai**, aur wajah pakki hai. Neeche Part 4 mein.

---

## 4. 🔴 Plan ka rule chal hi nahi sakta tha — humne badla

**Ye finale ka achha jawab hai.**

### Plan kya kehta hai

```
AGRI_BURN = lc_class == "cropland" AND ...
```

Yani source kisi **"khet" wale polygon pe** hona chahiye.

### Wo kaam kyun nahi karta

Phase 1 mein hi pata chal gaya tha:

> Punjab ke **5,113 detections** mein se sirf **PAANCH** kisi khet wale
> polygon pe hain. Kyunki OpenStreetMap pe Punjab ke khet mapped hi
> nahi hain — poore ilaake ka sirf **1.3%**.

Log OSM pe sadak aur building to map karte hain, khet nahi.

Agar hum plan ka rule lagate, to **Punjab ka 61% data UNSURE reh jata** —
aur AGRI_BURN class practically khaali hoti.

### Humne kya kiya

"Khet pe hai" ki jagah **paanch shartein** lagayin, jo milkar wahi kaam
karti hain:

```
1. jungle pe NAHI hai              (warna forest fire hoti)
2. factory se 3 km door hai
3. ek baar ki ghatna hai
4. katai ke mahine mein hui        (Apr/May = gehun, Oct/Nov = dhaan)
5. DIN mein hui                    (night_ratio < 0.3)
```

**Chauthi aur paanchvi shart Phase 2 ke findings se aayi hain:**
- Punjab ke **93%** detections inhi 4 mahinon mein hain
- Punjab ke **97%** detections din ke hain (kisan din mein jalata hai),
  jabki factory ke flare ka night_ratio **1.00** tha

> **Judge se kya kehna:** *"Plan mein cropland polygon wala rule tha.
> Maine data check kiya to pata chala OSM pe Punjab ke khet mapped hi
> nahi hain — sirf 1.3% coverage. To maine us ek shart ki jagah paanch
> aisi shartein lagayin jo satellite data se hi nikalti hain, kisi
> bahar ke naksha pe depend nahi karti."*

---

## 5. "Pata nahi" kehna — ek soch samajh kar liya faisla

2,152 sources (36%) **UNSURE** hain. Ye **failure nahi hai**, design hai.

Agar kisi source pe:
- **koi rule fit nahi baitha** → UNSURE
- **do rules ek saath fit baithe** (jaise jungle ke paas bhi hai aur
  factory ke paas bhi) → UNSURE

Hum zabardasti ek label nahi thopte.

**Kyun:** galat label model ko galat cheez sikha dega. **"Pata nahi"
kehna galat jawab dene se behtar hai.** Aur inhi UNSURE cases pe AI aur
insaan ki nazar padegi — wahin se asli seekh milegi.

### `needs_review` — kispe dobara dekhna hai

**2,156 sources** pe review chahiye:
1. jo UNSURE hain
2. jo **"confusing zone"** mein hain — factory se **500 se 3000 metre**
   door. Ye khatarnak doori hai: itni paas ki shayad factory ka hissa
   ho, itni door ki shayad bilkul alag cheez. Rules yahan sabse zyada
   galti karte hain.

---

## 6. Anomaly — "aaj kuch alag hua"

Anomaly ek **alag cheez** hai, class nahi.

**Idea:** agar koi factory roz 5 MW garmi deti hai, aur ek din achanak
20 MW de de — to **us din kuch hua tha**.

Har PERSISTENT source ke liye dekha ki kis din ki garmi uske **apne
normal se 3 guna** se zyada thi.

*"Apne normal se"* — ye zaroori hai. Har factory ka apna normal alag
hota hai; badi refinery ka 8 MW normal ho sakta hai, chhoti ka 2 MW.

### Result

| source | date | us din FRP | normal FRP | kitna guna |
|---|---|---|---|---|
| **Reliance Refinery** | 2025-11-09 | 6.95 | 1.63 | **4.26×** |

Ek anomaly mili. **9 November 2025 ko Reliance ke flare ne apne normal
se 4 guna zyada garmi di.**

*Sirf ek kyun mili:* abhi sirf 5 PERSISTENT sources hain, aur unki garmi
kaafi steady hai. Ye achhi baat hai — matlab threshold shor nahi utha
raha. Dashboard mein ye tab dikhega.

---

## 7. AI wala step (code ready hai, chalna baaki)

`src/step4b_vlm.py` — confusing sources ki **satellite photo** nikaal kar
Claude se poochta hai *"is photo mein kya dikh raha hai?"*

**Kyun kaam karta hai:** rules sirf **numbers** dekhte hain (doori,
mahina, raat/din). Photo mein **aankhon se** dikh jata hai ki wahan
factory hai, jungle hai, ya khet. Jahan OSM ka data adhoora hai (jaise
Punjab ke khet), wahan **photo hi sach bata sakti hai**.

### 🔴 Ek bug jo banate waqt pakda — photo galat jagah ki aa rahi thi

Naksha chhote chaukor tukdon (tiles) mein bata hua hai. Lat/long se tile
ka number nikalte waqt dashamlav kat jata hai — `22743.99` ban jata hai
`22743`.

Iska matlab hamari jagah us tile ke **kone** pe bhi ho sakti thi.
Zoom 15 pe ek tile **~1.2 km** ka hota hai, to source photo ke beech se
**1 km tak hat** sakta tha.

Aur hum Claude se keh rahe the *"photo ke BEECH wale hisse ko dekho"* —
wo galat jagah dekhta!

Test karke dekha: Reliance ka offset **(0.72, 0.99)** nikla — yani
bilkul kone pe.

**Fix:** 3×3 = 9 tiles download karke jodte hain, phir source ke theek
upar se 512×512 ka chaukor kaat lete hain. Ab source **pakka beech mein**
hai. Test karke confirm kiya — Reliance ki photo mein storage tanks aur
process units bilkul beech mein aaye.

### Do aur cheezein jo theek ki

**Structured output** — Claude se JSON maangne ki jagah **schema** diya
hai. Isse jawab **hamesha** valid JSON aata hai. Warna kabhi-kabhi model
` ```json ` laga deta hai aur code crash ho jata.

**Model** — plan mein `claude-sonnet-4-6` likha tha, wo purana ho chuka
hai. Ab `claude-opus-5` use kar rahe hain (`config.py` mein badal sakte ho).

### 🔴 Chalane ke liye API key chahiye

```bash
# .env mein ye line add karo:
ANTHROPIC_API_KEY=sk-ant-...
```
Key yahan se: https://console.anthropic.com/settings/keys

Phir:
```bash
python src/step4b_vlm.py --limit 20    # pehle 20 pe test karo
python src/step4b_vlm.py               # phir poore 100
```

---

## 8. 🔴 Ab tumhe ye 2 kaam karne hain

### Kaam 1 — API key daalo (2 minute)

Upar Part 7 mein likha hai. Bina iske AI wala step nahi chalega.
Pehle `--limit 20` se test karna, phir poora.

### Kaam 2 — 50 sources khud label karo ✅ **HO GAYA**

Result Part 12 mein hai. Neeche wala hissa reference ke liye hai.

---

### (ho chuka) 50 sources khud label karna ⭐

```bash
streamlit run src/gold_ui.py
```

Ek app khulegi. Har source pe dikhega:
- **satellite photo** (source beech mein)
- **FRP ka chart** — waqt ke saath garmi kaise badli
- **saare numbers** — kitni baar dikha, kitne din, raat ka %, factory se doori
- **Google Maps ka link** — shak ho to wahan zoom karke dekh lo
- **4 buttons:** INDUSTRIAL / FOREST_FIRE / AGRI_BURN / UNCLEAR
- **notes box**

Ek source pe **~1 minute**. Progress save hota rehta hai — beech mein
chhod ke wapas aa sakte ho. Chai leke baithna.

#### Ye skip mat karna — wajah samjho

Baaki 3,858 labels **rules** ne banaye hain. Agar model ko unhi pe test
karoge, to tum sirf ye check kar rahe ho ki **"model ne mere rules ratt
liye ya nahi"**. Wo accuracy **jhoothi** hai — 95% aayegi aur uska koi
matlab nahi hoga.

Ye 50 labels **insaan** ne banaye hain. Model ne inhe kabhi nahi dekha.
**Isi liye inpe mila score hi saccha score hai.**

Aur ek faayda: label karte waqt tumhe **3-4 aisi galtiyan khud dikhengi**
jo koi rule nahi pakad sakta — jaise koi factory OSM pe hai hi nahi, ya
koi jagah dono jaisi lagti hai. **Wahi tumhari sabse achhi slide banegi.**

*(App ke andar hi ek "Kaise decide karun?" section hai — confuse ho to
wo khol lena.)*

#### 50 sources kaise chune

Random 50 uthate to zyadatar Punjab ke AGRI_BURN aa jate (wahi sabse
zyada hain) aur INDUSTRIAL ek bhi nahi. Test set bekaar ho jata.

Isliye har (region × label) ke jode se **barabar** uthaye hain:

| | AGRI_BURN | FOREST_FIRE | INDUSTRIAL | UNSURE |
|---|---|---|---|---|
| Jamnagar | 4 | 0 | 4 | 5 |
| Punjab | 7 | 3 | 4 | 6 |
| Uttarakhand | 4 | 6 | 1 | 6 |

Har tarah ka source test mein aa gaya. (Isse **stratified sampling**
kehte hain — finale mein ye shabd kaam aayega.)

---

## 9. Verification — 20/20 pass

Sirf "error nahi aaya" kaafi nahi. Har rule ko **ulta** check kiya:

```
6,010 rows      - sources se ek bhi kam/zyada nahi
har source pe label hai, koi khaali nahi

har INDUSTRIAL  : sach mein <1km AND non-episodic hai
har FOREST_FIRE : sach mein forest AND >5km AND episodic hai
har AGRI_BURN   : sach mein paanchon shart poori karta hai

UNSURE bilkul wahi hain jinpe theek ek rule nahi laga
needs_review = UNSURE ya confusing-zone

har anomaly ka ratio > 3, aur sirf PERSISTENT sources se
```

**Aur code bhi test kiya:**
- tile math — `(0,0)` se `16384,16384` (naksha ka bilkul beech) ✓
- chip download — Reliance ki asli photo, 512×512, beech mein ✓
- gold UI — Streamlit ke apne test framework se chalayi, button dabaya,
  CSV likhi ✓
- 50 sources ka chunav deterministic hai (app dobara kholo, wahi 50) ✓

---

## 10. Files aur chalane ka tareeka

```bash
source venv/bin/activate

python src/step4_labels.py       # rules      (1 second)
python src/step4b_vlm.py         # AI         (API key chahiye)
streamlit run src/gold_ui.py     # tum        (~1 ghanta)
```

| File | Kya hai |
|---|---|
| `data/processed/sources_labelled.gpkg` | 6,010 sources + label |
| `data/processed/anomalies.csv` | 1 anomaly |
| `data/processed/gold_labels.csv` | *(tumhare 50 labels — abhi banegi)* |
| `data/chips/*.jpg` | satellite photos |

**Naye columns** `sources_labelled.gpkg` mein:

| Column | Matlab |
|---|---|
| `rule_label` | rules ne kya kaha (kabhi nahi badalta) |
| `label` | **final label** — AI ya insaan ise badal sakte hain |
| `label_source` | ye label kahan se aaya: `rule` / `vlm` / `none` |
| `needs_review` | ispe dobara dekhna hai? |
| `vlm_landuse` | AI ne photo mein kya dekha *(VLM chalne ke baad)* |

`rule_label` alag rakhne ka faayda: baad mein compare kar sakte ho ki
**AI ne rules ki kitni galtiyan sudhari** — wo bhi ek slide hai.

---

## 11. Phase 4 ke liye

Model train hoga. Do baatein yaad rakhni hain:

**1. `lon`/`lat` ko feature mat banana.** Warna model *"Jamnagar =
factory"* ratta maar lega aur naye shehar mein fail ho jayega.

**2. Teen alag score nikalna honge:**
- normal cross-validation
- GroupKFold (ek hi source train aur test dono mein na aaye)
- **50 gold labels pe** ← ye sabse kam aayega

**Score girna galat nahi hai — wahi imaandari hai.** Slide 5 yahi
banegi, aur wahi tumhe baaki teams se alag karegi.

Expected: gold-set pe **0.75–0.85**. Agar 0.97 aaya to kahin galti hai
(shayad lat/long feature mein reh gaya).

**3. Ab ek baseline bhi hai.** Rules ka gold set pe apna score **76%**
hai (Part 12). Model ko usse behtar karna chahiye — warna saabit ho
jayega ki model ne rules ko sirf ratta maara hai, unse zyada kuch nahi
seekha.


---

## 12. ⭐ Gold labels ka result — aur yahi sabse keemti cheez nikli

50 sources haath se label ho gaye:

```
AGRI_BURN     18
FOREST_FIRE   18
INDUSTRIAL    14
```

Achha balance — teeno class kaafi hain, aur ek bhi UNCLEAR nahi.

### Rules ka asli score — do alag numbers

Ek hi number se baat nahi banti, kyunki rules kabhi-kabhi *"pata nahi"*
bhi kehte hain. To do numbers chahiye:

| | |
|---|---|
| **Coverage** — rules ne kitno pe jawab diya | **33/50 = 66%** |
| **Accuracy** — jawab diya to kitna sahi | **25/33 = 76%** |
| rules ne "pata nahi" kaha | 17/50 |

**"Pata nahi" kehna galti nahi hai — wo design tha.** Isi liye AI aur
insaan wala step banaya gaya.

> **Ye do numbers alag batana zaroori hai.** Agar tum sirf "50 mein se 25
> sahi = 50%" kehte, to wo bhram paida karta — jaise rules aadhe waqt
> galat hain. Asal mein wo aadhe waqt **chup** rehte hain, aur jab bolte
> hain to 76% sahi bolte hain.

### 🔴 Galtiyon ka pattern — aur wo ek hi wajah se hain

| rules ne kaha | asal mein tha | kitni baar |
|---|---|---|
| AGRI_BURN | **FOREST_FIRE** | **4** |
| AGRI_BURN | INDUSTRIAL | 2 |
| FOREST_FIRE | AGRI_BURN | 1 |
| INDUSTRIAL | FOREST_FIRE | 1 |

Sabse badi galti (4 baar) ko khod kar dekha:

> **Charon** ka `lc_class` **"unknown"** tha.

Yani OSM pe wo jungle **mapped hi nahi tha**. Isliye AGRI rule ki pehli
shart — *"jungle pe NAHI hai"* — pass ho gayi, aur rule chal pada.
Jabki photo mein saaf jungle dikh raha tha.

**Ye wahi OSM gap hai jo Phase 1 mein Punjab ke khet pe mila tha — par
ab wo doosri taraf se kaat raha hai.** In 50 sources mein:

```
lc_class = unknown   41   (82%)
lc_class = forest     9   (18%)
```

**82% sources ki zameen ka type OSM ko pata hi nahi hai.**

> Slide 9 (Limitations) ke liye ye ab bahut mazboot ho gaya. Pehle ye
> ek shak tha; ab **insaan ke labels se saabit** ho chuka hai ki OSM ka
> adhoora hona rules ki sabse badi galti ki wajah hai.

### Aur jo tumne rules se behtar pakda

**4 sources** aise the jinpe rules ne haath khade kar diye, par tumne
INDUSTRIAL pehchan liya. Sabse dilchasp:

| source | raat ka % | factory se doori | kitni baar dikha |
|---|---|---|---|
| `jamnagar_n32` | **100%** | **57 m** | 1 |

Ye source factory ki chaardiwari se **57 metre** door hai aur **raat ko**
dikha — koi bhi keh dega ki industrial hai. Par rule ne mana kar diya,
kyunki wo sirf **ek baar** dikha tha aur INDUSTRIAL rule maangta hai ki
"ek baar ki ghatna na ho".

**Ye rule ka ek asli chhed hai** — aur wo insaan ne pakda, code ne nahi.

### 🔴 Par ab in galtiyon ko dekh kar rules mat sudharna

Ye jaal bahut aasan hai, isliye samajh lo:

Ab jab tumhe pata chal gaya hai ki rules kahan galat hain, to mann karega
ki rules theek kar do. **Aisa karte hi ye 50 labels bekaar ho jayenge.**

Kyunki phir rules **inhi 50 ko dekh kar** banaye gaye honge — aur inhi pe
test karoge to 100% aa jayega. Wo number jhootha hoga. Ye wahi galti hai
jisse bachne ke liye ye 50 labels banaye the.

**Ye 50 label sirf JAANCHNE ke liye hain, banane ke liye nahi.**

*(Agar rules sudharne hi hain, to un 5,960 sources ko dekh kar sudharo jo
in 50 mein nahi hain.)*

### Aage kaise use honge

```
Phase 4 mein model TRAIN hoga  -> rules ke 3,858 labels pe
Phase 4 mein model TEST hoga   -> in 50 gold labels pe
```

Aur ab tumhare paas **rules ka apna score (76%)** bhi hai. Agar model
uss se behtar karta hai, to saabit ho jayega ki **model ne rules se
zyada seekha hai, sirf unhe ratta nahi maara.**

Ye ek slide hai jo shayad hi koi doosri team dikha paye.
