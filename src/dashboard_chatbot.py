"""
Dashboard Q&A chatbot - "is data ke baare mein kuch bhi poocho".

KYUN YE HAI:
    Dashboard mein numbers/tables/charts hain, par kabhi kabhi koi
    (mentor, judge, agency official) seedha poochna chahta hai - "sabse
    zyada industrial sites kaunse region mein hain?", "model kitna
    accurate hai?", "night_ratio kya hota hai?". Har baar sahi tab
    dhoondhna padta hai. Ye chatbot un sawaalon ka seedha jawab deta hai.

KAISE KAAM KARTA HAI (jaan-boojh kar simple rakha):
    Poore 17,615-row dataset ko LLM ko NAHI bhejte (na zaroorat hai, na
    practical - context bahut bada ho jayega). Iske bajaye, hum wahi
    AGGREGATE STATS jo dashboard khud dikhata hai (summary, priorities,
    anomalies, model metrics) ek chhoti text summary mein pirokar LLM
    ko dete hain, saath mein user ka sawaal. LLM sirf usi context se
    jawab deta hai - agar kuch pata nahi to "pata nahi" bolta hai,
    banata nahi (system prompt mein saaf likha hai).

    Isse do faayde: (1) koi arbitrary code execution nahi (safe), (2)
    jawab hamesha REAL numbers pe based hote hain jo dashboard khud
    dikha raha hai - LLM sirf unhe explain/summarise karta hai.

Input : GROQ_API_KEY (primary - bahut fast, LPU hardware) ya
        GEMINI_API_KEY (fallback, VLM wali hi key reuse hoti hai)
Output: koi file nahi - seedha API response

DO PROVIDERS KYUN:
    Gemini free-tier kabhi kabhi 30-50 second le leta hai (high-demand
    503, retry ke baad success) - ek chat feature ke liye bahut slow
    hai. Groq wahi sawaal ~1-2 second mein jawab de deta hai (naapa
    hua). Isliye Groq PEHLE try karte hain, Gemini sirf tab jab Groq
    configure na ho ya fail ho jaye - dono jagah SAME system prompt +
    data context use hota hai, jawab ki quality/honesty same rehti hai.

Chalane ka tareeka: seedha import hota hai api/main.py se, standalone
script nahi hai.
"""
import os

from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

SYSTEM_PROMPT = """Tum ThermalSight dashboard ke andar baithe ek assistant ho -
ek system jo NASA satellite thermal data ko classify karta hai: INDUSTRIAL
(factory/refinery), FOREST_FIRE (jungle ki aag), AGRI_BURN (khet mein parali
jalana).

Neeche "DATA" section mein is dashboard ke ASLI, is-waqt-ke numbers diye hain.
Sirf isi DATA ka use karke jawab do - kabhi aisa number mat banao jo DATA mein
kahin bhi maujood nahi hai (hallucinate mat karo). Par DATA mein diye gaye
numbers pe simple analysis karna (jaise table mein sabse bada number dhoondna,
do numbers jodna/ghatana, ratio nikalna) bilkul theek hai - ye hallucination
nahi hai, ye tumhara kaam hai. Agar sawaal ka jawab DATA se seedha ya calculate
karke nahi nikal sakta, tabhi bolo "ye is dashboard ke data mein nahi hai".

Jawab CHHOTA rakho (2-5 lines), seedha point pe. Agar user Hindi/Hinglish mein
poochein to Hinglish mein jawab do, agar English mein to English mein.
"""


def build_data_context(store):
    """Store (api/main.py ka S) se ek chhoti text summary banao - dashboard
    ke saare "headline" numbers ek jagah, LLM ko dene layak."""
    p = store.pred
    m = store.metrics
    gold = m.get("gold", {})

    by_region_class = (
        p.groupby(["region", "klass"]).size().unstack(fill_value=0)
    )

    lines = [
        "=== OVERALL ===",
        f"Total raw FIRMS detections (1 year, 3 satellites): {int(p['n_detections'].sum()):,}",
        f"Distinct clustered sources (after DBSCAN): {len(p):,}",
        f"Regions: {', '.join(sorted(p['region'].unique()))}",
        "",
        "=== CLASSIFICATION BREAKDOWN (by class) ===",
    ]
    for k in ["INDUSTRIAL", "FOREST_FIRE", "AGRI_BURN", "REVIEW"]:
        n = int((p["klass"] == k).sum())
        lines.append(f"{k}: {n:,} sources")

    lines += ["", "=== BY REGION x CLASS (source counts) ==="]
    lines.append(by_region_class.to_string())

    lines += [
        "",
        "=== MODEL PERFORMANCE (measured on 159 human-labelled gold sources,"
        " NEVER seen during training) ===",
        f"Accuracy: {gold.get('accuracy', 0):.1%}",
        f"Macro-F1 (3 classes, excluding UNCLEAR): {gold.get('macro_f1_known_classes', 0):.3f}",
        f"Macro-F1 (all 4 labels incl UNCLEAR): {gold.get('macro_f1', 0):.3f}",
    ]
    report = gold.get("report", {})
    for cls in ["AGRI_BURN", "FOREST_FIRE", "INDUSTRIAL"]:
        r = report.get(cls, {})
        if r:
            lines.append(f"  {cls}: precision={r.get('precision', 0):.2f} "
                         f"recall={r.get('recall', 0):.2f} "
                         f"f1={r.get('f1-score', 0):.2f} "
                         f"(support={int(r.get('support', 0))})")

    lines += [
        "",
        "=== ANOMALIES (site burning >=3x its own historical baseline) ===",
        f"Total anomaly-days: {len(store.anom):,}",
        f"Distinct sites with anomalies: {store.anom['source_id'].nunique():,}"
        if len(store.anom) else "0",
        f"Largest single spike: {store.anom['ratio'].max():.1f}x normal"
        if len(store.anom) else "n/a",
    ]

    top_industrial = (p[p["klass"] == "INDUSTRIAL"]
                      .nlargest(5, "n_detections")[
                          ["site", "region", "n_detections", "night_ratio"]])
    lines += ["", "=== TOP 5 INDUSTRIAL SITES (by detection count) ==="]
    lines.append(top_industrial.to_string(index=False))

    lines += [
        "",
        "=== KEY FEATURES USED BY THE MODEL (20 total) ===",
        "night_ratio (share of detections at night - factories run 24/7,"
        " farmers burn only in daytime), dist_to_industry_m (distance to"
        " nearest mapped factory/power plant), lc_class (land cover: forest/"
        "cropland/urban), lifespan_days, n_detections, frp_mean/max (fire"
        " radiative power = heat intensity).",
        "",
        "=== WHY 'REVIEW' SOURCES EXIST ===",
        "Rules could not confidently classify these. The model was measured"
        " to be only ~39% accurate here (barely above the 33% chance level"
        " for 3 classes), so it deliberately does not guess - these go to a"
        " human review queue instead of a confident wrong answer.",
    ]

    return "\n".join(lines)


def _ask_groq(question, data_context, tries=2):
    """Groq (OpenAI-compatible REST) - naapa hua ~1-2 second response.
    reasoning model hai (gpt-oss), isliye max_tokens generous rakha hai
    warna reasoning hi poore tokens kha leta hai aur jawab khaali aata."""
    import requests

    last_err = None
    for attempt in range(tries):
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",
                         "content": f"DATA:\n{data_context}\n\nQUESTION: {question}"},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 600,
                },
                timeout=20,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            if content.strip():
                return content, None
            last_err = "empty response (reasoning used all tokens)"
        except Exception as e:
            last_err = str(e)[:200]
        if attempt < tries - 1:
            import time
            time.sleep(1)
    return None, last_err


def _ask_gemini(question, data_context, tries=3):
    """
    Gemini fallback. Retry chhota rakha hai - free tier ka "high
    demand" 503 kabhi-kabhi aata hai, usually 1-2 second mein theek ho
    jata hai (step4d_gemini.py ke batch-script wale 10-30s waits jitne
    lambe nahi, ye interactive chat hai).
    """
    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY not configured (.env)"

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None, "google-genai package not installed"

    client = genai.Client(api_key=GEMINI_API_KEY)
    last_err = None
    for attempt in range(tries):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=[f"DATA:\n{data_context}\n\nQUESTION: {question}"],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.2,
                    max_output_tokens=400,
                ),
            )
            return resp.text, None
        except Exception as e:
            last_err = str(e)[:200]
            if attempt < tries - 1:
                import time
                time.sleep(2 * (attempt + 1))   # 2s, 4s

    return None, last_err


def answer_question(question, data_context):
    """Groq PEHLE (fast) - fail ya unconfigured ho to Gemini pe gir jao."""
    if GROQ_API_KEY:
        answer, err = _ask_groq(question, data_context)
        if answer:
            return answer, None
        print(f"  (Groq fail: {err} - Gemini pe gir rahe hain)")

    return _ask_gemini(question, data_context)
