"""
Quick preview maps - QGIS ke bina bhi check ho jaye.

DO tarah ke maps banata hai:

  preview_<region>.png    Phase 1 ka check
      industry (laal), forest (hara), cropland (peela), hotspots (kaale dots)
      Sawaal: dots sahi polygons pe baithe hain?

  sources_<region>.png    Phase 2 ka check
      har source ek dot, persistence_tier ke hisaab se colour.
      Dot ka SIZE = kitni baar detect hua.
      Sawaal: PERSISTENT sources factory ke upar hain?

    python src/preview_map.py
"""
import matplotlib
matplotlib.use("Agg")          # bina screen ke chalane ke liye
import matplotlib.pyplot as plt
import geopandas as gpd

from config import REGIONS, DATA_PROCESSED, OUTPUTS

# har lc_class ka apna rang
LC_COLORS = {"forest": "#2d6a4f", "cropland": "#d4a017", "urban": "#9aa0a6"}

# har persistence_tier ka apna rang
TIER_COLORS = {
    "PERSISTENT": "#d00000",   # laal - chalti hui factory
    "OTHER": "#f77f00",        # orange - beech ka
    "EPISODIC": "#264653",     # gehra neela - ek baar ki ghatna
}


def draw_sources():
    """Phase 2 ka check - sources tier ke hisaab se colour karke."""
    src_path = DATA_PROCESSED / "sources.gpkg"
    if not src_path.exists():
        print("sources.gpkg nahi mili - step3_persistence.py pehle chalao")
        return

    sources = gpd.read_file(src_path)
    industry = gpd.read_file(DATA_PROCESSED / "industry.gpkg")

    for region_name, bbox in REGIONS.items():
        west, south, east, north = bbox
        fig, ax = plt.subplots(figsize=(11, 9))

        ind = industry[industry["region"] == region_name]
        if len(ind) > 0:
            ind.plot(ax=ax, color="#cccccc", edgecolor="#888888",
                     linewidth=0.8, label=f"industry ({len(ind)})")

        sub = sources[sources["region"] == region_name]

        # EPISODIC sabse pehle (sabse zyada hain, neeche rahein),
        # PERSISTENT sabse aakhir mein taaki upar dikhein
        for tier in ["EPISODIC", "OTHER", "PERSISTENT"]:
            part = sub[sub["persistence_tier"] == tier]
            if len(part) == 0:
                continue
            # dot ka size = kitni baar detect hua. Bada dot = zyada baar.
            size = 6 + part["n_detections"] * 1.5
            part.plot(ax=ax, color=TIER_COLORS[tier], markersize=size,
                      alpha=0.7, edgecolor="white", linewidth=0.3,
                      label=f"{tier} ({len(part)})")

        ax.set_xlim(west, east)
        ax.set_ylim(south, north)
        ax.set_title(f"{region_name.upper()} — sources "
                     f"(dot ka size = kitni baar detect hua)", fontsize=13)
        ax.set_xlabel("longitude")
        ax.set_ylabel("latitude")
        ax.legend(loc="upper right", fontsize=9)

        out = OUTPUTS / f"sources_{region_name}.png"
        fig.savefig(out, dpi=110, bbox_inches="tight")
        plt.close(fig)
        print(f"SAVED: {out}")


def draw_hotspots():
    hotspots = gpd.read_file(DATA_PROCESSED / "hotspots.gpkg")
    industry = gpd.read_file(DATA_PROCESSED / "industry.gpkg")
    landuse = gpd.read_file(DATA_PROCESSED / "landuse.gpkg")

    for region_name, bbox in REGIONS.items():
        west, south, east, north = bbox

        fig, ax = plt.subplots(figsize=(11, 9))

        # 1. landuse sabse neeche (background)
        lc = landuse[landuse["region"] == region_name]
        for cls, color in LC_COLORS.items():
            part = lc[lc["lc_class"] == cls]
            if len(part) > 0:
                part.plot(ax=ax, color=color, alpha=0.45,
                          linewidth=0, label=f"{cls} ({len(part)})")

        # 2. industry uske upar, laal outline ke saath
        ind = industry[industry["region"] == region_name]
        if len(ind) > 0:
            ind.plot(ax=ax, color="#d00000", alpha=0.75, edgecolor="#d00000",
                     linewidth=1.5, label=f"industry ({len(ind)})")

        # 3. hotspots sabse upar - yahi dekhne wali cheez hai
        hs = hotspots[hotspots["region"] == region_name]
        hs.plot(ax=ax, color="black", markersize=3, alpha=0.55,
                label=f"hotspots ({len(hs)})")

        # bbox pe hi zoom rakho, warna polygons map ko kheench denge
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)
        ax.set_title(f"{region_name.upper()}  —  bbox {bbox}", fontsize=13)
        ax.set_xlabel("longitude")
        ax.set_ylabel("latitude")
        ax.legend(loc="upper right", fontsize=9)

        out = OUTPUTS / f"preview_{region_name}.png"
        fig.savefig(out, dpi=110, bbox_inches="tight")
        plt.close(fig)
        print(f"SAVED: {out}")


def main():
    draw_hotspots()
    draw_sources()


if __name__ == "__main__":
    main()
