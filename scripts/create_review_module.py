#!/usr/bin/env python3
"""
Create a SEIF-MODULE-v2 from the output of seif_review.py.

Closes the inter-AI loop: review findings become persistent .seif modules
that the next AI session can read via --sync.

Usage:
    python scripts/create_review_module.py \
        --input seif_review.txt \
        --quality-report quality_report.md \
        --pr 9 \
        --run-id 12345 \
        --output .seif/projects/seif/review-codex-PR9.seif
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def parse_review_findings(review_text: str) -> dict:
    """Extract structured data from seif_review.py text output."""
    findings = {
        "critical": 0,
        "warnings": 0,
        "info": 0,
        "status": "UNKNOWN",
        "files_reviewed": [],
        "issues": [],
    }

    for line in review_text.split("\n"):
        line = line.strip()

        # Count severities
        if "critical" in line and "warning" in line:
            # Summary line: "Total: 0 critical, 2 warnings, 1 info"
            import re
            m = re.search(r"(\d+)\s+critical.*?(\d+)\s+warning.*?(\d+)\s+info", line)
            if m:
                findings["critical"] = int(m.group(1))
                findings["warnings"] = int(m.group(2))
                findings["info"] = int(m.group(3))

        # Status line
        if line.startswith("Status:"):
            findings["status"] = line.split("—")[0].replace("Status:", "").strip()

        # File paths (indented with colon)
        if line.endswith(":") and "/" in line:
            findings["files_reviewed"].append(line.rstrip(":").strip())

        # Individual issues
        if line.startswith("["):
            findings["issues"].append(line)

    if not findings["status"] or findings["status"] == "UNKNOWN":
        if findings["critical"] > 0:
            findings["status"] = "BLOCKED"
        elif findings["warnings"] > 0:
            findings["status"] = "REVIEW"
        elif "No issues found" in review_text:
            findings["status"] = "CLEAN"

    return findings


def extract_quality_grade(quality_report: str) -> dict:
    """Extract grade from quality_report.md."""
    result = {"grade": "?", "passing": True}
    for line in quality_report.split("\n"):
        if "Overall:" in line:
            if "PASS" in line:
                result["passing"] = True
            elif "FAIL" in line:
                result["passing"] = False
            # Extract worst grade
            import re
            m = re.search(r"worst grade:\s*([A-F])", line)
            if m:
                result["grade"] = m.group(1)
    return result


def create_module(
    review_text: str,
    quality_report: str,
    pr_number: int,
    run_id: str,
) -> dict:
    """Create a SEIF-MODULE-v2 from review output."""
    findings = parse_review_findings(review_text)
    quality = extract_quality_grade(quality_report) if quality_report else {}

    now = datetime.now(timezone.utc).isoformat()

    # Build summary — this is what the next AI session reads
    summary_parts = [
        f"## Codex Review — PR #{pr_number}",
        f"Date: {now[:10]}",
        f"Run: {run_id}",
        "",
        f"### Review Status: {findings['status']}",
        f"- Critical: {findings['critical']}",
        f"- Warnings: {findings['warnings']}",
        f"- Info: {findings['info']}",
        f"- Files reviewed: {len(findings['files_reviewed'])}",
    ]

    if quality:
        summary_parts.extend([
            "",
            f"### Quality Gate: Grade {quality.get('grade', '?')} ({'PASS' if quality.get('passing') else 'FAIL'})",
        ])

    if findings["issues"]:
        summary_parts.extend(["", "### Findings"])
        for issue in findings["issues"][:20]:  # Cap at 20
            summary_parts.append(f"- {issue}")

    if findings["files_reviewed"]:
        summary_parts.extend(["", "### Files"])
        for f in findings["files_reviewed"][:15]:
            summary_parts.append(f"- {f}")

    summary = "\n".join(summary_parts)

    # Compute integrity hash (SHA-256 of summary, first 16 hex chars)
    integrity_hash = hashlib.sha256(summary.encode()).hexdigest()[:16]

    # Verified data points — only factual, measurable items
    verified_data = [
        f"PR #{pr_number}: {findings['critical']} critical, {findings['warnings']} warnings, {findings['info']} info",
        f"Review status: {findings['status']}",
        f"Files reviewed: {len(findings['files_reviewed'])}",
    ]
    if quality:
        verified_data.append(f"Quality Gate: Grade {quality.get('grade', '?')}")

    module = {
        "_instruction": (
            "This is a S.E.I.F. compressed context module. "
            "Read the 'summary' field — it contains the full project context "
            "compressed from thousands of words to hundreds, with verified data "
            "points and an integrity hash. "
            "Protocol: github.com/and2carvalho/seif"
        ),
        "protocol": "SEIF-MODULE-v2",
        "source": f"codex-reviewer/PR-{pr_number}",
        "original_words": len(review_text.split()),
        "compressed_words": len(summary.split()),
        "compression_ratio": round(
            len(review_text.split()) / max(len(summary.split()), 1), 1
        ),
        "summary": summary,
        "resonance": {
            "note": "Not computed — reviewer is static analyzer, not LLM",
        },
        "verified_data": verified_data,
        "integrity_hash": integrity_hash,
        "active": True,
        "version": 1,
        "contributors": [
            {
                "author": "codex-reviewer",
                "at": now,
                "via": "github-actions",
                "action": "created",
            }
        ],
        "parent_hash": None,
        "updated_at": now,
        "classification": "INTERNAL",
    }

    return module


def main():
    parser = argparse.ArgumentParser(
        description="Create SEIF review module from reviewer output"
    )
    parser.add_argument("--input", required=True, help="Path to seif_review.txt")
    parser.add_argument("--quality-report", default=None, help="Path to quality_report.md")
    parser.add_argument("--pr", required=True, type=int, help="PR number")
    parser.add_argument("--run-id", default="local", help="GitHub Actions run ID")
    parser.add_argument("--output", required=True, help="Output .seif file path")
    args = parser.parse_args()

    review_text = Path(args.input).read_text()

    quality_report = None
    if args.quality_report and Path(args.quality_report).exists():
        quality_report = Path(args.quality_report).read_text()

    module = create_module(review_text, quality_report, args.pr, args.run_id)

    # Ensure output directory exists
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w") as f:
        json.dump(module, f, indent=2, ensure_ascii=False)

    print(f"Created review module: {args.output}")
    print(f"  PR: #{args.pr}")
    print(f"  Findings: {module['verified_data'][0].split(': ', 1)[1]}")
    print(f"  Hash: {module['integrity_hash']}")


if __name__ == "__main__":
    main()
