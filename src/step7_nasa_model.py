"""
STEP 7 - NASA ke apne labels pe model.   <<< CIRCULARITY KA ILAAJ

PROBLEM JISKA YE JAWAB HAI:
    step5 ka model 0.997 deta hai par wo NAKAL hai. Wajah saaf hai:

        labels   = f(lc_class, dist_to_industry, persistence_tier)
        features = lc_class, dist_to_industry, persistence_tier

    Model ko jawab bhi mila aur jis cheez se jawab bana wo bhi. Usne
    bas hamari likhi hui shartein dohra di. Ablation isse sabit karta
    hai: wo features hatate hi score 0.997 se 0.445 pe gir jata hai.

ISKA ILAAJ - ek hi asool:
    LABELS aise source se aayein jo model ke features se nikal na sakein.

    FIRMS har detection pe apna classification deta hai:
        type = 0  presumed vegetation fire
        type = 2  other static land source   (yani industrial)

    Ye NASA ka apna faisla hai - hamare rules se bilkul azaad. Aur ye
    59,078 labelled detections deta hai, jabki hamare paas insaan ke
    banaye sirf 45 the.

        type=0 : 46,847      type=2 : 12,231      imbalance sirf 3.8x
        (hamare INDUSTRIAL class ka imbalance 84x hai)

YE MODEL DETECTION-LEVEL HAI, source-level nahi:
    Har ek detection ko akele dekh kar batata hai ki wo aag hai ya
    chalti hui machine. Iska ek asli faayda hai - source-level model
    ko MAHINON ka data chahiye (persistence naapne ke liye), ye PEHLI
    detection pe hi jawab de deta hai.

Input : data/processed/detections.gpkg
Output: models/nasa_model.pkl
        outputs/nasa_metrics.json
        outputs/nasa_confusion.png

Chalane ka tareeka:
    python src/step7_nasa_model.py
"""
import json
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import joblib
from xgboost import XGBClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import (classification_report, confusion_matrix,
                             f1_score, accuracy_score, roc_auc_score)

from config import DATA_PROCESSED, MODELS, OUTPUTS

# ---------------------------------------------------------------
# FEATURES - sirf wo jo FIRMS ek AKELI detection pe deta hai.
#
# Yahan jaan-boojh kar koi bhi rule wala feature NAHI hai - na
# lc_class, na dist_to_industry, na persistence_tier. Warna wahi
# circularity wapas aa jayegi.
# ---------------------------------------------------------------
FEATURES = [
    "frp",           # fire radiative power (MW)
    "bright_ti4",    # I4 band temperature (K) - aag mein zyada
    "bright_ti5",    # I5 band temperature (K)
    "ti_diff",       # ti4 - ti5. Gas flare pehchanne ka jaana-maana tareeka:
                     # flare mein I4 saturate hota hai, farak bada aata hai
    "is_night",      # raat ki detection hai?
    "scan",          # pixel ka size - swath ke kinare pe bada hota hai
    "track",
    "conf_high",     # NASA ka apna confidence flag
    "conf_low",
    "month",         # mausam - aag mausami hoti hai, machine nahi
]


def build(det):
    """detections.gpkg -> model ke liye X, y, groups."""
    d = det[det["firms_type"].isin([0, 2])].copy()

    d["ti_diff"] = d["bright_ti4"] - d["bright_ti5"]
    d["is_night"] = (d["daynight"] == "N").astype(int)
    d["conf_high"] = (d["confidence"] == "h").astype(int)
    d["conf_low"] = (d["confidence"] == "l").astype(int)
    d["month"] = pd.to_datetime(d["acq_date"]).dt.month

    # y = 1 matlab "static land source" (industrial), 0 matlab aag
    y = (d["firms_type"] == 2).astype(int).values
    return d[FEATURES], y, d["region"], d


def make_model(n=400, pos_weight=1.0):
    return XGBClassifier(
        n_estimators=n, max_depth=6, learning_rate=0.08,
        subsample=0.85, colsample_bytree=0.85,
        scale_pos_weight=pos_weight,     # 3.8x imbalance ka ilaaj
        objective="binary:logistic", eval_metric="logloss",
        n_jobs=-1, random_state=42, tree_method="hist")


def main():
    path = DATA_PROCESSED / "detections.gpkg"
    if not path.exists():
        sys.exit("detections.gpkg nahi mili - pehle run_all.py chalao")

    det = gpd.read_file(path, layer="detections")
    if "firms_type" not in det.columns:
        sys.exit("firms_type column nahi hai - step1_download.py dobara chalao")

    X, y, groups, d = build(det)
    pos_w = (y == 0).sum() / max((y == 1).sum(), 1)

    print("=" * 68)
    print("STEP 7 - NASA KE APNE LABELS PE MODEL")
    print("=" * 68)
    print(f"\n  labelled detections : {len(X):,}")
    print(f"    type=0 (aag)      : {int((y == 0).sum()):,}")
    print(f"    type=2 (static)   : {int((y == 1).sum()):,}")
    print(f"    imbalance         : {pos_w:.1f}x")
    print(f"  features            : {len(FEATURES)}  (koi rule wala feature nahi)")

    # -----------------------------------------------------------
    # REGION HOLD-OUT - yahi asli imtihaan hai.
    #
    # type=2 lagbhag poora Korba/Singrauli mein hai (Punjab mein sirf
    # 1, Uttarakhand mein 0). Isliye poora region hataakar test karna
    # bahut kada hai - model ko us ilaake ki ek bhi row nahi milti.
    # -----------------------------------------------------------
    print("\n" + "-" * 68)
    print("REGION HOLD-OUT (kabhi na dekha hua ilaaka)")
    print("-" * 68)
    rows = []
    for tr, te in GroupKFold(n_splits=groups.nunique()).split(X, y, groups):
        held = groups.iloc[te].unique()[0]
        if y[te].sum() == 0:      # us region mein type=2 hai hi nahi
            rows.append({"held_out": held, "n_test": len(te),
                         "n_static": 0, "f1": np.nan, "auc": np.nan})
            continue
        m = make_model(300, pos_w)
        m.fit(X.iloc[tr], y[tr])
        p = m.predict(X.iloc[te])
        rows.append({
            "held_out": held, "n_test": len(te), "n_static": int(y[te].sum()),
            "f1": f1_score(y[te], p, zero_division=0),
            "auc": roc_auc_score(y[te], m.predict_proba(X.iloc[te])[:, 1]),
        })
    cv = pd.DataFrame(rows)
    print(cv.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    mean_f1 = cv["f1"].mean()
    print(f"\n  average F1 (static class): {mean_f1:.3f}")
    print("  NOTE: punjab/uttarakhand mein type=2 hai hi nahi, isliye")
    print("        unka score nikaala hi nahi ja sakta (NaN).")

    # ---- final model ----
    clf = make_model(400, pos_w)
    clf.fit(X, y)
    pred = clf.predict(X)
    print("\n" + "-" * 68)
    print("POORE DATA PE (training fit - upar wala region score zyada imaandar hai)")
    print("-" * 68)
    print(classification_report(y, pred, target_names=["fire", "static"],
                                zero_division=0))

    # ---- feature importance ----
    imp = pd.Series(clf.feature_importances_, index=FEATURES).sort_values(
        ascending=False)
    print("MODEL NE KYA USE KIYA:")
    for k, v in imp.head(8).items():
        print(f"    {k:<14}{v:.3f}  {'#' * int(v * 60)}")

    # ---- confusion matrix ----
    cm = confusion_matrix(y, pred)
    fig, ax = plt.subplots(figsize=(5, 4.2))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1], ["fire", "static"])
    ax.set_yticks([0, 1], ["fire", "static"])
    ax.set_xlabel("model ne kya kaha"); ax.set_ylabel("NASA ne kya kaha")
    ax.set_title("NASA type ke against")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.tight_layout()
    fig.savefig(OUTPUTS / "nasa_confusion.png", dpi=130)
    plt.close(fig)

    # -----------------------------------------------------------
    # ASLI IMTIHAAN: ye model insaan ke banaye labels se milta hai?
    #
    # Model ne NASA ke labels se seekha. Ab dekho ki uska jawab
    # TUMHARE gold labels se kitna milta hai. Ye do bilkul alag
    # cheezein hain - agar milte hain to model ne sach mein kuch
    # asli seekha hai.
    # -----------------------------------------------------------
    gold_path = DATA_PROCESSED / "gold_labels.csv"
    gold_res = None
    if gold_path.exists():
        gold = pd.read_csv(gold_path)
        d["p_static"] = clf.predict_proba(X)[:, 1]
        by_src = d.groupby("source_id")["p_static"].mean()
        g = gold.copy()
        g["p_static"] = g["source_id"].map(by_src)
        g = g.dropna(subset=["p_static"])
        if len(g):
            g["is_ind"] = (g["gold_label"] == "INDUSTRIAL").astype(int)
            print("\n" + "-" * 68)
            print(f"KYA YE MODEL INSAAN SE MILTA HAI?  ({len(g)} gold sources)")
            print("-" * 68)
            if g["is_ind"].nunique() > 1:
                auc = roc_auc_score(g["is_ind"], g["p_static"])
                best = max(
                    ((t, f1_score(g["is_ind"], (g["p_static"] >= t).astype(int),
                                  zero_division=0)) for t in np.arange(.1, .9, .05)),
                    key=lambda x: x[1])
                acc = accuracy_score(g["is_ind"],
                                     (g["p_static"] >= best[0]).astype(int))
                print(f"  AUC (INDUSTRIAL pehchanne mein) : {auc:.3f}")
                print(f"  best threshold {best[0]:.2f} pe F1  : {best[1]:.3f}")
                print(f"  accuracy                        : {acc:.1%}")
                print("\n  NASA ke labels pe train hua, INSAAN ke labels pe naapa -")
                print("  beech mein hamare rules kahin nahi aaye.")
                gold_res = {"auc": float(auc), "best_threshold": float(best[0]),
                            "f1": float(best[1]), "accuracy": float(acc),
                            "n": int(len(g))}
            print("\n  gold class ke hisaab se model ka p_static (median):")
            print(g.groupby("gold_label")["p_static"].median().round(3).to_string())

    joblib.dump({"model": clf, "features": FEATURES,
                 "classes": ["fire", "static"]}, MODELS / "nasa_model.pkl")

    # NaN ko None kar do. Wajah: json.dumps NaN ko bina quote ke likh
    # deta hai, aur wo VALID JSON nahi hai - Python padh leta hai par
    # JavaScript ya koi bhi strict parser phat jata hai. Punjab/
    # Uttarakhand ke folds mein type=2 hai hi nahi, to unka f1/auc NaN
    # aata hai - wahi yahan null ban jata hai.
    holdout = [{k: (None if isinstance(v, float) and np.isnan(v) else v)
                for k, v in row.items()}
               for row in cv.to_dict(orient="records")]

    (OUTPUTS / "nasa_metrics.json").write_text(json.dumps({
        "n_detections": int(len(X)), "n_static": int(y.sum()),
        "imbalance": float(pos_w), "features": FEATURES,
        "region_holdout": holdout,
        "region_holdout_mean_f1": float(mean_f1),
        "feature_importance": imp.to_dict(),
        "vs_human_labels": gold_res,
    }, indent=2, default=float))

    print("\n" + "=" * 68)
    print("saved: models/nasa_model.pkl")
    print("       outputs/nasa_metrics.json")
    print("       outputs/nasa_confusion.png")
    print("=" * 68)


if __name__ == "__main__":
    main()
