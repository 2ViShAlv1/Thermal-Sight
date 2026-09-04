"""
Gold labels ko jagah ke hisaab se dobara jodo.

--------------------------------------------------------------------
YE KYUN CHAHIYE

source_id sirf ek ginti thi - "jamnagar_n335" ka matlab "Jamnagar ka
335va akela point". Jab humne data badla (1 satellite se 3), to saare
clusters naye sire se bane aur poori numbering hil gayi.

Natija: ID to wahi rahi, par ab wo KISI AUR jagah ko bata rahi hai.

Par tumne label lagate waqt JAGAH dekhi thi, ID nahi. Tumne satellite
photo dekh kar kaha tha "yahan jungle hai". Wo baat aaj bhi sach hai -
bas usse naye source se jodna hai.

Isliye ye script har purani jagah ke sabse NAZDEEK naya source
dhoondhta hai. Agar wo 500 metre ke andar mila, to wahi jagah maani
jayegi aur label us par chipak jayega.

Aur ab gold_labels.csv mein lat/lon BHI save karte hain - taaki
agli baar data badle to ye dobara na tootey.
--------------------------------------------------------------------

    python src/rescue_gold_labels.py
"""
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

from config import DATA_PROCESSED, OUTPUTS, CRS_LATLON, CRS_METRES

# itne metre ke andar ka source "wahi jagah" maana jayega.
# 500 rakha hai kyunki DBSCAN ka eps bhi 500 hai - yani isse zyada
# door ka point waise bhi alag source hi hota.
MATCH_RADIUS_M = 500


def old_positions():
    """
    Purani jagah kahan se milegi.

    gold_50_TO_FILL.csv mein Google Maps ke link the, aur unke andar
    lat/lon likha hota hai. Wahin se nikaal lete hain.
    """
    path = OUTPUTS / "gold_50_TO_FILL.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    ll = df["google_maps"].str.extract(r"@([\d.\-]+),([\d.\-]+),").astype(float)
    return pd.DataFrame({"source_id": df["source_id"],
                         "lat": ll[0], "lon": ll[1]})


def main():
    gold_path = DATA_PROCESSED / "gold_labels.csv"
    if not gold_path.exists():
        print("gold_labels.csv nahi mili - kuch bachane ko nahi")
        sys.exit(1)

    gold = pd.read_csv(gold_path)
    if "notes" not in gold.columns:
        gold["notes"] = ""

    # agar lat/lon pehle se hain to badhiya, warna purani file se laao
    if "lat" not in gold.columns:
        pos = old_positions()
        if pos is None:
            print("ERROR: purani jagah kahin nahi mili")
            sys.exit(1)
        gold = gold.merge(pos, on="source_id", how="left")
        gold = gold.rename(columns={"source_id": "old_source_id"})

    missing = gold["lat"].isna().sum()
    if missing:
        print(f"  ! {missing} ki jagah nahi mili, unhe chhod rahe hain")
        gold = gold.dropna(subset=["lat", "lon"])

    # ---- naye sources se milao ----
    sources = gpd.read_file(DATA_PROCESSED / "sources_labelled.gpkg")

    # purani source_id hata do - warna sjoin ke baad do 'source_id'
    # column ban jate hain aur naam takra jaate hain
    gold = gold.drop(columns=["source_id", "match_dist_m"], errors="ignore")

    gold_gdf = gpd.GeoDataFrame(
        gold,
        geometry=gpd.points_from_xy(gold["lon"], gold["lat"]),
        crs=CRS_LATLON,
    ).to_crs(CRS_METRES)

    matched = gpd.sjoin_nearest(
        gold_gdf,
        sources[["source_id", "geometry"]].to_crs(CRS_METRES),
        how="left",
        distance_col="match_dist_m",
    )
    matched = matched[~matched.index.duplicated(keep="first")]

    good = matched[matched["match_dist_m"] <= MATCH_RADIUS_M]
    lost = matched[matched["match_dist_m"] > MATCH_RADIUS_M]

    print(f"{len(matched)} gold labels ko naye sources se jodne ki koshish:\n")
    print(f"  jud gaye ({MATCH_RADIUS_M} m ke andar) : {len(good)}")
    print(f"  nahi jude                       : {len(lost)}")
    if len(good):
        print(f"\n  jo jude, unka median fasla: {good['match_dist_m'].median():.0f} m")

    if len(lost):
        print(f"\n  jo nahi jude (naye data mein wahan koi source nahi bana):")
        print(lost[["gold_label", "lat", "lon", "match_dist_m"]]
              .round(4).to_string(index=False))

    # ---- save: ab lat/lon BHI save karo ----
    out = good[["source_id", "gold_label", "notes", "lat", "lon",
                "match_dist_m"]].copy()
    out.to_csv(gold_path, index=False)
    print(f"\nSAVED: {gold_path}")
    print("  (ab isme lat/lon bhi hai - agli baar data badle to")
    print("   ye script phir se jod degi, kaam dobara nahi karna padega)")

    print("\nlabels ab:")
    print(out["gold_label"].value_counts().to_string())


if __name__ == "__main__":
    main()
