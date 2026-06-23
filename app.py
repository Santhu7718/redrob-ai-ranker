"""
app.py — RedRob AI Candidate Ranker
Streamlit UI — fixed rendering, clean layout, no raw HTML leaks.
"""

import streamlit as st
import pandas as pd
import json
import io
import os
from universal_parser import parse_any_format
from universal_scorer import rank_candidates, _extract_skills_from_jd

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RedRob AI Candidate Ranker",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── GLOBAL CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

.stApp {
    background: linear-gradient(135deg,#0d0f1a 0%,#111827 60%,#0d0f1a 100%);
}

/* hero banner */
.hero {
    background: linear-gradient(135deg,rgba(99,102,241,.18),rgba(167,139,250,.10));
    border: 1px solid rgba(99,102,241,.25);
    border-radius: 20px;
    padding: 32px 36px 24px;
    margin-bottom: 24px;
}
.hero h1 {
    font-size: 2.4rem; font-weight: 800;
    background: linear-gradient(135deg,#e0e7ff,#a78bfa,#6366f1);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin: 0 0 8px;
}
.hero p { color:#94a3b8; font-size:1rem; margin:0; }

/* metric pill */
.pill-row { display:flex; gap:12px; flex-wrap:wrap; margin-top:16px; }
.pill {
    background:rgba(99,102,241,.12);
    border:1px solid rgba(99,102,241,.25);
    border-radius:30px;
    padding:6px 16px;
    font-size:.85rem; font-weight:600; color:#a78bfa;
}

/* candidate card */
.ccard {
    background:rgba(255,255,255,.03);
    border:1px solid rgba(255,255,255,.08);
    border-radius:14px;
    padding:16px 20px 12px;
    margin-bottom:10px;
    transition:border-color .2s,background .2s;
}
.ccard:hover { border-color:rgba(99,102,241,.35); background:rgba(99,102,241,.05); }
.ccard.gold   { border-color:rgba(234,179,8,.30); background:rgba(234,179,8,.04); }
.ccard.green  { border-color:rgba(34,197,94,.28); background:rgba(34,197,94,.04); }

.rank-num { font-size:1.55rem; line-height:1; }
.cname { font-size:1.05rem; font-weight:700; color:#e2e8f0; }
.cmeta { font-size:.88rem; color:#94a3b8; margin:3px 0 8px; }
.cbadge {
    display:inline-block; padding:2px 9px; border-radius:20px;
    font-size:.70rem; font-weight:700; letter-spacing:.04em;
    text-transform:uppercase; margin-right:5px;
}
.b-fresh { background:rgba(34,197,94,.15); color:#4ade80; border:1px solid rgba(34,197,94,.3); }
.b-top   { background:rgba(234,179,8,.15);  color:#fbbf24; border:1px solid rgba(234,179,8,.3); }
.b-boost { background:rgba(99,102,241,.15); color:#a78bfa; border:1px solid rgba(99,102,241,.3); }

/* progress bar row */
.pbar-row { display:flex; align-items:center; gap:8px; margin-bottom:4px; }
.pbar-label { color:#64748b; font-size:.75rem; min-width:72px; }
.pbar-bg {
    flex:1; background:rgba(255,255,255,.07);
    border-radius:5px; height:6px; overflow:hidden;
}
.pbar-fill { height:6px; border-radius:5px; }
.pbar-val { color:#94a3b8; font-size:.75rem; min-width:34px; text-align:right; }
.score-big { font-size:1.1rem; font-weight:800; text-align:right; }

/* skill chip */
.chip {
    display:inline-block; padding:3px 9px; border-radius:16px;
    font-size:.76rem; font-weight:500; margin:2px;
    background:rgba(99,102,241,.12); color:#a78bfa;
    border:1px solid rgba(99,102,241,.22);
}
.chip.matched { background:rgba(34,197,94,.12); color:#4ade80; border-color:rgba(34,197,94,.28); }

/* section divider */
.sdiv { border:none; border-top:1px solid rgba(255,255,255,.07); margin:18px 0; }

/* sidebar signal table */
.sig-row {
    display:flex; align-items:center; gap:8px;
    padding:5px 0; border-bottom:1px solid rgba(255,255,255,.05);
}
.sig-icon { font-size:1rem; min-width:22px; }
.sig-name { color:#e2e8f0; font-size:.82rem; font-weight:600; flex:1; }
.sig-wt {
    background:rgba(99,102,241,.18); color:#a78bfa;
    border-radius:10px; padding:1px 8px; font-size:.78rem; font-weight:700;
}
.sig-desc { color:#64748b; font-size:.76rem; margin-top:1px; }
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
            if os.path.isfile(_raw_path):
                size_mb = os.path.getsize(_raw_path) / 1024 / 1024
                st.success(f"✅ Ready: **{os.path.basename(_raw_path)}** — {size_mb:.1f} MB")
                local_path = _raw_path          # ← valid path confirmed
            else:
                st.error(f"❌ File not found:\n`{_raw_path}`\nCheck the path and try again.")
                local_path = None               # ← invalid, block ranking
        else:
            local_path = None                   # ← nothing typed, block ranking


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
    with st.spinner("⚙️ Parsing file and scoring candidates…"):

        if uploaded_file is not None:
            # ── browser upload path (small files) ──
            raw = uploaded_file.read()
            fname = uploaded_file.name
            candidates = parse_any_format(raw, fname)
            _has_progress = False

        else:
            # ── local file path (large files, read from disk) ──
            fname = os.path.basename(local_path)

            progress_bar = st.progress(0, text="📚 Reading file from disk…")
            _has_progress = True

            with open(local_path, "rb") as fh:
                raw = fh.read()

            progress_bar.progress(50, text="⚡ Parsing candidates…")
            candidates = parse_any_format(raw, fname)
            progress_bar.progress(80, text="🤖 Scoring candidates…")

        if not candidates:
            st.error("❌ Could not parse the file. Check the format and try again.")
            st.stop()

        ranked, jd_skills = rank_candidates(candidates, jd_text)
        if _has_progress:
            progress_bar.progress(100, text="✅ Done — ranked!")

    st.balloons()

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
        name     = r.get("name") or r.get("candidate_id", "—")
        title    = r.get("title", "")
        company  = r.get("company", "")
        location = r.get("location", "")
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
elif run_btn:
    st.warning("⚠️ Please enter a job description.")
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
