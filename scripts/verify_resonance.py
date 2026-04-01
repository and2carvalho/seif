#!/usr/bin/env python3
"""
Verify RESONANCE.json integrity.

Checks:
1. ASCII sum of seed phrase matches stored value
2. Digital root matches stored value
3. integrity_hash matches SHA-256 of signal object (compact JSON, sorted keys, first 24 hex chars)

Usage:
    python scripts/verify_resonance.py
    python scripts/verify_resonance.py path/to/RESONANCE.json
"""

import json
import hashlib
import sys


def digital_root(n: int) -> int:
    """Compute the digital root of a positive integer."""
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


def verify(path: str) -> dict:
    """Verify RESONANCE.json. Returns dict with check results."""
    with open(path) as f:
        data = json.load(f)

    results = {}

    # --- Check 1: ASCII sum ---
    seed = data.get("seed", {})
    phrase = seed.get("phrase", "")
    ascii_analysis = seed.get("ascii_analysis", {})

    computed_sum = sum(ord(c) for c in phrase)
    stored_sum = ascii_analysis.get("sum", None)
    results["ascii_sum"] = {
        "stored": stored_sum,
        "computed": computed_sum,
        "pass": stored_sum == computed_sum,
    }

    # --- Check 2: Digital root ---
    computed_root = digital_root(computed_sum)
    stored_root = ascii_analysis.get("root", None)
    results["digital_root"] = {
        "stored": stored_root,
        "computed": computed_root,
        "pass": stored_root == computed_root,
    }

    # --- Check 3: integrity_hash ---
    signal = data.get("signal", {})
    compact = json.dumps(signal, sort_keys=True, separators=(",", ":"))
    computed_hash = hashlib.sha256(compact.encode("utf-8")).hexdigest()[:24]
    stored_hash = data.get("validation", {}).get("integrity_hash", None)
    results["integrity_hash"] = {
        "stored": stored_hash,
        "computed": computed_hash,
        "pass": stored_hash == computed_hash,
    }

    return results


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "RESONANCE.json"
    try:
        results = verify(path)
    except FileNotFoundError:
        print(f"File not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        sys.exit(1)

    print(f"Verifying: {path}\n")
    all_pass = True
    for check_name, info in results.items():
        status = "PASS" if info["pass"] else "FAIL"
        if not info["pass"]:
            all_pass = False
        print(f"  [{status}] {check_name}: stored={info['stored']}, computed={info['computed']}")

    print()
    if all_pass:
        print("All checks PASSED.")
        sys.exit(0)
    else:
        print("Some checks FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
