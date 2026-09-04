"""
FastAPI backend - React frontend ke liye.

    uvicorn api.main:app --reload --port 8000
    (ya:  python api/main.py)

KYUN YE HAI:
    app.py (Streamlit) har widget pe poora script dobara chalata hai.
    Wo demo ke liye theek tha, par ek asli UI ke liye data alag hona
    chahiye aur dikhava alag. Ye file SIRF data deti hai - JSON mein.
    Dikhane ka kaam React karta hai (web/ folder).

DHYAN: ye koi naya calculation NAHI karti. Wahi files padhti hai jo
pipeline ne banayi hain, aur wahi tarke lagati hai jo app.py mein hain
(REVIEW queue, site naam ki doori wali shart, waghairah). Do jagah do
alag jawab nahi hone chahiye.
"""
import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from config import DATA_PROCESSED, OUTPUTS, REGIONS, LIVE_REFERENCE_REGIONS  # noqa: E402
import step8_live_monitor as live_monitor                 # noqa: E402
import dashboard_chatbot                                  # noqa: E402

# ---------------------------------------------------------------
# app.py se ek jaisa rakhne ke liye - dono jagah wahi values
# ---------------------------------------------------------------
CLASS_LABEL = {
    "INDUSTRIAL":  "Industrial / Mining",
    "FOREST_FIRE": "Forest fire",
    "AGRI_BURN":   "Crop residue burning",
    "REVIEW":      "Needs review",
}

# industry_name sabse PAAS wali industry ka naam hai, jo 45 km door bhi
# ho sakti hai. Bina doori check kiye dikhaoge to jungle ki aag pe
# "Mahan Thermal Power Plant" likha aa jayega.
NAME_MAX_DIST_M = 2000

app = FastAPI(title="Thermal Source Classifier API", version="1.0")

# dev mein React 5173 pe chalta hai, API 8000 pe - browser bina iske
# request block kar dega
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ===============================================================
# Data - ek baar load, phir memory mein
# ===============================================================
class Store:
    """Saari files ek baar padho. 17,615 rows har request pe padhna
    bewakoofi hai - process bhar ke liye ek hi copy kaafi hai."""

    def __init__(self):
        self.pred = None
        self.anom = None
        self.metrics = {}
        self.nasa = {}
        self.vlm = {}
        self.load()

    @staticmethod
    def _json(path):
        return json.loads(path.read_text()) if path.exists() else {}

    def load(self):
        pred = gpd.read_file(DATA_PROCESSED / "predictions.gpkg")

        # -------------------------------------------------------
        # Model ko UNSURE sources pe jawab dene ki IJAZAT NAHI hai.
        # Naapne pe wo wahan sirf 39% sahi tha (3 classes mein tukka
        # 33% hota hai). Wo sources review queue mein jaate hain.
        # Ye wahi tarka hai jo app.py mein hai - badalna ho to DONO
        # jagah badalna.
        # -------------------------------------------------------
        pred["klass"] = pred["label"].where(pred["label"] != "UNSURE", "REVIEW")
        pred["site"] = pred["industry_name"].where(
            pred["dist_to_industry_m"] <= NAME_MAX_DIST_M)

        # VLM wale columns pipeline ke optional step se aate hain -
        # na hon to bhi API chalni chahiye
        for col in ["vlm_landuse", "vlm_reason", "label_source"]:
            if col not in pred.columns:
                pred[col] = None

        # pd.to_numeric yahan isliye hai (sirf "float(nan) agar column
        # nahi hai" kaafi nahi tha): ek purani buggy run mein
        # vlm_confidence GPKG mein MIXED type ban gaya tha - kuch rows
        # "0.95" (string) the, kuch NaN (float). Wajah: column "object"
        # dtype se shuru hua tha, GPKG driver ne poore column ko TEXT
        # likh diya. Root cause step4e_merge_vlm.py mein theek kar diya
        # hai, par jo files DISK PE pehle se hain unhe dobara pipeline
        # chalaye bina bhi sahi dikhna chahiye - isliye yahan bhi.
        # to_numeric() string "0.95" ko 0.95 float bana deta hai, aur
        # kuch bhi ajeeb mila to NaN (crash nahi).
        pred["vlm_confidence"] = pd.to_numeric(
            pred["vlm_confidence"] if "vlm_confidence" in pred.columns else None,
            errors="coerce")

        if "vlm_conflict" not in pred.columns:
            pred["vlm_conflict"] = False

        self.pred = pred
        self.anom = pd.read_csv(DATA_PROCESSED / "anomalies.csv")
        self.metrics = self._json(OUTPUTS / "metrics.json")
        self.nasa = self._json(OUTPUTS / "nasa_metrics.json")
        self.vlm = self._json(OUTPUTS / "gemini_validation.json")


S = Store()


# ===============================================================
# Helpers
# ===============================================================
def clean(records):
    """NaN JSON mein valid nahi hai - None bana do, warna browser ka
    JSON.parse phat jayega."""
    out = []
    for r in records:
        out.append({k: (None if isinstance(v, float) and pd.isna(v) else v)
                    for k, v in r.items()})
    return out


def filtered(regions, classes, min_det, raw=False):
    """"Abhi screen pe kya dikh raha hai" ki EK hi definition -
    table, map aur export teeno yahi use karte hain.

    raw=True matlab "classification se PEHLE wala nazara". Satellite
    ke feed mein class hoti hi nahi, isliye class filter lagta hi
    nahi - baaki filters (region, min_det) waise ke waise chalte hain.
    Yahi tarka app.py ke apply_filters() mein hai.
    """
    df = S.pred
    if regions:
        df = df[df["region"].isin(regions)]
    if classes and not raw:
        df = df[df["klass"].isin(classes)]
    if min_det and min_det > 1:
        df = df[df["n_detections"] >= min_det]
    return df


RegionQ = Query(None, description="region names; omit for all")
ClassQ = Query(None, description="INDUSTRIAL / FOREST_FIRE / AGRI_BURN / REVIEW")


# ===============================================================
# Endpoints
# ===============================================================
@app.get("/api/meta")
def meta():
    """UI ko shuru mein kya-kya pata hona chahiye."""
    p = S.pred
    return {
        "regions": sorted(p["region"].unique().tolist()),
        "classes": [{"key": k, "label": v} for k, v in CLASS_LABEL.items()],
        "max_detections": int(p["n_detections"].max()),
        "has_vlm": bool((p["label_source"] == "vlm").any()),
        "year": 2025,
        "n_satellites": 3,
    }


@app.get("/api/summary")
def summary(regions: list[str] = RegionQ):
    """Upar wale bade numbers."""
    p = S.pred if not regions else S.pred[S.pred["region"].isin(regions)]
    total_det = int(p["n_detections"].sum())
    n_ind = int((p["klass"] == "INDUSTRIAL").sum())
    n_review = int((p["klass"] == "REVIEW").sum())
    n_vlm = int((p["label_source"] == "vlm").sum())
    return {
        "total_detections": total_det,
        "n_sources": int(len(p)),
        "n_industrial": n_ind,
        "n_review": n_review,
        "n_from_vlm": n_vlm,
        # "88,434 detections mein se sirf 192 jagah dekhni hain"
        "reduction_pct": round(100 * (1 - n_ind / total_det), 3) if total_det else 0,
        "by_class": {k: int((p["klass"] == k).sum()) for k in CLASS_LABEL},
        "n_anomalies": int(len(S.anom[S.anom["region"].isin(p["region"].unique())])),
    }


@app.get("/api/sources")
def sources(regions: list[str] = RegionQ,
            classes: list[str] = ClassQ,
            min_det: int = 1,
            limit: int = 800,
            raw: bool = False):
    """
    Map ke points.

    limit kyun: 17,615 markers browser ko jama deta hai. Sabse zyada
    detection wale pehle bhejte hain - wahi sabse maayne rakhte hain.

    raw=True pe class filter nahi lagta AUR class waale columns bheje
    hi nahi jaate. Ye jaan-boojh kar hai: "raw" ka poora matlab yahi
    hai ki us feed mein ye jaankari mojood hi nahi. Frontend ko chun
    kar chhupane ka mauka dena galat hoga - wo sirf CSS jaisa dhoka
    hota, sach nahi.
    """
    df = filtered(regions, classes, min_det, raw)
    total = len(df)
    df = df.nlargest(min(limit, 3000), "n_detections")
    cols = ["source_id", "region", "klass", "lat", "lon", "n_detections",
            "n_days", "night_ratio", "frp_max", "dist_to_industry_m",
            "lc_class", "site", "label_source", "vlm_landuse",
            "vlm_confidence", "vlm_reason", "n_anomalies"]
    if raw:
        cols = ["source_id", "region", "lat", "lon", "n_detections", "n_days"]
    cols = [c for c in cols if c in df.columns]
    return {"total_matching": int(total), "returned": int(len(df)),
            "raw": raw,
            "items": clean(df[cols].to_dict("records"))}


@app.get("/api/priorities")
def priorities(regions: list[str] = RegionQ, limit: int = 25):
    """
    Pollution control board ko yahi list chahiye.

    Ranking model ke confidence pe NAHI hai - wo is kaam pe bekaar hai
    (99% sources pe 1.00 deta hai). Ranking ANOMALY pe hai: kitne din
    us jagah ne apne khud ke normal se 3 guna zyada garmi di.
    """
    df = S.pred[S.pred["klass"] == "INDUSTRIAL"]
    if regions:
        df = df[df["region"].isin(regions)]
    df = df.nlargest(limit, "n_detections")
    cols = ["source_id", "site", "region", "n_detections", "n_days",
            "night_ratio", "frp_max", "n_anomalies", "worst_anomaly_ratio",
            "label_source", "vlm_landuse", "vlm_reason"]
    cols = [c for c in cols if c in df.columns]
    return {"items": clean(df[cols].to_dict("records"))}


@app.get("/api/recovered")
def recovered(regions: list[str] = RegionQ, limit: int = 20):
    """
    Wo sources jinpe RULES chup the aur AI ne photo dekh kar jawab diya.

    Ye alag endpoint isliye hai kyunki demo mein yahi sabse kaam ki
    cheez hai - "hamari AI ne wo dhoonda jo rules dhoondh hi nahi
    sakte the".
    """
    df = S.pred[S.pred["label_source"] == "vlm"]
    if regions:
        df = df[df["region"].isin(regions)]
    ind = df[df["klass"] == "INDUSTRIAL"].nlargest(limit, "n_detections")
    cols = ["source_id", "region", "klass", "n_detections", "night_ratio",
            "vlm_landuse", "vlm_confidence", "vlm_reason"]
    return {
        "n_total_recovered": int(len(df)),
        "by_class": {k: int((df["klass"] == k).sum()) for k in CLASS_LABEL},
        "items": clean(ind[[c for c in cols if c in ind.columns]]
                       .to_dict("records")),
    }


@app.get("/api/anomalies")
def anomalies(regions: list[str] = RegionQ, limit: int = 30):
    """"Aaj kuch alag hua" - apne hi normal se 3 guna zyada garmi."""
    a = S.anom
    if regions:
        a = a[a["region"].isin(regions)]
    top = a.nlargest(limit, "ratio")
    by_month = (pd.to_datetime(a["date"]).dt.month.value_counts()
                .reindex(range(1, 13), fill_value=0).sort_index())
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return {
        "n": int(len(a)),
        "n_sites": int(a["source_id"].nunique()) if len(a) else 0,
        "max_ratio": float(a["ratio"].max()) if len(a) else 0,
        "by_month": [{"month": months[i], "count": int(by_month.iloc[i])}
                     for i in range(12)],
        "items": clean(top.to_dict("records")),
    }


@app.get("/api/validation")
def validation():
    """
    Saare sabooot ek jagah. UI inhe 5 alag checks mein baantta hai.

    Har check ka apna FAILURE MODE hai - isliye paanch hain, ek nahi.
    """
    p = S.pred
    nasa_static = p[p["static_ratio"] > 0] if "static_ratio" in p.columns \
        else p.iloc[0:0]
    agree = float((nasa_static["klass"] == "INDUSTRIAL").mean()) \
        if len(nasa_static) else 0.0

    night = (p[p["klass"] != "REVIEW"].groupby("klass")["night_ratio"]
             .mean().to_dict())

    n_conflict = 0
    if "vlm_conflict" in p.columns:
        n_conflict = int(p["vlm_conflict"].fillna(False).astype(bool).sum())

    return {
        "gold": S.metrics.get("gold", {}),
        "ablation": S.metrics.get("ablation", []),
        "shap_importance": S.metrics.get("shap_importance", {}),
        "evaluation": S.metrics.get("evaluation", []),
        "n_train": S.metrics.get("n_train"),
        "nasa_agreement": {
            "n_flagged_static": int(len(nasa_static)),
            "n_we_called_industrial": int((nasa_static["klass"] == "INDUSTRIAL").sum()),
            "agreement": agree,
            "detections_covered": int(nasa_static["n_detections"].sum())
            if len(nasa_static) else 0,
            "detections_total": int(p["n_detections"].sum()),
        },
        "nasa_model": S.nasa,
        "vlm": S.vlm,
        "vlm_integration": {
            "n_labelled": int((p["label_source"] == "vlm").sum()),
            "n_conflicts": n_conflict,
        },
        "night_ratio_by_class": {k: float(v) for k, v in night.items()},
    }


@app.get("/api/export")
def export(regions: list[str] = RegionQ,
           classes: list[str] = ClassQ,
           min_det: int = 1,
           raw: bool = False):
    """GeoJSON - QGIS mein kholne ke liye."""
    df = filtered(regions, classes, min_det, raw)
    cols = ["source_id", "region", "klass", "n_detections", "n_days",
            "night_ratio", "frp_max", "dist_to_industry_m", "lc_class",
            "site", "geometry"]
    if raw:
        cols = ["source_id", "region", "n_detections", "n_days", "geometry"]
    gj = json.loads(df[[c for c in cols if c in df.columns]].to_json())
    return JSONResponse(gj, headers={
        "Content-Disposition": 'attachment; filename="thermal_sources.geojson"'})


@app.get("/api/health")
def health():
    return {"ok": True, "n_sources": int(len(S.pred))}


# ===============================================================
# CHATBOT - "is data ke baare mein kuch bhi poocho"
#
# Context (aggregate stats, poora dataset nahi) ek baar bana ke cache
# karte hain - S.pred badalta nahi jab tak koi naya pipeline run na
# ho, isliye har question pe dobara banane ki zaroorat nahi.
# ===============================================================
_CHAT_CONTEXT = None


class ChatRequest(BaseModel):
    question: str


@app.post("/api/chat")
def chat(req: ChatRequest):
    global _CHAT_CONTEXT
    q = req.question.strip()
    if not q:
        return JSONResponse({"error": "empty question"}, status_code=400)
    if len(q) > 500:
        return JSONResponse({"error": "question too long (max 500 chars)"},
                            status_code=400)

    if _CHAT_CONTEXT is None:
        _CHAT_CONTEXT = dashboard_chatbot.build_data_context(S)

    answer, err = dashboard_chatbot.answer_question(q, _CHAT_CONTEXT)
    if err:
        return JSONResponse({"error": err}, status_code=503)
    return {"answer": answer}


# ===============================================================
# LIVE - NASA FIRMS ka near-real-time feed, turant classify
#
# Ye batch pipeline se ALAG hai: yahan naya detection aate hi use
# JAANE-PEHCHANE sources (jinka poora saal ka itihaas hai) se match
# karte hain aur unka label seedha udhaar le lete hain. Model dobara
# nahi chalta - kyun, ye step8_live_monitor.py ke docstring mein hai.
#
# CACHE kyun: har frontend refresh pe NASA ko 15 requests (5 region x
# 3 satellite) bhejna na to zaroori hai na shaishtaachar - NRT feed
# khud hi kuch ghanton mein ek baar update hota hai. 60s cache kaafi
# hai "live" feel dene ke liye bina NASA ko spam kiye.
# ===============================================================
_LIVE_CACHE = {"key": None, "ts": 0.0, "payload": None}
LIVE_CACHE_TTL_S = 60


def _live_history():
    """S.pred se hi itihaas banao - 'klass' (UNSURE->REVIEW) taaki
    live status frontend ke existing rang/naam (CLASS_LABEL) se seedha
    match ho jaaye, do alag vocabulary na banein.

    frp_max bhi chahiye - step8_live_monitor.match_against_history()
    ab isi column se disaster-spike detect karta hai (jagah ka apna
    record se kitna zyada garam hai abhi)."""
    h = S.pred[["source_id", "klass", "persistence_tier", "site",
               "frp_max", "geometry"]].copy()
    return h.rename(columns={"klass": "label", "site": "industry_name"})


@app.get("/api/live/demo")
def live_demo():
    """
    DEMO ENDPOINT - NASA ko call nahi karta, koi network wait nahi.

    KYUN YE HAI: live feed genuinely khaali ho sakta hai kai ghanton
    tak (satellite ka apna schedule hai, cloud cover, off-season) -
    ye REAL hai, bug nahi. Par mentor/demo ke saamne "system chalta
    hai, bas abhi kuch nahi mila" bolna kamzor lagta hai bina proof ke.

    Ye endpoint 3 asli, jaani-pehchani sources (ek har class ka) par
    "abhi ka" detection banata hai, aur unhe WAHI reclassify_with_model()
    se guzarta hai jo asli live traffic use karta hai - matlab code
    path bilkul wahi hai, sirf NASA se fetch skip hota hai. Result mein
    "demo": true saaf likha hota hai taaki kabhi real data se confuse
    na ho.
    """
    # nlargest se top-5 mein se ek chunte hain, sirf .iloc[0] nahi -
    # warna chhota-sa 1-detection wala source mil jata aur "spread
    # direction" kabhi demo mein dikhta hi nahi (4+ points chahiye).
    # Top-1 (sabse extreme outlier) se bachte hain jaan-boojh kar -
    # ek baar wahan AGRI_BURN source itna persistent nikla ki khud
    # model use INDUSTRIAL bol raha tha - genuine, dilchasp edge case,
    # par demo ke liye ek "typical" udaharan behtar hai confusion se bachne ko.
    picks = []
    for cls in ["FOREST_FIRE", "INDUSTRIAL", "AGRI_BURN"]:
        sub = S.pred[S.pred["klass"] == cls].nlargest(5, "n_detections")
        if len(sub):
            picks.append(sub.iloc[min(2, len(sub) - 1)])

    now = live_monitor.datetime.now(live_monitor.timezone.utc)
    fake = pd.DataFrame({
        "latitude": [p.lat for p in picks],
        "longitude": [p.lon for p in picks],
        "acq_date": [now.strftime("%Y-%m-%d")] * len(picks),
        "acq_time": [int(now.strftime("%H%M"))] * len(picks),
        "timestamp_utc": [pd.Timestamp(now)] * len(picks),
        "satellite": ["N"] * len(picks),
        "frp": [8.0, 90.0, 4.5][:len(picks)],
        "daynight": ["N", "N", "D"][:len(picks)],
        "region": [p.region for p in picks],
    })
    fake["geometry"] = gpd.points_from_xy(fake["longitude"], fake["latitude"])
    fake_gdf = gpd.GeoDataFrame(fake, geometry="geometry", crs=4326)

    result = live_monitor.match_against_history(fake_gdf, _live_history())
    result["status_key"] = result["status"].str.split(" ").str[0]
    result = live_monitor.reclassify_with_model(result)

    cols = ["latitude", "longitude", "region", "timestamp_utc",
            "source_id", "status_key", "industry_name",
            "satellite", "frp", "daynight",
            "model_pred", "model_confidence", "model_n_detections",
            "spread_direction", "spread_bearing_deg", "spread_m",
            "wind_speed_kmh", "wind_push_compass", "wind_agrees"]
    items = clean(result[[c for c in cols if c in result.columns]]
                 .astype({"timestamp_utc": str}).to_dict("records"))

    return {
        "demo": True,
        "note": ("This is SIMULATED data - a 'right now' detection has been "
                "synthesised on top of 3 real sources, to show how the "
                "system would react if a new detection arrived. If the real "
                "NASA feed is empty, that means there is genuinely no "
                "active fire (satellite blind spot / off-season), not a bug."),
        "checked_at": now.isoformat(),
        "n_detections": len(items),
        "items": items,
    }


@app.get("/api/live")
def live(hours: int = Query(3, ge=1, le=48)):
    cache_key = hours
    now = time.time()
    if (_LIVE_CACHE["payload"] is not None and _LIVE_CACHE["key"] == cache_key
            and now - _LIVE_CACHE["ts"] < LIVE_CACHE_TTL_S):
        return {**_LIVE_CACHE["payload"], "cached": True,
                "cache_age_s": int(now - _LIVE_CACHE["ts"])}

    if not live_monitor.MAP_KEY:
        return JSONResponse(
            {"error": "FIRMS_MAP_KEY missing - .env dekho"}, status_code=503)

    # REGIONS (5 trained) + LIVE_REFERENCE_REGIONS (Jharia - koi training
    # history nahi, sirf isliye check karte hain ki NASA feed genuinely
    # live hai. Hamare 5 chhote regions kai baar ghanton khaali rehte
    # hain, Jharia ka coal seam saal bhar jalta rehta hai).
    #
    # PARALLEL fetch (18 HTTP calls ek saath) - sequentially ye 40-60s
    # le raha tha, jo frontend ke 45s auto-poll se bhi dheema tha:
    # requests overlap hokar dher lag jaati thi.
    all_regions = {**REGIONS, **LIVE_REFERENCE_REGIONS}
    raw_by_region = live_monitor.fetch_regions_nrt(all_regions)

    frames = []
    checked_regions = list(all_regions)
    for region_name in all_regions:
        raw = raw_by_region.get(region_name)
        if raw is None:
            continue
        recent = live_monitor.filter_last_n_hours(raw, hours)
        if len(recent):
            frames.append(recent)

    checked_at = live_monitor.datetime.now(live_monitor.timezone.utc)
    email_configured = bool(live_monitor.SMTP_USER and live_monitor.SMTP_PASSWORD
                            and live_monitor.ALERT_EMAIL_TO)
    payload = {
        "checked_at": checked_at.isoformat(),
        "hours": hours,
        "regions_checked": checked_regions,
        "n_detections": 0,
        "by_status": {},
        "items": [],
        "disasters": [],
        "model": {"n_reclassified": 0, "n_agree_with_rules": 0},
        "email_configured": email_configured,
    }

    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined["geometry"] = gpd.points_from_xy(
            combined["longitude"], combined["latitude"])
        live_gdf = gpd.GeoDataFrame(combined, geometry="geometry", crs=4326)

        result = live_monitor.match_against_history(live_gdf, _live_history())
        result["status_key"] = result["status"].str.split(" ").str[0]

        # Matched sources ke liye MODEL dobara chalao (itihaas + naya
        # live detection jodkar, taaza features se) - status_key purana
        # rule-label hai (baseline), model_pred taaza jawab hai. Dono
        # dikhao - agar alag hain, wahi sabse dilchasp signal hai.
        result = live_monitor.reclassify_with_model(result)

        by_status = {}
        for key, sub in result.groupby("status_key"):
            n_src = (int(sub["source_id"].nunique())
                     if key != "NEW" else int(len(sub)))
            by_status[key] = {"detections": int(len(sub)), "sources": n_src}

        n_modeled = int(result["model_pred"].notna().sum())
        n_agree = int((result["model_pred"] == result["status_key"]).sum())

        cols = ["latitude", "longitude", "region", "timestamp_utc",
                "source_id", "status_key", "industry_name",
                "dist_to_known_m", "satellite", "frp", "daynight",
                "model_pred", "model_confidence", "model_n_detections",
                "spread_direction", "spread_bearing_deg", "spread_m",
                "wind_speed_kmh", "wind_push_compass", "wind_agrees"]
        items = clean(result[[c for c in cols if c in result.columns]]
                     .astype({"timestamp_utc": str})
                     .to_dict("records"))

        # disaster-level spike (FOREST_FIRE/INDUSTRIAL jo abhi apne
        # itihaas se ya absolute floor se kaafi zyada garam hai) -
        # side-effect wala alert() nahi bulaya (wo console/log ke liye
        # hai, ek read-only API request se disk pe nahi likhna). Email
        # sirf background --loop process se jaati hai; yahan sirf uska
        # ALREADY-SAVED status padh kar dikhate hain (read-only).
        disasters = live_monitor.find_disasters(result)
        alert_state = live_monitor.read_alert_state()
        if len(disasters):
            disasters = disasters.copy()
            disasters["last_emailed"] = disasters.apply(
                lambda r: alert_state.get(live_monitor._alert_key(r)), axis=1)
        d_cols = ["latitude", "longitude", "region", "status", "frp",
                  "source_id", "industry_name", "timestamp_utc", "last_emailed"]
        disaster_items = clean(
            disasters[[c for c in d_cols if c in disasters.columns]]
            .astype({"timestamp_utc": str}).to_dict("records")
        ) if len(disasters) else []

        payload.update({
            "n_detections": int(len(result)),
            "by_status": by_status,
            "items": items,
            "disasters": disaster_items,
            "model": {"n_reclassified": n_modeled, "n_agree_with_rules": n_agree},
        })

    _LIVE_CACHE.update(key=cache_key, ts=now, payload=payload)
    return {**payload, "cached": False, "cache_age_s": 0}


# ---------------------------------------------------------------
# Banaya hua React (web/dist) yahin se serve ho jata hai, taaki demo
# mein sirf EK server chalana pade.
#
# Ye sabse aakhir mein hai - warna "/" wala catch-all upar ke /api
# routes ko kha jayega.
# ---------------------------------------------------------------
DIST = ROOT / "web" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        """React router client-side hai - har unknown path pe index.html."""
        f = DIST / full_path
        if full_path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=False)
