"""
STEP 4 (part 1) - har source ko naam ka label dena.

Ab tak har source ke paas SIRF NUMBERS the (kitni baar dikha, kitni door
hai, raat ko dikha ya din ko). Ab hum us source ko batayenge ki wo hai kya:

    INDUSTRIAL   - factory / refinery ka flare
    FOREST_FIRE  - jungle ki aag
    AGRI_BURN    - khet mein parali jalana
    UNSURE       - pakka nahi kah sakte

Ye kaam RULES se hota hai - yani seedhi shartein, koi AI nahi. Jaise:
"agar factory ke 1 km andar hai aur ek baar ki ghatna nahi hai, to
INDUSTRIAL hai."

Input : data/processed/sources.gpkg
        data/processed/detections.gpkg
Output: data/processed/sources_labelled.gpkg
        data/processed/anomalies.csv

Chalane ka tareeka:
    python src/step4_labels.py
"""
import sys

import geopandas as gpd
import pandas as pd

from config import (DATA_PROCESSED, ANOMALY_FRP_MULTIPLIER, INDUSTRY_RADIUS,
                    MIN_DIST_FROM_INDUSTRY, NIGHT_MAX_FOR_FIRE,
                    NIGHT_MIN_FOR_MACHINE, MIN_DET_FOR_NIGHT_RATIO)


# ===============================================================
# RULES - project ka poora "gyaan" in teen functions mein hai
# ===============================================================
def trust_night_ratio(s):
    """
    night_ratio pe bharosa kiya ja sakta hai ya nahi.

    Agar satellite ne kisi jagah ko sirf EK BAAR dekha aur wo raat ka
    pass tha, to night_ratio = 1.00 aa jayega. Isse ye sabit NAHI hota
    ki wo cheez raat mein jalti hai - ye satellite ki TIMING ka ittefaq
    hai, source ke vyavhaar ki baat nahi.

    Data mein 462 sources sirf night_ratio ki wajah se UNSURE the, aur
    unme se 319 ke paas sirf ek detection thi.
    """
    return s["n_detections"] >= MIN_DET_FOR_NIGHT_RATIO


def is_industrial(s):
    """
    Factory ka flare.

    Do shartein:
      1. factory ki chaardiwari ke 1 km ke andar hai
      2. sirf ek baar ki ghatna NAHI hai (yani baar-baar dikha hai)

    Doosri shart isliye zaroori hai ki factory ke bagal mein bhi koi
    ek baar aag laga sakta hai (kachra jalana waghairah). Wo factory
    ka flare nahi hai.
    """
    # -----------------------------------------------------------
    # DOOSRA RAASTA: raat mein jalna + mahinon tak chalna
    #
    # Upar wali shart OSM pe tiki hai - "mapped factory ke 1 km ke
    # andar". Par OSM adhoora hai. Korba mein ek source mila jiske
    # 2,859 detections hain, 266 alag din, raat 95% - aur OSM mein
    # us jagah KUCH BHI mapped nahi hai (sabse paas wali industry
    # 1,789 m door hai). Wo UNSURE pada tha.
    #
    # Satellite photo dekh kar confirm kiya: wahan buildings, khudi
    # hui zameen aur structures hain. Gemini ne bhi "industrial" kaha.
    #
    # Isliye ek doosra raasta: agar koi cheez RAAT mein jalti hai
    # AUR MAHINON tak chalti hai, to wo machine hai - aag nahi.
    # Kisan raat mein aag nahi lagata, aur jungle ki aag 266 din
    # nahi chalti.
    #
    # IMAANDARI: ye shart 45 gold labels pe naapi nahi ja sakti -
    # unme is type ka ek bhi udaharan nahi hai. Ye pehle usoolon pe
    # aur photo se confirm karke lagayi gayi hai. Isse 5 sources
    # UNSURE se INDUSTRIAL bane (3,176 detections).
    # -----------------------------------------------------------
    near_mapped = ((s["dist_to_industry_m"] < INDUSTRY_RADIUS)
                   & (s["persistence_tier"] != "EPISODIC"))
    burns_at_night = (trust_night_ratio(s)
                      & (s["night_ratio"] >= NIGHT_MIN_FOR_MACHINE)
                      & (s["persistence_tier"] == "PERSISTENT"))
    return near_mapped | burns_at_night


def is_forest_fire(s):
    """
    Jungle ki aag.

    Teen shartein:
      1. jungle wale ilaake pe hai
      2. factory se door hai
      3. lagatar chalne wali cheez NAHI hai

    ---------------------------------------------------------------
    DO SHARTEIN DHEELI KI GAYI - dono naap kar.

    (a) "5 km se door"  ->  "1 km se door"
        is_industrial pehle hi 1 km maangta hai. To 5 km ka buffer
        bekaar tha - 1 se 5 km ke beech ki har jungle ki aag UNSURE
        ban jati thi. Sirf isi shart se 684 sources atke huey the.

    (b) "tier == EPISODIC"  ->  "tier != PERSISTENT"
        EPISODIC ka matlab hai 30 din mein khatam. Par 40 din tak
        sulagti jungle ki aag bhi jungle ki aag hi hai. Beech wale
        (tier = OTHER) 1,656 sources bina wajah UNSURE the.
    ---------------------------------------------------------------
    """
    return ((s["lc_class"] == "forest")
            & (s["dist_to_industry_m"] > MIN_DIST_FROM_INDUSTRY)
            & (s["persistence_tier"] != "PERSISTENT"))


def is_agri_burn(s):
    """
    Khet mein parali jalana.

    ---------------------------------------------------------------
    YE RULE PLAN SE ALAG HAI - aur wajah pakki hai.

    Plan kehta hai pehli shart ho: lc_class == "cropland"
    (yani source kisi "khet" wale polygon pe ho).

    Par Phase 1 mein pata chala tha: Punjab ke 5,113 detections mein
    se sirf PAANCH kisi khet wale polygon pe hain. Kyunki OpenStreetMap
    pe Punjab ke khet mapped hi nahi hain - poore ilaake ka sirf 1.3%.

    To wo rule kabhi chalta hi nahi. Punjab ka 61% data UNSURE reh jata.

    Isliye humne "khet pe hai" ki jagah aisi shartein lagayi hain
    jo milkar wahi kaam karti hain.
    ---------------------------------------------------------------
    TEEN SHARTEIN DHEELI KI GAYI - har ek naap kar.

    (a) "3 km se door"  ->  "1 km se door"
        is_industrial pehle hi 1 km maangta hai, to 3 km ka buffer
        zaroorat se zyada tha. 2,440 sources sirf isi wajah se atke the.

    (b) "tier == EPISODIC"  ->  "tier != PERSISTENT"
        beech wale (tier = OTHER) bina wajah UNSURE ban rahe the.

    (c) peak_month wali shart HATA DI  <- sabse bada fix
        Wo shart thi: peak_month Apr/May/Oct/Nov mein ho.
        Ye PUNJAB ke katai ke mahine hain. Par shart POORE data pe
        lag rahi thi - Korba, Singrauli, Uttarakhand pe bhi, jahan
        fire season bilkul alag hai (central India mein March-April).

        Ek ilaake ka mausam poore desh pe thopna galat tha. Akele
        isi shart ne ~3,127 sources UNSURE bana diye the.
    -----------------------------------------------------------------
    """
    return (
        # 1. jungle pe nahi hai (warna wo forest fire hoti)
        (s["lc_class"] != "forest")
        # 2. factory se door hai
        & (s["dist_to_industry_m"] > MIN_DIST_FROM_INDUSTRY)
        # 3. lagatar chalne wali cheez nahi hai
        & (s["persistence_tier"] != "PERSISTENT")
        # 4. DIN mein hui.
        #    Data: katai ke mahinon (Oct-Nov, Apr-May) mein Punjab ke
        #    97% detections DIN ke hain, jabki refinery ke flare ka
        #    night_ratio 1.00 tha. Ye ek MAZBOOT jhukav hai - par
        #    "kisan raat mein aag nahi lagata" kehna galat hoga, kyunki
        #    3% raat ke hain, aur March-April mein 23-25% tak.
        #
        #    Isliye night_ratio pe bharosa TABHI karte hain jab kaafi
        #    detections hon. Kam detections wale sources ko ye shart
        #    rok nahi sakti (neeche ~ wala hissa).
        & (~trust_night_ratio(s) | (s["night_ratio"] < NIGHT_MAX_FOR_FIRE))
    )


def apply_rules(sources):
    """
    Teeno rules lagao aur label decide karo.

    Ek source pe DO rules bhi lag sakte hain (jaise koi jagah jungle ke
    paas bhi hai aur factory ke paas bhi). Aise mein hum zabardasti ek
    nahi chunte - use UNSURE chhod dete hain, taaki aage insaan ya AI
    use dekh sake.

    "Pata nahi" kehna galat jawab dene se behtar hai.
    """
    s = sources
    hits = pd.DataFrame({
        "INDUSTRIAL": is_industrial(s),
        "FOREST_FIRE": is_forest_fire(s),
        "AGRI_BURN": is_agri_burn(s),
    })

    n_matched = hits.sum(axis=1)          # har source pe kitne rules lage

    label = pd.Series("UNSURE", index=s.index)
    exactly_one = n_matched == 1
    # jis source pe theek ek rule laga, wahi rule ka naam le lo
    label[exactly_one] = hits[exactly_one].idxmax(axis=1)

    return label, n_matched


# ===============================================================
# needs_review - kaunse sources pe insaan/AI ki nazar chahiye
# ===============================================================
def mark_needs_review(sources, label):
    """
    Do tarah ke sources pe dobara nazar daalni chahiye:

      1. jinpe koi rule nahi laga (UNSURE)

      2. jo "confusing zone" mein hain - factory se 500 se 3000 metre
         door. Ye khatarnak doori hai: itni paas ki shayad factory ka
         hi hissa ho, itni door ki shayad bilkul alag cheez ho.
         Rules yahan aksar galti karte hain.
    """
    confusing_zone = sources["dist_to_industry_m"].between(500, 3000)
    return (label == "UNSURE") | confusing_zone


# ===============================================================
# Anomaly - "aaj kuch alag hua"
# ===============================================================
def find_anomalies(detections, sources):
    """
    Anomaly ek ALAG cheez hai, class nahi.

    Idea: agar koi factory roz 5 MW garmi deti hai, aur ek din achanak
    20 MW de de - to us din kuch hua tha. Shayad flaring badh gayi,
    shayad koi ghatna hui.

    Isliye har PERSISTENT source ke liye dekhte hain ki kis din ki
    garmi uske apne normal (median) se 3 guna se zyada thi.

    "Apne normal se" - ye zaroori hai. Har factory ka apna normal
    alag hota hai. Ek badi refinery ka 8 MW normal ho sakta hai,
    chhoti ka 2 MW.
    """
    persistent_ids = sources.loc[
        sources["persistence_tier"] == "PERSISTENT", "source_id"
    ]
    if len(persistent_ids) == 0:
        return pd.DataFrame()

    rows = []
    for source_id in persistent_ids:
        mine = detections[detections["source_id"] == source_id]
        if len(mine) == 0:
            continue

        normal_frp = mine["frp"].median()      # is source ka apna normal
        if normal_frp <= 0:
            continue

        # har din ki sabse tez garmi
        daily_max = mine.groupby("acq_date")["frp"].max()

        for date, frp in daily_max.items():
            ratio = frp / normal_frp
            if ratio > ANOMALY_FRP_MULTIPLIER:
                info = sources[sources["source_id"] == source_id].iloc[0]
                rows.append({
                    "source_id": source_id,
                    "date": date,
                    "frp": round(frp, 2),
                    "normal_frp": round(normal_frp, 2),
                    "ratio": round(ratio, 2),
                    "industry_name": info["industry_name"],
                    "region": info["region"],
                })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("ratio", ascending=False)


# ===============================================================
# Main
# ===============================================================
def main():
    src_path = DATA_PROCESSED / "sources.gpkg"
    det_path = DATA_PROCESSED / "detections.gpkg"
    if not src_path.exists() or not det_path.exists():
        print("ERROR: sources.gpkg ya detections.gpkg nahi mili.")
        print("  pehle ye chalao: python src/step3_persistence.py")
        sys.exit(1)

    sources = gpd.read_file(src_path, layer="sources")
    detections = gpd.read_file(det_path, layer="detections")
    print(f"load: {len(sources)} sources, {len(detections)} detections\n")

    # ---- rules lagao ----
    label, n_matched = apply_rules(sources)
    sources["rule_label"] = label
    sources["label"] = label           # aage VLM/insaan ise badal sakte hain
    sources["label_source"] = "rule"   # ye label kahan se aaya
    sources.loc[label == "UNSURE", "label_source"] = "none"
    sources["needs_review"] = mark_needs_review(sources, label)

    # ---- report ----
    print("=" * 58)
    print("RULES SE LABEL")
    print("=" * 58)
    counts = label.value_counts()
    for name in ["INDUSTRIAL", "FOREST_FIRE", "AGRI_BURN", "UNSURE"]:
        n = counts.get(name, 0)
        print(f"  {name:<14} {n:>6}   ({n / len(sources) * 100:5.1f}%)")

    print(f"\n  UNSURE kyun hue:")
    print(f"    kisi rule ne match nahi kiya : {(n_matched == 0).sum():>6}")
    print(f"    ek se zyada rule lag gaye    : {(n_matched > 1).sum():>6}")
    print(f"\n  needs_review (dobara dekhna hai): {sources['needs_review'].sum():>6}")

    print("\n  region ke hisaab se:")
    print(pd.crosstab(sources["region"], sources["label"]).to_string())

    # ---- anomalies ----
    print("\n" + "=" * 58)
    print("ANOMALIES (normal se 3 guna zyada garmi wale din)")
    print("=" * 58)
    anomalies = find_anomalies(detections, sources)
    if len(anomalies) == 0:
        print("  koi anomaly nahi mili")
    else:
        out_csv = DATA_PROCESSED / "anomalies.csv"
        anomalies.to_csv(out_csv, index=False)
        print(f"  {len(anomalies)} anomalies mili -> {out_csv}")
        print("\n  top 10:")
        print(anomalies.head(10).to_string(index=False))

    # ---- save ----
    out = DATA_PROCESSED / "sources_labelled.gpkg"
    sources.to_file(out, driver="GPKG")
    print(f"\nSAVED: {out}")
    print("\nAgla step: python src/step4b_vlm.py   (confusing cases pe AI)")
    print("        ya: streamlit run src/gold_ui.py  (150 sources khud label karna)")


if __name__ == "__main__":
    main()
