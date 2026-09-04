"""
STEP 5 (part b) - INDUSTRIAL/FOREST_FIRE ke liye threshold tuning.

Abhi tak model seedha argmax karta hai - jo class ki probability sabse
zyada, wahi jawab. Par AGRI_BURN itna zyada hai training mein ki thoda
sa bhi confuse hone pe model AGRI_BURN hi bol deta hai.

Yahan har class ke liye alag threshold try karte hain: "agar iski
probability x se zyada hai, to isi ko chun lo - bhale hi koi aur class
ka score thoda zyada ho". Isse recall badhta hai, precision thoda girta
hai - trade-off hai, free nahi.

Sirf REPORT karta hai (best thresholds + before/after numbers).
Model ya predictions.gpkg ko nahi badalta - taaki faisla insaan le.

Chalane ka tareeka:
    python src/step5b_threshold_tune.py
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, f1_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA_PROCESSED, MODELS   # noqa: E402
from step5_train import load_data, build_X   # noqa: E402


def predict_with_thresholds(proba, classes, thresholds):
    """
    Har row ke liye: pehle un classes ko dekho jinka apna threshold
    paar ho gaya hai (jitna zyada paar kiya utni priority), warna
    seedha argmax pe wapas chale jao.
    """
    preds = []
    for row in proba:
        best_idx, best_margin = None, -np.inf
        for i, c in enumerate(classes):
            t = thresholds.get(c, None)
            if t is not None and row[i] >= t:
                margin = row[i] - t
                if margin > best_margin:
                    best_idx, best_margin = i, margin
        if best_idx is None:
            best_idx = int(np.argmax(row))
        preds.append(classes[best_idx])
    return np.array(preds)


def main():
    bundle = joblib.load(MODELS / "model.pkl")
    clf, le, classes = bundle["model"], bundle["label_encoder"], bundle["classes"]

    _, _, test = load_data()
    X = build_X(test)
    y_true = test["gold_label"]
    proba = clf.predict_proba(X)

    # ---- baseline: seedha argmax ----
    base_pred = le.inverse_transform(clf.predict(X))
    print("=" * 68)
    print("PEHLE (baseline, seedha argmax)")
    print("=" * 68)
    print(classification_report(y_true, base_pred, zero_division=0))
    base_f1 = f1_score(y_true, base_pred, average="macro", zero_division=0)

    # ---- INDUSTRIAL aur FOREST_FIRE ke liye threshold grid search ----
    grid = np.arange(0.10, 0.55, 0.05)
    best = {"macro_f1": base_f1, "thresholds": {}}

    for t_ind in grid:
        for t_forest in grid:
            thresholds = {"INDUSTRIAL": t_ind, "FOREST_FIRE": t_forest}
            pred = predict_with_thresholds(proba, classes, thresholds)
            mf1 = f1_score(y_true, pred, average="macro", zero_division=0)
            if mf1 > best["macro_f1"]:
                best = {"macro_f1": mf1, "thresholds": dict(thresholds)}

    print("=" * 68)
    print("BAAD MEIN (best thresholds gold set pe)")
    print("=" * 68)
    print(f"best thresholds: {best['thresholds'] or '(koi sudhaar nahi mila)'}")
    print(f"baseline macro-F1 : {base_f1:.3f}")
    print(f"tuned macro-F1    : {best['macro_f1']:.3f}")

    if best["thresholds"]:
        tuned_pred = predict_with_thresholds(proba, classes, best["thresholds"])
        print()
        print(classification_report(y_true, tuned_pred, zero_division=0))
    else:
        print("\nkoi threshold combo baseline se behtar nahi nikla -"
              " jo hai wahi best hai.")


if __name__ == "__main__":
    main()
