# Vision layer — where rules go silent

**Status: ✅ working** | Gemini Flash-Lite (free tier) | `src/step4d_gemini.py` + `src/step4e_merge_vlm.py`

---

## 1. What the problem was

Rules only read **numbers**:

```
how far is the factory?     ->  dist_to_industry_m
does it show up at night?   ->  night_ratio
how many months did it run? ->  lifespan_days
what kind of land is it on? ->  lc_class
```

And decisions are made purely from those numbers. That works for 94% of
sources — but **on 1,099 sources no rule fit at all.** They became
"UNSURE".

We tried asking the model on those. Measured, it was only **39%**
accurate there — a coin toss across three classes is 33%. So the model
didn't actually know anything there, it was just guessing. It was made
to stay silent, and those sources became the "review queue".

**But a review queue means a human has to look at 1,099 photos by
hand.** That's not feasible.

---

## 2. The fix: information the rules simply don't have

What the rules don't have is the **actual image.**

A brick kiln hides in the middle of a field. In the numbers it looks
like "farmland": not forest, far from industry (because it isn't
mapped in OSM at all), sitting in one fixed spot. The rules get
confused.

In a photo it's **obvious** — a round chimney, red-brown soil, cut-up
ground.

So that's exactly what we do: pull a satellite photo of the location
and ask a vision model *"what is at this location?"*

---

## 3. Two measured fixes

This didn't work straight away — it went wrong twice, and both times
was fixed by measuring the mistake.

### (a) The source has to be at the CENTER of the photo

When computing the tile number, the decimal gets truncated
(`22743.6 -> 22743`). At zoom 15 a tile is about 1.2 km, so the source
could end up near a corner of the photo. We'd say "look at the
center" and the model would look at the wrong spot.

**Fix:** stitch 3×3 = 9 tiles together and crop a square from the
middle. Now the source is guaranteed to be centered.
(`download_chip()` — `src/step4b_vlm.py`)

### (b) The center needs to be VISIBLE

In the first attempt, Gemini missed **7 out of 11 INDUSTRIAL** cases.
Reading its own reasoning, the pattern was obvious:

> *"The image is **dominated by** agricultural fields..."*
> *"The **surrounding area** is overwhelmingly agricultural..."*

It was describing the **whole picture**. The prompt said "look at the
center", but the photo doesn't show where the center is — the model
had to guess.

**Fix:** draw a **red box** on the photo (about 430 m on the ground).
Now the model knows exactly where to look. (`add_center_mark()`)

---

## 4. Measured — BEFORE trusting it

Before spending money/time on the full run, it was tested on 45 gold
sources whose labels **a human** had made:

```
Gemini correct              81.0%    (answered 42 of 45)
RULES correct (same 42)     76.2%
```

Two things matter here:

1. **It beats the rules** — only slightly, but it does.
2. **It answers where the rules are silent** — and this is the real
   payoff. The rules' 76% is measured only on the sources they
   answered. On the remaining 1,099 they have no score at all.

An `UNSURE` answer is **not counted as wrong**. Saying "I don't know"
is different from giving a wrong answer — and better.

---

## 5. Three locks when merging

`step4e_merge_vlm.py` is deliberately **stingy**:

| Condition | Why |
|---|---|
| Only `UNSURE` sources get a label | Rules sit at 76%, VLM at 81%. That gap isn't big enough to justify ripping out labels that already work. Where rules were silent, there is nothing but the VLM — that's where the real gain is. |
| **Gold sources are never touched** | 45 gold labels are our exam. `gemini_labels.csv` also contains those 45 (from `--validate`). Stamping a VLM label on them would change the exam paper itself and inflate the score falsely. `step5_train.py` also removes gold from training — two locks are better than one. |
| A conflict does **not** change the label | Where the rule said one thing and the VLM said another, the rule's label stays and the source gets flagged `vlm_conflict = True`. A disagreement between two independent methods is exactly where a human's time is most useful. |

---

## 6. Result

```
                    BEFORE     NOW      change
INDUSTRIAL            136     192      +56    (+41%)
FOREST_FIRE         5,122   5,134      +12
AGRI_BURN          11,258  11,581     +323
UNSURE (queue)      1,099     708     −391    (−36%)
```

The most important line is **INDUSTRIAL**. It was our smallest class
by far (`DATA_AUDIT.md` complains about exactly this imbalance), and
it's the class the whole project is built around. Getting 41% more
examples is a direct benefit to the model.

---

## 7. What we are NOT claiming

- **81% is not a rock-solid number.** It was measured on 42 answered
  sources — the interval is roughly ±12 points. The honest reading is:
  *"it beats the rules and it answers where they're silent"*, not a
  precise score.
- **The model's own `confidence` isn't reliable.** Its average is 0.90
  — and that includes its MISTAKES. It's a comment, not a probability.
  That's why no threshold is applied to it.
- **This doesn't replace a human.** It **shrinks** the review queue, it
  doesn't eliminate it. 708 sources are still in the queue, and
  conflicting sources are deliberately put back into it.
- **On 12 sources the VLM said "forest" where ESA WorldCover doesn't
  call it forest.** Either could be wrong — WorldCover is from 2021 at
  10 m resolution, the imagery is newer. This is an open question, not
  hidden away.

---

## 8. How to run it

```bash
# put GEMINI_API_KEY in .env (free, no credit card needed)
#   https://aistudio.google.com/apikey

python src/step4d_gemini.py --validate   # measure first (on 45 gold)
python src/step4d_gemini.py              # then run on the review queue
python src/step4e_merge_vlm.py           # merge the answers into labels
python src/step5_train.py                # retrain on the new labels
```

Hitting `Ctrl+C` partway through loses nothing — progress is saved
continuously to `data/processed/gemini_labels.csv` and the next run
picks up from there.

Both of these steps are **optional** in `run_all.py`: without an API
key the pipeline prints a warning and moves on, building labels from
rules alone.

---

## 9. The Claude route

`src/step4b_vlm.py` does the same job with Claude Opus 5 (needs a paid
key), and `step4c_vlm_validate.py` measures it against gold. Both
scripts are ready but haven't been run yet — Gemini's free tier was
enough for this job.

The most useful future use: as a **referee**. Instead of rerunning
across all ~8,000 sources, run Claude only on the ~100 or so sources
where Gemini and the rules **disagree**. When two independent models
agree on something, that label is far more trustworthy — and where
they still don't agree, that's exactly what genuinely deserves human
eyes.
