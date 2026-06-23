#!/usr/bin/env python3
"""
app.py — RedRob AI Ranker Web Server  (Multi-Format Edition)
=============================================================
Supported upload formats:
  .jsonl  — Primary format (one JSON object per line)
  .json   — JSON array of candidate objects
  .csv    — Tabular candidate data (columns auto-mapped)
  .xlsx   — Excel workbook (first sheet)
  .xls    — Legacy Excel workbook
  .pdf    — PDF with embedded JSONL or plain-text candidates
  .txt    — Plain text, treated as JSONL lines
  .tsv    — Tab-separated values

Usage:
    source venv/bin/activate
    python app.py
    → visit http://localhost:8765
"""

import os
import sys
import json
import uuid
import csv
import io
import re
import time
import threading
import logging
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, make_response

# ── Setup ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
WEB_DIR  = BASE_DIR / "web"
sys.path.insert(0, str(BASE_DIR))

app = Flask(__name__, static_folder=str(WEB_DIR))
app.config["MAX_CONTENT_LENGTH"] = 600 * 1024 * 1024  # 600 MB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("redrob-web")

# Supported extensions → MIME types
SUPPORTED_EXTENSIONS = {
    ".jsonl", ".json", ".csv", ".tsv",
    ".xlsx", ".xls", ".pdf", ".txt",
}

# ── In-memory job store ────────────────────────────────────────────────────────
JOBS: dict = {}


# ═══════════════════════════════════════════════════════════════════════════════
#  MULTI-FORMAT CANDIDATE PARSERS
# ═══════════════════════════════════════════════════════════════════════════════

def _normalize_candidate(data: dict, idx: int) -> dict:
    """
    Map any dict (from CSV, Excel, PDF, JSON) to the expected candidate schema.
    Fields that don't exist default gracefully — the scorer handles missing data.
    """
    # ── candidate_id ─────────────────────────────────────────────────────────
    cid = (
        data.get("candidate_id")
        or data.get("id")
        or data.get("ID")
        or data.get("Candidate ID")
        or data.get("CandidateID")
        or f"CAND_{idx:06d}"
    )

    # ── profile block ─────────────────────────────────────────────────────────
    profile = data.get("profile") or {}
    if not isinstance(profile, dict):
        profile = {}

    # Merge flat fields into profile if profile is empty/partial
    def _first(*keys):
        for k in keys:
            v = data.get(k) or profile.get(k)
            if v:
                return str(v)
        return ""

    if not profile.get("anonymized_name"):
        profile["anonymized_name"] = _first("name", "Name", "full_name", "FullName", "candidate_name")
    if not profile.get("current_title"):
        profile["current_title"] = _first("title", "Title", "current_title", "job_title", "JobTitle", "designation")
    if not profile.get("current_company"):
        profile["current_company"] = _first("company", "Company", "current_company", "employer", "Employer", "organization")
    if not profile.get("location"):
        profile["location"] = _first("location", "Location", "city", "City", "country")

    # YoE
    yoe_raw = (
        data.get("yoe")
        or data.get("YoE")
        or data.get("years_experience")
        or data.get("YearsExperience")
        or data.get("experience_years")
        or profile.get("yoe_claimed")
        or 0
    )
    try:
        profile["yoe_claimed"] = float(str(yoe_raw).replace("+", "").strip() or 0)
    except ValueError:
        profile["yoe_claimed"] = 0.0

    # ── skills ────────────────────────────────────────────────────────────────
    raw_skills = data.get("skills") or data.get("Skills") or data.get("skill_set") or []
    if isinstance(raw_skills, str):
        # "Python, TensorFlow, SQL"
        skill_list = [s.strip() for s in re.split(r"[,;|/]", raw_skills) if s.strip()]
        raw_skills = [
            {"name": s, "proficiency": "intermediate", "years_used": 1, "endorsements": 0}
            for s in skill_list
        ]
    elif isinstance(raw_skills, list):
        normalized = []
        for s in raw_skills:
            if isinstance(s, str):
                normalized.append({"name": s, "proficiency": "intermediate",
                                   "years_used": 1, "endorsements": 0})
            elif isinstance(s, dict):
                normalized.append(s)
        raw_skills = normalized

    # ── work_experience ───────────────────────────────────────────────────────
    work_exp = data.get("work_experience") or data.get("experience") or data.get("WorkExperience") or []
    if isinstance(work_exp, str):
        work_exp = []  # Can't parse free text reliably
    if not isinstance(work_exp, list):
        work_exp = []

    # ── education ─────────────────────────────────────────────────────────────
    edu = data.get("education") or data.get("Education") or []
    if isinstance(edu, str):
        edu = [{"degree": edu, "field": "", "institution": "", "tier": "unknown"}]
    if not isinstance(edu, list):
        edu = []

    # ── certifications ────────────────────────────────────────────────────────
    certs = data.get("certifications") or data.get("Certifications") or []
    if isinstance(certs, str):
        certs = [{"name": c.strip()} for c in certs.split(",") if c.strip()]
    if not isinstance(certs, list):
        certs = []

    # ── redrob_signals ────────────────────────────────────────────────────────
    signals = data.get("redrob_signals") or {}
    if not isinstance(signals, dict):
        signals = {}
    # Map flat columns into signals if present
    for flat_key, sig_key in [
        ("github_score", "github_activity_score"),
        ("response_rate", "recruiter_response_rate"),
        ("open_to_work", "open_to_work_flag"),
        ("last_active", "last_active_date"),
    ]:
        flat_val = data.get(flat_key)
        if flat_val is not None and sig_key not in signals:
            signals[sig_key] = flat_val

    return {
        "candidate_id":   str(cid),
        "profile":        profile,
        "skills":         raw_skills,
        "work_experience": work_exp,
        "education":      edu,
        "certifications": certs,
        "redrob_signals": signals,
    }


def _parse_jsonl(path: str) -> list:
    """Parse JSONL / TXT — one JSON object per line."""
    candidates = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                # If it's already in the expected schema, pass through
                if "candidate_id" in obj and "profile" in obj:
                    candidates.append(obj)
                else:
                    candidates.append(_normalize_candidate(obj, i))
            except json.JSONDecodeError:
                pass  # skip malformed lines
    return candidates


def _parse_json(path: str) -> list:
    """Parse JSON — array of candidate objects or single candidate."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [
            obj if ("candidate_id" in obj and "profile" in obj)
            else _normalize_candidate(obj, i)
            for i, obj in enumerate(data)
        ]
    elif isinstance(data, dict):
        # Single candidate or wrapper object
        if "candidates" in data and isinstance(data["candidates"], list):
            return [_normalize_candidate(c, i) for i, c in enumerate(data["candidates"])]
        return [_normalize_candidate(data, 0)]
    return []


def _parse_csv_or_tsv(path: str, delimiter: str = ",") -> list:
    """Parse CSV/TSV — each row becomes a candidate."""
    candidates = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for i, row in enumerate(reader):
            # Convert OrderedDict to plain dict, strip whitespace from keys
            clean = {k.strip(): v.strip() if isinstance(v, str) else v
                     for k, v in row.items() if k}
            candidates.append(_normalize_candidate(clean, i))
    return candidates


def _parse_excel(path: str) -> list:
    """Parse XLSX/XLS — first sheet, each row becomes a candidate."""
    import pandas as pd
    df = pd.read_excel(path, sheet_name=0, dtype=str)
    df = df.fillna("")
    candidates = []
    for i, row in enumerate(df.to_dict(orient="records")):
        clean = {k.strip(): str(v).strip() for k, v in row.items() if k}
        candidates.append(_normalize_candidate(clean, i))
    return candidates


def _parse_pdf(path: str) -> list:
    """
    Parse PDF — tries two strategies:
    1. Extract JSONL lines from embedded text
    2. Extract JSON blocks delimited by { }
    3. Fallback: treat each detected 'Name / Title' block as a candidate
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")

    full_text = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text.append(t)

    text = "\n".join(full_text)

    # ── Strategy 1: JSONL lines in PDF ────────────────────────────────────────
    candidates = []
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                candidates.append(
                    obj if ("candidate_id" in obj and "profile" in obj)
                    else _normalize_candidate(obj, i)
                )
                continue
            except json.JSONDecodeError:
                pass

    if candidates:
        return candidates

    # ── Strategy 2: JSON blocks anywhere in text ───────────────────────────────
    json_blocks = re.findall(r"\{[^{}]{20,}\}", text, re.DOTALL)
    for i, block in enumerate(json_blocks):
        try:
            obj = json.loads(block)
            candidates.append(_normalize_candidate(obj, i))
        except json.JSONDecodeError:
            pass

    if candidates:
        return candidates

    # ── Strategy 3: Heuristic name-based parsing ───────────────────────────────
    # Look for patterns like "Name: John | Title: ML Engineer"
    entries = re.split(r"\n{2,}", text)
    for i, entry in enumerate(entries):
        if len(entry.strip()) < 10:
            continue
        candidate = {}
        for pattern, key in [
            (r"(?i)(?:name|candidate)[:\-]\s*(.+)", "name"),
            (r"(?i)(?:title|designation|role)[:\-]\s*(.+)", "title"),
            (r"(?i)(?:company|employer|org(?:anization)?)[:\-]\s*(.+)", "company"),
            (r"(?i)(?:yoe|years?\s+of\s+exp)[:\-]\s*([\d\.]+)", "yoe"),
            (r"(?i)(?:location|city)[:\-]\s*(.+)", "location"),
            (r"(?i)(?:skills?)[:\-]\s*(.+)", "skills"),
        ]:
            m = re.search(pattern, entry)
            if m:
                candidate[key] = m.group(1).strip()
        if candidate:
            candidates.append(_normalize_candidate(candidate, i))

    return candidates if candidates else []


def load_candidates_multiformat(path: str) -> tuple[list, str]:
    """
    Detect file format by extension and parse accordingly.
    Returns (candidates_list, format_name).
    """
    ext = Path(path).suffix.lower()
    log.info(f"Parsing format: {ext!r} from {Path(path).name}")

    if ext in (".jsonl", ".txt"):
        return _parse_jsonl(path), "JSONL"
    elif ext == ".json":
        return _parse_json(path), "JSON"
    elif ext == ".csv":
        return _parse_csv_or_tsv(path, delimiter=","), "CSV"
    elif ext == ".tsv":
        return _parse_csv_or_tsv(path, delimiter="\t"), "TSV"
    elif ext in (".xlsx", ".xls"):
        return _parse_excel(path), "Excel"
    elif ext == ".pdf":
        return _parse_pdf(path), "PDF"
    else:
        # Try JSONL as fallback
        try:
            return _parse_jsonl(path), "JSONL (auto)"
        except Exception:
            raise ValueError(f"Unsupported format: {ext}. Supported: JSONL, JSON, CSV, TSV, XLSX, XLS, PDF, TXT")


# ═══════════════════════════════════════════════════════════════════════════════
#  STATIC FILE SERVING
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory(str(WEB_DIR), "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(str(WEB_DIR), path)


# ═══════════════════════════════════════════════════════════════════════════════
#  API: START A RANKING JOB
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/rank", methods=["POST"])
def api_rank():
    """
    POST /api/rank
    Form fields:
      use_default=true   → use ./dataset/candidates.jsonl on disk
      file=<upload>      → any supported format file
    Returns: { job_id, format, candidate_count_estimate }
    """
    job_id = str(uuid.uuid4())[:8]
    use_default = request.form.get("use_default", "false").lower() == "true"
    candidates_path = None
    original_ext    = ".jsonl"
    cleanup_after   = False

    if use_default:
        default_path = BASE_DIR / "dataset" / "candidates.jsonl"
        if not default_path.exists():
            return jsonify({"error": "dataset/candidates.jsonl not found on disk"}), 404
        candidates_path = str(default_path)
        original_ext    = ".jsonl"
        log.info(f"[{job_id}] Using default dataset")

    elif "file" in request.files and request.files["file"].filename:
        f   = request.files["file"]
        ext = Path(f.filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            return jsonify({"error": f"Unsupported format '{ext}'. Supported: {supported}"}), 400

        tmp_path = BASE_DIR / f"_tmp_{job_id}{ext}"
        f.save(str(tmp_path))
        candidates_path = str(tmp_path)
        original_ext    = ext
        cleanup_after   = True
        log.info(f"[{job_id}] Uploaded {ext!r} file: {f.filename} ({tmp_path.stat().st_size:,} bytes)")

    else:
        return jsonify({"error": "Provide a file or set use_default=true"}), 400

    # Initialize job
    JOBS[job_id] = {
        "status":     "queued",
        "progress":   0,
        "message":    "Queued…",
        "results":    None,
        "error":      None,
        "started_at": time.time(),
        "total":      0,
        "scored":     0,
        "format":     original_ext,
    }

    t = threading.Thread(
        target=_run_ranking,
        args=(job_id, candidates_path, original_ext, cleanup_after),
        daemon=True,
    )
    t.start()

    return jsonify({"job_id": job_id, "format": original_ext})


# ═══════════════════════════════════════════════════════════════════════════════
#  BACKGROUND RANKING THREAD
# ═══════════════════════════════════════════════════════════════════════════════

def _run_ranking(job_id: str, candidates_path: str, ext: str, cleanup_after: bool):
    """Load → parse format → parse JD → score → dual-track rank → store."""
    job = JOBS[job_id]
    try:
        from jd_parser import parse_jd
        from scorer import score_candidate
        import numpy as np

        # ── Stage 1: Parse file ───────────────────────────────────────────────
        job["status"]   = "loading"
        job["message"]  = f"Parsing {ext.upper().lstrip('.')} file…"
        job["progress"] = 3

        # For JSONL default, use the fast native loader
        if ext == ".jsonl":
            try:
                from rank import load_candidates
                candidates = load_candidates(candidates_path)
                fmt = "JSONL"
            except Exception:
                candidates, fmt = load_candidates_multiformat(candidates_path)
        else:
            candidates, fmt = load_candidates_multiformat(candidates_path)

        total = len(candidates)
        if total == 0:
            raise ValueError(
                f"No candidates found in the {fmt} file. "
                "Check that it contains valid candidate data."
            )

        job["total"]    = total
        job["message"]  = f"Loaded {total:,} candidates from {fmt}"
        job["progress"] = 12
        log.info(f"[{job_id}] Loaded {total:,} candidates (format: {fmt})")

        # ── Stage 2: Parse JD ─────────────────────────────────────────────────
        job["status"]   = "parsing"
        job["message"]  = "Parsing Job Description…"
        job["progress"] = 15

        req = parse_jd()
        job["progress"] = 18
        log.info(f"[{job_id}] JD parsed: {len(req.critical_skills)} critical skills")

        # ── Stage 3: Score ────────────────────────────────────────────────────
        job["status"]  = "scoring"
        job["message"] = f"Scoring {total:,} candidates…"

        all_results         = []
        fresher_results     = []
        experienced_results = []
        t0    = time.time()
        BATCH = max(1, min(2000, total // 20 or 500))

        for i, candidate in enumerate(candidates):
            try:
                result = score_candidate(candidate, req)
                all_results.append(result)
                yoe = result.get("yoe", 99)
                (fresher_results if yoe <= 2 else experienced_results).append(result)
            except Exception as e:
                cid = candidate.get("candidate_id", f"UNKNOWN_{i}")
                all_results.append({
                    "candidate_id":     str(cid),
                    "final_score":      0.0,
                    "reasoning":        f"Scoring error: {str(e)[:100]}",
                    "name": str(candidate.get("profile", {}).get("anonymized_name", "")),
                    "title": "", "company": "", "yoe": 99,
                    "skill_score": 0, "career_score": 0, "experience_score": 0,
                    "education_score": 0, "behavioral_score": 0,
                    "location_score": 0, "penalty_multiplier": 1,
                })

            if (i + 1) % BATCH == 0 or i == total - 1:
                elapsed   = max(time.time() - t0, 0.001)
                rate      = (i + 1) / elapsed
                remaining = (total - i - 1) / max(rate, 1)
                pct = 18 + int(((i + 1) / total) * 70)
                job["progress"] = pct
                job["scored"]   = i + 1
                job["message"]  = (
                    f"Scored {i+1:,}/{total:,} "
                    f"({rate:.0f}/s · ~{int(remaining)}s remaining)"
                )

        # ── Stage 4: Dual-track ranking ───────────────────────────────────────
        job["status"]   = "ranking"
        job["message"]  = "Building dual-track ranking…"
        job["progress"] = 90

        experienced_results.sort(key=lambda r: (-r["final_score"], r["candidate_id"]))
        fresher_results.sort(key=lambda r:     (-r["final_score"], r["candidate_id"]))

        top_exp    = experienced_results[:70]
        top_fresh  = fresher_results[:30]
        combined   = sorted(top_exp + top_fresh, key=lambda r: (-r["final_score"], r["candidate_id"]))
        top100     = combined[:100]

        for r in top100:
            r["track"] = "fresher" if r.get("yoe", 99) <= 2 else "experienced"

        all_scores = [r["final_score"] for r in all_results]
        stats = {
            "total_candidates":    total,
            "format":              fmt,
            "freshers_in_top100":  sum(1 for r in top100 if r.get("yoe", 99) <= 2),
            "avg_score_top100":    round(float(np.mean([r["final_score"] for r in top100])), 4) if top100 else 0,
            "max_score":           round(float(np.max(all_scores)),            4) if all_scores else 0,
            "p99_score":           round(float(np.percentile(all_scores, 99)), 4) if all_scores else 0,
            "p50_score":           round(float(np.percentile(all_scores, 50)), 4) if all_scores else 0,
            "runtime_seconds":     round(time.time() - t0, 1),
        }

        job["results"]  = {"top100": top100, "stats": stats}
        job["status"]   = "done"
        job["progress"] = 100
        job["message"]  = (
            f"Done! Ranked {total:,} from {fmt} "
            f"in {stats['runtime_seconds']}s"
        )
        log.info(f"[{job_id}] Complete: {total:,} candidates, {stats['runtime_seconds']}s")

    except Exception as e:
        job["status"]  = "error"
        job["error"]   = str(e)
        job["message"] = f"Error: {str(e)[:200]}"
        log.exception(f"[{job_id}] Failed: {e}")

    finally:
        if cleanup_after and os.path.exists(candidates_path):
            os.unlink(candidates_path)


# ═══════════════════════════════════════════════════════════════════════════════
#  API: POLL STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/status/<job_id>")
def api_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    resp = {
        "status":   job["status"],
        "progress": job["progress"],
        "message":  job["message"],
        "total":    job["total"],
        "scored":   job["scored"],
    }
    if job["status"] == "done":
        resp["results"] = job["results"]
    elif job["status"] == "error":
        resp["error"] = job["error"]

    return jsonify(resp)


# ═══════════════════════════════════════════════════════════════════════════════
#  API: DOWNLOAD CSV
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/download/<job_id>")
def api_download(job_id):
    job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "Results not ready"}), 404

    top100 = job["results"]["top100"]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["candidate_id", "rank", "score", "reasoning"])

    scores = [r["final_score"] for r in top100]
    for i in range(1, len(scores)):
        if scores[i] > scores[i - 1]:
            scores[i] = scores[i - 1]

    for rank_idx, (result, adj_score) in enumerate(zip(top100, scores)):
        reasoning = result.get("reasoning", "").replace("\n", " ").replace("\r", " ")
        writer.writerow([result["candidate_id"], rank_idx + 1, f"{adj_score:.6f}", reasoning])

    output.seek(0)
    resp = make_response(output.getvalue())
    resp.headers["Content-Disposition"] = f"attachment; filename=submission_{job_id}.csv"
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    return resp


# ═══════════════════════════════════════════════════════════════════════════════
#  API: SUPPORTED FORMATS (for UI)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/formats")
def api_formats():
    return jsonify({
        "formats": [
            {"ext": ".jsonl", "label": "JSONL",  "desc": "Primary format — one JSON per line",  "icon": "{}"},
            {"ext": ".json",  "label": "JSON",   "desc": "JSON array of candidate objects",      "icon": "[]"},
            {"ext": ".csv",   "label": "CSV",    "desc": "Comma-separated values — columns auto-mapped", "icon": "⊞"},
            {"ext": ".xlsx",  "label": "Excel",  "desc": "Excel workbook — first sheet",         "icon": "⊞"},
            {"ext": ".xls",   "label": "Excel",  "desc": "Legacy Excel workbook",                "icon": "⊞"},
            {"ext": ".pdf",   "label": "PDF",    "desc": "PDF with embedded candidate data",     "icon": "📄"},
            {"ext": ".txt",   "label": "TXT",    "desc": "Plain text treated as JSONL",          "icon": "≡"},
            {"ext": ".tsv",   "label": "TSV",    "desc": "Tab-separated values",                 "icon": "⊞"},
        ]
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    log.info("=" * 55)
    log.info("  RedRob AI Ranker — Web Server (Multi-Format)")
    log.info(f"  Serving from: {WEB_DIR}")
    log.info("  Supported: JSONL, JSON, CSV, TSV, XLSX, XLS, PDF, TXT")
    log.info("  → http://localhost:8765")
    log.info("=" * 55)
    app.run(host="0.0.0.0", port=8765, debug=False, threaded=True)
