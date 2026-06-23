"""
app.py — ICD (Intelligent Candidate Discovery AI)
Streamlit Cloud deployment.

Strategy:
  - Read web/index.html exactly as-is
  - Inline web/styles.css (replace <link rel="stylesheet">)
  - Inject an auto-resize postMessage script so the iframe fills the page
  - Replace the Flask fetch() calls in main.js with a stub that shows
    the upload UI visually but posts a message to the Streamlit parent
  - Below the component: real Streamlit file_uploader + Python ranking
"""
import streamlit as st
import streamlit.components.v1 as components
import os, json, time, io, html as _html
import pandas as pd
from pathlib import Path
import re

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
HTML_FILE = WEB / "index.html"
CSS_FILE  = WEB / "styles.css"

html_src = HTML_FILE.read_text(encoding="utf-8")
css_src  = CSS_FILE.read_text(encoding="utf-8")

# ── Build the full inline HTML ────────────────────────────────────────────────
# 1. Replace <link rel="stylesheet" href="styles.css"> with inline <style>
#    (so the component is self-contained — no external file requests)
inline_html = re.sub(
    r'<link[^>]*styles\.css[^>]*>',
    f'<style>\n{css_src}\n</style>',
    html_src,
    flags=re.IGNORECASE
)

# 2. Remove the <script src="main.js"></script> — we'll inject a slim stub
#    that keeps all the visual/animation JS but rewires the ranking calls
STUB_JS = r"""
<script>
// ═══════════════════════════════════════════════════════════════════════
//  Streamlit Compatibility Stub
//  - Keeps all animations, nav, copy-buttons, scroll-reveal, etc.
//  - Replaces Flask fetch() calls with a postMessage to the parent
//    so Streamlit can handle the actual ranking in Python
// ═══════════════════════════════════════════════════════════════════════

// Auto-resize the Streamlit iframe to match this page height
function _sendHeight() {
  const h = Math.max(
    document.documentElement.scrollHeight,
    document.body.scrollHeight
  );
  window.parent.postMessage({ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: h }, "*");
}
window.addEventListener("load", () => { setTimeout(_sendHeight, 200); });
window.addEventListener("resize", _sendHeight);
new MutationObserver(_sendHeight).observe(document.body, { subtree: true, childList: true, attributes: true });

// ── Navbar scroll shrink ──────────────────────────────────────────────
(function initNavbar() {
  const navbar = document.getElementById("navbar");
  let last = 0;
  function onScroll() {
    const y = window.scrollY;
    if (navbar) {
      navbar.classList.toggle("navbar--scrolled", y > 60);
      navbar.classList.toggle("navbar--hidden", y > last + 80 && y > 200);
      navbar.classList.remove("navbar--hidden");
    }
    last = y;
  }
  window.addEventListener("scroll", onScroll, { passive: true });
})();

// ── Copy buttons ──────────────────────────────────────────────────────
(function initCopyButtons() {
  document.querySelectorAll(".copy-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const text = btn.dataset.clipboard;
      if (!text) return;
      navigator.clipboard.writeText(text).then(() => {
        btn.classList.add("copied");
        setTimeout(() => btn.classList.remove("copied"), 1800);
        const toast = document.getElementById("toast");
        if (toast) { toast.classList.add("toast--visible"); setTimeout(() => toast.classList.remove("toast--visible"), 2200); }
      });
    });
  });
})();

// ── Scroll reveal ─────────────────────────────────────────────────────
(function initScrollReveal() {
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add("visible"); obs.unobserve(e.target); } });
  }, { threshold: 0.1 });
  document.querySelectorAll(".pipeline-step, .score-card, .arch-card, .results-item, .run-step").forEach(el => obs.observe(el));
})();

// ── Weight bar animation ──────────────────────────────────────────────
(function initWeightBar() {
  const wb = document.querySelector(".weight-bar");
  if (!wb) return;
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        wb.querySelectorAll(".weight-segment").forEach((s, i) => {
          setTimeout(() => s.classList.add("animated"), i * 80);
        });
        obs.unobserve(wb);
      }
    });
  }, { threshold: 0.3 });
  obs.observe(wb);
})();

// ── Upload section: tell Streamlit parent to scroll to/show the uploader
(function initUploadSection() {
  const startBtn = document.getElementById("startRankBtn");
  const btnDefault = document.getElementById("btnDefault");
  const btnUpload  = document.getElementById("btnUpload");
  const dropZoneWrapper = document.getElementById("dropZoneWrapper");
  const fileInput = document.getElementById("fileInput");
  const dropZone  = document.getElementById("dropZone");

  // Source selector
  [btnDefault, btnUpload].forEach(btn => {
    btn?.addEventListener("click", () => {
      const src = btn.dataset.source;
      btnDefault?.classList.toggle("source-btn--active", src === "default");
      btnDefault?.setAttribute("aria-pressed", (src === "default").toString());
      btnUpload?.classList.toggle("source-btn--active", src === "upload");
      btnUpload?.setAttribute("aria-pressed", (src === "upload").toString());
      if (dropZoneWrapper) dropZoneWrapper.style.display = src === "upload" ? "block" : "none";
    });
  });

  // When Start Ranking is clicked → post to parent (Streamlit will handle)
  startBtn?.addEventListener("click", () => {
    // Scroll parent to the Streamlit upload section
    window.parent.postMessage({ type: "icd:scrollToUpload" }, "*");
    // Show a friendly banner in this page too
    const hint = document.createElement("div");
    hint.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#f43f5e;color:#fff;font-family:Inter,sans-serif;font-weight:700;font-size:.9rem;padding:14px 28px;border-radius:12px;z-index:9999;box-shadow:0 8px 32px rgba(244,63,94,.4);animation:fadeInUp .3s ease";
    hint.textContent = "⬇  Scroll down to upload your file in the Streamlit panel below";
    document.body.appendChild(hint);
    setTimeout(() => hint.remove(), 3500);
  });

  // File input change
  const dropZoneIdle = document.getElementById("dropZoneIdle");
  const dropZoneFile = document.getElementById("dropZoneFile");
  const selName = document.getElementById("selectedFileName");
  const selSize = document.getElementById("selectedFileSize");
  const clearBtn = document.getElementById("clearFile");

  fileInput?.addEventListener("change", e => {
    const f = e.target.files[0];
    if (!f) return;
    if (dropZoneIdle) dropZoneIdle.style.display = "none";
    if (dropZoneFile) dropZoneFile.style.display = "flex";
    if (selName) selName.textContent = f.name;
    if (selSize) selSize.textContent = (f.size / 1024 / 1024).toFixed(1) + " MB";
  });

  clearBtn?.addEventListener("click", e => {
    e.stopPropagation();
    if (fileInput) fileInput.value = "";
    if (dropZoneIdle) dropZoneIdle.style.display = "block";
    if (dropZoneFile) dropZoneFile.style.display = "none";
  });

  dropZone?.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
  dropZone?.addEventListener("dragleave", () => dropZone?.classList.remove("drag-over"));
  dropZone?.addEventListener("drop", e => {
    e.preventDefault();
    dropZone?.classList.remove("drag-over");
    const f = e.dataTransfer.files[0];
    if (f && fileInput) { fileInput.files = e.dataTransfer.files; fileInput.dispatchEvent(new Event("change")); }
  });
  dropZone?.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") fileInput?.click(); });
})();

// ── Smooth scroll ─────────────────────────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener("click", e => {
    const id = a.getAttribute("href").slice(1);
    const el = document.getElementById(id);
    if (el) { e.preventDefault(); el.scrollIntoView({ behavior: "smooth", block: "start" }); }
  });
});
</script>
"""

inline_html = re.sub(
    r'<script[^>]*main\.js[^>]*></script>',
    STUB_JS,
    inline_html,
    flags=re.IGNORECASE
)

# 3. Fix Google Fonts — keep the preconnect + font link as-is (they work fine)
# ── Streamlit chrome hiding + upload panel CSS ────────────────────────────────
CHROME_HIDE_CSS = """
<style>
/* Kill Streamlit chrome */
#MainMenu, footer,
header[data-testid="stHeader"],
.stDeployButton,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
.block-container, .stMainBlockContainer, .stMain > div {
  padding: 0 !important;
  max-width: 100% !important;
  margin: 0 !important;
}

/* Upload panel below the component */
.icd-upload-panel {
  background: #0d0f1a;
  min-height: 100vh;
  padding: 60px 24px 80px;
  font-family: 'Inter', -apple-system, sans-serif;
}
.icd-section-badge {
  display: inline-block;
  background: rgba(244,63,94,.12);
  border: 1px solid rgba(244,63,94,.25);
  color: #f43f5e;
  font-size: .78rem;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  padding: 6px 16px;
  border-radius: 999px;
  margin-bottom: 16px;
}
.icd-heading {
  font-size: clamp(1.6rem, 4vw, 2.4rem);
  font-weight: 800;
  color: #f1f5f9;
  margin: 0 0 8px;
  letter-spacing: -.03em;
}
.icd-sub {
  color: #94a3b8;
  font-size: 1rem;
  margin: 0 0 32px;
  max-width: 600px;
}
/* File uploader */
[data-testid="stFileUploaderDropzone"] {
  min-height: 120px;
  background: rgba(255,255,255,.02) !important;
  border: 2px dashed rgba(255,255,255,.10) !important;
  border-radius: 14px !important;
  transition: border-color .2s, background .2s !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: rgba(244,63,94,.35) !important;
  background: rgba(244,63,94,.04) !important;
}
[data-testid="stFileUploaderDropzone"] p,
[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] small {
  color: #64748b !important;
  font-family: 'Inter', sans-serif !important;
}
div[data-testid="stFileUploader"] section {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}
/* Button */
.stButton > button {
  background: linear-gradient(135deg, #f43f5e, #be123c) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 12px !important;
  padding: 14px 32px !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 1rem !important;
  font-weight: 700 !important;
  letter-spacing: -.01em !important;
  transition: all .2s !important;
  width: 100%;
  min-height: 52px;
}
.stButton > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 24px rgba(244,63,94,.35) !important;
}
/* Text area */
.stTextArea textarea {
  background: rgba(255,255,255,.03) !important;
  border: 1px solid rgba(255,255,255,.10) !important;
  border-radius: 12px !important;
  color: #e2e8f0 !important;
  font-family: 'Inter', sans-serif !important;
}
.stTextArea textarea:focus {
  border-color: rgba(244,63,94,.4) !important;
  box-shadow: 0 0 0 3px rgba(244,63,94,.08) !important;
}
.stTextArea label { color: #94a3b8 !important; font-family: 'Inter', sans-serif !important; }
/* Labels */
.stFileUploader label { color: #94a3b8 !important; font-family: 'Inter', sans-serif !important; }

/* Result cards */
.r-card {
  background: rgba(255,255,255,.03);
  border: 1px solid rgba(255,255,255,.08);
  border-radius: 14px;
  padding: 20px 24px;
  margin-bottom: 12px;
  font-family: 'Inter', sans-serif;
  transition: border-color .2s;
}
.r-card:hover { border-color: rgba(244,63,94,.25); }
.r-card.top3  { border-color: rgba(234,179,8,.30); background: rgba(234,179,8,.04); }
.r-card.fresh { border-color: rgba(34,197,94,.28); background: rgba(34,197,94,.04); }
.r-name  { font-size: 1.05rem; font-weight: 700; color: #e2e8f0; }
.r-meta  { font-size: .85rem; color: #94a3b8; margin-top: 3px; }
.r-score { font-size: 1.15rem; font-weight: 800; text-align: right; }
.r-score-sub { font-size: .72rem; color: #64748b; text-align: right; margin-top: 2px; }
.r-badge { display:inline-block;padding:2px 9px;border-radius:20px;font-size:.70rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;margin-right:5px; }
.b-fresh { background:rgba(34,197,94,.15);color:#4ade80;border:1px solid rgba(34,197,94,.3); }
.b-top   { background:rgba(234,179,8,.15); color:#fbbf24;border:1px solid rgba(234,179,8,.3); }
.b-boost { background:rgba(99,102,241,.15);color:#a78bfa;border:1px solid rgba(99,102,241,.3); }
.mbar { display:flex;align-items:center;gap:8px;margin:3px 0; }
.mbar-label { color:#64748b;font-size:.75rem;min-width:56px; }
.mbar-bg { flex:1;background:rgba(255,255,255,.06);border-radius:4px;height:5px;overflow:hidden; }
.mbar-fill { height:5px;border-radius:4px; }
.mbar-val { color:#94a3b8;font-size:.72rem;min-width:34px;text-align:right; }
.sum-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px; }
.sum-card { background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:20px 16px;text-align:center; }
.sum-val { font-size:1.8rem;font-weight:800;color:#f43f5e;font-family:'Inter',sans-serif; }
.sum-label { font-size:.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-top:4px; }
@media(max-width:640px) { .sum-grid { grid-template-columns:repeat(2,1fr); } }
</style>
"""

# ── Render ────────────────────────────────────────────────────────────────────
st.markdown(CHROME_HIDE_CSS, unsafe_allow_html=True)

# Full page as component — auto-resizes via postMessage
components.html(inline_html, height=6000, scrolling=False)

# ════════════════════════════════════════════════════════════════════════════
#  STREAMLIT UPLOAD + RANKING PANEL
#  (Appears below the full-page component as a seamless continuation)
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="icd-upload-panel" id="streamlit-upload">
  <div style="max-width:900px;margin:0 auto;">
    <div class="icd-section-badge">⚡ Upload &amp; Score</div>
    <h2 class="icd-heading">Upload Your Candidates File</h2>
    <p class="icd-sub">
      Drop your file below — CSV, Excel, JSON, JSONL or TXT.
      The ranking engine auto-detects columns and scores every candidate.
    </p>
  </div>
</div>
""", unsafe_allow_html=True)

with st.container():
    inner_col, _ = st.columns([10, 1])
    with inner_col:
        col_file, col_jd = st.columns([1, 1], gap="large")

        with col_file:
            st.markdown(
                '<p style="font-family:Inter,sans-serif;font-weight:600;'
                'color:#e2e8f0;margin-bottom:8px;">📂 Candidates File</p>',
                unsafe_allow_html=True
            )
            uploaded = st.file_uploader(
                "candidates_file",
                type=["csv", "xlsx", "xls", "json", "jsonl", "txt"],
                label_visibility="collapsed",
                help="Auto-detects any format — CSV, Excel, JSON, JSONL, TXT",
            )
            if uploaded:
                size_mb = uploaded.size / 1024 / 1024
                st.success(f"✅ **{uploaded.name}** — {size_mb:.1f} MB")

        with col_jd:
            st.markdown(
                '<p style="font-family:Inter,sans-serif;font-weight:600;'
                'color:#e2e8f0;margin-bottom:8px;">📝 Job Description</p>',
                unsafe_allow_html=True
            )
            DEFAULT_JD = """Software / AI Engineer — RedRob Tech

Core Skills:
- Python, Machine Learning, Deep Learning
- PyTorch or TensorFlow, scikit-learn
- NLP, Computer Vision, LLMs
- REST APIs, SQL, Git

Preferred:
- MLOps: Docker, Kubernetes, CI/CD
- Cloud: AWS / GCP / Azure
- Data Engineering: Spark, Pandas

Experience: 0–10 years (freshers welcome)
Location: Bangalore · Mumbai · Hyderabad · Remote"""
            jd_text = st.text_area(
                "jd_text",
                value=DEFAULT_JD,
                height=220,
                label_visibility="collapsed",
            )

        st.markdown("<br/>", unsafe_allow_html=True)
        run_col, _ = st.columns([2, 5])
        with run_col:
            run_btn = st.button("▶  Start Ranking", type="primary", use_container_width=True)

# ── Ranking ───────────────────────────────────────────────────────────────────
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
                raw        = uploaded.read()
                candidates = parse_any_format(raw, uploaded.name)
                if not candidates:
                    st.error("❌ Could not parse file. Check the format and try again.")
                    st.stop()
                ranked, jd_skills = rank_candidates(candidates, jd_text)
                elapsed = time.perf_counter() - t0
            except Exception as e:
                st.error(f"❌ Ranking failed: {e}")
                st.stop()

        freshers  = sum(1 for r in ranked if r.get("is_fresher"))
        avg_score = sum(r["final_score"] for r in ranked) / max(1, len(ranked))

        # ── Summary ──────────────────────────────────────────────────────────
        st.markdown(f"""
<div style="max-width:900px;margin:0 auto 0;font-family:Inter,sans-serif">
  <h2 style="font-size:1.8rem;font-weight:800;color:#f1f5f9;margin:24px 0 20px;letter-spacing:-.03em">
    🏆 Ranking Complete
  </h2>
  <div class="sum-grid">
    <div class="sum-card"><div class="sum-val">{len(candidates):,}</div><div class="sum-label">Total Candidates</div></div>
    <div class="sum-card"><div class="sum-val">{len(ranked)}</div><div class="sum-label">Top Ranked</div></div>
    <div class="sum-card"><div class="sum-val">{freshers}</div><div class="sum-label">Freshers in Top {len(ranked)}</div></div>
    <div class="sum-card"><div class="sum-val">{avg_score:.3f}</div><div class="sum-label">Avg Score ({elapsed:.0f}s)</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ── JD skills ────────────────────────────────────────────────────────
        if jd_skills:
            with st.expander(f"🔍 {len(jd_skills)} skills found in Job Description"):
                chips = "".join(
                    f'<span style="display:inline-block;background:rgba(99,102,241,.12);color:#a78bfa;'
                    f'border:1px solid rgba(99,102,241,.22);border-radius:16px;padding:3px 10px;'
                    f'font-size:.76rem;font-family:Inter,sans-serif;margin:3px;">{s}</span>'
                    for s in jd_skills[:60]
                )
                st.markdown(chips, unsafe_allow_html=True)

        # ── Results ───────────────────────────────────────────────────────────
        RANK_EMOJI = {1: "🥇", 2: "🥈", 3: "🥉"}
        def score_color(s):
            if s >= 0.75: return "#4ade80"
            if s >= 0.55: return "#a78bfa"
            if s >= 0.35: return "#fbbf24"
            return "#f87171"

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
                badges += f'<span class="r-badge b-boost">×{r["fresher_uplift"]:.2f}</span>'

            name    = _html.escape(str(r.get("name") or r.get("candidate_id", "—")))
            title   = _html.escape(str(r.get("title", "")))
            company = _html.escape(str(r.get("company", "")))
            yoe_v   = r.get("yoe", "")
            meta    = "  ".join(filter(None, [title, f"@ {company}" if company else "", f"• {yoe_v} YoE" if yoe_v not in ("", None, "None") else ""]))

            bars = ""
            for lbl, key, col in [
                ("Skill", "skill_score", "#f43f5e"),
                ("Exp",   "experience_score", "#4ade80"),
                ("Edu",   "education_score",  "#fbbf24"),
                ("Certs", "certification_score", "#a78bfa"),
            ]:
                sv = r.get(key, 0) or 0
                bars += (
                    f'<div class="mbar">'
                    f'<span class="mbar-label">{lbl}</span>'
                    f'<div class="mbar-bg"><div class="mbar-fill" style="width:{sv*100:.0f}%;background:{col}"></div></div>'
                    f'<span class="mbar-val">{sv:.2f}</span>'
                    f'</div>'
                )

            st.markdown(f"""
<div class="r-card {card_cls}" style="max-width:900px;margin:0 auto 12px;">
  <div style="display:flex;gap:16px;align-items:flex-start;">
    <div style="font-size:1.6rem;min-width:48px;text-align:center;padding-top:2px">{rlabel}</div>
    <div style="flex:1;min-width:0;">
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px;">
        <span class="r-name">{name}</span>{badges}
      </div>
      <div class="r-meta">{meta or "—"}</div>
      <div style="margin-top:10px;">{bars}</div>
    </div>
    <div style="min-width:70px;">
      <div class="r-score" style="color:{sc};">{score:.4f}</div>
      <div class="r-score-sub">Score</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            reasoning = r.get("reasoning", "")
            if reasoning:
                with st.expander(f"📋 Why #{rank}? — Full breakdown"):
                    ca, cb = st.columns(2)
                    with ca:
                        st.markdown("**Signal scores**")
                        for sl, sk, scol in [
                            ("🎯 Skill",      "skill_score",         "#f43f5e"),
                            ("📅 Experience", "experience_score",    "#4ade80"),
                            ("🎓 Education",  "education_score",     "#fbbf24"),
                            ("📋 Complete",   "completeness_score",  "#94a3b8"),
                            ("📜 Certs",      "certification_score", "#a78bfa"),
                            ("🔍 Keywords",   "keyword_score",       "#64748b"),
                        ]:
                            sv = r.get(sk, 0) or 0
                            filled = int(sv * 20)
                            bar = "█" * filled + "░" * (20 - filled)
                            st.markdown(f'{sl}: <code style="color:{scol}">{bar}</code> `{sv:.3f}`', unsafe_allow_html=True)
                        if r.get("fresher_uplift", 1) > 1.0:
                            st.success(f"🚀 Fresher boost ×{r['fresher_uplift']:.3f}")
                    with cb:
                        st.markdown("**Reasoning**")
                        for chunk in reasoning.split(" || "):
                            if ":" in chunk:
                                tag, _, detail = chunk.partition(": ")
                                st.markdown(f"**{tag}**: {detail}")

        # ── Download ──────────────────────────────────────────────────────────
        rows = [{
            "rank": r["rank"], "candidate_id": r.get("candidate_id", ""),
            "name": r.get("name", ""), "title": r.get("title", ""),
            "company": r.get("company", ""), "yoe": r.get("yoe", ""),
            "is_fresher": r.get("is_fresher", False),
            "final_score": round(r["final_score"], 6),
            "skill_score": round(r.get("skill_score", 0), 4),
            "experience_score": round(r.get("experience_score", 0), 4),
            "education_score": round(r.get("education_score", 0), 4),
            "certification_score": round(r.get("certification_score", 0), 4),
            "fresher_uplift": round(r.get("fresher_uplift", 1), 4),
            "reasoning": r.get("reasoning", ""),
        } for r in ranked]

        df_out = pd.DataFrame(rows)
        st.markdown("<br/>", unsafe_allow_html=True)
        st.markdown(
            f'<h3 style="font-family:Inter,sans-serif;font-weight:700;color:#f1f5f9;'
            f'max-width:900px;margin:0 auto 16px;">💾 Download Results</h3>',
            unsafe_allow_html=True
        )
        dl1, dl2, _ = st.columns([1, 1, 4])
        with dl1:
            st.download_button(
                "⬇️ CSV", df_out.to_csv(index=False).encode(),
                "ranked_candidates.csv", "text/csv", use_container_width=True,
            )
        with dl2:
            st.download_button(
                "⬇️ JSON", json.dumps(rows, indent=2, default=str).encode(),
                "ranked_candidates.json", "application/json", use_container_width=True,
            )
