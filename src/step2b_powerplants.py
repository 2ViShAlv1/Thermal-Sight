"""
STEP 2b - asli power plants, WRI ke database se.

--------------------------------------------------------------------
YE KYUN CHAHIYE

Ab tak "factory kahan hai" ka jawab sirf OpenStreetMap se aa raha tha.
OSM achha hai par adhoora - kaun sa plant map hua hai aur kaun nahi,
ye us jagah ke logon pe depend karta hai.

WRI (World Resources Institute) ka Global Power Plant Database ek
banaya hua, jaancha hua database hai. India ke 1,589 plants isme hain,
har ek ke saath:
    - theek coordinates
    - kaun sa fuel jalta hai (coal / gas / solar / wind / hydro)
    - kitni capacity (MW)

FUEL TYPE SABSE KAAM KI CHEEZ HAI.

Solar aur wind plants BILKUL GARMI NAHI DETE - satellite unhe kabhi
nahi dekhega. Coal, gas, oil, biomass dete hain. OSM sirf "power=plant"
likhta hai, ye nahi batata ki wo solar hai ya coal.

Agar hum solar farm ko bhi "industry" maan lete, to uske paas wali
khet ki aag galti se INDUSTRIAL ban jaati.

Isliye yahan sirf THERMAL plants lete hain.
--------------------------------------------------------------------

Input : internet (ek CSV, ~12 MB - script khud download karti hai)
Output: data/processed/industry.gpkg mein power plants jud jaate hain

Chalane ka tareeka (step2_context.py ke BAAD):
    python src/step2b_powerplants.py
"""
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

from config import (DATA_RAW, DATA_PROCESSED, REGIONS,
                    CRS_LATLON, CRS_METRES)

CSV_URL = ("https://raw.githubusercontent.com/wri/global-power-plant-database/"
           "master/output_database/global_power_plant_database.csv")

# Sirf ye fuel garmi dete hain jo VIIRS dekh sakta hai.
# Solar, Wind, Hydro, Nuclear jaan-boojh kar CHHODE hain -
# unse aisi garmi nahi nikalti jo satellite pakad sake.
THERMAL_FUELS = ["Coal", "Gas", "Oil", "Biomass", "Petcoke", "Cogeneration"]


def download_database():
    """WRI ka CSV download karo (ek baar, phir cache se)."""
    path = DATA_RAW / "global_power_plant_database.csv"
    if path.exists() and path.stat().st_size > 1_000_000:
        print(f"  pehle se hai ({path.stat().st_size / 1e6:.0f} MB)")
        return path

    print("  download ho raha hai (~12 MB)...")
    try:
        r = requests.get(CSV_URL, timeout=300)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  download fail: {e}")
        return None
    path.write_bytes(r.content)
    print(f"  ho gaya ({path.stat().st_size / 1e6:.0f} MB)")
    return path


def plant_radius_m(capacity_mw):
    """
    Plant ke aas-paas kitna ghera maanein.

    Database mein sirf EK point hota hai - plant ka beech. Par ek 4,000 MW
    ka plant zameen pe 2-3 kilometre faila hota hai! Uske kone pe hui
    detection ka distance "0" nahi aayega agar hum sirf point rakhein.

    Isliye capacity ke hisaab se ghera banate hain. Bada plant = bada ghera.
    Formula mota-mota hai, par point rakhne se kahin behtar.
    """
    cap = np.clip(capacity_mw.fillna(50), 10, 6000)
    return 300 + 15 * np.sqrt(cap)      # 100MW -> 450m,  4600MW -> 1320m


def main():
    print("WRI Global Power Plant Database:")
    csv_path = download_database()
    if csv_path is None:
        sys.exit(1)

    df = pd.read_csv(csv_path, low_memory=False)
    india = df[df["country"] == "IND"]
    print(f"  India mein kul plants     : {len(india):,}")

    thermal = india[india["primary_fuel"].isin(THERMAL_FUELS)].copy()
    print(f"  inme se THERMAL (garmi dene wale): {len(thermal)}")
    print(f"  (solar/wind/hydro/nuclear chhode: {len(india) - len(thermal)})")
    print("\n  fuel ke hisaab se:")
    for fuel, n in thermal["primary_fuel"].value_counts().items():
        mw = thermal.loc[thermal["primary_fuel"] == fuel, "capacity_mw"].sum()
        print(f"    {fuel:<12} {n:>4}  ({mw:>9,.0f} MW)")

    # ---- sirf hamare regions ke andar wale ----
    keep = []
    print("\n  hamare regions mein:")
    for name, (w, s, e, n) in REGIONS.items():
        sub = thermal[thermal["longitude"].between(w, e)
                      & thermal["latitude"].between(s, n)].copy()
        if len(sub) == 0:
            print(f"    {name:<12} 0 plants")
            continue
        sub["region"] = name
        keep.append(sub)
        print(f"    {name:<12} {len(sub):>3} plants  "
              f"({sub['capacity_mw'].sum():>8,.0f} MW)")

    if not keep:
        print("\n  kisi region mein koi thermal plant nahi mila")
        sys.exit(1)

    plants = pd.concat(keep, ignore_index=True)

    # ---- point -> ghera (polygon) ----
    gdf = gpd.GeoDataFrame(
        plants,
        geometry=gpd.points_from_xy(plants["longitude"], plants["latitude"]),
        crs=CRS_LATLON,
    ).to_crs(CRS_METRES)

    gdf["geometry"] = gdf.geometry.buffer(plant_radius_m(gdf["capacity_mw"]))
    gdf = gdf.to_crs(CRS_LATLON)

    # ---- industry.gpkg jaise columns bana do ----
    out = gpd.GeoDataFrame({
        "osm_id": "wri_" + gdf["gppd_idnr"].astype(str),
        "name": gdf["name"],
        "industry_type": "power_plant",
        "region": gdf["region"],
        # do NAYE features jo OSM kabhi nahi de sakta
        "capacity_mw": gdf["capacity_mw"],
        "primary_fuel": gdf["primary_fuel"],
        "geometry": gdf.geometry,
    }, crs=CRS_LATLON)

    # ---- purani industry.gpkg mein jodo ----
    ind_path = DATA_PROCESSED / "industry.gpkg"
    if not ind_path.exists():
        print("\nERROR: industry.gpkg nahi mili.")
        print("  pehle ye chalao: python src/step2_context.py")
        sys.exit(1)

    osm = gpd.read_file(ind_path)
    # dobara chalane pe purane WRI wale hata do, warna wo do baar aa jayenge
    osm = osm[~osm["osm_id"].astype(str).str.startswith("wri_")]

    combined = gpd.GeoDataFrame(
        pd.concat([osm, out], ignore_index=True), crs=CRS_LATLON
    )
    combined.to_file(ind_path, driver="GPKG")

    print(f"\nSAVED: {ind_path}")
    print(f"  OSM se        : {len(osm):>5}")
    print(f"  WRI se (naye) : {len(out):>5}")
    print(f"  kul           : {len(combined):>5}")
    print("\n  region ke hisaab se WRI ke plants:")
    print(out.groupby("region").size().to_string())
    print("\nAgla step: python src/step2_context.py --skip-part1")
    print("           (taaki naye plants ke saath distance dobara nikle)")


if __name__ == "__main__":
    main()
