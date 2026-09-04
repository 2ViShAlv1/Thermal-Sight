"""
STEP 3 - persistent thermal sources dhoondhna.  <<< PROJECT KA DIL

Idea ek line mein:
    Agar ek hi jagah mahinon tak baar-baar garam dikhti hai, to wo
    chalti hui factory hai. Agar 3 din dikhi aur gayab ho gayi, to
    wo ek aag ki ghatna thi.

Ab tak humne har detection ko alag row ki tarah dekha. Par ek refinery
ka flare 198 baar detect hua hai - wo 198 alag cheezein nahi hain,
EK cheez hai jo 198 baar dikhi.

Ye script un 198 rows ko jodkar EK "source" banati hai, aur us source
ke baare mein batati hai ki wo kitni der tak, kitni regular, aur din
mein ya raat mein active tha.

Input : data/processed/features.gpkg    (8,415 detections)
Output: data/processed/sources.gpkg     (unse bane sources)
        data/processed/detections.gpkg  (wahi 8,415 detections, par ab
                                         har ek pe likha hai wo kis
                                         source ka hissa hai)

Doosri file kyun: Phase 3 mein anomaly dhoondhni hai ("kis din is
factory ne normal se 3 guna zyada garmi di?") aur FRP ka chart banana
hai. Uske liye har detection alag chahiye - sirf source ka summary
kaafi nahi. Isliye mapping yahin save kar dete hain, taaki DBSCAN
dobara na chalana pade.

Chalane ka tareeka:
    python src/step3_persistence.py
"""
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from config import (DATA_PROCESSED, CRS_METRES, CRS_LATLON,
                    DBSCAN_EPS, DBSCAN_MIN_SAMPLES,
                    PERSISTENT_MIN_LIFESPAN, PERSISTENT_MIN_DAYS,
                    EPISODIC_MAX_LIFESPAN)


# ===============================================================
# Step A - detections ko clusters mein baantna
# ===============================================================
def cluster_one_region(sub, region_name):
    """
    Ek region ke detections pe DBSCAN chalata hai.

    DBSCAN kaise kaam karta hai (simple bhasha mein):
      - har point ke aas-paas `eps` metre ka daayra dekho
      - agar us daayre mein kam se kam `min_samples` points hain,
        to ye sab ek hi cluster ke hain
      - jo point kisi bhi cluster mein fit nahi hota, wo "noise" hai
        (DBSCAN use label -1 deta hai)

    Hum coordinates METRE wale CRS se lete hain (geometry.x / .y).
    Degrees mein karte to eps=500 ka matlab "500 degree" hota - bekaar.
    """
    xy = np.c_[sub.geometry.x, sub.geometry.y]
    labels = DBSCAN(eps=DBSCAN_EPS, min_samples=DBSCAN_MIN_SAMPLES).fit_predict(xy)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int((labels == -1).sum())
    print(f"  {region_name:14} {len(sub):>5} detections -> "
          f"{n_clusters:>4} clusters + {n_noise:>5} akele points "
          f"({n_noise / len(sub) * 100:.0f}%)")

    # -----------------------------------------------------------
    # NOISE ka kya karein - ye ek asli faisla hai
    #
    # DBSCAN ne 60% points ko "noise" kaha hai. Unhe phenk dena
    # aasan hota, par GALAT hota:
    #
    #   - Punjab mein har kisan apne khet mein ek baar aag lagata
    #     hai. Wo detection kisi cluster mein nahi aayegi. Par wo
    #     ek asli ghatna hai - AGRI_BURN ka udaharan hai.
    #   - Unhe girate to model ke paas AGRI_BURN sikhne ke liye
    #     kuch bacheta hi nahi.
    #
    # Isliye har noise point ko "ek baar dikha source" maan lete
    # hain. Uska lifespan 0 hoga, yani wo apne aap EPISODIC ban
    # jayega - jo ki bilkul sahi hai.
    #
    # Unhe alag id dete hain taaki har akela point apna alag source
    # rahe, sab milkar ek na ban jayein.
    # -----------------------------------------------------------
    out = sub.copy()
    out["_cluster"] = labels
    out["is_noise"] = labels == -1
    out["source_id"] = make_source_ids(out, region_name)
    return out


def make_source_ids(df, region_name):
    """
    Har source ko ek naam do - uski JAGAH ke hisaab se.

    -----------------------------------------------------------------
    Pehle hum ginti wale naam dete the: jamnagar_c0, jamnagar_n1,
    jamnagar_n2... yani "Jamnagar ka pehla cluster", "doosra akela
    point", waghairah.

    Wo TOOT GAYA. Jab humne data badla (1 satellite se 3 kiya), to
    saare clusters naye sire se bane aur poori ginti hil gayi.
    "jamnagar_n335" naam to bacha raha, par ab wo KISI AUR jagah ko
    bata raha tha - aurat 60 kilometre door!

    Iska nateeja: 50 gold labels jo haath se lagaye the, sab galat
    jagah point karne lage.

    Ab naam JAGAH se banta hai:  jamnagar_2234_6985
    yani "Jamnagar mein latitude 22.34, longitude 69.85 wala source".

    Ye naam data badalne pe bhi wahi rehta hai, kyunki jagah wahi
    rehti hai. Aur padhne mein bhi matlab rakhta hai.
    -----------------------------------------------------------------
    """
    # har point ko degrees mein laao (naam lat/lon se banega)
    latlon = df.to_crs(CRS_LATLON)
    tmp = pd.DataFrame({
        "cluster": df["_cluster"].values,
        "noise": df["is_noise"].values,
        "lon": latlon.geometry.x.values,
        "lat": latlon.geometry.y.values,
    })

    def name(lat, lon):
        # 4 dashamlav = lagbhag 11 metre - itna kaafi hai alag pehchan ke liye
        return f"{region_name}_{lat:.4f}_{lon:.4f}"

    # ---- cluster wale points ----
    # Ek cluster ke SAARE points ko EK HI naam milna chahiye - wahi to
    # baat hai, wo sab milkar ek source hain. Naam cluster ke beech ke
    # point se banta hai.
    centre = tmp[~tmp.noise].groupby("cluster")[["lon", "lat"]].mean()
    cluster_name = {c: name(r.lat, r.lon) for c, r in centre.iterrows()}

    # ---- akele (noise) points ----
    # Inme se har ek apna alag source hai, isliye har ek ko apna naam.
    # Do akele points 11 metre ke andar ho sakte hain - tab naam takrayega,
    # to peeche number laga dete hain. Ye SIRF noise pe karna hai; clusters
    # pe karte to ek cluster tut kar kai sources ban jata.
    used = set(cluster_name.values())
    ids = []
    for row in tmp.itertuples():
        if not row.noise:
            ids.append(cluster_name[row.cluster])
            continue
        base = name(row.lat, row.lon)
        candidate, k = base, 0
        while candidate in used:
            k += 1
            candidate = f"{base}_{k}"
        used.add(candidate)
        ids.append(candidate)

    return ids


# ===============================================================
# Step B - har cluster ko ek row mein nichodna
# ===============================================================
def _static_ratio(group):
    """NASA ne kitne detections ko "static land source" kaha (firms_type=2)."""
    if "firms_type" not in group.columns:
        return -1.0
    known = group["firms_type"].dropna()
    if len(known) == 0:
        return -1.0          # NRT-only source - NASA ne kuch kaha hi nahi
    return round((known == 2).mean(), 4)


def _temporal_shape(dates):
    """
    Source ka WAQT ka AAKAAR - "kab-kab dikha" ki shakal.

    Ye teen numbers RULES se bilkul azaad hain. step4 ke koi bhi rule
    inhe nahi dekhta. Isliye model ko yahan kuch NAYA milta hai -
    warna wo sirf rules ki nakal utaarta hai (naapa gaya: 16,516 mein
    se 16,516 pe model aur rule ka jawab EK JAISA tha).

    Idea seedha hai:
        aag    = EK ghatna. Shuru hoti hai, jalti hai, khatam.
                 -> lagatar dinon ka ek guchha, phir chup.
        machine = ghatna nahi, AADAT. Beech-beech mein dikhti rehti hai.
                 -> bikhre huey din, be-tarteeb faasle.

    Gold labels pe naapa gaya:
        gap_cv      INDUSTRIAL 1.16  vs  FOREST_FIRE 0.40
        burst_frac  INDUSTRIAL 0.29  vs  FOREST_FIRE 0.74

    Jis source ka sirf EK din hai uspe ye teeno bemaani hain - wahan
    -1 daalte hain ("pata nahi"), 0 se alag. XGBoost -1 ko apne aap
    alag category ki tarah handle kar leta hai.
    """
    days = np.sort(pd.to_datetime(pd.Series(dates)).dt.normalize().unique())
    if len(days) < 2:
        return -1.0, -1.0, -1.0

    gaps = np.diff(days).astype("timedelta64[D]").astype(int)

    # gap_cv - faasle kitne BE-TARTEEB hain.
    #   0.0 = har baar barabar faasle pe dikha (regular)
    #   1.5 = kabhi agle din, kabhi do mahine baad (be-tarteeb)
    gap_cv = gaps.std() / gaps.mean() if gaps.mean() > 0 else 0.0

    # burst_frac - sabse lambi LAGATAR chain kitne hisse ki hai.
    #   1.0 = saare din ek hi guchhe mein the (ek hi aag)
    #   0.2 = din poore saal mein bikhre huey the (machine)
    # 3 din tak ka faasla "lagatar" hi maana - VIIRS roz nahi dikhta
    # (baadal, orbit) to 1-2 din chhoot jana normal hai.
    runs, cur = [], 1
    for g in gaps:
        if g <= 3:
            cur += 1
        else:
            runs.append(cur)
            cur = 1
    runs.append(cur)
    burst_frac = max(runs) / len(days)

    # max_gap_days - sabse lambi CHUPPI.
    # Aag khatam ho kar chali jati hai. Factory band ho kar phir chalti hai.
    max_gap_days = int(gaps.max())

    return round(float(gap_cv), 4), round(float(burst_frac), 4), max_gap_days


def summarise_source(group):
    """
    Ek source ke saare detections lekar uska "character" nikalta hai.

    Yahi wo numbers hain jinse aage model seekhega ki kaunsa source
    factory hai aur kaunsa aag.
    """
    dates = pd.to_datetime(group["acq_date"])
    first_seen = dates.min()
    last_seen = dates.max()

    # kitne din ke faasle mein ye source dikha
    lifespan_days = int((last_seen - first_seen).days)

    # kitne ALAG dinon mein dikha (ek din mein 5 baar dikhe to bhi 1 din)
    n_days = int(dates.dt.date.nunique())

    # activity_ratio = kitna REGULAR tha
    #   1.0  = jitne din ke andar dikha, har din dikha (factory jaisa)
    #   0.05 = 200 din ke andar sirf 10 din dikha (kabhi-kabhaar)
    # +1 isliye kyunki ek hi din wale source ka lifespan 0 hota hai,
    # aur 0 se divide nahi kar sakte.
    activity_ratio = n_days / (lifespan_days + 1)

    # waqt ka aakaar - rules se azaad teen features (upar dekho)
    gap_cv, burst_frac, max_gap_days = _temporal_shape(dates)

    frp = group["frp"]
    return pd.Series({
        "region": group["region"].iloc[0],
        "n_detections": len(group),
        "n_days": n_days,
        "first_seen": first_seen.date().isoformat(),
        "last_seen": last_seen.date().isoformat(),
        "lifespan_days": lifespan_days,
        "activity_ratio": round(activity_ratio, 4),

        # ---- waqt ka aakaar - KOI RULE inhe nahi dekhta ----
        "gap_cv": gap_cv,               # faasle kitne be-tarteeb
        "burst_frac": burst_frac,       # sabse lambi lagatar chain ka hissa
        "max_gap_days": max_gap_days,   # sabse lambi chuppi

        # night_ratio = kitne detections raat ke the
        #   factory ka flare raat-din jalta hai       -> ~0.5
        #   kisan din mein aag lagata hai             -> ~0.0
        # Ye sabse kaam ka feature hai dono ko alag karne ke liye.
        "night_ratio": round(group["is_night"].mean(), 4),

        # -----------------------------------------------------------
        # static_ratio = NASA KHUD kitne detections ko "static land
        # source" (firms_type = 2) keh raha hai.
        #
        # FIRMS ka type column: 0 = vegetation fire, 1 = volcano,
        # 2 = other STATIC land source (yani industrial), 3 = offshore.
        #
        # Ye NASA ka apna classification hai - hamare rules se bilkul
        # AZAAD. Data mein type=2 wale 90% RAAT ke hain (type=0 wale
        # sirf 22%) aur lagbhag saare Korba/Singrauli/Jamnagar mein.
        #
        # DHYAN: NOAA-21 ka NRT product ye column deta hi nahi (NaN
        # aata hai). Isliye average sirf un detections pe lete hain
        # jinpe value maujood hai. Agar kisi source pe ek bhi value
        # na ho to -1 (matlab "pata nahi", 0 se alag).
        # -----------------------------------------------------------
        "static_ratio": _static_ratio(group),

        "frp_mean": round(frp.mean(), 3),
        "frp_median": round(frp.median(), 3),
        "frp_max": round(frp.max(), 3),
        # ek hi detection wale source ka std NaN aata hai -> 0 kar do
        "frp_std": round(frp.std(), 3) if len(frp) > 1 else 0.0,

        "dist_to_industry_m": round(group["dist_to_industry_m"].median(), 1),
        "industry_type": mode_or_none(group["industry_type"]),
        "industry_name": mode_or_none(group["industry_name"]),
        "lc_class": mode_or_none(group["lc_class"]) or "unknown",

        # cluster ka beech ka point - map pe yahi dikhega
        "lon": group.geometry.x.mean(),
        "lat": group.geometry.y.mean(),

        "n_months": int(dates.dt.month.nunique()),
        "peak_month": int(dates.dt.month.mode().iloc[0]),
    })


def mode_or_none(series):
    """
    Sabse zyada baar aane wali value.
    Jaise ek cluster ke 10 points mein se 8 'forest' pe hain -> 'forest'.
    """
    s = series.dropna()
    if len(s) == 0:
        return None
    return s.mode().iloc[0]


# ===============================================================
# Step C - har source ko tier dena
# ===============================================================
def persistence_tier(row):
    """
    Source ko teen mein se ek tier deta hai. Yahi project ka core idea hai.

      PERSISTENT - mahinon tak dikha AUR kai alag dinon mein dikha
                   -> chalti hui factory ka pattern
      EPISODIC   - kuch hi din mein shuru aur khatam
                   -> ek aag ki ghatna (jungle ya khet)
      OTHER      - beech ka. Seasonal cheezein yahan aati hain
                   (jaise brick kiln jo 6 mahine chalta hai)

    Dono shart kyun: sirf lifespan dekhein to "Jan mein ek baar,
    Dec mein ek baar" wala source bhi PERSISTENT ban jata - jabki
    wo do alag ghatnayein thi, ek chalta hua source nahi.

    (config.py mein likha hai ki plan wala activity_ratio threshold
     kyun hataya gaya - wo satellite ka revisit rate naap raha tha.)
    """
    if (row["lifespan_days"] > PERSISTENT_MIN_LIFESPAN
            and row["n_days"] >= PERSISTENT_MIN_DAYS):
        return "PERSISTENT"
    if row["lifespan_days"] <= EPISODIC_MAX_LIFESPAN:
        return "EPISODIC"
    return "OTHER"


# ===============================================================
# Main
# ===============================================================
def main():
    features_path = DATA_PROCESSED / "features.gpkg"
    if not features_path.exists():
        print("ERROR: features.gpkg nahi mili.")
        print("  pehle ye chalao: python src/step2_context.py")
        sys.exit(1)

    # metre wale CRS mein padho - DBSCAN ko metres chahiye
    feat = gpd.read_file(features_path).to_crs(CRS_METRES)
    print(f"load: {len(feat)} detections\n")

    print(f"DBSCAN clustering (eps={DBSCAN_EPS} m, min_samples={DBSCAN_MIN_SAMPLES}):")
    labelled = pd.concat(
        [cluster_one_region(feat[feat["region"] == r], r)
         for r in feat["region"].unique()],
        ignore_index=True,
    )
    labelled = gpd.GeoDataFrame(labelled, geometry="geometry", crs=CRS_METRES)

    # ---- detection-level file save karo (Phase 3 ke liye) ----
    det_out = DATA_PROCESSED / "detections.gpkg"
    labelled.to_crs(CRS_LATLON).to_file(det_out, driver="GPKG")
    print(f"SAVED: {det_out}  ({len(labelled)} detections + source_id)")

    # ---- har source ko ek row mein nichodo ----
    print("\nsources banaye ja rahe hain...")
    sources = (labelled.groupby("source_id", group_keys=True)
                       .apply(summarise_source, include_groups=False)
                       .reset_index())

    sources["persistence_tier"] = sources.apply(persistence_tier, axis=1)

    # centroid se geometry banao, aur wapas degrees mein save karo
    gdf = gpd.GeoDataFrame(
        sources,
        geometry=gpd.points_from_xy(sources["lon"], sources["lat"]),
        crs=CRS_METRES,
    ).to_crs(CRS_LATLON)

    # lon/lat columns ko degrees wale numbers se badal do (QGIS mein padhne ke liye)
    gdf["lon"] = gdf.geometry.x.round(6)
    gdf["lat"] = gdf.geometry.y.round(6)

    out = DATA_PROCESSED / "sources.gpkg"
    gdf.to_file(out, driver="GPKG")
    print(f"\nSAVED: {out}  ({len(gdf)} sources)")

    report(gdf, len(feat))
    return gdf


def report(gdf, n_detections):
    """Screen pe wo sab dikhao jo check karne layak hai."""
    print("\n" + "=" * 68)
    print(f"{n_detections:,} raw detections  ->  {len(gdf):,} sources")
    print("=" * 68)

    print("\ntier ke hisaab se (region-wise):")
    table = pd.crosstab(gdf["region"], gdf["persistence_tier"])
    print(table.to_string())

    print("\nEXPECTED: Jamnagar mein PERSISTENT hone chahiye,")
    print("          Uttarakhand/Punjab mein EPISODIC.")

    persistent = gdf[gdf["persistence_tier"] == "PERSISTENT"]
    if len(persistent) == 0:
        print("\n!! Ek bhi PERSISTENT source nahi mila - kuch galat hai.")
        return

    print("\n" + "-" * 68)
    print(f"TOP 20 PERSISTENT SOURCES  (kul {len(persistent)})")
    print("-" * 68)
    top = persistent.nlargest(20, "n_detections")
    print(f"{'industry_name':<28}{'det':>5}{'days':>6}{'life':>6}{'act':>6}{'night':>7}")
    for _, r in top.iterrows():
        name = str(r["industry_name"] or "-")[:27]
        print(f"{name:<28}{r['n_detections']:>5}{r['n_days']:>6}"
              f"{r['lifespan_days']:>6}{r['activity_ratio']:>6.2f}"
              f"{r['night_ratio']:>7.2f}")

    print("\nagar upar ASLI factory ke naam dikh rahe hain -> project kaam kar raha hai")
    print("\nAgla step: python src/step4_labels.py  (Phase 3)")


if __name__ == "__main__":
    main()
