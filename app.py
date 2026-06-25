"""
app.py — RedRob AI Candidate Ranker
Premium UI · No overlap · Balanced scoring · Full memoisation
"""

import streamlit as st
import pandas as pd
import json
import os
import html as html_mod
import time
from universal_parser import parse_any_format
from universal_scorer import rank_candidates, _extract_skills_from_jd

# ── CACHED FUNCTIONS ────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, max_entries=3)
def _cached_from_bytes(raw: bytes, filename: str, jd_text: str) -> tuple:
    cands = parse_any_format(raw, filename)
    if not cands:
        return [], []
    return rank_candidates(cands, jd_text)

@st.cache_data(show_spinner=False, max_entries=3)
def _cached_from_path(realpath: str, _mtime: float, _size: int,
                      filename: str, jd_text: str) -> tuple:
    with open(realpath, "rb") as fh:
        raw = fh.read()
    cands = parse_any_format(raw, filename)
    if not cands:
        return [], []
    return rank_candidates(cands, jd_text)

# ── PAGE CONFIG ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RedRob AI — Candidate Ranker",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── PREMIUM CSS — no div wrappers around widgets (causes overlap) ────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* ── Background ── */
.stApp {
    background: #07081a;
    background-image:
        radial-gradient(ellipse 70% 40% at 15% 0%,   rgba(99,102,241,.18) 0%, transparent 55%),
        radial-gradient(ellipse 50% 35% at 85% 95%,  rgba(168,85,247,.13) 0%, transparent 50%),
        radial-gradient(ellipse 35% 25% at 50% 50%,  rgba(6,182,212,.07)  0%, transparent 60%);
    min-height: 100vh;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,.02); }
::-webkit-scrollbar-thumb { background: rgba(99,102,241,.5); border-radius: 3px; }

/* ── Hero ── */
.hero-wrap {
    background: linear-gradient(135deg,
        rgba(99,102,241,.15) 0%, rgba(168,85,247,.10) 50%, rgba(6,182,212,.09) 100%);
    border: 1px solid rgba(99,102,241,.28);
    border-radius: 22px;
    padding: 38px 42px 30px;
    margin-bottom: 26px;
    position: relative; overflow: hidden;
}
.hero-wrap::before {
    content:''; position:absolute; top:-70px; right:-70px;
    width:280px; height:280px;
    background:radial-gradient(circle,rgba(168,85,247,.14),transparent 68%);
    border-radius:50%; pointer-events:none;
}
.hero-tag {
    display:inline-block;
    background:linear-gradient(135deg,rgba(99,102,241,.2),rgba(168,85,247,.15));
    border:1px solid rgba(99,102,241,.38); border-radius:20px;
    padding:4px 14px; font-size:.7rem; font-weight:700; letter-spacing:.09em;
    text-transform:uppercase; color:#a78bfa; margin-bottom:12px;
}
.hero-title {
    font-family:'Space Grotesk',sans-serif !important;
    font-size:2.6rem; font-weight:800;
    background:linear-gradient(135deg,#ffffff 0%,#c4b5fd 45%,#67e8f9 100%);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text; margin:0 0 10px; line-height:1.1;
}
.hero-sub { color:#94a3b8; font-size:.98rem; margin:0 0 18px; line-height:1.6; }
.pill-row { display:flex; gap:9px; flex-wrap:wrap; }
.pill {
    border-radius:30px; padding:5px 14px; font-size:.75rem; font-weight:600;
    border: 1px solid; display:inline-block;
}
.p-indigo { color:#a78bfa; border-color:rgba(99,102,241,.4);  background:rgba(99,102,241,.09); }
.p-cyan   { color:#67e8f9; border-color:rgba(6,182,212,.4);   background:rgba(6,182,212,.09); }
.p-purple { color:#d946ef; border-color:rgba(168,85,247,.4);  background:rgba(168,85,247,.09); }
.p-green  { color:#4ade80; border-color:rgba(34,197,94,.4);   background:rgba(34,197,94,.09); }
.p-slate  { color:#cbd5e1; border-color:rgba(255,255,255,.15); background:rgba(255,255,255,.05); }

/* ── Section label ── */
.sec-lbl {
    font-size:.68rem; font-weight:700; letter-spacing:.12em;
    text-transform:uppercase; color:#6366f1; margin-bottom:8px;
    display:block;
}

/* ── Widget overrides ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background:rgba(255,255,255,.04) !important;
    border:1px solid rgba(255,255,255,.11) !important;
    border-radius:10px !important; color:#e2e8f0 !important;
    font-size:.89rem !important; padding:10px 14px !important;
    transition:border-color .2s, box-shadow .2s !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color:rgba(99,102,241,.6) !important;
    box-shadow:0 0 0 3px rgba(99,102,241,.14) !important;
}
.stFileUploader > div {
    background:rgba(255,255,255,.02) !important;
    border:1.5px dashed rgba(99,102,241,.38) !important;
    border-radius:12px !important;
    transition:border-color .2s !important;
}
.stFileUploader > div:hover { border-color:rgba(99,102,241,.65) !important; }
.stTabs [data-baseweb="tab-list"] {
    background:rgba(255,255,255,.03) !important;
    border-radius:10px !important; padding:3px !important; gap:3px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius:8px !important; color:#64748b !important;
    font-weight:600 !important; font-size:.81rem !important;
    padding:7px 18px !important;
}
.stTabs [aria-selected="true"] {
    background:rgba(99,102,241,.22) !important; color:#a78bfa !important;
}

/* ── Buttons ── */
div[data-testid="stButton"] button[kind="primary"] {
    background:linear-gradient(135deg,#6366f1,#8b5cf6) !important;
    border:none !important; border-radius:12px !important;
    font-weight:700 !important; font-size:.97rem !important;
    padding:13px 28px !important; letter-spacing:.02em !important;
    box-shadow:0 4px 20px rgba(99,102,241,.38) !important;
    transition:transform .18s, box-shadow .18s !important;
    color:#fff !important;
}
div[data-testid="stButton"] button[kind="primary"]:hover {
    transform:translateY(-2px) !important;
    box-shadow:0 8px 30px rgba(99,102,241,.55) !important;
}
div[data-testid="stButton"] button[kind="secondary"] {
    background:rgba(99,102,241,.10) !important;
    border:1px solid rgba(99,102,241,.32) !important;
    border-radius:10px !important; color:#a78bfa !important;
    font-weight:600 !important; transition:all .18s !important;
}
div[data-testid="stButton"] button[kind="secondary"]:hover {
    background:rgba(99,102,241,.20) !important;
}

/* ── Metric cards ── */
.mc {
    border-radius:15px; padding:18px 16px 14px;
    position:relative; overflow:hidden; height:100%;
    transition:transform .2s;
}
.mc:hover { transform:translateY(-2px); }
.mc-label { font-size:.68rem; font-weight:700; letter-spacing:.09em;
            text-transform:uppercase; opacity:.6; margin-bottom:7px; }
.mc-value { font-family:'Space Grotesk',sans-serif !important;
            font-size:1.95rem; font-weight:800; line-height:1; }
.mc-sub   { font-size:.7rem; opacity:.5; margin-top:4px; }
.mc-indigo { background:rgba(99,102,241,.09); border:1px solid rgba(99,102,241,.28); }
.mc-cyan   { background:rgba(6,182,212,.09);  border:1px solid rgba(6,182,212,.28); }
.mc-purple { background:rgba(168,85,247,.09); border:1px solid rgba(168,85,247,.28); }
.mc-green  { background:rgba(34,197,94,.09);  border:1px solid rgba(34,197,94,.28); }
.mc-amber  { background:rgba(245,158,11,.09); border:1px solid rgba(245,158,11,.28); }

/* ── Candidate cards ── */
.cc {
    border-radius:15px; padding:16px 20px 12px;
    margin-bottom:9px; border:1px solid rgba(255,255,255,.07);
    background:rgba(255,255,255,.025);
    transition:border-color .22s, background .22s, transform .18s;
}
.cc:hover { border-color:rgba(99,102,241,.38); background:rgba(99,102,241,.05); transform:translateX(3px); }
.cc-gold   { background:rgba(245,158,11,.04); border-color:rgba(245,158,11,.28);
             box-shadow:0 0 20px rgba(245,158,11,.06); }
.cc-silver { background:rgba(148,163,184,.03); border-color:rgba(148,163,184,.20); }
.cc-bronze { background:rgba(180,120,70,.04);  border-color:rgba(180,120,70,.22); }
.cc-top    { background:rgba(99,102,241,.05);  border-color:rgba(99,102,241,.26); }

.rank-num  { font-family:'Space Grotesk',sans-serif !important;
             font-size:1.5rem; font-weight:800; line-height:1;
             min-width:50px; text-align:center; padding-top:2px; }
.cname     { font-size:1.02rem; font-weight:700; color:#e2e8f0; }
.cmeta     { font-size:.82rem; color:#64748b; margin:3px 0 8px; }
.cbadge {
    display:inline-block; padding:2px 9px; border-radius:20px;
    font-size:.65rem; font-weight:700; letter-spacing:.05em;
    text-transform:uppercase; margin-right:4px;
}
.b-fresh  { background:rgba(34,197,94,.10); color:#4ade80; border:1px solid rgba(34,197,94,.28); }
.b-top    { background:rgba(245,158,11,.10); color:#fbbf24; border:1px solid rgba(245,158,11,.28); }
.b-boost  { background:rgba(168,85,247,.10); color:#d946ef; border:1px solid rgba(168,85,247,.28); }
.b-exp    { background:rgba(6,182,212,.10);  color:#67e8f9; border:1px solid rgba(6,182,212,.28); }
.score-big { font-family:'Space Grotesk',sans-serif !important;
             font-size:1.45rem; font-weight:800; line-height:1; }
.score-lbl { font-size:.62rem; color:#475569; margin-top:2px;
             letter-spacing:.05em; text-transform:uppercase; }

/* ── Signal bars ── */
.pb-row { display:flex; align-items:center; gap:7px; margin-bottom:4px; }
.pb-lbl { font-size:.67rem; font-weight:600; color:#64748b; min-width:42px; }
.pb-bg  { flex:1; height:5px; background:rgba(255,255,255,.06); border-radius:3px; overflow:hidden; }
.pb-fill{ height:100%; border-radius:3px; }
.pb-val { font-size:.67rem; font-weight:700; color:#94a3b8; min-width:34px; text-align:right; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background:rgba(5,6,18,.75) !important;
    border-right:1px solid rgba(255,255,255,.06) !important;
}
.sidebar-brand {
    text-align:center; padding:6px 0 14px;
}
.brand-title {
    font-family:'Space Grotesk',sans-serif !important;
    font-size:1.25rem; font-weight:800;
    background:linear-gradient(135deg,#a78bfa,#67e8f9);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text;
}
.sig-row { display:flex; align-items:center; gap:8px; margin-bottom:3px; }
.sig-icon { font-size:.95rem; width:20px; }
.sig-name { font-size:.8rem; font-weight:600; color:#e2e8f0; flex:1; }
.sig-wt   { font-size:.75rem; font-weight:700; color:#6366f1;
             background:rgba(99,102,241,.12); border-radius:5px; padding:1px 7px; }

/* ── Divider ── */
.rdiv {
    height:2px;
    background:linear-gradient(90deg,#6366f1,#8b5cf6,#d946ef,#06b6d4,#6366f1);
    border:none; border-radius:2px; margin:22px 0; opacity:.45;
}

/* ── Progress ── */
.stProgress > div > div > div > div {
    background:linear-gradient(90deg,#6366f1,#8b5cf6,#06b6d4) !important;
    border-radius:4px !important;
}

/* ── Skill tag ── */
.stag {
    display:inline-block; margin:2px 3px;
    background:rgba(99,102,241,.13); border:1px solid rgba(99,102,241,.28);
    border-radius:15px; padding:3px 11px;
    font-size:.73rem; font-weight:600; color:#a78bfa;
}
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ───────────────────────────────────────────────────────────────
if "cache_stats" not in st.session_state:
    st.session_state["cache_stats"] = None

DEFAULT_JSONL = "/Users/dsanthoshkumar/Desktop/redrobs-ranker/dataset/candidates.jsonl"
ALLOWED_EXTS  = {".csv", ".xlsx", ".xls", ".json", ".jsonl"}

def validate_path(p: str):
    p = p.strip()
    if not p:
        return None, None
    ext = os.path.splitext(p)[1].lower()
    if ext not in ALLOWED_EXTS:
        return None, f"Unsupported file type `{ext or 'unknown'}`. Use: {', '.join(sorted(ALLOWED_EXTS))}"
    if not os.path.isfile(p):
        return None, f"File not found: `{p}`"
    return p, None

def pct(v):        return f"{v*100:.0f}%"
def score_color(s):
    if s >= 0.80:  return "#4ade80"
    if s >= 0.65:  return "#facc15"
    if s >= 0.50:  return "#fb923c"
    return "#f87171"

# ── SIDEBAR ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div class="sidebar-brand">
  <div style="font-size:1.9rem;margin-bottom:4px">🎯</div>
  <div class="brand-title">RedRob AI</div>
  <div style="color:#475569;font-size:.7rem;margin-top:2px">Candidate Intelligence Engine</div>
</div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("**🧠 Scoring Model**")
    st.info("Pure rule-based math — every decision is auditable.", icon="ℹ️")

    for icon, name, wt in [("🎯","Skill Match","35%"),("📅","Experience","25%"),
                            ("🎓","Education","15%"),("📋","Completeness","10%"),
                            ("📜","Certifications","10%"),("🔍","Keywords","5%")]:
        st.markdown(
            f'<div class="sig-row">'
            f'<span class="sig-icon">{icon}</span>'
            f'<span class="sig-name">{name}</span>'
            f'<span class="sig-wt">{wt}</span>'
            f'</div>', unsafe_allow_html=True)

    st.divider()
    st.markdown("**📈 Experience Curve**")
    exp_df = pd.DataFrame({
        "YoE Range":  ["0","1","2","3–4","5–7","8–10","11–15","15+"],
        "Exp Score":  ["0.60","0.65","0.72","0.85","1.00","0.92","0.78","0.62"],
    })
    st.dataframe(exp_df, hide_index=True, use_container_width=True)
    st.caption("5–7 YoE = prime range (1.00). Freshers boosted by skills & certs.")

    st.divider()
    st.markdown("**⚡ Cache**")
    cs = st.session_state.get("cache_stats")
    if cs:
        hit   = cs.get("hit", False)
        color = "#4ade80" if hit else "#f59e0b"
        label = "⚡ Cache Hit" if hit else "⚙️ Computed"
        st.markdown(
            f'<div style="background:rgba(255,255,255,.03);border:1px solid '
            f'rgba(255,255,255,.08);border-radius:10px;padding:11px 13px;">'
            f'<div style="color:{color};font-weight:700;font-size:.85rem;margin-bottom:5px;">{label}</div>'
            f'<div style="color:#64748b;font-size:.74rem;line-height:1.9;">'
            f'Total: <strong style="color:#94a3b8">{cs.get("total_ms",0):.0f} ms</strong></div>'
            f'</div>', unsafe_allow_html=True)
    else:
        st.caption("Run a ranking to see timing.")

    if st.button("🗑️ Clear Cache", use_container_width=True):
        _cached_from_bytes.clear()
        _cached_from_path.clear()
        st.session_state["cache_stats"] = None
        st.success("Cache cleared.")

# ── HERO ─────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-wrap">
  <div class="hero-tag">⚡ AI-Powered · Offline · Explainable</div>
  <div class="hero-title">Smart Candidate Ranking</div>
  <div class="hero-sub">Upload your data in any format — get a merit-ranked shortlist in seconds
  with full, transparent scoring. No black boxes. No APIs. No guesswork.</div>
  <div class="pill-row">
    <span class="pill p-indigo">🧠 6-Signal Scoring</span>
    <span class="pill p-cyan">📂 CSV · Excel · JSON · JSONL</span>
    <span class="pill p-purple">🌱 Fresher + Experienced</span>
    <span class="pill p-green">🔒 100% Offline</span>
    <span class="pill p-slate">💾 CSV + JSON Export</span>
  </div>
</div>""", unsafe_allow_html=True)

# ── INPUT LAYOUT ─────────────────────────────────────────────────────────────────
col_l, col_r = st.columns([1, 1], gap="large")

# ── LEFT: File Input ─────────────────────────────────────────────────────────────
with col_l:
    st.markdown('<span class="sec-lbl">📂 Candidate Data</span>', unsafe_allow_html=True)

    tab_up, tab_path = st.tabs(["⬆️ Upload  (< 100 MB)", "📁 Local Path  (400 MB+)"])

    uploaded_file = None
    local_path    = None
    path_error    = None

    with tab_up:
        st.caption("CSV · Excel · JSON · JSONL — drag and drop or click to browse")
        uploaded_file = st.file_uploader(
            "upload",
            type=["csv", "xlsx", "xls", "json", "jsonl"],
            label_visibility="collapsed",
        )
        if uploaded_file:
            st.success(f"✅ **{uploaded_file.name}** — {uploaded_file.size/1024/1024:.1f} MB ready")

    with tab_path:
        st.caption("Enter the full absolute path to a file already on this machine.")

        # Button writes directly into the text_input's widget key
        if os.path.isfile(DEFAULT_JSONL):
            if st.button("📂 Load  candidates.jsonl  (465 MB challenge dataset)",
                         use_container_width=True, key="btn_autofill"):
                st.session_state["_path_widget"] = DEFAULT_JSONL

        raw_path = st.text_input(
            "path",
            placeholder=DEFAULT_JSONL,
            label_visibility="collapsed",
            key="_path_widget",          # ← button writes here, widget reads here
        )

        if raw_path and raw_path.strip():
            local_path, path_error = validate_path(raw_path.strip())
            if local_path:
                sz = os.path.getsize(local_path) / 1024 / 1024
                st.success(f"✅ **{os.path.basename(local_path)}** — {sz:.1f} MB  ·  ready")
            else:
                st.error(f"❌ {path_error}")

# ── RIGHT: Job Description ───────────────────────────────────────────────────────
with col_r:
    st.markdown('<span class="sec-lbl">📝 Job Description</span>', unsafe_allow_html=True)

    DEFAULT_JD = """Software & Technology Engineer — Multi-Role Hiring Drive

Core Skills (Must Have ≥ 3):
- Python, Java, JavaScript, TypeScript, Go, C++, SQL
- REST APIs, Microservices, Node.js, FastAPI, Spring Boot
- PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch
- AWS, Azure, GCP, Docker, Kubernetes, Terraform, CI/CD
- React, Angular, Vue.js, TypeScript, Tailwind CSS
- Android (Kotlin), iOS (Swift), Flutter, React Native
- Selenium, Cypress, Unit Testing, Test Automation
- Spark, Kafka, Pandas, ETL, Snowflake, BigQuery, dbt

Preferred / Bonus:
- Machine Learning, Deep Learning, NLP, Computer Vision
- PyTorch, TensorFlow, Scikit-learn, Hugging Face
- LLM fine-tuning, RAG, Vector Embeddings, LangChain
- Figma, UI/UX Design, SAP, Salesforce, PMP

Education: B.E./B.Tech/BCA/MCA/B.Sc CS or related
Experience: 0–10 years (freshers from IIT/NIT/BITS very welcome)
Certifications: AWS, GCP, Azure, Coursera, DeepLearning.AI"""

    jd_text = st.text_area(
        "jd",
        value=DEFAULT_JD,
        height=320,
        label_visibility="collapsed",
        placeholder="Paste job description here…",
    )

# ── RUN BUTTON ──────────────────────────────────────────────────────────────────
st.markdown("")
bc, _ = st.columns([1, 3])
with bc:
    run_btn = st.button("🚀 Rank Candidates", type="primary", use_container_width=True)

has_file = (uploaded_file is not None) or (local_path is not None)

if run_btn and not has_file:
    st.warning("⚠️ Please upload a file or enter a valid file path first." +
               (f"\n\n_{path_error}_" if path_error else ""))
elif run_btn and not jd_text.strip():
    st.warning("⚠️ Please enter a job description.")

# ── RANKING ─────────────────────────────────────────────────────────────────────
if run_btn and has_file and jd_text.strip():

    _t0 = time.perf_counter()

    with st.spinner("⚡ Checking cache or computing ranking…"):
        if uploaded_file is not None:
            raw   = uploaded_file.read()
            fname = uploaded_file.name
            pb = st.progress(0, text="⚡ Parsing + ranking…")
            ranked, jd_skills = _cached_from_bytes(raw, fname, jd_text)
            pb.progress(100, text="✅ Done!")
        else:
            fname = os.path.basename(local_path)
            stat  = os.stat(local_path)
            pb = st.progress(0, text="⚡ Checking cache / reading file…")
            ranked, jd_skills = _cached_from_path(
                local_path, stat.st_mtime, stat.st_size, fname, jd_text)
            pb.progress(100, text="✅ Done — ranked!")

    _total_ms   = (time.perf_counter() - _t0) * 1000
    _from_cache = _total_ms < 80

    st.session_state["cache_stats"] = {"hit": _from_cache, "total_ms": _total_ms}

    if not ranked:
        st.error("❌ No candidates found. Check the file format and try again.")
        st.stop()

    if _from_cache:
        st.success(f"⚡ **Instant from cache** — {_total_ms:.0f} ms")
    else:
        st.info(f"⚙️ Ranked **{len(ranked):,}** candidates in **{_total_ms:.0f} ms** — cached for next run")

    # ── METRICS ──────────────────────────────────────────────────────────────────
    st.markdown('<hr class="rdiv">', unsafe_allow_html=True)
    st.markdown("## 📊 Ranking Results")

    n        = len(ranked)
    top_s    = ranked[0]["final_score"]
    avg_s    = sum(r["final_score"] for r in ranked) / max(1, n)
    freshers = sum(1 for r in ranked[:100] if r["is_fresher"])
    senior   = sum(1 for r in ranked[:100] if not r["is_fresher"])

    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    for col, cls, label, val, sub in [
        (mc1, "mc-indigo", "Total Ranked",  f"{n:,}",             "candidates"),
        (mc2, "mc-cyan",   "Top Score",     f"{top_s:.3f}",        "best match"),
        (mc3, "mc-purple", "Average Score", f"{avg_s:.3f}",        "all candidates"),
        (mc4, "mc-green",  "Freshers 🌱",   f"{freshers}",         "in top 100"),
        (mc5, "mc-amber",  "Experienced",   f"{senior}",           "in top 100"),
    ]:
        with col:
            st.markdown(
                f'<div class="mc {cls}">'
                f'<div class="mc-label">{label}</div>'
                f'<div class="mc-value">{val}</div>'
                f'<div class="mc-sub">{sub}</div>'
                f'</div>', unsafe_allow_html=True)

    # ── JD SKILLS ────────────────────────────────────────────────────────────────
    if jd_skills:
        st.markdown("")
        tags = " ".join(
            f'<span class="stag">{html_mod.escape(s)}</span>'
            for s in sorted(jd_skills[:40])
        )
        st.markdown(f"**JD skills extracted:** {tags}", unsafe_allow_html=True)

    # ── CANDIDATE CARDS ──────────────────────────────────────────────────────────
    st.markdown('<hr class="rdiv">', unsafe_allow_html=True)

    total_show = min(len(ranked), 200)
    show_n = st.slider("Candidates to display", 5, total_show, min(25, total_show), 5,
                       key="show_n_slider")

    for r in ranked[:show_n]:
        rk  = r["rank"]
        s   = r["final_score"]
        col = score_color(s)

        if rk == 1:    cc, rl = "cc-gold",   "🥇"
        elif rk == 2:  cc, rl = "cc-silver", "🥈"
        elif rk == 3:  cc, rl = "cc-bronze", "🥉"
        elif rk <= 10: cc, rl = "cc-top",    f"#{rk}"
        else:          cc, rl = "",           f"#{rk}"

        badges = ""
        if r.get("is_fresher"):                          badges += '<span class="cbadge b-fresh">🌱 Fresher</span>'
        elif r.get("yoe", 0) >= 5:                       badges += '<span class="cbadge b-exp">💼 Senior</span>'
        if rk <= 10:                                     badges += '<span class="cbadge b-top">⭐ Top 10</span>'
        if r.get("fresher_uplift", 1.0) > 1.02:         badges += f'<span class="cbadge b-boost">×{r["fresher_uplift"]:.2f} Boost</span>'

        name    = html_mod.escape(r.get("name") or r.get("candidate_id", "—"))
        title   = html_mod.escape(r.get("title", ""))
        company = html_mod.escape(r.get("company", ""))
        loc     = html_mod.escape(r.get("location", ""))
        yoe_v   = r.get("yoe", "")

        meta = []
        if title:   meta.append(title)
        if company: meta.append(f"@ {company}")
        if yoe_v not in (None, "", "N/A", 0): meta.append(f"• {yoe_v} YoE")
        if loc:     meta.append(f"• 📍 {loc}")
        meta_str = " &nbsp;·&nbsp; ".join(meta)

        bars = ""
        for bn, bk, bc_ in [
            ("Skill",  "skill_score",          "#6366f1"),
            ("Exp",    "experience_score",      "#22c55e"),
            ("Edu",    "education_score",       "#f59e0b"),
            ("Certs",  "certification_score",   "#a78bfa"),
        ]:
            sv = r.get(bk, 0)
            bars += (
                f'<div class="pb-row">'
                f'<span class="pb-lbl">{bn}</span>'
                f'<div class="pb-bg"><div class="pb-fill" style="width:{pct(sv)};background:{bc_};"></div></div>'
                f'<span class="pb-val">{pct(sv)}</span>'
                f'</div>'
            )

        st.markdown(f"""
<div class="cc {cc}">
  <div style="display:flex;gap:14px;align-items:flex-start;">
    <div class="rank-num">{rl}</div>
    <div style="flex:1;min-width:0;">
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:2px;">
        <span class="cname">{name}</span>{badges}
      </div>
      <div class="cmeta">{meta_str}</div>
      {bars}
    </div>
    <div style="text-align:right;min-width:65px;">
      <div class="score-big" style="color:{col};">{s:.3f}</div>
      <div class="score-lbl">Score</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

        # Expandable reasoning — uses native Streamlit, no HTML nesting
        with st.expander(f"📋 Reasoning · {name}", expanded=False):
            rc1, rc2 = st.columns(2)
            subs = {
                "Signal":  ["Skill","Experience","Education","Completeness","Certifications","Keywords"],
                "Score":   [f"{r.get(k,0):.3f}" for k in
                            ["skill_score","experience_score","education_score",
                             "completeness_score","certification_score","keyword_score"]],
                "Weight":  ["35%","25%","15%","10%","10%","5%"],
            }
            with rc1:
                st.dataframe(pd.DataFrame(subs), hide_index=True, use_container_width=True)
            with rc2:
                for part in r.get("reasoning","").split(" || "):
                    if ":" in part:
                        k2, v2 = part.split(":", 1)
                        st.markdown(f"**{k2.strip()}**: {v2.strip()}")

    # ── EXPORT ───────────────────────────────────────────────────────────────────
    st.markdown('<hr class="rdiv">', unsafe_allow_html=True)
    st.markdown("### 💾 Export")

    rows = [{
        "rank":               r["rank"],
        "candidate_id":       r["candidate_id"],
        "name":               r.get("name",""),
        "title":              r.get("title",""),
        "company":            r.get("company",""),
        "yoe":                r.get("yoe",""),
        "is_fresher":         r["is_fresher"],
        "final_score":        r["final_score"],
        "skill_score":        r["skill_score"],
        "experience_score":   r["experience_score"],
        "education_score":    r["education_score"],
        "completeness_score": r["completeness_score"],
        "certification_score":r["certification_score"],
        "keyword_score":      r["keyword_score"],
        "fresher_uplift":     r["fresher_uplift"],
        "reasoning":          r["reasoning"],
    } for r in ranked]

    df_exp = pd.DataFrame(rows)
    e1, e2, _ = st.columns([1, 1, 2])
    with e1:
        st.download_button("⬇️ CSV",
            df_exp.to_csv(index=False).encode(),
            "ranked_candidates.csv", "text/csv",
            use_container_width=True)
    with e2:
        st.download_button("⬇️ JSON",
            json.dumps(rows, indent=2).encode(),
            "ranked_candidates.json", "application/json",
            use_container_width=True)

    with st.expander("📊 Full ranked table", expanded=False):
        st.dataframe(df_exp[[
            "rank","name","title","company","yoe","is_fresher",
            "final_score","skill_score","experience_score","education_score",
        ]].rename(columns={
            "rank":"Rank","name":"Name","title":"Title","company":"Company",
            "yoe":"YoE","is_fresher":"Fresher","final_score":"Score",
            "skill_score":"Skill","experience_score":"Exp","education_score":"Edu",
        }), hide_index=True, use_container_width=True)


# ── GETTING STARTED ──────────────────────────────────────────────────────────────
elif not run_btn:
    st.markdown('<hr class="rdiv">', unsafe_allow_html=True)
    st.markdown("### 👋 Getting Started")

    gs1, gs2 = st.columns(2)
    with gs1:
        st.markdown("**Sample CSV structure:**")
        st.dataframe(pd.DataFrame({
            "name":           ["Priya Sharma",    "Rahul Mehta"],
            "yoe":            ["0",               "5"],
            "skills":         ["Python, PyTorch", "Java, AWS, Kubernetes"],
            "college":        ["IIT Bombay",      "NIT Trichy"],
            "gpa":            ["9.2",             "8.1"],
            "certifications": ["DeepLearning.AI", "AWS Solutions Architect"],
            "github":         ["github.com/ps",   "github.com/rm"],
        }), hide_index=True, use_container_width=True)

    with gs2:
        st.markdown("**Per-candidate output:**")
        for line in [
            "🏆 Final rank + composite 0–1 score",
            "🎯 Skill match — which JD skills were found",
            "📅 Experience score — balanced YoE curve",
            "🎓 Education — institution tier + GPA",
            "📜 Certifications — upskilling evidence",
            "📋 Full reasoning — every sub-score explained",
            "💾 CSV + JSON export",
        ]:
            st.markdown(f"- {line}")
        st.info("Auto-detects 50+ column name variants. Zero config.", icon="✨")
