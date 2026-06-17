"""
app.py — RedRob AI Candidate Ranker
====================================
Streamlit UI for ranking candidates from ANY file format.

Run with:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import io
import re
from typing import List, Dict, Any

from universal_parser import parse_any_format
from universal_scorer import rank_candidates, _extract_skills_from_jd, _parse_yoe

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RedRob AI Candidate Ranker",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS — dark glassmorphism theme
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Import Inter font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* Base */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* Main background */
.stApp {
    background: linear-gradient(135deg, #0d0f1a 0%, #111827 50%, #0d0f1a 100%);
    min-height: 100vh;
}

/* Cards */
.metric-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 20px;
    text-align: center;
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
}
.metric-card:hover {
    border-color: rgba(99,102,241,0.4);
    background: rgba(99,102,241,0.08);
}
.metric-number {
    font-size: 2.4rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6366f1, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.metric-label {
    color: #94a3b8;
    font-size: 0.85rem;
    margin-top: 4px;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

/* Header */
.hero-header {
    background: linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(167,139,250,0.1) 100%);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 24px;
    padding: 40px;
    margin-bottom: 32px;
    backdrop-filter: blur(20px);
}
.hero-title {
    font-size: 2.8rem;
    font-weight: 800;
    background: linear-gradient(135deg, #e0e7ff, #a78bfa, #6366f1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    line-height: 1.2;
}
.hero-subtitle {
    color: #94a3b8;
    font-size: 1.1rem;
    margin-top: 12px;
    font-weight: 400;
}

/* Rank cards */
.rank-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 12px;
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
}
.rank-card:hover {
    border-color: rgba(99,102,241,0.35);
    background: rgba(99,102,241,0.05);
    transform: translateX(4px);
}
.rank-card.top-3 {
    border-color: rgba(234,179,8,0.3);
    background: rgba(234,179,8,0.04);
}
.rank-card.fresher {
    border-color: rgba(34,197,94,0.3);
    background: rgba(34,197,94,0.04);
}

/* Score bar */
.score-bar-bg {
    background: rgba(255,255,255,0.06);
    border-radius: 6px;
    height: 8px;
    overflow: hidden;
    margin-top: 8px;
}
.score-bar-fill {
    height: 8px;
    border-radius: 6px;
    background: linear-gradient(90deg, #6366f1, #a78bfa);
    transition: width 0.8s ease;
}
.score-bar-fill.top-3 {
    background: linear-gradient(90deg, #f59e0b, #fbbf24);
}
.score-bar-fill.fresher {
    background: linear-gradient(90deg, #22c55e, #4ade80);
}

/* Badge */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.badge-fresher {
    background: rgba(34,197,94,0.15);
    color: #4ade80;
    border: 1px solid rgba(34,197,94,0.3);
}
.badge-top { 
    background: rgba(234,179,8,0.15);
    color: #fbbf24;
    border: 1px solid rgba(234,179,8,0.3);
}
.badge-rank {
    background: rgba(99,102,241,0.15);
    color: #a78bfa;
    border: 1px solid rgba(99,102,241,0.3);
    min-width: 48px;
    text-align: center;
}

/* How it works box */
.how-it-works {
    background: rgba(99,102,241,0.06);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 16px;
    padding: 24px;
}

/* Signal bars */
.signal-row {
    display: flex;
    align-items: center;
    margin-bottom: 6px;
    gap: 12px;
}
.signal-label {
    color: #94a3b8;
    font-size: 0.78rem;
    min-width: 80px;
    font-weight: 500;
}
.signal-bar-bg {
    flex: 1;
    background: rgba(255,255,255,0.06);
    border-radius: 4px;
    height: 6px;
}

/* Upload zone */
.uploadedFile {
    border-radius: 12px !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: rgba(255,255,255,0.03) !important;
    border-radius: 10px !important;
}

/* Override Streamlit defaults */
.stTextArea textarea {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
}
.stButton button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    padding: 12px 28px !important;
    font-size: 1rem !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.02em;
}
.stButton button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(99,102,241,0.4) !important;
}

/* Info / warning boxes */
.stAlert {
    border-radius: 12px !important;
}

div[data-testid="metric-container"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 12px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — How It Works
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 How the Scoring Works")
    st.markdown("""
<div class="how-it-works">

**No ML model was trained.** This is a rule-based multi-signal scoring engine — pure Python math.

Here's exactly how each candidate gets their score:

---

**📊 6 Scoring Signals**

| Signal | Weight | What it measures |
|--------|--------|-----------------|
| 🎯 Skill Match | **35%** | JD skills found in candidate profile |
| 📅 Experience | **25%** | YoE curve — freshers boosted |
| 🎓 Education | **15%** | Institution tier + field + GPA |
| 📋 Completeness | **10%** | How filled-in the profile is |
| 📜 Certifications | **10%** | ML/AI upskilling evidence |
| 🔍 Keyword Density | **5%** | Implicit JD matches across full text |

---

**🚀 Fresher Boost**

Freshers (≤2 YoE) get up to **+30% bonus** for:
- GitHub activity
- Certifications
- Strong education tier
- High skill match

---

**🏗️ Dual-Track Ranking**

- **70% slots** → Best experienced candidates
- **30% slots** → Best freshers (guaranteed representation)
- Final list sorted by score

---

**⚠️ What it is NOT**
- ❌ Not a neural network
- ❌ Not trained on labeled data
- ❌ No LLM / GPT calls
- ❌ No embeddings / vectors

**✅ What it IS**
- ✅ Deterministic, explainable
- ✅ Fully offline
- ✅ Auditable (you can see every formula)
- ✅ Fresher-friendly by design

</div>
""", unsafe_allow_html=True)

    st.divider()
    st.markdown("### 📁 Supported Formats")
    st.markdown("""
- **CSV** (Google Forms, custom)
- **Excel** (.xlsx / .xls)
- **JSON** (array of objects)
- **JSONL** (challenge format)

**Auto-detected columns:**
`name, email, skills, yoe, title, company, education, college, gpa, certifications, github, location, summary`
""")


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-header">
    <h1 class="hero-title">🎯 RedRob AI Candidate Ranker</h1>
    <p class="hero-subtitle">
        Upload candidate data in <strong>any format</strong> → get a ranked shortlist with full reasoning.
        Works with Google Forms exports, custom CSVs, Excel sheets, and JSON.
        <br>No AI black boxes — every score is fully explainable.
    </p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# INPUT SECTION
# ─────────────────────────────────────────────────────────────────────────────
col_upload, col_jd = st.columns([1, 1], gap="large")

with col_upload:
    st.markdown("### 📂 Upload Candidate Data")
    st.markdown("*CSV, Excel, JSON, or JSONL — any format works*")
    uploaded_file = st.file_uploader(
        label="Drop your file here",
        type=["csv", "xlsx", "xls", "json", "jsonl"],
        help="Google Forms CSV export, custom spreadsheet, or JSON array"
    )

    if uploaded_file:
        st.success(f"✅ **{uploaded_file.name}** — {uploaded_file.size / 1024:.1f} KB")

with col_jd:
    st.markdown("### 📝 Job Description")
    st.markdown("*Paste the JD or describe the role — the system extracts required skills*")

    DEFAULT_JD = """Senior AI Engineer — NLP & Retrieval Systems

We are looking for an engineer to build our next-generation retrieval and ranking systems.

Required Skills:
- Python (3+ years)
- NLP, transformers, BERT, LLM fine-tuning
- Vector search: FAISS, Qdrant, Pinecone, Elasticsearch
- LLM fine-tuning: LoRA, QLoRA, PEFT
- RAG (Retrieval Augmented Generation)
- Machine learning, deep learning
- PyTorch or TensorFlow

Nice to have:
- MLOps, model deployment
- Cloud: AWS or GCP
- SQL, data pipelines"""

    jd_text = st.text_area(
        label="Job Description",
        value=DEFAULT_JD,
        height=280,
        label_visibility="collapsed",
        placeholder="Paste the job description here...",
    )


# ─────────────────────────────────────────────────────────────────────────────
# RUN RANKING
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("")
run_col, _, _ = st.columns([1, 2, 2])
with run_col:
    run_btn = st.button("🚀 Rank Candidates", use_container_width=True)

if run_btn and uploaded_file and jd_text:
    with st.spinner("⚙️ Parsing candidates and computing scores..."):
        # Parse file
        file_bytes = uploaded_file.read()
        candidates = parse_any_format(file_bytes, uploaded_file.name)

        if not candidates:
            st.error("❌ Could not parse the file. Please check the format and try again.")
            st.stop()

        # Score & rank
        ranked, jd_skills = rank_candidates(candidates, jd_text)

    st.balloons()

    # ── STATS ROW ──────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## 📊 Ranking Complete")

    c1, c2, c3, c4, c5 = st.columns(5)
    total = len(ranked)
    freshers = sum(1 for r in ranked if r["is_fresher"])
    top_score = ranked[0]["final_score"] if ranked else 0
    avg_score = sum(r["final_score"] for r in ranked) / max(1, total)
    skills_used = len(jd_skills)

    with c1:
        st.metric("Candidates", f"{total:,}", help="Total candidates ranked")
    with c2:
        st.metric("Top Score", f"{top_score:.3f}", help="Highest composite score")
    with c3:
        st.metric("Avg Score", f"{avg_score:.3f}", help="Mean score across all candidates")
    with c4:
        st.metric("Freshers 🌱", f"{freshers}", help="Candidates with ≤2 YoE in shortlist")
    with c5:
        st.metric("JD Skills", f"{skills_used}", help="Skills extracted from JD")

    # ── JD SKILLS DETECTED ─────────────────────────────────────────────────
    with st.expander("🔍 Skills extracted from Job Description"):
        cols = st.columns(4)
        for i, skill in enumerate(jd_skills[:40]):
            with cols[i % 4]:
                st.markdown(
                    f'<span style="background:rgba(99,102,241,0.15);color:#a78bfa;'
                    f'padding:3px 10px;border-radius:20px;font-size:0.8rem;'
                    f'font-weight:500;display:inline-block;margin:2px;">'
                    f'{skill}</span>',
                    unsafe_allow_html=True
                )

    st.markdown("---")

    # ── RANKED LIST ────────────────────────────────────────────────────────
    st.markdown("## 🏆 Ranked Candidates")

    # Color scheme helper
    def get_card_class(rank, is_fresher):
        if rank <= 3:
            return "top-3"
        if is_fresher:
            return "fresher"
        return ""

    def rank_emoji(rank):
        return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")

    def score_color(score):
        if score >= 0.75:
            return "#22c55e"
        if score >= 0.55:
            return "#6366f1"
        if score >= 0.35:
            return "#f59e0b"
        return "#ef4444"

    def pct(score):
        return f"{score * 100:.0f}%"

    for r in ranked:
        card_class = get_card_class(r["rank"], r["is_fresher"])
        bar_class = card_class if card_class else ""

        with st.container():
            st.markdown(f"""
<div class="rank-card {card_class}">
  <div style="display:flex; align-items:flex-start; gap:16px;">
    <div style="min-width:52px; text-align:center;">
      <div style="font-size:1.6rem;">{rank_emoji(r['rank'])}</div>
      <div style="color:#64748b;font-size:0.72rem;font-weight:600;">RANK</div>
    </div>
    <div style="flex:1;">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:4px;">
        <span style="font-size:1.1rem;font-weight:700;color:#e2e8f0;">
          {r.get('name') or r.get('candidate_id','—')}
        </span>
        {'<span class="badge badge-top">TOP 3</span>' if r["rank"] <= 3 else ""}
        {'<span class="badge badge-fresher">🌱 FRESHER</span>' if r["is_fresher"] else ""}
        {'<span style="color:#fbbf24;font-size:0.8rem;font-weight:600">× {:.2f} BOOST</span>'.format(r["fresher_uplift"]) if r["fresher_uplift"] > 1.0 else ""}
      </div>
      <div style="color:#94a3b8;font-size:0.9rem;margin-bottom:8px;">
        {r.get('title','—')}
        {' @ <strong style="color:#c4b5fd;">' + r['company'] + '</strong>' if r.get('company') else ''}
        {' &nbsp;•&nbsp; ' + str(r['yoe']) + ' YoE' if r.get('yoe') is not None else ''}
        {' &nbsp;•&nbsp; 📍' + r['location'] if r.get('location') else ''}
      </div>
      <div class="score-bar-bg">
        <div class="score-bar-fill {bar_class}" style="width:{pct(r['final_score'])};"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:6px;">
        <div style="font-size:0.78rem;color:#64748b;">
          🎯 {pct(r['skill_score'])} skill &nbsp;
          📅 {pct(r['experience_score'])} exp &nbsp;
          🎓 {pct(r['education_score'])} edu &nbsp;
          📜 {pct(r['certification_score'])} certs
        </div>
        <div style="font-size:1rem;font-weight:700;color:{score_color(r['final_score'])};">
          {r['final_score']:.4f}
        </div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        # Expandable reasoning
        with st.expander(f"📋 Why #{r['rank']}? — Full scoring breakdown"):
            ra, rb = st.columns([1, 1])

            with ra:
                st.markdown("**🎯 Signal Scores**")
                signals = [
                    ("Skill Match", r["skill_score"], "🎯"),
                    ("Experience Fit", r["experience_score"], "📅"),
                    ("Education", r["education_score"], "🎓"),
                    ("Completeness", r["completeness_score"], "📋"),
                    ("Certifications", r["certification_score"], "📜"),
                    ("Keyword Density", r["keyword_score"], "🔍"),
                ]
                for name, score, icon in signals:
                    filled = int(score * 20)
                    bar = "█" * filled + "░" * (20 - filled)
                    color = score_color(score)
                    st.markdown(
                        f'{icon} **{name}**: '
                        f'<span style="font-family:monospace;color:{color}">{bar}</span> '
                        f'`{score:.3f}`',
                        unsafe_allow_html=True
                    )

                if r["is_fresher"] and r["fresher_uplift"] > 1.0:
                    st.markdown(
                        f'🚀 **Fresher Boost**: `×{r["fresher_uplift"]:.3f}` '
                        f'(high-potential signals detected)',
                    )

            with rb:
                st.markdown("**📝 Reasoning**")
                for line in r["reasoning"].split(" || "):
                    if line.strip():
                        tag, _, detail = line.partition(": ")
                        st.markdown(f"- **{tag}**: {detail}")

    # ── DOWNLOAD BUTTON ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💾 Download Results")

    export_rows = []
    for r in ranked:
        export_rows.append({
            "rank": r["rank"],
            "candidate_id": r["candidate_id"],
            "name": r.get("name", ""),
            "title": r.get("title", ""),
            "company": r.get("company", ""),
            "location": r.get("location", ""),
            "yoe": r.get("yoe", ""),
            "is_fresher": r["is_fresher"],
            "final_score": r["final_score"],
            "skill_score": r["skill_score"],
            "experience_score": r["experience_score"],
            "education_score": r["education_score"],
            "completeness_score": r["completeness_score"],
            "certification_score": r["certification_score"],
            "keyword_score": r["keyword_score"],
            "fresher_uplift": r["fresher_uplift"],
            "skill_match_detail": r["skill_match_detail"],
            "experience_detail": r["experience_detail"],
            "education_detail": r["education_detail"],
            "certification_detail": r["certification_detail"],
            "reasoning": r["reasoning"],
        })

    df_export = pd.DataFrame(export_rows)
    csv_bytes = df_export.to_csv(index=False).encode("utf-8")

    dl_col1, dl_col2, _ = st.columns([1, 1, 2])
    with dl_col1:
        st.download_button(
            label="⬇️ Download CSV",
            data=csv_bytes,
            file_name="ranked_candidates.csv",
            mime="text/csv",
        )
    with dl_col2:
        json_bytes = json.dumps(export_rows, indent=2, default=str).encode()
        st.download_button(
            label="⬇️ Download JSON",
            data=json_bytes,
            file_name="ranked_candidates.json",
            mime="application/json",
        )

    # ── TABLE VIEW ────────────────────────────────────────────────────────
    with st.expander("📊 View as Table"):
        display_df = df_export[[
            "rank", "name", "title", "company", "yoe",
            "is_fresher", "final_score",
            "skill_score", "experience_score", "education_score"
        ]].rename(columns={
            "rank": "Rank", "name": "Name", "title": "Title",
            "company": "Company", "yoe": "YoE",
            "is_fresher": "Fresher?", "final_score": "Score",
            "skill_score": "Skill", "experience_score": "Exp", "education_score": "Edu",
        })
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=1, format="%.3f"
                ),
                "Skill": st.column_config.ProgressColumn(
                    "Skill", min_value=0, max_value=1, format="%.2f"
                ),
                "Exp": st.column_config.ProgressColumn(
                    "Exp", min_value=0, max_value=1, format="%.2f"
                ),
                "Edu": st.column_config.ProgressColumn(
                    "Edu", min_value=0, max_value=1, format="%.2f"
                ),
            }
        )

elif run_btn and not uploaded_file:
    st.warning("⚠️ Please upload a candidate data file first.")
elif run_btn and not jd_text.strip():
    st.warning("⚠️ Please enter a job description.")
else:
    # Initial state — show sample data format
    st.markdown("---")
    st.markdown("### 👋 Getting Started")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**📄 Sample Google Forms CSV structure:**")
        sample_df = pd.DataFrame({
            "Timestamp": ["2024-01-15 10:30:00", "2024-01-15 11:00:00"],
            "Your Name": ["Priya Sharma", "Rahul Mehta"],
            "Email Address": ["priya@example.com", "rahul@example.com"],
            "Years of Experience": ["0", "3"],
            "Current Role / Title": ["Student", "ML Engineer"],
            "Technical Skills": [
                "Python, PyTorch, NLP, Transformers, BERT",
                "Python, TensorFlow, MLOps, FAISS, RAG"
            ],
            "College / University": ["IIT Delhi", "NIT Trichy"],
            "CGPA / Percentage": ["9.2 CGPA", "78%"],
            "Certifications": [
                "Deep Learning Specialization (Coursera)",
                "AWS ML Specialty"
            ],
            "GitHub Profile": [
                "github.com/priyasharma", "github.com/rahulmehta"
            ],
        })
        st.dataframe(sample_df, use_container_width=True, hide_index=True)

    with col_b:
        st.markdown("**🎯 What you'll get:**")
        st.markdown("""
- **Ranked list** with score breakdowns
- **Visual score bars** for each signal
- **Full reasoning** — exactly why each candidate ranked where they did
- **Fresher tracking** — guaranteed representation
- **Downloadable CSV/JSON** results

**✨ Smart column detection — no setup needed!**
The system auto-detects:
`name` / `your name` / `candidate name` → `name`
`yoe` / `years of experience` / `work experience` → `yoe`
`skills` / `technical skills` / `technologies` → `skills`
...and 50+ more aliases
""")
