"""
Poora pipeline, sahi order mein, ek command se.

    python run_all.py            # jo missing hai wahi banega
    python run_all.py --force    # sab kuch dobara

ORDER KYUN MAAYNE RAKHTA HAI:

  step2b (power plants) industry.gpkg BADALTA hai.
  step2 ka part 2 usi industry.gpkg se distance naapta hai.

  Isliye power plants pehle jodne padte hain, phir distance nikalni
  hoti hai. Ulta kiya to naye plants distance mein aayenge hi nahi
  aur kisi ko pata bhi nahi chalega.

  Isi tarah step2c (landcover) features.gpkg ko badalta hai, to wo
  step2 ke baad hi chalna chahiye - warna features.gpkg naye sire se
  banti hai aur landcover mit jata hai.
"""
import subprocess
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"

# (script, kya karta hai, ZAROORI hai kya)
#
# ORDER MAAYNE RAKHTA HAI - upar wajah likhi hai.
#
# optional=False  ->  ye fail hui to pipeline ruk jayegi (aage ka data
#                     galat banega, isliye rukna hi theek hai)
# optional=True   ->  fail hui to sirf warning, pipeline chalti rahegi.
#                     AI wale steps optional hain kyunki unke liye API
#                     key chahiye. Key na ho to project phir bhi poora
#                     chalta hai - bas rules wale labels ke saath.
STEPS = [
    ("step1_download.py",      "FIRMS se garam points (3 satellite)",        False),
    ("step2_context.py",       "OSM se polygons + har point pe context",     False),
    ("step2b_powerplants.py",  "WRI ke thermal power plants jodo",           False),
    ("step2_context.py",       "distance dobara naapo (naye plants ke saath)", False),
    ("step2c_landcover.py",    "ESA WorldCover se asli zameen ka type",      False),
    ("step3_persistence.py",   "clustering - kaun baar-baar dikhta hai",     False),
    ("step4_labels.py",        "rules se label",                             False),
    ("rescue_gold_labels.py",  "gold labels dobara jodo (jagah se)",         False),
    ("step4d_gemini.py",       "jahan rules chup hain, wahan AI photo dekhegi", True),
    ("step4e_merge_vlm.py",    "AI ke jawab labels mein jodo",               True),
    ("step5_train.py",         "model train + confidence score",             False),
    ("step7_nasa_model.py",    "NASA ke apne labels pe model (circularity ka ilaaj)", False),
    ("preview_map.py",         "check karne ke liye maps",                   False),
]


def run(script, args, optional=False):
    print("\n" + "=" * 64)
    print(f">>> {script}")
    print("=" * 64)
    t0 = time.time()
    result = subprocess.run([sys.executable, str(SRC / script)] + args,
                            cwd=SRC)
    took = time.time() - t0
    if result.returncode != 0:
        print(f"\n!! {script} FAIL ho gaya (code {result.returncode})")
        if optional:
            print("   ye step OPTIONAL hai (API key chahiye) - aage badh rahe hain.")
            print("   Iske bina labels sirf rules se banenge.")
            return False
        print("   pipeline yahin rok rahe hain - aage ka data galat banega")
        sys.exit(1)
    print(f"--- {script} ho gaya ({took:.0f} sec)")
    return True


def main():
    force = "--force" in sys.argv
    args = ["--force"] if force else []

    print("SIH26162 - poora pipeline")
    print(f"steps: {len(STEPS)}")

    start = time.time()
    for i, (script, what, optional) in enumerate(STEPS, 1):
        if not (SRC / script).exists():
            print(f"\n[{i}/{len(STEPS)}] {script} nahi mili - skip")
            continue
        print(f"\n[{i}/{len(STEPS)}] {what}")
        # --force sirf step2_context samajhta hai
        run(script, args if script == "step2_context.py" else [], optional)

    print("\n" + "=" * 64)
    print(f"SAB HO GAYA  ({(time.time() - start) / 60:.1f} minute)")
    print("=" * 64)
    print("\nAage:")
    print("  python verify.py         # sab kuch jaancho")
    print("  streamlit run app.py     # dashboard - yahi demo mein dikhana hai")


if __name__ == "__main__":
    main()
