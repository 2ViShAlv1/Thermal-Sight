"""
STEP 4d - Gemini (FREE) se satellite photo dekh kar label.

KYUN YE ZAROORI HAI:
    Phase 4 mein pata chala ki model rules ki NAKAL utaar raha hai -
    100% wahi jawab deta hai jo rules dete hain. Wajah: uske training
    labels bhi rules ne hi banaye the, to usme koi NAYI jaankari thi
    hi nahi.

    Iska ilaaj: aisi jaankari jo rules ke paas hai hi nahi - yani
    ASLI SATELLITE PHOTO. Rules sirf numbers dekhte hain (doori,
    mahina, raat/din). Photo mein aankhon se dikh jata hai ki wahan
    factory hai, jungle hai, ya khet.

KYUN GEMINI:
    Naapa hua: photo dekh kar label karna un sources pe 83% sahi tha
    jahan rules bilkul chup the (model wahan 39% pe tha, tukka 33%).

    Gemini ka free tier ismein sabse fit baitha:
      local gemma3 (CPU)  ->  36 din   (6.5 min per photo, GPU nahi hai)
      Gemini Flash-Lite   ->  ~1 din   FREE
      paid API            ->  20 min   ~$104

CHALANE SE PEHLE:
    1. Key lo (free, credit card nahi chahiye):
           https://aistudio.google.com/apikey
    2. .env mein daalo:
           GEMINI_API_KEY=AIza...

CHALANE KA TAREEKA:
    python src/step4d_gemini.py --validate     # pehle YE - 47 gold pe naapo
    python src/step4d_gemini.py --limit 200    # phir asli kaam
    python src/step4d_gemini.py                # saare UNSURE

    Beech mein Ctrl+C dabao to bhi kuch nahi jaata - progress CSV mein
    save hoti rehti hai aur agli baar wahin se aage chalta hai.

Output: data/processed/gemini_labels.csv   (har source pe VLM ka jawab)
        outputs/gemini_validation.json     (--validate ke saath)
"""
import json
import os
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
from PIL import Image, ImageDraw
from dotenv import load_dotenv
from tqdm import tqdm

from config import DATA_PROCESSED, OUTPUTS
from step4b_vlm import download_chip, PROMPT, HINT, VLM_TO_LABEL

load_dotenv()

# ---------------------------------------------------------------
# Model: Flash-Lite - sabse tez aur free tier mein sabse generous.
# Ye multimodal hai (photo + text dono leta hai).
# ---------------------------------------------------------------
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Free tier pe rate limit hai (~10-15 request/minute). Isse zyada tez
# bhejoge to 429 milega. 12/min surakshit hai.
RPM = int(os.getenv("GEMINI_RPM", "12"))
SLEEP = 60.0 / RPM

OUT_CSV = DATA_PROCESSED / "gemini_labels.csv"

# Itne sources LAGATAR fail ho jayein to ruk jao.
# Wajah: free tier pe roz ki limit hai. Wo khatam hote hi har call 429
# deti hai, aur retry backoff ke saath har source pe ~2 minute lagte
# hain. Aise mein chalte rehna ghante barbaad karta hai - ruk kar SAAF
# batana behtar hai.
STOP_AFTER_FAILS = 5

# ---------------------------------------------------------------
# BEECH KA NISHAAN - ye ek naapa hua fix hai.
#
# Pehli koshish mein Gemini 11 mein se 7 INDUSTRIAL chook gaya. Uski
# apni wajah padhne pe pattern saaf tha:
#     "The image is DOMINATED BY agricultural fields..."
#     "The SURROUNDING AREA is overwhelmingly agricultural..."
#
# Yani wo POORI tasveer describe kar raha tha, beech wale point ko
# nahi dekh raha tha. Prompt kehta hai "beech mein dekho", par photo
# mein beech kahan hai ye DIKHTA hi nahi - use andaza lagana padta hai.
#
# Bhatta ya chhoti factory khet ke beech chhupi hoti hai. Poori photo
# dekho to khet hi khet dikhte hain.
#
# Isliye photo pe ek laal chaukor bana dete hain. Ab VLM ko bilkul
# pata hai kahan dekhna hai.
# ---------------------------------------------------------------
MARK_BOX = 90        # pixels - lagbhag 430 m zameen pe (zoom 15)


def add_center_mark(chip_path):
    """Photo ke beech mein laal chaukor bana kar nayi file mein save karo."""
    marked = chip_path.with_name(chip_path.stem + "_marked.jpg")
    if marked.exists() and marked.stat().st_size > 1000:
        return marked
    im = Image.open(chip_path).convert("RGB")
    w, h = im.size
    cx, cy = w // 2, h // 2
    d = ImageDraw.Draw(im)
    half = MARK_BOX // 2
    # laal chaukor + chaar chhote kone ke nishaan
    d.rectangle([cx - half, cy - half, cx + half, cy + half],
                outline=(255, 0, 0), width=3)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        d.line([cx + dx * half, cy + dy * half,
                cx + dx * (half + 18), cy + dy * (half + 18)],
               fill=(255, 0, 0), width=3)
    im.save(marked, "JPEG", quality=88)
    return marked


# ---------------------------------------------------------------
# Naya prompt - do badlav:
#   1. laal chaukor ka zikr (kahan dekhna hai)
#   2. saaf warning ki chhoti industrial cheez khet ke beech ho sakti hai
#      (yahi 7 galtiyon ki wajah thi)
# ---------------------------------------------------------------
GEMINI_PROMPT = """Ye satellite photo hai (Esri World Imagery, zoom 15).

Photo ke beech mein ek LAAL CHAUKOR bana hai. Thermal detection THEEK
USI CHAUKOR ke andar aayi thi. Sirf uske ANDAR kya hai wo batao.

BAHUT ZAROORI: laal chaukor ke andar koi CHHOTI cheez ho sakti hai -
eent ka bhatta, factory ka shed, chimney, godown, paved yard - bhale hi
aas-paas door tak khet ya jungle ho. Aas-paas kya hai us se jawab MAT
do. Sirf chaukor ke andar dekho.

Eent ke bhatte aise dikhte hain: ek lambi oval ya aayat shakal, uske
paas ek chimney, aas-paas kacchi eent ke dher, aur nangi bhoori zameen.
Ye industrial hain, cropland nahi - chahe chaaron taraf khet hon.

{hint}

Dhyan rakhna:
- industrial: refinery, factory, power plant, bhatta, gol storage tank,
  chimney, bade shed, paved yard, kacchi zameen pe machine
- mine: khadaan, khuli khudai
- cropland: chaukor/aayat khet, seedhi medh ki lakeerein, jale hue kaale khet
- forest: ghane ped
- barren: khaali sookhi zameen, na khet na ped
- agar chaukor ke andar dhundhla ya badal hai to "unclear" kehna"""

# Jawab ka dhaancha - isse Gemini ka jawab HAMESHA valid JSON aata hai,
# "```json" jaisi galtiyan nahi hoti.
SCHEMA = {
    "type": "object",
    "properties": {
        "landuse": {"type": "string",
                    "enum": ["industrial", "mine", "forest", "cropland",
                             "urban", "water", "barren", "unclear"]},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["landuse", "confidence", "reason"],
}


def ask_gemini(client, types, chip_path, industry_name, dist, tries=4):
    """
    Ek photo Gemini ko bhejo. Jawab dict mein, ya None agar sach mein
    fail ho jaye.

    -----------------------------------------------------------------
    RETRY KYUN ZAROORI HAI (ye ek BUG ka fix hai):

    Pehle ek hi retry thi, aur uske baad source CHUP-CHAAP skip ho
    jata tha. Nateeja: 1,099 sources mein se sirf 410 hue, aur script
    ne "poora ho gaya" bol diya - kisi ko pata hi nahi chala ki 690
    reh gaye.

    Free tier pe rate limit (429) aana normal hai. Ab exponential
    backoff hai (10s, 20s, 40s) aur aakhir tak fail ho to WAPAS
    batate hain, chup nahi rehte.
    -----------------------------------------------------------------
    """
    hint = ""
    if industry_name and str(industry_name) != "nan":
        hint = HINT.format(name=industry_name, dist=dist)

    for attempt in range(tries):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=[
                    types.Part.from_bytes(data=chip_path.read_bytes(),
                                          mime_type="image/jpeg"),
                    GEMINI_PROMPT.format(hint=hint),
                ],
                config=types.GenerateContentConfig(
                    temperature=0,           # har baar wahi jawab
                    response_mime_type="application/json",
                    response_schema=SCHEMA,
                ),
            )
            return json.loads(resp.text)
        except Exception as e:
            msg = str(e)
            last = attempt == tries - 1
            if last:
                print(f"\n  {tries} koshishon ke baad bhi fail: {msg[:100]}")
                return None
            # 429 = rate limit -> zyada rukо. Baaki errors -> thoda rukо.
            wait = 10 * (2 ** attempt)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg.upper():
                wait = max(wait, 30)
            time.sleep(wait)
    return None


def load_done():
    """Pehle se ho chuke sources - taaki dobara paisa/time kharch na ho."""
    if OUT_CSV.exists():
        df = pd.read_csv(OUT_CSV)
        return df, set(df["source_id"])
    return pd.DataFrame(), set()


def run(client, types, todo, label_col=None):
    """todo ke har source pe Gemini chalao. Beech-beech mein save karo."""
    done_df, done_ids = load_done()
    todo = todo[~todo["source_id"].isin(done_ids)]
    print(f"  pehle se ho chuke : {len(done_ids)}")
    print(f"  ab karne hain     : {len(todo)}\n")
    if len(todo) == 0:
        return done_df

    rows = []
    skipped = {"chip": 0, "api": 0}
    consecutive_fail = 0
    for _, r in tqdm(todo.iterrows(), total=len(todo), desc="photos"):
        chip = download_chip(r["source_id"], r["lat"], r["lon"])
        if chip is None:
            skipped["chip"] += 1
            continue
        chip = add_center_mark(chip)      # beech mein laal chaukor

        ans = ask_gemini(client, types, chip, r["industry_name"],
                         r["dist_to_industry_m"])
        if not isinstance(ans, dict):
            skipped["api"] += 1
            consecutive_fail += 1
            if consecutive_fail >= STOP_AFTER_FAILS:
                print(f"\n\n  {STOP_AFTER_FAILS} sources LAGATAR fail huey.")
                print("  Lagta hai daily quota khatam ho gaya "
                      "(free tier ki roz ki limit).")
                print("  Kal dobara chalao - script wahin se aage le legi.")
                break
            continue
        consecutive_fail = 0

        row = {"source_id": r["source_id"],
               "vlm_landuse": ans["landuse"],
               "vlm_label": VLM_TO_LABEL.get(ans["landuse"], "UNSURE"),
               "vlm_confidence": ans["confidence"],
               "vlm_reason": str(ans["reason"])[:250]}
        if label_col:
            row[label_col] = r[label_col]
        rows.append(row)

        # har 10 pe save - Ctrl+C ya crash pe kaam na jaaye
        if len(rows) % 10 == 0:
            pd.concat([done_df, pd.DataFrame(rows)]).to_csv(OUT_CSV, index=False)

        time.sleep(SLEEP)

    out = pd.concat([done_df, pd.DataFrame(rows)], ignore_index=True)
    out.to_csv(OUT_CSV, index=False)

    # SKIP ki ginti batao - chup-chaap chhodna sabse bura hai
    if skipped["chip"] or skipped["api"]:
        print(f"\n  !! {skipped['chip'] + skipped['api']} sources SKIP huey "
              f"(photo nahi mili: {skipped['chip']}, API fail: {skipped['api']})")
        print("     Dobara chalao - script wahin se aage le legi.")
    return out


# ===============================================================
def validate(client, types, src, gold):
    """
    Paisa/time kharch karne se PEHLE naapo ki Gemini sahi bhi hai ya nahi.

    47 gold sources pe chalate hain - jinke labels INSAAN ne banaye the.
    Agar Gemini insaan se ~80% milti hai, to bade paimane pe chalana
    theek hai.
    """
    t = src[src["source_id"].isin(set(gold["source_id"]))].merge(
        gold[["source_id", "gold_label"]], on="source_id")

    print("=" * 70)
    print(f"VALIDATION - {len(t)} gold sources pe   (model: {MODEL})")
    print("=" * 70)
    print("\nSawaal: Gemini insaan se kitna milti hai?\n")

    df = run(client, types, t, label_col="gold_label")
    df = df[df["gold_label"].notna()] if "gold_label" in df else df
    if df.empty:
        sys.exit("!! koi jawab nahi aaya")

    # "UNSURE" ko galat ginna beimaani hoga - "pata nahi" kehna alag baat hai
    ans = df[df["vlm_label"] != "UNSURE"]
    acc = (ans["gold_label"] == ans["vlm_label"]).mean() if len(ans) else 0

    rules_row = src.set_index("source_id")["rule_label"]
    df["rule"] = df["source_id"].map(rules_row)
    ra = df[df["rule"] != "UNSURE"]
    racc = (ra["gold_label"] == ra["rule"]).mean() if len(ra) else 0

    silent = df[df["rule"] == "UNSURE"]
    sa = silent[silent["vlm_label"] != "UNSURE"]
    sacc = (sa["gold_label"] == sa["vlm_label"]).mean() if len(sa) else 0

    print("\n" + "=" * 70)
    print("NATEEJA")
    print("=" * 70)
    print(f"\n  Gemini ne jawab diya : {len(ans)}/{len(df)}"
          f"   ({len(df) - len(ans)} pe 'pata nahi' kaha)")
    print(f"  Gemini sahi          : {acc:.1%}")
    print(f"  RULES sahi (unhi pe) : {racc:.1%}   [{len(ra)} sources]")
    print(f"\n  >> Jahan RULES CHUP the ({len(silent)} sources):")
    print(f"       Gemini ne jawab diya : {len(sa)}")
    print(f"       Gemini sahi          : {sacc:.1%}")
    print("       (hamara model yahan 39% pe tha, tukka 33% hota hai)")

    if len(ans):
        print("\n  confusion (row=insaan, col=Gemini):")
        print(pd.crosstab(ans["gold_label"], ans["vlm_label"]).to_string())

    wrong = ans[ans["gold_label"] != ans["vlm_label"]]
    if len(wrong):
        print(f"\n  {len(wrong)} GALTIYAN:")
        for _, r in wrong.head(10).iterrows():
            print(f"    {r['source_id'][:28]:<30} insaan={r['gold_label']:<12}"
                  f" gemini={r['vlm_label']:<12} ({r['vlm_landuse']})")
            print(f"       \"{str(r['vlm_reason'])[:95]}\"")

    (OUTPUTS / "gemini_validation.json").write_text(json.dumps({
        "model": MODEL, "n": len(df), "n_answered": len(ans),
        "gemini_accuracy": float(acc), "rule_accuracy": float(racc),
        "rules_silent": {"n": len(silent), "n_answered": len(sa),
                         "gemini_accuracy": float(sacc)},
    }, indent=2, default=float))

    print("\n" + "-" * 70)
    if acc >= 0.80:
        print("FAISLA: Gemini bharosemand hai -> saare UNSURE pe chalao")
        print("        python src/step4d_gemini.py")
    elif acc >= 0.65:
        print("FAISLA: theek-thaak. Sirf high-confidence jawab lo,")
        print("        ya prompt sudhaar kar dobara naapo.")
    else:
        print("FAISLA: rules se behtar nahi. Pehle prompt/zoom sudhaaro.")
    print("-" * 70)


# ===============================================================
def main():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("ERROR: GEMINI_API_KEY nahi mili.\n")
        print("  1. Key lo (FREE, credit card nahi chahiye):")
        print("       https://aistudio.google.com/apikey")
        print("  2. .env mein ye line daalo:")
        print("       GEMINI_API_KEY=AIza...")
        sys.exit(1)

    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)

    src = gpd.read_file(DATA_PROCESSED / "sources_labelled.gpkg")

    if "--validate" in sys.argv:
        gold = pd.read_csv(DATA_PROCESSED / "gold_labels.csv")
        validate(client, types, src, gold)
        return

    # ---- asli kaam: wo sources jinpe rules chup hain ----
    todo = src[src["label"] == "UNSURE"].copy()
    if "--limit" in sys.argv:
        n = int(sys.argv[sys.argv.index("--limit") + 1])
        # sabse zyada dikhne wale pehle - unka asar sabse zyada hai
        todo = todo.nlargest(n, "n_detections")

    print("=" * 70)
    print(f"GEMINI LABELLING   (model: {MODEL}, {RPM} req/min)")
    print("=" * 70)
    print(f"\nrules ne {(src['label'] == 'UNSURE').sum():,} sources pe "
          f"haath khade kar diye the")
    print(f"lagbhag time: {len(todo) * SLEEP / 3600:.1f} ghante\n")

    df = run(client, types, todo)

    print(f"\n{len(df):,} sources pe jawab mila")
    print(f"SAVED: {OUT_CSV}\n")
    print("Gemini ne photo mein kya dekha:")
    print(df["vlm_landuse"].value_counts().to_string())
    print("\nhamare labels mein badla:")
    print(df["vlm_label"].value_counts().to_string())
    print("\nAgla step: python src/step5_train.py  (ab naye labels ke saath)")


if __name__ == "__main__":
    main()
