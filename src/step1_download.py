"""
STEP 1 - NASA FIRMS se garam points (hotspots) download karna.

Input : kuch nahi (bas internet + .env mein FIRMS_MAP_KEY)
Output: data/raw/*.csv          (har 10-din ka ek chunk)
        data/processed/hotspots.gpkg   (sab jodkar ek file)

Chalane ka tareeka:
    python src/step1_download.py
"""
import os
import time
from datetime import date, timedelta

import pandas as pd
import geopandas as gpd
import requests
from dotenv import load_dotenv

from config import (REGIONS, START, END, DATA_RAW, DATA_PROCESSED,
                    CRS_LATLON, FIRMS_SOURCES)

# .env file se FIRMS_MAP_KEY padho (key ko code mein kabhi mat likhna)
load_dotenv()
MAP_KEY = os.getenv("FIRMS_MAP_KEY")

# FIRMS API ek request mein zyada se zyada 5 din de sakta hai.
# (Purane docs 10 din kehte hain - ab galat hai, API "Invalid day
#  range. Expects [1..5]" bhejta hai. Isliye 5.)
# Pure saal ko 5-5 din ke tukdon mein todenge.
CHUNK_DAYS = 5

# Kaunse satellite - config.py mein list hai, wahan wajah bhi likhi hai.
# Pehle hum sirf EK satellite lete the aur baaki chhod dete the. Ab
# TEENO ka data lete hain aur jod dete hain - 3 guna zyada detections,
# aur 3 guna zyada chakkar.
#
# Agar koi source kaam na kare to uske badle ye try karenge:
FALLBACK = {
    "VIIRS_SNPP_SP": "VIIRS_SNPP_NRT",
    "VIIRS_NOAA20_SP": "VIIRS_NOAA20_NRT",
}

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def build_url(source, bbox, days, start_date):
    """
    FIRMS ka URL banata hai.
    bbox ka order (west, south, east, north) hai - yani longitude pehle.
    Ye order galat hua to points samundar mein ya duniya ke doosre kone
    mein dikhenge. Sabse common bug yahi hai.
    """
    west, south, east, north = bbox
    return f"{BASE_URL}/{MAP_KEY}/{source}/{west},{south},{east},{north}/{days}/{start_date}"


def looks_like_error(text):
    """
    FIRMS error hone par bhi HTTP 200 bhejta hai, par body mein CSV ke
    bajaye error message hota hai. Isliye content khud check karna padta hai.
    Sahi CSV ki pehli line hamesha 'latitude' se shuru hoti hai.
    """
    if text is None:
        return True
    head = text.strip()[:200].lower()
    if head == "":
        return True                       # bilkul khaali response
    if not head.startswith("latitude"):   # header hi nahi hai -> error message hai
        return True
    return False


def download_chunk(source, region_name, bbox, start_date, days):
    """
    Ek region ka ek 10-din ka tukda download karta hai.
    Agar file pehle se hai to download SKIP kar deta hai (rerun tez rahe).

    Return: (file ka path ya None, network use hua ya nahi)
    Doosri value isliye chahiye kyunki rate-limit wali sleep sirf tab
    honi chahiye jab sach mein request bheji ho. Cached file pe bhi
    sleep karenge to rerun 4 minute le lega - poora point hi khatam.
    """
    out_path = DATA_RAW / f"{region_name}_{source}_{start_date}_{days}d.csv"

    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path, False   # pehle se downloaded hai, dobara mat maango

    url = build_url(source, bbox, days, start_date)
    try:
        resp = requests.get(url, timeout=120)
    except requests.RequestException as e:
        print(f"    [network fail] {region_name} {start_date}: {e}")
        return None, True

    if resp.status_code != 200:
        print(f"    [HTTP {resp.status_code}] {region_name} {start_date}")
        return None, True

    if looks_like_error(resp.text):
        # pehla 120 characters dikha do taaki asli wajah pata chale
        print(f"    [bad response] {region_name} {start_date}: {resp.text.strip()[:120]!r}")
        return None, True

    out_path.write_text(resp.text)
    return out_path, True


def rows_in(path):
    """CSV mein kitni data rows hain (header chhodkar)."""
    if path is None or not path.exists():
        return 0
    df = pd.read_csv(path)
    return len(df)


def pick_working_source(bbox, wanted):
    """
    Ek satellite ka source name check karo ki wo sach mein data de raha
    hai ya nahi. Na de to uska NRT wala bhai try karo.

    Dhyan do: header hone se kaam nahi chalta. NRT sirf pichhle ~2 mahine
    ka data rakhta hai, to purana saal maangne pe wo khaali CSV (sirf
    header) bhejta hai - koi error nahi. Isliye ROWS ginte hain, na ki
    bas "error to nahi aaya" dekhte hain.

    -----------------------------------------------------------------
    TEEN window kyun test karte hain (ye ek BUG ka fix hai):

    Pehle sirf EK window test hota tha - START se CHUNK_DAYS din.
    START = 1 January. Punjab mein January mein parali jalti hi nahi
    (wo Oct-Nov aur April-May mein jalti hai). To NOAA-21 ne 0 rows
    bheje, code ne samjha "ye satellite kaam nahi karta", aur POORE
    SAAL ka Punjab N21 data skip ho gaya - 0 files.

    Baaki regions mein January mein bhi aag thi (Korba ki coal mines
    saal bhar jalti hain), isliye wahan bug dikha hi nahi.

    Galti ye thi: "is window mein aag nahi lagi" ko "ye satellite data
    hi nahi deta" samajh liya. Ab teen alag mausam test karte hain -
    kisi EK mein bhi rows mil gayi to source theek hai.
    -----------------------------------------------------------------
    """
    candidates = [wanted]
    if wanted in FALLBACK:
        candidates.append(FALLBACK[wanted])

    # saal ke teen alag mausam - kisi ek mein bhi aag mili to kaafi hai
    year = START[:4]
    probes = [START, f"{year}-05-01", f"{year}-11-01"]

    for source in candidates:
        print(f"  source '{source}' test kar rahe hain...")
        failed = False
        for probe in probes:
            url = build_url(source, bbox, CHUNK_DAYS, probe)
            try:
                resp = requests.get(url, timeout=120)
            except requests.RequestException as e:
                print(f"    network problem ({probe}): {e}")
                continue
            if resp.status_code != 200 or looks_like_error(resp.text):
                print(f"    '{source}' ne data nahi diya: "
                      f"{resp.text.strip()[:120]!r}")
                failed = True
                break
            n_rows = len(resp.text.strip().splitlines()) - 1
            if n_rows > 0:
                print(f"  -> '{source}' chal raha hai "
                      f"({probe} window mein {n_rows} rows)")
                return source
        if not failed:
            print(f"    '{source}' teeno window mein khaali - agla try karte hain")
    return None


def date_chunks(start_str, end_str, chunk_days):
    """
    START se END tak 10-10 din ke tukde banata hai.
    Har tukda: (start_date_string, number_of_days)
    Aakhri tukda chhota ho sakta hai.
    """
    start = date.fromisoformat(start_str)
    end = date.fromisoformat(end_str)
    chunks = []
    cur = start
    while cur <= end:
        # is tukde mein kitne din? END se aage mat jao
        days = min(chunk_days, (end - cur).days + 1)
        chunks.append((cur.isoformat(), days))
        cur = cur + timedelta(days=days)
    return chunks


def main():
    if not MAP_KEY:
        print("ERROR: FIRMS_MAP_KEY nahi mila.")
        print("  .env.example ko .env mein copy karo aur apni key paste karo.")
        print("  Key yahan se: https://firms.modaps.eosdis.nasa.gov/api/map_key/")
        return

    chunks = date_chunks(START, END, CHUNK_DAYS)
    print(f"{START} se {END} tak = {len(chunks)} tukde ({CHUNK_DAYS} din each)\n")

    all_frames = []   # har region ka DataFrame yahan jama hoga

    for region_name, bbox in REGIONS.items():
        print(f"=== {region_name.upper()}  bbox={bbox} ===")

        region_total = 0
        # ab har region ke liye TEENO satellite ka data lete hain
        for wanted in FIRMS_SOURCES:
            source = pick_working_source(bbox, wanted)
            if source is None:
                print(f"  !! {wanted} kaam nahi kiya, skip\n")
                continue

            sat_frames = []
            n_downloaded = 0
            for i, (start_date, days) in enumerate(chunks, start=1):
                path, used_network = download_chunk(
                    source, region_name, bbox, start_date, days
                )
                n = rows_in(path)

                if n > 0:
                    df = pd.read_csv(path)
                    sat_frames.append(df)

                if used_network:
                    n_downloaded += 1
                    time.sleep(1)   # FIRMS pe polite raho - 1 second gap

            if not sat_frames:
                print(f"  {source:18} ek bhi detection nahi")
                continue

            sat_df = pd.concat(sat_frames, ignore_index=True)
            sat_df["region"] = region_name
            # kaunse satellite se aaya - baad mein compare karne ke kaam aayega
            sat_df["product"] = source
            all_frames.append(sat_df)
            region_total += len(sat_df)
            print(f"  {source:18} {len(sat_df):>6} rows   "
                  f"({n_downloaded} naye, {len(chunks) - n_downloaded} cached)")

        print(f"  {region_name} total: {region_total} rows\n")

    if not all_frames:
        print("Kuch bhi download nahi hua. Upar ke error messages padho.")
        return

    combined = pd.concat(all_frames, ignore_index=True)

    # Ek hi detection do baar aa sakti hai (chunks ke overlap ya rerun se).
    #
    # DHYAN DO: 'product' bhi shaamil hai. Do alag satellite ek hi aag ko
    # dekh sakte hain - wo DO alag detections hain, duplicate nahi. Unhe
    # hatana galat hoga, kyunki "kitni baar dikha" hi hamara asli signal hai.
    before = len(combined)
    combined = combined.drop_duplicates(
        subset=["latitude", "longitude", "acq_date", "acq_time", "product"]
    ).reset_index(drop=True)
    print(f"Duplicates hataye: {before - len(combined)}")

    # -----------------------------------------------------------
    # FIRMS ka 'type' column BACHANA zaroori hai.
    #
    # Ye NASA ka apna classification hai:
    #     0 = presumed vegetation fire
    #     1 = active volcano
    #     2 = other STATIC land source   <-- yani INDUSTRIAL
    #     3 = offshore
    #
    # Ye seedha hamare kaam ka hai. Data mein: type=2 wale 83% RAAT
    # ke hain (type=0 wale sirf 21%), aur wo lagbhag saare Korba/
    # Singrauli/Jamnagar mein hain - yani hamare industrial regions.
    #
    # DIKKAT: GeoDataFrame banate hi 'type' column geometry ke type se
    # OVERWRITE ho jata hai (sab "Point" ban jata hai) aur NASA ka
    # signal chup-chaap gayab ho jata hai. Isliye pehle rename.
    # -----------------------------------------------------------
    if "type" in combined.columns:
        combined = combined.rename(columns={"type": "firms_type"})

    # DataFrame -> GeoDataFrame. Har row ka ek Point banega.
    # CRS 4326 = degrees. Yahan distance mat nikalna, wo Day 2 mein 32643 pe hoga.
    gdf = gpd.GeoDataFrame(
        combined,
        geometry=gpd.points_from_xy(combined["longitude"], combined["latitude"]),
        crs=CRS_LATLON,
    )

    out = DATA_PROCESSED / "hotspots.gpkg"
    gdf.to_file(out, driver="GPKG")

    # ---------------- Summary ----------------
    print("\n" + "=" * 50)
    print(f"SAVED: {out}  ({out.stat().st_size / 1e6:.1f} MB)")
    print(f"Total rows      : {len(gdf)}")
    print("\nRows per region:")
    print(gdf["region"].value_counts().to_string())
    print("\nRows per satellite:")
    print(gdf["product"].value_counts().to_string())
    print(f"\nDate range      : {gdf['acq_date'].min()}  se  {gdf['acq_date'].max()}")
    print("\nFRP stats (fire radiative power, MW):")
    print(gdf["frp"].describe().to_string())
    print("=" * 50)
    print("\nAb QGIS kholo aur hotspots.gpkg drag karke daalo.")


if __name__ == "__main__":
    main()
