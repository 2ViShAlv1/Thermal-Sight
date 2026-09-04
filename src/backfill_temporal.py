"""
sources_labelled.gpkg mein waqt-ke-aakaar wale teen naye features jodta hai
BINA poora pipeline dobara chalaye.

Kyun: step3 dobara chalane se DBSCAN phir se clustering karega. Agar ek bhi
cluster ka centre thoda hila to source_id badal jayega - aur gold_labels.csv
ke 159 labels un ids se bandhe huey hain. Wo toot jate (isiliye
rescue_gold_labels.py likhna pada tha).

Ye script clustering ko haath NAHI lagata. Sirf detections.gpkg se teen
number ginta hai aur sources_labelled.gpkg pe chipka deta hai.

Feature ki definition step3_persistence._temporal_shape se AATI hai -
copy nahi ki, import ki. Isliye dono jagah ek hi hisaab chalega.

Chalane ka tareeka:
    python src/backfill_temporal.py
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_PROCESSED
from step3_persistence import _temporal_shape


def main():
    det = gpd.read_file(DATA_PROCESSED / "detections.gpkg")
    src = gpd.read_file(DATA_PROCESSED / "sources_labelled.gpkg")
    print(f"detections: {len(det):,}   sources: {len(src):,}")

    rows = []
    for sid, grp in det.groupby("source_id"):
        gap_cv, burst_frac, max_gap = _temporal_shape(grp["acq_date"])
        rows.append({"source_id": sid, "gap_cv": gap_cv,
                     "burst_frac": burst_frac, "max_gap_days": max_gap})
    feats = pd.DataFrame(rows)

    src = src.drop(columns=[c for c in ["gap_cv", "burst_frac", "max_gap_days"]
                            if c in src.columns])
    out = src.merge(feats, on="source_id", how="left")

    # jo source detections mein mila hi nahi (nahi hona chahiye) -> "pata nahi"
    for c in ["gap_cv", "burst_frac", "max_gap_days"]:
        n_missing = out[c].isna().sum()
        if n_missing:
            print(f"  !! {c}: {n_missing} sources pe value nahi mili -> -1")
        out[c] = out[c].fillna(-1.0)

    assert len(out) == len(src), "merge ne rows badal di"
    out.to_file(DATA_PROCESSED / "sources_labelled.gpkg", driver="GPKG")
    print(f"\nSAVED: {DATA_PROCESSED / 'sources_labelled.gpkg'}")

    known = out[out.gap_cv >= 0]
    print(f"\n{len(known):,} sources pe values hain "
          f"({len(out) - len(known):,} pe ek hi din tha -> -1)")
    print("\nlabel ke hisaab se औसत:")
    print(known.groupby("label")[["gap_cv", "burst_frac", "max_gap_days"]]
          .mean().round(3).to_string())


if __name__ == "__main__":
    main()
