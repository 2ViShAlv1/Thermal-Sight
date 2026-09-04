"""
Bhari hui CSV ko gold_labels.csv mein badal deta hai.

Agar tumne app ki jagah outputs/gold_50_TO_FILL.csv mein haath se
labels bhare hain, to ye chala do. Ye check bhi karta hai ki labels
sahi likhe hain ya nahi.

    python src/import_gold_csv.py
"""
import sys

import pandas as pd

from config import OUTPUTS, DATA_PROCESSED

ALLOWED = {"INDUSTRIAL", "FOREST_FIRE", "AGRI_BURN", "UNCLEAR"}


def main():
    src = OUTPUTS / "gold_50_TO_FILL.csv"
    if not src.exists():
        print(f"ERROR: {src} nahi mili")
        sys.exit(1)

    df = pd.read_csv(src)
    df["gold_label"] = df["gold_label"].fillna("").astype(str).str.strip().str.upper()

    filled = df[df["gold_label"] != ""]
    if len(filled) == 0:
        print("Abhi ek bhi label nahi bhara. gold_label column bharo.")
        sys.exit(1)

    # galat spelling pakdo - warna Phase 4 mein chup-chaap row gir jayegi
    bad = filled[~filled["gold_label"].isin(ALLOWED)]
    if len(bad) > 0:
        print("Ye labels galat likhe hain (spelling dekho):\n")
        print(bad[["num", "gold_label"]].to_string(index=False))
        print(f"\nSirf ye 4 chal sakte hain: {', '.join(sorted(ALLOWED))}")
        sys.exit(1)

    out = DATA_PROCESSED / "gold_labels.csv"
    filled[["source_id", "gold_label", "notes"]].to_csv(out, index=False)

    print(f"{len(filled)} labels import ho gaye -> {out}\n")
    print(filled["gold_label"].value_counts().to_string())
    if len(filled) < len(df):
        print(f"\n({len(df) - len(filled)} abhi khaali hain - baad mein bhar ke")
        print(" ye script dobara chala dena)")


if __name__ == "__main__":
    main()
