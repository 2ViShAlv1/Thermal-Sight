"""
STEP 6 - final data PostGIS mein daalna.  (OPTIONAL)

KYUN:
    Project chalane ke liye ye ZAROORI NAHI hai. GeoPackage khud ek
    poora GIS format hai - QGIS usse seedha kholta hai, dashboard usse
    seedha padhta hai.

    Ye step isliye hai kyunki SIH ke deliverables mein aksar "spatial
    database" maanga jata hai. Agar PostGIS chal raha ho to data usme
    chala jayega; na chale to koi nuksan nahi, project waise hi chalega.

DATABASE CHALANE KA TAREEKA (Docker, ek command):

    docker run -d --name sih-postgis -p 5432:5432 \
        -e POSTGRES_PASSWORD=postgres postgis/postgis:16-3.4

    Phir .env mein (ya default hi chhod do):
        PG_HOST=localhost
        PG_PORT=5432
        PG_USER=postgres
        PG_PASSWORD=postgres
        PG_DATABASE=postgres

CHALANE KA TAREEKA:
    python src/step6_postgis.py           # sab tables daalo
    python src/step6_postgis.py --check   # sirf connection test karo
"""
import os
import sys

import geopandas as gpd
import pandas as pd
from dotenv import load_dotenv

from config import DATA_PROCESSED, CRS_LATLON

load_dotenv()

# Kaunsi file kis table mein jayegi
TABLES = {
    "hotspots":        "raw thermal detections (FIRMS se)",
    "sources":         "DBSCAN se bane sources",
    "sources_labelled": "sources + rules ke labels",
    "predictions":     "sources + model ka jawab + confidence",
    "industry":        "OSM/WRI ke industry polygons",
    "landuse":         "OSM ke landuse polygons",
}


def engine_url():
    return (f"postgresql://{os.getenv('PG_USER', 'postgres')}:"
            f"{os.getenv('PG_PASSWORD', 'postgres')}@"
            f"{os.getenv('PG_HOST', 'localhost')}:"
            f"{os.getenv('PG_PORT', '5432')}/"
            f"{os.getenv('PG_DATABASE', 'postgres')}")


def connect():
    """
    Connection banao. Na bane to saaf batao ki kya karna hai -
    aur ROKO mat, kyunki ye step optional hai.
    """
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("ERROR: sqlalchemy nahi mili.")
        print("  pip install sqlalchemy psycopg2-binary")
        return None

    try:
        eng = create_engine(engine_url())
        with eng.connect() as con:
            ver = con.execute(text("SELECT postgis_version()")).scalar()
        print(f"PostGIS mil gaya: {ver}")
        return eng
    except Exception as e:
        print(f"PostGIS se connect nahi hua:\n  {str(e)[:160]}\n")
        print("Database chalane ke liye (ek command):")
        print("  docker run -d --name sih-postgis -p 5432:5432 \\")
        print("      -e POSTGRES_PASSWORD=postgres postgis/postgis:16-3.4")
        print("\nYA ise chhod do - project GeoPackage se poora chalta hai.")
        return None


def main():
    eng = connect()
    if eng is None:
        sys.exit(0 if "--check" in sys.argv else 1)
    if "--check" in sys.argv:
        return

    print()
    done = 0
    for table, what in TABLES.items():
        path = DATA_PROCESSED / f"{table}.gpkg"
        if not path.exists():
            print(f"  skip  {table:<18} (file nahi hai)")
            continue

        gdf = gpd.read_file(path)
        # PostGIS ko ek hi CRS chahiye har table mein
        if gdf.crs is None:
            gdf = gdf.set_crs(CRS_LATLON)
        gdf = gdf.to_crs(CRS_LATLON)

        # date columns text hain gpkg mein - PostGIS mein sahi type do
        for col in ("first_seen", "last_seen", "acq_date"):
            if col in gdf.columns:
                gdf[col] = pd.to_datetime(gdf[col], errors="coerce")

        gdf.to_postgis(table, eng, if_exists="replace", index=False)
        print(f"  ok    {table:<18} {len(gdf):>7,} rows   {what}")
        done += 1

    # anomalies geometry wali nahi hai - normal table
    anom = DATA_PROCESSED / "anomalies.csv"
    if anom.exists():
        df = pd.read_csv(anom)
        df.to_sql("anomalies", eng, if_exists="replace", index=False)
        print(f"  ok    {'anomalies':<18} {len(df):>7,} rows   FRP anomalies")
        done += 1

    print(f"\n{done} tables PostGIS mein daal diye.")
    print("\nCheck karne ke liye:")
    print('  docker exec -it sih-postgis psql -U postgres -c "\\dt"')
    print("\nQGIS se: Layer > Add Layer > Add PostGIS Layers")


if __name__ == "__main__":
    main()
