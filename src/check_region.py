"""
Naya region add karne se pehle ye chala lo.

Batata hai:
  1. Is bbox ke liye kaunsi Geofabrik zone file chahiye
  2. Kaunsa UTM CRS sahi rahega (distance ke liye)
  3. Bbox ka size theek hai ya nahi

Kyun zaroori: Geofabrik ke zone naam dhokha dete hain. "Northern zone"
mein Uttarakhand hai hi nahi (wo central zone mein hai). Ek baar ye
galti ho chuki hai - is script se dobara nahi hogi.

    python src/check_region.py 82.4 22.2 82.9 22.5
    (order: west south east north)
"""
import sys
import urllib.request

from config import DATA_RAW, CRS_METRES

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

# India ki saari zone files
ZONES = ["northern-zone", "central-zone", "eastern-zone",
         "western-zone", "southern-zone", "north-eastern-zone"]

POLY_URL = "https://download.geofabrik.de/asia/india/{}.poly"


def load_zone_polygon(zone):
    """
    Geofabrik ki .poly file download karke ek shapely polygon banata hai.
    .poly format simple hai: har ring ke coordinates, phir 'END'.
    """
    # ek baar download karke cache kar lo - Geofabrik kabhi kabhi timeout
    # deta hai, aur ye files chhoti (kuch KB) hain
    cache = DATA_RAW / f"{zone}.poly"
    if cache.exists():
        text = cache.read_text()
    else:
        text = urllib.request.urlopen(POLY_URL.format(zone), timeout=60).read().decode()
        cache.write_text(text)

    rings, current = [], []
    for line in text.splitlines():
        t = line.strip()
        if t == "END":
            if current:
                rings.append(Polygon(current))
                current = []
            continue
        parts = t.split()
        if len(parts) == 2:
            try:
                current.append((float(parts[0]), float(parts[1])))
            except ValueError:
                pass   # header lines ("polygon", "1" waghairah) - chhod do

    # buffer(0) tooti geometries ko theek kar deta hai
    return unary_union([r.buffer(0) for r in rings
                        if len(r.exterior.coords) > 3])


def best_utm_crs(west, east):
    """
    UTM zone number nikaalo bbox ke beech ke longitude se.
    Har UTM zone 6 degree chaudi hai, zone 1 ka start -180 pe.
    India northern hemisphere mein hai, isliye EPSG = 32600 + zone.
    """
    centre_lon = (west + east) / 2
    zone = int((centre_lon + 180) / 6) + 1
    return 32600 + zone, zone


def distortion_percent(epsg, lon, lat):
    """
    Diye gaye CRS mein 1 km kitna galat naapa jata hai (percent mein).

    Tareeka: is jagah se theek 1000 m poorab ek doosra point nikalo
    (geodesic, yani zameen pe asli fasla), phir dono ko CRS mein
    convert karke unke beech ki doori naapo. Farak hi distortion hai.
    """
    import geopandas as gpd
    from shapely.geometry import Point
    from pyproj import Geod

    lon2, lat2, _ = Geod(ellps="WGS84").fwd(lon, lat, 90, 1000)
    pts = gpd.GeoSeries([Point(lon, lat), Point(lon2, lat2)],
                        crs=4326).to_crs(epsg)
    measured = pts.iloc[0].distance(pts.iloc[1])
    return (measured - 1000) / 1000 * 100


def main():
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)

    west, south, east, north = [float(v) for v in sys.argv[1:5]]
    target = box(west, south, east, north)
    print(f"bbox = ({west}, {south}, {east}, {north})   [west south east north]\n")

    # ---- 1. bbox sanity ----
    if west >= east or south >= north:
        print("ERROR: bbox ulta hai. Order (west, south, east, north) hona chahiye,")
        print("       yani LONGITUDE pehle. Ye sabse common galti hai.")
        sys.exit(1)

    width_km = (east - west) * 111 * 0.9    # rough, cos(latitude) ka approx
    height_km = (north - south) * 111
    print(f"size: lagbhag {width_km:.0f} x {height_km:.0f} km")
    if width_km > 400 or height_km > 400:
        print("  ! kaafi bada hai - FIRMS ke bahut saare rows aayenge, dhyan rakhna")
    print()

    # ---- 2. kaunsi zone file ----
    print("Geofabrik zone check kar rahe hain...")
    found = False
    for zone in ZONES:
        try:
            geom = load_zone_polygon(zone)
        except Exception as e:
            print(f"  {zone}: download nahi hua ({e})")
            continue
        covered = geom.intersection(target).area / target.area * 100
        if covered > 0.5:
            print(f"  {zone:20} {covered:5.1f}% covered")
            if covered > 99:
                print(f"     -> REGION_PBF mein ye daalo: \"{zone}-latest.osm.pbf\"")
                found = True
    if not found:
        print("  ! koi bhi zone 100% cover nahi karta.")
        print("  ! Matlab bbox do zones ke beech mein hai - dono download karke")
        print("  ! polygons jodne padenge, ya bbox thoda chhota karo.")
    print()

    # ---- 3. CRS ----
    epsg, zone_num = best_utm_crs(west, east)
    print(f"Is bbox ka nominal UTM zone: EPSG:{epsg}  (zone {zone_num}N)")

    # Zone number match na karna apne aap problem nahi hai. Asli sawaal:
    # config wala CRS is jagah pe distance kitni galat deta hai?
    # Isliye bbox ke beech mein 1 km ka asli fasla lekar compare karte hain.
    err = distortion_percent(CRS_METRES, (west + east) / 2, (south + north) / 2)
    print(f"config ka CRS_METRES ({CRS_METRES}) yahan 1 km ko {err:+.2f}% galat naapta hai")

    if abs(err) < 1.0:
        print("  theek hai - itni chhoti galti se rules pe koi farak nahi padta.")
    else:
        print(f"  ! ye zyada hai. config.py mein CRS_METRES = {epsg} kar do,")
        print(f"  ! warna 1000 m wala rule asal mein {1000 * (1 + err/100):.0f} m ka ban jayega.")


if __name__ == "__main__":
    main()
