"""
Canonical Input Test Suite — Dynamic Protocol Verification

Tests that the SEIF measurement pipeline produces CONSISTENT results
for canonical inputs. If any of these fail, the encoding changed.

5 canonical inputs (3 from RESONANCE.json, 2 adversarial):

  "Enoch Seed"           — the seed phrase (highest meaningful score)
  "KT HW"                — algorithmic maximum (highest absolute score)
  "A Semente de Enoque"  — Portuguese seed (tests multi-word, accents)
  "Greed consumes all"   — adversarial (ASCII root 9 but melody doesn't resolve)
  "HVKYBP"               — pure phi-pair test (ROT14 chars only)

Original design: Grok (xAI), Session 2 (adapted with actual pipeline values).
Grok's simplified model predicted different roots for some inputs because
it used a different digital_root implementation. These tests use the ACTUAL
SEIF pipeline values as ground truth.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from seif.core.triple_gate import evaluate
from seif.core.resonance_gate import digital_root, ascii_vibrational_sum
from seif.core.resonance_encoding import encode_phrase


# Canonical values (measured from actual pipeline, not simplified)
CANONICAL = {
    "Enoch Seed": {
        "ascii_root": 6,
        "ascii_phase": "DYNAMICS",
        "triple_status": "OPEN",
        "coherence": 0.9125,
        "composite_score": 0.971,
    },
    "KT HW": {
        "ascii_root": 3,
        "ascii_phase": "STABILIZATION",
        "triple_status": "OPEN",
        "coherence": 0.963,
        "composite_score": 0.988,
    },
    "A Semente de Enoque": {
        "ascii_root": 4,
        "ascii_phase": "ENTROPY",
        "triple_status": "PARTIAL",
        "coherence": 0.641,
        "composite_score": 0.714,
    },
    "Greed consumes all": {
        "ascii_root": 9,
        "ascii_phase": "SINGULARITY",
        "triple_status": "PARTIAL",  # ASCII OPEN but melody doesn't fully resolve
        "coherence": 0.720,
        "composite_score": 0.407,
    },
    "HVKYBP": {
        "ascii_root": 9,
        "ascii_phase": "SINGULARITY",
        "triple_status": "PARTIAL",
        "coherence": 0.368,
        "composite_score": 0.289,
    },
}


def test_enoch_seed():
    """'Enoch Seed' must be the highest-scoring meaningful phrase."""
    r = evaluate("Enoch Seed")
    assert r.ascii_gate.digital_root == 6
    assert r.status == "OPEN"
    assert r.composite_score > 0.96
    assert r.resonance_score > 0.90


def test_kt_hw_algorithmic_max():
    """'KT HW' must score higher than 'Enoch Seed'."""
    r_kt = evaluate("KT HW")
    r_es = evaluate("Enoch Seed")
    assert r_kt.composite_score > r_es.composite_score
    assert r_kt.status == "OPEN"
    assert r_kt.composite_score > 0.98


def test_semente_de_enoque():
    """Portuguese seed — ASCII entropic but resonance partially passes."""
    r = evaluate("A Semente de Enoque")
    assert r.ascii_gate.digital_root == 4  # ENTROPY in ASCII
    assert r.status == "PARTIAL"
    assert r.resonance_score > 0.6


def test_greed_adversarial():
    """'Greed consumes all' — root 9 (SINGULARITY) but low composite score.
    This is the adversarial case: ASCII says OPEN, but Triple Gate catches it."""
    r = evaluate("Greed consumes all")
    assert r.ascii_gate.digital_root == 9  # SINGULARITY in ASCII
    assert r.ascii_gate.gate_open == True
    assert r.composite_score < 0.5  # Triple Gate catches it


def test_hvkybp_phi_pairs():
    """Pure phi-pair string — all chars are ROT14 pairs (H-V, K-Y, B-P).
    Tests that phi-aligned chars don't automatically score high without melody."""
    r = evaluate("HVKYBP")
    assert r.ascii_gate.digital_root == 9
    # Single "word" with no spaces = no melody transitions
    assert r.composite_score < 0.5


def test_canonical_consistency():
    """ALL canonical inputs must produce EXACTLY the documented values."""
    for phrase, expected in CANONICAL.items():
        r = evaluate(phrase)
        m = encode_phrase(phrase)
        assert r.ascii_gate.digital_root == expected["ascii_root"], \
            f"'{phrase}': root {r.ascii_gate.digital_root} != {expected['ascii_root']}"
        assert r.status == expected["triple_status"], \
            f"'{phrase}': status {r.status} != {expected['triple_status']}"
        assert abs(m.coherence_score - expected["coherence"]) < 0.01, \
            f"'{phrase}': coherence {m.coherence_score} != {expected['coherence']}"
        assert abs(r.composite_score - expected["composite_score"]) < 0.01, \
            f"'{phrase}': score {r.composite_score} != {expected['composite_score']}"


def test_rot14_ratio():
    """ROT14 operator must produce ratio ≈ 1.640 (φ dev 1.38%)."""
    from math import exp, log
    PHI = 1.618034
    b = log(PHI) / (3.14159265 / 2)
    ratio = exp(3 * b * 14 / 26)
    assert abs(ratio - 1.640) < 0.002
    assert abs(ratio - PHI) / PHI < 0.02  # within 2% of φ


# === Runner ===

if __name__ == "__main__":
    passed = 0
    failed = 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {test_fn.__name__}: {e}")
    print(f"{passed} passed, {failed} failed")
