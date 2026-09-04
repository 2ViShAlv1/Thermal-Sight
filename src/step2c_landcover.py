"""
STEP 2c - asli landcover, ESA WorldCover se.

--------------------------------------------------------------------
YE KYUN BANAYA

Ab tak zameen ka type OpenStreetMap se aa raha tha. Problem: OSM par
log sadak aur building to map karte hain, khet aur jungle nahi.

Natija: hamare 6,010 sources mein se 82% ka lc_class "unknown" tha.
Aur tumhare 50 gold labels ne saabit kiya ki rules ki sabse badi
galti (4 mein se 4) bilkul isi wajah se hui thi - OSM par wo jungle
mapped hi nahi tha, isliye "jungle pe nahi hai" wali shart pass ho
gayi aur khet wala rule chal pada.

ESA WorldCover ek SATELLITE se bani hui tasveer hai jisme poori
duniya ki har 10x10 metre ki jagah pe likha hai wahan kya hai.
Koi insaan ne nahi banaya - satellite ne dekha aur likh diya.
Isliye usme "unknown" hota hi nahi.

Free hai, bina login ke download ho jaati hai.
--------------------------------------------------------------------

Input : data/processed/features.gpkg
        data/raw/worldcover/*.tif  (script khud download kar leta hai)
Output: wahi features.gpkg, par ab lc_class ASLI hai

Chalane ka tareeka:
    python src/step2c_landcover.py
"""
import math
import sys

import geopandas as gpd
import rasterio
import requests
from rasterio.sample import sample_gen

from config import DATA_RAW, DATA_PROCESSED, CRS_LATLON, REGIONS

WC_DIR = DATA_RAW / "worldcover"
BASE_URL = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
            "v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif")

# ESA WorldCover ke apne code -> hamare 3 naam
#
# Humein sirf teen cheezein chahiye: forest, cropland, urban.
# Baaki (paani, ghaas, jhaadi, khaali zameen) ko "other" keh dete hain -
# wo hamare teen classes mein se kisi ka pakka ishara nahi dete.
WC_CLASSES = {
    10: "forest",      # Tree cover
    20: "other",       # Shrubland
    30: "other",       # Grassland
    40: "cropland",    # Cropland
    50: "urban",       # Built-up
    60: "other",       # Bare / sparse vegetation
    70: "other",       # Snow and ice
    80: "other",       # Permanent water
    90: "other",       # Herbaceous wetland
    95: "other",       # Mangroves
    100: "other",      # Moss and lichen
}


def tiles_for_bbox(west, south, east, north):
    """
    Bbox ke liye kaunsi WorldCover file chahiye.

    WorldCover ki har file 3 degree x 3 degree ki hai, aur uska naam
    uske NEECHE-BAAYEIN kone se banta hai. Jaise N21E069 ka matlab
    21 se 24 latitude, 69 se 72 longitude.

    Isliye kone ko 3 ke multiple pe neeche laate hain (floor).
    Ek bbox do ya chaar files pe faila ho sakta hai - saari chahiye.
    """
    tiles = set()
    lat = math.floor(south / 3) * 3
    while lat <= north:
        lon = math.floor(west / 3) * 3
        while lon <= east:
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            tiles.add(f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}")
            lon += 3
        lat += 3
    return sorted(tiles)


def download_tile(tile):
    """Ek WorldCover file download karo. Pehle se ho to skip."""
    WC_DIR.mkdir(parents=True, exist_ok=True)
    path = WC_DIR / f"{tile}.tif"
    if path.exists() and path.stat().st_size > 1_000_000:
        print(f"  {tile}  pehle se hai ({path.stat().st_size / 1e6:.0f} MB)")
        return path

    print(f"  {tile}  download ho rahi hai (~100 MB)...")
    try:
        with requests.get(BASE_URL.format(tile=tile), stream=True,
                          timeout=600) as r:
            if r.status_code != 200:
                print(f"    nahi mili (HTTP {r.status_code})")
                return None
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
    except requests.RequestException as e:
        print(f"    download fail: {e}")
        return None

    print(f"    ho gaya ({path.stat().st_size / 1e6:.0f} MB)")
    return path


def read_landcover(points_gdf, tile_paths):
    """
    Har point ke neeche WorldCover mein kya likha hai, wo padho.

    Ek point sirf EK tile mein hoga. Isliye har tile ke liye dekhte
    hain ki uske andar kaunse points aate hain, aur unhi ko padhte
    hain. Isse poori 100 MB ki file memory mein nahi aati.
    """
    values = {}                      # index -> class ka naam

    for path in tile_paths:
        with rasterio.open(path) as src:
            b = src.bounds
            inside = points_gdf.cx[b.left:b.right, b.bottom:b.top]
            if len(inside) == 0:
                continue

            coords = [(p.x, p.y) for p in inside.geometry]
            # rasterio ek-ek pixel padh leta hai, poori file nahi kholta
            for idx, val in zip(inside.index, src.sample(coords)):
                values[idx] = WC_CLASSES.get(int(val[0]), "other")

            print(f"  {path.stem}: {len(inside)} points padhe")

    return values


def main():
    path = DATA_PROCESSED / "features.gpkg"
    if not path.exists():
        print("ERROR: features.gpkg nahi mili.")
        print("  pehle ye chalao: python src/step2_context.py")
        sys.exit(1)

    feat = gpd.read_file(path).to_crs(CRS_LATLON)
    print(f"load: {len(feat)} detections\n")

    # ---- kaunsi tiles chahiye ----
    needed = set()
    for bbox in REGIONS.values():
        needed.update(tiles_for_bbox(*bbox))
    print(f"WorldCover tiles chahiye: {sorted(needed)}\n")

    tile_paths = []
    for tile in sorted(needed):
        p = download_tile(tile)
        if p:
            tile_paths.append(p)

    if not tile_paths:
        print("\nEk bhi tile nahi mili - purana lc_class hi rehne dete hain")
        sys.exit(1)

    # ---- padho ----
    print("\nlandcover padh rahe hain...")
    values = read_landcover(feat, tile_paths)

    # purana OSM wala rakh lo, taaki compare kar sakein
    feat["lc_class_osm"] = feat["lc_class"]
    feat["lc_class"] = feat.index.map(values).fillna("unknown")

    feat.to_file(path, driver="GPKG")
    print(f"\nSAVED: {path}")

    # ---- compare: OSM vs WorldCover ----
    print("\n" + "=" * 58)
    print("PEHLE (OSM se)  vs  AB (satellite se)")
    print("=" * 58)
    old = feat["lc_class_osm"].value_counts()
    new = feat["lc_class"].value_counts()
    for cls in sorted(set(old.index) | set(new.index)):
        o, n = old.get(cls, 0), new.get(cls, 0)
        print(f"  {cls:<10} {o:>6}  ->  {n:>6}")

    unknown_before = (feat["lc_class_osm"] == "unknown").mean() * 100
    unknown_after = (feat["lc_class"] == "unknown").mean() * 100
    print(f"\n  'unknown':  {unknown_before:.0f}%  ->  {unknown_after:.0f}%")

    print("\n  region ke hisaab se (ab):")
    for region in feat["region"].unique():
        sub = feat[feat["region"] == region]
        top = sub["lc_class"].value_counts(normalize=True).head(3)
        print(f"    {region:<13} " +
              ", ".join(f"{k} {v*100:.0f}%" for k, v in top.items()))

    print("\nAgla step: python src/step3_persistence.py  (dobara chalao)")


if __name__ == "__main__":
    main()
