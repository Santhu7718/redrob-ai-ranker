"""
universal_scorer.py
-------------------
Scores any flat candidate dict (from universal_parser) against a job description.

Unlike the original scorer.py (which required the exact nested challenge format),
this works with ANY data — Google Forms CSV, custom Excel, plain JSON, or the
original challenge JSONL.

HOW IT WORKS (no ML model, no training):
=========================================
This is a rule-based multi-signal scoring system. Here's every calculation:

SIGNAL 1 — SKILL MATCH (weight: 0.35)
  - Extracts required skills from the job description (JD) using keyword search
  - Searches the candidate's skills, summary, title, and education fields
  - Each skill found adds to a coverage score
  - Score = matched_skills / total_required_skills (capped at 1.0)

SIGNAL 2 — EXPERIENCE FIT (weight: 0.25)
  - Parses YoE from the candidate's "yoe" field (e.g. "3", "3 years", "2.5")
  - Uses a curve that FAVORS FRESHERS:
    * 0 YoE  → 0.65 base score (freshers are valued!)
    * 1 YoE  → 0.70
    * 2 YoE  → 0.72
    * 3-5 YoE → 0.80
    * 5-8 YoE → 0.85 (sweet spot)
    * 8+ YoE  → 0.70 (over-experienced penalty)

SIGNAL 3 — EDUCATION QUALITY (weight: 0.15)
  - Detects institution tier from college name keywords (IIT/NIT/BITS → tier_1)
  - Detects field relevance (CS/ML/AI → high, unrelated → low)
  - Detects degree level (PhD > M.Tech/M.S > B.Tech/B.E > Diploma)
  - Parses GPA (CGPA, %, raw number)

SIGNAL 4 — PROFILE COMPLETENESS (weight: 0.10)
  - Rewards candidates who filled in more fields (GitHub, LinkedIn, portfolio)
  - A fresher with a GitHub link > a senior with no online presence

SIGNAL 5 — CERTIFICATIONS / UPSKILLING (weight: 0.10)
  - Checks if certifications contain ML-relevant keywords
  - Recency bonus for recent certifications

SIGNAL 6 — KEYWORD DENSITY (weight: 0.05)
  - Full-text scan of all fields for JD keywords
  - Catches implicit matches (mentions "FAISS" in a project description)

COMPOSITE:
  final_score = Σ(signal_i × weight_i)
  For freshers (YoE ≤ 2): final_score × fresher_uplift (up to 1.25×)

WHY NO TRAINED MODEL?
  The challenge says "no network calls during ranking". Training would require
  labeled data. Instead, the scoring rules were derived by reading the JD
  carefully and encoding what a great recruiter would look for.
"""

import re
import math
from typing import Dict, Any, Tuple, List


# ─────────────────────────────────────────────────────────────────────────────
# SCORING WEIGHTS
# ─────────────────────────────────────────────────────────────────────────────
WEIGHTS = {
    "skill_match":     0.35,
    "experience_fit":  0.25,
    "education":       0.15,
    "completeness":    0.10,
    "certifications":  0.10,
    "keyword_density": 0.05,
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _clamp(x: float, lo=0.0, hi=1.0) -> float:
    return max(lo, min(hi, x))


def _norm(text: str) -> str:
    """Lowercase and normalize text for matching."""
    return re.sub(r'[^a-z0-9\s]', ' ', text.lower())


def _all_text(candidate: Dict) -> str:
    """Concatenate all string fields for full-text search."""
    parts = []
    for k, v in candidate.items():
        if isinstance(v, str) and not k.startswith("_"):
            parts.append(v)
    return _norm(" ".join(parts))


def _parse_yoe(raw: str) -> float:
    """Parse years of experience from any string format."""
    if not raw or str(raw).strip() in ("", "nan", "None", "-1"):
        return 0.0
    raw = str(raw).strip()
    # Handle ranges like "3-5" → take lower
    rng = re.match(r'(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)', raw)
    if rng:
        return float(rng.group(1))
    # Handle "3 years", "3.5 yrs", "3+ years"
    nums = re.findall(r'\d+(?:\.\d+)?', raw)
    if nums:
        return float(nums[0])
    return 0.0


def _extract_skills_from_jd(jd_text: str) -> List[str]:
    """
    Extract required skills from job description text.
    Looks for: bulleted lists, "Required:", "Skills:", common tech terms.
    Returns lowercase skill list.
    """
    jd_norm = _norm(jd_text)

    # Known ML/tech skill keywords to scan for
    KNOWN_SKILLS = [
        # Core ML / AI
        "machine learning", "deep learning", "neural network", "nlp",
        "natural language processing", "computer vision", "reinforcement learning",
        "generative ai", "large language model", "llm", "transformer",
        "bert", "gpt", "fine tuning", "fine-tuning", "rag", "retrieval augmented",
        "vector embedding", "embedding", "semantic search",
        # ML Frameworks
        "pytorch", "tensorflow", "keras", "jax", "hugging face", "huggingface",
        "langchain", "llamaindex", "llama index",
        # Vector / Search
        "faiss", "pinecone", "qdrant", "weaviate", "milvus", "pgvector",
        "elasticsearch", "opensearch", "solr", "bm25", "vector search",
        # ML Ops / Engineering
        "mlops", "model serving", "model deployment", "kubeflow", "airflow",
        "feature store", "experiment tracking", "mlflow", "wandb",
        # Fine-tuning methods
        "lora", "qlora", "peft", "sft", "dpo", "rlhf",
        # Programming
        "python", "sql", "spark", "scala", "java", "rust", "go", "typescript",
        "javascript", "c++", "r language",
        # Data / DB
        "pandas", "numpy", "data pipeline", "etl", "kafka", "redis",
        "postgresql", "mongodb", "bigquery", "snowflake", "dbt",
        # Cloud / Infra
        "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
        "ci/cd", "github actions",
        # Generic
        "api", "rest api", "microservices", "agile", "system design",
        "data structure", "algorithm",
    ]

    found = []
    for skill in KNOWN_SKILLS:
        if skill in jd_norm:
            found.append(skill)

    # Also extract multi-word phrases after bullets / colons
    bullet_items = re.findall(
        r'(?:^|\n)\s*[-•*]\s*(.+?)(?:\n|$)', jd_text, re.MULTILINE
    )
    for item in bullet_items:
        item_norm = _norm(item)
        if len(item_norm) < 60:  # Short items are likely skill requirements
            found.append(item_norm.strip())

    # Deduplicate preserving order
    seen = set()
    result = []
    for s in found:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            result.append(s)
    return result[:60]  # cap at 60 skills


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def score_skill_match(candidate: Dict, jd_skills: List[str]) -> Tuple[float, str]:
    """SIGNAL 1: How many JD skills does the candidate have?"""
    if not jd_skills:
        return 0.5, "No skills extracted from JD"

    full_text = _all_text(candidate)
    matched = []
    missed = []

    for skill in jd_skills:
        # Use word boundary matching to avoid partial matches
        pattern = r'\b' + re.escape(skill.replace(' ', r'\s+')) + r'\b'
        if re.search(pattern, full_text):
            matched.append(skill)
        else:
            missed.append(skill)

    score = _clamp(len(matched) / max(len(jd_skills), 1))

    # Boost if high-value ML skills are present
    high_value = {"pytorch", "tensorflow", "hugging face", "huggingface", "lora",
                  "qlora", "rag", "vector search", "embedding", "nlp",
                  "large language model", "llm", "bert", "transformer"}
    hv_matched = [s for s in matched if s in high_value]
    if hv_matched:
        score = _clamp(score + 0.05 * len(hv_matched))

    top_matched = matched[:5]
    reason = (
        f"Matched {len(matched)}/{len(jd_skills)} JD skills: "
        f"{', '.join(top_matched)}" +
        (f" (+{len(hv_matched)} high-value)" if hv_matched else "")
    )
    return _clamp(score), reason


def score_experience_fit(candidate: Dict) -> Tuple[float, str]:
    """SIGNAL 2: Balanced YoE curve — values both freshers AND experienced."""
    raw_yoe = candidate.get("yoe", "0")
    yoe = _parse_yoe(str(raw_yoe))

    if yoe == 0:
        base = 0.60
        tag = "Fresher (0 YoE) — potential-based"
    elif yoe <= 1:
        base = 0.65
        tag = f"Entry-level ({yoe:.1f} YoE)"
    elif yoe <= 2:
        base = 0.72
        tag = f"Junior ({yoe:.1f} YoE)"
    elif yoe <= 4:
        base = 0.85
        tag = f"Early mid-level ({yoe:.1f} YoE)"
    elif yoe <= 7:
        base = 1.00
        tag = f"Mid-level ({yoe:.1f} YoE) — prime range"
    elif yoe <= 10:
        base = 0.92
        tag = f"Senior ({yoe:.1f} YoE)"
    elif yoe <= 15:
        base = 0.78
        tag = f"Senior+ ({yoe:.1f} YoE)"
    else:
        base = 0.62
        tag = f"Very senior ({yoe:.1f} YoE) — likely over-qualified for entry roles"

    return _clamp(base), tag


def score_education(candidate: Dict) -> Tuple[float, str]:
    """SIGNAL 3: Education quality, institution tier, field relevance, GPA."""
    edu_text = _norm(" ".join([
        candidate.get("education", ""),
        candidate.get("college", ""),
        candidate.get("_edu_tier", ""),
    ]))
    gpa_raw = candidate.get("gpa", "")

    score = 0.50  # neutral base
    reasons = []

    # Institution tier detection
    tier1_keywords = ["iit", "iisc", "bits pilani", "nit ", "iiser", "vit ",
                      "mit ", "stanford", "carnegie mellon", "cmu", "cambridge"]
    tier2_keywords = ["delhi university", "bombay", "jadavpur", "hyderabad",
                      "manipal", "symbiosis", "srm ", "amity ", "lpu "]

    explicit_tier = candidate.get("_edu_tier", "unknown")

    if explicit_tier == "tier_1" or any(k in edu_text for k in tier1_keywords):
        score += 0.25
        reasons.append("Tier-1 institution")
    elif explicit_tier == "tier_2" or any(k in edu_text for k in tier2_keywords):
        score += 0.15
        reasons.append("Tier-2 institution")
    elif explicit_tier in ("tier_3", "tier_4"):
        score += 0.05
        reasons.append(f"{explicit_tier} institution")

    # Field relevance
    cs_ml_keywords = ["computer science", "cs", "artificial intelligence", "ai",
                      "machine learning", "data science", "information technology",
                      "it", "electronics", "ece", "software", "mathematics",
                      "statistics", "physics"]
    if any(k in edu_text for k in cs_ml_keywords):
        score += 0.15
        reasons.append("Relevant field (CS/ML/IT/Math)")

    # Degree level
    if any(k in edu_text for k in ["phd", "ph.d", "doctorate"]):
        score += 0.10
        reasons.append("PhD")
    elif any(k in edu_text for k in ["m.tech", "mtech", "m.s.", "ms ", "m.e.", "mba"]):
        score += 0.07
        reasons.append("Masters")
    elif any(k in edu_text for k in ["b.tech", "btech", "b.e.", "be ", "bsc", "b.sc"]):
        score += 0.03
        reasons.append("Bachelors")

    # GPA parsing
    gpa_score = _parse_gpa(str(gpa_raw))
    if gpa_score is not None:
        if gpa_score >= 0.85:
            score += 0.05
            reasons.append(f"High GPA ({gpa_raw})")
        elif gpa_score >= 0.70:
            score += 0.02
            reasons.append(f"Good GPA ({gpa_raw})")

    reason = " | ".join(reasons) if reasons else "Education: insufficient data"
    return _clamp(score), reason


def _parse_gpa(raw: str) -> float | None:
    """Return GPA as 0.0–1.0 or None if can't parse."""
    raw = raw.strip()
    if not raw or raw in ("nan", "", "None"):
        return None

    # CGPA out of 10
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:/\s*10|cgpa|out of 10)', raw, re.IGNORECASE)
    if m:
        return _clamp(float(m.group(1)) / 10.0)

    # Percentage
    m = re.search(r'(\d+(?:\.\d+)?)\s*%', raw)
    if m:
        return _clamp(float(m.group(1)) / 100.0)

    # Raw number
    nums = re.findall(r'\d+(?:\.\d+)?', raw)
    if nums:
        val = float(nums[0])
        if val <= 10:
            return _clamp(val / 10.0)
        elif val <= 100:
            return _clamp(val / 100.0)
    return None


def score_completeness(candidate: Dict) -> Tuple[float, str]:
    """SIGNAL 4: Profile completeness — more data = better candidate signal."""
    fields_filled = []
    if candidate.get("name"):
        fields_filled.append("name")
    if candidate.get("email"):
        fields_filled.append("email")
    if candidate.get("skills"):
        fields_filled.append("skills")
    if candidate.get("yoe"):
        fields_filled.append("yoe")
    if candidate.get("title"):
        fields_filled.append("title")
    if candidate.get("company"):
        fields_filled.append("company")
    if candidate.get("education") or candidate.get("college"):
        fields_filled.append("education")
    if candidate.get("gpa"):
        fields_filled.append("gpa")
    if candidate.get("certifications"):
        fields_filled.append("certifications")
    if candidate.get("summary"):
        fields_filled.append("summary")
    if candidate.get("location"):
        fields_filled.append("location")
    if candidate.get("phone"):
        fields_filled.append("phone")

    # Online presence (big signal for freshers)
    github = candidate.get("github", "")
    if github and github not in ("-1", "", "nan", "None"):
        if re.search(r'github\.com|github\.io|\d{2,}', github):  # URL or activity score
            fields_filled.append("github_active")

    if candidate.get("linkedin"):
        fields_filled.append("linkedin")
    if candidate.get("portfolio"):
        fields_filled.append("portfolio")

    score = _clamp(len(fields_filled) / 12.0)
    reason = f"Filled {len(fields_filled)}/14 profile fields: {', '.join(fields_filled[:5])}"
    return score, reason


def score_certifications(candidate: Dict) -> Tuple[float, str]:
    """SIGNAL 5: Relevant certifications — upskilling signal."""
    certs_text = _norm(" ".join([
        candidate.get("certifications", ""),
        candidate.get("summary", ""),
        candidate.get("skills", ""),
    ]))

    ml_cert_keywords = [
        "machine learning", "deep learning", "nlp", "tensorflow", "pytorch",
        "aws certified", "google cloud", "azure", "data science", "python",
        "coursera", "udacity", "fast.ai", "hugging face", "kaggle",
        "nvidia", "databricks", "snowflake", "langchain",
        "llm", "bert", "transformer", "vector", "embedding",
        "deeplearning.ai", "andrew ng",
    ]

    found_certs = [k for k in ml_cert_keywords if k in certs_text]

    if not found_certs:
        return 0.30, "No ML certifications detected"

    score = _clamp(0.40 + 0.08 * len(found_certs))
    reason = f"ML certifications/upskilling: {', '.join(found_certs[:4])}"
    return score, reason


def score_keyword_density(candidate: Dict, jd_skills: List[str]) -> Tuple[float, str]:
    """SIGNAL 6: Full-text keyword density — catches implicit expertise."""
    full_text = _all_text(candidate)
    if not full_text or not jd_skills:
        return 0.3, "Insufficient text for density analysis"

    total_words = max(1, len(full_text.split()))
    hit_count = sum(1 for skill in jd_skills if skill in full_text)

    # Density: hits per 100 words
    density = (hit_count / total_words) * 100
    score = _clamp(min(1.0, density / 5.0))  # 5 hits per 100 words = 1.0

    reason = f"Keyword density: {hit_count} JD terms across full profile text"
    return score, reason


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE SCORER
# ─────────────────────────────────────────────────────────────────────────────

def score_candidate(candidate: Dict, jd_text: str, jd_skills: List[str]) -> Dict[str, Any]:
    """
    Score a single candidate against a job description.
    Returns a dict with all scores, reasoning, and final composite score.
    """
    # Run all 6 signals
    skill_score, skill_reason = score_skill_match(candidate, jd_skills)
    exp_score, exp_reason = score_experience_fit(candidate)
    edu_score, edu_reason = score_education(candidate)
    comp_score, comp_reason = score_completeness(candidate)
    cert_score, cert_reason = score_certifications(candidate)
    kw_score, kw_reason = score_keyword_density(candidate, jd_skills)

    # Weighted composite
    composite = (
        skill_score    * WEIGHTS["skill_match"] +
        exp_score      * WEIGHTS["experience_fit"] +
        edu_score      * WEIGHTS["education"] +
        comp_score     * WEIGHTS["completeness"] +
        cert_score     * WEIGHTS["certifications"] +
        kw_score       * WEIGHTS["keyword_density"]
    )

    # Fresher uplift — modest boost for high-signal freshers only
    yoe = _parse_yoe(str(candidate.get("yoe", "0")))
    fresher_uplift = 1.0
    if yoe <= 2:
        potential = 0
        if skill_score >= 0.45:  potential += 2   # raised bar — needs strong skill match
        if edu_score  >= 0.65:   potential += 2   # raised bar — needs strong education
        if comp_score >= 0.65:   potential += 1
        if cert_score >= 0.55:   potential += 2
        if yoe == 0:             potential += 1
        # Cap at ×1.15 (was ×1.30) — uplift assists but doesn't dominate
        fresher_uplift = 1.0 + min(0.15, potential * 0.03)
        composite = min(0.90, composite * fresher_uplift)

    final_score = _clamp(composite)

    # Build human-readable reasoning
    component_str = (
        f"Skill({skill_score:.2f}×{WEIGHTS['skill_match']}) + "
        f"Exp({exp_score:.2f}×{WEIGHTS['experience_fit']}) + "
        f"Edu({edu_score:.2f}×{WEIGHTS['education']}) + "
        f"Completeness({comp_score:.2f}×{WEIGHTS['completeness']}) + "
        f"Certs({cert_score:.2f}×{WEIGHTS['certifications']}) + "
        f"Keywords({kw_score:.2f}×{WEIGHTS['keyword_density']})"
    )
    if yoe <= 2 and fresher_uplift > 1.0:
        component_str += f" × FRESHER_BOOST({fresher_uplift:.2f})"

    reasoning = " || ".join([
        f"SKILLS: {skill_reason}",
        f"EXPERIENCE: {exp_reason}",
        f"EDUCATION: {edu_reason}",
        f"COMPLETENESS: {comp_reason}",
        f"CERTIFICATIONS: {cert_reason}",
        f"FORMULA: {component_str}",
    ])

    return {
        "candidate_id": candidate.get("candidate_id", ""),
        "name": candidate.get("name", candidate.get("candidate_id", "")),
        "title": candidate.get("title", ""),
        "company": candidate.get("company", ""),
        "location": candidate.get("location", ""),
        "yoe": yoe,
        "final_score": round(final_score, 4),
        "skill_score": round(skill_score, 3),
        "experience_score": round(exp_score, 3),
        "education_score": round(edu_score, 3),
        "completeness_score": round(comp_score, 3),
        "certification_score": round(cert_score, 3),
        "keyword_score": round(kw_score, 3),
        "fresher_uplift": round(fresher_uplift, 3),
        "is_fresher": yoe <= 2,
        "skill_match_detail": skill_reason,
        "experience_detail": exp_reason,
        "education_detail": edu_reason,
        "completeness_detail": comp_reason,
        "certification_detail": cert_reason,
        "reasoning": reasoning,
    }


def rank_candidates(candidates: List[Dict], jd_text: str) -> List[Dict]:
    """
    Score and rank all candidates. Returns sorted list (best first).
    Pure score-based ranking — no forced quotas.
    Freshers rise on merit: strong skills + education + certs = high score.
    """
    jd_skills = _extract_skills_from_jd(jd_text)

    all_scored = [score_candidate(c, jd_text, jd_skills) for c in candidates]

    # Pure merit sort — score decides everything
    all_scored.sort(key=lambda r: -r["final_score"])

    # Assign ranks
    for i, r in enumerate(all_scored):
        r["rank"] = i + 1

    return all_scored, jd_skills
