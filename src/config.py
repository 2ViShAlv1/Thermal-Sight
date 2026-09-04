"""
SIH26162 - ek hi jagah saare settings.
Har script yahan se import karegi, taaki kabhi bhi bbox ya date
badalna ho to sirf yahi file badle.
"""
from pathlib import Path

# ---------------------------------------------------------------
# Folders - __file__ se nikale gaye hain, isliye script kahin se
# bhi chalao, paths hamesha sahi rahenge.
# ---------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent   # sih26162/ folder
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_CHIPS = ROOT / "data" / "chips"
MODELS = ROOT / "models"
OUTPUTS = ROOT / "outputs"

# Agar folder na ho to bana do (rerun pe error nahi aayega)
for _folder in (DATA_RAW, DATA_PROCESSED, DATA_CHIPS, MODELS, OUTPUTS):
    _folder.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------
# 3 regions. Order: (west, south, east, north)
# yani LONGITUDE pehle, LATITUDE baad mein.
# FIRMS API bhi isi order mein maangta hai, isliye seedha bheja ja sakta hai.
# ---------------------------------------------------------------
REGIONS = {
    "jamnagar":    (69.4, 21.8, 70.6, 22.9),   # Gujarat - refineries (INDUSTRIAL milega)
    "uttarakhand": (78.8, 29.2, 80.2, 30.4),   # Kumaon - jungle (FOREST_FIRE milega)
    "punjab":      (75.2, 30.2, 76.4, 31.0),   # Ludhiana - khet (AGRI_BURN milega)

    # ---- ye do baad mein jode gaye ----
    # Wajah: pehle 3 regions mein se sirf EK industrial tha (Jamnagar),
    # to INDUSTRIAL class ke sirf 40 udaharan mile - jabki AGRI_BURN ke
    # 4,073. Model itne imbalance pe INDUSTRIAL theek se seekh hi nahi
    # paata.
    #
    # Ye do jagah GUESS se nahi chuni. WRI ke Global Power Plant Database
    # (388 thermal plants poore India mein) se nikala ki India ke sabse
    # bade thermal cluster kahan hain:
    #     1. Korba/Sipat      28 plants, 24,056 MW
    #     2. Singrauli         9 plants, 21,164 MW
    #     5. Jamnagar (hamara) 5 plants, 10,476 MW
    # Yani Korba akela Jamnagar se 2.3 guna bada hai.
    "korba":       (82.2, 21.6, 83.4, 22.5),   # Chhattisgarh - India ka sabse bada thermal hub
    "singrauli":   (82.0, 23.7, 83.2, 24.6),   # MP/UP border - doosra sabse bada
}

# ---------------------------------------------------------------
# REFERENCE REGION - sirf LIVE monitoring ke liye, batch pipeline mein
# nahi (koi training data, OSM/WorldCover context, model history yahan
# NAHI hai).
#
# KYUN: hamare 5 asli regions chhote hain - kai baar (khaas kar
# monsoon mein) unmein GHANTON tak koi hotspot hi nahi hota. Demo ke
# waqt agar live tab khaali dikhe to "NASA se connection hai ya nahi"
# wala shak paida hota hai.
#
# Jharia-Dhanbad-Bokaro coalfield (Jharkhand, India) - yahan coal seam
# 1916 se ZAMEEN KE ANDAR lagatar jal raha hai (duniya ke sabse
# mashhoor "eternal fire" mining accidents mein se ek), poore saal,
# mausam se azaad. INDIAN hai, aur hamare project ki thim (industrial/
# persistent thermal source) se bilkul milta hai. Bbox jaan-boojh kar
# poora coal belt cover karta hai (sirf Jharia nahi) - zyada area,
# thoda zyada consistent detections.
#
# HONEST NOTE: is jagah ki activity bhi BURSTY hai (kabhi ek din 30+
# detections, kabhi agle din 0-1) - koi Indian jagah is se zyada
# consistent nahi mili (Iraq/Nigeria ke gas-flares jaisi 24x7 activity
# India mein nahi hai). Agar Live tab kabhi khaali dikhe, wahi wajah
# hai - NASA connection sahi hai, bas is chhote area mein us waqt
# genuinely kuch garam nahi mila.
#
# Is jagah ka koi historical match nahi hoga (hum yahan train nahi
# hue), isliye ye hamesha "NEW" dikhega - model yahan chalta bhi nahi
# (jaan-boojh kar, itni kam history se confident jawab dena imaandar
# nahi hoga). Yehi sahi/honest behaviour hai.
# ---------------------------------------------------------------
LIVE_REFERENCE_REGIONS = {
    "Jharia-Dhanbad Coalfield, India (reference)": (85.7, 23.4, 86.6, 24.2),
}

# ---------------------------------------------------------------
# Har region ka OSM data kis Geofabrik zone file mein hai.
#
# Ye mapping isliye likhi hai kyunki naam dhokha dete hain:
# Geofabrik ke "northern zone" mein Uttarakhand hai hi NAHI
# (wo central zone mein hai). Ek baar .poly boundaries se check
# karke ye confirm kiya gaya hai - dobara mat guess karna.
#
# Poori India ki 1.4 GB file ki zaroorat nahi, ye 3 files kaafi hain.
# Download: https://download.geofabrik.de/asia/india/<zone>-latest.osm.pbf
# ---------------------------------------------------------------
REGION_PBF = {
    "jamnagar":    "western-zone-latest.osm.pbf",    # Gujarat
    "uttarakhand": "central-zone-latest.osm.pbf",    # UP / Uttarakhand / MP
    "punjab":      "northern-zone-latest.osm.pbf",   # Punjab / Haryana / HP / Rajasthan
    "korba":       "central-zone-latest.osm.pbf",    # Chhattisgarh
    "singrauli":   "central-zone-latest.osm.pbf",    # MP / UP
}

# ---------------------------------------------------------------
# Kaun-kaun se satellite ka data lena hai
#
# Ek nahi, TEEN satellite hain jo bilkul ek jaisa VIIRS sensor
# laad kar ghoom rahe hain - Suomi-NPP, NOAA-20, aur NOAA-21.
# Teeno ka data 375 metre ka hai, yani aapas mein tulnayogya.
#
# Teeno lene ka faayda:
#   1. lagbhag 3 GUNA zyada detections
#   2. aur zyada zaroori - teen guna zyada CHAKKAR. Ek satellite
#      din mein ek-do baar guzarta hai; teen milkar kahin zyada
#      baar dekhte hain. Isse "satellite roz dekh hi nahi pata"
#      wali problem kaafi kam ho jaati hai.
#
# MODIS jaan-boojh kar nahi liya - wo 1 KILOMETRE ka hai, yani
# bahut mota. Usse chhoti aagein aur factory ke flare ghul-mil
# jate hain.
#
# _SP = Standard Processing (purana, saaf data)
# _NRT = Near Real Time (naya, thoda kam saaf)
# NOAA-21 ka SP abhi nahi hai, isliye uska NRT lena padta hai.
# ---------------------------------------------------------------
FIRMS_SOURCES = [
    "VIIRS_SNPP_SP",      # Suomi-NPP  (2012 se)
    "VIIRS_NOAA20_SP",    # NOAA-20    (2018 se)
    "VIIRS_NOAA21_NRT",   # NOAA-21    (2024 se)
]

# ---------------------------------------------------------------
# Time window - 2025 ka pura saal
# ---------------------------------------------------------------
START = "2025-01-01"
END = "2025-12-31"

# ---------------------------------------------------------------
# DBSCAN ke do parameters (step3_persistence.py mein use hote hain)
#
# eps = 500 metre. Iske andar ke points ek hi source maane jayenge.
#   Kyun 500: VIIRS ka ek pixel hi 375 m ka hota hai, aur satellite
#   ki location mein thodi galti bhi hoti hai. To ek hi flare ke do
#   detections 500 m tak alag aa sakte hain.
#
# min_samples = 3. Kam se kam itne points ho to hi "cluster" banega.
#   Isse kam wale "noise" kehlate hain - par hum unhe phenkte nahi,
#   unhe akela source maan lete hain (ek baar dikhi aag bhi ek
#   ghatna hai). Detail step3_persistence.py mein.
#
# Inhe badalne ka asar: bada eps = kam clusters par alag factories
# aapas mein jud sakti hain. Chhota eps = ek hi factory kai tukdon
# mein toot sakti hai.
# ---------------------------------------------------------------
DBSCAN_EPS = 500          # metres
DBSCAN_MIN_SAMPLES = 3

# ---------------------------------------------------------------
# persistence_tier ke thresholds
#
# Idea: factory MAHINON tak baar-baar dikhti hai, jungle ki aag
# kuch din mein khatam ho jati hai.
#
# PERSISTENT = do shart, dono poori honi chahiye:
#   1. lambe samay tak dikhi        (lifespan > 150 din)
#   2. kai ALAG dinon mein dikhi    (n_days >= 10)
#
# Doosri shart kyun zaroori hai: bina uske "Jan mein ek baar dikhi
# aur Dec mein ek baar" wala source bhi PERSISTENT ban jata, jabki
# wo do alag ghatnayein thi.
#
# --------------------------------------------------------------
# NOTE: plan mein doosri shart "activity_ratio > 0.25" thi.
# Wo threshold data pe test karne pe galat nikla. Wajah:
#
#   activity_ratio = n_days / lifespan_days, yani "jitne din ke
#   andar dikha, unme se kitne din dikha".
#
#   Par VIIRS roz detect kar hi nahi sakta! Poore Jamnagar region
#   mein saal ke sirf 217 din (365 mein se) koi detection aayi -
#   baaki din badal the ya satellite ka angle theek nahi tha.
#
#   Reliance ka flare saal ke BAARAH mahine dikha (yani 24/7 jalta
#   hai), phir bhi sirf 127 alag din pe. Uska activity_ratio 0.25
#   aaya - matlab wo bilkul kagaar pe pass hua. Vadinar Refinery
#   (night_ratio 1.00, distance 0 m - pakka industrial) ka 0.08
#   aaya aur wo FAIL ho gaya.
#
#   To activity_ratio source ka behaviour nahi, SATELLITE ka
#   revisit rate naap raha tha. Isliye uski jagah n_days.
#
# activity_ratio ab bhi nikala jaata hai - model use feature ki
# tarah use karega. Bas tier decide karne mein use nahi hota.
# --------------------------------------------------------------
PERSISTENT_MIN_LIFESPAN = 150     # din - itne lambe samay tak dikhi
PERSISTENT_MIN_DAYS = 10          # aur itne alag dinon mein dikhi
EPISODIC_MAX_LIFESPAN = 30        # din - itne mein khatam = ek ghatna thi

# ---------------------------------------------------------------
# RULE THRESHOLDS (step4_labels.py)
#
# INDUSTRY_RADIUS = 1000 m. Iske andar hai to "factory ki chaardiwari
#   mein" maana jayega (is_industrial).
#
# MIN_DIST_FROM_INDUSTRY = 1000 m. FOREST_FIRE aur AGRI_BURN ke liye
#   "factory se door" ki definition.
#
#   Pehle ye 5000 (forest) aur 3000 (agri) tha. Wo bahut zyada tha:
#   is_industrial pehle hi sirf 1 km ke andar wale leta hai, to 1-5 km
#   ke beech ka har source kisi rule mein fit hi nahi hota tha aur
#   UNSURE ban jata tha. Naapne pe: is ek badlav se 3,124 sources
#   UNSURE se nikal aaye, aur accuracy giri nahi.
#
# NIGHT_MAX_FOR_FIRE = 0.3. Isse zyada raat mein dikhne wali cheez
#   shayad aag nahi, chalti hui machine hai.
#
#   IMAANDARI: "kisan raat mein aag nahi lagata" ek POORI SACH baat
#   nahi hai - hamare apne data mein Punjab ke 3.6% detections raat
#   ke hain (katai ke mahinon mein 3.0%). March-April mein to 23-25%
#   tak raat ke hain. Ye ek MAZBOOT jhukav hai, koi kanoon nahi.
#
# MIN_DET_FOR_NIGHT_RATIO = 3. night_ratio pe bharosa tabhi karo jab
#   itni detections hon.
#
#   Wajah SAAF hai: agar satellite ne kisi jagah ko sirf EK BAAR dekha
#   aur wo raat ka pass tha, to night_ratio = 1.00 aa jayega. Isse ye
#   sabit NAHI hota ki wo cheez raat mein jalti hai - ye satellite ki
#   timing ka ittefaq hai.
#
#   Data mein: 462 sources sirf night_ratio ki wajah se UNSURE the.
#   Unme se 319 ke paas SIRF EK detection thi. Ek observation se
#   ratio banta hi nahi.
#
# NIGHT_MIN_FOR_MACHINE = 0.5. Isse zyada raat mein dikhti ho AUR
#   mahinon tak chalti ho, to wo machine hai - aag nahi. Ye shart OSM
#   ke BINA bhi industry dhoondh leti hai: Korba mein ek source mila
#   jiske 2,859 detections hain, 266 alag din, raat 95% - par OSM mein
#   us jagah kuch bhi mapped nahi hai. Satellite photo se confirm kiya.
# ---------------------------------------------------------------
INDUSTRY_RADIUS = 1000            # metres
MIN_DIST_FROM_INDUSTRY = 1000     # metres
NIGHT_MAX_FOR_FIRE = 0.3
NIGHT_MIN_FOR_MACHINE = 0.5
MIN_DET_FOR_NIGHT_RATIO = 3

# ---------------------------------------------------------------
# Anomaly ka threshold (step4_labels.py)
#
# Agar kisi din ki garmi us source ke APNE normal se itne guna
# zyada ho, to wo din "anomaly" hai. 3 rakha hai - itna bada farak
# sirf tab aata hai jab sach mein kuch hua ho, roz ke utaar-chadhaav se nahi.
# ---------------------------------------------------------------
ANOMALY_FRP_MULTIPLIER = 3.0

# ---------------------------------------------------------------
# VLM (Vision Language Model) ki settings - step4b_vlm.py
#
# Ye wo AI hai jo satellite photo dekh kar batati hai wahan kya hai.
# Rules sirf numbers dekhte hain; ye AANKHON se dekhti hai.
#
# VLM_MAX_SOURCES = kitne sources pe chalana hai. 100 rakha hai -
# itne mein kaam ho jata hai aur kharcha bhi kam rehta hai.
# ---------------------------------------------------------------
VLM_MODEL = "claude-opus-5"
VLM_MAX_SOURCES = 100

# ---------------------------------------------------------------
# 3 classes. Anomaly ek alag flag hai, class nahi.
# ---------------------------------------------------------------
CLASSES = ["INDUSTRIAL", "FOREST_FIRE", "AGRI_BURN"]

# ---------------------------------------------------------------
# CRS (coordinate system) - do hi kaam ke hain:
#   4326  = degrees mein. Map dikhane / file save karne ke liye.
#   32643 = metres mein (UTM zone 43N, North India ke liye sahi).
#           DISTANCE nikalne se pehle HAMESHA isme convert karo,
#           warna "0.004 degree" jaise bekaar numbers milenge.
# ---------------------------------------------------------------
CRS_LATLON = 4326
CRS_METRES = 32643
