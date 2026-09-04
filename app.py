"""
Thermal Source Classifier - dashboard.

    streamlit run app.py

Design notes:
  - all heavy IO sits behind @st.cache_data so interaction stays instant
  - the map is capped; drawing 17k markers freezes the browser
  - every headline number states where it came from, so nothing looks
    like it was invented
"""
import json
from pathlib import Path
import sys

import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from config import DATA_PROCESSED, OUTPUTS

st.set_page_config(page_title="Thermal Source Classifier",
                   page_icon="🛰️", layout="wide",
                   initial_sidebar_state="expanded")

# ---------------------------------------------------------------
# One palette for the whole app - map, legend and charts all use it.
# ---------------------------------------------------------------
CLASS_COLOR = {
    "INDUSTRIAL":  "#c0392b",
    "FOREST_FIRE": "#1e8449",
    "AGRI_BURN":   "#d4a017",
    "REVIEW":      "#7f8c8d",
}
CLASS_LABEL = {
    "INDUSTRIAL":  "Industrial / Mining",
    "FOREST_FIRE": "Forest fire",
    "AGRI_BURN":   "Crop residue burning",
    "REVIEW":      "Needs review",
}

# industry_name is the NEAREST mapped industry, which can be 45 km away.
# Only 229 of 5,120 named sources sit within 1 km. Showing the name
# without a distance test puts "Mahan Thermal Power Plant" on a forest
# fire 45 km away, so gate it.
NAME_MAX_DIST_M = 2000

st.markdown("""
<style>
  .block-container {padding-top: 2.2rem; padding-bottom: 2rem; max-width: 1400px;}
  h1 {font-size: 2rem !important; font-weight: 700; letter-spacing: -0.02em;}
  h2 {font-size: 1.25rem !important; font-weight: 650; margin-top: 0.4rem;}
  h3 {font-size: 1.05rem !important; font-weight: 620;}
  [data-testid="stMetricValue"] {font-size: 1.65rem; font-weight: 680;}
  [data-testid="stMetricLabel"] {font-size: 0.78rem; text-transform: uppercase;
      letter-spacing: 0.04em; color: #5a6570;}
  [data-testid="stMetric"] {background: #fafbfc; border: 1px solid #e5e9ed;
      border-radius: 10px; padding: 0.9rem 1.1rem;}
  .stTabs [data-baseweb="tab"] {font-size: 0.94rem; font-weight: 560;}
  .subtle {color: #5a6570; font-size: 0.88rem; line-height: 1.55;}
  .pill {display:inline-block; padding: 2px 10px; border-radius: 999px;
      font-size: 0.78rem; font-weight: 600; margin-right: 6px;}
  hr {margin: 1.2rem 0;}
</style>
""", unsafe_allow_html=True)


# ===============================================================
@st.cache_data(show_spinner="Loading data…")
def load():
    pred = gpd.read_file(DATA_PROCESSED / "predictions.gpkg")
    gold = pd.read_csv(DATA_PROCESSED / "gold_labels.csv")
    anom = pd.read_csv(DATA_PROCESSED / "anomalies.csv")

    # -----------------------------------------------------------
    # The model is deliberately NOT allowed to answer on sources the
    # rules left as UNSURE. Measured, it was right only 39% of the
    # time there - a coin toss across three classes is 33%. Those
    # sources are surfaced as a review queue instead. A system that
    # says "I don't know" is more useful than one that guesses.
    # -----------------------------------------------------------
    pred["klass"] = pred["label"].where(pred["label"] != "UNSURE", "REVIEW")
    pred["site"] = pred["industry_name"].where(
        pred["dist_to_industry_m"] <= NAME_MAX_DIST_M)
    return pred, gold, anom


@st.cache_data
def load_metrics():
    f = OUTPUTS / "metrics.json"
    return json.loads(f.read_text()) if f.exists() else {}


@st.cache_data
def load_nasa_metrics():
    """step7 - the model trained on NASA's labels instead of our rules."""
    f = OUTPUTS / "nasa_metrics.json"
    return json.loads(f.read_text()) if f.exists() else {}


@st.cache_data
def load_vlm_metrics():
    """step4d - the vision model measured against the human labels."""
    f = OUTPUTS / "gemini_validation.json"
    return json.loads(f.read_text()) if f.exists() else {}


pred, gold, anom = load()
M = load_metrics()
NM = load_nasa_metrics()
VM = load_vlm_metrics()

TOTAL_DET = int(pred["n_detections"].sum())
N_IND = int((pred["klass"] == "INDUSTRIAL").sum())
N_REVIEW = int((pred["klass"] == "REVIEW").sum())

# Sources whose label came from the vision model rather than a rule.
# Absent until step4e_merge_vlm.py has run, so every use is guarded.
HAS_VLM = "label_source" in pred.columns
N_VLM = int((pred["label_source"] == "vlm").sum()) if HAS_VLM else 0


# ===============================================================
# Header
# ===============================================================
head_l, head_r = st.columns([3, 1])
with head_l:
    st.title("Thermal Source Classifier")
    st.markdown(
        '<div class="subtle">Satellites detect <b>heat</b>, not its cause. '
        'This system separates industrial thermal sources from forest fires '
        'and crop residue burning using persistence, night-time behaviour '
        'and land context.</div>', unsafe_allow_html=True)
with head_r:
    st.markdown(
        f'<div class="subtle" style="text-align:right;padding-top:1.4rem">'
        f'<b>SIH 26162</b><br>Calendar year 2025<br>'
        f'5 regions · 3 VIIRS satellites</div>', unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------
# Before / after - the core of the pitch, in one click.
# ---------------------------------------------------------------
view = st.radio("View", ["Raw satellite data", "After classification"],
                horizontal=True, label_visibility="collapsed", index=1)
raw_view = view == "Raw satellite data"

k = st.columns(4)
if raw_view:
    k[0].metric("Thermal detections", f"{TOTAL_DET:,}", "NASA FIRMS")
    k[1].metric("Distinguishable", "None", "all points look identical")
    k[2].metric("Industrial sites", "Unknown")
    k[3].metric("Actionable output", "None")
    st.info("A satellite sees only **temperature**. A refinery flare, a "
            "forest fire and a burning field produce the same kind of "
            "record. Switch the toggle to see what the system resolves "
            "them into.")
else:
    k[0].metric("Thermal detections", f"{TOTAL_DET:,}", "NASA FIRMS")
    k[1].metric("Distinct sources", f"{len(pred):,}", "after clustering")
    k[2].metric("Industrial sites", f"{N_IND:,}",
                f"−{100 * (1 - N_IND / TOTAL_DET):.2f}% of raw volume")
    k[3].metric("Flagged for review", f"{N_REVIEW:,}",
                "system declines to guess", delta_color="off")


# ===============================================================
# Sidebar
# ===============================================================
with st.sidebar:
    st.markdown("### Filters")
    regions = st.multiselect(
        "Region", sorted(pred["region"].unique()),
        default=sorted(pred["region"].unique()),
        format_func=str.title)
    classes = st.multiselect(
        "Class", list(CLASS_LABEL),
        default=["INDUSTRIAL", "FOREST_FIRE", "AGRI_BURN"],
        format_func=lambda c: CLASS_LABEL[c], disabled=raw_view)
    min_det = st.slider("Minimum detections per source", 1, 200, 1,
                        help="Higher values isolate persistent sources.")
    st.markdown("### Map")
    n_map = st.slider("Markers to draw", 100, 3000, 600, step=100,
                      help="Drawing every source freezes the browser. "
                           "The largest sources are drawn first.")
    st.divider()
    st.markdown(
        '<div class="subtle">Data: NASA FIRMS · OpenStreetMap · '
        'WRI Global Power Plant Database · ESA WorldCover.<br>'
        'All sources are openly licensed.</div>', unsafe_allow_html=True)

def apply_filters(df, regions, classes, min_det, raw_view):
    """Single definition of "the current view" — used by the table and the export."""
    out = df[df["region"].isin(regions) & (df["n_detections"] >= min_det)]
    return out if raw_view else out[out["klass"].isin(classes)]


EXPORT_COLS = ["source_id", "region", "klass", "n_detections", "n_days",
               "night_ratio", "frp_max", "dist_to_industry_m", "lc_class",
               "site", "geometry"]


@st.cache_data(show_spinner=False)
def export_geojson(regions, classes, min_det, raw_view):
    """
    Serialising the full view is expensive — 17,615 sources is 5.5 MB and
    about 3.4 seconds. Streamlit re-runs the whole script on every widget
    interaction, so building this inline cost ~3.5 s on every slider drag
    and every tab switch, which is plainly visible during a live demo.

    Cached on the filter values instead, so it is rebuilt only when the
    selection actually changes. Arguments must be hashable — hence the
    tuples at the call site.
    """
    return apply_filters(pred, regions, classes, min_det, raw_view)[
        EXPORT_COLS].to_json()


f = apply_filters(pred, regions, classes, min_det, raw_view)


# ===============================================================
# step8_live_monitor.py writes these files on its own schedule (run it
# with --loop in a terminal). The dashboard just reads whatever is
# there - a short TTL cache means a refresh (or the button below)
# picks up a new run within a minute without a full page reload.
# ===============================================================
LIVE_STATUS_COLOR = {**CLASS_COLOR, "NEW": "#2980b9", "REVIEW": "#7f8c8d"}
LIVE_STATUS_LABEL = {
    "INDUSTRIAL": "Industrial / Mining", "FOREST_FIRE": "Forest fire",
    "AGRI_BURN": "Crop residue burning", "NEW": "New - no history yet",
    "REVIEW": "Known site, label unsure"}


def _live_bucket(status):
    if status.startswith("NEW"):
        return "NEW"
    if status.startswith("REVIEW"):
        return "REVIEW"
    return status


@st.cache_data(ttl=60, show_spinner=False)
def load_live():
    path = DATA_PROCESSED / "live_detections.gpkg"
    if not path.exists():
        return None, None
    gdf = gpd.read_file(path)
    gdf["bucket"] = gdf["status"].apply(_live_bucket)
    if "timestamp_utc" in gdf.columns:
        gdf["timestamp_utc"] = pd.to_datetime(gdf["timestamp_utc"], utc=True,
                                              errors="coerce")
    return gdf, pd.Timestamp(path.stat().st_mtime, unit="s", tz="UTC")


@st.cache_data(ttl=60, show_spinner=False)
def load_disaster_alerts():
    path = OUTPUTS / "disaster_alerts.log"
    if not path.exists():
        return []
    lines = [l.strip() for l in path.read_text().splitlines() if l.strip()]
    return lines[-15:][::-1]  # most recent first


tab_live, tab_map, tab_pri, tab_anom, tab_val, tab_method = st.tabs(
    ["Live", "Map", "Inspection priorities", "Anomalies", "Validation", "Method"])

# -------------------------------------------------------------- LIVE
with tab_live:
    lcol, rcol = st.columns([1, 5])
    with lcol:
        if st.button("Refresh now", width="stretch"):
            load_live.clear()
            load_disaster_alerts.clear()
            st.rerun()

    live, updated_at = load_live()
    alerts = load_disaster_alerts()

    if live is None:
        st.info(
            "No live data yet. Start the monitor in a terminal:\n\n"
            "`python src/step8_live_monitor.py --loop 900`\n\n"
            "This tab reads `data/processed/live_detections.gpkg`, which "
            "that script writes on every pass - it does not run on its own "
            "from the dashboard.")
    else:
        with rcol:
            st.caption(f"Last run: {updated_at:%Y-%m-%d %H:%M UTC} "
                       "· auto-refreshes within 60s, or use the button")

        if alerts:
            st.error("**Disaster-level fire alert(s)**", icon="🔥")
            for line in alerts:
                st.markdown(f"<span class='subtle'>{line}</span>",
                           unsafe_allow_html=True)
            st.divider()

        k = st.columns(4)
        k[0].metric("Live detections", f"{len(live):,}")
        k[1].metric("Forest fire", int((live['bucket'] == 'FOREST_FIRE').sum()))
        k[2].metric("Industrial", int((live['bucket'] == 'INDUSTRIAL').sum()))
        k[3].metric("New (no history)", int((live['bucket'] == 'NEW').sum()))

        if len(live):
            m = folium.Map(location=[live["latitude"].mean(), live["longitude"].mean()],
                           zoom_start=5, tiles="CartoDB positron", control_scale=True)
            for _, r in live.iterrows():
                bucket = r["bucket"]
                ts = (f"{r['timestamp_utc']:%H:%M UTC}"
                      if pd.notna(r.get("timestamp_utc")) else "—")
                folium.CircleMarker(
                    [r["latitude"], r["longitude"]], radius=6,
                    color=LIVE_STATUS_COLOR.get(bucket, "#7f8c8d"), fill=True,
                    fill_opacity=0.8, weight=1,
                    tooltip=LIVE_STATUS_LABEL.get(bucket, bucket),
                    popup=folium.Popup(
                        f"<div style='font-family:system-ui;font-size:13px'>"
                        f"<b style='color:{LIVE_STATUS_COLOR.get(bucket, '#7f8c8d')}'>"
                        f"{LIVE_STATUS_LABEL.get(bucket, bucket)}</b><br>"
                        f"Region: {r.get('region', '—')}<br>"
                        f"FRP: {r.get('frp', float('nan')):.1f} MW<br>"
                        f"Detected: {ts}</div>", max_width=260)).add_to(m)
            st_folium(m, height=520, width=None, returned_objects=[])
        st.caption("Blue = brand-new hotspot with no history yet; grey = known "
                   "site whose past label was never certain. Both need a human "
                   "look before they can be called forest fire, industrial or "
                   "agri-burn.")

# --------------------------------------------------------------- MAP
with tab_map:
    left, right = st.columns([4, 1])
    with left:
        st.markdown(f"**{len(f):,}** sources match the current filters — "
                    f"drawing the {min(n_map, len(f)):,} largest.")
        top = f.nlargest(n_map, "n_detections")
        if len(top):
            m = folium.Map(location=[top["lat"].mean(), top["lon"].mean()],
                           zoom_start=5, tiles="CartoDB positron",
                           control_scale=True)
            for _, r in top.iterrows():
                if raw_view:
                    folium.CircleMarker(
                        [r["lat"], r["lon"]], radius=3, color="#95a5a6",
                        fill=True, fill_opacity=0.5, weight=0).add_to(m)
                else:
                    site = str(r["site"]) if pd.notna(r["site"]) else "—"
                    # If a vision model looked at this source, show what it
                    # saw and why. This is the only part of the popup that
                    # explains a classification in words rather than numbers.
                    ai = ""
                    if HAS_VLM and pd.notna(r.get("vlm_landuse")):
                        by_ai = r.get("label_source") == "vlm"
                        ai = (f"<br><span style='color:#5a6570'>"
                              f"{'Classified by' if by_ai else 'Also checked by'} "
                              f"vision model: <b>{r['vlm_landuse']}</b>"
                              f"</span>")
                    folium.CircleMarker(
                        [r["lat"], r["lon"]],
                        radius=3 + min(7, r["n_detections"] ** 0.35),
                        color=CLASS_COLOR[r["klass"]], fill=True,
                        fill_opacity=0.72, weight=1,
                        tooltip=CLASS_LABEL[r["klass"]],
                        popup=folium.Popup(
                            f"<div style='font-family:system-ui;font-size:13px'>"
                            f"<b style='color:{CLASS_COLOR[r['klass']]}'>"
                            f"{CLASS_LABEL[r['klass']]}</b><br>"
                            f"<b>{site}</b><br><br>"
                            f"Detections: <b>{int(r['n_detections'])}</b><br>"
                            f"Active days: {int(r['n_days'])}<br>"
                            f"Night-time share: <b>{r['night_ratio']:.0%}</b><br>"
                            f"Peak FRP: {r['frp_max']:.1f} MW<br>"
                            f"Distance to industry: {r['dist_to_industry_m']:,.0f} m<br>"
                            f"Land cover: {r['lc_class']}{ai}</div>",
                            max_width=290)).add_to(m)
            st_folium(m, height=560, width=None, returned_objects=[])
    with right:
        st.markdown("**Legend**")
        if raw_view:
            st.markdown(
                '<span class="pill" style="background:#eceff1;color:#546e7a">'
                '● Thermal detection</span><br><br>'
                '<span class="subtle">Every point is identical. '
                'No class information exists in the raw feed.</span>',
                unsafe_allow_html=True)
        else:
            for c, lbl in CLASS_LABEL.items():
                n = int((f["klass"] == c).sum())
                st.markdown(
                    f'<div style="margin-bottom:7px"><span style="color:'
                    f'{CLASS_COLOR[c]};font-size:1.15rem">●</span> '
                    f'&nbsp;{lbl}<br><span class="subtle" '
                    f'style="margin-left:20px">{n:,} sources</span></div>',
                    unsafe_allow_html=True)
            st.caption("Marker size scales with detection count.")

        st.download_button(
            "Export view (GeoJSON)",
            export_geojson(tuple(regions), tuple(classes), min_det, raw_view),
            file_name="thermal_sources.geojson",
            mime="application/geo+json",
            width="stretch")

# --------------------------------------------------------- PRIORITIES
with tab_pri:
    st.subheader("Industrial sources ranked for inspection")
    st.markdown('<div class="subtle">This is the operational output — the '
                'list a pollution control board would act on.</div>',
                unsafe_allow_html=True)
    st.write("")

    ind = f[f["klass"] == "INDUSTRIAL"].nlargest(25, "n_detections")
    tbl = ind[["site", "region", "n_detections", "n_days", "night_ratio",
               "frp_max", "n_anomalies", "worst_anomaly_ratio"]].copy()
    tbl.columns = ["Site (OSM)", "Region", "Detections", "Active days",
                   "Night share", "Peak FRP (MW)", "Anomaly days",
                   "Worst spike (×)"]
    tbl["Region"] = tbl["Region"].str.title()
    st.dataframe(
        tbl, width="stretch", hide_index=True,
        column_config={
            "Night share": st.column_config.ProgressColumn(
                format="%.0f%%", min_value=0, max_value=1),
            "Worst spike (×)": st.column_config.NumberColumn(format="%.1f×")})
    st.caption("Anomaly days count dates where a site's radiative power "
               "exceeded three times its own baseline. Ranking uses "
               "observed behaviour, not model confidence — on a task this "
               "deterministic the model reports ~1.00 confidence for 99% "
               "of sources, which carries no information.")

    st.divider()
    c1, c2, c3 = st.columns([1, 1, 2])
    c1.metric("Review queue", f"{N_REVIEW:,}")
    if N_VLM:
        c2.metric("Resolved by vision model", f"{N_VLM:,}",
                  f"−{100 * N_VLM / (N_REVIEW + N_VLM):.0f}% queue",
                  delta_color="normal")
    c3.markdown(
        '<div class="subtle" style="padding-top:0.6rem">No rule matched '
        'these sources. They are left unclassified on purpose: when the '
        'model was allowed to answer here it was correct <b>39%</b> of the '
        'time, against a <b>33%</b> baseline for three classes. Declining '
        'to answer is the more useful behaviour.</div>',
        unsafe_allow_html=True)

    # --- what the vision model recovered from the queue ---
    if N_VLM:
        st.markdown("")
        st.markdown("**Recovered from the review queue by satellite imagery**")
        st.markdown(
            '<div class="subtle">The rules read numbers — distance, month, '
            'night share. They cannot see a kiln hidden inside a field. '
            'These sources had no rule match at all; a vision model was '
            'shown the satellite chip and asked what is physically there. '
            'Its answer is quoted verbatim, so a reviewer can overrule '
            'it.</div>', unsafe_allow_html=True)
        rec = pred[(pred["label_source"] == "vlm")
                   & pred["region"].isin(regions)]
        rec = rec[rec["klass"] == "INDUSTRIAL"].nlargest(15, "n_detections")
        if len(rec):
            rt = rec[["region", "n_detections", "night_ratio", "vlm_landuse",
                      "vlm_confidence", "vlm_reason"]].copy()
            rt.columns = ["Region", "Detections", "Night share",
                          "Seen as", "Model confidence", "Stated reason"]
            rt["Region"] = rt["Region"].str.title()
            st.dataframe(
                rt, width="stretch", hide_index=True,
                column_config={
                    "Night share": st.column_config.ProgressColumn(
                        format="%.0f%%", min_value=0, max_value=1),
                    "Model confidence": st.column_config.NumberColumn(
                        format="%.2f"),
                    "Stated reason": st.column_config.TextColumn(width="large")})
            st.caption(
                "Model confidence is the vision model's own estimate of "
                "itself, and it averages 0.90 across answers that include "
                "its mistakes — read it as commentary, not as a "
                "probability. The measured accuracy is in the Validation "
                "tab.")
        else:
            st.caption("No recovered industrial sources in the selected regions.")

# ----------------------------------------------------------- ANOMALIES
with tab_anom:
    st.subheader("Radiative power anomalies")
    st.markdown('<div class="subtle">A site burning far hotter than its own '
                'normal is the strongest actionable signal in the dataset.</div>',
                unsafe_allow_html=True)
    st.write("")

    a = anom[anom["region"].isin(regions)].copy()
    c = st.columns(4)
    c[0].metric("Anomalies", f"{len(a):,}")
    c[1].metric("Distinct sites", f"{a['source_id'].nunique():,}")
    c[2].metric("Largest spike", f"{a['ratio'].max():.0f}×")
    c[3].metric("Detection threshold", "3× baseline")

    show = a.nlargest(30, "ratio")[["date", "industry_name", "region",
                                    "frp", "normal_frp", "ratio"]].copy()
    show.columns = ["Date", "Site (OSM)", "Region", "FRP (MW)",
                    "Baseline FRP", "Ratio"]
    show["Region"] = show["Region"].str.title()
    st.dataframe(show, width="stretch", hide_index=True,
                 column_config={"Ratio": st.column_config.NumberColumn(
                     format="%.1f×")})

    st.markdown("**Anomalies by month**")
    a["month"] = pd.to_datetime(a["date"]).dt.month_name().str[:3]
    order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    counts = a["month"].value_counts().reindex(order).fillna(0)
    st.bar_chart(counts, height=220)

# ---------------------------------------------------------- VALIDATION
with tab_val:
    st.subheader("How we know this works")
    st.markdown('<div class="subtle">Five checks, each with a different '
                'failure mode. None of them reuses the rules that produced '
                'the labels.</div>',
                unsafe_allow_html=True)
    st.write("")

    # --- 1. human labels
    st.markdown("#### 1 · Human-verified labels")
    if M:
        g = M["gold"]
        c = st.columns(4)
        c[0].metric("Accuracy", f"{g['accuracy']:.1%}")
        c[1].metric("Macro F1", f"{g['macro_f1']:.3f}")
        c[2].metric("Test set", f"{g['n']} sources")
        c[3].metric("Random baseline", "33%")
        rep = pd.DataFrame(g["report"]).T.loc[
            ["INDUSTRIAL", "FOREST_FIRE", "AGRI_BURN"],
            ["precision", "recall", "f1-score", "support"]]
        rep.index = [CLASS_LABEL[i] for i in rep.index]
        rep.columns = ["Precision", "Recall", "F1", "n"]
        st.dataframe(rep.style.format(
            {"Precision": "{:.2f}", "Recall": "{:.2f}",
             "F1": "{:.2f}", "n": "{:.0f}"}), width="stretch")
        st.caption("Labelled by hand from satellite imagery, held out "
                   "entirely from training. With 45 samples the 95% "
                   "confidence interval is roughly ±14 points — the "
                   "headline number is honest but not precise.")

    st.divider()

    # --- 2. NASA agreement
    st.markdown("#### 2 · Agreement with NASA's own classification")
    nasa = pred[pred.get("static_ratio", pd.Series(0, index=pred.index)) > 0]
    if len(nasa):
        agree = (nasa["label"] == "INDUSTRIAL").mean()
        c = st.columns(4)
        c[0].metric("Flagged static by FIRMS", f"{len(nasa)}")
        c[1].metric("Classified industrial by us", f"{int((nasa['label'] == 'INDUSTRIAL').sum())}")
        c[2].metric("Agreement", f"{agree:.0%}")
        c[3].metric("Detections covered", f"{int(nasa['n_detections'].sum()):,}")
        st.success(
            "FIRMS assigns every detection a type, where **type 2** means "
            "*other static land source* — NASA's own term for an industrial "
            "heat source. **Our rules never read that field.** They use "
            "distance to mapped industry, night-time share and persistence. "
            f"The two systems agree on **{agree:.0%}** of cases, covering "
            f"**{nasa['n_detections'].sum() / TOTAL_DET:.0%}** of all "
            "detections. This is stronger evidence than our own label set, "
            "because it comes from outside the project.")

    st.divider()

    # --- 3. ablation
    st.markdown("#### 3 · Is the model learning, or repeating the rules?")
    if M.get("ablation"):
        ab = pd.DataFrame(M["ablation"])
        ab.columns = ["Feature set", "Features", "Region hold-out F1",
                      "Gold accuracy", "Gold macro F1"]
        st.dataframe(ab.style.format({
            "Region hold-out F1": "{:.3f}", "Gold accuracy": "{:.1%}",
            "Gold macro F1": "{:.3f}"}), width="stretch",
            hide_index=True)
        first, last = ab.iloc[0], ab.iloc[-1]
        gap = first["Gold accuracy"] - last["Gold accuracy"]
        st.warning(
            f"Our labels come from rules, and the model is given the same "
            f"features those rules use — so a high score may only mean the "
            f"model memorised the rules. We tested it: removing those "
            f"features collapses the region hold-out score from "
            f"**{first['Region hold-out F1']:.3f}** to "
            f"**{last['Region hold-out F1']:.3f}**. That score was "
            f"reproduction, not understanding, and we do not report it as a "
            f"result.\n\nAgainst human labels the picture is different and "
            f"more useful: **{first['Gold accuracy']:.1%}** with map context, "
            f"**{last['Gold accuracy']:.1%}** on satellite behaviour alone — "
            f"still well clear of the 33% three-class baseline. The satellite "
            f"signal stands on its own; the map layers add roughly "
            f"{gap:.0%} points on top.")
    else:
        st.info("Ablation results appear here after `python src/step5_train.py`.")

    st.divider()

    # --- 4. a model that was never shown our rules at all
    st.markdown("#### 4 · A model trained without any of our rules")
    if NM:
        vs = NM.get("vs_human_labels") or {}
        c = st.columns(4)
        c[0].metric("Training labels", f"{NM['n_detections']:,}",
                    "NASA FIRMS, not ours")
        c[1].metric("Rule-derived features", "0", delta_color="off")
        c[2].metric("Agreement with human labels", f"{vs.get('accuracy', 0):.1%}")
        c[3].metric("AUC", f"{vs.get('auc', 0):.3f}")

        st.success(
            "The ablation above shows our main model partly reproduces its own "
            "rules. This model is built so it cannot. FIRMS assigns every "
            "detection a type — **0** for a presumed vegetation fire, **2** for "
            "*other static land source* — and we train on that instead, using "
            "only per-detection satellite measurements: radiative power, the two "
            "brightness bands and their difference, pixel geometry, day or "
            "night, month. No land cover, no distance to industry, no "
            "persistence tier. **None of our rules can leak into it.**\n\n"
            f"Trained on NASA's labels and then measured against *our human* "
            f"labels — two label sets produced independently of each other — it "
            f"reaches **{vs.get('accuracy', 0):.1%}** accuracy and "
            f"**{vs.get('auc', 0):.3f}** AUC at identifying industrial sources. "
            "Our rules appear nowhere in that chain. It also classifies a single "
            "detection on its own, so unlike the persistence model it does not "
            "need months of history before it can answer.")

        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown("**Held-out region performance**")
            rh = pd.DataFrame(NM["region_holdout"]).copy()
            rh["held_out"] = rh["held_out"].str.title()
            rh.columns = ["Region", "Detections", "Static (type 2)", "F1", "AUC"]
            st.dataframe(rh.style.format(
                {"Detections": "{:,.0f}", "Static (type 2)": "{:,.0f}",
                 "F1": "{:.3f}", "AUC": "{:.3f}"}, na_rep="—"),
                width="stretch", hide_index=True)
            st.caption(
                "Reported in full, including where it fails. NASA marks almost "
                "no static sources outside the thermal belt — one detection in "
                "Punjab, none in Uttarakhand — so those folds have essentially "
                "no positive class and their scores are undefined or "
                "meaningless. Where the class genuinely exists (Jamnagar, "
                "Korba) it reaches 0.96 and 0.88 AUC. This is a limitation of "
                "the label coverage, not a result we are hiding.")
        with c2:
            imp = pd.Series(NM["feature_importance"]).nlargest(6)
            st.markdown("**What it relies on**")
            st.bar_chart(imp, height=250)
            st.caption("Night-time acquisition dominates — the model rediscovers "
                       "the project's core premise on its own.")

        p = OUTPUTS / "nasa_confusion.png"
        if p.exists():
            st.image(str(p), width=430,
                     caption="Agreement with NASA's own classification")
    else:
        st.info("Run `python src/step7_nasa_model.py` to populate this section.")

    st.divider()

    # --- 5. an independent vision model
    st.markdown("#### 5 · An independent look at the imagery")
    if VM:
        acc = VM.get("gemini_accuracy", 0)
        racc = VM.get("rule_accuracy", 0)
        n_ans = VM.get("n_answered", 0)
        c = st.columns(4)
        c[0].metric("Vision model vs human labels", f"{acc:.1%}")
        c[1].metric("Rules on the same sources", f"{racc:.1%}")
        c[2].metric("Answered", f"{n_ans}/{VM.get('n', 0)}",
                    "declined the rest", delta_color="off")
        c[3].metric("Queue sources resolved", f"{N_VLM:,}" if N_VLM else "—")

        st.success(
            "Every check above reasons over the same tabular features: "
            "distance, night share, persistence, land cover. This one does "
            "not. A vision-language model is shown the **satellite image "
            "itself**, with the detection marked, and asked what is "
            "physically at that point. It never sees a single one of our "
            "features, thresholds or labels.\n\n"
            f"On the human-labelled set it agrees **{acc:.1%}** of the time "
            f"against **{racc:.1%}** for the rules — and, more usefully, it "
            "answers where the rules produce nothing at all. That is what "
            f"the {N_VLM:,} recovered sources in the Inspection priorities "
            "tab are.")

        st.caption(
            f"Measured on {n_ans} answered sources, so the interval is wide "
            "— roughly ±12 points. The honest reading is *beats the rules "
            "and covers cases they cannot*, not a precise figure. "
            "Answers of *water*, *barren*, *urban* or *unclear* map to no "
            "class and are left in the queue rather than forced into one; "
            "counting those as errors would be the wrong measurement, and "
            "counting them as successes would be dishonest.")

        if HAS_VLM and "vlm_conflict" in pred.columns:
            n_conf = int(pred["vlm_conflict"].fillna(False).astype(bool).sum())
            if n_conf:
                st.warning(
                    f"**{n_conf} sources where the rules and the vision "
                    "model disagree outright.** The rule label is kept — the "
                    "vision model is not authoritative enough to overturn a "
                    "matched rule — but these are flagged, because a "
                    "disagreement between two independent methods is the "
                    "single most informative thing a human reviewer can "
                    "spend time on.")
    else:
        st.info("Run `python src/step4d_gemini.py --validate` to populate "
                "this section.")

    st.divider()
    st.markdown("#### The discriminating signal")
    st.markdown('<div class="subtle">Industrial plant runs around the clock; '
                'agricultural burning does not happen at night. Night-time '
                'share separates them.</div>', unsafe_allow_html=True)
    nr = pred[pred["klass"] != "REVIEW"].groupby("klass")["night_ratio"].mean()
    st.bar_chart(nr.rename(index=CLASS_LABEL), height=230)

    imgs = [("shap_summary.png", "Feature attribution (SHAP)"),
            ("confusion_matrix.png", "Confusion matrix, human-labelled test set")]
    cols = st.columns(2)
    for col, (fn, cap) in zip(cols, imgs):
        p = OUTPUTS / fn
        if p.exists():
            col.image(str(p), caption=cap, width="stretch")

# -------------------------------------------------------------- METHOD
with tab_method:
    st.subheader("How a detection becomes a classification")
    st.code("""NASA FIRMS          88,434 thermal detections, 3 satellites, full year 2025
      │
      ├─ DBSCAN (500 m, min 3)      →  distinct physical sources
      │
      ├─ OpenStreetMap + WRI        →  distance to nearest industry
      ├─ ESA WorldCover (10 m)      →  land cover class
      └─ persistence analysis       →  how often, how long, day or night
      │
      ▼
   Rule engine  →  INDUSTRIAL | FOREST_FIRE | AGRI_BURN | review queue
      │
      ├─ vision model on the queue  →  reads the satellite chip itself,
      │                                answers where no rule matched
      ▼
   XGBoost      →  applies the rules across all sources and unseen regions

   ── validated separately ──────────────────────────────────────────────
   Second model, trained on NASA's own detection types with none of the
   features above, agrees with our human labels at 88.9% — see Validation""",
            language="text")

    st.markdown("#### The classification rules")
    st.code("""INDUSTRIAL   within 1 km of mapped industry AND not a one-off event
             OR  burns at night AND persists for months

FOREST_FIRE  forest land cover  AND  beyond 1 km of industry
             AND  not a continuously operating source

AGRI_BURN    non-forest         AND  beyond 1 km of industry
             AND  not continuous AND  daytime""", language="text")
    st.markdown(
        '<div class="subtle">Exactly one rule must match. Zero matches or a '
        'conflict sends the source to the review queue. Every threshold is '
        'documented with the measurement that justifies it in '
        '<code>src/config.py</code>.</div>', unsafe_allow_html=True)

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Data sources")
        st.markdown("""
| Source | Contribution |
|---|---|
| NASA FIRMS | Where and when heat occurred |
| OpenStreetMap | Industrial footprints and names |
| WRI Power Plants | Thermal plants missing from OSM |
| ESA WorldCover | Land cover at 10 m |

All openly licensed; no paid data.
""")
    with c2:
        st.markdown("#### Known limitations")
        st.markdown("""
- **45 human labels** give a ±14 point confidence interval
- **OpenStreetMap is incomplete** in India — small kilns and some
  facilities are unmapped, which caps rule accuracy
- **The main model reproduces the rules** rather than extending them.
  The ablation quantifies this, and section 4 of the Validation tab
  answers it with a model that never sees those features
- **Crop burning is a residual class** — the rule is *not forest, away
  from industry, not persistent, daytime*. It is what remains once the
  other two are excluded, not a positive detection
- **No human labels** yet from Korba or Singrauli, which supply most
  of the industrial data
- **The vision model was measured on 42 answered sources.** It beats
  the rules and it covers cases they cannot, but that sample cannot
  support a precise accuracy claim, and it is not allowed to overturn
  a matched rule
""")
