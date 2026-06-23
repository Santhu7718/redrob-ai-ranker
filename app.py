"""
app.py — ICD (Intelligent Candidate Discovery AI)
Streamlit Cloud deployment of the full beautiful ICD site.
Same CSS, same design — but upload & ranking handled via Python.
"""
import streamlit as st
import os, json, time, io, html as _html
import pandas as pd
from pathlib import Path

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ICD — Intelligent Candidate Discovery AI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Read assets ───────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
WEB  = BASE / "web"
CSS  = (WEB / "styles.css").read_text(encoding="utf-8") if (WEB / "styles.css").exists() else ""

# ── Inject CSS + kill all Streamlit chrome ────────────────────────────────────
st.markdown(f"""
<style>
{CSS}

/* ═══ Hide every piece of Streamlit's default UI ═══ */
#MainMenu, footer,
header[data-testid="stHeader"],
.stDeployButton,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stAppViewBlockContainer"] > div:first-child {{ display: none !important; }}
section[data-testid="stSidebar"] {{ display: none !important; }}

/* ═══ Remove all Streamlit padding ═══ */
.block-container,
.stMainBlockContainer,
.stMain > div {{ padding: 0 !important; max-width: 100% !important; margin: 0 !important; }}

/* ═══ Style Streamlit file uploader to match drop zone ═══ */
[data-testid="stFileUploaderDropzone"] {{
    min-height: 140px;
    background: rgba(255,255,255,0.02) !important;
    border: 2px dashed rgba(255,255,255,0.10) !important;
    border-radius: 16px !important;
    transition: border-color 0.2s, background 0.2s !important;
}}
[data-testid="stFileUploaderDropzone"]:hover {{
    border-color: rgba(244,63,94,0.35) !important;
    background: rgba(244,63,94,0.04) !important;
}}
[data-testid="stFileUploaderDropzone"] p,
[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] small {{
    color: var(--color-neutral-400) !important;
    font-family: 'Inter', sans-serif !important;
}}
div[data-testid="stFileUploader"] section {{
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}}
/* ═══ Style primary button ═══ */
.stButton > button[kind="primary"],
.stButton > button {{
    background: linear-gradient(135deg, #f43f5e, #be123c) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 14px 32px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
    transition: all 0.2s !important;
    width: 100%;
    min-height: 52px;
}}
.stButton > button:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(244,63,94,0.35) !important;
    background: linear-gradient(135deg, #fb5370, #e11d48) !important;
}}
/* ═══ Style spinner ═══ */
.stSpinner > div {{ border-top-color: #f43f5e !important; }}
/* ═══ Style text area ═══ */
.stTextArea textarea {{
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: 12px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
}}
.stTextArea textarea:focus {{
    border-color: rgba(244,63,94,0.4) !important;
    box-shadow: 0 0 0 3px rgba(244,63,94,0.08) !important;
}}
/* ═══ Style alerts ═══ */
[data-testid="stAlert"] {{
    border-radius: 12px !important;
    font-family: 'Inter', sans-serif !important;
}}
/* ═══ Upload section container ═══ */
.upload-streamlit-wrap {{
    max-width: 860px;
    margin: 0 auto;
    padding: 0 24px 48px;
}}
.upload-streamlit-wrap .section-badge {{
    margin-bottom: 12px;
}}
.jd-streamlit {{
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
}}
.jd-streamlit label {{
    color: var(--color-neutral-300) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.875rem !important;
    font-weight: 600 !important;
}}
/* result card */
.r-card {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 12px;
    font-family: 'Inter', sans-serif;
    transition: border-color 0.2s;
}}
.r-card:hover {{ border-color: rgba(244,63,94,0.25); }}
.r-card.top3 {{ border-color: rgba(234,179,8,0.3); background: rgba(234,179,8,0.04); }}
.r-card.fresh {{ border-color: rgba(34,197,94,0.28); background: rgba(34,197,94,0.04); }}
.r-rank {{ font-size: 1.6rem; min-width: 48px; text-align: center; }}
.r-name {{ font-size: 1.05rem; font-weight: 700; color: #e2e8f0; }}
.r-meta {{ font-size: 0.85rem; color: #94a3b8; margin-top: 3px; }}
.r-score {{ font-size: 1.15rem; font-weight: 800; text-align: right; }}
.r-score-sub {{ font-size: 0.72rem; color: #64748b; margin-top: 2px; text-align: right; }}
.r-badge {{
    display: inline-block; padding: 2px 9px; border-radius: 20px;
    font-size: 0.70rem; font-weight: 700; letter-spacing: 0.04em;
    text-transform: uppercase; margin-right: 5px;
}}
.b-fresh {{ background: rgba(34,197,94,.15); color: #4ade80; border: 1px solid rgba(34,197,94,.3); }}
.b-top   {{ background: rgba(234,179,8,.15); color: #fbbf24; border: 1px solid rgba(234,179,8,.3); }}
.b-boost {{ background: rgba(99,102,241,.15); color: #a78bfa; border: 1px solid rgba(99,102,241,.3); }}
.mini-bar-wrap {{ display: flex; align-items: center; gap: 8px; margin: 2px 0; }}
.mini-bar-label {{ color: #64748b; font-size: 0.75rem; min-width: 60px; }}
.mini-bar-bg {{ flex: 1; background: rgba(255,255,255,0.06); border-radius: 4px; height: 5px; overflow: hidden; }}
.mini-bar-fill {{ height: 5px; border-radius: 4px; }}
.mini-bar-val {{ color: #94a3b8; font-size: 0.72rem; min-width: 36px; text-align: right; }}
.sum-grid {{
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 16px; margin: 0 0 28px;
}}
.sum-card {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px; padding: 20px 16px; text-align: center;
}}
.sum-val {{ font-size: 1.8rem; font-weight: 800; color: #f43f5e; font-family: 'Inter', sans-serif; }}
.sum-label {{ font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 4px; }}
@media (max-width: 640px) {{ .sum-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  NAVBAR
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<nav class="navbar" id="navbar" role="navigation" aria-label="Main navigation">
  <div class="nav-container">
    <a href="#" class="nav-logo" aria-label="ICD — Home">
      <div class="logo-mark" aria-hidden="true"><span class="logo-r">ICD</span></div>
      <span class="logo-text">Intelligent <span class="logo-accent">Candidate Discovery AI</span></span>
    </a>
    <ul class="nav-links" role="list">
      <li><a href="#upload-score" class="nav-link">⚡ Upload &amp; Score</a></li>
      <li><a href="#how-it-works" class="nav-link">How it Works</a></li>
      <li><a href="#scoring-engine" class="nav-link">Scoring Engine</a></li>
      <li><a href="#results" class="nav-link">Results</a></li>
    </ul>
  </div>
</nav>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  HERO
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<section class="section hero-section" id="hero">
  <div class="container hero-container">
    <div class="hero-eyebrow">
      <span class="hero-badge">● RedRob India Runs Data &amp; AI Challenge</span>
    </div>
    <h1 class="hero-heading">
      Rank Candidates<br/>
      <span class="hero-heading-accent">Like a Great Recruiter</span>
    </h1>
    <p class="hero-subheading">
      A <strong>no-API, fully local</strong> multi-signal candidate ranking engine.
      Scores 90,000+ profiles using endorsement trust, career trajectory,
      behavioral signals &amp; anti-gaming intelligence — zero network calls.
    </p>
    <div class="hero-cta-group" role="group">
      <a href="#upload-score" class="btn btn-primary btn-lg">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        Run the Ranker
      </a>
      <a href="#scoring-engine" class="btn btn-ghost btn-lg">
        Explore Scoring Engine
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
      </a>
    </div>
    <div class="hero-stats" role="list" aria-label="Key statistics">
      <div class="hero-stat" role="listitem">
        <span class="hero-stat-num">89.8K</span>
        <span class="hero-stat-label">CANDIDATES RANKED</span>
      </div>
      <div class="hero-stat-divider" aria-hidden="true"></div>
      <div class="hero-stat" role="listitem">
        <span class="hero-stat-num">6</span>
        <span class="hero-stat-label">SIGNAL DIMENSIONS</span>
      </div>
      <div class="hero-stat-divider" aria-hidden="true"></div>
      <div class="hero-stat" role="listitem">
        <span class="hero-stat-num">0</span>
        <span class="hero-stat-label">API CALLS MADE</span>
      </div>
      <div class="hero-stat-divider" aria-hidden="true"></div>
      <div class="hero-stat" role="listitem">
        <span class="hero-stat-num">~5<span style="font-size:1.2rem">min</span></span>
        <span class="hero-stat-label">FULL RANKING TIME</span>
      </div>
    </div>
  </div>
</section>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  UPLOAD & SCORE  (Interactive — Streamlit widgets)
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<section class="section" id="upload-score">
  <div class="container">
    <div class="section-header">
      <div class="section-badge">⚡ Interactive</div>
      <h2 class="section-heading">Upload &amp; Score Candidates</h2>
      <p class="section-subheading">
        Upload your candidates file in <strong>any format</strong> and rank them
        against the job description — all in-browser, no backend needed.
      </p>
      <div class="format-pills" role="list" aria-label="Supported formats">
        <span class="format-pill format-pill--jsonl" role="listitem"><span class="fp-ext">.jsonl</span><span class="fp-label">Primary</span></span>
        <span class="format-pill format-pill--json"  role="listitem"><span class="fp-ext">.json</span><span class="fp-label">JSON</span></span>
        <span class="format-pill format-pill--csv"   role="listitem"><span class="fp-ext">.csv</span><span class="fp-label">CSV</span></span>
        <span class="format-pill format-pill--xlsx"  role="listitem"><span class="fp-ext">.xlsx</span><span class="fp-label">Excel</span></span>
        <span class="format-pill format-pill--txt"   role="listitem"><span class="fp-ext">.txt</span><span class="fp-label">Text</span></span>
      </div>
    </div>
  </div>
</section>
""", unsafe_allow_html=True)

# ── Streamlit upload widgets ──────────────────────────────────────────────────
with st.container():
    st.markdown('<div class="upload-streamlit-wrap">', unsafe_allow_html=True)

    col_file, col_jd = st.columns([1, 1], gap="large")

    with col_file:
        st.markdown("#### 📂 Candidate File")
        uploaded = st.file_uploader(
            "Drop your file here",
            type=["csv", "xlsx", "xls", "json", "jsonl", "txt"],
            label_visibility="collapsed",
            help="Supports CSV, Excel, JSON, JSONL, TXT — columns auto-mapped",
        )
        if uploaded:
            size_mb = uploaded.size / 1024 / 1024
            st.success(f"✅ **{uploaded.name}** — {size_mb:.1f} MB loaded")

    with col_jd:
        st.markdown("#### 📝 Job Description")
        DEFAULT_JD = """Software / AI Engineer — RedRob Tech

Core Skills Required:
- Python, Machine Learning, Deep Learning
- PyTorch or TensorFlow, scikit-learn
- NLP, Computer Vision, LLMs
- REST APIs, SQL, Git

Preferred:
- MLOps: Docker, Kubernetes, CI/CD
- Data: Pandas, NumPy, Spark
- Cloud: AWS / GCP / Azure
- System design, distributed systems

Experience: 0–10 years (freshers welcome)
Location: Bangalore · Mumbai · Hyderabad · Remote"""
        jd_text = st.text_area(
            "Job Description",
            value=DEFAULT_JD,
            height=240,
            label_visibility="collapsed",
            placeholder="Paste your job description here…",
        )

    # ── Run button ───────────────────────────────────────────────────────────
    st.markdown("<br/>", unsafe_allow_html=True)
    run_col, _ = st.columns([1, 3])
    with run_col:
        run_btn = st.button("▶ Start Ranking", type="primary", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ── Ranking logic ─────────────────────────────────────────────────────────────
if run_btn:
    if not uploaded:
        st.warning("⚠️ Please upload a candidates file first.")
    elif not jd_text.strip():
        st.warning("⚠️ Please enter a job description.")
    else:
        with st.spinner("⚡ Parsing candidates and running multi-signal scoring…"):
            t0 = time.perf_counter()
            try:
                from universal_parser import parse_any_format
                from universal_scorer import rank_candidates, _extract_skills_from_jd

                raw = uploaded.read()
                candidates = parse_any_format(raw, uploaded.name)

                if not candidates:
                    st.error("❌ Could not parse file. Check the format and try again.")
                    st.stop()

                ranked, jd_skills = rank_candidates(candidates, jd_text)
                elapsed = time.perf_counter() - t0

            except Exception as e:
                st.error(f"❌ Ranking failed: {e}")
                st.stop()

        # ── Summary cards ────────────────────────────────────────────────────
        freshers = sum(1 for r in ranked if r.get("is_fresher"))
        avg_score = sum(r["final_score"] for r in ranked) / max(1, len(ranked))

        st.markdown(f"""
<div class="upload-streamlit-wrap" style="padding-top:0">
  <h2 class="section-heading" style="margin-bottom:20px">🏆 Ranking Complete</h2>
  <div class="sum-grid">
    <div class="sum-card"><div class="sum-val">{len(candidates):,}</div><div class="sum-label">Total Candidates</div></div>
    <div class="sum-card"><div class="sum-val">{len(ranked)}</div><div class="sum-label">Top Ranked</div></div>
    <div class="sum-card"><div class="sum-val">{freshers}</div><div class="sum-label">Freshers in Top {len(ranked)}</div></div>
    <div class="sum-card"><div class="sum-val">{avg_score:.3f}</div><div class="sum-label">Avg Score</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ── JD skills found ──────────────────────────────────────────────────
        if jd_skills:
            with st.expander(f"🔍 {len(jd_skills)} skills extracted from Job Description", expanded=False):
                chips = "".join(
                    f'<span style="display:inline-block;background:rgba(99,102,241,.12);color:#a78bfa;'
                    f'border:1px solid rgba(99,102,241,.22);border-radius:16px;padding:3px 10px;'
                    f'font-size:.76rem;font-family:Inter,sans-serif;margin:3px;">{s}</span>'
                    for s in jd_skills[:60]
                )
                st.markdown(chips, unsafe_allow_html=True)

        # ── Results table ────────────────────────────────────────────────────
        RANK_EMOJI = {1: "🥇", 2: "🥈", 3: "🥉"}

        def score_color(s):
            if s >= 0.75: return "#4ade80"
            if s >= 0.55: return "#a78bfa"
            if s >= 0.35: return "#fbbf24"
            return "#f87171"

        st.markdown('<div class="upload-streamlit-wrap" style="padding-top:0">', unsafe_allow_html=True)

        for r in ranked:
            rank     = r["rank"]
            is_fresh = r.get("is_fresher", False)
            score    = r["final_score"]
            sc       = score_color(score)
            card_cls = "top3" if rank <= 3 else ("fresh" if is_fresh else "")
            rlabel   = RANK_EMOJI.get(rank, f"#{rank}")

            badges = ""
            if rank <= 3:  badges += '<span class="r-badge b-top">⭐ Top 3</span>'
            if is_fresh:   badges += '<span class="r-badge b-fresh">🌱 Fresher</span>'
            if r.get("fresher_uplift", 1) > 1.0:
                badges += f'<span class="r-badge b-boost">×{r["fresher_uplift"]:.2f} Boost</span>'

            name    = _html.escape(str(r.get("name") or r.get("candidate_id", "—")))
            title   = _html.escape(str(r.get("title", "")))
            company = _html.escape(str(r.get("company", "")))
            yoe_v   = r.get("yoe", "")
            meta_parts = []
            if title:   meta_parts.append(title)
            if company: meta_parts.append(f"@ {company}")
            if yoe_v not in ("", None, "None"): meta_parts.append(f"• {yoe_v} YoE")
            meta = "  ".join(meta_parts) or "—"

            # Mini signal bars
            bars_html = ""
            for label, key, color in [
                ("Skill",  "skill_score",          "#f43f5e"),
                ("Exp",    "experience_score",      "#4ade80"),
                ("Edu",    "education_score",       "#fbbf24"),
                ("Certs",  "certification_score",   "#a78bfa"),
            ]:
                sv = r.get(key, 0) or 0
                bars_html += (
                    f'<div class="mini-bar-wrap">'
                    f'<span class="mini-bar-label">{label}</span>'
                    f'<div class="mini-bar-bg"><div class="mini-bar-fill" style="width:{sv*100:.0f}%;background:{color}"></div></div>'
                    f'<span class="mini-bar-val">{sv:.2f}</span>'
                    f'</div>'
                )

            st.markdown(f"""
<div class="r-card {card_cls}">
  <div style="display:flex;gap:16px;align-items:flex-start;">
    <div class="r-rank">{rlabel}</div>
    <div style="flex:1;min-width:0;">
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px;">
        <span class="r-name">{name}</span>{badges}
      </div>
      <div class="r-meta">{meta}</div>
      <div style="margin-top:10px;">{bars_html}</div>
    </div>
    <div style="min-width:70px;">
      <div class="r-score" style="color:{sc};">{score:.4f}</div>
      <div class="r-score-sub">Score</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            # Reasoning expander
            reasoning = r.get("reasoning", "")
            if reasoning:
                with st.expander(f"📋 Why #{rank}? — Full breakdown"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**Signal scores**")
                        for sig_lbl, sig_key, sig_col in [
                            ("🎯 Skill",      "skill_score",          "#f43f5e"),
                            ("📅 Experience", "experience_score",     "#4ade80"),
                            ("🎓 Education",  "education_score",      "#fbbf24"),
                            ("📋 Complete",   "completeness_score",   "#94a3b8"),
                            ("📜 Certs",      "certification_score",  "#a78bfa"),
                            ("🔍 Keywords",   "keyword_score",        "#64748b"),
                        ]:
                            sv = r.get(sig_key, 0) or 0
                            filled = int(sv * 20)
                            bar = "█" * filled + "░" * (20 - filled)
                            st.markdown(
                                f'{sig_lbl}: <code style="color:{sig_col}">{bar}</code> `{sv:.3f}`',
                                unsafe_allow_html=True,
                            )
                        if r.get("fresher_uplift", 1) > 1.0:
                            st.success(f"🚀 Fresher boost: ×{r['fresher_uplift']:.3f}")
                    with col_b:
                        st.markdown("**Reasoning**")
                        for chunk in reasoning.split(" || "):
                            if ":" in chunk:
                                tag, _, detail = chunk.partition(": ")
                                st.markdown(f"**{tag}**: {detail}")

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Download ─────────────────────────────────────────────────────────
        rows = [{
            "rank": r["rank"], "candidate_id": r.get("candidate_id", ""),
            "name": r.get("name", ""), "title": r.get("title", ""),
            "company": r.get("company", ""), "yoe": r.get("yoe", ""),
            "is_fresher": r.get("is_fresher", False),
            "final_score": r["final_score"],
            "skill_score": r.get("skill_score", 0),
            "experience_score": r.get("experience_score", 0),
            "education_score": r.get("education_score", 0),
            "certification_score": r.get("certification_score", 0),
            "fresher_uplift": r.get("fresher_uplift", 1),
            "reasoning": r.get("reasoning", ""),
        } for r in ranked]

        df_out = pd.DataFrame(rows)
        st.markdown('<div class="upload-streamlit-wrap" style="padding-top:0">', unsafe_allow_html=True)
        st.markdown(f"### 💾 Download Results &nbsp; <span style='color:#64748b;font-size:.875rem'>({len(ranked)} candidates · {elapsed:.1f}s)</span>", unsafe_allow_html=True)
        dl1, dl2, _ = st.columns([1, 1, 2])
        with dl1:
            st.download_button(
                "⬇️ Download CSV", df_out.to_csv(index=False).encode(),
                "ranked_candidates.csv", "text/csv", use_container_width=True,
            )
        with dl2:
            st.download_button(
                "⬇️ Download JSON", json.dumps(rows, indent=2, default=str).encode(),
                "ranked_candidates.json", "application/json", use_container_width=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  HOW IT WORKS
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<section class="section" id="how-it-works" style="padding-top:80px">
  <div class="container">
    <div class="section-header">
      <div class="section-badge">How It Works</div>
      <h2 class="section-heading" id="hiw-heading">From 90K Profiles to Top 100</h2>
      <p class="section-subheading">
        A four-stage pipeline that reasons about candidates the way a seasoned
        technical recruiter would — understanding context, not just matching keywords.
      </p>
    </div>
    <div class="pipeline-flow" role="list" aria-label="Processing pipeline">
      <div class="pipeline-step" role="listitem" data-step="1">
        <div class="pipeline-step-icon" aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        </div>
        <div class="pipeline-step-num" aria-hidden="true">01</div>
        <h3 class="pipeline-step-title">Load Candidates</h3>
        <p class="pipeline-step-desc">89,788 candidate profiles streamed from JSONL — no batching bottlenecks, no memory spikes.</p>
        <div class="pipeline-step-meta">
          <span class="meta-tag">JSONL streaming</span><span class="meta-tag">~418 MB</span>
        </div>
      </div>
      <div class="pipeline-arrow" aria-hidden="true">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
      </div>
      <div class="pipeline-step" role="listitem" data-step="2">
        <div class="pipeline-step-icon" aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        </div>
        <div class="pipeline-step-num" aria-hidden="true">02</div>
        <h3 class="pipeline-step-title">Parse Job Description</h3>
        <p class="pipeline-step-desc">JD is parsed into structured skill ontology — 55+ critical terms, role tiers, and scoring weights.</p>
        <div class="pipeline-step-meta">
          <span class="meta-tag">jd_parser.py</span><span class="meta-tag">55 core skills</span>
        </div>
      </div>
      <div class="pipeline-arrow" aria-hidden="true">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
      </div>
      <div class="pipeline-step" role="listitem" data-step="3">
        <div class="pipeline-step-icon" aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        </div>
        <div class="pipeline-step-num" aria-hidden="true">03</div>
        <h3 class="pipeline-step-title">Multi-Signal Scoring</h3>
        <p class="pipeline-step-desc">6 independent scorers run in parallel. Each uses trust-weighted signals — endorsements, duration, career text.</p>
        <div class="pipeline-step-meta">
          <span class="meta-tag">scorer.py</span><span class="meta-tag">~1000 c/s</span>
        </div>
      </div>
      <div class="pipeline-arrow" aria-hidden="true">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
      </div>
      <div class="pipeline-step" role="listitem" data-step="4">
        <div class="pipeline-step-icon" aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        </div>
        <div class="pipeline-step-num" aria-hidden="true">04</div>
        <h3 class="pipeline-step-title">Dual-Track Ranking</h3>
        <p class="pipeline-step-desc">Top 70 experienced + 30 fresher quota merged by score. Final 100 sorted ensuring freshers surface.</p>
        <div class="pipeline-step-meta">
          <span class="meta-tag">Top 100 output</span><span class="meta-tag">submission.csv</span>
        </div>
      </div>
    </div>
  </div>
</section>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  SCORING ENGINE
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<section class="section" id="scoring-engine" style="padding-top:80px">
  <div class="container">
    <div class="section-header">
      <div class="section-badge">Scoring Engine</div>
      <h2 class="section-heading">6 Dimensions of Candidate Intelligence</h2>
      <p class="section-subheading">
        Every candidate is evaluated across six orthogonal signals. No single
        dimension dominates — it takes depth across the board to rank highly.
      </p>
    </div>
    <div class="scoring-grid" role="list" aria-label="Scoring dimensions">

      <article class="score-card score-card--primary" role="listitem">
        <div class="score-card-header">
          <div class="score-icon skill-icon" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
          </div>
          <div class="score-weight"><span class="weight-num">30</span><span class="weight-pct">%</span></div>
        </div>
        <h3 class="score-card-title">Skill Match</h3>
        <p class="score-card-desc">Not keyword presence — <em>trust-weighted</em> skill quality. Endorsements, usage duration, and platform assessment scores all factor in. Keyword stuffers are actively penalized.</p>
        <div class="trust-formula">
          <div class="formula-label">Trust Score Formula</div>
          <code class="formula-code">0.5×proficiency + 0.3×endorsements/20 + 0.2×months/12 + assessment_bonus</code>
        </div>
      </article>

      <article class="score-card" role="listitem">
        <div class="score-card-header">
          <div class="score-icon career-icon" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
          </div>
          <div class="score-weight"><span class="weight-num">20</span><span class="weight-pct">%</span></div>
        </div>
        <h3 class="score-card-title">Career Signal</h3>
        <p class="score-card-desc">Title relevance tiers, product vs. services company detection, ML work density in job descriptions. Marketing Manager listing ML skills? Flagged and down-ranked.</p>
        <div class="score-signals">
          <span class="signal-chip">Title tier mapping</span>
          <span class="signal-chip">Product co. detection</span>
          <span class="signal-chip">ML density</span>
        </div>
      </article>

      <article class="score-card" role="listitem">
        <div class="score-card-header">
          <div class="score-icon exp-icon" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          </div>
          <div class="score-weight"><span class="weight-num">18</span><span class="weight-pct">%</span></div>
        </div>
        <h3 class="score-card-title">Experience Fit</h3>
        <p class="score-card-desc">Fresher-skewed curve — 0 YoE starts at 0.65 base. Certifications, GitHub activity &amp; platform assessments can boost freshers up to 0.50 additional points.</p>
        <div class="yoe-table" role="table">
          <div class="yoe-row yoe-header" role="row"><span role="columnheader">YoE</span><span role="columnheader">Score</span><span role="columnheader">Note</span></div>
          <div class="yoe-row" role="row"><span role="cell">0</span><span role="cell" class="yoe-score">0.65</span><span role="cell" class="yoe-note">Fresher boost</span></div>
          <div class="yoe-row" role="row"><span role="cell">≤2</span><span role="cell" class="yoe-score">0.72</span><span role="cell" class="yoe-note">Junior</span></div>
          <div class="yoe-row" role="row"><span role="cell">5–6</span><span role="cell" class="yoe-score yoe-ideal">0.80</span><span role="cell" class="yoe-note yoe-ideal">Sweet spot</span></div>
          <div class="yoe-row" role="row"><span role="cell">10+</span><span role="cell" class="yoe-score yoe-warn">0.65</span><span role="cell" class="yoe-note yoe-warn">Over-exp penalty</span></div>
        </div>
      </article>

      <article class="score-card" role="listitem">
        <div class="score-card-header">
          <div class="score-icon edu-icon" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
          </div>
          <div class="score-weight"><span class="weight-num">12</span><span class="weight-pct">%</span></div>
        </div>
        <h3 class="score-card-title">Education Quality</h3>
        <p class="score-card-desc">Institution tier (IIT/NIT → 0.95), field relevance (CS/ECE/Stats), degree level, and parsed GPA/CGPA. Critical potential proxy for freshers.</p>
        <div class="score-signals">
          <span class="signal-chip">Institution tier</span>
          <span class="signal-chip">Field relevance</span>
          <span class="signal-chip">GPA parsed</span>
        </div>
      </article>

      <article class="score-card" role="listitem">
        <div class="score-card-header">
          <div class="score-icon behav-icon" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 13a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91A16 16 0 0 0 14 15.82l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
          </div>
          <div class="score-weight"><span class="weight-num">15</span><span class="weight-pct">%</span></div>
        </div>
        <h3 class="score-card-title">Behavioral Signals</h3>
        <p class="score-card-desc">Active engagement, open-to-work flag, and recruiter response rate are critical multipliers. A perfect-on-paper candidate inactive for 6 months is not actually hirable.</p>
        <div class="score-signals">
          <span class="signal-chip">Open to work</span>
          <span class="signal-chip">Last active date</span>
          <span class="signal-chip">Response rate</span>
        </div>
      </article>

      <article class="score-card score-card--penalty" role="listitem">
        <div class="score-card-header">
          <div class="score-icon penalty-icon" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          </div>
          <div class="score-weight penalty-weight"><span class="weight-num">×</span><span class="weight-pct">penalty</span></div>
        </div>
        <h3 class="score-card-title">Anti-Gaming Shield</h3>
        <p class="score-card-desc">Applied as a multiplier (0–1.0) on the final score. Catches keyword stuffers, title-chasers, ghost profiles, and pure services careers with no real AI work.</p>
        <div class="penalty-table" role="table">
          <div class="penalty-row" role="row">
            <span class="penalty-pattern" role="cell">15+ skills, avg &lt;3 endorsements</span>
            <span class="penalty-value" role="cell">×0.70</span>
          </div>
          <div class="penalty-row" role="row">
            <span class="penalty-pattern" role="cell">Title ≠ skills (e.g. HR listing ML)</span>
            <span class="penalty-value" role="cell">×0.60</span>
          </div>
          <div class="penalty-row" role="row">
            <span class="penalty-pattern" role="cell">Ghost profile (&lt;3 connections)</span>
            <span class="penalty-value" role="cell">×0.50</span>
          </div>
        </div>
      </article>

    </div>

    <!-- Weight bar -->
    <div class="weight-bar-container" style="margin-top:40px">
      <h3 class="weight-bar-title">Score Weight Distribution</h3>
      <div class="weight-bar" role="img" aria-label="Score weights">
        <div class="weight-segment seg-skill" style="width:30%"><span>Skill 30%</span></div>
        <div class="weight-segment seg-career" style="width:20%"><span>Career 20%</span></div>
        <div class="weight-segment seg-exp" style="width:18%"><span>Exp 18%</span></div>
        <div class="weight-segment seg-behav" style="width:15%"><span>Behav 15%</span></div>
        <div class="weight-segment seg-edu" style="width:12%"><span>Edu 12%</span></div>
        <div class="weight-segment seg-loc" style="width:5%"><span>5%</span></div>
      </div>
      <div class="weight-bar-legend" aria-hidden="true">
        <span class="wbl-item"><span class="wbl-dot" style="background:#f43f5e"></span>Skill</span>
        <span class="wbl-item"><span class="wbl-dot" style="background:#8b5cf6"></span>Career</span>
        <span class="wbl-item"><span class="wbl-dot" style="background:#10b981"></span>Experience</span>
        <span class="wbl-item"><span class="wbl-dot" style="background:#0ea5e9"></span>Behavioral</span>
        <span class="wbl-item"><span class="wbl-dot" style="background:#d97706"></span>Education</span>
        <span class="wbl-item"><span class="wbl-dot" style="background:#6b7280"></span>Location</span>
      </div>
    </div>
  </div>
</section>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  WHAT THE RANKING REWARDS
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<section class="section" id="results" style="padding-top:80px">
  <div class="container">
    <div class="section-header">
      <div class="section-badge">Results</div>
      <h2 class="section-heading">What the Ranking Rewards</h2>
      <p class="section-subheading">The system is designed to surface genuinely strong candidates — not profile optimizers.</p>
    </div>
    <div class="results-split">
      <div class="results-col" aria-labelledby="rewards-heading">
        <div class="results-col-header">
          <div class="results-col-icon" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
          <h3 class="results-col-title" id="rewards-heading">Ranks Highly</h3>
        </div>
        <ul class="results-list">
          <li class="results-item results-item--good"><span class="ri-icon">🌱</span><div><strong>Fresher with IIT/NIT degree + GitHub + 3 ML certifications</strong><span class="ri-desc">Even with 0 YoE — signals competence, initiative, hiring potential</span></div></li>
          <li class="results-item results-item--good"><span class="ri-icon">💼</span><div><strong>3–6 YoE ML Engineer at product company (Zepto, CRED)</strong><span class="ri-desc">Real AI work, high endorsements on verified skills, active on platform</span></div></li>
          <li class="results-item results-item--good"><span class="ri-icon">🎯</span><div><strong>Candidate with 8/10 required skills, 15+ endorsements each</strong><span class="ri-desc">Trust-weighted — verified by peers, not self-reported</span></div></li>
          <li class="results-item results-item--good"><span class="ri-icon">🚀</span><div><strong>Open-to-work, responded to recruiters in last 30 days</strong><span class="ri-desc">Behaviorally hirable — not just resume-hirable</span></div></li>
        </ul>
      </div>
      <div class="results-col results-col--bad" aria-labelledby="penalized-heading">
        <div class="results-col-header">
          <div class="results-col-icon results-col-icon--bad" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </div>
          <h3 class="results-col-title" id="penalized-heading">Down-Ranked</h3>
        </div>
        <ul class="results-list">
          <li class="results-item results-item--bad"><span class="ri-icon">🚩</span><div><strong>20 skills listed, avg 0.5 endorsements per skill</strong><span class="ri-desc">Anti-gaming penalty: ×0.70 multiplier on final score</span></div></li>
          <li class="results-item results-item--bad"><span class="ri-icon">🚩</span><div><strong>Marketing Manager who lists "PyTorch, TensorFlow, NLP"</strong><span class="ri-desc">Title-skill mismatch detector: ×0.60 career penalty</span></div></li>
          <li class="results-item results-item--bad"><span class="ri-icon">🚩</span><div><strong>12 YoE COBOL developer switching to ML</strong><span class="ri-desc">Over-experience curve + irrelevant career penalty</span></div></li>
          <li class="results-item results-item--bad"><span class="ri-icon">🚩</span><div><strong>Ghost profile: joined 3 years ago, 2 connections, no activity</strong><span class="ri-desc">Behavioral score near zero: ×0.50 on final</span></div></li>
        </ul>
      </div>
    </div>
  </div>
</section>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  FOOTER
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<footer class="footer" role="contentinfo" style="margin-top:80px">
  <div class="footer-content container">
    <div class="footer-brand">
      <div class="footer-logo">
        <div class="logo-mark" aria-hidden="true"><span class="logo-r">ICD</span></div>
        <span class="logo-text">Intelligent <span class="logo-accent">Candidate Discovery AI</span></span>
      </div>
      <p class="footer-tagline">No APIs. No cloud. No black boxes. Just math.</p>
    </div>
    <div class="footer-meta">
      <div class="footer-team">
        <span class="footer-team-label">Built by</span>
        <strong class="footer-team-name">Santhosh Kumar</strong>
        <span class="footer-team-role">ML Engineer · AI Engineer</span>
      </div>
      <div class="footer-challenge">
        <span class="footer-challenge-badge">RedRob India Runs Data &amp; AI Challenge</span>
      </div>
    </div>
  </div>
  <div class="footer-bottom">
    <p>© 2026 RedRob AI Ranker · Zero API calls · Zero cloud dependency</p>
  </div>
</footer>
""", unsafe_allow_html=True)
