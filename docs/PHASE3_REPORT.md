# Phase 3 — Naming every source (labelling)

**Status: ✅ COMPLETE** | 20/20 checks pass | **50 gold labels done** ✅
**Remaining:** only the AI step (needs an API key — Part 7)

---

## 1. Let's start with a story

Imagine you have 6,010 photos — each with a bright dot in it. You need
to write on every photo what that dot is: a **factory**, a **forest
fire**, or a **field fire**.

Sit down and label them one by one and that's 6,010 minutes = **100
hours**.

So three methods are combined:

| Method | How many sources | Who does it |
|---|---|---|
| **1. Rules** — simple conditions | 3,858 (64%) | code, in 1 second |
| **2. AI** — looks at the satellite photo | 100 | Claude |
| **3. Human** — you yourself | 50 | **you, ~1 hour** |

The first method is **cheap and fast** but crude. The second is
**expensive but smart**. The third is **most expensive but most
honest**.

---

## 2. ⭐ Result — the rules worked

```
6,010 sources
  INDUSTRIAL      17   ( 0.3%)
  FOREST_FIRE    824   (13.7%)
  AGRI_BURN    3,017   (50.2%)
  ─────────────────────────────
  UNSURE       2,152   (35.8%)   <- no rule fit these
```

By region:

| | AGRI_BURN | FOREST_FIRE | INDUSTRIAL | UNSURE |
|---|---|---|---|---|
| **Jamnagar** | 140 | 0 | **10** | 321 |
| **Punjab** | **2,593** | 3 | 6 | 1,174 |
| **Uttarakhand** | 284 | **821** | 1 | 657 |

Look — in every region, the label that dominates is exactly the one
that should. Farmland in Punjab, forest in Uttarakhand, factories in
Jamnagar. **The rules are working.**

---

## 3. Three rules — that's the entire "knowledge" here

### INDUSTRIAL — a factory's flare

```
within 1 km of a factory  AND  not a one-off event
```

**Why the second condition:** someone could burn something once right
next to a factory too (burning trash, say). That's not the factory's
flare.

### FOREST_FIRE — a forest fire

```
on a forested area  AND  5 km from a factory  AND  a one-off event
```

### AGRI_BURN — a field fire

This rule **differs from the plan**, and for a solid reason. See Part
4 below.

---

## 4. 🔴 The plan's rule simply couldn't work — we changed it

**This is a good answer for the finals.**

### What the plan says

```
AGRI_BURN = lc_class == "cropland" AND ...
```

Meaning the source had to sit on a **"farmland" polygon**.

### Why that doesn't work

This was already discovered in Phase 1:

> Of Punjab's **5,113 detections**, only **FIVE** sit on any farmland
> polygon. Because Punjab's farmland simply isn't mapped on
> OpenStreetMap — only **1.3%** of the whole area.

People map roads and buildings on OSM, not fields.

Applying the plan's rule as-is would have left **61% of Punjab's data
as UNSURE** — and the AGRI_BURN class would be practically empty.

### What was done instead

Instead of "sits on farmland", **five conditions** were used together
to do the same job:

```
1. NOT on forest                    (otherwise it'd be a forest fire)
2. 3 km from a factory
3. a one-off event
4. happened during harvest months   (Apr/May = wheat, Oct/Nov = rice)
5. happened during the DAY          (night_ratio < 0.3)
```

**Conditions 4 and 5 came from Phase 2's findings:**
- **93%** of Punjab's detections fall in exactly these 4 months
- **97%** of Punjab's detections are daytime (a farmer burns during
  the day), while a factory's flare had a night_ratio of **1.00**

> **What to tell a judge:** *"The plan had a cropland-polygon rule. I
> checked the data and found Punjab's farmland isn't mapped on OSM at
> all — only 1.3% coverage. So instead of that one condition, I used
> five conditions that come straight from the satellite data itself,
> with no dependence on an external map."*

---

## 5. Saying "I don't know" — a deliberate decision

2,152 sources (36%) are **UNSURE**. This is **not a failure**, it's a
design choice.

For any source where:
- **no rule fit** → UNSURE
- **two rules fit at once** (e.g. near forest and near a factory both)
  → UNSURE

we don't force a label onto it.

**Why:** a wrong label would teach the model the wrong thing. **Saying
"I don't know" is better than giving a wrong answer.** And it's
exactly these UNSURE cases that AI and human eyes will look at — the
real learning happens there.

### `needs_review` — what needs a second look

**2,156 sources** need review:
1. those that are UNSURE
2. those in the **"confusing zone"** — between **500 and 3000 metres**
   from a factory. This is a dangerous distance: close enough that it
   might be part of the factory, far enough that it might be something
   entirely different. Rules make most of their mistakes here.

---

## 6. Anomaly — "something different happened today"

An anomaly is a **separate thing**, not a class.

**The idea:** if a factory gives off 5 MW of heat every day, and one
day it suddenly gives off 20 MW — then **something happened that
day**.

For every PERSISTENT source, each day's heat was compared against
**that source's own normal**.

*"Against its own normal"* — this matters. Every factory's normal is
different; a big refinery might normally run at 8 MW, a small one at 2
MW.

### Result

| source | date | that day's FRP | normal FRP | how many times |
|---|---|---|---|---|
| **Reliance Refinery** | 2025-11-09 | 6.95 | 1.63 | **4.26×** |

One anomaly found. **On November 9, 2025, the Reliance flare gave off
4 times its normal heat.**

*Why only one:* there are only 5 PERSISTENT sources so far, and their
heat is fairly steady. That's a good thing — it means the threshold
isn't raising noise. This will show up as a tab in the dashboard.

---

## 7. The AI step (code ready, hasn't run yet)

`src/step4b_vlm.py` pulls a **satellite photo** of confusing sources
and asks Claude *"what do you see in this photo?"*

**Why it works:** rules only look at **numbers** (distance, month,
day/night). A photo shows **with your own eyes** whether there's a
factory, forest, or field there. Where OSM's data is incomplete (like
Punjab's farmland), **the photo alone can tell the truth**.

### 🔴 A bug caught while building this — the photo was of the wrong place

Maps are stored as small square tiles. When computing the tile number
from lat/long, the decimal gets truncated — `22743.99` becomes
`22743`.

That meant our location could end up right at a tile's **corner**. At
zoom 15 a tile is **~1.2 km**, so the source could be **up to 1 km**
away from the photo's center.

And we were telling Claude *"look at the CENTER of the photo"* — it
would look at the wrong spot!

Tested it: Reliance's offset came out as **(0.72, 0.99)** — right at
the corner.

**Fix:** download 3×3 = 9 tiles, stitch them together, then crop a
512×512 square directly over the source. Now the source is
**guaranteed centered**. Confirmed by testing — Reliance's photo shows
its storage tanks and process units right in the middle.

### Two more things fixed

**Structured output** — instead of asking Claude for JSON in plain
text, a **schema** was given. This guarantees the answer **always**
comes back as valid JSON. Without it, the model would sometimes wrap
the reply in ` ```json ` and crash the code.

**Model** — the plan named `claude-sonnet-4-6`, which is now outdated.
`claude-opus-5` is used now (can be changed in `config.py`).

### 🔴 Needs an API key to run

```bash
# add this line to .env:
ANTHROPIC_API_KEY=sk-ant-...
```
Get a key here: https://console.anthropic.com/settings/keys

Then:
```bash
python src/step4b_vlm.py --limit 20    # test on the first 20
python src/step4b_vlm.py               # then run on all 100
```

---

## 8. 🔴 You now have 2 things to do

### Task 1 — add the API key (2 minutes)

Covered in Part 7 above. The AI step won't run without it. Test with
`--limit 20` first, then run the full batch.

### Task 2 — label 50 sources yourself ✅ **DONE**

The result is in Part 12. The section below is kept for reference.

---

### (done) Labelling 50 sources yourself ⭐

```bash
streamlit run src/gold_ui.py
```

An app opens. For each source it shows:
- **satellite photo** (source centered)
- **an FRP chart** — how the heat changed over time
- **all the numbers** — how often seen, over how many days, % at night,
  distance from factory
- **a Google Maps link** — zoom in there if unsure
- **4 buttons:** INDUSTRIAL / FOREST_FIRE / AGRI_BURN / UNCLEAR
- **a notes box**

About **1 minute** per source. Progress is saved continuously — you
can stop partway and come back. Grab a cup of tea and sit down for it.

#### Don't skip this — here's why

The other 3,858 labels were made by **rules**. Testing the model only
against those just checks **"did the model memorize my own rules"**.
That accuracy would be **fake** — it'd come out at 95% and mean
nothing.

These 50 labels were made by a **human**. The model has never seen
them. **That's exactly why the score on them is the honest score.**

One more benefit: while labelling, you'll spot **3-4 mistakes yourself**
that no rule could ever catch — like a factory that isn't even on OSM,
or a spot that looks like it could be either. **That will make your
best slide.**

*(There's a "How do I decide?" section built into the app itself — open
it if you're unsure.)*

#### How the 50 sources were chosen

Picking 50 at random would have pulled mostly Punjab's AGRI_BURN cases
(there are the most of those) and zero INDUSTRIAL. The test set would
be useless.

So an **equal** number was drawn from every (region × label) pair:

| | AGRI_BURN | FOREST_FIRE | INDUSTRIAL | UNSURE |
|---|---|---|---|---|
| Jamnagar | 4 | 0 | 4 | 5 |
| Punjab | 7 | 3 | 4 | 6 |
| Uttarakhand | 4 | 6 | 1 | 6 |

Every kind of source made it into the test set. (This is called
**stratified sampling** — that term will come in handy at the finals.)

---

## 9. Verification — 20/20 pass

Just "no errors" isn't enough. Every rule was checked **backwards**:

```
6,010 rows      - not one more or fewer than the sources
every source has a label, none blank

every INDUSTRIAL  : is genuinely <1km AND non-episodic
every FOREST_FIRE : is genuinely forest AND >5km AND episodic
every AGRI_BURN   : genuinely satisfies all five conditions

UNSURE are exactly those where no single rule fit
needs_review = UNSURE or confusing-zone

every anomaly has ratio > 3, and only from PERSISTENT sources
```

**The code was also tested:**
- tile math — from `(0,0)` to `16384,16384` (the exact center of the
  map) ✓
- chip download — Reliance's actual photo, 512×512, centered ✓
- gold UI — run through Streamlit's own test framework, button pressed,
  CSV written ✓
- the choice of 50 sources is deterministic (reopen the app, same 50) ✓

---

## 10. Files and how to run it

```bash
source venv/bin/activate

python src/step4_labels.py       # rules      (1 second)
python src/step4b_vlm.py         # AI         (needs an API key)
streamlit run src/gold_ui.py     # you        (~1 hour)
```

| File | What it is |
|---|---|
| `data/processed/sources_labelled.gpkg` | 6,010 sources + label |
| `data/processed/anomalies.csv` | 1 anomaly |
| `data/processed/gold_labels.csv` | *(your 50 labels — created once run)* |
| `data/chips/*.jpg` | satellite photos |

**New columns** in `sources_labelled.gpkg`:

| Column | Meaning |
|---|---|
| `rule_label` | what the rules said (never changes) |
| `label` | **final label** — AI or a human can change this |
| `label_source` | where this label came from: `rule` / `vlm` / `none` |
| `needs_review` | does this need a second look? |
| `vlm_landuse` | what the AI saw in the photo *(after the VLM runs)* |

The benefit of keeping `rule_label` separate: later you can compare
**how many of the rules' mistakes the AI fixed** — that's a slide of
its own.

---

## 11. For Phase 4

The model gets trained. Two things to keep in mind:

**1. Don't make `lon`/`lat` a feature.** Otherwise the model will just
memorize *"Jamnagar = factory"* and fail in a new city.

**2. Three separate scores are needed:**
- normal cross-validation
- GroupKFold (the same source never in both train and test)
- **on the 50 gold labels** ← this will come out the lowest

**A lower score here isn't wrong — it's honest.** That's what Slide 5
will be, and it's what will set you apart from other teams.

Expected: **0.75–0.85** on the gold set. If it comes out at 0.97,
something's wrong somewhere (probably a lat/long feature leaking in).

**3. There's now a baseline too.** The rules' own score on the gold set
is **76%** (Part 12). The model should beat that — otherwise it would
prove the model only memorized the rules and learned nothing beyond
them.


---

## 12. ⭐ Gold label results — and this turned out to be the most valuable part

50 sources were hand-labelled:

```
AGRI_BURN     18
FOREST_FIRE   18
INDUSTRIAL    14
```

Good balance — all three classes are well represented, and none are
UNCLEAR.

### The rules' real score — two separate numbers

One single number doesn't tell the story, because the rules sometimes
say *"I don't know"* too. So two numbers are needed:

| | |
|---|---|
| **Coverage** — how many the rules answered | **33/50 = 66%** |
| **Accuracy** — of those answered, how many correct | **25/33 = 76%** |
| rules said "don't know" | 17/50 |

**Saying "I don't know" isn't a mistake — it was by design.** That's
exactly why the AI and human steps exist.

> **It's important to report these two numbers separately.** Saying
> just "25 out of 50 correct = 50%" would be misleading — as if the
> rules are wrong half the time. In reality they stay **silent** half
> the time, and when they do answer, they're right 76% of the time.

### 🔴 The pattern in the mistakes — and they share one cause

| rules said | it actually was | how many times |
|---|---|---|
| AGRI_BURN | **FOREST_FIRE** | **4** |
| AGRI_BURN | INDUSTRIAL | 2 |
| FOREST_FIRE | AGRI_BURN | 1 |
| INDUSTRIAL | FOREST_FIRE | 1 |

Digging into the biggest category of mistake (4 times):

> All **four** had `lc_class` = **"unknown"**.

Meaning the forest simply **wasn't mapped** on OSM. So the AGRI rule's
first condition — *"NOT on forest"* — passed, and the rule fired.
Even though the photo clearly showed forest.

**This is the same OSM gap found in Phase 1 for Punjab's farmland —
just cutting from the other direction now.** Among these 50 sources:

```
lc_class = unknown   41   (82%)
lc_class = forest     9   (18%)
```

**OSM has no idea what kind of land 82% of these sources sit on.**

> This is now very strong material for Slide 9 (Limitations). What was
> once a suspicion is now **proven by human labels**: OSM's
> incompleteness is the rules' single biggest source of error.

### And what you caught better than the rules

**4 sources** where the rules gave up, but you correctly identified
INDUSTRIAL. The most interesting one:

| source | % at night | distance from factory | how often seen |
|---|---|---|---|
| `jamnagar_n32` | **100%** | **57 m** | 1 |

This source is **57 metres** from the factory's boundary and showed up
**at night** — anyone would call it industrial. But the rule rejected
it, because it only showed up **once**, and the INDUSTRIAL rule
requires "not a one-off event."

**This is a genuine hole in the rule** — and a human caught it, not
the code.

### 🔴 But don't now go and "fix" the rules using these mistakes

This trap is very easy to fall into, so understand it clearly:

Now that you know where the rules go wrong, you'll be tempted to fix
them. **Doing that would make these 50 labels worthless.**

Because then the rules would have been **built by looking at these
exact 50** — and testing on them again would give 100%. That number
would be fake. That's the exact mistake these 50 labels were created
to avoid.

**These 50 labels exist only to CHECK, not to build.**

*(If the rules do need fixing, do it by looking at the other 5,960
sources — the ones not in these 50.)*

### How these will be used going forward

```
Phase 4 will TRAIN the model  -> on the rules' 3,858 labels
Phase 4 will TEST the model   -> on these 50 gold labels
```

And now there's also **the rules' own score (76%)** to compare
against. If the model beats it, that proves **the model learned more
than the rules, not just memorized them.**

This is a slide almost no other team will be able to show.
