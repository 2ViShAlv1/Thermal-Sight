"""
STEP 4 (part 3) - 150 sources TUM khud label karoge.

Ye ek chhoti si app hai. Ek-ek source dikhayegi - uski satellite photo,
uska FRP ka chart, uske numbers - aur tum teen buttons mein se ek dabaoge.

--------------------------------------------------------------------
YE KAAM KYUN ZAROORI HAI (skip mat karna)

Baaki saare labels RULES ne banaye hain. Agar model ko unhi labels pe
test karoge, to tum sirf ye check kar rahe ho ki "model ne mere rules
ratt liye ya nahi". Wo accuracy jhoothi hai - 95% aayegi aur uska koi
matlab nahi hoga.

Ye 150 labels INSAAN ne banaye hain. Model ne inhe kabhi nahi dekha.
Isi liye inpe mila score hi SACCHA score hai.

Aur ek faayda: label karte waqt tumhe 3-4 aisi galtiyan khud dikhengi
jo koi rule nahi pakad sakta (jaise koi factory OSM pe hai hi nahi).
Wahi tumhari sabse achhi slide banegi.
--------------------------------------------------------------------

Chalane ka tareeka:
    streamlit run src/gold_ui.py

Output: data/processed/gold_labels.csv
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA_PROCESSED, DATA_CHIPS, CLASSES     # noqa: E402
from step4b_vlm import download_chip                        # noqa: E402

GOLD_CSV = DATA_PROCESSED / "gold_labels.csv"
BASE_TARGET = 150
BALANCE_TOP_UP = 30   # AGRI_BURN already hawi hai 150 mein - 30 aur
                       # INDUSTRIAL/FOREST_FIRE/UNSURE jodo balance ke liye
N_TO_LABEL = BASE_TARGET + BALANCE_TOP_UP

st.set_page_config(page_title="Gold Labels", layout="wide")


# ===============================================================
# Data load karna
# ===============================================================
@st.cache_data
def load_data():
    sources = gpd.read_file(DATA_PROCESSED / "sources_labelled.gpkg")
    detections = gpd.read_file(DATA_PROCESSED / "detections.gpkg",
                               layer="detections")
    return sources, detections


@st.cache_data
def pick_sources(_sources, already_done_ids):
    """
    150 sources chuno - par soch samajh kar.

    Agar hum bas 150 random utha lete, to zyadatar Punjab ke AGRI_BURN
    aa jaate (kyunki wahi sabse zyada hain), aur INDUSTRIAL ek bhi nahi.
    Phir test set bekaar ho jata.

    Isliye har (region x rule_label) ke jode se barabar uthate hain -
    isse "stratified sampling" kehte hain. Har tarah ka source test
    set mein aata hai.

    Jo already_done_ids pehle se label ho chuke hain (purane 50 wale
    round se), unhe hamesha shaamil rakhte hain - taaki pehle ka kaam
    zaya na ho.
    """
    sources = _sources
    already_done_ids = set(already_done_ids)

    forced = sources[sources.source_id.isin(already_done_ids)]
    result = forced

    # sirf tab base-stratification chalao jab forced (jo already ho chuka
    # hai) abhi BASE_TARGET tak nahi pahuncha - warna ye ulta zyada
    # sources jod deta hai kyunki forced khud hi target se bada ho chuka.
    if len(result) < BASE_TARGET:
        groups = sources.groupby(["region", "rule_label"])
        n_groups = len(groups)
        per_group = max(1, BASE_TARGET // n_groups)

        picked = [result]
        for _, group in groups:
            group = group[~group.source_id.isin(already_done_ids)]
            # random_state fix hai, taaki app dobara kholne pe wahi sources aayein
            picked.append(group.sample(min(per_group, len(group)), random_state=42))

        result = pd.concat(picked).drop_duplicates(subset="source_id")

        # agar target se kam hue to baaki random bhar do
        if len(result) < BASE_TARGET:
            remaining = sources[~sources.source_id.isin(result.source_id)]
            extra = remaining.sample(min(BASE_TARGET - len(result), len(remaining)),
                                     random_state=42)
            result = pd.concat([result, extra])

        # agar target se zyada ho gaye, to order ke hisaab se kaat-na mat -
        # (isse pichhle region/label poore ke poore gayab ho jaate the).
        # forced wale hamesha rakho, baaki mein se random ghata do - taaki
        # sab groups ka hissa barabar bacha rahe.
        if len(result) > BASE_TARGET:
            rest = result[~result.source_id.isin(forced.source_id)]
            keep_extra = rest.sample(BASE_TARGET - len(forced), random_state=42)
            result = pd.concat([forced, keep_extra])

    # BALANCE_TOP_UP: AGRI_BURN hawi ho gaya (data mein wahi sabse zyada
    # hai). Ab sirf non-AGRI_BURN se aur sources jodo (agar abhi tak
    # itne nahi jud paaye), taaki INDUSTRIAL/FOREST_FIRE/UNSURE ka
    # hissa bhi thik-thaak ho.
    n_non_agri_have = (result.rule_label != "AGRI_BURN").sum()
    non_agri_needed = max(0, BALANCE_TOP_UP - n_non_agri_have)

    if non_agri_needed > 0:
        non_agri = sources[(sources.rule_label != "AGRI_BURN") &
                           (~sources.source_id.isin(result.source_id))]
        ng = non_agri.groupby(["region", "rule_label"])
        per_ng = max(1, non_agri_needed // max(1, len(ng)))

        balance_picked = []
        for _, group in ng:
            balance_picked.append(group.sample(min(per_ng, len(group)), random_state=7))
        if balance_picked:
            balance = pd.concat(balance_picked).drop_duplicates(subset="source_id")
            if len(balance) > non_agri_needed:
                balance = balance.sample(non_agri_needed, random_state=7)
            result = pd.concat([result, balance]).drop_duplicates(subset="source_id")

    return result.sample(frac=1, random_state=42).reset_index(drop=True)


def load_done():
    """Ab tak kitne label ho chuke."""
    if GOLD_CSV.exists():
        return pd.read_csv(GOLD_CSV)
    return pd.DataFrame(columns=["source_id", "gold_label", "notes"])


def save_answer(source_id, label, notes):
    """Ek jawab CSV mein likh do - turant, taaki kuch na khoye."""
    done = load_done()
    done = done[done.source_id != source_id]         # purana hata do
    new = pd.DataFrame([{"source_id": source_id,
                         "gold_label": label,
                         "notes": notes}])
    pd.concat([done, new], ignore_index=True).to_csv(GOLD_CSV, index=False)


# ===============================================================
# App
# ===============================================================
sources, detections = load_data()
done = load_done()
todo = pick_sources(sources, tuple(sorted(done.source_id)))

st.title("150 sources khud label karo")

remaining = todo[~todo.source_id.isin(done.source_id)]

# ---- progress ----
n_done = len(todo) - len(remaining)
st.progress(n_done / len(todo), text=f"{n_done} / {len(todo)} ho gaye")

if len(remaining) == 0:
    st.success(f"Sab ho gaye! {GOLD_CSV} mein save hain.")
    st.write(load_done())
    st.stop()

# jo bacha hai usme se pehla dikhao
row = remaining.iloc[0]
mine = detections[detections.source_id == row.source_id].copy()

st.caption(f"source: `{row.source_id}`  |  region: **{row.region}**")

left, right = st.columns([1, 1])

# ---------------- baayein: photo ----------------
with left:
    st.subheader("Satellite photo")
    chip_path = DATA_CHIPS / f"{row.source_id}.jpg"
    if not chip_path.exists():
        with st.spinner("photo download ho rahi hai..."):
            chip_path = download_chip(row.source_id, row.lat, row.lon)

    if chip_path and Path(chip_path).exists():
        st.image(str(chip_path),
                 caption="source photo ke BEECH mein hai", width="stretch")
    else:
        st.warning("photo nahi mili")

    # Google Maps ka link - shak ho to wahan zoom karke dekh lo
    st.markdown(
        f"[Google Maps pe kholo]"
        f"(https://www.google.com/maps/@{row.lat},{row.lon},1000m/data=!3m1!1e3)"
    )

# ---------------- daayein: numbers ----------------
with right:
    st.subheader("Is source ke numbers")

    a, b = st.columns(2)
    a.metric("kitni baar dikha", int(row.n_detections))
    b.metric("kitne alag din", int(row.n_days))
    a.metric("kitne din tak", f"{int(row.lifespan_days)} din")
    b.metric("raat ke detections", f"{row.night_ratio * 100:.0f}%")
    a.metric("factory se doori", f"{row.dist_to_industry_m:,.0f} m")
    b.metric("garmi (FRP median)", f"{row.frp_median:.1f}")

    st.write(f"**paas ki industry:** {row.industry_name or '— koi nahi —'}")
    st.write(f"**zameen ka type:** {row.lc_class}")
    st.write(f"**tier:** {row.persistence_tier}")
    st.write(f"**dikha:** {row.first_seen} se {row.last_seen} tak")
    st.write(f"**rules ne kaha:** `{row.rule_label}`")
    if pd.notna(row.get("vlm_landuse")):
        st.write(f"**AI ne photo mein dekha:** `{row.vlm_landuse}` "
                 f"({row.vlm_confidence})")

    # FRP ka chart - waqt ke saath garmi kaise badli
    if len(mine) > 1:
        st.subheader("Garmi (FRP) waqt ke saath")
        chart = (mine.assign(date=pd.to_datetime(mine.acq_date))
                     .groupby("date")["frp"].max())
        st.line_chart(chart)
        st.caption("faili hui line = saal bhar chalne wala source (factory jaisa). "
                   "ek hi tez chubhan = ek baar ki aag.")

# ---------------- neeche: buttons ----------------
st.divider()
st.subheader("Ye kya hai?")

notes = st.text_input("Notes (kuch ajeeb laga to yahan likho)", key=row.source_id)

c1, c2, c3, c4 = st.columns(4)
buttons = [
    (c1, "INDUSTRIAL", "factory / refinery"),
    (c2, "FOREST_FIRE", "jungle ki aag"),
    (c3, "AGRI_BURN", "khet ki aag"),
    (c4, "UNCLEAR", "samajh nahi aaya"),
]
for col, label, hint in buttons:
    with col:
        if st.button(label, width="stretch", key=f"btn_{label}"):
            save_answer(row.source_id, label, notes)
            st.rerun()
        st.caption(hint)

st.divider()
with st.expander("Kaise decide karun?"):
    st.markdown("""
**INDUSTRIAL** — photo mein gol storage tank, chimney, pipe, bade shed,
paved yard. Numbers mein: saal bhar dikha, raat ko dikha, factory se 0 m.

**FOREST_FIRE** — photo mein ghane ped. Numbers mein: kuch hi din chala,
factory se bahut door.

**AGRI_BURN** — photo mein chaukor khet, seedhi medh, jale hue kaale khet.
Numbers mein: ek-do din, din ka waqt, Apr/May ya Oct/Nov.

**UNCLEAR** — photo dhundhli hai, badal hain, ya sach mein samajh nahi
aa raha. **Ye dabana galat nahi hai** — jhootha jawab dene se behtar hai.

*Tip:* pehle photo dekho, phir numbers. Agar dono alag keh rahe hain,
to wo source dilchasp hai — notes mein likh do, wo PPT mein jayega.
    """)
