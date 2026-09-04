# Vision layer — jahan rules chup ho jaate hain

**Status: ✅ chal raha hai** | Gemini Flash-Lite (free tier) | `src/step4d_gemini.py` + `src/step4e_merge_vlm.py`

---

## 1. Problem kya thi

Rules sirf **numbers** padhte hain:

```
factory kitni door hai?     ->  dist_to_industry_m
raat mein dikhta hai?       ->  night_ratio
kitne mahine chala?         ->  lifespan_days
zameen kaisi hai?           ->  lc_class
```

Aur inhi numbers se faisla lete hain. Ye 94% sources pe kaam kar jata
hai — par **1,099 sources pe koi rule fit hi nahi baitha.** Wo "UNSURE"
ho gaye.

Unpe model se poochne ki koshish ki thi. Naapne pe wo wahan sirf **39%**
sahi tha — teen classes mein tukka hi 33% hota hai. Yani model wahan
kuch jaanta hi nahi tha, bas bol raha tha. Isliye use chup kara diya
gaya aur wo sources "review queue" ban gaye.

**Par review queue ka matlab hai insaan ko 1,099 photos khud dekhni
padengi.** Wo ho nahi sakta.

---

## 2. Ilaaj: aisi jaankari jo rules ke paas hai hi nahi

Rules ke paas jo nahi hai wo hai — **asli tasveer.**

Ek bhatta (brick kiln) khet ke beech mein chhupa hota hai. Numbers
mein wo "khet" jaisa dikhta hai: forest nahi, industry se door
(kyunki OSM mein wo mapped hi nahi hai), ek jagah tikka hua. Rules
confuse ho jaate hain.

Photo mein wo **saaf dikhta hai** — gol chimney, laal-bhoori mitti,
katari hui zameen.

To hum wahi karte hain: us jagah ki satellite photo nikaalte hain aur
ek vision model se poochte hain *"is jagah pe kya hai?"*

---

## 3. Do naapa hua sudhaar

Ye seedha kaam nahi kiya — do baar galat hua, dono baar naap kar
theek kiya.

### (a) Photo ke BEECH mein source hona chahiye

Tile number nikalte waqt dashamlav kat jata hai (`22743.6 -> 22743`).
Zoom 15 pe ek tile ~1.2 km ka hota hai, to source photo ke kone pe
bhi aa sakta hai. Hum kehte "beech mein dekho" aur model galat jagah
dekhta.

**Fix:** 3×3 = 9 tiles jod kar, beech se chaukor kaat lo. Ab source
pakka beech mein hai. (`download_chip()` — `src/step4b_vlm.py`)

### (b) Beech kahan hai, ye DIKHNA chahiye

Pehli koshish mein Gemini 11 mein se **7 INDUSTRIAL chook gaya**.
Uski apni wajah padhne pe pattern saaf tha:

> *"The image is **dominated by** agricultural fields..."*
> *"The **surrounding area** is overwhelmingly agricultural..."*

Wo **poori tasveer** describe kar raha tha. Prompt kehta hai "beech
mein dekho", par photo mein beech kahan hai ye dikhta nahi — model ko
andaza lagana padta hai.

**Fix:** photo pe ek **laal chaukor** bana do (~430 m zameen pe). Ab
model ko bilkul pata hai kahan dekhna hai. (`add_center_mark()`)

---

## 4. Naapa — bharosa karne se PEHLE

Paisa/time kharch karne se pehle 45 gold sources pe chalaya, jinke
labels **insaan ne** banaye the:

```
Gemini sahi              81.0%    (45 mein se 42 pe jawab diya)
RULES sahi (unhi pe)     76.2%
```

Dono baatein maayne rakhti hain:

1. **Rules se behtar hai** — thoda hi sahi, par behtar.
2. **Wahan jawab deta hai jahan rules chup hain** — aur yahi asli
   faayda hai. Rules ka 76% un sources pe hai jinpe unhone jawab
   diya. Baaki 1,099 pe unka score hai hi nahi.

`UNSURE` jawab ko **galat nahi gina**. "Pata nahi" kehna galat jawab
dene se alag baat hai — aur behtar bhi.

---

## 5. Jodte waqt teen taale

`step4e_merge_vlm.py` jaan-boojh kar **kanjoos** hai:

| Shart | Kyun |
|---|---|
| Sirf `UNSURE` sources pe label lagta hai | Rules 76% pe hain, VLM 81% pe. Ye farak itna bada nahi ki pehle se kaam kar rahe labels ukhaad diye jayein. Jahan rules chup the, wahan VLM ke alawa kuch hai hi nahi — wahi asli faayda hai. |
| **Gold sources ko haath nahi lagate** | 45 gold labels hamara imtihaan hain. `gemini_labels.csv` mein wo 45 bhi hain (`--validate` se aaye the). Unpe VLM ka label chadha diya to imtihaan ka paper hi badal jayega aur score jhootha zyada aayega. `step5_train.py` bhi gold ko training se hatata hai — do taale ek se behtar hain. |
| Takraav pe label **nahi** badalta | Jahan rule ne kuch kaha aur VLM ne kuch aur, wahan rule ka label rehta hai aur source `vlm_conflict = True` ho jata hai. Do azaad tareekon ka jhagda hi wo jagah hai jahan insaan ka waqt sabse zyada kaam ka hai. |

---

## 6. Nateeja

```
                    PEHLE      AB      farak
INDUSTRIAL            136     192      +56    (+41%)
FOREST_FIRE         5,122   5,134      +12
AGRI_BURN          11,258  11,581     +323
UNSURE (queue)      1,099     708     −391    (−36%)
```

Sabse zaroori line **INDUSTRIAL** wali hai. Wo hamari sabse kam data
wali class thi (`DATA_AUDIT.md` mein imbalance ki shikayat isi pe hai),
aur wahi class hai jispe poora project tika hai. 41% zyada udaharan
milna model ke liye seedha faayda hai.

---

## 7. Jo hum NAHI keh rahe

- **81% ek pakka number nahi hai.** 42 answered sources pe naapa gaya
  hai — interval lagbhag ±12 points hai. Imaandar padhai ye hai:
  *"rules se behtar hai aur wahan jawab deta hai jahan wo chup hain"*,
  koi precise score nahi.
- **Model ka apna `confidence` bharosemand nahi hai.** Uska average
  0.90 hai — aur usme uski GALTIYAN bhi shaamil hain. Wo ek tippani
  hai, probability nahi. Isliye uspe threshold nahi lagaya gaya.
- **Ye insaan ki jagah nahi leta.** Ye review queue **chhoti** karta
  hai, khatam nahi. 708 sources ab bhi queue mein hain, aur takraav
  wale sources jaan-boojh kar wapas queue mein daale jaate hain.
- **12 sources pe VLM ne "forest" kaha jahan ESA WorldCover forest
  nahi kehta.** Dono galat ho sakte hain — WorldCover 2021 ka hai aur
  10 m ka, imagery nayi hai. Ye khula sawaal hai, chhupaya nahi gaya.

---

## 8. Chalane ka tareeka

```bash
# .env mein GEMINI_API_KEY daalo (free, credit card nahi chahiye)
#   https://aistudio.google.com/apikey

python src/step4d_gemini.py --validate   # pehle naapo (45 gold pe)
python src/step4d_gemini.py              # phir review queue pe chalao
python src/step4e_merge_vlm.py           # jawab labels mein jodo
python src/step5_train.py                # naye labels pe dobara train
```

Beech mein `Ctrl+C` dabao to kuch nahi jaata — progress
`data/processed/gemini_labels.csv` mein save hoti rehti hai aur agli
baar wahin se aage chalta hai.

`run_all.py` mein ye dono steps **optional** hain: API key na ho to
pipeline warning de kar aage badh jati hai aur labels sirf rules se
banate hain.

---

## 9. Claude wala raasta

`src/step4b_vlm.py` wahi kaam Claude Opus 5 se karta hai (paid key
chahiye), aur `step4c_vlm_validate.py` use gold pe naapta hai. Dono
scripts taiyaar hain par abhi chalayi nahi gayi hain — Gemini ka free
tier is kaam ke liye kaafi tha.

Aage ka sabse kaam ka istemaal: **referee**. Poore 8,000 sources pe
dobara chalane ki jagah, sirf un ~100 sources pe Claude chalao jahan
Gemini aur rules **alag bole**. Do azaad model ek baat pe raazi ho
jayein to us label pe bharosa kahin zyada hota hai — aur jahan wo bhi
na maanein, wahi sach mein insaan ke dekhne layak hai.
