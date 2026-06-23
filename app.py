"""
app.py — RedRob AI Candidate Ranker
Premium UI · Fixed path loader · Full memoisation
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

# ── PREMIUM CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&display=swap');

*, html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ── Base ── */
.stApp {
    background: #060714;
    background-image:
        radial-gradient(ellipse 80% 50% at 20% -10%, rgba(99,102,241,0.15) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 80% 100%, rgba(168,85,247,0.12) 0%, transparent 50%),
        radial-gradient(ellipse 40% 30% at 50% 50%, rgba(6,182,212,0.06) 0%, transparent 60%);
    min-height: 100vh;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,.03); }
::-webkit-scrollbar-thumb { background: rgba(99,102,241,.4); border-radius: 3px; }

/* ── Hero Banner ── */
.hero-wrap {
    background: linear-gradient(135deg,
        rgba(99,102,241,0.18) 0%,
        rgba(168,85,247,0.12) 40%,
        rgba(6,182,212,0.10) 100%);
    border: 1px solid rgba(99,102,241,0.3);
    border-radius: 24px;
    padding: 40px 44px 32px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
}
.hero-wrap::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 260px; height: 260px;
    background: radial-gradient(circle, rgba(168,85,247,0.15), transparent 70%);
    border-radius: 50%;
    pointer-events: none;
}
.hero-wrap::after {
    content: '';
    position: absolute;
    bottom: -40px; left: -40px;
    width: 200px; height: 200px;
    background: radial-gradient(circle, rgba(6,182,212,0.10), transparent 70%);
    border-radius: 50%;
    pointer-events: none;
}
.hero-tag {
    display: inline-block;
    background: linear-gradient(135deg, rgba(99,102,241,.25), rgba(168,85,247,.20));
    border: 1px solid rgba(99,102,241,.4);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: .72rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: #a78bfa;
    margin-bottom: 14px;
}
.hero-title {
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 2.8rem;
    font-weight: 800;
    background: linear-gradient(135deg, #ffffff 0%, #c4b5fd 45%, #67e8f9 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 10px;
    line-height: 1.1;
}
.hero-sub { color: #94a3b8; font-size: 1.02rem; margin: 0 0 20px; line-height: 1.6; }
.pill-row { display: flex; gap: 10px; flex-wrap: wrap; }
.pill {
    background: rgba(255,255,255,.05);
    border: 1px solid rgba(255,255,255,.10);
    border-radius: 30px;
    padding: 5px 14px;
    font-size: .78rem;
    font-weight: 600;
    color: #cbd5e1;
}
.pill.indigo { border-color: rgba(99,102,241,.4); color: #a78bfa; background: rgba(99,102,241,.08); }
.pill.cyan   { border-color: rgba(6,182,212,.4);  color: #67e8f9; background: rgba(6,182,212,.08); }
.pill.purple { border-color: rgba(168,85,247,.4); color: #d946ef; background: rgba(168,85,247,.08); }
.pill.green  { border-color: rgba(34,197,94,.4);  color: #4ade80; background: rgba(34,197,94,.08); }

/* ── Section header ── */
.sec-hdr {
    font-size: .7rem; font-weight: 700; letter-spacing: .12em;
    text-transform: uppercase; color: #6366f1; margin-bottom: 10px;
}

/* ── Input panels ── */
.input-panel {
    background: rgba(255,255,255,.03);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 18px;
    padding: 20px 20px 16px;
    height: 100%;
}
.input-panel:hover { border-color: rgba(99,102,241,.25); }

/* ── Streamlit widget overrides ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: rgba(255,255,255,.04) !important;
    border: 1px solid rgba(255,255,255,.12) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    font-size: .9rem !important;
    padding: 10px 14px !important;
    transition: border-color .2s !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: rgba(99,102,241,.6) !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,.15) !important;
}
.stFileUploader {
    background: rgba(255,255,255,.02) !important;
    border: 1.5px dashed rgba(99,102,241,.35) !important;
    border-radius: 12px !important;
    padding: 10px !important;
}
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,.03) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    color: #94a3b8 !important;
    font-weight: 600 !important;
    font-size: .82rem !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(99,102,241,.25) !important;
    color: #a78bfa !important;
}
div[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    padding: 12px 28px !important;
    box-shadow: 0 4px 20px rgba(99,102,241,.35) !important;
    transition: all .2s !important;
    letter-spacing: .02em !important;
}
div[data-testid="stButton"] button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 30px rgba(99,102,241,.5) !important;
}
div[data-testid="stButton"] button[kind="secondary"] {
    background: rgba(99,102,241,.12) !important;
    border: 1px solid rgba(99,102,241,.35) !important;
    border-radius: 10px !important;
    color: #a78bfa !important;
    font-weight: 600 !important;
    transition: all .2s !important;
}
div[data-testid="stButton"] button[kind="secondary"]:hover {
    background: rgba(99,102,241,.22) !important;
    border-color: rgba(99,102,241,.6) !important;
}

/* ── Metric cards ── */
.metric-grid { display: flex; gap: 14px; flex-wrap: wrap; margin: 20px 0; }
.metric-card {
    flex: 1; min-width: 120px;
    border-radius: 16px;
    padding: 18px 18px 14px;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 16px;
    padding: 1px;
    background: linear-gradient(135deg, var(--c1), var(--c2));
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
}
.mc-indigo  { background: rgba(99,102,241,.08);  --c1: rgba(99,102,241,.6);  --c2: rgba(168,85,247,.3); }
.mc-cyan    { background: rgba(6,182,212,.08);   --c1: rgba(6,182,212,.6);   --c2: rgba(99,102,241,.3); }
.mc-purple  { background: rgba(168,85,247,.08);  --c1: rgba(168,85,247,.6);  --c2: rgba(236,72,153,.3); }
.mc-green   { background: rgba(34,197,94,.08);   --c1: rgba(34,197,94,.6);   --c2: rgba(6,182,212,.3); }
.mc-amber   { background: rgba(245,158,11,.08);  --c1: rgba(245,158,11,.6);  --c2: rgba(234,179,8,.3); }
.metric-label { font-size:.7rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; opacity:.6; margin-bottom:6px; }
.metric-value { font-family:'Space Grotesk',sans-serif !important; font-size:2rem; font-weight:800; line-height:1; }
.metric-sub   { font-size:.72rem; opacity:.55; margin-top:4px; }

/* ── Candidate cards ── */
.ccard {
    background: rgba(255,255,255,.025);
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 16px;
    padding: 18px 22px 14px;
    margin-bottom: 10px;
    transition: border-color .25s, background .25s, transform .2s;
    cursor: default;
}
.ccard:hover {
    border-color: rgba(99,102,241,.4);
    background: rgba(99,102,241,.05);
    transform: translateX(4px);
}
.ccard.gold {
    background: rgba(245,158,11,.04);
    border-color: rgba(245,158,11,.30);
    box-shadow: 0 0 24px rgba(245,158,11,.06);
}
.ccard.silver {
    background: rgba(148,163,184,.03);
    border-color: rgba(148,163,184,.22);
}
.ccard.bronze {
    background: rgba(180,120,70,.04);
    border-color: rgba(180,120,70,.25);
}
.ccard.top {
    background: rgba(99,102,241,.05);
    border-color: rgba(99,102,241,.28);
}
.rank-badge {
    min-width: 52px;
    text-align: center;
}
.rank-num { font-family:'Space Grotesk',sans-serif !important; font-size:1.6rem; font-weight:800; line-height:1; }
.cname { font-size:1.05rem; font-weight:700; color:#e2e8f0; }
.cmeta { font-size:.84rem; color:#64748b; margin:3px 0 10px; }
.cbadge {
    display:inline-block; padding:2px 9px; border-radius:20px;
    font-size:.67rem; font-weight:700; letter-spacing:.05em;
    text-transform:uppercase; margin-right:4px;
}
.b-fresh  { background:rgba(34,197,94,.12); color:#4ade80; border:1px solid rgba(34,197,94,.3); }
.b-top    { background:rgba(245,158,11,.12); color:#fbbf24; border:1px solid rgba(245,158,11,.3); }
.b-boost  { background:rgba(168,85,247,.12); color:#d946ef; border:1px solid rgba(168,85,247,.3); }
.b-cached { background:rgba(6,182,212,.12);  color:#67e8f9; border:1px solid rgba(6,182,212,.3); }

/* ── Score big ── */
.score-wrap { text-align:right; min-width:70px; }
.score-big { font-family:'Space Grotesk',sans-serif !important; font-size:1.5rem; font-weight:800; line-height:1; }
.score-lbl { font-size:.65rem; color:#475569; margin-top:2px; letter-spacing:.05em; text-transform:uppercase; }

/* ── Signal bars ── */
.pbar-row { display:flex; align-items:center; gap:8px; margin-bottom:5px; }
.pbar-label { font-size:.68rem; font-weight:600; color:#64748b; min-width:44px; }
.pbar-bg { flex:1; height:5px; background:rgba(255,255,255,.06); border-radius:3px; overflow:hidden; }
.pbar-fill { height:100%; border-radius:3px; transition:width .4s ease; }
.pbar-val { font-size:.68rem; font-weight:700; color:#94a3b8; min-width:36px; text-align:right; }

/* ── Reasoning box ── */
.reason-box {
    background: rgba(255,255,255,.02);
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 10px;
    padding: 12px 14px;
    font-size: .78rem;
    color: #94a3b8;
    line-height: 1.7;
    margin-top: 10px;
}
.reason-box strong { color: #c4b5fd; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: rgba(6,7,20,.7) !important;
    border-right: 1px solid rgba(255,255,255,.06) !important;
}
.sidebar-logo {
    text-align: center;
    padding: 8px 0 16px;
}
.sidebar-logo-title {
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 1.3rem;
    font-weight: 800;
    background: linear-gradient(135deg, #a78bfa, #67e8f9);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.sig-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 2px;
}
.sig-icon { font-size: 1rem; width: 22px; }
.sig-name { font-size: .82rem; font-weight: 600; color: #e2e8f0; flex: 1; }
.sig-wt   { font-size: .78rem; font-weight: 700; color: #6366f1;
             background: rgba(99,102,241,.12); border-radius: 6px;
             padding: 1px 7px; }

/* ── Cache status ── */
.cache-panel {
    background: rgba(255,255,255,.03);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 12px;
    padding: 12px 14px;
    margin-top: 4px;
}

/* ── Divider ── */
.rainbow-divider {
    height: 2px;
    background: linear-gradient(90deg, #6366f1, #8b5cf6, #d946ef, #06b6d4, #6366f1);
    border: none;
    border-radius: 2px;
    margin: 24px 0;
    opacity: .5;
}

/* ── Progress bar ── */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #6366f1, #8b5cf6, #06b6d4) !important;
    border-radius: 4px !important;
}

/* ── Alerts ── */
.stSuccess { border-left: 3px solid #22c55e !important; }
.stInfo    { border-left: 3px solid #6366f1 !important; }
.stWarning { border-left: 3px solid #f59e0b !important; }
.stError   { border-left: 3px solid #ef4444 !important; }

/* ── Dataframe ── */
.stDataFrame { border-radius: 12px !important; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE INIT ──────────────────────────────────────────────────────────
if "file_path" not in st.session_state:
    st.session_state["file_path"] = ""
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
        return None, f"File type `{ext or 'unknown'}` not supported. Use: {', '.join(sorted(ALLOWED_EXTS))}"
    if not os.path.isfile(p):
        return None, f"File not found:\n`{p}`"
    return p, None

def pct(v): return f"{v*100:.0f}%"
def score_color(s):
    if s >= 0.80: return "#4ade80"
    if s >= 0.65: return "#facc15"
    if s >= 0.50: return "#fb923c"
    return "#f87171"

# ── SIDEBAR ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div class="sidebar-logo">
  <div style="font-size:2rem;margin-bottom:6px;">🎯</div>
  <div class="sidebar-logo-title">RedRob AI</div>
  <div style="color:#475569;font-size:.72rem;margin-top:2px;">Candidate Intelligence Engine</div>
</div>
""", unsafe_allow_html=True)

    st.divider()
    st.markdown("### 🧠 Scoring Model")
    st.info("**No ML model.** Pure rule-based math — every decision is auditable.", icon="ℹ️")

    signals = [
        ("🎯", "Skill Match",    "35%", "#6366f1"),
        ("📅", "Experience",     "25%", "#22c55e"),
        ("🎓", "Education",      "15%", "#f59e0b"),
        ("📋", "Completeness",   "10%", "#06b6d4"),
        ("📜", "Certifications", "10%", "#a78bfa"),
        ("🔍", "Keywords",        "5%", "#f43f5e"),
    ]
    for icon, name, wt, color in signals:
        st.markdown(
            f'<div class="sig-row">'
            f'<span class="sig-icon">{icon}</span>'
            f'<span class="sig-name">{name}</span>'
            f'<span class="sig-wt" style="color:{color};background:rgba(0,0,0,.2);">{wt}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("### 🌱 Fresher Boost")
    st.markdown("≤ 2 YoE → up to **×1.30 score boost** for GitHub, certs, IIT/BITS/NIT, strong skills.")
    st.markdown("Top-100 always reserves **30 slots** for freshers.")

    st.divider()
    st.markdown("### ⚡ Cache")
    cs = st.session_state.get("cache_stats")
    if cs:
        hit   = cs.get("hit", False)
        color = "#4ade80" if hit else "#f59e0b"
        label = "⚡ Cache Hit" if hit else "⚙️ Computed"
        st.markdown(
            f'<div class="cache-panel">'
            f'<div style="color:{color};font-weight:700;font-size:.88rem;margin-bottom:6px;">{label}</div>'
            f'<div style="color:#64748b;font-size:.76rem;line-height:1.8;">'
            f'Total: <strong style="color:#94a3b8;">{cs.get("total_ms",0):.0f} ms</strong><br>'
            f'Operation: <strong style="color:#94a3b8;">{cs.get("op_ms",0):.0f} ms</strong>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("Run a ranking to see timing.")

    if st.button("🗑️ Clear Cache", use_container_width=True):
        _cached_from_bytes.clear()
        _cached_from_path.clear()
        st.session_state["cache_stats"] = None
        st.success("Cache cleared.")

    st.divider()
    st.markdown("### 📂 Formats")
    for fmt, desc in [("CSV","Google Forms / spreadsheet"),("Excel",".xlsx / .xls"),
                      ("JSON","Array of objects"),("JSONL","Challenge dataset format")]:
        st.markdown(f"**{fmt}** — {desc}")


# ── HERO ─────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-wrap">
  <div class="hero-tag">⚡ AI-Powered · Offline · Explainable</div>
  <div class="hero-title">Smart Candidate Ranking</div>
  <div class="hero-sub">
    Upload your data in any format and get a ranked shortlist in seconds —
    with full, transparent reasoning. No black boxes. No APIs. No guesswork.
  </div>
  <div class="pill-row">
    <span class="pill indigo">🧠 6-Signal Scoring</span>
    <span class="pill cyan">📂 CSV · Excel · JSON · JSONL</span>
    <span class="pill purple">🌱 Fresher-Friendly</span>
    <span class="pill green">🔒 100% Offline</span>
    <span class="pill">💾 Export CSV + JSON</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ── INPUT SECTION ────────────────────────────────────────────────────────────────
col_file, col_jd = st.columns([1, 1], gap="large")

with col_file:
    st.markdown('<div class="sec-hdr">📂 Candidate Data</div>', unsafe_allow_html=True)
    st.markdown('<div class="input-panel">', unsafe_allow_html=True)

    tab_up, tab_path = st.tabs(["⬆️ Upload  (small files)", "📁 Local Path  (large files)"])

    uploaded_file = None
    local_path    = None
    path_error    = None

    with tab_up:
        st.caption("Best for CSV / Excel / JSON under ~100 MB")
        uploaded_file = st.file_uploader(
            "Drop your file here",
            type=["csv", "xlsx", "xls", "json", "jsonl"],
            label_visibility="collapsed",
        )
        if uploaded_file:
            st.success(f"✅ **{uploaded_file.name}** — {uploaded_file.size/1024/1024:.1f} MB")

    with tab_path:
        st.caption("For large files already on this machine (400 MB+)")

        # ── Quick-fill button ──────────────────────────────────────────
        if os.path.isfile(DEFAULT_JSONL):
            if st.button("📂 Load challenge dataset  (candidates.jsonl — 465 MB)",
                         use_container_width=True):
                # Write directly to session_state key the text_input uses
                st.session_state["_path_input_widget"] = DEFAULT_JSONL

        # ── Path text input ────────────────────────────────────────────
        # KEY FIX: use the widget's own key to pre-fill it from the button above.
        # st.session_state["_path_input_widget"] is written by the button,
        # and Streamlit reads it as the widget's current value on re-render.
        raw_path = st.text_input(
            "Full file path",
            placeholder=DEFAULT_JSONL,
            label_visibility="collapsed",
            key="_path_input_widget",          # widget manages its own state
        )

        # ── Validate ───────────────────────────────────────────────────
        if raw_path and raw_path.strip():
            local_path, path_error = validate_path(raw_path.strip())
            if local_path:
                sz = os.path.getsize(local_path) / 1024 / 1024
                st.success(f"✅ **{os.path.basename(local_path)}** — {sz:.1f} MB  ·  ready to rank")
            else:
                st.error(f"❌ {path_error}")

    st.markdown('</div>', unsafe_allow_html=True)

with col_jd:
    st.markdown('<div class="sec-hdr">📝 Job Description</div>', unsafe_allow_html=True)
    st.markdown('<div class="input-panel">', unsafe_allow_html=True)

    DEFAULT_JD = """Software / Data / AI Engineer — General Tech Hiring

Core Skills Required:
- Python, Java, JavaScript, Go, or TypeScript
- REST APIs, Microservices, SQL, system design
- Cloud: AWS, Azure, or GCP
- Agile / Scrum, Git, CI/CD

Preferred Skills:
- Machine learning, NLP, deep learning
- Docker, Kubernetes, DevOps
- React, TypeScript (frontend)
- Spark, Kafka, Hadoop (data engineering)
- Mobile: Android or iOS

Education: Engineering / CS background
Experience: 0–10 years (freshers very welcome)"""

    jd_text = st.text_area(
        "Job Description",
        value=DEFAULT_JD,
        height=278,
        label_visibility="collapsed",
        placeholder="Paste your job description here…",
    )
    st.markdown('</div>', unsafe_allow_html=True)


# ── RUN BUTTON ──────────────────────────────────────────────────────────────────
st.markdown("")
bc, _ = st.columns([1, 3])
with bc:
    run_btn = st.button("🚀 Rank Candidates", type="primary", use_container_width=True)

has_file = (uploaded_file is not None) or (local_path is not None)

# ── VALIDATION MESSAGES ──────────────────────────────────────────────────────────
if run_btn and not has_file:
    if path_error:
        st.error(f"❌ {path_error}")
    else:
        st.warning("⚠️ Please upload a file or enter a valid file path.")
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
                local_path, stat.st_mtime, stat.st_size, fname, jd_text
            )
            pb.progress(100, text="✅ Done — ranked!")

    _total_ms = (time.perf_counter() - _t0) * 1000
    _from_cache = _total_ms < 80

    st.session_state["cache_stats"] = {
        "hit":      _from_cache,
        "total_ms": _total_ms,
        "op_ms":    _total_ms,
    }

    if not ranked:
        st.error("❌ No candidates found. Check the file format.")
        st.stop()

    if _from_cache:
        st.success(f"⚡ **Instant from cache** — {_total_ms:.0f} ms (no recompute needed)")
    else:
        st.info(f"⚙️ Ranked in **{_total_ms:.0f} ms** — cached for next run")

    # ── METRICS ──────────────────────────────────────────────────────
    st.markdown('<hr class="rainbow-divider">', unsafe_allow_html=True)
    st.markdown("## 📊 Ranking Results")

    total_c   = len(ranked)
    top_score = ranked[0]["final_score"] if ranked else 0
    avg_score = sum(r["final_score"] for r in ranked) / max(1, total_c)
    freshers  = sum(1 for r in ranked if r["is_fresher"])
    jd_count  = len(jd_skills)
    avg_exp   = sum(float(str(r.get("yoe","0")).split()[0]) if str(r.get("yoe","0")).replace(".","",1).isdigit() else 0 for r in ranked) / max(1, total_c)

    metrics = [
        ("mc-indigo",  "Candidates",  f"{total_c:,}",        "total ranked"),
        ("mc-cyan",    "Top Score",   f"{top_score:.3f}",     "best match"),
        ("mc-purple",  "Avg Score",   f"{avg_score:.3f}",     "across all"),
        ("mc-green",   "Freshers 🌱", f"{freshers}",          f"of {min(total_c,100)} top"),
        ("mc-amber",   "JD Skills",   f"{jd_count}",          "extracted"),
    ]
    cols = st.columns(5)
    for col, (cls, label, val, sub) in zip(cols, metrics):
        with col:
            st.markdown(
                f'<div class="metric-card {cls}">'
                f'<div class="metric-label">{label}</div>'
                f'<div class="metric-value">{val}</div>'
                f'<div class="metric-sub">{sub}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── JD SKILLS ────────────────────────────────────────────────────
    if jd_skills:
        st.markdown("")
        skill_html = " ".join(
            f'<span style="background:rgba(99,102,241,.14);border:1px solid rgba(99,102,241,.3);'
            f'border-radius:16px;padding:3px 11px;font-size:.75rem;font-weight:600;color:#a78bfa;'
            f'display:inline-block;margin:2px;">{html_mod.escape(s)}</span>'
            for s in sorted(jd_skills)
        )
        st.markdown(f"**Skills extracted from JD:** {skill_html}", unsafe_allow_html=True)

    # ── CANDIDATE CARDS ───────────────────────────────────────────────
    st.markdown('<hr class="rainbow-divider">', unsafe_allow_html=True)

    top_n = min(len(ranked), 100)
    disp_col, _ = st.columns([3, 1])
    with disp_col:
        show_n = st.slider("Candidates to display", 5, top_n, min(25, top_n), 5)

    for r in ranked[:show_n]:
        rk    = r["rank"]
        score = r["final_score"]
        col   = score_color(score)

        if rk == 1:   card_cls = "gold"
        elif rk == 2: card_cls = "silver"
        elif rk == 3: card_cls = "bronze"
        elif rk <= 10: card_cls = "top"
        else:          card_cls = ""

        if rk == 1:   rank_label = "🥇"
        elif rk == 2: rank_label = "🥈"
        elif rk == 3: rank_label = "🥉"
        else:          rank_label = f"#{rk}"

        badges = ""
        if r.get("is_fresher"):      badges += '<span class="cbadge b-fresh">🌱 Fresher</span>'
        if rk <= 10:                 badges += '<span class="cbadge b-top">⭐ Top 10</span>'
        if r.get("fresher_uplift",1) > 1.05:
            badges += f'<span class="cbadge b-boost">×{r["fresher_uplift"]:.2f} Boost</span>'

        name     = html_mod.escape(r.get("name") or r.get("candidate_id", "—"))
        title    = html_mod.escape(r.get("title", ""))
        company  = html_mod.escape(r.get("company", ""))
        location = html_mod.escape(r.get("location", ""))
        yoe_val  = r.get("yoe", "")

        meta = []
        if title:   meta.append(title)
        if company: meta.append(f"@ {company}")
        if yoe_val not in (None, "", "N/A"): meta.append(f"• {yoe_val} YoE")
        if location: meta.append(f"• 📍 {location}")
        meta_str = "  &nbsp;".join(meta)

        # Signal bars
        bars_html = ""
        for sig_name, sig_key, sig_color in [
            ("Skill",  "skill_score",        "#6366f1"),
            ("Exp",    "experience_score",    "#22c55e"),
            ("Edu",    "education_score",     "#f59e0b"),
            ("Certs",  "certification_score", "#a78bfa"),
        ]:
            sv = r.get(sig_key, 0)
            bars_html += (
                f'<div class="pbar-row">'
                f'<span class="pbar-label">{sig_name}</span>'
                f'<div class="pbar-bg"><div class="pbar-fill" '
                f'style="width:{pct(sv)};background:{sig_color};"></div></div>'
                f'<span class="pbar-val">{pct(sv)}</span>'
                f'</div>'
            )

        card_html = f"""
<div class="ccard {card_cls}">
  <div style="display:flex;gap:16px;align-items:flex-start;">
    <div class="rank-badge">
      <div class="rank-num">{rank_label}</div>
    </div>
    <div style="flex:1;min-width:0;">
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:2px;">
        <span class="cname">{name}</span>
        {badges}
      </div>
      <div class="cmeta">{meta_str}</div>
      {bars_html}
    </div>
    <div class="score-wrap">
      <div class="score-big" style="color:{col};">{score:.3f}</div>
      <div class="score-lbl">Score</div>
    </div>
  </div>
</div>
"""
        st.markdown(card_html, unsafe_allow_html=True)

        # Expandable reasoning
        with st.expander(f"📋 Full reasoning — {name}", expanded=False):
            reason = r.get("reasoning", "")
            parts  = reason.split(" || ")
            cols_r = st.columns(2)
            for i, part in enumerate(parts):
                with cols_r[i % 2]:
                    if ":" in part:
                        key_r, val_r = part.split(":", 1)
                        st.markdown(f"**{key_r.strip()}**: {val_r.strip()}")
                    else:
                        st.markdown(part)

            # Sub-scores table
            sub = {
                "Signal": ["Skill", "Experience", "Education", "Completeness", "Certifications", "Keywords"],
                "Score":  [
                    f"{r.get('skill_score',0):.3f}",
                    f"{r.get('experience_score',0):.3f}",
                    f"{r.get('education_score',0):.3f}",
                    f"{r.get('completeness_score',0):.3f}",
                    f"{r.get('certification_score',0):.3f}",
                    f"{r.get('keyword_score',0):.3f}",
                ],
                "Weight": ["35%","25%","15%","10%","10%","5%"],
            }
            st.dataframe(pd.DataFrame(sub), hide_index=True, use_container_width=True)

    # ── EXPORT ───────────────────────────────────────────────────────
    st.markdown('<hr class="rainbow-divider">', unsafe_allow_html=True)
    st.markdown("### 💾 Export Results")

    rows = [{
        "rank":            r["rank"],
        "candidate_id":    r["candidate_id"],
        "name":            r.get("name",""),
        "title":           r.get("title",""),
        "company":         r.get("company",""),
        "yoe":             r.get("yoe",""),
        "is_fresher":      r["is_fresher"],
        "final_score":     r["final_score"],
        "skill_score":     r["skill_score"],
        "experience_score":r["experience_score"],
        "education_score": r["education_score"],
        "completeness_score": r["completeness_score"],
        "certification_score":r["certification_score"],
        "keyword_score":   r["keyword_score"],
        "fresher_uplift":  r["fresher_uplift"],
        "reasoning":       r["reasoning"],
    } for r in ranked]

    df_exp = pd.DataFrame(rows)
    ec1, ec2, _ = st.columns([1, 1, 2])
    with ec1:
        st.download_button("⬇️ Download CSV",
            df_exp.to_csv(index=False).encode(),
            "ranked_candidates.csv", "text/csv",
            use_container_width=True)
    with ec2:
        st.download_button("⬇️ Download JSON",
            json.dumps(rows, indent=2).encode(),
            "ranked_candidates.json", "application/json",
            use_container_width=True)

    # ── FULL TABLE ────────────────────────────────────────────────────
    with st.expander("📊 View full ranked table", expanded=False):
        st.dataframe(df_exp[[
            "rank","name","title","company","yoe","is_fresher",
            "final_score","skill_score","experience_score","education_score",
        ]].rename(columns={
            "rank":"Rank","name":"Name","title":"Title","company":"Company",
            "yoe":"YoE","is_fresher":"Fresher?","final_score":"Score",
            "skill_score":"Skill","experience_score":"Exp","education_score":"Edu",
        }), hide_index=True, use_container_width=True)


# ── GETTING STARTED (no data yet) ────────────────────────────────────────────────
elif not run_btn:
    st.markdown('<hr class="rainbow-divider">', unsafe_allow_html=True)
    st.markdown("### 👋 Getting Started")

    ga, gb = st.columns(2)
    with ga:
        st.markdown("**Sample Google Forms CSV structure:**")
        st.dataframe(pd.DataFrame({
            "Your Name":           ["Priya Sharma",    "Rahul Mehta"],
            "Years of Experience": ["0",               "5"],
            "Technical Skills":    ["Python, PyTorch", "Java, AWS"],
            "College":             ["IIT Bombay",      "NIT Trichy"],
            "CGPA":                ["9.2",             "8.1"],
            "Certifications":      ["DeepLearning.AI", "AWS ML"],
            "GitHub":              ["github.com/ps",   "github.com/rm"],
        }), hide_index=True, use_container_width=True)

    with gb:
        st.markdown("**What you get per candidate:**")
        st.markdown("""
- 🏆 **Final rank** with composite 0–1 score
- 🎯 **Skill match** — which JD skills were found
- 📅 **Experience score** — YoE curve + fresher boost
- 🎓 **Education score** — institution tier + GPA
- 📜 **Certification score** — upskilling evidence
- 📋 **Full reasoning** — every sub-score explained
- 💾 **CSV + JSON** export ready
""")
        st.info("Auto-detects 50+ column name variants — no setup needed.", icon="✨")
