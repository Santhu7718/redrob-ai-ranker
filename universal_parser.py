"""
universal_parser.py
-------------------
Reads candidate data in ANY format:
  - CSV (Google Forms export, custom spreadsheets)
  - Excel (.xlsx, .xls)
  - JSON (array of objects)
  - JSONL (one JSON object per line - the original challenge format)

Auto-detects column semantics and normalizes into a flat dict
that the universal_scorer can work with.
"""

import json
import io
import re
import pandas as pd
from typing import List, Dict, Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# COLUMN ALIAS MAP
# Maps common column name patterns → canonical field names
# ─────────────────────────────────────────────────────────────────────────────
COLUMN_ALIASES = {
    # Name
    "name": ["name", "full name", "fullname", "candidate name", "applicant name",
             "your name", "applicant", "respondent name"],
    # Email
    "email": ["email", "e-mail", "email address", "mail", "contact email"],
    # Phone
    "phone": ["phone", "mobile", "contact", "phone number", "mobile number", "contact number"],
    # Experience
    "yoe": ["years of experience", "experience", "yoe", "years_of_experience",
            "work experience", "total experience", "exp", "years exp",
            "how many years", "experience (years)", "total work experience"],
    # Skills
    "skills": ["skills", "technical skills", "key skills", "skill set",
               "technologies", "tech stack", "tools", "programming skills",
               "competencies", "expertise", "what skills do you have"],
    # Current/Last Role
    "title": ["current title", "designation", "role", "job title", "position",
              "current role", "current position", "current designation",
              "job role", "title", "current job title", "your current role"],
    # Company
    "company": ["company", "current company", "employer", "organization",
                "organisation", "current employer", "workplace", "company name"],
    # Location
    "location": ["location", "city", "current location", "where are you based",
                 "city/state", "place", "residing city", "state"],
    # Education
    "education": ["education", "degree", "qualification", "highest qualification",
                  "educational qualification", "highest degree", "academic background"],
    # College / Institution
    "college": ["college", "university", "institution", "school", "alma mater",
                "college/university", "institute"],
    # GPA / Marks
    "gpa": ["gpa", "cgpa", "percentage", "marks", "grade", "score",
            "academic score", "aggregate", "% marks"],
    # GitHub
    "github": ["github", "github url", "github profile", "github link",
               "github username", "your github"],
    # LinkedIn
    "linkedin": ["linkedin", "linkedin url", "linkedin profile", "linkedin link"],
    # Portfolio / Resume
    "portfolio": ["portfolio", "resume", "cv", "resume link", "portfolio url",
                  "resume/cv link", "your resume"],
    # Job Objective / Summary
    "summary": ["summary", "bio", "about", "objective", "profile summary",
                "tell us about yourself", "career objective", "introduction"],
    # Notice Period
    "notice": ["notice period", "notice", "joining time", "available from",
               "earliest joining date", "when can you join"],
    # Expected Salary
    "salary": ["expected salary", "ctc", "expected ctc", "salary expectation",
               "expected compensation", "salary"],
    # Certifications
    "certifications": ["certifications", "certificates", "certifications/courses",
                       "courses", "training", "online courses", "moocs"],
    # Projects
    "projects": ["projects", "key projects", "notable projects", "project experience"],
    # Open to work / Availability
    "open_to_work": ["open to work", "actively looking", "available", "job search status",
                     "currently looking", "are you open to opportunities"],
}


def _normalize_col(col: str) -> str:
    """Lowercase, strip whitespace, collapse spaces."""
    return re.sub(r'\s+', ' ', col.lower().strip())


def detect_field(col: str, aliases: Dict[str, List[str]]) -> Optional[str]:
    """Given a raw column name, return the canonical field name or None."""
    nc = _normalize_col(col)
    for field, patterns in aliases.items():
        for pattern in patterns:
            if pattern in nc or nc in pattern:
                return field
    return None


def parse_any_format(file_content: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Main entry point. Takes raw file bytes and filename.
    Returns list of normalized candidate dicts.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"

    if ext == "jsonl":
        return _parse_jsonl(file_content)
    elif ext == "json":
        return _parse_json(file_content)
    elif ext in ("xlsx", "xls"):
        return _parse_excel(file_content, ext)
    else:  # Default to CSV
        return _parse_csv(file_content)


def _parse_jsonl(content: bytes) -> List[Dict]:
    """Handle the original challenge JSONL format (nested structure)."""
    results = []
    for i, line in enumerate(content.decode("utf-8", errors="replace").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            # Check if it's the nested challenge format
            if "profile" in obj and "skills" in obj:
                results.append(_normalize_challenge_format(obj))
            else:
                # Flat JSON object
                results.append(_normalize_flat(obj))
        except json.JSONDecodeError:
            pass
    return results


def _parse_json(content: bytes) -> List[Dict]:
    """Handle JSON file - either array or single object."""
    try:
        data = json.loads(content.decode("utf-8", errors="replace"))
        if isinstance(data, list):
            candidates = []
            for obj in data:
                if "profile" in obj and "skills" in obj:
                    candidates.append(_normalize_challenge_format(obj))
                else:
                    candidates.append(_normalize_flat(obj))
            return candidates
        elif isinstance(data, dict):
            if "profile" in data:
                return [_normalize_challenge_format(data)]
            return [_normalize_flat(data)]
    except Exception:
        pass
    return []


def _parse_csv(content: bytes) -> List[Dict]:
    """Parse CSV (Google Forms export or custom) with auto column detection."""
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str)
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(content), dtype=str, encoding="latin-1")
        except Exception:
            return []
    return _df_to_candidates(df)


def _parse_excel(content: bytes, ext: str) -> List[Dict]:
    """Parse Excel file."""
    try:
        df = pd.read_excel(io.BytesIO(content), dtype=str)
    except Exception:
        return []
    return _df_to_candidates(df)


def _df_to_candidates(df: pd.DataFrame) -> List[Dict]:
    """Convert a DataFrame (from CSV/Excel) to normalized candidate dicts."""
    # Map columns to canonical names
    col_map = {}  # raw_col -> canonical_field
    for col in df.columns:
        field = detect_field(col, COLUMN_ALIASES)
        if field and field not in col_map.values():  # first match wins
            col_map[col] = field

    candidates = []
    for idx, row in df.iterrows():
        candidate = {"candidate_id": f"ROW_{idx + 1:04d}", "_raw_row": dict(row)}

        # Map detected columns
        for raw_col, field in col_map.items():
            val = row.get(raw_col, "")
            if pd.isna(val):
                val = ""
            candidate[field] = str(val).strip()

        # For unmapped columns, keep them under their original name
        mapped_cols = set(col_map.keys())
        for col in df.columns:
            if col not in mapped_cols:
                val = row.get(col, "")
                if not pd.isna(val):
                    candidate[f"_raw_{col}"] = str(val).strip()

        # Generate a stable ID if we have name/email
        if candidate.get("name") and candidate.get("email"):
            candidate["candidate_id"] = f"CAND_{abs(hash(candidate['email'])) % 100000:05d}"
        elif candidate.get("name"):
            candidate["candidate_id"] = f"CAND_{abs(hash(candidate['name'])) % 100000:05d}"

        candidates.append(candidate)

    return candidates


def _normalize_flat(obj: Dict) -> Dict:
    """Normalize a flat JSON object using alias detection."""
    candidate = {"candidate_id": obj.get("candidate_id", obj.get("id", "UNKNOWN")),
                 "_raw_row": obj}
    for key, val in obj.items():
        field = detect_field(key, COLUMN_ALIASES)
        if field and field not in candidate:
            candidate[field] = str(val) if val is not None else ""
        else:
            candidate[key] = val  # keep original too
    return candidate


def _normalize_challenge_format(obj: Dict) -> Dict:
    """Convert the challenge's nested JSONL format to flat canonical form."""
    profile = obj.get("profile", {})
    redrob = obj.get("redrob_signals", {})
    edu_list = obj.get("education", [])
    skills_list = obj.get("skills", [])
    certs_list = obj.get("certifications", [])
    jobs_list = obj.get("work_experience", [])

    # Flatten skills to comma-separated
    skills_str = ", ".join([s.get("name", "") for s in skills_list if s.get("name")])
    # Flatten education
    edu_str = ""
    edu_tier = "unknown"
    gpa_str = ""
    if edu_list:
        best = edu_list[0]
        edu_str = f"{best.get('degree', '')} from {best.get('institution', '')}"
        edu_tier = best.get("tier", "unknown")
        gpa_str = str(best.get("gpa", best.get("percentage", "")))

    # Flatten certifications
    certs_str = ", ".join([c.get("name", "") for c in certs_list if c.get("name")])

    # Flatten work history
    career_str = ""
    if jobs_list:
        career_str = " | ".join([
            f"{j.get('title', '')} @ {j.get('company', '')}"
            for j in jobs_list[:5]
        ])

    return {
        "candidate_id": obj.get("candidate_id", ""),
        "name": profile.get("anonymized_name", ""),
        "title": profile.get("current_title", ""),
        "company": profile.get("current_company", ""),
        "location": profile.get("location", ""),
        "yoe": str(profile.get("years_of_experience", 0)),
        "skills": skills_str,
        "education": edu_str,
        "college": "",
        "gpa": gpa_str,
        "certifications": certs_str,
        "summary": career_str,
        "github": str(redrob.get("github_activity_score", -1)),
        "open_to_work": "yes" if redrob.get("open_to_work_flag") else "no",
        "_edu_tier": edu_tier,
        "_skills_list": skills_list,
        "_certs_list": certs_list,
        "_redrob": redrob,
        "_raw_obj": obj,
    }
