"""
STEP 4 (part 2) - confusing sources pe AI ki nazar.

Rules ne 2,152 sources ko "UNSURE" chhod diya - unpe koi rule fit nahi
baitha. Aur kuch sources "confusing zone" mein hain (factory se 500 se
3000 metre door - itni paas ki shayad factory ka hissa ho, itni door ki
shayad kuch aur).

In pe hum kya karte hain: us jagah ki SATELLITE PHOTO nikaalte hain aur
Claude se poochte hain "is photo mein kya dikh raha hai?"

Kyun ye kaam karta hai: rules sirf NUMBERS dekhte hain (doori, mahina,
raat/din). Photo mein aankhon se dikh jata hai ki wahan factory hai,
jungle hai, ya khet hai. Jahan OSM ka data adhoora hai (jaise Punjab ke
khet), wahan photo hi sach bata sakti hai.

Input : data/processed/sources_labelled.gpkg
Output: wahi file, par ab usme vlm_landuse / vlm_confidence / vlm_reason
        aur updated label bhi hai
        data/chips/<source_id>.jpg  (downloaded satellite photos)

CHALANE SE PEHLE: .env mein ANTHROPIC_API_KEY daalna hoga.
    https://console.anthropic.com/settings/keys

Chalane ka tareeka:
    python src/step4b_vlm.py            # 100 sources (default)
    python src/step4b_vlm.py --limit 20 # sirf 20 (test ke liye)
"""
import base64
import io
import json
import math
import os
import sys

import geopandas as gpd
import requests
from PIL import Image
from dotenv import load_dotenv
from tqdm import tqdm

from config import DATA_PROCESSED, DATA_CHIPS, VLM_MODEL, VLM_MAX_SOURCES

load_dotenv()

# Esri ki free satellite imagery. Zoom 15 = lagbhag 4.8 metre per pixel -
# itne mein factory ke tank, khet ki lakeerein, jungle sab pehchane jaate hain.
TILE_URL = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}")
ZOOM = 15
TILE_PX = 256      # har tile 256x256 pixel ka hota hai
CHIP_PX = 512      # final photo ka size - lagbhag 2.5 km x 2.5 km zameen

# har 10 photos ke baad save karo - crash ho to kaam na jaye
SAVE_EVERY = 10


# ===============================================================
# lat/lon -> tile number
# ===============================================================
def latlon_to_tile_float(lat, lon, zoom):
    """
    Latitude/longitude ko "tile number" mein badalta hai - dashamlav ke saath.

    Duniya ka naksha chhote-chhote chaukor tukdon (tiles) mein bata hua
    hai. Zoom 15 pe duniya 2^15 = 32,768 tiles chaudi hai, aur har tile
    256x256 pixel ka.

    Dashamlav kyun rakhte hain: 22743.6 ka matlab hai "22743 number ke
    tile ke andar, 60% aage". Isse pata chalta hai ki hamari jagah tile
    ke ANDAR kahan hai - kone pe ya beech mein.

    y ka formula tedha isliye hai kyunki naksha "Mercator" projection
    mein hota hai - usme poles ki taraf jagah khinchti jaati hai.
    """
    n = 2.0 ** zoom
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def latlon_to_tile(lat, lon, zoom):
    """Poora tile number (bina dashamlav ke)."""
    x, y = latlon_to_tile_float(lat, lon, zoom)
    return int(x), int(y)


def fetch_tile(x, y, zoom):
    """Ek tile download karo. Nahi mila to None."""
    url = TILE_URL.format(z=zoom, x=x, y=y)
    try:
        resp = requests.get(url, timeout=30,
                            headers={"User-Agent": "SIH26162-student-project"})
    except requests.RequestException:
        return None
    if resp.status_code != 200 or len(resp.content) < 1000:
        return None
    return resp.content


def download_chip(source_id, lat, lon):
    """
    Ek source ki satellite photo banata hai, jisme wo source BILKUL
    BEECH mein ho.

    -----------------------------------------------------------------
    Seedha ek tile download karna KAAFI NAHI hai.

    Tile number nikalte waqt hum dashamlav kaat dete hain (22743.6 ->
    22743). Iska matlab hamari jagah us tile ke kone pe bhi ho sakti
    hai, beech mein bhi. Zoom 15 pe ek tile ~1.2 km ka hota hai, to
    source photo ke beech se 1 km tak hat sakta hai!

    Aur hum Claude se kehte hain "photo ke BEECH wale hisse ko dekho" -
    to wo galat jagah dekhta.

    Isliye: 3x3 = 9 tiles download karke jodte hain, phir beech wale
    source ke theek upar se ek chaukor kaat lete hain. Ab source pakka
    beech mein hai.
    -----------------------------------------------------------------
    """
    path = DATA_CHIPS / f"{source_id}.jpg"
    if path.exists() and path.stat().st_size > 1000:
        return path

    fx, fy = latlon_to_tile_float(lat, lon, ZOOM)
    cx, cy = int(fx), int(fy)          # beech wala tile

    # 3x3 tiles ko ek badi photo mein jodo
    big = Image.new("RGB", (TILE_PX * 3, TILE_PX * 3))
    got_any = False
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            data = fetch_tile(cx + dx, cy + dy, ZOOM)
            if data is None:
                continue
            tile = Image.open(io.BytesIO(data)).convert("RGB")
            big.paste(tile, ((dx + 1) * TILE_PX, (dy + 1) * TILE_PX))
            got_any = True

    if not got_any:
        return None

    # badi photo mein hamari jagah kaunse pixel pe hai?
    # (fx - cx) matlab beech wale tile ke andar kitna aage - 0 se 1 ke beech.
    # +1 isliye kyunki beech wala tile grid mein doosre number pe hai.
    px = int((fx - cx + 1) * TILE_PX)
    py = int((fy - cy + 1) * TILE_PX)

    half = CHIP_PX // 2
    chip = big.crop((px - half, py - half, px + half, py + half))
    chip.save(path, "JPEG", quality=85)
    return path


# ===============================================================
# Claude se poochna
# ===============================================================
PROMPT = """Ye ek satellite photo hai (Esri World Imagery, zoom 15).
Photo ke BEECH wale hisse ko dekho - wahin thermal detection aayi thi.

Batao us jagah pe kya hai. Sirf PHOTO dekh kar batao.

{hint}

Dhyan rakhna:
- industrial mein aate hain: refinery, factory, power plant, gol storage
  tanks, chimney, bade shed, paved yard
- cropland mein aate hain: chaukor/aayat khet, seedhi medh ki lakeerein,
  jale hue kaale khet
- forest matlab ghane ped
- barren matlab khaali sookhi zameen, na khet na ped
- agar photo dhundhli hai ya badal hain to "unclear" kehna"""

HINT = """Ek ishara: OSM ke hisaab se paas mein "{name}" naam ki industry
hai, lagbhag {dist:.0f} metre door. PAR ye ishara galat bhi ho sakta hai -
jo PHOTO mein dikhe usi pe bharosa karo, ishare pe nahi."""

# Jawab ka dhaancha. Isse Claude ka jawab HAMESHA valid JSON aata hai -
# "```json" jaisi galtiyan nahi hoti, parse karne ki tension nahi.
SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "landuse": {
                "type": "string",
                "enum": ["industrial", "mine", "forest", "cropland",
                         "urban", "water", "barren", "unclear"],
            },
            "confidence": {"type": "number"},
            "reason": {"type": "string"},
        },
        "required": ["landuse", "confidence", "reason"],
        "additionalProperties": False,
    },
}


def ask_claude(client, image_path, industry_name, dist):
    """
    Photo Claude ko bhejo aur poocho wahan kya hai.
    Return: dict, ya None agar kuch gadbad ho.

    GALTIYAN CHUP-CHAAP NAHI CHHUPTIN: har fail hone ki wajah alag se
    chhapti hai. 8,000 sources pe chalate waqt "kuch nahi hua" sabse
    khatarnak jawab hai - pata hi nahi chalta ki rate limit lagi thi,
    internet gaya tha, ya jawab hi kharab aaya tha.
    """
    import anthropic

    image_b64 = base64.standard_b64encode(image_path.read_bytes()).decode()

    hint = ""
    if industry_name and str(industry_name) != "nan":
        hint = HINT.format(name=industry_name, dist=dist)

    try:
        response = client.messages.create(
            model=VLM_MODEL,
            max_tokens=1024,
            # effort medium: ye ek seedha "photo mein kya hai" wala sawaal
            # hai, isme gehri sochne ki zaroorat nahi
            output_config={"effort": "medium", "format": SCHEMA},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64,
                    }},
                    {"type": "text", "text": PROMPT.format(hint=hint)},
                ],
            }],
        )
    # Alag-alag galti ka alag matlab hai, isliye alag-alag pakadte hain.
    # Sabse khaas pehle, aam baad mein.
    except anthropic.BadRequestError as e:
        # aksar photo hi kharab hai (khaali file, galat format)
        print(f"\n  request galat ({image_path.name}): {e}")
        return None
    except anthropic.AuthenticationError:
        # ye har source pe dohrayegi - rukna hi theek hai
        sys.exit("\n  ANTHROPIC_API_KEY galat hai. .env dekho.")
    except anthropic.RateLimitError as e:
        # SDK khud 2 baar retry kar chuka hota hai, tab jaake yahan aata hai
        retry = e.response.headers.get("retry-after", "?")
        print(f"\n  rate limit lagi (retry-after: {retry}s) - ye source chhoda")
        return None
    except anthropic.APIStatusError as e:
        print(f"\n  API error {e.status_code}: {str(e)[:120]}")
        return None
    except anthropic.APIConnectionError:
        print("\n  internet/connection problem - ye source chhoda")
        return None

    # Claude mana bhi kar sakta hai. Tab content khaali hoti hai, aur
    # bina check kiye padhoge to crash - 500 photos ke baad.
    if response.stop_reason == "refusal":
        why = getattr(response.stop_details, "category", None)
        print(f"\n  model ne jawab dene se mana kiya ({why})")
        return None

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # schema ke rehte aisa hona nahi chahiye, par agar ho to ek
        # source chhodna theek hai - poora run girana nahi.
        print(f"\n  jawab JSON nahi tha: {text[:80]}")
        return None


# ===============================================================
# VLM ka jawab -> hamara label
# ===============================================================
VLM_TO_LABEL = {
    "industrial": "INDUSTRIAL",
    "mine": "INDUSTRIAL",       # khadaan bhi industrial activity hai
    "forest": "FOREST_FIRE",
    "cropland": "AGRI_BURN",
    # urban / water / barren / unclear -> UNSURE hi rehne do.
    # "pata nahi" kehna galat jawab dene se behtar hai.
}


# ===============================================================
# Main
# ===============================================================
def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY nahi mili.")
        print("  .env file mein ye line daalo:")
        print("      ANTHROPIC_API_KEY=sk-ant-...")
        print("  Key yahan se: https://console.anthropic.com/settings/keys")
        sys.exit(1)

    import anthropic
    client = anthropic.Anthropic()

    path = DATA_PROCESSED / "sources_labelled.gpkg"
    if not path.exists():
        print("ERROR: sources_labelled.gpkg nahi mili.")
        print("  pehle ye chalao: python src/step4_labels.py")
        sys.exit(1)

    sources = gpd.read_file(path)

    limit = VLM_MAX_SOURCES
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    # ---- kaunse sources dekhne hain ----
    # jinpe review chahiye, aur jinpe pehle se VLM nahi chala
    todo = sources[sources["needs_review"]].copy()
    if "vlm_landuse" in sources.columns:
        todo = todo[todo["vlm_landuse"].isna()]

    # Sabse zyada detection wale pehle - unka asar sabse zyada hai,
    # aur unki photo bhi zyada bharosemand hoti hai
    todo = todo.nlargest(limit, "n_detections")

    print(f"{len(sources)} sources mein se {sources['needs_review'].sum()} pe "
          f"review chahiye")
    print(f"AI ko dikha rahe hain: {len(todo)}  (model: {VLM_MODEL})\n")

    if len(todo) == 0:
        print("kuch karne ko nahi hai")
        return

    # ---- naye columns ----
    for col in ["vlm_landuse", "vlm_confidence", "vlm_reason"]:
        if col not in sources.columns:
            sources[col] = None

    done = 0
    for idx, row in tqdm(todo.iterrows(), total=len(todo), desc="photos"):
        chip = download_chip(row["source_id"], row["lat"], row["lon"])
        if chip is None:
            continue

        answer = ask_claude(client, chip, row["industry_name"],
                            row["dist_to_industry_m"])
        if answer is None:
            continue

        sources.loc[idx, "vlm_landuse"] = answer["landuse"]
        sources.loc[idx, "vlm_confidence"] = answer["confidence"]
        sources.loc[idx, "vlm_reason"] = answer["reason"][:300]

        # AI ka jawab hamare label mein badlo
        new_label = VLM_TO_LABEL.get(answer["landuse"])
        if new_label:
            sources.loc[idx, "label"] = new_label
            sources.loc[idx, "label_source"] = "vlm"

        done += 1
        if done % SAVE_EVERY == 0:
            sources.to_file(path, driver="GPKG")

    sources.to_file(path, driver="GPKG")

    # ---- report ----
    print(f"\n{done} sources pe AI chala")
    print(f"SAVED: {path}\n")

    seen = sources[sources["vlm_landuse"].notna()]
    if len(seen) > 0:
        print("AI ne photo mein kya dekha:")
        print(seen["vlm_landuse"].value_counts().to_string())
        print(f"\nlabel VLM se aaya: {(sources['label_source'] == 'vlm').sum()}")
        print("\nab labels aise hain:")
        print(sources["label"].value_counts().to_string())


if __name__ == "__main__":
    main()
