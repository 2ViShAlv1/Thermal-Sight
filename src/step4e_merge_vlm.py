"""
STEP 4e - VLM ke jawab ko pipeline mein JODNA.

KYUN YE FILE BANI:
    step4d_gemini.py ne 455 sources pe satellite photo dekh kar jawab
    diya aur wo gemini_labels.csv mein pada tha - par use koi PADH hi
    nahi raha tha. Na step5_train, na app.py, na verify.py.

    Yani 455 API calls ka kaam disk pe pada tha aur project pe uska
    ASAR ZERO tha. Ye file wahi jodti hai.

KYA JODA JATA HAI (aur kya JAAN-BOOJH KAR nahi):

  1. SIRF UNSURE sources pe VLM ka label lagta hai.
     Jahan rules ne pehle hi jawab de diya, wahan VLM ko upar nahi
     bithate. Wajah: rules gold pe 76% sahi the, VLM 81% - farak itna
     bada nahi ki pehle se kaam kar rahe labels ukhaad diye jayein.
     Jahan rules CHUP the, wahan VLM ke alawa kuch hai hi nahi - wahi
     asli faayda hai.

  2. GOLD sources ko HAATH NAHI LAGATE.
     45 gold labels INSAAN ne banaye hain aur wahi hamara imtihaan
     hai. gemini_labels.csv mein wo 45 bhi hain (--validate se aaye
     the). Agar unpe VLM ka label chadha diya to imtihaan ka paper
     hi badal jayega - score jhootha zyada aayega.
     step5_train bhi gold ko training se hatata hai, par yahan bhi
     rok lagana zaroori hai - do taale ek se behtar hain.

  3. JAHAN VLM aur RULES ALAG BOLE, wo alag se nishaan-zada hote hain
     (vlm_conflict). Ye label nahi badalte - par yahi wo mutthi bhar
     sources hain jinpe insaan ki nazar sabse zyada kaam ki hai.

Input : data/processed/sources_labelled.gpkg
        data/processed/gemini_labels.csv     (step4d se)
        data/processed/gold_labels.csv       (bachane ke liye)

Output: wahi sources_labelled.gpkg, ab in naye columns ke saath:
        vlm_landuse / vlm_confidence / vlm_reason / vlm_conflict
        aur UNSURE sources pe bhara hua label (label_source = "vlm")

Chalane ka tareeka:
    python src/step4e_merge_vlm.py
    python src/step4e_merge_vlm.py --dry-run    # sirf dikhao, likho mat
"""
import sys

import geopandas as gpd
import pandas as pd

from config import DATA_PROCESSED, CLASSES

VLM_CSV = DATA_PROCESSED / "gemini_labels.csv"
SRC_GPKG = DATA_PROCESSED / "sources_labelled.gpkg"
GOLD_CSV = DATA_PROCESSED / "gold_labels.csv"

# VLM ke jawab ke naye columns
VLM_COLS = ["vlm_landuse", "vlm_confidence", "vlm_reason"]


def main():
    dry = "--dry-run" in sys.argv

    if not VLM_CSV.exists():
        print(f"ERROR: {VLM_CSV.name} nahi mili.")
        print("  pehle ye chalao: python src/step4d_gemini.py --validate")
        print("               phir: python src/step4d_gemini.py")
        sys.exit(1)
    if not SRC_GPKG.exists():
        print("ERROR: sources_labelled.gpkg nahi mili.")
        print("  pehle ye chalao: python src/step4_labels.py")
        sys.exit(1)

    src = gpd.read_file(SRC_GPKG)
    vlm = pd.read_csv(VLM_CSV)
    gold_ids = set(pd.read_csv(GOLD_CSV)["source_id"]) if GOLD_CSV.exists() else set()

    print("=" * 68)
    print("VLM KE JAWAB JODNA")
    print("=" * 68)
    print(f"\n  sources        : {len(src):,}")
    print(f"  VLM ke jawab   : {len(vlm):,}")
    print(f"  gold (bachane) : {len(gold_ids)}")

    # ---- ek source pe do jawab? aakhri wala lo ----
    # (script rok kar dobara chalane pe duplicate ban sakte hain)
    before = len(vlm)
    vlm = vlm.drop_duplicates(subset="source_id", keep="last")
    if len(vlm) < before:
        print(f"  {before - len(vlm)} duplicate jawab the - aakhri wala liya")

    # ---- naye columns banao (pehli baar chalne pe) ----
    #
    # BUG jo yahan tha: vlm_confidence ko `None` se shuru karne se
    # column "object" dtype ban jata hai. Baad mein usmein float
    # (0.95 jaisa) daalo to pandas ANDAR se to float rakhta hai, par
    # GPKG (GeoPackage) mein likhte waqt driver poore column ko ek hi
    # type dena chahta hai - yahan usne "object" dekh kar TEXT chun
    # liya. Nateeja: 455 rows mein confidence "0.95" (STRING) ban gaya,
    # baaki 17,160 NaN (float) rahe - EK HI column mein DO alag types.
    # Isse frontend mein .toFixed() crash hota hai kyunki string pe
    # wo function hai hi nahi.
    #
    # Fix: shuru se hi float64 NaN rakho, kabhi object None nahi.
    # Aur agar column pehle se (purani buggy run se) maujood hai to
    # use bhi saaf kar do - warna purana data hamesha kharab rahega.
    for col in VLM_COLS:
        if col == "vlm_confidence":
            if col in src.columns:
                src[col] = pd.to_numeric(src[col], errors="coerce")
            else:
                src[col] = pd.Series(float("nan"), index=src.index, dtype="float64")
        elif col not in src.columns:
            src[col] = None
    if "vlm_conflict" not in src.columns:
        src["vlm_conflict"] = False

    # source_id se jodne ke liye index
    src = src.set_index("source_id", drop=False)
    vlm = vlm.set_index("source_id")

    # sirf wahi jawab jinka source hamare paas hai
    common = src.index.intersection(vlm.index)
    print(f"  dono mein mile : {len(common):,}")
    if len(common) == 0:
        sys.exit("!! ek bhi source match nahi hua - source_id dekho")

    # ---- VLM ka kaccha jawab har jagah rakh do (label badle ya na badle) ----
    # Ye dashboard ke liye hai: "AI ne photo mein kya dekha aur kyun".
    for col in VLM_COLS:
        if col in vlm.columns:
            src.loc[common, col] = vlm.loc[common, col]

    # ---- ab decide karo kispe label BADLEGA ----
    is_gold = src.index.isin(gold_ids)
    is_unsure = src["label"] == "UNSURE"
    vlm_label = pd.Series(index=src.index, dtype=object)
    vlm_label.loc[common] = vlm.loc[common, "vlm_label"]
    vlm_said_class = vlm_label.isin(CLASSES)      # UNSURE/NaN yahan chhoot jate hain

    fill = is_unsure & vlm_said_class & ~is_gold
    # jahan rules bol chuke the aur VLM ne kuch AUR kaha - sirf nishaan
    conflict = (~is_unsure) & vlm_said_class & ~is_gold & (src["label"] != vlm_label)

    # ---- report BEFORE ----
    print("\n" + "-" * 68)
    print("PEHLE (sirf rules):")
    print("-" * 68)
    before_counts = src["label"].value_counts()
    for name in CLASSES + ["UNSURE"]:
        print(f"  {name:<14} {before_counts.get(name, 0):>6}")

    print("\n" + "-" * 68)
    print("VLM NE KYA JODA:")
    print("-" * 68)
    print(f"  UNSURE the, ab label mila : {int(fill.sum()):>6}")
    if fill.any():
        for landuse, n in src.loc[fill, "vlm_landuse"].value_counts().items():
            print(f"      {landuse:<12} {n:>5}")
    skipped_gold = int((is_gold & vlm_said_class).sum())
    skipped_unclear = int((is_unsure & src.index.isin(common) & ~vlm_said_class).sum())
    print(f"  gold the, chhode gaye     : {skipped_gold:>6}   (imtihaan ka paper)")
    print(f"  VLM ne 'pata nahi' kaha   : {skipped_unclear:>6}   (UNSURE hi rahe)")
    print(f"  rules se TAKRAAV          : {int(conflict.sum()):>6}   "
          f"(label nahi badla, sirf nishaan)")

    # naye labels - dry-run mein bhi ginti dikhane ke liye alag se
    projected = src["label"].copy()
    projected[fill] = vlm_label[fill]

    if not dry:
        src.loc[fill, "label"] = vlm_label[fill]
        src.loc[fill, "label_source"] = "vlm"
        # jinpe jawab mil gaya unhe review queue se hata do -
        # ab unpe AI ki nazar pad chuki hai
        src.loc[fill, "needs_review"] = False
        src.loc[conflict, "vlm_conflict"] = True
        # takraav wale wapas review queue mein - yahi sabse kaam ke hain
        src.loc[conflict, "needs_review"] = True

    # ---- report AFTER ----
    print("\n" + "-" * 68)
    print("AB (rules + VLM):")
    print("-" * 68)
    after_counts = projected.value_counts()
    for name in CLASSES + ["UNSURE"]:
        b, a = before_counts.get(name, 0), after_counts.get(name, 0)
        d = a - b
        arrow = f"  ({d:+,})" if d else ""
        print(f"  {name:<14} {a:>6}{arrow}")

    n_ind_b = before_counts.get("INDUSTRIAL", 0)
    n_ind_a = after_counts.get("INDUSTRIAL", 0)
    if n_ind_b and n_ind_a > n_ind_b:
        print(f"\n  >> INDUSTRIAL {100 * (n_ind_a / n_ind_b - 1):.0f}% badhe - "
              f"yahi sabse kam data wali class thi")

    n_unsure_b = before_counts.get("UNSURE", 0)
    n_unsure_a = after_counts.get("UNSURE", 0)
    if n_unsure_b:
        print(f"  >> review queue {n_unsure_b:,} se {n_unsure_a:,} pe aayi "
              f"({100 * (1 - n_unsure_a / n_unsure_b):.0f}% kam)")

    # ---- takraav ki misaalein - inhi se pata chalta hai kaun galat hai ----
    if conflict.any():
        print("\n  TAKRAAV ki misaalein (rules vs AI):")
        for sid, r in src[conflict].head(5).iterrows():
            print(f"    {sid[:30]:<32} rule={r['label']:<12} "
                  f"AI={r['vlm_landuse']} ({r['vlm_confidence']:.2f})")
            print(f"       \"{str(r['vlm_reason'])[:88]}\"")

    if dry:
        print("\n--dry-run tha, kuch likha nahi gaya.")
        return

    # ---- save ----
    src = src.reset_index(drop=True)
    src.to_file(SRC_GPKG, driver="GPKG")
    print(f"\nSAVED: {SRC_GPKG}")
    print("\nAgla step: python src/step5_train.py   (ab naye labels ke saath)")


if __name__ == "__main__":
    main()
