#!/usr/bin/env python3
"""
S.E.I.F. Code Reviewer — machine reviewing machine.

Scans changed files for SEIF-specific issues:
  1. Hardcoded constants that should come from constants.py
  2. Stance drift in documentation
  3. CONTEXT_NOT_COMMAND violations
  4. Missing .seif module fields
  5. Sensitive data exposure

Usage:
    # Review staged changes:
    PYTHONPATH=src python scripts/seif_review.py

    # Review specific files:
    PYTHONPATH=src python scripts/seif_review.py src/seif/core/gate.py docs/new.md

    # Review diff against a base branch:
    PYTHONPATH=src python scripts/seif_review.py --base dev

    # Output as JSON (for CI integration):
    PYTHONPATH=src python scripts/seif_review.py --json
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# --- Constants that must not be hardcoded ---

PROTECTED_CONSTANTS = {
    r"\b432\b": ("FREQ_TESLA", "Tesla fundamental frequency"),
    r"\b438\b": ("FREQ_GIZA", "King's Chamber resonance"),
    r"\b7\.83\b": ("FREQ_SCHUMANN", "Schumann fundamental"),
    r"\b1\.618034\b": ("PHI", "Golden ratio"),
    r"\b0\.618034\b": ("PHI_INVERSE", "Resonance threshold"),
    r"\b0\.612372\b": ("TF_ZETA", "Damping ratio"),
    r"\b51\.844\b": ("GIZA_ANGLE_DEG", "Pyramid inclination"),
    r"\b29\.9792458\b": ("GIZA_LATITUDE", "Speed of light digits"),
    r"\b216\b": ("TF_PEAK_432", "Peak at 432 Hz"),
}

# Files where constants are DEFINED or documented (not violations)
CONSTANT_DEFINITION_FILES = {
    "constants.py", "RESONANCE.json", "CONTEXT_SEED.md",
    "seif_review.py", "copilot-instructions.md",
}

# Command language patterns (CONTEXT_NOT_COMMAND violations)
COMMAND_PATTERNS = [
    (r"\bMUST\b(?!\s+be\s+imported)", "MUST — consider softer CONTEXT language"),
    (r"\bFORCED_OPEN\b", "FORCED_OPEN — gate status should be measured, not forced"),
    (r"priority.*ABSOLUTE", "ABSOLUTE priority — measurement, not authority"),
    (r"\bbypass\b.*(?:gate|filter|check)", "bypassing safety — investigate root cause"),
]

# Sensitive data patterns
SENSITIVE_PATTERNS = [
    (r"API_KEY\s*=\s*['\"][^'\"]+['\"]", "Hardcoded API key"),
    (r"SECRET_KEY\s*=\s*['\"][^'\"]+['\"]", "Hardcoded secret"),
    (r"PASSWORD\s*=\s*['\"][^'\"]+['\"]", "Hardcoded password"),
    (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY", "Private key in source"),
    (r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer token in source"),
]

# Severity levels
CRITICAL = "CRITICAL"
WARNING = "WARNING"
INFO = "INFO"


def get_changed_files(base: str = None) -> list[str]:
    """Get changed files from git."""
    if base:
        cmd = f"git diff --name-only origin/{base}...HEAD"
    else:
        # Staged + unstaged
        cmd = "git diff --name-only HEAD"
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    staged = subprocess.run(
        "git diff --name-only --cached", shell=True, capture_output=True, text=True
    )
    files = set(filter(None, (r.stdout + "\n" + staged.stdout).strip().split("\n")))
    return sorted(f for f in files if Path(f).exists())


def check_hardcoded_constants(filepath: str, content: str) -> list[dict]:
    """Check for hardcoded SEIF constants."""
    findings = []
    basename = Path(filepath).name

    if basename in CONSTANT_DEFINITION_FILES:
        return []

    # Skip test files and documentation — they legitimately reference values
    if basename.startswith("test_") or filepath.endswith(".md"):
        return []

    lines = content.split("\n")

    # Pre-compute which lines are inside docstrings or comments
    in_docstring = set()
    in_ds = False
    ds_char = None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if not in_ds:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                ds_char = stripped[:3]
                in_ds = True
                in_docstring.add(i)
                # Single-line docstring: """..."""
                if stripped.count(ds_char) >= 2:
                    in_ds = False
                continue
        else:
            in_docstring.add(i)
            if ds_char in stripped:
                in_ds = False

    for pattern, (const_name, meaning) in PROTECTED_CONSTANTS.items():
        for match in re.finditer(pattern, content):
            line_num = content[:match.start()].count("\n") + 1
            line_idx = line_num - 1
            line_text = lines[line_idx] if line_idx < len(lines) else ""

            # Skip docstrings and comments
            if line_idx in in_docstring:
                continue
            stripped = line_text.lstrip()
            if stripped.startswith("#"):
                continue
            # Skip inline comments (value appears after #)
            code_part = line_text.split("#")[0]
            if match.group() not in code_part:
                continue

            findings.append({
                "file": filepath,
                "line": line_num,
                "severity": WARNING,
                "check": "hardcoded-constant",
                "message": (
                    f"Value `{match.group()}` appears as literal. "
                    f"Import `{const_name}` from constants.py ({meaning})."
                ),
            })
    return findings


def check_command_language(filepath: str, content: str) -> list[dict]:
    """Check for CONTEXT_NOT_COMMAND violations."""
    findings = []

    # Only check non-test, non-config files
    basename = Path(filepath).name
    if basename.startswith("test_") or basename in ("Makefile", "pyproject.toml"):
        return []

    for pattern, description in COMMAND_PATTERNS:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            line_num = content[:match.start()].count("\n") + 1
            findings.append({
                "file": filepath,
                "line": line_num,
                "severity": INFO,
                "check": "context-not-command",
                "message": f"{description} (found: `{match.group()[:40]}`)",
            })
    return findings


def check_sensitive_data(filepath: str, content: str) -> list[dict]:
    """Check for sensitive data exposure."""
    findings = []
    for pattern, description in SENSITIVE_PATTERNS:
        for match in re.finditer(pattern, content):
            line_num = content[:match.start()].count("\n") + 1
            findings.append({
                "file": filepath,
                "line": line_num,
                "severity": CRITICAL,
                "check": "sensitive-data",
                "message": f"{description} — do not commit secrets.",
            })
    return findings


def check_seif_module(filepath: str, content: str) -> list[dict]:
    """Check .seif module integrity."""
    findings = []
    if not filepath.endswith(".seif"):
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        findings.append({
            "file": filepath,
            "line": 1,
            "severity": CRITICAL,
            "check": "seif-integrity",
            "message": "Invalid JSON in .seif module.",
        })
        return findings

    required = ["_instruction", "integrity_hash", "summary"]
    for field in required:
        if not data.get(field):
            findings.append({
                "file": filepath,
                "line": 1,
                "severity": WARNING,
                "check": "seif-integrity",
                "message": f"Missing required field `{field}` in .seif module.",
            })
    return findings


def check_stance_drift(filepath: str, content: str) -> list[dict]:
    """Check for stance drift in documentation."""
    findings = []
    if not filepath.endswith((".md", ".seif")):
        return []

    try:
        from seif.analysis.stance_detector import analyze
        result = analyze(content[:2000])
        if result.status == "DRIFT" and result.flagged_sentences:
            for sentence in result.flagged_sentences[:3]:
                findings.append({
                    "file": filepath,
                    "line": 0,
                    "severity": WARNING,
                    "check": "stance-drift",
                    "message": f"Interpretive claim without stance label: \"{sentence[:80]}\"",
                })
    except ImportError:
        pass  # stance_detector not available — skip

    return findings


def review_file(filepath: str) -> list[dict]:
    """Run all checks on a single file."""
    # Self-exclusion: the reviewer's own pattern definitions are not violations
    basename = Path(filepath).name
    if basename in ("seif_review.py", "copilot-instructions.md"):
        return []

    content = Path(filepath).read_text(errors="replace")
    findings = []
    findings.extend(check_hardcoded_constants(filepath, content))
    findings.extend(check_command_language(filepath, content))
    findings.extend(check_sensitive_data(filepath, content))
    findings.extend(check_seif_module(filepath, content))
    findings.extend(check_stance_drift(filepath, content))
    return findings


def format_findings(findings: list[dict], as_json: bool = False) -> str:
    """Format findings for display."""
    if as_json:
        return json.dumps(findings, indent=2)

    if not findings:
        return "=== SEIF Review: No issues found. The gate resonates. ==="

    lines = ["=== SEIF Review ===", ""]

    severity_icon = {CRITICAL: "!!", WARNING: "~~", INFO: ".."}

    by_file = {}
    for f in findings:
        by_file.setdefault(f["file"], []).append(f)

    critical_count = sum(1 for f in findings if f["severity"] == CRITICAL)
    warning_count = sum(1 for f in findings if f["severity"] == WARNING)
    info_count = sum(1 for f in findings if f["severity"] == INFO)

    for filepath, file_findings in sorted(by_file.items()):
        lines.append(f"  {filepath}:")
        for f in file_findings:
            icon = severity_icon.get(f["severity"], "  ")
            loc = f"L{f['line']}" if f["line"] else "   "
            lines.append(f"    [{icon}] {loc}: {f['message']}")
        lines.append("")

    lines.append(f"  Total: {critical_count} critical, {warning_count} warnings, {info_count} info")

    if critical_count > 0:
        lines.append("  Status: BLOCKED — resolve critical issues before merge.")
    elif warning_count > 0:
        lines.append("  Status: REVIEW — warnings should be addressed.")
    else:
        lines.append("  Status: CLEAN — informational notes only.")

    lines.append("")
    lines.append("  The gate does not filter — it resonates.")
    return "\n".join(lines)


def load_model_profile(ai_author: str) -> dict | None:
    """Load the model-profile for the detected AI author."""
    profile_path = Path(".seif/models") / f"{ai_author}.seif"
    if not profile_path.exists():
        return None
    try:
        data = json.loads(profile_path.read_text())
        return data
    except (json.JSONDecodeError, OSError):
        return None


def load_prior_reviews() -> list[dict]:
    """Load prior review modules for recurring pattern detection."""
    review_dir = Path(".seif/projects/seif")
    if not review_dir.exists():
        return []
    reviews = []
    for p in sorted(review_dir.glob("review-codex-*.seif")):
        try:
            reviews.append(json.loads(p.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return reviews


def check_recurring_patterns(
    findings: list[dict], prior_reviews: list[dict]
) -> list[dict]:
    """Flag findings that match patterns from prior reviews."""
    if not prior_reviews:
        return []

    # Collect prior finding types (check + message prefix)
    prior_types = set()
    for review in prior_reviews:
        summary = review.get("summary", "")
        for line in summary.split("\n"):
            line = line.strip()
            if line.startswith("- ["):
                # Extract check type from finding line
                if "hardcoded-constant" in line or "appears as literal" in line:
                    prior_types.add("hardcoded-constant")
                elif "CONTEXT" in line or "MUST" in line:
                    prior_types.add("context-not-command")
                elif "stance" in line.lower() or "drift" in line.lower():
                    prior_types.add("stance-drift")
                elif "sensitive" in line.lower() or "secret" in line.lower():
                    prior_types.add("sensitive-data")

    recurring = []
    for f in findings:
        if f["check"] in prior_types:
            recurring.append({
                "file": f["file"],
                "line": f["line"],
                "severity": WARNING,
                "check": "recurring-pattern",
                "message": (
                    f"Recurring: '{f['check']}' was also flagged in a prior PR review. "
                    f"Original: {f['message'][:80]}"
                ),
            })
    return recurring


def format_model_context(profile: dict | None, ai_author: str) -> str:
    """Format model-profile context for the review header."""
    if not profile:
        return ""
    summary = profile.get("summary", "")
    # Extract failure modes section
    lines = []
    in_failures = False
    for line in summary.split("\n"):
        if "Failure Modes" in line:
            in_failures = True
            continue
        if in_failures:
            if line.startswith("###") or (line.strip() == "" and lines):
                break
            if line.strip().startswith("-"):
                lines.append(line.strip())
    if lines:
        return (
            f"\n  Model profile loaded: {ai_author}\n"
            f"  Known failure modes:\n"
            + "\n".join(f"    {l}" for l in lines[:5])
            + "\n"
        )
    return f"\n  Model profile loaded: {ai_author} (no failure modes documented)\n"


def main():
    parser = argparse.ArgumentParser(description="S.E.I.F. Code Reviewer")
    parser.add_argument("files", nargs="*", help="Files to review (default: changed files)")
    parser.add_argument("--base", default=None, help="Base branch for diff (e.g., dev)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--ai-author", default=None, help="Detected AI model (e.g., claude, grok)")
    args = parser.parse_args()

    # Load SEIF context
    model_profile = None
    if args.ai_author:
        model_profile = load_model_profile(args.ai_author)

    prior_reviews = load_prior_reviews()

    if args.files:
        files = [f for f in args.files if Path(f).exists()]
    else:
        files = get_changed_files(args.base)

    if not files:
        print("No files to review.")
        return

    header = f"Reviewing {len(files)} file(s)..."
    if args.ai_author:
        header += f" (AI author: {args.ai_author})"
    if prior_reviews:
        header += f" ({len(prior_reviews)} prior review(s) loaded)"
    print(header)
    if model_profile:
        print(format_model_context(model_profile, args.ai_author))

    all_findings = []
    for f in files:
        all_findings.extend(review_file(f))

    # Check for recurring patterns from prior reviews
    recurring = check_recurring_patterns(all_findings, prior_reviews)
    all_findings.extend(recurring)

    print(format_findings(all_findings, as_json=args.json))

    # Exit code: 1 if critical issues found
    if any(f["severity"] == CRITICAL for f in all_findings):
        sys.exit(1)


if __name__ == "__main__":
    main()
