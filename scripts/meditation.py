"""
Meditation — Periodic system identification for the SEIF protocol.

The "tuning fork" (diapasão) of the protocol. Runs periodically to:
  1. Aggregate behavioral observations → compute model reliability
  2. Check model profile staleness (>7 days without update)
  3. Run genesis convergence analysis (quality gate on historical data)
  4. Blue Team security audit
  5. Self-healing report (errors detected and corrected)

Maps to H(s) = 9/(s² + 3s + 6):
  - This script IS the system identification step
  - It measures the actual response and compares to theoretical model
  - Drift between measured and theoretical triggers corrective action

Usage:
  python scripts/meditation.py                    # full meditation
  python scripts/meditation.py --behavioral       # behavioral only
  python scripts/meditation.py --convergence      # convergence only
  python scripts/meditation.py --security         # blue team only
  python scripts/meditation.py --report           # generate report only
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from seif.bridge.model_tracker import (
    load_behavioral_observations,
    compute_behavioral_stats,
    update_all_profiles,
    describe_profiles,
    BEHAVIOR_TYPES,
)


def behavioral_audit() -> dict:
    """Aggregate behavioral observations across all models."""
    obs_dir = Path.home() / ".seif" / "model_observations"
    if not obs_dir.exists():
        return {"status": "NO_DATA", "models": {}}

    models = {}
    backends = set()
    for f in obs_dir.glob("*_behavior.jsonl"):
        backends.add(f.stem.replace("_behavior", ""))

    for backend in sorted(backends):
        obs = load_behavioral_observations(backend)
        if not obs:
            continue
        stats = compute_behavioral_stats(obs)
        models[backend] = {
            "incidents": stats["total_incidents"],
            "reliability": stats["measured_reliability"],
            "top_failures": [
                {"type": fm["type"], "count": fm["count"]}
                for fm in stats["failure_modes"][:3]
            ],
            "last_incident": stats["last_incident"][:10],
        }

    return {
        "status": "OK" if models else "NO_DATA",
        "models": models,
        "total_models": len(models),
        "total_incidents": sum(m["incidents"] for m in models.values()),
    }


def profile_staleness_check() -> dict:
    """Check which model profiles are stale (>7 days without update)."""
    models_dir = Path.home() / ".seif" / "models"
    if not models_dir.exists():
        return {"status": "NO_PROFILES", "stale": [], "current": []}

    now = datetime.now(timezone.utc)
    threshold = timedelta(days=7)
    stale = []
    current = []

    for profile in sorted(models_dir.glob("*.seif")):
        try:
            data = json.loads(profile.read_text())
            updated = data.get("updated_at", "")
            contributors = data.get("contributors", [])

            # Get most recent update
            dates = []
            if updated:
                dates.append(updated)
            for c in contributors:
                ts = c.get("at") or c.get("timestamp", "")
                if ts:
                    dates.append(ts)

            if dates:
                latest = max(dates)
                try:
                    dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
                    age = now - dt
                    entry = {
                        "model": profile.stem,
                        "last_updated": latest[:10],
                        "age_days": age.days,
                    }
                    if age > threshold:
                        stale.append(entry)
                    else:
                        current.append(entry)
                except (ValueError, TypeError):
                    stale.append({"model": profile.stem, "last_updated": "UNKNOWN", "age_days": -1})
            else:
                stale.append({"model": profile.stem, "last_updated": "NEVER", "age_days": -1})

        except (json.JSONDecodeError, OSError):
            stale.append({"model": profile.stem, "last_updated": "ERROR", "age_days": -1})

    return {
        "status": "STALE" if stale else "CURRENT",
        "stale": stale,
        "current": current,
    }


def convergence_check() -> dict:
    """Run quality gate convergence analysis on genesis data."""
    genesis_json = Path(__file__).parent / "genesis_analysis.json"

    if not genesis_json.exists():
        # Run the analysis first
        from analyze_genesis import main as run_genesis
        try:
            run_genesis()
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}

    if not genesis_json.exists():
        return {"status": "NO_DATA"}

    data = json.loads(genesis_json.read_text())
    summary = data.get("summary", {})

    return {
        "status": "OK",
        "total_turns": summary.get("total_turns", 0),
        "global_avg_score": summary.get("global_avg_score", 0),
        "convergence_direction": summary.get("convergence_direction", "UNKNOWN"),
        "convergence_delta": summary.get("convergence_delta", 0),
        "phases": {
            name: {
                "avg_score": phase.get("avg_score", 0),
                "avg_verifiability": phase.get("avg_verifiability", 0),
            }
            for name, phase in summary.get("phases", {}).items()
        },
    }


def security_audit() -> dict:
    """Run Blue Team audit on .seif context."""
    seif_dir = Path.home() / ".seif"
    if not seif_dir.exists():
        # Try repo-local
        seif_dir = Path(__file__).parent.parent.parent / ".seif"
    if not seif_dir.exists():
        return {"status": "NO_CONTEXT", "grade": "N/A"}

    try:
        from seif.security.redblue import blue_team_audit
        audit = blue_team_audit(str(seif_dir))
        return {
            "status": "OK",
            "modules_audited": audit.modules_audited,
            "compliance_score": round(audit.compliance_score, 4),
            "grade": audit.grade(),
            "hash_valid": audit.hash_valid,
            "provenance_complete": audit.provenance_complete,
            "issues_count": len(audit.issues),
            "top_issues": audit.issues[:5],
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def generate_report(behavioral: dict, staleness: dict,
                    convergence: dict, security: dict) -> str:
    """Generate human-readable meditation report."""
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        "=" * 60,
        "SEIF MEDITATION REPORT — System Identification",
        f"Timestamp: {now}",
        "=" * 60,
        "",
    ]

    # 1. Behavioral
    lines.append("## 1. Behavioral Fidelity (Model Reliability)")
    if behavioral["status"] == "OK":
        lines.append(f"   Models tracked: {behavioral['total_models']}")
        lines.append(f"   Total incidents: {behavioral['total_incidents']}")
        for model, data in behavioral["models"].items():
            lines.append(f"   {model}: reliability={data['reliability']}, "
                        f"incidents={data['incidents']}")
            for fm in data["top_failures"]:
                lines.append(f"      ! {fm['type']} (x{fm['count']})")
    else:
        lines.append("   No behavioral data yet.")
    lines.append("")

    # 2. Profile Staleness
    lines.append("## 2. Profile Staleness Check")
    if staleness["stale"]:
        lines.append(f"   STALE profiles ({len(staleness['stale'])}):")
        for s in staleness["stale"]:
            lines.append(f"      {s['model']}: last updated {s['last_updated']} "
                        f"({s['age_days']} days ago)")
    else:
        lines.append("   All profiles current.")
    if staleness["current"]:
        lines.append(f"   Current profiles ({len(staleness['current'])}):")
        for c in staleness["current"]:
            lines.append(f"      {c['model']}: {c['last_updated']} ({c['age_days']}d)")
    lines.append("")

    # 3. Convergence
    lines.append("## 3. Genesis Convergence Analysis")
    if convergence["status"] == "OK":
        lines.append(f"   Turns analyzed: {convergence['total_turns']}")
        lines.append(f"   Global avg score: {convergence['global_avg_score']}")
        lines.append(f"   Direction: {convergence['convergence_direction']} "
                    f"(Δ = {convergence['convergence_delta']})")
        for name, phase in convergence.get("phases", {}).items():
            lines.append(f"      {name}: score={phase['avg_score']:.4f}, "
                        f"verif={phase['avg_verifiability']:.4f}")
    else:
        lines.append(f"   Status: {convergence['status']}")
    lines.append("")

    # 4. Security
    lines.append("## 4. Blue Team Security Audit")
    if security["status"] == "OK":
        lines.append(f"   Modules audited: {security['modules_audited']}")
        lines.append(f"   Compliance: {security['compliance_score']:.1%} "
                    f"(Grade {security['grade']})")
        lines.append(f"   Hash valid: {security['hash_valid']}/{security['modules_audited']}")
        lines.append(f"   Provenance complete: {security['provenance_complete']}/{security['modules_audited']}")
        if security["top_issues"]:
            lines.append(f"   Issues ({security['issues_count']}):")
            for issue in security["top_issues"]:
                lines.append(f"      [!] {issue}")
    else:
        lines.append(f"   Status: {security['status']}")
    lines.append("")

    # 5. Summary verdict
    lines.append("## 5. Meditation Verdict")
    issues = []
    if behavioral.get("total_incidents", 0) > 0:
        worst = max(behavioral.get("models", {}).values(),
                   key=lambda m: m["incidents"], default=None)
        if worst and worst["reliability"] < 0.5:
            issues.append(f"Model reliability below 0.5")
    if staleness.get("stale"):
        issues.append(f"{len(staleness['stale'])} stale profile(s)")
    if convergence.get("convergence_direction") == "DIVERGING":
        issues.append("Genesis convergence is DIVERGING")
    if security.get("grade") in ("D", "F"):
        issues.append(f"Security grade {security.get('grade')}")

    if not issues:
        lines.append("   HEALTHY — Protocol is calibrated.")
    else:
        lines.append("   ATTENTION NEEDED:")
        for issue in issues:
            lines.append(f"      [!] {issue}")

    lines.append("")
    lines.append("The gate does not filter — it resonates.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="SEIF Meditation — System Identification")
    parser.add_argument("--behavioral", action="store_true", help="Run behavioral audit only")
    parser.add_argument("--convergence", action="store_true", help="Run convergence check only")
    parser.add_argument("--security", action="store_true", help="Run security audit only")
    parser.add_argument("--staleness", action="store_true", help="Run staleness check only")
    parser.add_argument("--report", action="store_true", help="Generate full report (default)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output", type=str, help="Write report to file")
    parser.add_argument("--update-profiles", action="store_true",
                       help="Update model profiles from observations")
    args = parser.parse_args()

    run_all = not (args.behavioral or args.convergence or args.security or args.staleness)

    results = {}

    if run_all or args.behavioral:
        print("Running behavioral audit...")
        results["behavioral"] = behavioral_audit()
        if args.update_profiles:
            print("Updating model profiles...")
            update_all_profiles()

    if run_all or args.staleness:
        print("Checking profile staleness...")
        results["staleness"] = profile_staleness_check()

    if run_all or args.convergence:
        print("Running convergence analysis...")
        results["convergence"] = convergence_check()

    if run_all or args.security:
        print("Running Blue Team security audit...")
        results["security"] = security_audit()

    if args.json:
        output = json.dumps(results, indent=2, ensure_ascii=False)
        if args.output:
            Path(args.output).write_text(output)
        print(output)
    else:
        report = generate_report(
            results.get("behavioral", {"status": "SKIPPED"}),
            results.get("staleness", {"status": "SKIPPED", "stale": [], "current": []}),
            results.get("convergence", {"status": "SKIPPED"}),
            results.get("security", {"status": "SKIPPED"}),
        )
        if args.output:
            Path(args.output).write_text(report)
        print(report)


if __name__ == "__main__":
    main()
