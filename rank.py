#!/usr/bin/env python3
"""
rank.py — Main Ranking Script for RedRob AI Challenge
======================================================
Usage:
    python rank.py --candidates ./dataset/candidates.jsonl --out ./submission.csv

Features:
- No external APIs / no network calls during ranking
- Multi-signal hybrid scoring (skills + career + experience + education + behavioral)
- Fresher-skewed: 0 YoE is not penalized — compensated by certs, GitHub, assessments
- Anti-gaming: endorsement trust multiplier, services-firm penalty, inactivity penalty
- TF-IDF semantic layer for skill-text matching against JD
- Runtime: ~60-90s for 90K candidates on CPU
"""

import json
import csv
import sys
import time
import argparse
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Any

# Local modules
from jd_parser import parse_jd
from scorer import score_candidate

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("redrob-ranker")


# ─────────────────────────────────────────────────────────────────────────────
# LOADING
# ─────────────────────────────────────────────────────────────────────────────

def load_candidates(path: str) -> List[Dict]:
    """Load all candidates from JSONL file."""
    candidates = []
    path_obj = Path(path)
    if not path_obj.exists():
        log.error(f"Candidates file not found: {path}")
        sys.exit(1)

    log.info(f"Loading candidates from {path}...")
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                candidates.append(json.loads(line))
            except json.JSONDecodeError as e:
                log.warning(f"Skipping malformed line {i+1}: {e}")

    log.info(f"Loaded {len(candidates):,} candidates")
    return candidates


# ─────────────────────────────────────────────────────────────────────────────
# RANKING
# ─────────────────────────────────────────────────────────────────────────────

def rank_candidates(candidates: List[Dict]) -> List[Dict]:
    """
    Score all candidates and return top 100 ranked list.
    
    DUAL-TRACK SYSTEM (fresher-skewed per challenge requirement):
    - Track A: ALL candidates scored fairly → Top 70 non-freshers
    - Track B: FRESHERS ONLY (YoE ≤ 2) scored with uplift → Top 30 freshers
    - Final: Merge and re-rank by score (both tracks compete on same score)
    
    This ensures qualified freshers always appear in the shortlist,
    even when the overall population skews heavily toward experienced candidates.
    """
    req = parse_jd()
    log.info("Job requirements parsed successfully")
    log.info(f"Critical skills: {len(req.critical_skills)}")
    log.info(f"Preferred skills: {len(req.preferred_skills)}")

    log.info(f"Scoring {len(candidates):,} candidates...")
    t0 = time.time()

    all_results = []
    fresher_results = []
    experienced_results = []

    batch_size = 5000
    for i, candidate in enumerate(candidates):
        try:
            result = score_candidate(candidate, req)
            all_results.append(result)
            yoe = result.get("yoe", 99)
            if yoe <= 2:
                fresher_results.append(result)
            else:
                experienced_results.append(result)
        except Exception as e:
            log.warning(f"Error scoring {candidate.get('candidate_id', f'#{i}')}: {e}")
            all_results.append({
                "candidate_id": candidate.get("candidate_id", f"UNKNOWN_{i}"),
                "final_score": 0.0,
                "reasoning": f"Scoring error: {str(e)[:100]}",
                "name": "", "title": "", "company": "", "yoe": 99
            })

        if (i + 1) % batch_size == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            remaining = (len(candidates) - i - 1) / rate
            log.info(
                f"  Scored {i+1:,}/{len(candidates):,} "
                f"({rate:.0f}/s, ~{remaining:.0f}s remaining)"
            )

    elapsed = time.time() - t0
    log.info(f"Scoring complete: {len(all_results):,} candidates in {elapsed:.1f}s "
             f"({len(all_results)/elapsed:.0f} candidates/s)")

    # ── DUAL-TRACK RANKING ───────────────────────────────────────────────────────
    # Sort tracks by score descending
    experienced_results.sort(key=lambda r: (-r["final_score"], r["candidate_id"]))
    fresher_results.sort(key=lambda r: (-r["final_score"], r["candidate_id"]))

    log.info(f"\n=== DUAL TRACK STATS ===")
    log.info(f"  Experienced (>2 YoE): {len(experienced_results):,}")
    log.info(f"  Freshers (\u22642 YoE): {len(fresher_results):,}")

    # Allocate: 30 fresher slots + 70 experienced slots
    # Merge and re-rank purely by score to ensure highest scorers rank highest
    FRESHER_QUOTA = 30
    top_experienced = experienced_results[:70]
    top_freshers = fresher_results[:FRESHER_QUOTA]

    # Combine and sort by score (freshers already have uplift in their score)
    combined = top_experienced + top_freshers
    combined.sort(key=lambda r: (-r["final_score"], r["candidate_id"]))
    top100 = combined[:100]

    # Count actual freshers in final top 100
    actual_freshers = sum(1 for r in top100 if r.get("yoe", 99) <= 2)
    log.info(f"  Freshers in final top 100: {actual_freshers}")

    # Print top 10 preview
    log.info("\n=== TOP 10 CANDIDATES ===")
    for i, r in enumerate(top100[:10]):
        fresher_tag = " [FRESHER]" if r.get("yoe", 99) <= 2 else ""
        log.info(
            f"  #{i+1} {r['candidate_id']} | Score: {r['final_score']:.4f} | "
            f"{r.get('title', '')} @ {r.get('company', '')} | YoE: {r.get('yoe', 0):.1f}{fresher_tag}"
        )

    log.info("\n=== TOP FRESHERS IN SHORTLIST ===")
    fresher_in_list = [r for r in top100 if r.get("yoe", 99) <= 2]
    for i, r in enumerate(fresher_in_list[:10]):
        rank_pos = top100.index(r) + 1
        log.info(
            f"  Rank #{rank_pos} {r['candidate_id']} | Score: {r['final_score']:.4f} | "
            f"{r.get('title', '')} | YoE: {r.get('yoe', 0):.1f}"
        )

    log.info("\n=== SCORE DISTRIBUTION ===")
    all_scores = [r["final_score"] for r in all_results]
    log.info(f"  Max: {max(all_scores):.4f}")
    log.info(f"  P99: {np.percentile(all_scores, 99):.4f}")
    log.info(f"  P95: {np.percentile(all_scores, 95):.4f}")
    log.info(f"  P90: {np.percentile(all_scores, 90):.4f}")
    log.info(f"  Mean: {np.mean(all_scores):.4f}")
    log.info(f"  P10: {np.percentile(all_scores, 10):.4f}")
    log.info(f"  Min: {min(all_scores):.4f}")

    yoe_vals = [r.get("yoe", 0) for r in top100 if "yoe" in r]
    freshers_in_top100 = sum(1 for y in yoe_vals if y <= 2)
    log.info(f"\n=== TOP 100 YoE PROFILE ===")
    log.info(f"  Freshers (≤2 YoE): {freshers_in_top100}/100")
    log.info(f"  Avg YoE: {np.mean(yoe_vals):.1f}")
    log.info(f"  Min YoE: {min(yoe_vals):.1f}")
    log.info(f"  Max YoE: {max(yoe_vals):.1f}")

    return top100


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

def write_submission(ranked: List[Dict], out_path: str) -> None:
    """
    Write the submission CSV in the required format:
    candidate_id, rank, score, reasoning
    
    Rules:
    - Exactly 100 data rows
    - Scores non-increasing by rank
    - Tie-break: candidate_id ascending
    - UTF-8 encoded
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Normalize scores to ensure strict non-increasing order
    # (minor floating point jitter could cause issues)
    scores = [r["final_score"] for r in ranked]
    
    # Ensure non-increasing (should already be sorted, but be safe)
    for i in range(1, len(scores)):
        if scores[i] > scores[i-1]:
            scores[i] = scores[i-1]
    
    log.info(f"Writing submission to {out_path}...")

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])

        for rank_idx, (result, adj_score) in enumerate(zip(ranked, scores)):
            rank = rank_idx + 1
            candidate_id = result["candidate_id"]
            
            # Score rounded to 6 decimal places
            score_str = f"{adj_score:.6f}"
            
            # Reasoning: clean, escaped
            reasoning = result.get("reasoning", "")
            # Remove any characters that could break CSV
            reasoning = reasoning.replace("\n", " ").replace("\r", " ")

            writer.writerow([candidate_id, rank, score_str, reasoning])

    log.info(f"Submission written: {out_path}")
    log.info(f"  Rows: 100 data rows + 1 header = 101 total")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="RedRob AI Candidate Ranking System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rank.py --candidates ./dataset/candidates.jsonl --out ./submission.csv
  python rank.py --candidates ./candidates.jsonl --out ./my_team.csv
        """
    )
    parser.add_argument(
        "--candidates", "-c",
        required=True,
        help="Path to candidates.jsonl file"
    )
    parser.add_argument(
        "--out", "-o",
        required=True,
        help="Output CSV path (e.g. submission.csv)"
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=100,
        help="Number of candidates to output (default: 100)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    log.info("=" * 60)
    log.info("  RedRob AI Candidate Ranking System")
    log.info("  Multi-Signal Hybrid Scorer (No-API, Local-Only)")
    log.info("=" * 60)

    # Load candidates
    candidates = load_candidates(args.candidates)

    # Rank
    top_n = rank_candidates(candidates)[:args.top_n]

    # Write output
    write_submission(top_n, args.out)

    log.info("\n✅ Done! Run validation with:")
    log.info(f"   python dataset/validate_submission.py {args.out}")


if __name__ == "__main__":
    main()
