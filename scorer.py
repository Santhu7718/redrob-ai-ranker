"""
scorer.py — Multi-Signal Candidate Scoring Engine
No external APIs. Pure Python + sklearn + numpy.

Scoring philosophy:
  - Understand what the role NEEDS, not just match keywords
  - Fresher-friendly: 0 YoE is NOT penalized; projects/GitHub/certs compensate
  - Anti-gaming: endorsement trust multiplier catches keyword stuffers
  - Behavioral signals: availability and engagement are multipliers, not additive
"""

import re
import math
import json
import numpy as np
from datetime import datetime, date
from typing import Dict, List, Any, Tuple, Optional
from jd_parser import JobRequirements


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

TODAY = datetime.now().date()

# Services-only companies per JD (penalize if ALL career is here)
SERVICES_FIRMS = {
    "tcs", "tata consultancy services", "infosys", "wipro",
    "accenture", "cognizant", "capgemini", "hcl technologies",
    "tech mahindra", "mphasis", "hexaware", "l&t infotech",
    "ltimindtree", "mindtree", "persistent systems", "niit technologies",
    "cyient", "zensar", "mastech", "igate"
}

# Skills that are CORE to this JD
CORE_SKILLS = {
    # Vector/embeddings — most critical
    "faiss", "pinecone", "weaviate", "qdrant", "milvus", "opensearch",
    "elasticsearch", "chroma", "pgvector", "annoy",
    "sentence-transformers", "sentence_transformers", "sentence transformers",
    "embeddings", "vector embeddings", "dense embeddings",
    "bge", "e5", "instructor embeddings",
    # Ranking / retrieval
    "bm25", "tf-idf", "tfidf", "hybrid search", "hybrid retrieval",
    "semantic search", "vector search", "dense retrieval",
    "learning to rank", "ltr", "reranking", "re-ranking",
    "information retrieval", "search ranking",
    "ndcg", "mrr", "map", "recall@k",
    # ML / AI
    "transformers", "huggingface", "hugging face", "bert", "roberta",
    "llm", "large language model", "fine-tuning", "finetuning",
    "rag", "retrieval augmented generation",
    "lora", "qlora", "peft",
    "pytorch", "tensorflow", "keras",
    "mlops", "model serving", "triton", "torchserve",
    # Python / data
    "python", "numpy", "pandas", "sklearn", "scikit-learn",
    "recommendation system", "recommendation engine",
    "matching algorithm", "candidate matching",
    # NLP
    "nlp", "natural language processing", "text mining",
    "word2vec", "glove", "fasttext",
}

# Good-to-have skills
PREFERRED_SKILLS = {
    "xgboost", "lightgbm", "catboost", "lambdamart",
    "spark", "kafka", "airflow", "dbt",
    "kubernetes", "docker", "aws", "gcp", "azure",
    "sql", "postgresql", "mongodb",
    "a/b testing", "experimentation", "statistics",
    "open source", "github contributions",
    "research", "published", "paper", "arxiv",
    "distributed systems", "high availability", "low latency",
}

# Non-relevant / red-flag roles
IRRELEVANT_ROLES = {
    "marketing", "sales", "hr", "recruiter", "customer support",
    "content", "seo", "graphic design", "accountant", "finance",
    "legal", "operations manager", "business development",
    "project coordinator", "procurement",
}

# Product company signals (positive)
PRODUCT_COMPANY_SIGNALS = {
    "saas", "product", "platform", "startup", "tech", "software",
    "fintech", "edtech", "healthtech", "proptech", "api", "b2b", "b2c",
    "marketplace", "consumer", "e-commerce", "ecommerce",
}

# Preferred India locations
INDIA_LOCATIONS = {
    "pune", "noida", "hyderabad", "mumbai", "bangalore", "bengaluru",
    "delhi", "chennai", "gurgaon", "gurugram", "ncr", "india",
    "new delhi", "greater noida", "navi mumbai", "thane"
}


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation for matching."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[_\-/]", " ", text)
    text = re.sub(r"[^\w\s@]", "", text)
    return text.strip()


def days_since(date_str: Optional[str]) -> int:
    """Days since a date string (YYYY-MM-DD). Returns large number if None."""
    if not date_str:
        return 9999
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (TODAY - d).days
    except Exception:
        return 9999


def sigmoid(x: float, scale: float = 1.0) -> float:
    """Sigmoid squash to (0, 1)."""
    return 1.0 / (1.0 + math.exp(-scale * x))


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# ─────────────────────────────────────────────────────────────────────────────
# SKILL SCORING
# ─────────────────────────────────────────────────────────────────────────────

def score_skills(candidate: Dict, req: JobRequirements) -> Tuple[float, str]:
    """
    Score skill match quality — NOT just keyword presence.
    Uses endorsement count + proficiency + duration as a TRUST multiplier
    to penalize keyword stuffers.
    
    Returns: (score 0-1, reasoning str)
    """
    skills_list = candidate.get("skills", [])
    if not skills_list:
        return 0.0, "No skills listed"

    core_hits = []
    preferred_hits = []
    total_trust_weighted_score = 0.0
    max_possible = 0.0

    # Also scan career descriptions for implicit skill evidence
    career_text = " ".join([
        normalize_text(job.get("description", "") + " " + job.get("title", ""))
        for job in candidate.get("career_history", [])
    ])
    summary_text = normalize_text(
        candidate.get("profile", {}).get("summary", "") +
        candidate.get("profile", {}).get("headline", "")
    )
    full_text = career_text + " " + summary_text

    # Check career text for core skills even if not listed
    career_core_matches = set()
    for skill in CORE_SKILLS:
        if skill.replace(" ", "") in full_text.replace(" ", ""):
            career_core_matches.add(skill)

    # Skill assessment scores from platform (very reliable signal)
    assessment_scores = candidate.get("redrob_signals", {}).get("skill_assessment_scores", {})

    for skill_obj in skills_list:
        name = normalize_text(skill_obj.get("name", ""))
        proficiency = skill_obj.get("proficiency", "beginner")
        endorsements = skill_obj.get("endorsements", 0)
        duration_months = skill_obj.get("duration_months", 0)

        # Trust multiplier: prevents keyword stuffing
        # High endorsements + long duration = reliable skill
        endorsement_trust = min(1.0, endorsements / 20.0)  # 20+ endorsements = full trust
        duration_trust = min(1.0, duration_months / 12.0)  # 12+ months = full trust
        proficiency_weight = {"beginner": 0.3, "intermediate": 0.6, "advanced": 0.85, "expert": 1.0}.get(proficiency, 0.3)

        # Platform assessment bonus
        assessment_bonus = 0.0
        for assess_skill, assess_score in assessment_scores.items():
            if normalize_text(assess_skill) in name or name in normalize_text(assess_skill):
                assessment_bonus = assess_score / 100.0 * 0.3  # up to 30% bonus
                break

        trust_score = (0.5 * proficiency_weight +
                      0.3 * endorsement_trust +
                      0.2 * duration_trust +
                      assessment_bonus)

        # Is this a core skill?
        is_core = any(core in name or name in core for core in CORE_SKILLS if len(core) > 3)
        is_preferred = any(pref in name or name in pref for pref in PREFERRED_SKILLS if len(pref) > 3)

        if is_core:
            max_possible += 2.0
            total_trust_weighted_score += trust_score * 2.0
            core_hits.append(name)
        elif is_preferred:
            max_possible += 1.0
            total_trust_weighted_score += trust_score * 1.0
            preferred_hits.append(name)

    # Bonus for career-implied skills (verified through work, not just listed)
    career_core_bonus = len(career_core_matches) * 0.5
    total_trust_weighted_score += career_core_bonus
    max_possible += max(len(CORE_SKILLS) * 0.3, 5.0)  # normalize against expected max

    # Base score
    if max_possible > 0:
        raw_score = total_trust_weighted_score / max_possible
    else:
        raw_score = 0.0

    # Bonus for having many distinct core skills
    unique_core_count = len(set(core_hits))
    coverage_bonus = min(0.3, unique_core_count * 0.05)  # up to 0.3 for 6+ core skills
    raw_score = clamp(raw_score + coverage_bonus)

    # Build reasoning
    core_str = ", ".join(list(set(core_hits))[:5]) if core_hits else "none"
    pref_str = ", ".join(list(set(preferred_hits))[:3]) if preferred_hits else "none"
    reasoning = (
        f"Core skills: {core_str} | Preferred: {pref_str} | "
        f"Career-implied: {len(career_core_matches)} | Score: {raw_score:.2f}"
    )

    return clamp(raw_score), reasoning


# ─────────────────────────────────────────────────────────────────────────────
# CAREER SIGNAL SCORING
# ─────────────────────────────────────────────────────────────────────────────

def score_career(candidate: Dict, req: JobRequirements) -> Tuple[float, str]:
    """
    Score career trajectory quality.
    Key signals:
    - ML/AI role titles (not just 'Engineer')
    - Product company experience (vs pure services)
    - Career progression (not title-chasing)
    - Relevance of work done (description analysis)
    - Fresher: 0 experience OK — use internships, projects
    """
    career = candidate.get("career_history", [])
    profile = candidate.get("profile", {})
    yoe = profile.get("years_of_experience", 0)
    current_title = normalize_text(profile.get("current_title", ""))
    current_industry = normalize_text(profile.get("current_industry", ""))

    reasoning_parts = []
    score = 0.0

    # ── 1. IRRELEVANT ROLE PENALTY ──────────────────────────────────────────
    is_irrelevant = any(role in current_title for role in IRRELEVANT_ROLES)
    if is_irrelevant:
        return 0.05, f"Irrelevant current role: {current_title}"

    # ── 2. CURRENT TITLE RELEVANCE ──────────────────────────────────────────
    ml_title_terms = {
        "machine learning", "ml engineer", "ai engineer", "data scientist",
        "research scientist", "nlp", "computer vision", "deep learning",
        "applied scientist", "ranking engineer", "search engineer",
        "recommendation", "retrieval", "nlp engineer", "ai researcher",
        "data engineer",  # adjacent, partial credit
        "backend engineer",  # adjacent if skills match
        "software engineer",  # general — partial credit
        "full stack", "platform engineer"
    }
    title_score = 0.0
    for term in ml_title_terms:
        if term in current_title:
            if term in {"machine learning", "ml engineer", "ai engineer", "nlp engineer",
                       "research scientist", "ranking engineer", "search engineer",
                       "recommendation", "applied scientist"}:
                title_score = 1.0
                reasoning_parts.append(f"Strong ML title: {current_title}")
                break
            elif term in {"data scientist", "deep learning", "nlp"}:
                title_score = max(title_score, 0.85)
            elif term in {"data engineer"}:
                title_score = max(title_score, 0.65)
            elif term in {"software engineer", "backend engineer", "full stack"}:
                title_score = max(title_score, 0.45)
    score += title_score * 0.25

    # ── 3. CAREER HISTORY ANALYSIS ──────────────────────────────────────────
    if not career:
        # No career history — fresher or student; rely on other signals
        reasoning_parts.append("No career history — fresher profile")
        score += 0.15  # neutral, not penalized
    else:
        # Check each role
        ml_role_months = 0
        services_only = True
        product_role_found = False
        description_ml_score = 0.0

        for job in career:
            title = normalize_text(job.get("title", ""))
            company = normalize_text(job.get("company", ""))
            industry = normalize_text(job.get("industry", ""))
            desc = normalize_text(job.get("description", ""))
            duration = job.get("duration_months", 0)
            company_size = job.get("company_size", "")

            # Services firm check
            is_services = any(sf in company for sf in SERVICES_FIRMS)
            if not is_services:
                services_only = False

            # Product company signals
            if any(signal in company or signal in industry for signal in PRODUCT_COMPANY_SIGNALS):
                product_role_found = True

            # Count ML role months
            for term in {"machine learning", "ml", "ai ", "data science", "nlp",
                          "deep learning", "research", "search", "ranking"}:
                if term in title:
                    ml_role_months += duration
                    break

            # Description quality for ML/retrieval work
            retrieval_terms_in_desc = sum(1 for term in CORE_SKILLS
                                          if term.replace(" ", "") in desc.replace(" ", ""))
            description_ml_score += min(1.0, retrieval_terms_in_desc / 5.0) * (duration / 12.0)

        # Services penalty
        if services_only and len(career) >= 2:
            score *= 0.5  # significant but not disqualify (they might have great skills)
            reasoning_parts.append("All career at services firms (penalized)")
        elif product_role_found:
            score += 0.1
            reasoning_parts.append("Product company experience found")

        # ML role experience credit
        ml_years = ml_role_months / 12.0
        ml_career_score = min(1.0, ml_years / 4.0)  # 4+ ML years = full score
        score += ml_career_score * 0.2

        # Description quality
        desc_score = min(1.0, description_ml_score / 3.0)
        score += desc_score * 0.2
        reasoning_parts.append(f"ML role years: {ml_years:.1f} | Desc quality: {desc_score:.2f}")

    # ── 4. FRESHERS: INTERNSHIP/PROJECT BONUS ───────────────────────────────
    if yoe <= 2:
        for job in career:
            title = normalize_text(job.get("title", ""))
            desc = normalize_text(job.get("description", ""))
            if any(t in title for t in ["intern", "trainee", "project", "research"]):
                retrieval_in_intern = sum(1 for t in CORE_SKILLS
                                          if t.replace(" ", "") in desc.replace(" ", ""))
                if retrieval_in_intern >= 2:
                    score += 0.15
                    reasoning_parts.append(f"Relevant internship/project: {job.get('title')}")
                    break

    score = clamp(score)
    return score, " | ".join(reasoning_parts) if reasoning_parts else "Career assessed"


# ─────────────────────────────────────────────────────────────────────────────
# EXPERIENCE FIT SCORING
# ─────────────────────────────────────────────────────────────────────────────

def score_experience(candidate: Dict, req: JobRequirements) -> Tuple[float, str]:
    """
    Score experience fit — fresher skewed.
    JD says 5-9 years but: "We'd seriously consider candidates outside the band if other signals strong."
    Freshers: compensate with certs, GitHub, education, assessments.
    """
    yoe = candidate.get("profile", {}).get("years_of_experience", 0)
    redrob = candidate.get("redrob_signals", {})
    certs = candidate.get("certifications", [])

    reasoning_parts = []

    # ── Base experience score (fresher-SKEWED curve) ────────────────────────
    # Freshers start high and build with signals — this is intentional!
    if yoe == 0:
        base_score = 0.65  # Fresher — starts competitive, signals take them higher
        reasoning_parts.append("Fresher (0 YoE) — potential-based scoring")
    elif yoe <= 1:
        base_score = 0.70
        reasoning_parts.append(f"Entry level ({yoe:.1f} YoE)")
    elif yoe <= 2:
        base_score = 0.72
        reasoning_parts.append(f"Junior ({yoe:.1f} YoE)")
    elif yoe <= 4:
        base_score = 0.75
        reasoning_parts.append(f"Mid-level ({yoe:.1f} YoE)")
    elif yoe <= 6:
        base_score = 0.80  # Sweet spot
        reasoning_parts.append(f"Ideal range ({yoe:.1f} YoE)")
    elif yoe <= 9:
        base_score = 0.82  # Still strong but less uplift vs freshers
        reasoning_parts.append(f"Senior ({yoe:.1f} YoE)")
    else:
        base_score = 0.65  # Over-experienced, penalized more
        reasoning_parts.append(f"Over-experienced ({yoe:.1f} YoE) — penalized")

    # ── Potential Boosters (stronger for freshers) ───────────────────────────
    # Freshers get 2-3× the bonus for the same signal vs experienced candidates
    is_fresher = yoe <= 2
    fresher_multiplier = 2.5 if is_fresher else 1.0
    fresher_bonus = 0.0

    # Certifications (learning velocity signal)
    ml_cert_keywords = {
        "machine learning", "deep learning", "nlp", "tensorflow", "pytorch",
        "aws", "google cloud", "azure", "data science", "python", "ai",
        "coursera", "udacity", "fast.ai", "hugging face", "kaggle",
        "google", "nvidia", "databricks", "snowflake", "langchain",
        "vector", "embedding", "llm", "bert", "transformer", "rag"
    }
    relevant_certs = []
    for cert in certs:
        cert_name = normalize_text(cert.get("name", ""))
        cert_issuer = normalize_text(cert.get("issuer", ""))
        cert_year = cert.get("year", 0)
        cert_text = cert_name + " " + cert_issuer
        if any(kw in cert_text for kw in ml_cert_keywords):
            recency = 1.0 if cert_year >= 2022 else 0.7
            per_cert = 0.06 * recency * fresher_multiplier
            fresher_bonus += per_cert
            relevant_certs.append(cert.get("name", ""))

    if relevant_certs:
        reasoning_parts.append(f"Relevant certs ({len(relevant_certs)}): {', '.join(relevant_certs[:3])}")

    # GitHub activity (strongest real project signal for freshers)
    github_score = redrob.get("github_activity_score", -1)
    if github_score > 0:
        github_bonus = min(0.25, (github_score / 100.0) * 0.25 * fresher_multiplier)
        fresher_bonus += github_bonus
        reasoning_parts.append(f"GitHub activity: {github_score:.0f}/100 (+{github_bonus:.3f})")

    # Platform skill assessments (verified competency — very important for freshers)
    assessments = redrob.get("skill_assessment_scores", {})
    if assessments:
        avg_assessment = np.mean(list(assessments.values()))
        assessment_bonus = min(0.20, (avg_assessment / 100.0) * 0.20 * fresher_multiplier)
        fresher_bonus += assessment_bonus
        reasoning_parts.append(f"Platform assessments avg: {avg_assessment:.0f} (+{assessment_bonus:.3f})")

    # Education quality is a strong proxy for fresher potential
    edu = candidate.get("education", [])
    if edu and is_fresher:
        best_tier = min(  # lower is better
            [{"tier_1": 1, "tier_2": 2, "tier_3": 3, "tier_4": 4, "unknown": 3}.get(
                e.get("tier", "unknown"), 3) for e in edu]
        )
        edu_bonus = {1: 0.15, 2: 0.08, 3: 0.03, 4: 0.0}.get(best_tier, 0.0)
        fresher_bonus += edu_bonus
        if edu_bonus > 0:
            reasoning_parts.append(f"Strong education bonus: tier_{best_tier} (+{edu_bonus:.2f})")

    # Cap fresher bonus (higher cap for freshers)
    max_bonus = 0.50 if is_fresher else 0.20
    fresher_bonus = min(max_bonus, fresher_bonus)

    final_score = clamp(base_score + fresher_bonus)
    return final_score, " | ".join(reasoning_parts) if reasoning_parts else "Experience assessed"


# ─────────────────────────────────────────────────────────────────────────────
# EDUCATION SCORING
# ─────────────────────────────────────────────────────────────────────────────

def score_education(candidate: Dict, req: JobRequirements) -> Tuple[float, str]:
    """
    Score education quality.
    Especially important for freshers where it's a key proxy for potential.
    """
    education = candidate.get("education", [])
    if not education:
        return 0.30, "No education data"

    best_score = 0.0
    reasoning_parts = []

    # Relevant fields of study
    relevant_fields = {
        "computer science", "cs", "information technology", "it",
        "electrical engineering", "ece", "electronics",
        "statistics", "mathematics", "maths", "data science",
        "artificial intelligence", "machine learning",
        "computational", "cognitive science"
    }

    for edu in education:
        tier = edu.get("tier", "unknown")
        degree = normalize_text(edu.get("degree", ""))
        field = normalize_text(edu.get("field_of_study", ""))
        grade_raw = edu.get("grade", "") or ""
        end_year = edu.get("end_year", 2000)

        # Tier score
        tier_score = {"tier_1": 0.95, "tier_2": 0.80, "tier_3": 0.55,
                      "tier_4": 0.35, "unknown": 0.40}.get(tier, 0.40)

        # Field relevance
        field_relevant = any(rf in field for rf in relevant_fields)
        field_bonus = 0.1 if field_relevant else 0.0

        # Degree level
        degree_bonus = 0.0
        if any(d in degree for d in ["ph.d", "phd", "doctorate"]):
            degree_bonus = 0.15
        elif any(d in degree for d in ["m.tech", "m.e.", "m.s.", "msc", "masters", "mba"]):
            degree_bonus = 0.08
        elif any(d in degree for d in ["b.tech", "b.e.", "bsc", "bachelor"]):
            degree_bonus = 0.0

        # GPA / grade parsing
        gpa_bonus = 0.0
        grade_text = str(grade_raw).lower()
        gpa_match = re.search(r"(\d+\.?\d*)\s*(cgpa|gpa|/10|/4)", grade_text)
        pct_match = re.search(r"(\d+\.?\d*)\s*%", grade_text)
        if gpa_match:
            gpa = float(gpa_match.group(1))
            scale = 4.0 if "/4" in grade_text else 10.0
            normalized = gpa / scale
            gpa_bonus = min(0.10, normalized * 0.10)
        elif pct_match:
            pct = float(pct_match.group(1))
            gpa_bonus = min(0.10, (pct - 60) / 40 * 0.10) if pct >= 60 else 0.0

        # Recency (graduated recently = fresher)
        recency_bonus = 0.05 if end_year >= 2022 else 0.0

        edu_score = clamp(tier_score + field_bonus + degree_bonus + gpa_bonus + recency_bonus)
        if edu_score > best_score:
            best_score = edu_score
            reasoning_parts = [
                f"Tier: {tier} | Field: {field[:20]} | Degree: {degree[:10]} | GPA: {grade_raw}"
            ]

    return clamp(best_score), " | ".join(reasoning_parts)


# ─────────────────────────────────────────────────────────────────────────────
# BEHAVIORAL SIGNAL SCORING
# ─────────────────────────────────────────────────────────────────────────────

def score_behavioral(candidate: Dict, req: JobRequirements) -> Tuple[float, str]:
    """
    Score behavioral/engagement signals from the Redrob platform.
    These act as a MULTIPLIER (availability) + ADDITIVE (engagement quality).
    
    Key insight from JD: "A perfect-on-paper candidate who hasn't logged in for
    6 months and has a 5% response rate is, for hiring purposes, not actually available."
    """
    redrob = candidate.get("redrob_signals", {})
    reasoning_parts = []
    score = 0.0

    # ── 1. AVAILABILITY SIGNALS (critical — are they actually hirable?) ──────
    open_to_work = redrob.get("open_to_work_flag", False)
    last_active = redrob.get("last_active_date", "")
    days_inactive = days_since(last_active)
    recruiter_response_rate = redrob.get("recruiter_response_rate", 0.0)
    notice_period = redrob.get("notice_period_days", 60)
    avg_response_hours = redrob.get("avg_response_time_hours", 48)

    # Open to work flag
    if open_to_work:
        score += 0.15
        reasoning_parts.append("Open to work ✓")
    else:
        score += 0.02

    # Last active recency
    if days_inactive <= 7:
        active_score = 0.20
        reasoning_parts.append("Active this week")
    elif days_inactive <= 30:
        active_score = 0.15
        reasoning_parts.append("Active this month")
    elif days_inactive <= 90:
        active_score = 0.08
        reasoning_parts.append(f"Last active {days_inactive}d ago")
    elif days_inactive <= 180:
        active_score = 0.03
        reasoning_parts.append(f"Semi-inactive ({days_inactive}d)")
    else:
        active_score = 0.0
        reasoning_parts.append(f"INACTIVE: {days_inactive}d — down-weighted")
    score += active_score

    # Recruiter response rate (key availability signal)
    if recruiter_response_rate >= 0.7:
        score += 0.15
        reasoning_parts.append(f"High response rate: {recruiter_response_rate:.0%}")
    elif recruiter_response_rate >= 0.4:
        score += 0.08
    elif recruiter_response_rate <= 0.1:
        score += 0.0
        reasoning_parts.append(f"Low response: {recruiter_response_rate:.0%}")

    # Notice period (shorter = better for hiring velocity)
    if notice_period <= 15:
        score += 0.08
        reasoning_parts.append(f"Short notice: {notice_period}d")
    elif notice_period <= 30:
        score += 0.05
    elif notice_period >= 90:
        score -= 0.03

    # Response time
    if avg_response_hours <= 4:
        score += 0.05
    elif avg_response_hours <= 24:
        score += 0.03

    # ── 2. ENGAGEMENT / QUALITY SIGNALS ─────────────────────────────────────
    profile_completeness = redrob.get("profile_completeness_score", 0)
    github_score = redrob.get("github_activity_score", -1)
    connection_count = redrob.get("connection_count", 0)
    endorsements_received = redrob.get("endorsements_received", 0)
    saved_by_recruiters = redrob.get("saved_by_recruiters_30d", 0)
    interview_completion = redrob.get("interview_completion_rate", 0.5)
    offer_acceptance = redrob.get("offer_acceptance_rate", -1)
    verified_email = redrob.get("verified_email", False)
    verified_phone = redrob.get("verified_phone", False)
    linkedin_connected = redrob.get("linkedin_connected", False)

    # Profile completeness
    score += (profile_completeness / 100.0) * 0.08

    # GitHub activity (real technical signal)
    if github_score > 0:
        score += (github_score / 100.0) * 0.10
        reasoning_parts.append(f"GitHub: {github_score:.0f}/100")

    # Recruiters saving profile (social proof)
    if saved_by_recruiters >= 5:
        score += 0.08
        reasoning_parts.append(f"Saved by {saved_by_recruiters} recruiters")
    elif saved_by_recruiters >= 2:
        score += 0.04

    # Endorsements received (peer validation)
    endorsement_score = min(0.05, endorsements_received / 100.0 * 0.05)
    score += endorsement_score

    # Interview completion (reliability signal)
    if interview_completion >= 0.8:
        score += 0.05
    elif interview_completion < 0.3:
        score -= 0.05

    # Offer acceptance (commitment signal)
    if offer_acceptance > 0.8:
        score += 0.03
    elif offer_acceptance >= 0:
        score += offer_acceptance * 0.03

    # Verification signals
    verification_count = sum([verified_email, verified_phone, linkedin_connected])
    score += verification_count * 0.02

    score = clamp(score)
    return score, " | ".join(reasoning_parts) if reasoning_parts else "Behavioral assessed"


# ─────────────────────────────────────────────────────────────────────────────
# LOCATION & SALARY FIT
# ─────────────────────────────────────────────────────────────────────────────

def score_location_fit(candidate: Dict, req: JobRequirements) -> float:
    """Quick location fit — Pune/Noida preferred per JD."""
    location = normalize_text(candidate.get("profile", {}).get("location", ""))
    country = normalize_text(candidate.get("profile", {}).get("country", ""))
    willing_to_relocate = candidate.get("redrob_signals", {}).get("willing_to_relocate", False)

    if any(loc in location for loc in INDIA_LOCATIONS):
        return 1.0
    if "india" in country:
        return 0.85 if willing_to_relocate else 0.70
    # Outside India — case-by-case per JD
    return 0.40 if willing_to_relocate else 0.30


# ─────────────────────────────────────────────────────────────────────────────
# ANTI-GAMING PENALTIES
# ─────────────────────────────────────────────────────────────────────────────

def compute_penalties(candidate: Dict, req: JobRequirements) -> Tuple[float, str]:
    """
    Detect and penalize gaming / mismatched profiles.
    Returns a penalty multiplier (0 to 1.0 — multiply final score by this).
    """
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    skills_list = candidate.get("skills", [])
    redrob = candidate.get("redrob_signals", {})
    reasoning_parts = []

    penalty = 1.0  # Start with no penalty

    # ── 1. KEYWORD STUFFER DETECTION ────────────────────────────────────────
    # Many skills listed but very low average endorsements
    if len(skills_list) >= 15:
        avg_endorsements = np.mean([s.get("endorsements", 0) for s in skills_list])
        if avg_endorsements < 3:
            penalty *= 0.70
            reasoning_parts.append(f"Keyword stuffer: {len(skills_list)} skills, avg {avg_endorsements:.1f} endorsements")

    # ── 2. TITLE MISMATCH WITH SKILLS ───────────────────────────────────────
    current_title = normalize_text(profile.get("current_title", ""))
    skill_names = [normalize_text(s.get("name", "")) for s in skills_list]
    if any(role in current_title for role in IRRELEVANT_ROLES):
        penalty *= 0.20  # Strong penalty for completely irrelevant roles
        reasoning_parts.append(f"Irrelevant role: {current_title}")

    # ── 3. TITLE-CHASER DETECTION ───────────────────────────────────────────
    # Many short stints at different companies = title optimization
    if len(career) >= 4:
        short_stints = sum(1 for job in career if job.get("duration_months", 99) < 18)
        if short_stints >= 3:
            penalty *= 0.85
            reasoning_parts.append(f"Title-chasing pattern: {short_stints} stints < 18 months")

    # ── 4. PURELY SERVICES CAREER WITH NO AI ────────────────────────────────
    if career:
        services_count = sum(
            1 for job in career
            if any(sf in normalize_text(job.get("company", "")) for sf in SERVICES_FIRMS)
        )
        if services_count == len(career) and len(career) >= 2:
            # Check if career descriptions redeem them
            all_desc = " ".join(normalize_text(j.get("description", "")) for j in career)
            ml_signals_in_services = sum(1 for skill in CORE_SKILLS
                                          if skill.replace(" ", "") in all_desc.replace(" ", ""))
            if ml_signals_in_services < 3:
                penalty *= 0.60
                reasoning_parts.append("Services-only career, minimal AI work in descriptions")

    # ── 5. COMPLETE INACTIVITY PENALTY ──────────────────────────────────────
    last_active = redrob.get("last_active_date", "")
    days_inactive = days_since(last_active)
    response_rate = redrob.get("recruiter_response_rate", 1.0)
    if days_inactive > 180 and response_rate < 0.15:
        penalty *= 0.50
        reasoning_parts.append("Effectively unavailable: inactive + low response")

    return clamp(penalty, 0.05, 1.0), " | ".join(reasoning_parts)


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE SCORING
# ─────────────────────────────────────────────────────────────────────────────

# Weights (sum to 1.0)
# Fresher-skewed: experience weight reduced, skill+education+behavioral boosted
WEIGHTS = {
    "skill":      0.30,   # What they can actually do — core signal
    "career":     0.20,   # How they've worked / trajectory
    "experience": 0.18,   # YoE + fresher boosters — raised, carries heavy fresher uplift
    "education":  0.12,   # Especially important for freshers as potential proxy
    "behavioral": 0.15,   # Platform signals — availability & engagement
    "location":   0.05,   # Pune/Noida preferred
}


def score_candidate(candidate: Dict, req: JobRequirements) -> Dict[str, Any]:
    """
    Compute full composite score for a candidate.
    Returns dict with total_score, component scores, reasoning string.
    
    Fresher-skewed: candidates with <=2 YoE get a score normalization boost
    that makes their top potential competitive with experienced candidates.
    """
    candidate_id = candidate.get("candidate_id", "")
    profile = candidate.get("profile", {})
    yoe = profile.get("years_of_experience", 0)

    # Component scores
    skill_score, skill_reason = score_skills(candidate, req)
    career_score, career_reason = score_career(candidate, req)
    exp_score, exp_reason = score_experience(candidate, req)
    edu_score, edu_reason = score_education(candidate, req)
    behav_score, behav_reason = score_behavioral(candidate, req)
    location_score = score_location_fit(candidate, req)

    # Penalty multiplier (anti-gaming)
    penalty_mult, penalty_reason = compute_penalties(candidate, req)

    # Weighted sum
    weighted = (
        skill_score * WEIGHTS["skill"] +
        career_score * WEIGHTS["career"] +
        exp_score * WEIGHTS["experience"] +
        edu_score * WEIGHTS["education"] +
        behav_score * WEIGHTS["behavioral"] +
        location_score * WEIGHTS["location"]
    )

    # ── FRESHER UPLIFT: Score normalization to make top freshers competitive ──
    # Freshers (<=2 YoE) who show strong signals (GitHub, certs, skills, education)
    # get a boosted final score using a potential-adjusted scaling.
    # This directly addresses the challenge requirement to skew toward freshers.
    if yoe <= 2:
        # Freshers earn up to 1.15× on their weighted score based on potential signals
        redrob = candidate.get("redrob_signals", {})
        github_score = redrob.get("github_activity_score", -1)
        assessments = redrob.get("skill_assessment_scores", {})
        certs = candidate.get("certifications", [])
        edu = candidate.get("education", [])
        
        potential_signals = 0
        if github_score > 50: potential_signals += 2
        elif github_score > 20: potential_signals += 1
        if assessments: potential_signals += min(2, len(assessments))
        if len(certs) >= 2: potential_signals += 2
        elif len(certs) == 1: potential_signals += 1
        if edu and any(e.get("tier") in ["tier_1", "tier_2"] for e in edu):
            potential_signals += 2
        if skill_score >= 0.4: potential_signals += 1
        if redrob.get("open_to_work_flag", False): potential_signals += 1
        
        # Scale: 0 signals = 1.0×, 5+ signals = 1.25×
        fresher_uplift = 1.0 + min(0.25, potential_signals * 0.05)
        weighted = min(0.95, weighted * fresher_uplift)  # cap at 0.95
    else:
        fresher_uplift = 1.0

    # Apply penalty as multiplier
    final_score = clamp(weighted * penalty_mult)

    # Build reasoning for the CSV output
    name = profile.get("anonymized_name", "Unknown")
    title = profile.get("current_title", "")
    company = profile.get("current_company", "")
    location = profile.get("location", "")

    fresher_tag = f" [FRESHER-UPLIFT×{fresher_uplift:.2f}]" if yoe <= 2 else ""
    reasoning_parts = [
        f"{name} | {title} @ {company} | {yoe:.1f}yr | {location}{fresher_tag}",
        f"Skills({skill_score:.2f}) Career({career_score:.2f}) Exp({exp_score:.2f}) "
        f"Edu({edu_score:.2f}) Behavioral({behav_score:.2f}) Location({location_score:.2f}) Penalty({penalty_mult:.2f})",
    ]
    if skill_reason:
        reasoning_parts.append(f"SKILLS: {skill_reason}")
    if career_reason:
        reasoning_parts.append(f"CAREER: {career_reason}")
    if exp_reason:
        reasoning_parts.append(f"EXP: {exp_reason}")
    if edu_reason:
        reasoning_parts.append(f"EDU: {edu_reason}")
    if behav_reason:
        reasoning_parts.append(f"BEHAVIORAL: {behav_reason}")
    if penalty_reason:
        reasoning_parts.append(f"PENALTIES: {penalty_reason}")

    # Truncate to fit CSV nicely
    full_reasoning = " || ".join(reasoning_parts)
    if len(full_reasoning) > 1000:
        full_reasoning = full_reasoning[:997] + "..."

    return {
        "candidate_id": candidate_id,
        "final_score": round(final_score, 6),
        "skill_score": round(skill_score, 4),
        "career_score": round(career_score, 4),
        "experience_score": round(exp_score, 4),
        "education_score": round(edu_score, 4),
        "behavioral_score": round(behav_score, 4),
        "location_score": round(location_score, 4),
        "penalty_multiplier": round(penalty_mult, 4),
        "reasoning": full_reasoning,
        "name": name,
        "title": title,
        "company": company,
        "yoe": yoe,
    }
