"""
app.py — RedRob AI Candidate Ranker
Streamlit UI — fixed rendering, clean layout, no raw HTML leaks.
"""

import streamlit as st
import pandas as pd
import json
import io
import os
import html as html_mod
import time
import hashlib
from universal_parser import parse_any_format
from universal_scorer import rank_candidates, _extract_skills_from_jd

# ── MEMOISED WRAPPERS ──────────────────────────────────────────────────────────
# st.cache_data persists across reruns for the same cache key.
# parse: keyed on (file_bytes, filename) — Streamlit auto-hashes bytes.
# rank:  keyed on a stable tuple from the parsed candidates + jd_text.
# For LOCAL PATH files (400MB+), we avoid re-hashing the giant byte array
# by using (realpath, mtime, size) as an O(1) cache key instead.

@st.cache_data(show_spinner=False, max_entries=3)
def _cached_parse_bytes(raw: bytes, filename: str) -> list:
    """Parse file bytes → list of candidate dicts. Cached by file content hash."""
    return parse_any_format(raw, filename)

@st.cache_data(show_spinner=False, max_entries=3)
def _cached_parse_path(realpath: str, _mtime: float, _size: int, filename: str) -> list:
    """
    Parse a large on-disk file WITHOUT loading its full bytes into the cache key.
    Cache key = (realpath, mtime, size) — O(1) stat call instead of O(n) hash.
    _mtime and _size are prefixed with _ so Streamlit skips hashing them (they
    are already primitive types embedded in the key).
    """
    with open(realpath, "rb") as fh:
        raw = fh.read()
    return parse_any_format(raw, filename)

@st.cache_data(show_spinner=False, max_entries=5)
def _cached_rank(candidates_json: str, jd_text: str) -> tuple:
    """
    Rank candidates. Cache key = (serialised candidates, jd_text).
    Candidates are serialised to a compact JSON string so the list-of-dicts
    is hashable and change-aware.
    """
    import json as _json
    cands = _json.loads(candidates_json)
    return rank_candidates(cands, jd_text)

def _serialise_candidates(cands: list) -> str:
    """Compact JSON for cache key — stable sort by candidate_id."""
    return json.dumps(
        sorted(cands, key=lambda c: c.get("candidate_id", "")),
        sort_keys=True, separators=(',', ':')
    )


# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RedRob AI Candidate Ranker",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── GLOBAL CSS — Complete Design System ───────────────────────────────────────
st.markdown("""
<style>
/* ═══════════════════════════════════════════════════════════════════
   PHASE 3 — DESIGN TOKENS
═══════════════════════════════════════════════════════════════════ */
:root {
  /* Backgrounds */
  --bg-base:      #080B14;
  --bg-surface:   #0F1220;
  --bg-elevated:  #161B2E;
  --bg-glass:     rgba(15,18,32,0.75);

  /* Brand */
  --primary:      #6366F1;
  --primary-dim:  rgba(99,102,241,0.15);
  --primary-glow: rgba(99,102,241,0.40);
  --secondary:    #A78BFA;
  --secondary-dim:rgba(167,139,250,0.12);

  /* Semantic */
  --success:      #22C55E; --success-dim: rgba(34,197,94,0.14);
  --warning:      #F59E0B; --warning-dim: rgba(245,158,11,0.14);
  --error:        #EF4444; --error-dim:   rgba(239,68,68,0.14);
  --gold:         #EAB308; --gold-dim:    rgba(234,179,8,0.10);

  /* Text */
  --text-1: #E2E8F0;
  --text-2: #94A3B8;
  --text-3: #475569;

  /* Borders */
  --border:       rgba(255,255,255,0.07);
  --border-hover: rgba(99,102,241,0.45);

  /* Radius */
  --r-sm: 8px; --r-md: 14px; --r-lg: 20px; --r-xl: 28px;

  /* Typography */
  --font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 3 — TYPOGRAPHY & BASE
═══════════════════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, p, span, div {
  font-family: var(--font) !important;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 3 — APP BACKGROUND (animated mesh gradient)
═══════════════════════════════════════════════════════════════════ */
.stApp {
  background:
    radial-gradient(ellipse 80% 50% at 20% -10%, rgba(99,102,241,0.12) 0%, transparent 60%),
    radial-gradient(ellipse 60% 40% at 80% 110%, rgba(167,139,250,0.09) 0%, transparent 55%),
    radial-gradient(ellipse 100% 80% at 50% 50%, #080B14 0%, #080B14 100%);
  min-height: 100vh;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 3 — SIDEBAR
═══════════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0C0F1E 0%, #080B14 100%) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] > div { padding: 0 !important; }
[data-testid="stSidebarContent"] { padding: 20px 16px 24px !important; }

/* Sidebar headings */
[data-testid="stSidebar"] h2 {
  font-size: 1.1rem !important; font-weight: 800 !important;
  color: var(--text-1) !important; margin: 0 0 2px !important;
  letter-spacing: -.01em;
}
[data-testid="stSidebar"] h3 {
  font-size: .82rem !important; font-weight: 700 !important;
  color: var(--secondary) !important;
  text-transform: uppercase; letter-spacing: .08em;
  margin: 18px 0 10px !important;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — HERO BANNER
═══════════════════════════════════════════════════════════════════ */
.hero {
  position: relative; overflow: hidden;
  background: linear-gradient(135deg, rgba(99,102,241,.16) 0%, rgba(167,139,250,.08) 100%);
  border: 1px solid rgba(99,102,241,.28);
  border-radius: var(--r-xl);
  padding: 40px 44px 32px;
  margin-bottom: 28px;
}
.hero::before {
  content: ''; position: absolute;
  top: -60px; right: -60px;
  width: 220px; height: 220px;
  background: radial-gradient(circle, rgba(99,102,241,.18) 0%, transparent 70%);
  pointer-events: none;
}
.hero::after {
  content: ''; position: absolute;
  bottom: -40px; left: 30%;
  width: 160px; height: 160px;
  background: radial-gradient(circle, rgba(167,139,250,.12) 0%, transparent 70%);
  pointer-events: none;
}
.hero h1 {
  font-size: 2.5rem; font-weight: 900; letter-spacing: -.03em;
  background: linear-gradient(135deg, #E0E7FF 0%, #A78BFA 50%, #6366F1 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 10px; line-height: 1.15;
}
.hero p {
  color: var(--text-2); font-size: 1rem; font-weight: 400;
  line-height: 1.65; margin: 0 0 18px; max-width: 580px;
}

/* Feature pills row */
.pill-row { display: flex; gap: 8px; flex-wrap: wrap; }
.pill {
  display: inline-flex; align-items: center; gap: 5px;
  background: rgba(99,102,241,.10);
  border: 1px solid rgba(99,102,241,.25);
  border-radius: 30px;
  padding: 5px 14px;
  font-size: .78rem; font-weight: 600; color: var(--secondary);
  letter-spacing: .01em;
  transition: background .2s, border-color .2s;
}
.pill:hover { background: rgba(99,102,241,.18); border-color: rgba(99,102,241,.45); }

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — SECTION LABEL
═══════════════════════════════════════════════════════════════════ */
.section-label {
  font-size: .72rem; font-weight: 700; letter-spacing: .10em;
  text-transform: uppercase; color: var(--text-3);
  margin: 0 0 8px;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — INPUT PANELS (glassmorphism)
═══════════════════════════════════════════════════════════════════ */
.input-panel {
  background: rgba(15,18,32,0.6);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 20px;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: border-color .25s;
}
.input-panel:hover { border-color: rgba(99,102,241,.25); }

/* Streamlit tab bar */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  background: rgba(255,255,255,.03) !important;
  border-radius: var(--r-md) var(--r-md) 0 0 !important;
  border-bottom: 1px solid var(--border) !important;
  gap: 0 !important; padding: 0 4px !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
  background: transparent !important;
  border: none !important; border-radius: 0 !important;
  color: var(--text-2) !important;
  font-size: .83rem !important; font-weight: 600 !important;
  padding: 10px 16px !important;
  transition: color .2s !important;
}
[data-testid="stTabs"] [data-baseweb="tab"]:hover { color: var(--text-1) !important; }
[data-testid="stTabs"] [aria-selected="true"] {
  color: var(--secondary) !important;
  border-bottom: 2px solid var(--primary) !important;
}
[data-testid="stTabs"] [data-baseweb="tab-panel"] {
  background: rgba(15,18,32,.45) !important;
  border: 1px solid var(--border) !important;
  border-top: none !important;
  border-radius: 0 0 var(--r-md) var(--r-md) !important;
  padding: 16px !important;
}

/* Streamlit text inputs */
[data-testid="stTextInput"] > div > div > input,
[data-testid="stTextArea"] > div > div > textarea {
  background: rgba(8,11,20,.6) !important;
  border: 1px solid rgba(255,255,255,.10) !important;
  border-radius: var(--r-sm) !important;
  color: var(--text-1) !important;
  font-family: var(--font) !important;
  font-size: .9rem !important;
  transition: border-color .2s, box-shadow .2s !important;
}
[data-testid="stTextInput"] > div > div > input:focus,
[data-testid="stTextArea"] > div > div > textarea:focus {
  border-color: var(--primary) !important;
  box-shadow: 0 0 0 3px rgba(99,102,241,.20) !important;
  outline: none !important;
}

/* File uploader */
[data-testid="stFileUploader"] > div {
  background: rgba(8,11,20,.5) !important;
  border: 1.5px dashed rgba(99,102,241,.35) !important;
  border-radius: var(--r-md) !important;
  padding: 20px !important;
  transition: border-color .2s, background .2s !important;
}
[data-testid="stFileUploader"] > div:hover {
  border-color: rgba(99,102,241,.65) !important;
  background: rgba(99,102,241,.06) !important;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 6 — PRIMARY BUTTON (CTA — Rank Candidates)
═══════════════════════════════════════════════════════════════════ */
[data-testid="stButton"] button[kind="primary"] {
  background: linear-gradient(135deg, #6366F1 0%, #7C3AED 100%) !important;
  border: none !important;
  border-radius: var(--r-sm) !important;
  color: #FFFFFF !important;
  font-size: .95rem !important; font-weight: 700 !important;
  letter-spacing: .01em;
  padding: 14px 28px !important;
  box-shadow: 0 4px 20px rgba(99,102,241,.35), 0 1px 0 rgba(255,255,255,.1) inset !important;
  transition: all .2s ease !important;
  position: relative; overflow: hidden;
}
[data-testid="stButton"] button[kind="primary"]::before {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,.08) 0%, transparent 60%);
  pointer-events: none;
}
[data-testid="stButton"] button[kind="primary"]:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 32px rgba(99,102,241,.50), 0 1px 0 rgba(255,255,255,.15) inset !important;
}
[data-testid="stButton"] button[kind="primary"]:active {
  transform: translateY(0) !important;
  box-shadow: 0 2px 8px rgba(99,102,241,.30) !important;
}
[data-testid="stButton"] button[kind="primary"]:focus-visible {
  outline: 3px solid rgba(99,102,241,.6) !important;
  outline-offset: 3px !important;
}

/* Secondary buttons */
[data-testid="stButton"] button[kind="secondary"] {
  background: rgba(255,255,255,.04) !important;
  border: 1px solid rgba(255,255,255,.12) !important;
  border-radius: var(--r-sm) !important;
  color: var(--text-1) !important;
  font-size: .86rem !important; font-weight: 600 !important;
  transition: all .2s !important;
}
[data-testid="stButton"] button[kind="secondary"]:hover {
  background: rgba(99,102,241,.10) !important;
  border-color: rgba(99,102,241,.40) !important;
  color: var(--secondary) !important;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — CANDIDATE RANK CARDS
═══════════════════════════════════════════════════════════════════ */
.ccard {
  position: relative; overflow: hidden;
  background: rgba(15,18,32,.7);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  padding: 18px 22px 14px;
  margin-bottom: 10px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: border-color .25s, background .25s, transform .2s, box-shadow .25s;
  cursor: default;
}
.ccard::before {
  content: ''; position: absolute;
  left: 0; top: 0; bottom: 0; width: 3px;
  background: var(--primary); border-radius: 3px 0 0 3px;
  opacity: 0; transition: opacity .25s;
}
.ccard:hover {
  border-color: var(--border-hover);
  background: rgba(99,102,241,.06);
  transform: translateX(3px);
  box-shadow: 0 4px 24px rgba(0,0,0,.4), 0 0 0 1px rgba(99,102,241,.15);
}
.ccard:hover::before { opacity: 1; }

/* Gold — top 3 */
.ccard.gold {
  border-color: rgba(234,179,8,.30);
  background: rgba(234,179,8,.05);
}
.ccard.gold::before { background: var(--gold); }
.ccard.gold:hover { border-color: rgba(234,179,8,.55); box-shadow: 0 4px 24px rgba(234,179,8,.12); }

/* Green — freshers */
.ccard.green {
  border-color: rgba(34,197,94,.25);
  background: rgba(34,197,94,.04);
}
.ccard.green::before { background: var(--success); }

/* Rank badge */
.rank-num {
  font-size: 1.6rem; line-height: 1; font-weight: 900;
  letter-spacing: -.04em;
}

/* Candidate name */
.cname {
  font-size: 1.05rem; font-weight: 700;
  color: var(--text-1); letter-spacing: -.01em;
}

/* Meta line (title, company, YoE) */
.cmeta {
  font-size: .84rem; color: var(--text-2);
  margin: 4px 0 10px; line-height: 1.5;
}

/* Badges */
.cbadge {
  display: inline-flex; align-items: center;
  padding: 2px 9px; border-radius: 20px;
  font-size: .68rem; font-weight: 700; letter-spacing: .05em;
  text-transform: uppercase; margin-right: 5px;
  vertical-align: middle;
}
.b-fresh { background: var(--success-dim); color: #4ADE80; border: 1px solid rgba(34,197,94,.30); }
.b-top   { background: var(--gold-dim);    color: #FBBF24; border: 1px solid rgba(234,179,8,.30); }
.b-boost { background: var(--primary-dim); color: var(--secondary); border: 1px solid rgba(99,102,241,.30); }

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — SIGNAL PROGRESS BARS (animated)
═══════════════════════════════════════════════════════════════════ */
.pbar-row {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 5px;
}
.pbar-label {
  color: var(--text-3); font-size: .73rem; font-weight: 600;
  min-width: 42px; text-transform: uppercase; letter-spacing: .04em;
}
.pbar-bg {
  flex: 1; background: rgba(255,255,255,.06);
  border-radius: 4px; height: 5px; overflow: hidden;
}
.pbar-fill {
  height: 5px; border-radius: 4px;
  animation: barGrow .6s cubic-bezier(.22,1,.36,1) forwards;
  transform-origin: left;
}
@keyframes barGrow {
  from { transform: scaleX(0); opacity: .4; }
  to   { transform: scaleX(1); opacity: 1; }
}
.pbar-val {
  color: var(--text-2); font-size: .73rem; font-weight: 600;
  min-width: 36px; text-align: right;
}
.score-big {
  font-size: 1.15rem; font-weight: 900;
  letter-spacing: -.03em; text-align: right;
  font-variant-numeric: tabular-nums;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — SKILL CHIPS
═══════════════════════════════════════════════════════════════════ */
.chip {
  display: inline-flex; align-items: center;
  padding: 3px 10px; border-radius: 20px;
  font-size: .74rem; font-weight: 500; margin: 2px 2px 2px 0;
  background: var(--primary-dim); color: var(--secondary);
  border: 1px solid rgba(99,102,241,.20);
  transition: background .15s, border-color .15s;
}
.chip:hover { background: rgba(99,102,241,.22); border-color: rgba(99,102,241,.40); }
.chip.matched {
  background: var(--success-dim); color: #4ADE80;
  border-color: rgba(34,197,94,.28);
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — REASONING EXPANDER
═══════════════════════════════════════════════════════════════════ */
[data-testid="stExpander"] {
  background: rgba(8,11,20,.5) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-sm) !important;
  margin-top: 10px !important;
}
[data-testid="stExpander"]:hover {
  border-color: rgba(99,102,241,.30) !important;
}
[data-testid="stExpander"] summary {
  color: var(--text-2) !important;
  font-size: .82rem !important; font-weight: 600 !important;
  padding: 10px 14px !important;
}
[data-testid="stExpander"] summary:hover { color: var(--secondary) !important; }

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — METRICS ROW
═══════════════════════════════════════════════════════════════════ */
[data-testid="metric-container"] {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  padding: 16px !important;
  transition: border-color .2s !important;
}
[data-testid="metric-container"]:hover {
  border-color: rgba(99,102,241,.30) !important;
}
[data-testid="stMetricLabel"] { color: var(--text-3) !important; font-size: .76rem !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: .07em; }
[data-testid="stMetricValue"] { color: var(--text-1) !important; font-size: 1.6rem !important; font-weight: 800 !important; letter-spacing: -.03em; }

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — DOWNLOAD BUTTONS
═══════════════════════════════════════════════════════════════════ */
[data-testid="stDownloadButton"] button {
  background: rgba(255,255,255,.04) !important;
  border: 1px solid rgba(255,255,255,.12) !important;
  border-radius: var(--r-sm) !important;
  color: var(--text-1) !important;
  font-weight: 600 !important; font-size: .86rem !important;
  transition: all .2s !important;
}
[data-testid="stDownloadButton"] button:hover {
  background: var(--success-dim) !important;
  border-color: rgba(34,197,94,.40) !important;
  color: #4ADE80 !important;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — ALERT / INFO / SUCCESS / WARNING BOXES
═══════════════════════════════════════════════════════════════════ */
[data-testid="stAlert"] {
  border-radius: var(--r-sm) !important;
  border-left-width: 3px !important;
  font-size: .88rem !important;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — SECTION DIVIDER
═══════════════════════════════════════════════════════════════════ */
.sdiv {
  border: none; border-top: 1px solid var(--border);
  margin: 22px 0;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — SIDEBAR SCORING SIGNALS
═══════════════════════════════════════════════════════════════════ */
.sig-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,.04);
}
.sig-icon { font-size: .95rem; min-width: 20px; }
.sig-name {
  color: var(--text-1); font-size: .80rem; font-weight: 600;
  flex: 1; letter-spacing: -.01em;
}
.sig-wt {
  background: var(--primary-dim); color: var(--secondary);
  border-radius: 10px; padding: 1px 8px;
  font-size: .74rem; font-weight: 700; letter-spacing: .02em;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 3 — SCROLLBAR
═══════════════════════════════════════════════════════════════════ */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(99,102,241,.30); border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(99,102,241,.55); }

/* ═══════════════════════════════════════════════════════════════════
   PHASE 3 — STREAMLIT CHROME CLEANUP
═══════════════════════════════════════════════════════════════════ */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
.block-container {
  padding: 28px 32px 48px !important;
  max-width: 1280px !important;
}

/* Streamlit select/radio */
[data-testid="stRadio"] label, [data-testid="stSelectbox"] label {
  color: var(--text-2) !important; font-size: .84rem !important; font-weight: 500 !important;
}
[data-testid="stSelectbox"] > div > div {
  background: rgba(8,11,20,.6) !important;
  border-color: rgba(255,255,255,.10) !important;
  border-radius: var(--r-sm) !important;
  color: var(--text-1) !important;
}
[data-testid="stDataFrame"] {
  border-radius: var(--r-md) !important;
  overflow: hidden !important;
  border: 1px solid var(--border) !important;
}

/* Caption / help text */
[data-testid="stCaptionContainer"] p {
  color: var(--text-3) !important; font-size: .78rem !important;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 3 — FOCUS (WCAG 2.2 AA)
═══════════════════════════════════════════════════════════════════ */
*:focus-visible {
  outline: 2px solid rgba(99,102,241,.7) !important;
  outline-offset: 3px !important;
  border-radius: 4px;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 6 — MICRO-ANIMATIONS
═══════════════════════════════════════════════════════════════════ */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes pulse-ring {
  0%   { box-shadow: 0 0 0 0   rgba(99,102,241,.35); }
  70%  { box-shadow: 0 0 0 10px rgba(99,102,241,.00); }
  100% { box-shadow: 0 0 0 0   rgba(99,102,241,.00); }
}
.ccard { animation: fadeUp .35s ease both; }
.ccard:nth-child(2) { animation-delay: .05s; }
.ccard:nth-child(3) { animation-delay: .10s; }
.ccard:nth-child(4) { animation-delay: .15s; }
.ccard:nth-child(5) { animation-delay: .20s; }

/* ═══════════════════════════════════════════════════════════════════
   PHASE 5 — FORM FIELD LABELS (Streamlit)
═══════════════════════════════════════════════════════════════════ */
[data-testid="stTextInput"] label, [data-testid="stTextArea"] label,
[data-testid="stFileUploader"] label {
  color: var(--text-2) !important;
  font-size: .80rem !important; font-weight: 600 !important;
  letter-spacing: .01em; text-transform: uppercase;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 8 — RESPONSIVE (Mobile-first)
═══════════════════════════════════════════════════════════════════ */
@media (max-width: 768px) {
  .hero { padding: 24px 20px 20px; }
  .hero h1 { font-size: 1.65rem; }
  .hero p { font-size: .88rem; }
  .block-container { padding: 16px 12px 32px !important; }
  .ccard { padding: 14px 14px 10px; }
  .rank-num { font-size: 1.25rem; }
  .score-big { font-size: .95rem; }
}
@media (max-width: 480px) {
  .hero h1 { font-size: 1.35rem; }
  .pill { font-size: .70rem; padding: 4px 10px; }
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — RESULTS SECTION HEADER
═══════════════════════════════════════════════════════════════════ */
.results-header {
  display: flex; align-items: center; gap: 12px;
  margin: 24px 0 16px;
}
.results-header h2 {
  font-size: 1.35rem; font-weight: 800;
  color: var(--text-1); letter-spacing: -.02em; margin: 0;
}
.results-badge {
  background: var(--primary-dim);
  border: 1px solid rgba(99,102,241,.28);
  border-radius: 20px; padding: 3px 12px;
  font-size: .75rem; font-weight: 700;
  color: var(--secondary); letter-spacing: .03em;
}

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — GETTING STARTED (empty state)
═══════════════════════════════════════════════════════════════════ */
.empty-state {
  text-align: center; padding: 48px 24px;
  border: 1.5px dashed rgba(255,255,255,.08);
  border-radius: var(--r-lg);
  margin-top: 16px;
}
.empty-state .es-icon { font-size: 2.5rem; margin-bottom: 12px; }
.empty-state h3 { font-size: 1.1rem; font-weight: 700; color: var(--text-1); margin: 0 0 8px; }
.empty-state p { color: var(--text-2); font-size: .88rem; line-height: 1.65; max-width: 420px; margin: 0 auto; }

/* ═══════════════════════════════════════════════════════════════════
   PHASE 4 — CACHE BANNER (hit/miss)
═══════════════════════════════════════════════════════════════════ */
.cache-hit  { border-left: 3px solid var(--success) !important; }
.cache-miss { border-left: 3px solid var(--warning) !important; }
</style>
""", unsafe_allow_html=True)



# ── SIDEBAR ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎯 RedRob AI Ranker")
    st.caption("Intelligent, explainable, fresher-friendly ranking")
    st.divider()

    st.markdown("### 🧠 How Scoring Works")
    st.info("**No ML model was trained.** Pure rule-based math — every score is auditable.", icon="ℹ️")

    st.markdown("**6 Scoring Signals:**")
    signals_info = [
        ("🎯", "Skill Match",     "35%", "JD skills found in candidate profile"),
        ("📅", "Experience",      "25%", "YoE curve — freshers boosted"),
        ("🎓", "Education",       "15%", "Institution tier + field + GPA"),
        ("📋", "Completeness",    "10%", "Fields filled + GitHub / LinkedIn"),
        ("📜", "Certifications",  "10%", "ML/AI upskilling evidence"),
        ("🔍", "Keywords",         "5%", "Implicit JD mentions across full text"),
    ]
    for icon, name, weight, desc in signals_info:
        st.markdown(
            f'<div class="sig-row">'
            f'<span class="sig-icon">{icon}</span>'
            f'<span class="sig-name">{name}</span>'
            f'<span class="sig-wt">{weight}</span>'
            f'</div>'
            f'<div style="color:#64748b;font-size:.74rem;padding:1px 0 4px 30px;">{desc}</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("### 🌱 Fresher Boost")
    st.markdown("""
Candidates with **≤ 2 YoE** get up to **×1.30 bonus** for:
- GitHub activity
- Strong certifications
- Top-tier institution
- Good skill coverage
""")
    st.markdown("Dual-track guarantees **30 fresher slots** in the top 100.")

    st.divider()
    st.markdown("### 📂 Accepted Formats")
    st.markdown("""
- **CSV** — Google Forms export
- **Excel** — .xlsx / .xls
- **JSON** — array of objects
- **JSONL** — challenge format
""")
    st.markdown("**Auto-detects** 50+ column name variants — no setup needed.")

    st.divider()
    st.markdown("### ⚡ Cache Status")
    if "cache_stats" in st.session_state:
        cs = st.session_state["cache_stats"]
        hit  = cs.get("hit", False)
        icon = "⚡ Cache Hit" if hit else "⚙️ Computed"
        color = "#22c55e" if hit else "#f59e0b"
        st.markdown(
            f'<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);'
            f'border-radius:10px;padding:12px 14px;">>'
            f'<div style="color:{color};font-weight:700;font-size:.9rem;">{icon}</div>'
            f'<div style="color:#94a3b8;font-size:.78rem;margin-top:4px;">>'
            f'Parse: {cs.get("parse_ms",0):.0f} ms<br>'
            f'Rank: {cs.get("rank_ms",0):.0f} ms<br>'
            f'Total: {cs.get("total_ms",0):.0f} ms'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("Run a ranking to see cache stats.")

    if st.button("🗑️ Clear Cache", use_container_width=True):
        _cached_parse_bytes.clear()
        _cached_parse_path.clear()
        _cached_rank.clear()
        if "cache_stats" in st.session_state:
            del st.session_state["cache_stats"]
        st.success("✅ Cache cleared.")


# ── HEADER ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🎯 RedRob AI Candidate Ranker</h1>
  <p>Upload candidate data in <strong>any format</strong> and get a ranked shortlist
     with full, explainable reasoning — no APIs, no black boxes.</p>
  <div class="pill-row">
    <span class="pill">📂 CSV · Excel · JSON · JSONL</span>
    <span class="pill">🧠 6-Signal Scoring</span>
    <span class="pill">🌱 Fresher-Friendly</span>
    <span class="pill">🔒 100% Offline</span>
    <span class="pill">💾 Export CSV / JSON</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ── INPUT ROW ──────────────────────────────────────────────────────────────────
left_col, right_col = st.columns([1, 1], gap="large")

# Session-state initialisation (runs once)
if "local_path_val" not in st.session_state:
    st.session_state["local_path_val"] = ""

with left_col:
    st.markdown("#### 📂 Candidate Data")

    tab_upload, tab_path = st.tabs(["⬆️ Upload File (small files)", "📁 Load from Path (large files)"])

    uploaded_file = None
    local_path    = None          # will be set below from session_state or text_input

    with tab_upload:
        st.caption("Best for CSV / Excel / JSON under ~100 MB")
        uploaded_file = st.file_uploader(
            "Drop your file here",
            type=["csv", "xlsx", "xls", "json", "jsonl"],
            help="Google Forms CSV, spreadsheet, JSON array or JSONL",
            label_visibility="collapsed",
        )
        if uploaded_file:
            st.success(f"✅ **{uploaded_file.name}** — {uploaded_file.size/1024/1024:.1f} MB")

    with tab_path:
        st.caption("Use this for large files (400 MB+) already on your computer")

        DEFAULT_JSONL = "/Users/dsanthoshkumar/Desktop/redrobs-ranker/dataset/candidates.jsonl"

        # ── Security: allowed extensions and base directories ──
        ALLOWED_EXTS  = {'.csv', '.xlsx', '.xls', '.json', '.jsonl'}
        ALLOWED_BASES = [
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Downloads"),
            os.path.expanduser("~/Documents"),
            "/tmp",
        ]

        def _safe_path(p):
            """Return (ok, reason) — True only if ext and base dir are whitelisted."""
            p = os.path.realpath(p)          # resolve symlinks / traversal
            ext = os.path.splitext(p)[1].lower()
            if ext not in ALLOWED_EXTS:
                return False, f"File type `{ext}` not allowed. Use: {', '.join(sorted(ALLOWED_EXTS))}"
            if not any(p.startswith(b) for b in ALLOWED_BASES):
                return False, f"Path must be inside Desktop, Downloads, or Documents."
            return True, ""

        # One-click quick-fill button — stores path in session_state
        if os.path.isfile(DEFAULT_JSONL):
            if st.button("📂 Use challenge dataset  (candidates.jsonl — 465 MB)",
                         use_container_width=True):
                st.session_state["local_path_val"] = DEFAULT_JSONL

        # Text input — pre-filled from session_state so quick-fill works instantly
        typed = st.text_input(
            "Or paste any file path:",
            value=st.session_state["local_path_val"],
            placeholder=DEFAULT_JSONL,
            key="path_text_input",
        )
        # Always sync typed value back to session_state
        st.session_state["local_path_val"] = typed.strip()

        # Validate and expose
        _raw_path = st.session_state["local_path_val"]
        if _raw_path:
            ok, reason = _safe_path(_raw_path)
            if not ok:
                st.error(f"❌ {reason}")
                local_path = None
            elif os.path.isfile(os.path.realpath(_raw_path)):
                size_mb = os.path.getsize(_raw_path) / 1024 / 1024
                st.success(f"✅ Ready: **{os.path.basename(_raw_path)}** — {size_mb:.1f} MB")
                local_path = os.path.realpath(_raw_path)   # canonical safe path
            else:
                st.error(f"❌ File not found:\n`{_raw_path}`")
                local_path = None
        else:
            local_path = None


with right_col:
    st.markdown("#### 📝 Job Description")
    DEFAULT_JD = """Software / AI Engineer (General Tech Hiring)

We are hiring across engineering, data, AI, and product roles.

Core Skills Required:
- Python or Java or JavaScript or Go
- REST APIs, Microservices, SQL
- Cloud platforms: AWS or Azure or GCP
- Agile / Scrum methodologies
- Problem-solving and system design

Preferred / Additional Skills:
- Machine learning, NLP, or data science
- DevOps: Docker, Kubernetes, CI/CD
- Frontend: React, TypeScript
- Data engineering: Spark, Kafka, Hadoop
- Mobile: Android or iOS development

Education: Any engineering or CS background
Experience: 0–10 years (freshers welcome)
Location: India preferred, open to remote"""

    jd_text = st.text_area(
        "Job Description",
        value=DEFAULT_JD,
        height=260,
        label_visibility="collapsed",
    )

# ── RUN BUTTON ─────────────────────────────────────────────────────────────────
st.markdown("")
btn_col, _ = st.columns([1, 4])
with btn_col:
    run_btn = st.button("🚀 Rank Candidates", type="primary", use_container_width=True)


# ── RESULTS ────────────────────────────────────────────────────────────────────
has_file = (uploaded_file is not None) or bool(local_path)

if run_btn and has_file and jd_text.strip():

    _t_total_start = time.perf_counter()
    _parse_ms = _rank_ms = 0
    _from_cache = True          # assume cache hit; set False if we compute

    with st.spinner("⚡ Loading from cache or computing…"):

        if uploaded_file is not None:
            # ── browser upload ──
            raw   = uploaded_file.read()
            fname = uploaded_file.name
            _t0 = time.perf_counter()
            try:
                candidates = _cached_parse_bytes.__wrapped__(raw, fname)   # test cache
            except AttributeError:
                pass
            _t0 = time.perf_counter()
            candidates  = _cached_parse_bytes(raw, fname)
            _parse_ms   = (time.perf_counter() - _t0) * 1000
            _has_progress = False

        else:
            # ── local file path ──
            fname  = os.path.basename(local_path)
            stat   = os.stat(local_path)
            _mtime = stat.st_mtime
            _size  = stat.st_size

            progress_bar  = st.progress(0, text="⚡ Checking cache / reading file…")
            _has_progress = True

            _t0        = time.perf_counter()
            candidates = _cached_parse_path(local_path, _mtime, _size, fname)
            _parse_ms  = (time.perf_counter() - _t0) * 1000

            progress_bar.progress(70, text="🤖 Ranking candidates…")

        if not candidates:
            st.error("❌ Could not parse the file. Check the format and try again.")
            st.stop()

        # ── Serialise for rank cache key ──
        cands_json = _serialise_candidates(candidates)

        _t0          = time.perf_counter()
        ranked, jd_skills = _cached_rank(cands_json, jd_text)
        _rank_ms     = (time.perf_counter() - _t0) * 1000

        _total_ms = (time.perf_counter() - _t_total_start) * 1000

        # Detect cache hit: very fast (<50ms) almost certainly came from cache
        _from_cache = (_parse_ms + _rank_ms) < 50

        st.session_state["cache_stats"] = {
            "hit":      _from_cache,
            "parse_ms": _parse_ms,
            "rank_ms":  _rank_ms,
            "total_ms": _total_ms,
        }

        if _has_progress:
            progress_bar.progress(100, text="✅ Done — ranked!")

    # ── Cache hit badge ──
    if _from_cache:
        st.success("⚡ **Results served from cache** — instant! (no recompute)")
    else:
        st.info(f"⚙️ Computed in **{_total_ms:.0f} ms** — result now cached for next run.")


    # ── STATS ─────────────────────────────────────────────────────
    st.markdown("<hr class='sdiv'>", unsafe_allow_html=True)
    st.markdown("## 📊 Ranking Complete")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Candidates", f"{len(ranked):,}")
    m2.metric("Top Score",  f"{ranked[0]['final_score']:.3f}" if ranked else "—")
    m3.metric("Avg Score",  f"{sum(r['final_score'] for r in ranked)/max(1,len(ranked)):.3f}")
    m4.metric("Freshers 🌱", sum(1 for r in ranked if r["is_fresher"]))
    m5.metric("JD Skills",  len(jd_skills))

    # ── JD SKILLS CHIPS ───────────────────────────────────────────
    with st.expander("🔍 Skills extracted from Job Description", expanded=False):
        chip_html = "".join(
            f'<span class="chip">{s}</span>' for s in jd_skills[:50]
        )
        st.markdown(chip_html, unsafe_allow_html=True)
        st.caption(f"{len(jd_skills)} skills identified from the job description text.")

    st.markdown("<hr class='sdiv'>", unsafe_allow_html=True)

    # ── RANKED LIST ───────────────────────────────────────────────
    st.markdown("## 🏆 Ranked Candidates")

    RANK_EMOJI = {1: "🥇", 2: "🥈", 3: "🥉"}

    def score_bar_color(score):
        if score >= 0.75: return "#22c55e"
        if score >= 0.55: return "#6366f1"
        if score >= 0.35: return "#f59e0b"
        return "#ef4444"

    def pct_str(score):
        return f"{score*100:.0f}%"

    for r in ranked:
        rank = r["rank"]
        is_fresh = r["is_fresher"]
        is_top3  = rank <= 3

        card_class = "gold" if is_top3 else ("green" if is_fresh else "")
        rank_label = RANK_EMOJI.get(rank, f"#{rank}")

        # badges
        badges = ""
        if is_top3:
            badges += '<span class="cbadge b-top">⭐ Top 3</span>'
        if is_fresh:
            badges += '<span class="cbadge b-fresh">🌱 Fresher</span>'
        if r["fresher_uplift"] > 1.0:
            badges += f'<span class="cbadge b-boost">×{r["fresher_uplift"]:.2f} Boost</span>'

        # meta line
        # ── XSS protection: escape ALL user-supplied data before HTML rendering ──
        name     = html_mod.escape(r.get("name") or r.get("candidate_id", "—"))
        title    = html_mod.escape(r.get("title", ""))
        company  = html_mod.escape(r.get("company", ""))
        location = html_mod.escape(r.get("location", ""))
        yoe_val  = r.get("yoe", "")

        meta_parts = []
        if title:   meta_parts.append(title)
        if company: meta_parts.append(f"@ {company}")
        if yoe_val is not None and yoe_val != "": meta_parts.append(f"• {yoe_val} YoE")
        if location: meta_parts.append(f"• 📍 {location}")
        meta_str = "  ".join(meta_parts)

        # signal mini-bars (HTML)
        bar_color = score_bar_color(r["final_score"])
        signals_html = ""
        for sig_name, sig_key, sig_color in [
            ("Skill",  "skill_score",          "#6366f1"),
            ("Exp",    "experience_score",      "#22c55e"),
            ("Edu",    "education_score",       "#f59e0b"),
            ("Certs",  "certification_score",   "#a78bfa"),
        ]:
            sv = r.get(sig_key, 0)
            signals_html += (
                f'<div class="pbar-row">'
                f'<span class="pbar-label">{sig_name}</span>'
                f'<div class="pbar-bg"><div class="pbar-fill" '
                f'style="width:{pct_str(sv)};background:{sig_color};"></div></div>'
                f'<span class="pbar-val">{pct_str(sv)}</span>'
                f'</div>'
            )

        card_html = f"""
<div class="ccard {card_class}">
  <div style="display:flex;gap:16px;align-items:flex-start;">
    <div style="min-width:48px;text-align:center;padding-top:2px;">
      <div class="rank-num">{rank_label}</div>
    </div>
    <div style="flex:1;min-width:0;">
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:3px;">
        <span class="cname">{name}</span>
        {badges}
      </div>
      <div class="cmeta">{meta_str}</div>
      {signals_html}
    </div>
    <div style="min-width:64px;text-align:right;">
      <div class="score-big" style="color:{bar_color};">{r['final_score']:.4f}</div>
      <div style="color:#64748b;font-size:.72rem;margin-top:2px;">Score</div>
    </div>
  </div>
</div>
"""
        st.markdown(card_html, unsafe_allow_html=True)

        # Expandable breakdown
        with st.expander(f"📋 Why #{rank}? — Full scoring breakdown"):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Signal Breakdown**")
                sigs = [
                    ("🎯 Skill Match",    r["skill_score"],          "#6366f1"),
                    ("📅 Experience",     r["experience_score"],     "#22c55e"),
                    ("🎓 Education",      r["education_score"],      "#f59e0b"),
                    ("📋 Completeness",   r["completeness_score"],   "#94a3b8"),
                    ("📜 Certifications", r["certification_score"],  "#a78bfa"),
                    ("🔍 Keywords",       r["keyword_score"],        "#64748b"),
                ]
                for sig_label, sig_val, sig_col in sigs:
                    filled = int(sig_val * 20)
                    bar_s  = "█" * filled + "░" * (20 - filled)
                    st.markdown(
                        f'{sig_label}: <code style="color:{sig_col}">{bar_s}</code> '
                        f'`{sig_val:.3f}`',
                        unsafe_allow_html=True,
                    )
                if r["fresher_uplift"] > 1.0:
                    st.success(f"🚀 Fresher Boost applied: ×{r['fresher_uplift']:.3f}")

            with col_b:
                st.markdown("**Reasoning**")
                for chunk in r.get("reasoning", "").split(" || "):
                    if ":" in chunk:
                        tag, _, detail = chunk.partition(": ")
                        st.markdown(f"**{tag}**: {detail}")

    # ── DOWNLOAD ──────────────────────────────────────────────────
    st.markdown("<hr class='sdiv'>", unsafe_allow_html=True)
    st.markdown("### 💾 Download Results")

    rows = [{
        "rank": r["rank"], "candidate_id": r["candidate_id"],
        "name": r.get("name",""), "title": r.get("title",""),
        "company": r.get("company",""), "location": r.get("location",""),
        "yoe": r.get("yoe",""), "is_fresher": r["is_fresher"],
        "final_score": r["final_score"],
        "skill_score": r["skill_score"], "experience_score": r["experience_score"],
        "education_score": r["education_score"], "completeness_score": r["completeness_score"],
        "certification_score": r["certification_score"], "keyword_score": r["keyword_score"],
        "fresher_uplift": r["fresher_uplift"],
        "skill_match_detail": r["skill_match_detail"],
        "experience_detail": r["experience_detail"],
        "education_detail": r["education_detail"],
        "certification_detail": r["certification_detail"],
        "reasoning": r["reasoning"],
    } for r in ranked]

    df_exp = pd.DataFrame(rows)
    dc1, dc2, _ = st.columns([1, 1, 2])
    with dc1:
        st.download_button("⬇️ Download CSV",
            df_exp.to_csv(index=False).encode(),
            "ranked_candidates.csv", "text/csv",
            use_container_width=True)
    with dc2:
        st.download_button("⬇️ Download JSON",
            json.dumps(rows, indent=2, default=str).encode(),
            "ranked_candidates.json", "application/json",
            use_container_width=True)

    with st.expander("📊 View as Table"):
        st.dataframe(df_exp[[
            "rank","name","title","company","yoe","is_fresher",
            "final_score","skill_score","experience_score","education_score",
        ]].rename(columns={
            "rank":"Rank","name":"Name","title":"Title","company":"Company",
            "yoe":"YoE","is_fresher":"Fresher?","final_score":"Score",
            "skill_score":"Skill","experience_score":"Exp","education_score":"Edu",
        }), hide_index=True, use_container_width=True)

elif run_btn and not has_file:
    st.warning("⚠️ Please upload a file or paste a file path first.")
elif run_btn and not jd_text.strip():
    st.warning("⚠️ Please enter a job description before ranking.")
else:
    # ── GETTING STARTED ───────────────────────────────────────────
    st.markdown("<hr class='sdiv'>", unsafe_allow_html=True)
    st.markdown("### 👋 Getting Started")
    ga, gb = st.columns(2)
    with ga:
        st.markdown("**Sample Google Forms CSV columns:**")
        st.dataframe(pd.DataFrame({
            "Your Name":             ["Priya Sharma",  "Rahul Mehta"],
            "Years of Experience":   ["0",             "5"],
            "Technical Skills":      ["Python, PyTorch, NLP", "Python, FAISS, MLOps"],
            "College / University":  ["IIT Bombay",    "NIT Trichy"],
            "CGPA / Percentage":     ["9.2 CGPA",      "75%"],
            "Certifications":        ["DeepLearning.AI", "AWS ML Specialty"],
            "GitHub Profile":        ["github.com/ps", "github.com/rm"],
        }), hide_index=True, use_container_width=True)

    with gb:
        st.markdown("**What you'll get per candidate:**")
        st.markdown("""
- 🏆 **Final rank** (1–N) with composite score
- 🎯 **Skill match %** — which JD skills were found
- 📅 **Experience score** — YoE curve with fresher boost
- 🎓 **Education score** — institution tier + GPA
- 📜 **Certification score** — ML upskilling signals
- 📋 **Full reasoning** — every score explained in plain text
- 💾 **Downloadable** CSV + JSON output
""")
        st.info("The system auto-detects column names — no manual mapping needed.", icon="✨")
