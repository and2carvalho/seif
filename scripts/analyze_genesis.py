"""
Genesis Analysis — Apply quality gate to conversa.md to measure
the convergence trajectory from speculation to grounded protocol.

Segments the conversation into turns and measures:
  - score (0-1)
  - grade (A-F)
  - status (SOLID/MIXED/WEAK/LOW_DATA)
  - stance verifiability_ratio
  - resonance composite_score

Outputs: CSV data + summary statistics + convergence analysis.
"""

import csv
import json
import re
import sys
from pathlib import Path
from dataclasses import asdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from seif.analysis.quality_gate import assess


CONVERSA_PATH = Path(__file__).parent.parent.parent / ".seif" / "private" / "conversa.md"
OUTPUT_CSV = Path(__file__).parent.parent / "scripts" / "genesis_analysis.csv"
OUTPUT_JSON = Path(__file__).parent.parent / "scripts" / "genesis_analysis.json"


def segment_turns(text: str) -> list[dict]:
    """Split conversa.md into turns by ## headers."""
    # Match turn headers: ## Usuário, ## Gemini, ## Turno N — ...
    pattern = re.compile(
        r'^## (Usuário|Gemini|Turno \d+|Claude)(.*)$',
        re.MULTILINE
    )

    matches = list(pattern.finditer(text))
    turns = []

    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        speaker = match.group(1).strip()
        title = match.group(2).strip().lstrip("—").strip()
        content = text[start:end].strip()

        # Skip very short turns (just "---" separators)
        if len(content) < 20:
            continue

        # Determine role
        if speaker == "Usuário":
            role = "human"
        else:
            role = "ai"

        turns.append({
            "turn_number": len(turns) + 1,
            "speaker": speaker,
            "title": title,
            "role": role,
            "content": content,
            "char_count": len(content),
        })

    return turns


def analyze_turns(turns: list[dict]) -> list[dict]:
    """Run quality gate on each turn and collect metrics."""
    results = []

    for turn in turns:
        content = turn["content"]

        # Truncate very long turns to avoid processing issues
        if len(content) > 5000:
            content = content[:5000]

        try:
            verdict = assess(content, role=turn["role"])
            result = {
                "turn": turn["turn_number"],
                "speaker": turn["speaker"],
                "title": turn["title"][:60],
                "role": turn["role"],
                "chars": turn["char_count"],
                "score": verdict.score,
                "grade": verdict.grade,
                "status": verdict.status,
                "stance_status": verdict.stance.status,
                "verifiability": round(verdict.stance.verifiability_ratio, 4),
                "resonance": round(verdict.triple_gate.composite_score, 4),
                "verifiable_count": verdict.stance.verifiable_count,
                "interpretive_count": verdict.stance.interpretive_count,
            }
        except Exception as e:
            result = {
                "turn": turn["turn_number"],
                "speaker": turn["speaker"],
                "title": turn["title"][:60],
                "role": turn["role"],
                "chars": turn["char_count"],
                "score": None,
                "grade": "ERR",
                "status": "ERROR",
                "stance_status": "ERROR",
                "verifiability": None,
                "resonance": None,
                "verifiable_count": 0,
                "interpretive_count": 0,
                "error": str(e),
            }

        results.append(result)

    return results


def compute_summary(results: list[dict]) -> dict:
    """Compute summary statistics and convergence metrics."""
    valid = [r for r in results if r["score"] is not None]
    if not valid:
        return {"error": "No valid results"}

    scores = [r["score"] for r in valid]
    verifiabilities = [r["verifiability"] for r in valid]

    # Split into phases (quarters)
    n = len(valid)
    q = n // 4
    phases = {
        "genesis": valid[:q],
        "formalization": valid[q:2*q],
        "proof": valid[2*q:3*q],
        "validation": valid[3*q:],
    }

    phase_stats = {}
    for name, phase in phases.items():
        if not phase:
            continue
        p_scores = [r["score"] for r in phase]
        p_verif = [r["verifiability"] for r in phase]
        phase_stats[name] = {
            "turns": len(phase),
            "avg_score": round(sum(p_scores) / len(p_scores), 4),
            "avg_verifiability": round(sum(p_verif) / len(p_verif), 4),
            "grade_distribution": {},
            "status_distribution": {},
        }
        for r in phase:
            g = r["grade"]
            s = r["status"]
            phase_stats[name]["grade_distribution"][g] = \
                phase_stats[name]["grade_distribution"].get(g, 0) + 1
            phase_stats[name]["status_distribution"][s] = \
                phase_stats[name]["status_distribution"].get(s, 0) + 1

    # Compute moving average (window=10) for convergence detection
    window = 10
    moving_avg = []
    for i in range(len(scores)):
        start = max(0, i - window + 1)
        chunk = scores[start:i+1]
        moving_avg.append(round(sum(chunk) / len(chunk), 4))

    # Convergence: is the moving average increasing over time?
    if len(moving_avg) > 20:
        first_half_avg = sum(moving_avg[:len(moving_avg)//2]) / (len(moving_avg)//2)
        second_half_avg = sum(moving_avg[len(moving_avg)//2:]) / (len(moving_avg) - len(moving_avg)//2)
        convergence_delta = round(second_half_avg - first_half_avg, 4)
    else:
        convergence_delta = None

    return {
        "total_turns": len(valid),
        "global_avg_score": round(sum(scores) / len(scores), 4),
        "global_avg_verifiability": round(sum(verifiabilities) / len(verifiabilities), 4),
        "min_score": round(min(scores), 4),
        "max_score": round(max(scores), 4),
        "phases": phase_stats,
        "convergence_delta": convergence_delta,
        "convergence_direction": (
            "CONVERGING" if convergence_delta and convergence_delta > 0.02
            else "STABLE" if convergence_delta and abs(convergence_delta) <= 0.02
            else "DIVERGING" if convergence_delta and convergence_delta < -0.02
            else "INSUFFICIENT_DATA"
        ),
        "moving_average_window": window,
        "moving_average": moving_avg,
    }


def main():
    print(f"Reading {CONVERSA_PATH}...")
    text = CONVERSA_PATH.read_text(encoding="utf-8")

    print("Segmenting into turns...")
    turns = segment_turns(text)
    print(f"  Found {len(turns)} turns")

    print("Running quality gate on each turn...")
    results = analyze_turns(turns)
    valid_count = sum(1 for r in results if r["score"] is not None)
    print(f"  Analyzed {valid_count}/{len(results)} turns successfully")

    print("Computing summary statistics...")
    summary = compute_summary(results)

    # Write CSV
    fieldnames = [
        "turn", "speaker", "title", "role", "chars",
        "score", "grade", "status", "stance_status",
        "verifiability", "resonance",
        "verifiable_count", "interpretive_count",
    ]
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"  CSV → {OUTPUT_CSV}")

    # Write JSON
    output = {
        "source": str(CONVERSA_PATH),
        "total_turns": len(turns),
        "results": results,
        "summary": summary,
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  JSON → {OUTPUT_JSON}")

    # Print summary
    print("\n" + "=" * 60)
    print("GENESIS CONVERGENCE ANALYSIS")
    print("=" * 60)
    print(f"Total turns analyzed: {summary['total_turns']}")
    print(f"Global avg score:     {summary['global_avg_score']}")
    print(f"Global avg verif.:    {summary['global_avg_verifiability']}")
    print(f"Score range:          {summary['min_score']} → {summary['max_score']}")
    print(f"Convergence:          {summary['convergence_direction']} (Δ = {summary['convergence_delta']})")

    print("\nPhase breakdown:")
    for name, stats in summary.get("phases", {}).items():
        print(f"  {name:15s}: avg_score={stats['avg_score']:.4f}  "
              f"avg_verif={stats['avg_verifiability']:.4f}  "
              f"turns={stats['turns']}  "
              f"grades={stats['grade_distribution']}")

    print("\nMoving average (first 5 → last 5):")
    ma = summary.get("moving_average", [])
    if len(ma) >= 10:
        print(f"  Start: {ma[:5]}")
        print(f"  End:   {ma[-5:]}")


if __name__ == "__main__":
    main()
