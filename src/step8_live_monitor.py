"""
STEP 8 - LIVE monitoring. Pichhle N ghante ka data, turant classify.

--------------------------------------------------------------------
IDEA

NASA FIRMS ka NRT (Near Real-Time) feed ~3 ghante mein publish hota
hai. Ye script wahi feed maangta hai, aur dekhta hai:

  1. Jo naya hotspot dikha, kya wo kisi PEHLE SE JAANI-PEHCHANI jagah
     (500m ke andar) pe hai? Agar haan - us jagah ka pura itihaas
     (rules + model se banaya label) hamare paas pehle se hai, to
     turant confident jawab de sakte hain: "ye source abhi bhi active
     hai, aur ye [INDUSTRIAL/FOREST_FIRE/AGRI_BURN] hai."

  2. Agar BILKUL NAYI jagah hai (koi match nahi) - hamare paas uski
     koi history nahi hai. Persistence-based rules (jo poore project
     ka core hain) sirf TABHI kaam karte hain jab kai din/mahine ka
     data ho. Ek akela detection se "factory hai ya aag" nahi bataya
     ja sakta - isliye aisi jagah ko IMAANDARI se "NEW - abhi
     monitor ho raha hai" bolte hain, jhoota confident jawab nahi.

--------------------------------------------------------------------
YE "PREDICTION" NAHI HAI

Ye FOREST_FIRE hone se PEHLE nahi bata sakta (uske liye mausam/
vegetation-dryness data chahiye, jo humare paas nahi hai). Ye sirf
bata sakta hai: "abhi, is waqt, ye jagah garam hai, aur hamara
itihaas kehta hai ye [X] hai." Yani real-time DETECTION+CLASSIFICATION
hai, forecasting nahi.

Input : internet + .env mein FIRMS_MAP_KEY
        data/processed/sources_labelled.gpkg   (jaana-pehchana itihaas)
Output: data/processed/live_detections.gpkg
        terminal pe turant summary

Chalane ka tareeka:
    python src/step8_live_monitor.py                  # pichhle 3 ghante
    python src/step8_live_monitor.py --hours 6         # pichhle 6 ghante
    python src/step8_live_monitor.py --loop 900         # har 15 min chalta rahe
"""
import argparse
import json
import os
import smtplib
import sys
import time
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from io import StringIO

import geopandas as gpd
import pandas as pd
import requests
from dotenv import load_dotenv
from shapely.geometry import Point

from config import (REGIONS, LIVE_REFERENCE_REGIONS, DATA_PROCESSED, MODELS,
                    OUTPUTS, CRS_LATLON, CRS_METRES)
from step3_persistence import summarise_source, persistence_tier
from step5_train import build_X

load_dotenv()
MAP_KEY = os.getenv("FIRMS_MAP_KEY")

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# NRT sources - purane SP wale sirf kuch hafton purana data rakhte
# hain, aaj ka data sirf NRT variant mein aata hai.
NRT_SOURCES = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]

# Jaana-pehchana source maanne ke liye kitni doori tak dhoondhna hai.
# Yahi radius DBSCAN clustering mein bhi use hua tha (step3) - taaki
# "ek hi jagah" ki definition dono jagah same rahe.
MATCH_RADIUS_M = 500

# ---------------------------------------------------------------
# DISASTER ALERT
#
# VIIRS FRP (Fire Radiative Power, MW) ka rough scale: chhoti agri-burn
# aksar <10 MW, normal forest fire/industrial flare 10-50 MW. 50 MW se
# upar bahut kam detections hoti hain - wahi humara absolute floor hai.
# Iske saath-saath, agar koi jaani-pehchani jagah apne ab tak ke
# record (frp_max, itihaas se) se 1.5x zyada garam dikhe, wo bhi
# "kuch normal se bada ho raha hai" ka sanket hai, chaahe absolute
# FRP kam ho.
# ---------------------------------------------------------------
DISASTER_FRP_FLOOR = 50.0
DISASTER_SPIKE_MULT = 1.5
DISASTER_STATUSES = {"FOREST_FIRE", "INDUSTRIAL"}
ALERTS_LOG = OUTPUTS / "disaster_alerts.log"

# --loop mode mein har 15 min pe wahi 3-ghante ka NRT window dobara
# aata hai, to ek hi jalti hui aag baar-baar alert karegi (din mein 96
# baar). Isliye kaunsi source kab alert hui, wo yaad rakhte hain aur
# utne ghante tak chup rehte hain. Aag abhi bhi RESULT summary mein
# dikhti rahegi - sirf ALARM dobara nahi bajta.
ALERT_STATE = OUTPUTS / ".alert_state.json"
RE_ALERT_HOURS = 6

# ---------------------------------------------------------------
# EMAIL ALERT - disaster-level FRP mile to mail bhi jaye, sirf
# console/log tak seemit na rahe. Isi RE_ALERT_HOURS cooldown ka
# istemal karta hai jo upar console alert ke liye bhi hai - ek hi
# aag ke liye baar-baar mail nahi aayega.
#
# .env mein set karna hoga (na kiya to email chup-chaap skip ho
# jayega, baaki sab - console/log - waise hi chalta rahega):
#     SMTP_USER=tumhara.email@gmail.com
#     SMTP_PASSWORD=<Gmail App Password, khud ka password NAHI>
#     ALERT_EMAIL_TO=jisko-bhejna-hai@example.com  (comma se kai log)
#
# Gmail App Password kaise banayein: Google Account -> Security ->
# 2-Step Verification (ON karna padega) -> App Passwords.
# ---------------------------------------------------------------
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
ALERT_EMAIL_TO = [a.strip() for a in os.getenv("ALERT_EMAIL_TO", "").split(",") if a.strip()]


def _fetch_one(region_name, bbox, source, tries=3):
    """
    Ek (region, satellite) jodi ka aaj ka data. None agar sach mein
    kuch na mile.

    RETRY zaroori hai (jo pehle nahi tha): FIRMS rate-limit karta hai,
    aur jab 18-21 requests ek saath (parallel) jaati hain, kabhi-kabhi
    HTTP 500 wapas aata hai - naapa hua, agli hi koshish mein theek ho
    jata hai. Pehle isse "is satellite se aaj kuch nahi mila" samajh
    liya jata tha - GALAT, kyunki 500 ka matlab "server pareshan hai",
    "yahan data nahi hai" nahi. In dono ko alag rakhna zaroori hai:
        status != 200          -> transient error, RETRY karo
        status == 200, khaali  -> genuinely aaj kuch nahi, retry mat karo
    """
    west, south, east, north = bbox
    url = f"{BASE_URL}/{MAP_KEY}/{source}/{west},{south},{east},{north}/1"

    for attempt in range(tries):
        try:
            resp = requests.get(url, timeout=30)
        except requests.RequestException as e:
            if attempt == tries - 1:
                print(f"    [{region_name}/{source}] network fail: {e}")
                return None
            time.sleep(1.5 * (attempt + 1))
            continue

        if resp.status_code != 200:
            if attempt == tries - 1:
                print(f"    [{region_name}/{source}] HTTP {resp.status_code} "
                     f"(after {tries} tries)")
                return None
            time.sleep(1.5 * (attempt + 1))   # 1.5s, 3s - server ko saans lene do
            continue

        text = resp.text.strip()
        if not text.lower().startswith("latitude"):
            # 200 mila par CSV header hi nahi - ye bhi shayad error
            # message hai (FIRMS 200 pe bhi error text bhejta hai kabhi)
            if attempt == tries - 1:
                return None
            time.sleep(1.5 * (attempt + 1))
            continue

        df = pd.read_csv(StringIO(text))
        if len(df) == 0:
            return None   # 200 + saaf CSV + 0 rows = GENUINELY khaali, retry mat karo
        df["region"] = region_name
        return df

    return None


def fetch_region_nrt(region_name, bbox):
    """Ek region ka aaj ka NRT data, teeno satellite se, jodkar."""
    return fetch_regions_nrt({region_name: bbox}).get(region_name)


def fetch_regions_nrt(regions):
    """
    SAARE regions x SAARE satellites ek saath (parallel) fetch karo.

    KYUN PARALLEL: 6 regions x 3 satellites = 18 HTTP calls. Sequentially
    ye 40-60 SECOND le raha tha - itna slow ki dashboard ka 45s auto-poll
    pichhli request khatam hone se PEHLE hi nayi bhej deta tha, aur
    requests server pe dher lagti jaati thi. Parallel mein total time
    sabse dheemi EK request jitna hi rehta hai (~3-5s).

    Ye network-I/O hai (CPU nahi), isliye threads yahan bilkul theek
    hain - GIL request ke dauraan chhod diya jata hai.

    Return: {region_name: DataFrame ya None}
    """
    from concurrent.futures import ThreadPoolExecutor

    jobs = [(name, bbox, source)
            for name, bbox in regions.items()
            for source in NRT_SOURCES]

    # max_workers 8 (12 nahi) - poora burst FIRMS ko rate-limit trigger
    # karwa raha tha (500s). 8 phir bhi sequential (18-21 one-by-one)
    # se kaafi tez hai, par utna aggressive nahi.
    with ThreadPoolExecutor(max_workers=min(8, len(jobs) or 1)) as pool:
        results = list(pool.map(lambda a: _fetch_one(*a), jobs))

    per_region = {name: [] for name in regions}
    for (name, _, _), df in zip(jobs, results):
        if df is not None:
            per_region[name].append(df)

    return {name: (pd.concat(frames, ignore_index=True) if frames else None)
            for name, frames in per_region.items()}


def filter_last_n_hours(df, hours):
    """
    acq_date + acq_time (dono UTC mein) se asli timestamp banao,
    phir sirf pichhle N ghante ka rakho.
    """
    df = df.copy()
    df["acq_time"] = df["acq_time"].astype(int).astype(str).str.zfill(4)
    df["timestamp_utc"] = pd.to_datetime(
        df["acq_date"] + " " + df["acq_time"].str[:2] + ":" + df["acq_time"].str[2:],
        utc=True)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return df[df["timestamp_utc"] >= cutoff].reset_index(drop=True)


def match_against_history(live_gdf, history_gdf):
    """
    Har live detection ke liye: kya 500m ke andar koi jaana-pehchana
    source hai? Agar haan, uska label/history udhaar le lo.
    """
    live_m = live_gdf.to_crs(CRS_METRES)
    hist_m = history_gdf.to_crs(CRS_METRES)

    joined = gpd.sjoin_nearest(live_m, hist_m[["source_id", "label",
                                               "persistence_tier",
                                               "industry_name", "frp_max",
                                               "geometry"]],
                               how="left", distance_col="dist_to_known_m")
    # duplicate rows agar do source barabar door - pehla hi rakho
    joined = joined[~joined.index.duplicated(keep="first")]

    joined["status"] = "NEW - itihaas nahi hai, abhi confident label nahi"
    known = joined["dist_to_known_m"] <= MATCH_RADIUS_M
    joined.loc[known, "status"] = joined.loc[known, "label"]

    # Jaani-pehchani jagah, par uska itihaas bhi UNSURE tha (rules wahan
    # bhi chup the). Isko seedha "UNSURE" bolna dhoka dega - wo ek class
    # jaisa dikhta hai. Saaf-saaf REVIEW likho.
    joined.loc[joined["status"] == "UNSURE", "status"] = \
        "REVIEW - jaani-pehchani jagah, par label pakka nahi"

    # sjoin_nearest HAMESHA sabse paas wala source jod deta hai, chahe
    # wo 2,000 km hi door kyun na ho (jaise Basra reference region ka
    # "nearest" bhi kisi Indian source ko bata dega). Agar match nahi
    # hua (~= "NEW"), to ye borrowed columns MISLEADING hain - saaf
    # kar do, warna ek Iraq detection pe Jamnagar ka source_id chipak
    # jayega.
    unmatched = ~known
    for col in ["source_id", "label", "persistence_tier",
               "industry_name", "frp_max"]:
        if col in joined.columns:
            joined.loc[unmatched, col] = None

    return joined.to_crs(CRS_LATLON)


# ---------------------------------------------------------------
# SPREAD DIRECTION - "fire kis taraf badh raha hai"
#
# Idea: source ke detections ko waqt ke hisaab se do hisson mein
# baanto (purana aadha, naya aadha), dono ka centroid nikalo, aur
# purane centroid se naye centroid tak ka compass bearing nikal lo.
# Wahi "direction" hai.
#
# MIN_MOVEMENT_M zaroori hai: agar fire ne 200m se kam hila hai, to
# ye satellite pixel/GPS noise ho sakta hai, asli movement nahi -
# aisi jagah "direction" bolna galat hoga, isliye None lautate hain.
# ---------------------------------------------------------------
COMPASS_16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
             "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
MIN_MOVEMENT_M = 200
MIN_POINTS_FOR_DIRECTION = 4


def _bearing_deg(lat1, lon1, lat2, lon2):
    """Great-circle bearing (lat1,lon1) -> (lat2,lon2). 0=North, clockwise."""
    import math
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = (math.cos(phi1) * math.sin(phi2)
         - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda))
    theta = math.atan2(y, x)
    return (math.degrees(theta) + 360) % 360


def estimate_spread_direction(group):
    """
    `group` = ek source ke saare detections (geometry + acq_date wale
    rows, jaisa reclassify_with_model() mein banaya jata hai).

    Return: (bearing_deg, compass_label, movement_m) - agar movement
    itna kam hai ki bharosa na ho, teeno None/0 aate hain.
    """
    if len(group) < MIN_POINTS_FOR_DIRECTION:
        return None, None, 0.0

    g = group.copy()
    g["acq_date"] = pd.to_datetime(g["acq_date"])
    g = g.sort_values("acq_date")

    mid = len(g) // 2
    early, late = g.iloc[:mid], g.iloc[mid:]
    lat1, lon1 = early.geometry.y.mean(), early.geometry.x.mean()
    lat2, lon2 = late.geometry.y.mean(), late.geometry.x.mean()

    centroids = gpd.GeoSeries(
        [Point(lon1, lat1), Point(lon2, lat2)], crs=CRS_LATLON
    ).to_crs(CRS_METRES)
    dist_m = float(centroids.iloc[0].distance(centroids.iloc[1]))

    if dist_m < MIN_MOVEMENT_M:
        return None, None, round(dist_m, 0)

    bearing = _bearing_deg(lat1, lon1, lat2, lon2)
    label = COMPASS_16[round(bearing / 22.5) % 16]
    return round(bearing, 1), label, round(dist_m, 0)


# ---------------------------------------------------------------
# WIND - Open-Meteo (free, koi API key nahi chahiye)
#
# Fire wahi taraf FASTEST failti hai jidhar hawa use dhakel rahi ho.
# Isse hum apne satellite-se-nikale spread_direction ko VALIDATE kar
# sakte hain: agar dono match karein, wahi strong proof hai ki hamara
# direction genuine signal hai, satellite noise nahi.
#
# DHYAN: meteorology mein wind_direction_10m = "hawa KAHAN SE aa rahi
# hai" (jaise 270deg = West se aa rahi hai). Hawa jidhar DHAKELTI hai
# (fire jidhar failegi) wo iska 180deg ULTA hai - isliye neeche +180
# kiya gaya hai.
# ---------------------------------------------------------------
WIND_API_URL = "https://api.open-meteo.com/v1/forecast"
WIND_AGREE_TOLERANCE_DEG = 45   # itne andar ho to "hawa se match karta hai"


# Open-Meteo khud har 15 min pe update hota hai ("interval": 900), to
# usse tez poochne ka koi fayda nahi. Cache isliye bhi zaroori hai ki
# ek hi source pe har poll pe dobara call na jaye.
#
# FAILURE bhi cache karte hain (chhote TTL pe): Open-Meteo is network
# se kabhi-kabhi 20s+ le leta hai. Bina failure-cache ke har poll wahi
# slow call dobara karta aur /api/live ko 9s se wapas 40s+ pe le jata.
_WIND_CACHE = {}          # (lat_r, lon_r) -> (timestamp, wind_dict ya None)
WIND_CACHE_TTL_S = 900
WIND_FAIL_TTL_S = 120
# (connect, read) alag-alag - single value dono pe LAGTI hai, yani
# timeout=8 ka matlab worst case 16s ho jata hai. Tuple se total
# strictly ~8s pe bandha rehta hai.
WIND_TIMEOUT_S = (3, 5)   # ek hi koshish - live path ko block nahi karna


def fetch_wind(lat, lon):
    """
    Return dict: {speed_kmh, from_deg, push_deg, push_compass} ya None
    (network fail ho ya API kuch ajeeb de - chup-chaap skip, crash nahi
    kyunki wind sirf EXTRA context hai, core classification nahi).

    Ek hi koshish, 8s timeout: ye function LIVE request ke andar chalta
    hai, isliye worst-case cost bounded rakhna zaroori hai. Retry/lambe
    timeout se /api/live phir se 40s+ ka ho jata tha.
    """
    key = (round(float(lat), 2), round(float(lon), 2))
    hit = _WIND_CACHE.get(key)
    if hit:
        age, cached = time.time() - hit[0], hit[1]
        ttl = WIND_CACHE_TTL_S if cached is not None else WIND_FAIL_TTL_S
        if age < ttl:
            return cached

    try:
        resp = requests.get(WIND_API_URL, params={
            "latitude": lat, "longitude": lon,
            "current": "wind_speed_10m,wind_direction_10m",
        }, timeout=WIND_TIMEOUT_S)
        resp.raise_for_status()
        cur = resp.json()["current"]
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"    (wind fetch fail @ {key}: {type(e).__name__})")
        _WIND_CACHE[key] = (time.time(), None)
        return None

    from_deg = float(cur["wind_direction_10m"])
    push_deg = (from_deg + 180) % 360
    wind = {
        "speed_kmh": round(float(cur["wind_speed_10m"]), 1),
        "from_deg": round(from_deg, 0),
        "push_deg": round(push_deg, 0),
        "push_compass": COMPASS_16[round(push_deg / 22.5) % 16],
    }
    _WIND_CACHE[key] = (time.time(), wind)
    return wind


def wind_agrees_with_spread(wind, spread_bearing_deg):
    """Fire kis taraf badh rahi hai vs hawa kis taraf dhakel rahi hai -
    dono kitne paas hain (circular difference, 0-180)."""
    if wind is None or spread_bearing_deg is None:
        return None
    diff = abs(wind["push_deg"] - spread_bearing_deg) % 360
    diff = min(diff, 360 - diff)
    return diff <= WIND_AGREE_TOLERANCE_DEG


_DETECTIONS = None
_MODEL_BUNDLE = None


def _load_detections():
    """detections.gpkg (88k rows) ek baar padho - loop/API mein baar
    baar chale to har baar disk se padhna dheema hoga."""
    global _DETECTIONS
    if _DETECTIONS is None:
        _DETECTIONS = gpd.read_file(DATA_PROCESSED / "detections.gpkg")
    return _DETECTIONS


def _load_model():
    global _MODEL_BUNDLE
    if _MODEL_BUNDLE is None:
        import joblib
        _MODEL_BUNDLE = joblib.load(MODELS / "model.pkl")
    return _MODEL_BUNDLE


def reclassify_with_model(result):
    """
    Purana rule-label seedha copy karne ki jagah - asli TRAINED MODEL
    chalao, par SAHI tarike se: jaani-pehchani source ka poora itihaas
    (detections.gpkg se) + naya live detection jodkar, wahi 20 features
    DOBARA banao jo training mein bante hain (step3.summarise_source),
    phir model.predict_proba() se jawab lo.

    Sirf MATCHED (jaani-pehchani) sources pe chalta hai. Bilkul nayi
    jagah ke liye land-cover/factory-distance taaza nikalne padenge
    aur itne kam detections (1-2) se persistence features beemani
    honge - isliye wahan model NAHI chalate. "NEW - itihaas nahi hai"
    hi imaandar jawab hai, jhoota confident jawab nahi.
    """
    result = result.copy()
    result["model_pred"] = None
    result["model_confidence"] = None
    result["model_n_detections"] = None
    result["spread_bearing_deg"] = None
    result["spread_direction"] = None
    result["spread_m"] = None
    result["wind_speed_kmh"] = None
    result["wind_push_compass"] = None
    result["wind_agrees"] = None

    matched = result[result["dist_to_known_m"] <= MATCH_RADIUS_M]
    if len(matched) == 0:
        return result

    detections = _load_detections()
    bundle = _load_model()
    clf, le = bundle["model"], bundle["label_encoder"]

    hist_cols = ["region", "frp", "acq_date", "is_night", "dist_to_industry_m",
                "industry_type", "industry_name", "lc_class", "firms_type",
                "geometry"]

    for source_id, live_rows in matched.groupby("source_id"):
        hist = detections[detections["source_id"] == source_id]
        if len(hist) == 0:
            continue   # itihaas wale source ki detections.gpkg mein entry nahi (edge case)

        # naya live detection - jagah wahi hai, isliye static context
        # (industry/land-cover) us jagah ke itihaas se udhaar liya.
        # Teen satellite alag waqt pe dekhein to teeno ALAG detections
        # hain (jaise batch pipeline mein bhi hota) - isliye dedupe
        # nahi karte, sab count mein jaate hain.
        ctx = hist.iloc[0]
        new_rows = gpd.GeoDataFrame({
            "region": [ctx["region"]] * len(live_rows),
            "frp": pd.to_numeric(live_rows["frp"], errors="coerce").values,
            "acq_date": live_rows["timestamp_utc"].dt.strftime("%Y-%m-%d").values,
            "is_night": (live_rows["daynight"] == "N").astype(int).values,
            "dist_to_industry_m": [ctx["dist_to_industry_m"]] * len(live_rows),
            "industry_type": [ctx["industry_type"]] * len(live_rows),
            "industry_name": [ctx["industry_name"]] * len(live_rows),
            "lc_class": [ctx["lc_class"]] * len(live_rows),
            "firms_type": [float("nan")] * len(live_rows),   # NRT ye deta hi nahi
        }, geometry=gpd.points_from_xy(live_rows["longitude"], live_rows["latitude"]),
           crs=CRS_LATLON)

        combined = pd.concat([hist[hist_cols], new_rows], ignore_index=True)
        combined = gpd.GeoDataFrame(combined, geometry="geometry", crs=CRS_LATLON)

        feats = summarise_source(combined)
        feats["persistence_tier"] = persistence_tier(feats)

        X = build_X(pd.DataFrame([feats]))
        proba = clf.predict_proba(X)[0]
        pred = le.inverse_transform([proba.argmax()])[0]

        idx = live_rows.index
        result.loc[idx, "model_pred"] = pred
        result.loc[idx, "model_confidence"] = round(float(proba.max()), 3)
        result.loc[idx, "model_n_detections"] = int(len(combined))

        # Direction sirf FOREST_FIRE ke liye maayne rakhti hai -
        # INDUSTRIAL/AGRI_BURN "spread" nahi hote, ek jagah tikke rehte
        # hain, unke liye bearing sirf noise hoga.
        if pred == "FOREST_FIRE":
            bearing, label, moved_m = estimate_spread_direction(combined)
            result.loc[idx, "spread_bearing_deg"] = bearing
            result.loc[idx, "spread_direction"] = label
            result.loc[idx, "spread_m"] = moved_m

            wind = fetch_wind(live_rows["latitude"].mean(),
                              live_rows["longitude"].mean())
            if wind is not None:
                result.loc[idx, "wind_speed_kmh"] = wind["speed_kmh"]
                result.loc[idx, "wind_push_compass"] = wind["push_compass"]
                result.loc[idx, "wind_agrees"] = wind_agrees_with_spread(wind, bearing)

    return result


def find_disasters(result):
    """
    'Disaster-level' = FOREST_FIRE ya INDUSTRIAL jagah jahan abhi ki FRP
    ya to absolute floor (DISASTER_FRP_FLOOR) se upar hai, ya us jagah
    ke apne itihaas ke record (frp_max) se DISASTER_SPIKE_MULT guna
    zyada hai. Ek source ki kai rows (teen satellite) ho sakti hain -
    isliye source_id pe dedupe karke, sabse garam row rakhte hain.
    """
    if "frp" not in result.columns:
        return result.iloc[0:0]

    candidates = result[result["status"].isin(DISASTER_STATUSES)].copy()
    if len(candidates) == 0:
        return candidates

    # frp_max tabhi milta hai jab history match hui ho. Column hi na ho
    # (purani sources_labelled.gpkg) to sirf absolute floor pe chalo -
    # crash mat karo.
    candidates["frp"] = pd.to_numeric(candidates["frp"], errors="coerce")
    if "frp_max" in candidates.columns:
        hist_max = pd.to_numeric(candidates["frp_max"], errors="coerce")
    else:
        hist_max = pd.Series(float("nan"), index=candidates.index)

    over_floor = candidates["frp"] >= DISASTER_FRP_FLOOR
    over_own_history = hist_max.notna() & (
        candidates["frp"] >= hist_max * DISASTER_SPIKE_MULT)
    disasters = candidates[over_floor | over_own_history].copy()
    if len(disasters) == 0:
        return disasters

    disasters = disasters.sort_values("frp", ascending=False)
    return disasters.drop_duplicates(subset="source_id", keep="first")


def _alert_key(row):
    """Ek source ki pehchaan. source_id na ho to lat/lon se bana lo."""
    src = row.get("source_id")
    if pd.notna(src):
        return str(src)
    return f"{row['latitude']:.4f},{row['longitude']:.4f}"


def read_alert_state():
    """Kaunsa source kab email-alert hua - {source_key: iso_timestamp}.
    Dashboard (read-only) aur filter_already_alerted() dono isi ek jagah
    se padhte hain, taaki dono ki definition kabhi alag na ho."""
    try:
        return json.loads(ALERT_STATE.read_text())
    except (OSError, ValueError):
        return {}


def filter_already_alerted(disasters, now):
    """
    Jo source pichhle RE_ALERT_HOURS ghante mein already alert ho chuki
    hai, use hata do. Lautao (bheji jaane wali rows, dabayi gayi rows).
    """
    if len(disasters) == 0:
        return disasters, 0

    state = read_alert_state()

    cutoff = now - timedelta(hours=RE_ALERT_HOURS)
    fresh_idx = []
    for idx, row in disasters.iterrows():
        last = state.get(_alert_key(row))
        if last is not None:
            try:
                if datetime.fromisoformat(last) > cutoff:
                    continue        # abhi haal hi mein bata chuke hain
            except ValueError:
                pass                # kharab entry - dobara alert kar do
        fresh_idx.append(idx)

    fresh = disasters.loc[fresh_idx]
    suppressed = len(disasters) - len(fresh)

    for _, row in fresh.iterrows():
        state[_alert_key(row)] = now.isoformat()
    try:
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        ALERT_STATE.write_text(json.dumps(state, indent=1))
    except OSError as e:
        print(f"  (alert state save nahi hui: {e})")

    return fresh, suppressed


def alert_disasters(disasters):
    """Zor se, chhoota jaana mushkil console alert + local log file."""
    if len(disasters) == 0:
        return

    now = datetime.now(timezone.utc)
    fresh, suppressed = filter_already_alerted(disasters, now)
    if suppressed:
        print(f"\n  ({suppressed} disaster source pehle se alert ho chuki hai, "
              f"{RE_ALERT_HOURS}h tak dobara nahi bajega)")
    if len(fresh) == 0:
        return

    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    bar = "!" * 68
    print("\a\n" + bar)          # \a = terminal bell, ek hi baar
    print(f"  DISASTER-LEVEL FIRE ALERT - {stamp}")
    print(bar)

    lines = []
    for _, r in fresh.iterrows():
        industry = r.get("industry_name")
        line = (f"  [{r['status']}] {str(r.get('region', '?')):<12} "
                f"{r['latitude']:.4f},{r['longitude']:.4f}  "
                f"FRP={r['frp']:.1f}MW  source={_alert_key(r)}"
                f"{'  (' + str(industry) + ')' if pd.notna(industry) else ''}")
        print(line)
        lines.append(f"{stamp}  {line.strip()}")
    print(bar)

    try:
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        with open(ALERTS_LOG, "a") as f:
            f.write("\n".join(lines) + "\n")
        print(f"  (logged to {ALERTS_LOG})\n")
    except OSError as e:
        print(f"  (log likhne mein dikkat: {e})\n")

    send_disaster_email(fresh, stamp)


def send_disaster_email(fresh, stamp):
    """
    Disaster-level alert ko mail bhi bhejo - console/log kaafi nahi hai
    agar koi terminal dekh hi nahi raha. Cooldown wahi hai jo console
    alert ke liye upar use hua (RE_ALERT_HOURS) - `fresh` yahan pehle
    se filter_already_alerted() se guzar chuka hai.

    Config nahi hai to chup-chaap skip - baaki poora system (console,
    log, dashboard) waise hi chalta rehta hai, email sirf ek EXTRA
    channel hai, zaroori nahi.
    """
    if not (SMTP_USER and SMTP_PASSWORD and ALERT_EMAIL_TO):
        print("  (email skip - .env mein SMTP_USER/SMTP_PASSWORD/"
              "ALERT_EMAIL_TO set nahi hain)")
        return False

    n = len(fresh)
    subject = f"[ThermalSight] DISASTER-LEVEL FIRE ALERT - {n} source(s)"

    body_lines = [
        f"Disaster-level thermal spike detected at {stamp}.",
        f"({n} source{'s' if n != 1 else ''}, FRP >= {DISASTER_FRP_FLOOR:.0f} MW "
        f"or >= {DISASTER_SPIKE_MULT}x that site's own historical peak)",
        "",
    ]
    for _, r in fresh.iterrows():
        industry = r.get("industry_name")
        maps_link = f"https://www.google.com/maps?q={r['latitude']:.5f},{r['longitude']:.5f}"
        body_lines += [
            f"- [{r['status']}] {r.get('region', '?')}",
            f"  location : {r['latitude']:.5f}, {r['longitude']:.5f}  ({maps_link})",
            f"  FRP      : {r['frp']:.1f} MW",
            f"  source   : {_alert_key(r)}"
            f"{'  (' + str(industry) + ')' if pd.notna(industry) else ''}",
            "",
        ]
    body_lines.append(
        "This is an automated alert from ThermalSight's live monitor "
        "(step8_live_monitor.py). Re-alerts for the same source are "
        f"suppressed for {RE_ALERT_HOURS}h.")

    msg = MIMEText("\n".join(body_lines))
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(ALERT_EMAIL_TO)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, ALERT_EMAIL_TO, msg.as_string())
        print(f"  (email bheja: {', '.join(ALERT_EMAIL_TO)})\n")
        return True
    except (smtplib.SMTPException, OSError) as e:
        print(f"  (email bhejne mein dikkat: {e})\n")
        return False


def run_once(hours):
    if not MAP_KEY:
        sys.exit("ERROR: FIRMS_MAP_KEY nahi mila (.env check karo)")

    history_path = DATA_PROCESSED / "sources_labelled.gpkg"
    if not history_path.exists():
        sys.exit("ERROR: sources_labelled.gpkg nahi mili - pehle "
                 "step1-4 chala chuke ho na?")
    history = gpd.read_file(history_path)

    print("=" * 68)
    print(f"LIVE MONITOR - pichhle {hours} ghante  "
          f"({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})")
    print("=" * 68)

    # REGIONS (hamare 5 trained) + LIVE_REFERENCE_REGIONS (Basra - koi
    # training history nahi, sirf isliye check karte hain ki NASA feed
    # genuinely live hai. Demo mein hamare 5 chhote regions kai baar
    # ghanton khaali rehte hain - Basra saal bhar active rehta hai).
    all_check_regions = {**REGIONS, **LIVE_REFERENCE_REGIONS}

    print(f"  {len(all_check_regions)} regions parallel mein fetch ho rahe hain...")
    raw_by_region = fetch_regions_nrt(all_check_regions)

    all_frames = []
    for region_name in all_check_regions:
        raw = raw_by_region.get(region_name)
        print(f"  {region_name}... ", end="")
        if raw is None:
            # Do wajah ho sakti hain aur hum dono mein farak nahi kar
            # sakte: (a) satellite abhi upar se guzra hi nahi, ya
            # (b) guzra par kuch garam mila hi nahi. Isliye dono mat
            # bolo - sirf wahi bolo jo sach mein pata hai.
            print("aaj koi hotspot nahi mila")
            continue
        recent = filter_last_n_hours(raw, hours)
        print(f"{len(raw)} aaj ke, {len(recent)} pichhle {hours}h mein")
        if len(recent) > 0:
            all_frames.append(recent)

    if not all_frames:
        print("\nPichhle kuch ghanton mein KUCH bhi naya nahi mila.")
        return None

    combined = pd.concat(all_frames, ignore_index=True)
    combined["geometry"] = [Point(xy) for xy in
                            zip(combined["longitude"], combined["latitude"])]
    live_gdf = gpd.GeoDataFrame(combined, geometry="geometry", crs=CRS_LATLON)

    result = match_against_history(live_gdf, history)

    # Matched sources ke liye ab MODEL dobara chalate hain (itihaas +
    # naya live detection jodkar, taaza features se) - purana rule-
    # label sirf display ke liye "status" mein reh gaya hai, asli
    # taaza jawab model_pred/model_confidence mein hai.
    print("\n  model dobara chala raha hai jaani-pehchani sources pe...")
    result = reclassify_with_model(result)

    # DHYAN: ek hi aag ko teeno satellite alag-alag dekh sakte hain, to
    # ek source ki 3 rows ban jaati hain. Detections aur SOURCES do alag
    # cheezein hain - "3 forest fire" bolna jhooth hoga jab wo ek hi aag
    # ho. Isliye dono ginte hain.
    print("\n" + "-" * 68)
    print(f"RESULT - {len(result)} detections")
    print("-" * 68)
    for status, n in result["status"].value_counts().items():
        sub = result[result["status"] == status]
        n_src = sub["source_id"].nunique() if status.split()[0] not in ("NEW",) else n
        print(f"  {status:<48} {n:>4} detections"
              f"{f'  ({n_src} unique sources)' if n_src != n else ''}")

    modeled = result[result["model_pred"].notna()].drop_duplicates(subset="source_id")
    if len(modeled) > 0:
        print(f"\n  MODEL KA TAAZA JAWAB ({len(modeled)} jaani-pehchani sources):")
        agree = int((modeled["model_pred"] == modeled["status"]).sum())
        print(f"    rules se match: {agree}/{len(modeled)}")
        for _, r in modeled.iterrows():
            flag = "" if r["model_pred"] == r["status"] else "  << RULES SE ALAG"
            print(f"       {r['region']:<12} {r['model_pred']:<12} "
                  f"conf={r['model_confidence']:.2f}{flag}")

    fires = result[(result["model_pred"] == "FOREST_FIRE")
                   | ((result["model_pred"].isna()) & (result["status"] == "FOREST_FIRE"))]
    if len(fires) > 0:
        uniq = fires.drop_duplicates(subset="source_id")
        print(f"\n  >> {len(uniq)} FOREST_FIRE source(s) ABHI active hain:")
        for _, r in uniq.iterrows():
            print(f"       {r['region']:<12} {r['latitude']:.4f},{r['longitude']:.4f}"
                  f"  ({r['timestamp_utc']:%H:%M UTC})")

    alert_disasters(find_disasters(result))

    out_path = DATA_PROCESSED / "live_detections.gpkg"
    result.to_file(out_path, driver="GPKG")
    print(f"\nSAVED: {out_path}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=3,
                    help="pichhle kitne ghante ka data (default 3)")
    ap.add_argument("--loop", type=int, default=0,
                    help="har N second baad dobara chalao (0 = sirf ek baar)")
    args = ap.parse_args()

    if args.loop <= 0:
        run_once(args.hours)
        return

    print(f"LOOP MODE - har {args.loop}s baad dobara chalega. Ctrl+C se roko.")
    while True:
        run_once(args.hours)
        print(f"\n... {args.loop}s so rahe hain ...\n")
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
