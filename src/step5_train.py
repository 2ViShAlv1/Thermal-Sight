"""
STEP 5 - model train karna.  <<< PHASE 4

Ab tak rules ne labels lagaye the ("agar factory 500m ke andar aur
night_ratio > 0.7 to INDUSTRIAL"). Rules kaam karte hain par bhurbhure
hain - har naye ilaake ke liye threshold dobara set karna padta hai.

Ab machine ko 16,474 labelled sources dikhate hain aur wo KHUD pattern
seekh legi.

DHYAN: model prediction to SAARE sources pe deta hai, par dashboard un
1,099 UNSURE sources pe uska jawab JAAN-BOOJH KAR nahi dikhata. Naapne
pe wo wahan sirf 39% sahi tha (3 classes mein tukka 33% hota hai), to
wo "review queue" ban jate hain. Detail app.py mein.

Input : data/processed/sources_labelled.gpkg   (17,615 sources)
        data/processed/gold_labels.csv         (45 insaan ke labels)

Output: models/model.pkl                  trained model + feature list
        data/processed/predictions.gpkg   saare sources + jawab + yakeen
        outputs/metrics.json              saare scores (ablation samet)
        outputs/confusion_matrix.png      kahan galti hui
        outputs/shap_summary.png          kaunsa sabooot kaam aaya

Chalane ka tareeka:
    python src/step5_train.py
"""
import json
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")            # headless - koi window nahi kholni
import matplotlib.pyplot as plt

import shap
from xgboost import XGBClassifier
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (classification_report, confusion_matrix,
                             f1_score, accuracy_score)
import joblib

from config import DATA_PROCESSED, MODELS, OUTPUTS, CLASSES


# ===============================================================
# FEATURES - model ko kya-kya dikhana hai
#
# Ye list ka ORDER pavitra hai. Model ko column ke NAAM yaad nahi
# rehte, sirf JAGAH yaad rehti hai ("chautha number = night_ratio").
# Agar predict ke waqt order badal gaya to model frp ki jagah
# night_ratio padh lega aur bakwaas jawab dega - BINA ERROR DIYE.
# Isliye ye list model ke saath hi save hoti hai (neeche dekho).
# ===============================================================
NUM_FEATURES = [
    # --- persistence: "kitni baar, kitne din" (step3 se) ---
    "n_detections",       # kul kitni baar dikha
    "n_days",             # kitne ALAG dinon pe dikha
    "lifespan_days",      # pehli aur aakhri detection ke beech
    "activity_ratio",     # n_days / lifespan
    "n_months",           # kitne alag mahinon mein dikha
    "peak_month",         # sabse zyada kis mahine

    # --- waqt ka AAKAAR (step3._temporal_shape se) ---
    # Ye teen features KISI RULE mein nahi hain. Baaki sab features
    # step4 ke rules bhi dekhte hain - isliye model unse kuch naya
    # nahi seekh sakta, sirf rule ka formula ratta maar leta hai
    # (naapa: 16,516/16,516 sources pe model = rule, EK bhi ikhtilaf
    # nahi). Ye teen wo pehli cheezein hain jinpe model apni RAAI
    # bana sakta hai.
    #
    # aag = EK ghatna (lagatar din, phir khatam)
    # machine = AADAT (bikhre din, be-tarteeb faasle)
    "gap_cv",             # faasle kitne be-tarteeb    IND 1.36 | FOR 0.32
    "burst_frac",         # sabse lambi lagatar chain  IND 0.41 | FOR 0.71
    "max_gap_days",       # sabse lambi chuppi

    # --- behaviour: "kab aur kitni tez" (FIRMS se) ---
    "night_ratio",        # raat wali detections ka hissa  <- sabse strong
    "frp_mean",
    "frp_median",
    "frp_max",
    "frp_std",

    # --- NASA ka apna classification ---
    # static_ratio = FIRMS ne kitne detections ko "static land source"
    # (type=2) kaha. Ye NASA ka apna faisla hai, hamare rules se AZAAD -
    # isliye ye un chand features mein se hai jo model ko kuch NAYA
    # bata sakte hain.
    # -1 ka matlab "NASA ne kuch kaha hi nahi" (NOAA-21 NRT ye field
    # nahi deta). XGBoost -1 ko apne aap alag category ki tarah handle
    # kar leta hai - wo trees banata hai, scaling nahi karta.
    "static_ratio",

    # --- context: "aas-paas kya hai" (OSM/WRI se) ---
    "dist_to_industry_m",
]

CAT_FEATURES = ["lc_class", "persistence_tier"]
LC_VALUES = ["cropland", "forest", "urban", "other"]
TIER_VALUES = ["PERSISTENT", "EPISODIC", "OTHER"]

# ---------------------------------------------------------------
# lat/lon JAAN-BOOJH KAR nahi liye.
#
# Wajah: AGRI_BURN ka 79% Punjab se aata hai. Agar model ko lat/lon
# de diya to wo seedha ratta maar lega - "latitude 30.4 ke aas-paas
# = AGRI_BURN". Training pe score shaandaar aayega aur naye ilaake
# pe model bilkul bekaar nikkega.
#
# Hum chahte hain ki wo VYAVHAAR se pehchane (raat mein jalta hai?
# baar-baar dikhta hai?), JAGAH se nahi.
# ---------------------------------------------------------------


# ===============================================================
def load_data():
    """sources + gold labels padho, aur gold ko training se ALAG karo."""
    src = gpd.read_file(DATA_PROCESSED / "sources_labelled.gpkg")
    gold = pd.read_csv(DATA_PROCESSED / "gold_labels.csv")

    # -----------------------------------------------------------
    # LEAKAGE FIX - ye sabse zaroori 3 lines hain is file mein.
    #
    # 45 gold sources mein se 42 pe rules ne bhi label lagaya hai,
    # yani wo training data mein BHI hain. Agar na hataye to model
    # unhe padhai ke waqt dekh lega aur phir unhi pe test hoga -
    # score jhootha zyada aayega, aur humein pata bhi nahi chalega.
    #
    # Kharcha: 16,516 mein se 42 rows. Kuch bhi nahi.
    # -----------------------------------------------------------
    gold_ids = set(gold["source_id"])

    train = src[(src["label"] != "UNSURE") & (~src["source_id"].isin(gold_ids))].copy()

    # gold ke liye asli features sources file se uthao (csv mein sirf label hai)
    test = src[src["source_id"].isin(gold_ids)].merge(
        gold[["source_id", "gold_label"]], on="source_id", how="inner")

    return src, train, test


def build_X(df):
    """df ko model ke samajhne layak numbers ki table mein badlo."""
    X = df[NUM_FEATURES].copy()

    # text ko model nahi khata. One-hot: har value ka apna 0/1 column.
    # get_dummies ka order alag-alag data pe badal sakta hai, isliye
    # values fix karke khud bana rahe hain.
    for v in LC_VALUES:
        X[f"lc_{v}"] = (df["lc_class"] == v).astype(int)
    for v in TIER_VALUES:
        X[f"tier_{v}"] = (df["persistence_tier"] == v).astype(int)

    return X


def feature_names():
    return (NUM_FEATURES
            + [f"lc_{v}" for v in LC_VALUES]
            + [f"tier_{v}" for v in TIER_VALUES])


def make_model(n_estimators=400):
    """
    XGBoost. Plan mein yahi likha hai, aur wajah bhi hai:
    boosting har naye tree se pichhli GALTI theek karta hai, isliye
    kam data pe bhi RandomForest se behtar nikalta hai.

    XGBoost text labels nahi khata - 0/1/2 chahiye. Isliye baahar
    LabelEncoder lagta hai (neeche).
    """
    return XGBClassifier(
        n_estimators=n_estimators, max_depth=5, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        objective="multi:softprob", num_class=3,
        n_jobs=-1, random_state=42, eval_metric="mlogloss")


def sample_weights(y):
    """
    class_weight XGBoost mein nahi hota - weight har ROW pe dena padta hai.
    INDUSTRIAL sirf 115 hai vs AGRI 4,399. Iske bina model chalaki karega:
    har baar "INDUSTRIAL nahi" bol kar 98.7% accuracy pa lega, bina ek
    bhi factory pehchane.
    """
    counts = y.value_counts()
    return y.map(len(y) / (len(counts) * counts)).values


# ===============================================================
def evaluate_three_ways(train):
    """
    TEEN tarah se naapo. Score (a) se (c) tak GIREGA - aur wo girna
    imaandari hai, galti nahi. Har agla test pichhle se KADA hai.

      (a) random 5-fold  - sabse aasan. Rows randomly baant do.
      (b) region hold-out - poora ilaaka hataao. Model ne us region ki
          ek bhi row nahi dekhi. Asli duniya mein bhi naya ilaaka hi aayega.
      (c) gold labels    - INSAAN ke banaye 47. Sabse imaandar.

    Plan (b) ke liye source_id se group karne ko kehta hai, par DBSCAN
    ke baad har source ki EK hi row hai - to source_id se group karna
    random split jaisa hi hoga, kuch naya test nahi karta. Region se
    group karna ussey kaafi KADA hai, isliye wahi kiya.
    """
    X, y = build_X(train), train["label"]
    le = LabelEncoder().fit(y)
    yc = le.transform(y)
    rows = []

    # ---- (a) random 5-fold ----
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    for tr, te in skf.split(X, yc):
        clf = make_model(300)
        clf.fit(X.iloc[tr], yc[tr], sample_weight=sample_weights(y.iloc[tr]))
        rows.append({"test": "(a) random 5-fold", "held_out": "-",
                     "n": len(te),
                     "macro_f1": f1_score(yc[te], clf.predict(X.iloc[te]),
                                          average="macro", zero_division=0)})

    # ---- (b) region hold-out ----
    groups = train["region"]
    gkf = GroupKFold(n_splits=groups.nunique())
    for tr, te in gkf.split(X, yc, groups):
        clf = make_model(300)
        clf.fit(X.iloc[tr], yc[tr], sample_weight=sample_weights(y.iloc[tr]))
        rows.append({"test": "(b) region hold-out",
                     "held_out": groups.iloc[te].unique()[0], "n": len(te),
                     "macro_f1": f1_score(yc[te], clf.predict(X.iloc[te]),
                                          average="macro", zero_division=0)})

    return pd.DataFrame(rows), le


def ablation(train, test, le):
    """
    ABLATION - "kya model sach mein seekh raha hai, ya rules ki nakal
    utaar raha hai?" Ka NAAPA HUA jawab.

    -----------------------------------------------------------------
    Problem: hamare labels RULES ne banaye, aur rules 3 cheezein dekhte
    hain - lc_class, dist_to_industry_m, aur persistence_tier. Model ko
    bhi WAHI cheezein di jati hain.

    To model ke liye kaam bahut aasan ho jata hai: use bas rules ka
    formula ratta maarna hai. Isiliye region hold-out pe 0.997 aata hai -
    wo "samajh" nahi, "nakal" hai.

    Iska SABOOOT kaise dein? Model se wo features CHHEEN lo aur dobara
    naapo. Agar score gir jaye, to matlab wo unhi pe tika tha.

    Naapa hua nateeja:
        sab features        region 0.997 | gold 75.6%
        bina lc_class       region 0.671 | gold 73.3%
        sirf FIRMS data     region 0.445 | gold 62.2%

    Yani lc_class akela model ko 32 points ka JHOOTHA region score de
    raha tha, jabki asli faayda sirf 2 points ka hai.

    Ye table hamari sabse imaandar cheez hai - isse pata chalta hai ki
    hum apne hi model ki seemayein jaante hain.
    -----------------------------------------------------------------
    """
    y = le.transform(train["label"])
    w = sample_weights(train["label"])
    groups = train["region"]
    rows = []

    for name, drop in [("sab features", []),
                       ("bina lc_class", ["lc_"]),
                       ("bina lc + dist", ["lc_", "dist_to_industry_m"]),
                       ("sirf FIRMS (koi naksha nahi)",
                        ["lc_", "dist_to_industry_m", "tier_"])]:
        keep = [c for c in feature_names()
                if not any(c.startswith(d) or c == d for d in drop)]
        Xt, Xe = build_X(train)[keep], build_X(test)[keep]

        # region hold-out - kabhi na dekhe hue ilaake pe
        f1s = []
        for tr_i, te_i in GroupKFold(n_splits=groups.nunique()).split(Xt, y, groups):
            m = make_model(250)
            m.fit(Xt.iloc[tr_i], y[tr_i], sample_weight=w[tr_i])
            f1s.append(f1_score(y[te_i], m.predict(Xt.iloc[te_i]),
                                average="macro", zero_division=0))

        m = make_model(400)
        m.fit(Xt, y, sample_weight=w)
        pred = le.inverse_transform(m.predict(Xe))
        rows.append({
            "features": name, "n_features": len(keep),
            "region_f1": float(pd.Series(f1s).mean()),
            "gold_accuracy": float(accuracy_score(test["gold_label"], pred)),
            "gold_macro_f1": float(f1_score(test["gold_label"], pred,
                                            average="macro", zero_division=0)),
        })
    return pd.DataFrame(rows)


def evaluate_on_gold(clf, le, test):
    """
    IMTIHAAN 2 - insaan ke banaye 45 labels.

    Ye sabse imaandar score hai: labels rules ne nahi, INSAAN ne
    banaye. Par sirf 45 hain (~15 per class), to score ka margin
    chauda rahega (95% CI lagbhag +-14 points). Isko "lagbhag" ki
    tarah padho, "exactly" nahi.
    """
    X = build_X(test)
    y_true = test["gold_label"]
    pred = le.inverse_transform(clf.predict(X))

    # UNCLEAR insaan ka jawab hai, model ki class nahi (predict kabhi
    # kar hi nahi sakta) - to use macro average mein daalna unfair hai.
    # macro_f1 (saare labels, UNCLEAR samet - conservative) aur
    # macro_f1_known_classes (sirf 3 asli classes - fair comparison)
    # dono report karo.
    return {
        "n": len(test),
        "accuracy": accuracy_score(y_true, pred),
        "macro_f1": f1_score(y_true, pred, average="macro", zero_division=0),
        "macro_f1_known_classes": f1_score(y_true, pred, average="macro",
                                           labels=CLASSES, zero_division=0),
        "report": classification_report(y_true, pred, zero_division=0,
                                        output_dict=True),
        "_y_true": y_true, "_pred": pred,
    }


# ===============================================================
def plot_confusion(y_true, pred, path):
    """Kahan galti hui - tasveer mein."""
    labels = [c for c in CLASSES if c in set(y_true) | set(pred)]
    cm = confusion_matrix(y_true, pred, labels=labels)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=30, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("model ne kya kaha"); ax.set_ylabel("asli jawab")
    ax.set_title(f"Confusion Matrix (gold set, n={len(y_true)})")
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def plot_shap(clf, X, path):
    """
    SHAP - "har feature ne jawab ko kitna DHAKKA diya".

    feature_importances_ se behtar kyun: wo sirf batata hai "ye feature
    kaam ka tha". SHAP batata hai KIS TARAF dhakela - "night_ratio
    zyada tha, isliye INDUSTRIAL ki taraf gaya".

    Ye sabse zaroori tasveer hai. Isse sabit hota hai ki model ne WAHI
    seekha jo hona chahiye tha - ratta nahi maara.
    """
    # 8,793 rows pe SHAP dheema hai; 1,000 ka sample kaafi hai
    Xs = X.sample(min(1000, len(X)), random_state=42)
    sv = shap.TreeExplainer(clf).shap_values(Xs)

    plt.figure()
    shap.summary_plot(sv, Xs, plot_type="bar", show=False,
                      class_names=list(CLASSES))
    plt.tight_layout(); plt.savefig(path, dpi=130); plt.close()

    # numbers bhi chahiye report ke liye.
    # multiclass pe SHAP ka shape (samples, features, classes) hota hai -
    # feature wale axis ko chhod kar baaki sab pe average lena hai.
    import numpy as np
    a = np.abs(np.array(sv))
    if a.ndim == 3:
        # purane SHAP mein (classes, samples, features) bhi aata hai
        axis = (0, 2) if a.shape[1] == len(Xs.columns) else (0, 1)
        imp = a.mean(axis=axis)
    else:
        imp = a.mean(axis=0)
    return pd.Series(imp, index=Xs.columns).sort_values(ascending=False)


# ===============================================================
def main():
    src, train, test = load_data()

    print("=" * 68)
    print("STEP 5 - MODEL TRAINING")
    print("=" * 68)
    print(f"\ntraining rows : {len(train):,}")
    print(f"gold test rows: {len(test):,}  (training se hata diye gaye)")
    print(f"features      : {len(feature_names())}")
    print("\nclass balance:")
    for k, v in train["label"].value_counts().items():
        print(f"    {k:<14}{v:>6,}")

    if len(test) == 0:
        sys.exit("!! gold labels merge nahi hue - source_id match nahi kar rahe")

    # ---- TEEN tarah se evaluate ----
    print("\n" + "-" * 68)
    print("EVALUATION - teen tarah se, har agla pichhle se KADA")
    print("-" * 68)
    cv, le = evaluate_three_ways(train)
    print(cv.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    for t in cv["test"].unique():
        print(f"\n  {t}: macro-F1 {cv[cv['test'] == t]['macro_f1'].mean():.3f}")
    print("\n  NOTE: score (a) se (c) tak GIRTA hai - aur ye theek hai.")
    print("        (a) sabse aasan test, (c) sabse kada. Sirf (c) imaandar")
    print("        hai kyunki uske labels INSAAN ne banaye, rules ne nahi.")

    # ---- final model: poore training data pe ----
    X, y = build_X(train), train["label"]
    clf = make_model(400)
    clf.fit(X, le.transform(y), sample_weight=sample_weights(y))

    # ---- IMTIHAAN 2: insaan ke gold labels ----
    print("\n" + "-" * 68)
    print(f"IMTIHAAN 2 - insaan ke {len(test)} gold labels")
    print("-" * 68)
    gold_res = evaluate_on_gold(clf, le, test)
    print(f"  accuracy              : {gold_res['accuracy']:.3f}")
    print(f"  macro-F1 (4 labels)   : {gold_res['macro_f1']:.3f}  "
          f"(UNCLEAR samet - model wo kabhi predict nahi kar sakta)")
    print(f"  macro-F1 (3 classes)  : {gold_res['macro_f1_known_classes']:.3f}  "
          f"(sirf INDUSTRIAL/FOREST_FIRE/AGRI_BURN - fair comparison)")
    print("\n" + classification_report(gold_res["_y_true"], gold_res["_pred"],
                                       zero_division=0))

    # ---- ABLATION: kya model seekh raha hai ya nakal kar raha hai ----
    print("\n" + "-" * 68)
    print("ABLATION - rule wale features chheen kar dekho")
    print("-" * 68)
    abl = ablation(train, test, le)
    print(abl.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    drop = abl.iloc[0]["region_f1"] - abl.iloc[-1]["region_f1"]
    print(f"\n  region score {abl.iloc[0]['region_f1']:.3f} se "
          f"{abl.iloc[-1]['region_f1']:.3f} tak GIRA ({drop:.3f})")
    print("  -> yahi sabooot hai ki upar wala score 'samajh' nahi, 'nakal' thi.")
    print("  -> aur gold accuracy sirf "
          f"{abl.iloc[0]['gold_accuracy'] - abl.iloc[-1]['gold_accuracy']:.1%} giri,")
    print("     yani asli faayda utna nahi tha jitna score dikha raha tha.")

    # ---- tasveerein ----
    plot_confusion(gold_res["_y_true"], gold_res["_pred"],
                   OUTPUTS / "confusion_matrix.png")
    imp = plot_shap(clf, X, OUTPUTS / "shap_summary.png")
    print("-" * 68)
    print("TOP 8 SABOOOT (SHAP):")
    for k, v in imp.head(8).items():
        print(f"    {k:<22}{v:.3f}  {'#' * int(v * 100)}")

    # ---- saare 17,615 pe prediction ----
    # UNSURE wale 1,099 bhi isme hain. DHYAN: dashboard un pe model ka
    # jawab dikhata NAHI hai (wahan wo sirf 39% sahi tha) - wo "review
    # queue" ban jate hain. Prediction phir bhi nikaalte hain taaki
    # naapa ja sake ki model wahan kitna kamzor hai.
    all_X = build_X(src)
    proba = clf.predict_proba(all_X)
    out = src.copy()
    out["pred_label"] = le.inverse_transform(proba.argmax(axis=1))
    out["confidence"] = proba.max(axis=1)
    for i, c in enumerate(le.classes_):
        out[f"proba_{c}"] = proba[:, i]

    # -----------------------------------------------------------
    # INSPECTION PRIORITY
    #
    # Pehle ye model ke confidence pe tha. Wo GALAT tha: model rules ki
    # nakal karta hai, to uska kaam deterministic hai aur wo 99% sources
    # pe 1.00 confidence deta hai. Aisa "yakeen" kuch nahi batata.
    #
    # Isliye ab ye ASLI cheez pe hai - anomalies. Anomaly matlab wo din
    # jab us source ne apne KHUD ke normal se 3 guna zyada garmi di.
    # Ek factory jisne 12 baar aisa kiya, wo sach mein dekhne layak hai.
    # -----------------------------------------------------------
    anom_path = DATA_PROCESSED / "anomalies.csv"
    if anom_path.exists():
        anom = pd.read_csv(anom_path)
        counts = anom.groupby("source_id").size()
        worst = anom.groupby("source_id")["ratio"].max()
        out["n_anomalies"] = out["source_id"].map(counts).fillna(0).astype(int)
        out["worst_anomaly_ratio"] = out["source_id"].map(worst).fillna(0.0)
    else:
        out["n_anomalies"] = 0
        out["worst_anomaly_ratio"] = 0.0

    out["needs_inspection"] = ((out["label"] == "INDUSTRIAL")
                               & (out["n_anomalies"] > 0))

    out.to_file(DATA_PROCESSED / "predictions.gpkg", driver="GPKG")

    # ---- model + FEATURE LIST save (order wala bug yahin ruk-ta hai) ----
    joblib.dump({"model": clf,
                 "label_encoder": le,
                 "features": feature_names(),
                 "num_features": NUM_FEATURES,
                 "cat_features": CAT_FEATURES,
                 "classes": list(le.classes_)},
                MODELS / "model.pkl")

    metrics = {
        "n_train": int(len(train)),
        "n_gold_test": int(len(test)),
        "features": feature_names(),
        "evaluation": cv.to_dict(orient="records"),
        "macro_f1_by_test": {t: float(cv[cv["test"] == t]["macro_f1"].mean())
                             for t in cv["test"].unique()},
        "gold": {k: gold_res[k] for k in
                ("n", "accuracy", "macro_f1", "macro_f1_known_classes", "report")},
        "shap_importance": imp.to_dict(),
        "ablation": abl.to_dict(orient="records"),
    }
    (OUTPUTS / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float))

    # ---- report ----
    print("\n" + "=" * 68)
    print(f"SAARE {len(out):,} SOURCES PE PREDICTION")
    print("=" * 68)
    print(out["pred_label"].value_counts().to_string())
    unsure = out[out["label"] == "UNSURE"]
    print(f"\nrules ne {len(unsure):,} pe haath khade kar diye the. Model ne:")
    print(unsure["pred_label"].value_counts().to_string())
    print(f"\ninspection chahiye (INDUSTRIAL + anomaly mili): "
          f"{int(out['needs_inspection'].sum()):,}")

    print("\nsaved:")
    for f in ["models/model.pkl", "data/processed/predictions.gpkg",
              "outputs/metrics.json", "outputs/confusion_matrix.png",
              "outputs/shap_summary.png"]:
        print(f"    {f}")
    # ---- headline - yahi PPT ke pehle slide pe jayega ----
    n_raw = int(src["n_detections"].sum())
    n_ind = int((out["label"] == "INDUSTRIAL").sum())
    print("\n" + "=" * 68)
    print(f"  {n_raw:,} raw FIRMS detections  ->  {n_ind} industrial sources")
    print(f"  reduction: {100 * (1 - n_ind / n_raw):.3f}%")
    print("=" * 68)

    print("\nAgla step: streamlit run app.py")


if __name__ == "__main__":
    main()
