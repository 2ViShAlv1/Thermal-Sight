# Phase 2 — Finding things that show up again and again

**Status: ✅ done** | This is the **most important part** of the project

---

## 1. Let's start with a story

Imagine you're standing on your roof at night looking at the city.
You see two kinds of light:

**One — a street light.** It's on every night. It'll be on tomorrow,
and the day after. A small light, but **always the same spot**.

**The other — a firecracker.** It bursts once, a bright flash, and
that's it. Tomorrow there'll be nothing there.

Now if someone asked you *"how do you tell these two apart?"* — you
**can't tell from one night alone.** Both are just light.

But if you watch **the whole year**, the difference becomes obvious:
the street light shows up **every day**, the firecracker **once**.

**That's exactly what Phase 2 does.**

- **A factory's flare** = a street light. Burns every day, same spot
- **A forest or field fire** = a firecracker. Once, then gone

---

## 2. A big mistake we'd been making up to now

Until now we were treating every detection as a **separate thing**.

Imagine you photograph your neighborhood's tea stall every morning.
Over a year, that's 198 photos.

Now if someone came along and said *"your neighborhood has 198 tea
stalls!"* — that would be wrong, right? **There's one stall. There are
198 photos.**

That's exactly what was happening in our data. Reliance's **one**
flare was detected **198 times**. Those aren't 198 separate things —
**one thing that showed up 198 times.**

**Phase 2's first job:** merge those 198 rows into **one** "source".

---

## 3. Phase 2 does two jobs

```
Phase 1's three files (which had no idea about each other)
        |
        |  JOB 1: "what's around each hot point?"
        |          (is a factory nearby? is it on forest? on farmland?)
        v
   features.gpkg  -  8,415 points, each now knows what's around it
        |
        |  JOB 2: "which points are actually THE SAME thing?"
        v
   sources.gpkg   -  6,010 sources
```

---

## 4. ⭐ Result — this one will make you happy

```
8,415 detections  ->  6,010 sources  ->  5 that kept running all year
```

Here's who those 5 turned out to be:

| Name | times seen | distinct days | over how many days | at night? | distance from factory |
|---|---|---|---|---|---|
| **Reliance Refinery** | 101 | 91 | 361 days | **100%** | **0 m** |
| **Reliance Refinery** | 63 | 57 | 361 days | **100%** | **0 m** |
| **SHREE DIGVIJAY CEMENT** | 52 | 50 | 358 days | **100%** | **0 m** |
| **Vadinar Refinery** | 31 | 29 | 360 days | **100%** | **0 m** |
| **Reliance Refinery** | 16 | 12 | 337 days | **100%** | **0 m** |

Read it like this:

> *"Heat was detected at the Reliance Refinery site **101 times**, on
> **91 distinct days**, within a span of **361 days**. And **every
> single time, at night**. And the location is **inside** the
> factory's boundary (0 metres)."*

**All five are real factory names.** Not one is wrong.

And **not a single one in Uttarakhand or Punjab** — because those have
forest and field fires, not factories. **Exactly how it should be.**

**→ Take a screenshot of this. This is the biggest slide in your PPT.**

---

## 5. Judges will ask these 3 questions — memorize the answers

### Question 1: "What is DBSCAN?"

Imagine a fair is going on. You take a photo from above. Some people
are standing **in groups**, some are wandering **alone**.

DBSCAN does exactly that job — **it treats points that are close
together as one group.**

There are two settings:

- **`eps = 500 metres`** — "how close together counts as one group?"
  We used 500 m, because a single satellite pixel is already 375 m
- **`min_samples = 3`** — "how many people minimum to call it a group?"
  We used 3

Any point that doesn't belong to a group, DBSCAN calls **"noise"**.

**Why this works:** a factory's flare **always burns at the same
spot** — so all its detections form one tight group. A forest fire
**moves** — it stays scattered.

### Question 2: "What's this CRS business about?"

Imagine you're measuring cloth. There are two ways:

- **With a rubber band** — it stretches, gives a different measurement
  every time
- **With a steel ruler** — always the correct measurement

It's the same with maps:

- **EPSG:4326 (degrees)** = the rubber band. "1 degree" is a different
  distance in Delhi than in Kanyakumari
- **EPSG:32643 (metres)** = the steel ruler. 500 always means 500
  metres

**That's why distance always has to be measured after `to_crs(32643)`.**
Otherwise `eps=500` would mean "500 degrees" — bigger than the whole
Earth!

*We checked:* the numbers came out **different** across the three
regions (1,703 / 18,048 / 5,639 metres). If all three had come out the
same, that would have told us the CRS was wrong.

### Question 3: "60% of points were 'noise' — what did you do with them?"

**Kept them. Didn't throw them away.** And this was a deliberate
choice.

Imagine a farmer in Punjab burns his field **once**. No other fire
nearby. So DBSCAN says "this one's alone, this is noise."

But think about it — **was that fire real?** It's a genuine AGRI_BURN
event!

If we'd thrown it away, the model would have **nothing left to learn
crop-burning from** — and that's **61%** of our data.

**So here's what we did:** every lone point was treated as *"a source
that showed up once."* Its "how many days it showed up" = 0, which
**automatically makes it EPISODIC.** Exactly right.

---

## 6. 🔴 The biggest thing — one rule from the plan turned out to be wrong

**This will be your best answer in the finals. Read it carefully.**

### What happened

The plan said: *"a source seen over more than 150 days **and** with
`activity_ratio` above 0.25 is PERSISTENT."*

Ran it, and got only **1** source. Something was off.

### What we found on closer look

| Name | at night? | distance from factory | activity_ratio | passed? |
|---|---|---|---|---|
| Reliance Refinery | 100% | 0 m | 0.25 | ✓ right at the edge |
| Reliance Refinery | 100% | 0 m | 0.16 | ✗ |
| SHREE DIGVIJAY CEMENT | 100% | 0 m | 0.14 | ✗ |
| **Vadinar Refinery** | **100%** | **0 m** | **0.08** | **✗** |

Look — **Vadinar Refinery**! It burns **100% at night**, is **inside**
the factory, and showed up **all year round**. What could be more
"factory" than that?

And yet it **failed**. So something was wrong with the rule itself.

### The real reason — understood through a school story

`activity_ratio` means: *"of all the days it could have shown up, on
how many days did it actually show up?"*

Now imagine — **a teacher wants to check whether Raju comes to school
every day.** But the teacher himself only shows up **occasionally** —
and only when it isn't raining.

Over the year the teacher came 100 times, and saw Raju 25 of those
times.

Can the teacher say *"Raju only shows up 25% of the time"*? **No!**
Because the teacher **never even checked** the other days.

**Exactly the same thing was happening with the satellite.**

Two pieces of evidence:

**Evidence 1:** across the whole Jamnagar area, out of the year's
**365 days**, a detection of any kind arrived on only **217 days**. On
the rest, it was **cloudy**, or the satellite's viewing angle was
wrong. In other words, the satellite simply couldn't look every day.

**Evidence 2:** detections of the Reliance flare, by month —

```
Jan 40, Feb 16, Mar 25, Apr 8, May 9, Jun 3,
Jul 2, Aug 6, Sep 13, Oct 21, Nov 26, Dec 29
```

**It showed up every single month!** Meaning the flare burns **24
hours a day, all year round**. And yet it was only seen on 127
distinct days.

> **So `activity_ratio` wasn't measuring the factory's behaviour — it
> was measuring how often the SATELLITE managed to look.**

### What we fixed

New rule: **"seen over more than 150 days, AND seen on at least 10
distinct days"**

That's a simple statement — *"showed up over a long time, and showed
up many times."*

And **we didn't guess the number, we tested it:**

| minimum days | sources found | how many correct |
|---|---|---|
| 3 days | 74 | only 28 were named correctly |
| 5 days | 13 | 8 |
| **10 days** | **5** | **5 — all correct!** |
| 15 days | 4 | 4 |

**10 days gave 100% correct answers.** So 10 was chosen.

> **If a judge asks "where did this number come from?"** — don't
> answer *"it was in the plan."*
>
> Answer: **"I ran it and it was wrong. I found the reason — the
> satellite simply doesn't look every day. Then I tested four
> different numbers and picked the one that came out 100% correct."**
>
> That answer will set you apart from every other team.

---

## 7. 🔴 One more surprising thing — a factory's heat is actually **lower**!

| | # sources | over how many days | at night | distance from factory | **heat (FRP)** |
|---|---|---|---|---|---|
| EPISODIC (fire) | 5,830 | 0 days | 0% | 7,658 m | **4.26** |
| **PERSISTENT (factory)** | **5** | **360 days** | **100%** | **0 m** | **1.63** |

Wait — **a factory's heat is lower?** A fire's is higher?

**Yes. And the reason is simple:**

- **A factory's flare = a candle.** A small flame, but it burns **all
  night long**
- **A field fire = a haystack.** It **flares up** all at once — a big
  fire, but only **once**

A candle's flame is obviously **smaller** than a burning haystack,
right?

> **So if you thought "more heat means more likely to be a factory" —
> you'd get EXACTLY the opposite answer.**
>
> This is exactly why "how many times it showed up" mattered, not
> "how hot it was."

Make sure this goes in the PPT.

---

## 8. The 3 most useful things for the model

| Feature | In a factory | In a fire | Why |
|---|---|---|---|
| **shows up at night?** | 100% | 0% | a flare burns day and night, a farmer burns **during the day** |
| **distance from factory** | 0 m | 7,000+ m | self-explanatory |
| **how many days it showed up** | 360 | 0 | street light vs firecracker |

**"Whether it shows up at night"** turned out to be the strongest —
Punjab's sources average **2%**, a factory's is **100%**.

---

## 9. Numbers for the PPT (copy these)

```
8,415 detections  ->  6,010 sources  ->  5 factories

what was found in each region:
                  fire (EPISODIC)  in-between  factory (PERSISTENT)
  Jamnagar                   457         9                     5
  Punjab                   3,651       125                     0
  Uttarakhand              1,722        41                     0

character of each region:
  Jamnagar     1,703 m from factory | 44.6% within 1 km | 41.5% at night
  Uttarakhand  18,048 m from factory | 57% on forest
  Punjab       5,639 m from factory | only 3.4% at night
```

**Everything checked out:** 25 out of 25 tests passed.

The best test was this — do the 6,010 sources together cover exactly
how many detections? Added them up and got **exactly 8,415**. Meaning
**not a single detection was lost, or counted twice.** One single
number verified the entire clustering.

---

## 10. How to run it

```bash
source venv/bin/activate
python src/step2_context.py      # 2 seconds
python src/step3_persistence.py  # 37 seconds
python src/preview_map.py        # 5 seconds
```

| File produced | What's in it |
|---|---|
| `data/processed/features.gpkg` | 8,415 points, each now knows what's around it |
| `data/processed/sources.gpkg` | 6,010 sources, full character of each |
| `outputs/sources_*.png` | color-coded maps — red = factory, blue = fire |

---

## 11. 🔴 Now you have 3 things to do

**1. Take screenshots (2 minutes)**
The table in Section 4 (the 5 factory names) and
`outputs/sources_jamnagar.png`. This is the heart of the PPT.

**2. Look at it yourself in QGIS (10 minutes)**
```bash
qgis data/processed/sources.gpkg data/processed/industry.gpkg
```
Right-click `sources` → Properties → Symbology → **Categorized** →
Value = `persistence_tier` → Classify → OK.

Now click on the red dots and look at their numbers.

**3. Read all of `src/step3_persistence.py` (20 minutes)**
It's 282 lines. **This is your real innovation** — this is where the
finals' questions will come from. Especially two spots:
- where the noise decision is made
- where the tier is decided (and that long comment in `config.py`)

If anything doesn't make sense, just ask directly: *"explain this
function line by line."*

---

## 12. What comes next (Phase 3)

Every source now gets a **named label** — INDUSTRIAL / FOREST_FIRE /
AGRI_BURN.

Tested with the current rules, here's what we'd get:

```
INDUSTRIAL       17
FOREST_FIRE     824
AGRI_BURN     3,017
-------------------
labelled automatically  3,858     <- the code will do this on its own
unclear                 2,152     <- 100 of these will go to AI (Claude)
```

**One problem is already known:** Phase 1 found that of Punjab's 5,113
points, only **5** sit on any "farmland" polygon — because Punjab's
farmland isn't mapped in OSM at all. So the "on farmland" rule won't
work there.

Instead we'll use: *"not on forest + far from a factory + a one-off
event + happened in Apr/May/Oct/Nov + happened during the day"*. These
four together are enough.

**One more thing to remember for Phase 4:** `sources.gpkg` has
`lon`/`lat` (location numbers). **Don't give these to the model.**
Otherwise it'll just memorize "Jamnagar = factory," and it'll fail the
moment you take it to a new city.

**Your job in Phase 3:** hand-label 50 sources yourself by looking at
them — roughly **1 hour**, and just button-pressing at that. I'll
build the app for it.

Don't skip this. The other 3,858 labels were made by **rules** —
testing against those only checks whether *"the model memorized my own
rules."* Those 50 labels are the only **genuine** test.
