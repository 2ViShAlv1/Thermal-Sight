"""
Poora project ek command mein jaancho.

    python verify.py

Har cheez pe PASS / FAIL likhta hai. Demo se pehle chalao - agar sab
PASS hai to project chalne ke liye taiyaar hai.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import geopandas as gpd
import pandas as pd

from config import DATA_PROCESSED, MODELS, OUTPUTS

OK, BAD = [], []


def check(name, condition, detail=""):
    (OK if condition else BAD).append(name)
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {name}" + (f"   {detail}" if detail else ""))
    return condition


def main():
    print("=" * 70)
    print("PROJECT VERIFICATION")
    print("=" * 70)

    # ---------------------------------------------------------------
    print("\n0. LIBRARIES")
    # Demo wale din "ModuleNotFoundError" se bura kuch nahi hota.
    # ---------------------------------------------------------------
    import importlib
    for mod in ["geopandas", "pandas", "shapely", "pyogrio", "rasterio",
                "sklearn", "xgboost", "shap", "joblib", "streamlit", "folium",
                "streamlit_folium", "matplotlib", "requests", "dotenv", "tqdm"]:
        try:
            importlib.import_module(mod)
            check(mod, True)
        except Exception as e:
            check(mod, False, str(e)[:50])

    # ---------------------------------------------------------------
    print("\n1. FILES")
    # ---------------------------------------------------------------
    files = {
        "hotspots.gpkg":         DATA_PROCESSED / "hotspots.gpkg",
        "features.gpkg":         DATA_PROCESSED / "features.gpkg",
        "sources.gpkg":          DATA_PROCESSED / "sources.gpkg",
        "detections.gpkg":       DATA_PROCESSED / "detections.gpkg",
        "sources_labelled.gpkg": DATA_PROCESSED / "sources_labelled.gpkg",
        "predictions.gpkg":      DATA_PROCESSED / "predictions.gpkg",
        "gold_labels.csv":       DATA_PROCESSED / "gold_labels.csv",
        "model.pkl":             MODELS / "model.pkl",
    }
    for name, path in files.items():
        check(f"{name} maujood", path.exists(),
              f"{path.stat().st_size/1e6:.1f} MB" if path.exists() else "")

    if BAD:
        print("\n!! kuch files missing hain - pehle 'python run_all.py' chalao")
        return report()

    # ---------------------------------------------------------------
    print("\n2. DATA")
    # ---------------------------------------------------------------
    hot = gpd.read_file(DATA_PROCESSED / "hotspots.gpkg")
    det = gpd.read_file(DATA_PROCESSED / "detections.gpkg", layer="detections")
    src = gpd.read_file(DATA_PROCESSED / "sources_labelled.gpkg")
    pred = gpd.read_file(DATA_PROCESSED / "predictions.gpkg")
    gold = pd.read_csv(DATA_PROCESSED / "gold_labels.csv")

    check("detections khoye nahi", src["n_detections"].sum() == len(det),
          f"{src['n_detections'].sum():,} == {len(det):,}")
    check("sources == predictions", len(src) == len(pred), f"{len(src):,}")
    check("3 satellites", hot["satellite"].nunique() == 3,
          ", ".join(sorted(hot["satellite"].unique())))
    check("5 regions", src["region"].nunique() == 5,
          ", ".join(sorted(src["region"].unique())))
    check("poora saal 2025",
          hot["acq_date"].min() <= "2025-01-05" and hot["acq_date"].max() >= "2025-12-25",
          f"{hot['acq_date'].min()} -> {hot['acq_date'].max()}")

    # landcover - yahi wo cheez thi jo pehle 78% 'unknown' thi
    unknown = (src["lc_class"] == "unknown").sum()
    check("landcover bhara hua", unknown == 0, f"unknown: {unknown}")

    # koi khaali feature nahi
    feats = ["n_detections", "n_days", "lifespan_days", "night_ratio",
             "frp_mean", "frp_median", "frp_max", "frp_std",
             "n_months", "peak_month", "dist_to_industry_m", "lc_class"]
    nulls = int(src[feats].isna().sum().sum())
    check("koi feature khaali nahi", nulls == 0, f"nulls: {nulls}")

    # ---------------------------------------------------------------
    print("\n3. LABELS")
    # ---------------------------------------------------------------
    lab = src["label"].value_counts()
    for cls in ["INDUSTRIAL", "FOREST_FIRE", "AGRI_BURN"]:
        check(f"{cls} ke udaharan hain", lab.get(cls, 0) > 0, f"{lab.get(cls, 0):,}")

    # -----------------------------------------------------------
    # Sabse zaroori sanity check: jo INDUSTRIAL kaha, wo sach mein
    # factory ke paas hona chahiye.
    #
    # DHYAN: ye check SIRF rules wale labels pe lagta hai. Wajah saaf
    # hai - rule kehta hi yahi hai "1 km ke andar", to uspe ye check
    # lagana matlab rule ko apne hi se naapna. VLM wale labels PHOTO
    # se aaye hain, doori se nahi; unpe ye shart lagana galat hoga.
    # Dono ko mila kar naapoge to pata hi nahi chalega ki kaunsi
    # tarah ke labels mein gadbad hai.
    # -----------------------------------------------------------
    ind = src[src["label"] == "INDUSTRIAL"]
    src_col = src["label_source"] if "label_source" in src.columns else None
    ind_rule = ind[ind["label_source"] == "rule"] if src_col is not None else ind
    near = (ind_rule["dist_to_industry_m"] < 1000).mean() if len(ind_rule) else 0
    check("rules wale INDUSTRIAL factory ke paas hain", near > 0.9,
          f"{near:.0%} < 1 km  ({len(ind_rule)} sources)")

    # aur FOREST_FIRE jungle mein - yahan bhi wahi baat
    fire = src[src["label"] == "FOREST_FIRE"]
    fire_rule = fire[fire["label_source"] == "rule"] if src_col is not None else fire
    inforest = (fire_rule["lc_class"] == "forest").mean() if len(fire_rule) else 0
    check("rules wale FOREST_FIRE jungle mein hain", inforest > 0.9,
          f"{inforest:.0%} forest  ({len(fire_rule)} sources)")

    if src_col is not None:
        print("\n     label kahan se aaya:")
        for s, n in src["label_source"].value_counts().items():
            print(f"         {str(s):<8}{n:>7,}")

    # ---------------------------------------------------------------
    print("\n4. GOLD LABELS (insaan ke banaye)")
    # ---------------------------------------------------------------
    merged = src[src["source_id"].isin(set(gold["source_id"]))]
    check("gold sources mil rahe hain", len(merged) == len(gold),
          f"{len(merged)}/{len(gold)}")

    g = merged.merge(gold[["source_id", "gold_label"]], on="source_id")
    answered = g[g["rule_label"] != "UNSURE"]
    acc = (answered["gold_label"] == answered["rule_label"]).mean() if len(answered) else 0
    check("rules insaan se milte hain", acc >= 0.70,
          f"{acc:.1%} sahi ({len(answered)} pe jawab diya, "
          f"{len(g) - len(answered)} pe chup)")

    # ---------------------------------------------------------------
    print("\n5. MODEL")
    # ---------------------------------------------------------------
    import joblib
    bundle = joblib.load(MODELS / "model.pkl")
    check("model load hua", "model" in bundle and "features" in bundle,
          f"{len(bundle.get('features', []))} features")

    # feature order - ye wo bug hai jo chupchaap galat jawab deta hai
    check("feature list saved hai", len(bundle.get("features", [])) > 0,
          "predict ke waqt order check ho sakta hai")

    check("confidence har source pe hai", pred["confidence"].notna().all(),
          f"{pred['confidence'].min():.2f} - {pred['confidence'].max():.2f}")

    # ---------------------------------------------------------------
    print("\n6. NASA SE SWATANTRA VALIDATION")
    # FIRMS har detection pe apna classification deta hai (firms_type):
    #   0 = vegetation fire, 2 = other STATIC land source (= industrial)
    #
    # Ye NASA ka apna faisla hai. Hamare rules ne ye field KABHI DEKHA
    # HI NAHI - wo sirf OSM ki doori, night_ratio aur persistence dekhte
    # hain. To agar dono ka jawab milta hai, wo ek ASLI validation hai -
    # hamare 45 gold labels se kahin mazboot, kyunki ye bahar se aaya hai.
    # ---------------------------------------------------------------
    if "static_ratio" in src.columns:
        nasa = src[src["static_ratio"] > 0]
        agree = (nasa["label"] == "INDUSTRIAL").mean() if len(nasa) else 0
        check("NASA ke 'static' sources humne bhi INDUSTRIAL kahe",
              len(nasa) > 0 and agree >= 0.9,
              f"{int((nasa['label'] == 'INDUSTRIAL').sum())}/{len(nasa)} = {agree:.0%}"
              f"  ({int(nasa['n_detections'].sum()):,} detections)")
    else:
        check("static_ratio column maujood", False, "step3 dobara chalao")

    # ---------------------------------------------------------------
    print("\n7. NASA-LABEL MODEL (step7 - circularity ka ilaaj)")
    #
    # step5 ka model hamare RULES ke banaye labels pe train hota hai,
    # aur usse WAHI features milte hain jo rules dekhte hain. Isliye
    # uska 0.997 "nakal" hai, "samajh" nahi.
    #
    # step7 ka model NASA ke apne firms_type pe train hota hai aur usme
    # ek bhi rule wala feature nahi hai. Agar wo phir bhi hamare INSAAN
    # ke gold labels se milta hai, to wo asli swatantra sabooot hai.
    # ---------------------------------------------------------------
    nasa_metrics = OUTPUTS / "nasa_metrics.json"
    if check("nasa_metrics.json maujood", nasa_metrics.exists(),
             "" if nasa_metrics.exists() else "chalao: python src/step7_nasa_model.py"):
        import json
        nm = json.loads(nasa_metrics.read_text())   # NaN nahi hona chahiye

        check("nasa_model.pkl maujood", (MODELS / "nasa_model.pkl").exists())

        rule_feats = {"lc_class", "dist_to_industry_m", "persistence_tier"}
        leaked = rule_feats.intersection(nm.get("features", []))
        check("step7 mein koi rule wala feature nahi", not leaked,
              f"{len(nm.get('features', []))} features, leak: {leaked or 'koi nahi'}")

        vs = nm.get("vs_human_labels") or {}
        check("NASA-label model insaan se milta hai",
              vs.get("auc", 0) >= 0.70,
              f"AUC {vs.get('auc', 0):.3f}, accuracy {vs.get('accuracy', 0):.1%} "
              f"({vs.get('n', 0)} gold sources)")

    # ---------------------------------------------------------------
    print("\n8. VLM (satellite photo dekhne wali AI)")
    #
    # Ye step OPTIONAL hai - API key ke bina project poora chalta hai,
    # bas labels sirf rules se aayenge. Isliye yahan "file nahi mili"
    # FAIL nahi hai, sirf ek soochna hai.
    #
    # Par agar VLM chala hai, to do cheezein PAKKI honi chahiye:
    #   1. usne gold sources ko haath na lagaya ho (warna imtihaan ka
    #      paper hi badal gaya)
    #   2. usne SIRF UNSURE sources pe label lagaya ho, rules ke upar
    #      na baitha ho
    # ---------------------------------------------------------------
    import json
    vlm_json = OUTPUTS / "gemini_validation.json"
    if not vlm_json.exists():
        print("     [skip] gemini_validation.json nahi mili - VLM chalaya "
              "nahi gaya (optional hai)")
        print("            chalao: python src/step4d_gemini.py --validate")
    else:
        vm = json.loads(vlm_json.read_text())
        acc = vm.get("gemini_accuracy", 0)
        racc = vm.get("rule_accuracy", 0)
        check("VLM insaan ke labels se milta hai", acc >= 0.70,
              f"{acc:.1%} sahi ({vm.get('n_answered', 0)}/{vm.get('n', 0)} pe "
              f"jawab diya)")
        check("VLM rules se behtar hai", acc >= racc,
              f"VLM {acc:.1%} vs rules {racc:.1%}")

        if "label_source" in src.columns:
            vlm_rows = src[src["label_source"] == "vlm"]
            check("VLM ne kuch sources pe label lagaya", len(vlm_rows) > 0,
                  f"{len(vlm_rows)} sources")

            # LEAKAGE: gold pe VLM ka label nahi hona chahiye
            gold_ids = set(gold["source_id"])
            leaked = vlm_rows["source_id"].isin(gold_ids).sum()
            check("VLM ne gold labels ko haath nahi lagaya", leaked == 0,
                  f"{leaked} gold sources pe VLM ka label" if leaked
                  else "imtihaan ka paper saaf hai")

            # VLM sirf wahan bola jahan rules chup the
            over = (vlm_rows["rule_label"] != "UNSURE").sum()
            check("VLM rules ke upar nahi baitha", over == 0,
                  f"{over} sources pe rule tha aur VLM ne badal diya" if over
                  else "sirf UNSURE sources pe")

    # ---------------------------------------------------------------
    print("\n9. ASLI FACTORY KE NAAM  (project kaam kar raha hai iska sabooot)")
    # ---------------------------------------------------------------
    named = src[(src["label"] == "INDUSTRIAL") & src["industry_name"].notna()]
    check("asli industry ke naam mile", len(named) > 0, f"{len(named)} sources")
    if len(named):
        top = named.nlargest(5, "n_detections")
        for _, r in top.iterrows():
            print(f"         {str(r['industry_name'])[:34]:<36}"
                  f"{r['n_detections']:>4} baar, raat {r['night_ratio']:.0%}")

    return report()


def report():
    print("\n" + "=" * 70)
    if BAD:
        print(f"{len(OK)} PASS, {len(BAD)} FAIL")
        print("\nFAIL huey:")
        for b in BAD:
            print(f"   - {b}")
        return 1
    print(f"SAB {len(OK)} CHECKS PASS - project chalne ke liye taiyaar hai")
    print("\nAgla: streamlit run app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
