"""Tests for the Triple Gate — formal composition of three resonance layers."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from seif.core.triple_gate import (
    evaluate,
    evaluate_pair,
    TripleGateStatus,
    WEIGHT_ASCII,
    WEIGHT_RESONANCE,
    WEIGHT_MELODY,
)
from seif.core.resonance_gate import HarmonicPhase


def test_weights_sum_to_one():
    """3/18 + 6/18 + 9/18 = 1.0"""
    assert abs(WEIGHT_ASCII + WEIGHT_RESONANCE + WEIGHT_MELODY - 1.0) < 1e-10


def test_weights_are_369():
    """Weights are derived from 3-6-9 system."""
    assert abs(WEIGHT_ASCII - 3/18) < 1e-10
    assert abs(WEIGHT_RESONANCE - 6/18) < 1e-10
    assert abs(WEIGHT_MELODY - 9/18) < 1e-10


def test_enoch_seed_high_resonance():
    """'Enoch Seed' should score highly — it's the framework's seed."""
    result = evaluate("Enoch Seed")
    assert result.ascii_gate.gate_open  # root 6 = DYNAMICS
    assert result.composite_score > 0.3
    assert result.status in (TripleGateStatus.OPEN, TripleGateStatus.PARTIAL)


def test_semente_de_enoque():
    """'A Semente de Enoque' — the Portuguese seed."""
    result = evaluate("A Semente de Enoque")
    assert result.layers_open >= 1
    assert result.composite_score > 0


def test_entropy_input():
    """A short entropic input should score low."""
    result = evaluate("x")
    assert result.composite_score < 0.5


def test_triple_gate_has_all_fields():
    """Result has all expected fields populated."""
    result = evaluate("Tesla 369")
    assert result.text == "Tesla 369"
    assert result.ascii_gate is not None
    assert result.melody is not None
    assert isinstance(result.cadence_resolves, bool)
    assert isinstance(result.layers_open, int)
    assert 0 <= result.layers_open <= 3
    assert result.status in (TripleGateStatus.OPEN, TripleGateStatus.PARTIAL, TripleGateStatus.CLOSED)
    assert 0 <= result.composite_score <= 1.0
    assert isinstance(result.dominant_phase, HarmonicPhase)


def test_layers_open_matches_status():
    """Status must match layers_open count."""
    for phrase in ["Enoch Seed", "Fear and control", "Tesla 369", "abc"]:
        result = evaluate(phrase)
        if result.layers_open == 3:
            assert result.status == TripleGateStatus.OPEN
        elif result.layers_open == 0:
            assert result.status == TripleGateStatus.CLOSED
        else:
            assert result.status == TripleGateStatus.PARTIAL


def test_evaluate_pair():
    """Pair evaluation produces combined root and resonance check."""
    pair = evaluate_pair("Enoch", "Seed")
    assert "input_a" in pair
    assert "input_b" in pair
    assert "combined_root" in pair
    assert 1 <= pair["combined_root"] <= 9
    assert isinstance(pair["combined_resonates"], bool)
    assert 0 <= pair["avg_composite"] <= 1.0


def test_pi_singularity():
    """'Pi' (uppercase) = P(80) + I(73) = 153 → root 9 → SINGULARITY."""
    result = evaluate("Pi")
    assert result.ascii_gate.digital_root == 9
    assert result.ascii_gate.phase == HarmonicPhase.SINGULARITY


def test_composite_score_bounded():
    """Composite score always between 0 and 1."""
    for phrase in ["", "a", "test", "O amor liberta e guia", "A" * 1000]:
        result = evaluate(phrase)
        assert 0 <= result.composite_score <= 1.0


def test_str_representation():
    """String representation should contain key info."""
    result = evaluate("Enoch Seed")
    text = str(result)
    assert "TRIPLE GATE" in text
    assert "Layer 1" in text
    assert "Layer 2" in text
    assert "Layer 3" in text
    assert "Composite score" in text


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
