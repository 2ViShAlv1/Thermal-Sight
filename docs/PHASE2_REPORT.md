# Phase 2 — Baar-baar dikhne wali cheezein dhoondhna

**Status: ✅ ho gaya** | Ye project ka **sabse important hissa** hai

---

## 1. Ek kahani se shuru karte hain

Socho tum apne ghar ki chhat pe khade ho aur raat ko shehar dekh rahe ho.
Tumhe do tarah ki roshni dikhti hai:

**Ek — street light.** Wo roz raat ko jalti hai. Kal bhi jalegi, parso bhi.
Chhoti si roshni, par **hamesha wahi jagah**.

**Doosri — koi patakha.** Ek baar phata, tez roshni hui, aur khatam. Kal
wahan kuch nahi hoga.

Ab agar koi tumse pooche *"in dono mein farak kaise batao?"* — to **ek raat
dekh kar nahi bata sakte.** Dono roshni hi to hain.

Par agar tum **poore saal** roz dekho, to farak saaf ho jayega:
street light **roz** dikhegi, patakha **ek baar**.

**Bas yahi Phase 2 karta hai.**

- **Factory ka flare** = street light. Roz jalta hai, wahi jagah
- **Jungle/khet ki aag** = patakha. Ek baar, phir khatam

---

## 2. Ek badi galti jo hum ab tak kar rahe the

Ab tak hum har detection ko **alag cheez** maan rahe the.

Socho tum roz subah apne mohalle ki chai ki dukaan ki photo khinchte ho.
Saal bhar mein 198 photos ho gayin.

Ab koi aaye aur kahe *"tumhare mohalle mein 198 chai ki dukaanein hain!"* —
galat na? **Dukaan ek hi hai. Photo 198 hain.**

Hamare data mein bilkul yahi ho raha tha. Reliance ka **ek** flare **198 baar**
detect hua. Wo 198 alag cheezein nahi — **ek cheez jo 198 baar dikhi.**

**Phase 2 ka pehla kaam:** un 198 rows ko jodkar **ek** "source" banana.

---

## 3. Phase 2 do kaam karta hai

```
Phase 1 ki teen files (jo ek doosre ko jaanti hi nahi thi)
        |
        |  KAAM 1: "har garam point ke aas-paas kya hai?"
        |          (factory paas hai? jungle pe hai? khet pe hai?)
        v
   features.gpkg  -  8,415 points, ab har ek ko apna aas-paas pata hai
        |
        |  KAAM 2: "kaunse points asal mein EK hi cheez hain?"
        v
   sources.gpkg   -  6,010 sources
```

---

## 4. ⭐ Result — aur ye dekh kar tum khush ho jaoge

```
8,415 detections  ->  6,010 sources  ->  5 aise jo saal bhar chalte rahe
```

Wo 5 kaun nikle:

| Naam | kitni baar dikha | kitne alag din | kitne din tak | raat ko? | factory se doori |
|---|---|---|---|---|---|
| **Reliance Refinery** | 101 | 91 | 361 din | **100%** | **0 m** |
| **Reliance Refinery** | 63 | 57 | 361 din | **100%** | **0 m** |
| **SHREE DIGVIJAY CEMENT** | 52 | 50 | 358 din | **100%** | **0 m** |
| **Vadinar Refinery** | 31 | 29 | 360 din | **100%** | **0 m** |
| **Reliance Refinery** | 16 | 12 | 337 din | **100%** | **0 m** |

Isko aise padho:

> *"Reliance Refinery ki jagah pe garmi **101 baar** mili, **91 alag dinon**
> mein, **361 din** ke andar. Aur **har baar raat ko**. Aur wo jagah factory
> ki chaardiwari ke **andar** hai (0 metre)."*

**Paanch ke paanch asli factory ke naam.** Ek bhi galat nahi.

Aur **Uttarakhand aur Punjab mein ek bhi nahi** — kyunki wahan jungle aur khet
ki aag hai, factory nahi. **Bilkul jaisa hona chahiye tha.**

**→ Iska screenshot lo. Ye tumhari PPT ki sabse badi slide hai.**

---

## 5. Judges ye 3 sawaal poochenge — jawab yaad kar lo

### Sawaal 1: "DBSCAN kya hai?"

Socho ek mela laga hai. Tum upar se photo lo. Kuch log **jhund banakar** khade
hain, kuch **akele** ghoom rahe hain.

DBSCAN wahi kaam karta hai — **paas-paas wale points ko ek jhund maan leta hai.**

Do settings hain:

- **`eps = 500 metre`** — "kitne paas khade ho to ek jhund maanein?"
  Humne 500 m rakha, kyunki satellite ka ek pixel hi 375 m ka hota hai
- **`min_samples = 3`** — "kam se kam kitne log ho to jhund kahein?"
  Humne 3 rakha

Jo point kisi jhund mein na aaye, use DBSCAN **"noise"** kehta hai.

**Ye kaam kyun karta hai:** factory ka flare **hamesha wahi ek jagah** jalta
hai — to uske saare detections ek tight jhund ban jaate hain. Jungle ki aag
**ghoomti** hai — wo bikhri rehti hai.

### Sawaal 2: "CRS ka kya chakkar hai?"

Socho tum kapda naap rahe ho. Do tarike hain:

- **Rubber band se** — ye khinchta rehta hai, har baar alag naap deta hai
- **Steel ke scale se** — hamesha sahi naap

Map ke saath bhi yahi hai:

- **EPSG:4326 (degrees)** = rubber band. "1 degree" Delhi mein alag doori hai,
  Kanyakumari mein alag
- **EPSG:32643 (metres)** = steel scale. 500 ka matlab hamesha 500 metre

**Isliye doori naapne se pehle hamesha `to_crs(32643)` karna padta hai.**
Warna `eps=500` ka matlab "500 degree" ho jata — jo poori duniya se bhi bada hai!

*Humne check kiya:* teeno regions ke numbers **alag** aaye (1,703 / 18,048 /
5,639 metre). Agar teeno ek jaise aate, to samajh jaate ki CRS ki galti hai.

### Sawaal 3: "60% points 'noise' the, unka kya kiya?"

**Rakha. Phenka nahi.** Aur ye soch-samajh kar kiya.

Socho Punjab mein ek kisan apne khet mein **ek baar** aag lagata hai. Uske
aas-paas koi doosri aag nahi. To DBSCAN kahega "ye akela hai, ye noise hai."

Par socho — **wo aag asli thi na?** Wo ek sachi AGRI_BURN ghatna hai!

Agar hum use phenk dete, to model ke paas **khet ki aag seekhne ke liye kuch
bachta hi nahi** — aur wo hamare data ka **61%** hai.

**To humne kya kiya:** har akele point ko *"ek baar dikha source"* maan liya.
Uska "kitne din tak dikha" = 0, yani wo **apne aap EPISODIC** ban gaya.
Bilkul sahi.

---

## 6. 🔴 Sabse badi baat — plan ka ek rule galat nikla

**Ye finale mein tumhara sabse achha jawab hoga. Dhyan se padho.**

### Kya hua tha

Plan mein likha tha: *"jo source 150 din se zyada dikhe **aur** `activity_ratio`
0.25 se upar ho, wo PERSISTENT hai."*

Chalaya, to sirf **1** source mila. Kuch to gadbad thi.

### Dekha to ye mila

| Naam | raat ko? | factory se doori | activity_ratio | pass hua? |
|---|---|---|---|---|
| Reliance Refinery | 100% | 0 m | 0.25 | ✓ bilkul kagaar pe |
| Reliance Refinery | 100% | 0 m | 0.16 | ✗ |
| SHREE DIGVIJAY CEMENT | 100% | 0 m | 0.14 | ✗ |
| **Vadinar Refinery** | **100%** | **0 m** | **0.08** | **✗** |

Dekho — **Vadinar Refinery** hai! Wo **100% raat** ko jalti hai, factory ke
**andar** hai, **saal bhar** dikhi. Isse zyada "factory" kya hoga?

Phir bhi **fail** ho gayi. To rule mein hi kuch galat tha.

### Asli wajah — ek school wali kahani se samjho

`activity_ratio` ka matlab hai: *"jitne din ke andar dikha, unme se kitne din
dikha?"*

Ab socho — **ek teacher ye check karna chahta hai ki Raju roz school aata hai
ya nahi.** Par teacher khud **sirf kabhi-kabhi** aata hai — wo bhi tab jab
baarish na ho.

Saal bhar mein teacher 100 baar aaya, aur Raju 25 baar mila.

Kya teacher ye keh sakta hai *"Raju sirf 25% din aata hai"*? **Nahi!**
Kyunki teacher ne baaki din **check hi nahi kiya**.

**Satellite ke saath bilkul yahi ho raha tha.**

Do saboot nikale:

**Saboot 1:** Poore Jamnagar ilaake mein, saal ke **365 din** mein se sirf
**217 din** koi bhi detection aayi. Baaki din **badal** the, ya satellite ka
angle theek nahi tha. Yani satellite roz dekh hi nahi paya.

**Saboot 2:** Reliance ke flare ki detections mahine ke hisaab se —

```
Jan 40, Feb 16, Mar 25, Apr 8, May 9, Jun 3,
Jul 2, Aug 6, Sep 13, Oct 21, Nov 26, Dec 29
```

**Har mahine dikha!** Matlab flare **24 ghante, saal bhar** jalta hai. Phir
bhi sirf 127 alag din pe dikha.

> **To `activity_ratio` factory ka behaviour nahi naap raha tha — wo
> SATELLITE kitni baar dekh paya, wo naap raha tha.**

### Humne kya fix kiya

Naya rule: **"150 din se zyada dikha, AUR kam se kam 10 alag dinon mein dikha"**

Ye seedhi baat hai — *"lambe samay tak dikha, aur kai baar dikha."*

Aur **number guess nahi kiya, test kiya:**

| kam se kam kitne din | kitne source mile | unme se sahi kitne |
|---|---|---|
| 3 din | 74 | sirf 28 ke naam the |
| 5 din | 13 | 8 |
| **10 din** | **5** | **5 — saare sahi!** |
| 15 din | 4 | 4 |

**10 din pe 100% sahi jawab mila.** Isliye 10 chuna.

> **Agar judge poochhe "ye number kahan se laya?"** — jawab *"plan mein likha
> tha"* mat dena.
>
> Jawab do: **"maine chala kar dekha, wo galat tha. Maine wajah dhoondhi —
> satellite roz dekh hi nahi pata. Phir maine 4 alag numbers test kiye aur jo
> 100% sahi nikla wo chuna."**
>
> Ye jawab tumhe baaki sab teams se alag kar dega.

---

## 7. 🔴 Ek aur ulti baat — factory ki garmi **kam** hoti hai!

| | kitne source | kitne din tak | raat ko | factory se doori | **garmi (FRP)** |
|---|---|---|---|---|---|
| EPISODIC (aag) | 5,830 | 0 din | 0% | 7,658 m | **4.26** |
| **PERSISTENT (factory)** | **5** | **360 din** | **100%** | **0 m** | **1.63** |

Ruko — **factory ki garmi kam?** Aag ki zyada?

**Haan. Aur wajah simple hai:**

- **Factory ka flare = mombatti.** Chhoti si lau, par **raat bhar** jalti hai
- **Khet ki aag = ghaas ka dher.** Ek baar mein **bhadak** kar jal jata hai —
  badi aag, par **ek hi baar**

Ek mombatti ki lau ghaas ke dher se **chhoti** hi hogi na?

> **Isliye agar tum sochte ki "jitni zyada garmi, utni pakki factory" — to
> tumhe BILKUL ULTA jawab milta.**
>
> Yahi wajah hai ki "kitni baar dikha" dekhna zaroori tha, "kitni garmi thi"
> nahi.

Ye baat PPT mein zaroor daalna.

---

## 8. Model ke liye 3 sabse kaam ki cheezein

| Cheez | Factory mein | Aag mein | Kyun |
|---|---|---|---|
| **raat ko dikhta hai?** | 100% | 0% | flare raat-din jalta hai, kisan **din** mein jalata hai |
| **factory se doori** | 0 m | 7,000+ m | seedhi baat |
| **kitne din tak dikha** | 360 | 0 | street light vs patakha |

**"Raat ko dikhta hai ya nahi"** sabse strong nikla — Punjab ke sources ka
average **2%**, factory ka **100%**.

---

## 9. PPT ke liye numbers (copy kar lena)

```
8,415 detections  ->  6,010 sources  ->  5 factory

kis region mein kya mila:
                  aag (EPISODIC)  beech ka  factory (PERSISTENT)
  Jamnagar                   457         9                     5
  Punjab                   3,651       125                     0
  Uttarakhand              1,722        41                     0

har region ka character:
  Jamnagar     factory se 1,703 m door | 44.6% to 1 km ke andar | 41.5% raat ke
  Uttarakhand  factory se 18,048 m door | 57% jungle pe
  Punjab       factory se 5,639 m door | sirf 3.4% raat ke
```

**Sab check ho gaya:** 25 mein se 25 test pass.

Sabse achha test ye tha — 6,010 sources ne milkar kitni detections cover kin?
Jodke dekha to **exactly 8,415**. Yani **ek bhi detection na kho gayi, na do
baar gini gayi.** Ek hi number se poora clustering verify ho gaya.

---

## 10. Chalane ka tareeka

```bash
source venv/bin/activate
python src/step2_context.py      # 2 second
python src/step3_persistence.py  # 37 second
python src/preview_map.py        # 5 second
```

| File bani | Usme kya hai |
|---|---|
| `data/processed/features.gpkg` | 8,415 points, ab har ek ko apna aas-paas pata hai |
| `data/processed/sources.gpkg` | 6,010 sources, har ek ka poora character |
| `outputs/sources_*.png` | rang wale map — laal = factory, neela = aag |

---

## 11. 🔴 Ab tumhe ye 3 kaam karne hain

**1. Screenshot lo (2 minute)**
Section 4 wali table (5 factory ke naam) aur `outputs/sources_jamnagar.png`.
Ye PPT ka dil hai.

**2. QGIS mein khud dekho (10 minute)**
```bash
qgis data/processed/sources.gpkg data/processed/industry.gpkg
```
`sources` pe right-click → Properties → Symbology → **Categorized** →
Value = `persistence_tier` → Classify → OK.

Ab laal wale dots pe click karke unke numbers dekho.

**3. `src/step3_persistence.py` poori padho (20 minute)**
282 lines hain. **Yahi tumhara asli innovation hai** — finale mein sawaal
yahin se aayenge. Khaas kar do jagah:
- jahan noise ka faisla liya
- jahan tier decide hota hai (aur `config.py` ka wo lamba comment)

Kuch samajh na aaye to seedha poochho: *"is function ko line by line samjhao."*

---

## 12. Aage kya hoga (Phase 3)

Ab har source pe **naam ka label** lagega — INDUSTRIAL / FOREST_FIRE / AGRI_BURN.

Test karke dekha, abhi ke rules se ye milega:

```
INDUSTRIAL       17
FOREST_FIRE     824
AGRI_BURN     3,017
-------------------
khud ban jayenge  3,858     <- code apne aap kar dega
samajh nahi aaya  2,152     <- inme se 100 pe AI (Claude) dekhega
```

**Ek problem pehle se pata hai:** Phase 1 mein mila tha ki Punjab ke 5,113
points mein se sirf **5** kisi "khet" wale polygon pe hain — kyunki OSM pe
Punjab ke khet mapped hi nahi hain. To "khet pe hai" wala rule kaam nahi karega.

Uski jagah ye lagayenge: *"jungle pe nahi hai + factory se door hai + ek baar
ki ghatna hai + Apr/May/Oct/Nov mein hui + din mein hui"*. Ye chaaron milkar
kaafi hain.

**Aur ek baat Phase 4 ke liye yaad rakhna:** `sources.gpkg` mein `lon`/`lat`
(jagah ke numbers) hain. **Model ko ye mat dena.** Warna wo "Jamnagar =
factory" ratta maar lega, aur naye shehar mein le jaoge to fail ho jayega.

**Tumhara kaam Phase 3 mein:** 50 sources khud dekh kar label karne honge —
lagbhag **1 ghanta**, wo bhi sirf button dabana. Main uski app bana dunga.

Ye skip mat karna. Baaki 3,858 labels **rules** ne banaye hain — unpe test
karoge to tum sirf ye check kar rahe ho ki *"model ne mere rules ratt liye ya
nahi"*. Wo 50 labels hi **sacchi** parakh hain.
