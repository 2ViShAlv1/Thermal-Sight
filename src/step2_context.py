"""
STEP 2 - har hotspot ke aas-paas kya hai, ye pata karna.

"Context" ka matlab: har garam point ke aas-paas kya hai?
Factory? Jungle? Khet? Wahi decide karega label.

Is file mein DO parts hain:

  PART 1 - OSM se polygons nikalna
     Input : data/raw/*.osm.pbf
     Output: industry.gpkg (factories) + landuse.gpkg (forest/khet/shehar)

  PART 2 - un polygons ko hotspots se jodna
     Input : hotspots.gpkg + industry.gpkg + landuse.gpkg
     Output: features.gpkg - har hotspot pe distance aur landcover

Part 1 ka output part 2 ka input hai. Agar part 1 ki files pehle se
maujood hain to wo skip ho jata hai (2 minute bachte hain).

Chalane ka tareeka:
    python src/step2_context.py            # jo missing hai wahi banega
    python src/step2_context.py --force    # sab kuch dobara
"""
import os
import sys
import warnings

import geopandas as gpd
import pandas as pd
import pyogrio

from config import (REGIONS, REGION_PBF, DATA_RAW, DATA_PROCESSED,
                    CRS_LATLON, CRS_METRES)

# GDAL ko bada temp buffer do, warna bade pbf pe "tmpfile too small" error aata hai
os.environ.setdefault("OSM_MAX_TMPFILE_SIZE", "4000")   # MB

# OSM data mein tooti-phooti geometries aam baat hai (non-closed rings waghairah).
# GDAL unhe khud theek kar leta hai, bas screen bhar bhar ke warning deta hai.
# Warnings chhupa rahe hain taaki asli output dikhe.
warnings.filterwarnings("ignore", category=RuntimeWarning)


# ===============================================================
# OSM tags parse karne ka helper
# ===============================================================
def parse_other_tags(text):
    """
    GDAL saare 'extra' OSM tags ko ek hi string mein daal deta hai,
    is format mein:   "power"=>"plant","operator"=>"NTPC"
    Ye function usse ek normal Python dict bana deta hai.

    Zaroorat kyun: 'power' aur 'industrial' jaise tags GDAL ke default
    columns mein nahi aate, sirf is string ke andar hote hain.
    """
    tags = {}
    if not text or not isinstance(text, str):
        return tags
    # simple split - OSM values mein comma ho sakta hai, isliye '","' pe todte hain
    for part in text.split('","'):
        if "=>" not in part:
            continue
        key, _, value = part.partition("=>")
        tags[key.strip().strip('"')] = value.strip().strip('"')
    return tags


def tag_value(row, key):
    """Pehle asli column dekho, na mile to other_tags dict mein dekho."""
    if key in row and pd.notna(row[key]):
        return str(row[key]).lower()
    return str(row.get("_tags", {}).get(key, "")).lower()


# ===============================================================
# pbf file dhoondhna aur bbox se clip karna
# ===============================================================
def pbf_for_region(region_name):
    """
    Is region ki zone file ka path do.

    Har region ek hi zone mein hai (config.REGION_PBF dekho), isliye
    saari pbf files scan karne ki zaroorat nahi - seedha sahi file
    kholte hain. Isse 3 guna tez chalta hai.
    """
    filename = REGION_PBF[region_name]
    path = DATA_RAW / filename
    if not path.exists():
        print(f"  ERROR: {filename} nahi mili.")
        print(f"    download: https://download.geofabrik.de/asia/india/{filename}")
        print(f"    aur data/raw/ mein rakho")
        return None
    return path


def read_region_polygons(pbf_path, bbox):
    """
    Ek pbf se sirf ek region ke bbox ke andar ke multipolygons padho.

    ZAROORI: bbox filter yahin lagta hai. Poori India file kabhi
    memory mein mat lo - ghante lag jayenge aur RAM khatam ho jayegi.
    pyogrio ka bbox= argument ye kaam GDAL ke level pe kar deta hai.
    """
    try:
        gdf = pyogrio.read_dataframe(
            pbf_path,
            layer="multipolygons",
            bbox=bbox,          # (west, south, east, north) - config wala hi order
        )
    except Exception as e:
        print(f"    padhne mein problem ({pbf_path.name}): {e}")
        return gpd.GeoDataFrame()

    if len(gdf) == 0:
        return gdf

    # other_tags string ko dict mein badal do, taaki power/industrial mil sakein
    if "other_tags" in gdf.columns:
        gdf["_tags"] = gdf["other_tags"].apply(parse_other_tags)
    else:
        gdf["_tags"] = [{} for _ in range(len(gdf))]

    return gdf


# ===============================================================
# INDUSTRY - factory / refinery / plant wale polygons
# ===============================================================
INDUSTRY_MAN_MADE = ("works", "petroleum_well", "flare", "storage_tank")


def is_industry(row):
    """Ek polygon industry hai ya nahi - plan ke rules seedha yahan."""
    landuse = tag_value(row, "landuse")
    man_made = tag_value(row, "man_made")
    power = tag_value(row, "power")
    industrial = tag_value(row, "industrial")

    if landuse in ("industrial", "quarry"):
        return True
    if man_made in INDUSTRY_MAN_MADE:
        return True
    if power == "plant":
        return True
    if industrial != "":              # 'industrial' tag ka hona hi kaafi hai
        return True
    return False


def simplify_industry_type(row):
    """
    OSM mein 50 tarah ke tags hote hain. Model ke liye unhe 7 buckets
    mein daal dete hain - kam categories = model ke liye aasan.
    """
    landuse = tag_value(row, "landuse")
    man_made = tag_value(row, "man_made")
    power = tag_value(row, "power")
    industrial = tag_value(row, "industrial")
    name = str(row.get("name") or "").lower()

    # naam mein hi jawab hota hai kai baar (e.g. "Reliance Jamnagar Refinery")
    if "refin" in name or industrial == "oil" or man_made in ("petroleum_well", "flare"):
        return "refinery"
    if power == "plant" or "power" in name or "thermal" in name:
        return "power_plant"
    if "steel" in name or industrial == "steel":
        return "steel"
    if "chemical" in name or "cement" in name or industrial in ("chemical", "cement"):
        return "chemical"
    if landuse == "quarry" or industrial == "mine":
        return "mine"
    if man_made in ("storage_tank", "works") and "tank" in man_made:
        return "storage"
    if man_made == "storage_tank":
        return "storage"
    return "other"


# ===============================================================
# LANDUSE - forest / cropland / urban
# ===============================================================
def landcover_class(row):
    """Polygon ka land cover. Match na ho to None (row hata denge)."""
    landuse = tag_value(row, "landuse")
    natural = tag_value(row, "natural")

    if natural == "wood" or landuse == "forest":
        return "forest"
    if landuse in ("farmland", "orchard"):
        return "cropland"
    if landuse in ("residential", "commercial"):
        return "urban"
    return None


def fix_geometries(gdf, label):
    """
    Tooti hui geometries theek karo.

    OSM mein self-intersecting rings ("bow-tie" shapes) aam hain -
    kisi ne map karte waqt line cross kar di. GeoPandas inhe padh to
    leta hai, par sjoin / distance jaise operations un pe galat jawab
    de sakte hain ya crash kar sakte hain.

    make_valid() unhe repair kar deta hai, par wo aksar polygon ko
    GeometryCollection bana deta hai - polygon + wo lines jahan ring
    khud ko cut kar raha tha. Un lines ka humein koi kaam nahi
    (area zero hai), isliye collection mein se sirf polygon wale
    hisse nikaal lete hain. Row girana galat hoga - us jungle ka
    area asli hai, bas uski drawing tooti thi.
    """
    invalid = ~gdf.geometry.is_valid
    if not invalid.any():
        return gdf

    print(f"  {invalid.sum()} tooti geometry {label} mein - repair kar rahe hain")
    gdf = gdf.copy()
    repaired = gdf.loc[invalid, "geometry"].make_valid()

    # GeometryCollection mein se sirf Polygon/MultiPolygon rakho
    repaired = repaired.apply(keep_polygons_only)
    gdf.loc[invalid, "geometry"] = repaired

    # ab bhi agar kuch khaali hai to hi girao
    empty = gdf.geometry.is_empty | gdf.geometry.isna()
    if empty.any():
        print(f"    {empty.sum()} repair ke baad bhi khaali - hata diye")
        gdf = gdf[~empty]

    still_bad = (~gdf.geometry.is_valid).sum()
    print(f"    ab {still_bad} invalid bache")
    return gdf


def keep_polygons_only(geom):
    """
    make_valid() ka output GeometryCollection ho sakta hai.
    Usme se sirf area wale (polygon) hisse rakho, lines/points phenk do.
    """
    if geom is None or geom.is_empty:
        return geom
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if geom.geom_type == "GeometryCollection":
        parts = [g for g in geom.geoms
                 if g.geom_type in ("Polygon", "MultiPolygon")]
        if not parts:
            return geom
        if len(parts) == 1:
            return parts[0]
        from shapely.ops import unary_union
        return unary_union(parts)
    return geom


# ===============================================================
# PART 2 - polygons ko hotspots se jodna
# ===============================================================
def add_context_features():
    """
    Har hotspot ke liye do sawaal ka jawab nikalta hai:

      1. Sabse nazdeeki factory kitni door hai?  -> dist_to_industry_m
      2. Ye point kis tarah ki zameen pe hai?    -> lc_class

    Ye do jawab hi aage ka pura labelling decide karenge.
    """
    print("\n" + "=" * 55)
    print("PART 2 - hotspots pe context features lagana")
    print("=" * 55)

    hotspots = gpd.read_file(DATA_PROCESSED / "hotspots.gpkg")
    industry = gpd.read_file(DATA_PROCESSED / "industry.gpkg")
    landuse = gpd.read_file(DATA_PROCESSED / "landuse.gpkg")
    print(f"load: {len(hotspots)} hotspots, {len(industry)} industry, "
          f"{len(landuse)} landuse")

    # -----------------------------------------------------------
    # SABSE ZAROORI STEP - metre wale CRS mein convert karo
    #
    # Abhi teeno files EPSG:4326 mein hain, yani numbers DEGREES mein.
    # Degrees mein distance naapna bekaar hai: jawab "0.004" aayega,
    # aur 0.004 degree kitne metre hai ye latitude pe depend karta hai
    # (poles ke paas longitude ki lines paas aa jati hain).
    #
    # EPSG:32643 (UTM zone 43N) metres mein hai. Convert karne ke baad
    # "500" ka matlab seedha 500 metre.
    #
    # Agar ye step bhool gaye to teeno regions ke numbers ek jaise
    # aayenge - wahi sabse bada warning sign hai.
    # -----------------------------------------------------------
    hotspots = hotspots.to_crs(CRS_METRES)
    industry = industry.to_crs(CRS_METRES)
    landuse = landuse.to_crs(CRS_METRES)
    print(f"CRS -> EPSG:{CRS_METRES} (ab sab metres mein hai)")

    # -----------------------------------------------------------
    # FEATURE 1 - sabse nazdeeki factory kitni door hai
    #
    # sjoin_nearest har hotspot ke liye sabse paas wala industry
    # polygon dhoondh leta hai aur doori distance_col mein bhar deta hai.
    # Agar point polygon ke ANDAR hai to distance 0 aata hai.
    # -----------------------------------------------------------
    ind_cols = industry[["industry_type", "name", "geometry"]].rename(
        columns={"name": "industry_name"}
    )
    feat = gpd.sjoin_nearest(hotspots, ind_cols, how="left",
                             distance_col="dist_to_industry_m")
    feat = dedup_join(feat, len(hotspots), "sjoin_nearest (industry)")
    feat = feat.drop(columns=["index_right"], errors="ignore")

    # -----------------------------------------------------------
    # FEATURE 2 - ye point kis tarah ki zameen pe hai
    #
    # predicate="within" matlab: point polygon ke ANDAR ho tabhi match.
    # Jis point pe koi polygon nahi hai (OSM pe mapped hi nahi), uska
    # jawab khaali aayega - use "unknown" bhar dete hain.
    # -----------------------------------------------------------
    lc_cols = landuse[["lc_class", "geometry"]]
    feat = gpd.sjoin(feat, lc_cols, how="left", predicate="within")
    feat = dedup_join(feat, len(hotspots), "sjoin within (landuse)")
    feat = feat.drop(columns=["index_right"], errors="ignore")
    feat["lc_class"] = feat["lc_class"].fillna("unknown")

    # -----------------------------------------------------------
    # FEATURE 3, 4 - time se jude do simple features
    # -----------------------------------------------------------
    # month: season pakadne ke liye. Parali Apr-May aur Oct-Nov mein
    # jalti hai, jungle ki aag Apr-Jun mein.
    feat["month"] = pd.to_datetime(feat["acq_date"]).dt.month

    # is_night: raat ka detection zyada bharosemand hai. Dhoop se garam
    # hui chhat raat ko garam nahi dikhti, par factory ka flare dikhta hai.
    # Yahi feature aage industry aur agri ko alag karega.
    feat["is_night"] = (feat["daynight"] == "N").astype(int)

    out = DATA_PROCESSED / "features.gpkg"
    feat.to_crs(CRS_LATLON).to_file(out, driver="GPKG")
    print(f"\nSAVED: {out}  ({len(feat)} rows, {len(feat.columns)} columns)")

    print_feature_summary(feat)
    return feat


def dedup_join(joined, expected_rows, label):
    """
    Spatial join ke baad duplicate rows hata deta hai.

    KYUN ZAROORI: sjoin ek hotspot ke liye DO rows bana sakta hai -
    agar wo do overlapping polygons ke andar ho (jaise forest aur
    urban dono), ya sjoin_nearest mein do polygons barabar door hon.

    Aisa hone pe koi error nahi aata - rows chup-chaap badh jate hain,
    aur aage saare counts galat ho jaate hain. Isliye har join ke baad
    check karna zaroori hai.
    """
    extra = len(joined) - expected_rows
    if extra > 0:
        joined = joined[~joined.index.duplicated(keep="first")]
        print(f"  {label}: {extra} duplicate rows bane the, hata diye")
    return joined


def print_feature_summary(feat):
    """
    Region-wise summary - ye check karne ke liye ki CRS sahi laga hai.

    Teeno regions ke numbers ALAG hone chahiye. Agar ek jaise aayein
    to CRS ki galti hai - wahin ruk ke fix karo, aage mat badho.
    """
    print("\n" + "-" * 55)
    print("SUMMARY (har region alag dikhna chahiye)")
    print("-" * 55)
    for region in feat["region"].unique():
        sub = feat[feat["region"] == region]
        print(f"\n{region.upper()}  ({len(sub)} hotspots)")
        print(f"  factory se doori (median) : {sub['dist_to_industry_m'].median():>10,.0f} m")
        print(f"  1 km ke andar             : {(sub['dist_to_industry_m'] < 1000).mean() * 100:>10.1f} %")
        print(f"  raat ke detections        : {sub['is_night'].mean() * 100:>10.1f} %")
        print("  land cover:")
        for cls, n in sub["lc_class"].value_counts().items():
            print(f"      {cls:<10} {n:>6}  ({n / len(sub) * 100:.1f}%)")


# ===============================================================
# Main
# ===============================================================
def missing_regions():
    """
    Kaunse regions ke polygons abhi nahi bane.

    Sirf file ka hona kaafi nahi hai - file purani ho sakti hai. Agar
    config.py mein naya region add kiya gaya, to file to maujood hogi
    par usme wo region hoga hi nahi, aur uske saare hotspots bina
    context ke reh jayenge.

    Isliye har region ko file ke ANDAR dhoondhte hain.
    """
    missing = set()
    for name in ("industry", "landuse"):
        path = DATA_PROCESSED / f"{name}.gpkg"
        if not path.exists():
            return sorted(REGIONS)          # kuch bhi nahi hai
        have = set(gpd.read_file(path)["region"].unique())
        missing |= set(REGIONS) - have
    return sorted(missing)


def extract_polygons():
    """PART 1 - OSM pbf se industry aur landuse polygons nikalna."""
    print("=" * 55)
    print("PART 1 - OSM se polygons nikalna")
    print("=" * 55)
    industry_parts = []
    landuse_parts = []

    for region_name, bbox in REGIONS.items():
        print(f"=== {region_name.upper()}  bbox={bbox} ===")

        pbf = pbf_for_region(region_name)
        if pbf is None:
            print()
            continue

        print(f"  {pbf.name} padh rahe hain (bbox clip ke saath)...")
        region_gdf = read_region_polygons(pbf, bbox)
        print(f"    -> {len(region_gdf)} polygons bbox ke andar")

        if len(region_gdf) == 0:
            # ye tab hota hai jab zone file mein ye region hai hi nahi.
            # config.REGION_PBF check karo.
            print(f"  !! {region_name} mein koi polygon nahi mila - galat zone file?\n")
            continue

        # ---------- INDUSTRY ----------
        ind_mask = region_gdf.apply(is_industry, axis=1)
        ind = region_gdf[ind_mask].copy()
        if len(ind) > 0:
            ind["industry_type"] = ind.apply(simplify_industry_type, axis=1)
            ind["region"] = region_name
            industry_parts.append(ind[["osm_id", "name", "industry_type", "region", "geometry"]])

        # ---------- LANDUSE ----------
        region_gdf["lc_class"] = region_gdf.apply(landcover_class, axis=1)
        lc = region_gdf[region_gdf["lc_class"].notna()].copy()
        if len(lc) > 0:
            lc["region"] = region_name
            landuse_parts.append(lc[["osm_id", "name", "lc_class", "region", "geometry"]])

        # ---------- per-region report ----------
        print(f"  industry polygons : {len(ind)}")
        if len(ind) > 0:
            for t, c in ind["industry_type"].value_counts().items():
                print(f"      {t:<12} {c}")
        else:
            # ye loud warning plan mein maanga gaya hai
            print("  " + "!" * 50)
            print(f"  !! WARNING: {region_name} mein ZERO industry polygons!")
            print("  !! Matlab galat zone file hai (config.REGION_PBF check karo),")
            print("  !! ya bbox galat hai.")
            print("  " + "!" * 50)

        print(f"  landuse polygons  : {len(lc)}")
        if len(lc) > 0:
            for t, c in lc["lc_class"].value_counts().items():
                print(f"      {t:<12} {c}")
        print()

    # ---------- save ----------
    if industry_parts:
        industry = gpd.GeoDataFrame(
            pd.concat(industry_parts, ignore_index=True), crs=CRS_LATLON
        )
        industry = fix_geometries(industry, "industry")
        out = DATA_PROCESSED / "industry.gpkg"
        industry.to_file(out, driver="GPKG")
        print(f"SAVED: {out}  ({len(industry)} polygons)")

    if landuse_parts:
        landuse = gpd.GeoDataFrame(
            pd.concat(landuse_parts, ignore_index=True), crs=CRS_LATLON
        )
        landuse = fix_geometries(landuse, "landuse")
        out = DATA_PROCESSED / "landuse.gpkg"
        landuse.to_file(out, driver="GPKG")
        print(f"SAVED: {out}  ({len(landuse)} polygons)")


def main():
    # --force diya ho to part 1 dobara chalega, warna sirf tab jab
    # files missing hon. Part 1 mein 2 minute lagte hain aur uska
    # output kabhi badalta nahi (jab tak pbf na badle), isliye use
    # baar-baar chalane ka koi matlab nahi.
    force = "--force" in sys.argv
    missing = missing_regions()

    if force or missing:
        if missing and not force:
            # Ye tab hota hai jab config.py mein naya region add kiya gaya ho.
            # Sirf "file maujood hai" check karna KAAFI NAHI - file purani ho
            # sakti hai aur usme naya region ho hi na. Ek baar ye galti ho
            # chuki hai, isliye ab region-wise check karte hain.
            print(f"PART 1 chalana padega - in regions ka data nahi hai: {missing}")
        extract_polygons()
    else:
        print("PART 1 skip - saare regions ke polygons pehle se hain")
        print("             (dobara banane ke liye: --force)")

    if not (DATA_PROCESSED / "hotspots.gpkg").exists():
        print("\nERROR: hotspots.gpkg nahi mili.")
        print("  pehle ye chalao: python src/step1_download.py")
        sys.exit(1)

    add_context_features()

    print("\nAgla step: python src/step3_persistence.py")


if __name__ == "__main__":
    main()
