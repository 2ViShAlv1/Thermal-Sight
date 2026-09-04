"""
STEP 4c - VLM ko naapna, uspe bharosa karne se PEHLE.

Kyun ye script hai:
    Phase 4 mein pata chala ki model rules ki nakal utaar raha hai
    (100% ek jaisa jawab), kyunki training labels bhi rules ne hi
    banaye the. Usme koi nayi jaankari thi hi nahi.

    Iska ilaaj VLM hai - wo PHOTO dekh kar batati hai, rules se azaad.
    Par 8,000 sources pe chalane se pehle ye jaanna zaroori hai ki
    VLM sach mein sahi bhi hai ya nahi.

    Isliye usse tumhare 47 gold labels pe chalate hain - jo INSAAN ne
    banaye the. Agar VLM insaan se ~85% milti hai, to bade paimane pe
    chalana theek hai. Agar 60% pe atki, to wo rules se behtar nahi
    aur paisa barbaad hoga.

Ye 47 API calls hain - sasta test, bada faisla.

Output: outputs/vlm_validation.json
        data/chips/<source_id>.jpg

Chalane ka tareeka:
    python src/step4c_vlm_validate.py
"""
import json
import os
import sys

import geopandas as gpd
import pandas as pd
from tqdm import tqdm

from config import DATA_PROCESSED, OUTPUTS, VLM_MODEL
from step4b_vlm import download_chip, ask_claude, VLM_TO_LABEL


def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ERROR: ANTHROPIC_API_KEY nahi mili (.env dekho)")

    import anthropic
    client = anthropic.Anthropic()

    src = gpd.read_file(DATA_PROCESSED / "sources_labelled.gpkg")
    gold = pd.read_csv(DATA_PROCESSED / "gold_labels.csv")
    t = src[src["source_id"].isin(set(gold["source_id"]))].merge(
        gold[["source_id", "gold_label"]], on="source_id")

    print("=" * 68)
    print(f"VLM VALIDATION - {len(t)} gold sources pe  (model: {VLM_MODEL})")
    print("=" * 68)
    print("\nSawaal: VLM insaan se kitna milti hai?\n")

    rows = []
    for _, r in tqdm(t.iterrows(), total=len(t), desc="photos"):
        chip = download_chip(r["source_id"], r["lat"], r["lon"])
        if chip is None:
            continue
        ans = ask_claude(client, chip, r["industry_name"],
                         r["dist_to_industry_m"])
        if ans is None:
            continue
        rows.append({
            "source_id": r["source_id"],
            "gold": r["gold_label"],
            "rule": r["rule_label"],
            # VLM ka landuse -> hamari 3 classes mein. urban/water/barren/
            # unclear ka koi label nahi banta - wo "UNSURE" rehte hain.
            "vlm": VLM_TO_LABEL.get(ans["landuse"], "UNSURE"),
            "vlm_landuse": ans["landuse"],
            "vlm_conf": ans["confidence"],
            "reason": ans["reason"][:200],
        })

    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("!! ek bhi jawab nahi aaya")

    # ---- scores ----
    # "answered" = jinpe VLM ne koi 3 classes wala jawab diya.
    # UNSURE ko galat ginna beimaani hogi - "pata nahi" kehna alag baat hai.
    ans_df = df[df["vlm"] != "UNSURE"]
    vlm_acc = (ans_df["gold"] == ans_df["vlm"]).mean() if len(ans_df) else 0.0

    rule_df = df[df["rule"] != "UNSURE"]
    rule_acc = (rule_df["gold"] == rule_df["rule"]).mean() if len(rule_df) else 0.0

    # sabse zaroori: jahan RULES chup the, wahan VLM ne kya kiya?
    # Yahi wo 1,099 sources hain jinke liye ye poori kawayad hai.
    silent = df[df["rule"] == "UNSURE"]
    silent_ans = silent[silent["vlm"] != "UNSURE"]
    silent_acc = (silent_ans["gold"] == silent_ans["vlm"]).mean() if len(silent_ans) else 0.0

    print("\n" + "=" * 68)
    print("NATEEJA")
    print("=" * 68)
    print(f"\n  VLM ne jawab diya      : {len(ans_df)}/{len(df)}"
          f"   ({len(df) - len(ans_df)} pe 'pata nahi' kaha)")
    print(f"  VLM sahi               : {vlm_acc:.1%}")
    print(f"  RULES sahi (unhi pe)   : {rule_acc:.1%}   [{len(rule_df)} sources]")

    print(f"\n  >> Jahan RULES CHUP the ({len(silent)} sources):")
    print(f"       VLM ne jawab diya : {len(silent_ans)}")
    print(f"       VLM sahi          : {silent_acc:.1%}")
    print("       (model yahan 38.9% pe tha - tukka 33% hota hai)")

    print("\n  class-wise (jahan VLM ne jawab diya):")
    if len(ans_df):
        ct = pd.crosstab(ans_df["gold"], ans_df["vlm"])
        print(ct.to_string())

    print("\n  VLM ne photo mein kya dekha:")
    print(df["vlm_landuse"].value_counts().to_string())

    # ---- galtiyan dikhao - inhi se pata chalta hai kya sudhaarna hai ----
    wrong = ans_df[ans_df["gold"] != ans_df["vlm"]]
    if len(wrong):
        print(f"\n  {len(wrong)} GALTIYAN:")
        for _, r in wrong.head(10).iterrows():
            print(f"    {r['source_id'][:28]:<30} gold={r['gold']:<12} "
                  f"vlm={r['vlm']:<12} ({r['vlm_landuse']}, {r['vlm_conf']:.2f})")
            print(f"       \"{r['reason'][:100]}\"")

    out = {
        "n": len(df),
        "n_answered": len(ans_df),
        "vlm_accuracy": float(vlm_acc),
        "rule_accuracy": float(rule_acc),
        "rules_silent": {"n": len(silent), "n_answered": len(silent_ans),
                         "vlm_accuracy": float(silent_acc)},
        "rows": rows,
    }
    (OUTPUTS / "vlm_validation.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"\nsaved: outputs/vlm_validation.json")

    # ---- faisla ----
    print("\n" + "-" * 68)
    if vlm_acc >= 0.80:
        print("FAISLA: VLM bharosemand hai -> bade paimane pe chalao")
    elif vlm_acc >= 0.65:
        print("FAISLA: VLM theek-thaak hai. Sirf HIGH confidence wale jawab lo,")
        print("        ya prompt sudhaar kar dobara naapo.")
    else:
        print("FAISLA: VLM rules se behtar nahi. Paisa mat kharcho -")
        print("        pehle prompt/zoom sudhaaro, phir dobara naapo.")
    print("-" * 68)


if __name__ == "__main__":
    main()
