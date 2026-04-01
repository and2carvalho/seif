#!/usr/bin/env python3
"""
Propose a change to S.E.I.F. — AI agent helper.

Creates a branch, runs tests and Quality Gate locally,
then opens a PR with proper formatting and Co-Authored-By.

Requires: git, gh (GitHub CLI).

Usage:
    python scripts/propose_change.py \
        --branch feat/improve-tests \
        --author "Claude (Anthropic)" \
        --message "Add edge case tests for triple gate"

    # Dry run (checks only, no PR):
    python scripts/propose_change.py \
        --branch feat/x --author "Grok (xAI)" \
        --message "Fix boundary" --dry-run
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Known AI systems for email defaults
AI_EMAILS = {
    "anthropic": "noreply@anthropic.com",
    "claude": "noreply@anthropic.com",
    "xai": "noreply@x.ai",
    "grok": "noreply@x.ai",
    "google": "noreply@google.com",
    "gemini": "noreply@google.com",
    "deepseek": "noreply@deepseek.com",
    "moonshot": "noreply@moonshot.ai",
    "kimi": "noreply@moonshot.ai",
}


def run(cmd, check=True):
    """Run a shell command, return stdout."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"FAILED: {cmd}")
        if r.stderr:
            print(f"  {r.stderr.strip()}")
        sys.exit(1)
    return r.stdout.strip()


def guess_email(author: str) -> str:
    """Guess email from author string."""
    lower = author.lower()
    for key, email in AI_EMAILS.items():
        if key in lower:
            return email
    return "noreply@contributor.ai"


def get_changed_files() -> list[str]:
    """Get modified tracked files."""
    out = run("git diff --name-only", check=False)
    staged = run("git diff --name-only --cached", check=False)
    files = set(filter(None, (out + "\n" + staged).split("\n")))
    return sorted(files)


def run_tests() -> bool:
    """Run test suite. Returns True if passed."""
    print("\n--- Tests ---")
    env = {**os.environ, "PYTHONPATH": "src"}
    r = subprocess.run("make test", shell=True, env=env)
    passed = r.returncode == 0
    print(f"{'PASS' if passed else 'FAIL'}: test suite")
    return passed


def run_quality_gate(files: list[str]) -> tuple[str, str]:
    """Assess changed .seif files. Returns (worst_grade, report)."""
    from seif.analysis.quality_gate import assess

    grade_order = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
    worst = "A"
    lines = []

    for f in files:
        p = Path(f)
        if not p.exists() or p.suffix != ".seif":
            continue
        content = p.read_text()[:2000]
        if len(content.strip()) < 20:
            continue
        v = assess(content)
        icon = {"A": "+", "B": "+", "C": "~", "D": "-", "F": "-"}.get(v.grade, "?")
        lines.append(f"  [{icon}] {f}: Grade {v.grade} (score {v.score:.3f}, {v.status})")
        if grade_order.get(v.grade, 0) < grade_order.get(worst, 5):
            worst = v.grade

    report = "\n".join(lines) if lines else "  (no assessable .md/.seif files changed)"
    return worst, report


def main():
    parser = argparse.ArgumentParser(
        description="Propose a S.E.I.F. change (AI agent helper)"
    )
    parser.add_argument("--branch", required=True, help="Branch name (e.g., feat/improve-tests)")
    parser.add_argument("--author", required=True, help="AI system name (e.g., 'Claude (Anthropic)')")
    parser.add_argument("--email", default=None, help="Co-Author email (auto-detected if omitted)")
    parser.add_argument("--message", required=True, help="Commit message (concise, conventional format)")
    parser.add_argument("--description", default="", help="PR body description")
    parser.add_argument("--base", default="dev", help="Base branch (default: dev)")
    parser.add_argument("--dry-run", action="store_true", help="Run checks only, don't create PR")
    args = parser.parse_args()

    email = args.email or guess_email(args.author)

    print(f"=== S.E.I.F. Proposal ===")
    print(f"  Agent:   {args.author}")
    print(f"  Branch:  {args.branch}")
    print(f"  Base:    {args.base}")
    print(f"  Message: {args.message}")

    # 1. Check for changes
    changed = get_changed_files()
    if not changed:
        print("\nNo changes detected. Make changes first, then run this script.")
        sys.exit(1)
    print(f"\n  Files changed: {len(changed)}")
    for f in changed:
        print(f"    {f}")

    # 2. Run tests
    if not run_tests():
        sys.exit(1)

    # 3. Run Quality Gate
    print("\n--- Quality Gate ---")
    grade, report = run_quality_gate(changed)
    print(report)
    grade_order = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
    if grade_order.get(grade, 0) < 3:
        print(f"FAIL: Quality Gate grade {grade} < C. Improve content before proposing.")
        sys.exit(1)
    print(f"PASS: Quality Gate worst grade {grade}")

    if args.dry_run:
        print("\n--- Dry run complete. No PR created. ---")
        return

    # 4. Create branch
    current = run("git branch --show-current")
    if current != args.branch:
        run(f"git checkout -b {args.branch}")

    # 5. Commit
    co_author = f"Co-Authored-By: {args.author} <{email}>"
    run("git add -u")
    commit_msg = f"{args.message}\n\n{co_author}"
    # Use a temp file for the commit message to handle special chars
    msg_file = Path("/tmp/seif_commit_msg.txt")
    msg_file.write_text(commit_msg)
    run(f"git commit -F {msg_file}")
    msg_file.unlink()

    # 6. Push
    run(f"git push -u origin {args.branch}")

    # 7. Create PR
    pr_body = f"""## Summary

{args.description if args.description else args.message}

## Quality Gate

Worst grade: **{grade}**
```
{report}
```

## Provenance

- **Agent:** {args.author}
- **Guide:** [CONTRIBUTING_AI.md](CONTRIBUTING_AI.md)
- **Origin:** [GENESIS.md](GENESIS.md)

---
The gate does not filter — it resonates.
"""
    body_file = Path("/tmp/seif_pr_body.md")
    body_file.write_text(pr_body)
    run(f'gh pr create --base {args.base} --title "{args.message}" --body-file {body_file}')
    body_file.unlink()

    print("\n=== PR created. Human review required. ===")


if __name__ == "__main__":
    main()
