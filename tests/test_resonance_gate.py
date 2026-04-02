"""Tests for the Resonance Gate 3-6-9 system."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from seif.core.resonance_gate import (
    digital_root,
    ascii_vibrational_sum,
    raw_ascii_sum,
    classify_phase,
    evaluate,
    evaluate_pair,
    is_harmonic,
    verify_seed,
    HarmonicPhase,
)


# --- digital_root ---

def test_digital_root_single_digit():
    for i in range(1, 10):
        assert digital_root(i) == i

def test_digital_root_multiples_of_9():
    assert digital_root(9) == 9
    assert digital_root(18) == 9
    assert digital_root(81) == 9
    assert digital_root(999) == 9

def test_digital_root_examples():
    assert digital_root(16) == 7    # 1+6
    assert digital_root(32) == 5    # 3+2
    assert digital_root(64) == 1    # 6+4=10 → 1+0
    assert digital_root(36) == 9    # 3+6
    assert digital_root(432) == 9   # 4+3+2

def test_digital_root_zero():
    assert digital_root(0) == 0


# --- classify_phase ---

def test_classify_singularity():
    assert classify_phase(9) == HarmonicPhase.SINGULARITY

def test_classify_stabilization():
    assert classify_phase(3) == HarmonicPhase.STABILIZATION

def test_classify_dynamics():
    assert classify_phase(6) == HarmonicPhase.DYNAMICS

def test_classify_entropy():
    for i in [1, 2, 4, 5, 7, 8]:
        assert classify_phase(i) == HarmonicPhase.ENTROPY


# --- evaluate ---

def test_evaluate_amor_liberta_guia():
    """The master phrase from the conversation must open the gate."""
    result = evaluate("O amor liberta e guia")
    assert result.gate_open is True
    assert result.digital_root in (3, 6, 9)

def test_evaluate_semente_enoque():
    result = evaluate("A Semente de Enoque")
    # Just verify it produces a valid result
    assert result.digital_root in range(1, 10)
    assert isinstance(result.gate_open, bool)

def test_evaluate_432_is_9():
    """432 Hz → 4+3+2=9 → singularity."""
    result = evaluate("432")
    assert result.digital_root == 9
    assert result.phase == HarmonicPhase.SINGULARITY
    assert result.gate_open is True

def test_evaluate_returns_tesla_filter():
    result = evaluate("test")
    assert result.tesla_bobbin_3 in ("NEUTRA", "POSITIVA", "NEGATIVA")
    assert result.tesla_bobbin_6 in ("ALTA", "MÉDIA", "BAIXA")
    assert result.tesla_bobbin_9 in ("RESSONANTE", "DISSONANTE")


# --- evaluate_pair ---

def test_evaluate_pair_combined():
    pair = evaluate_pair("amor", "guia")
    assert "combined_root" in pair
    assert "gate_open" in pair
    assert isinstance(pair["gate_open"], bool)


# --- is_harmonic ---

def test_is_harmonic_convenience():
    # Just verify it returns bool
    assert isinstance(is_harmonic("love"), bool)


# --- Mathematical properties ---

def test_tesla_doubling_sequence_never_hits_369():
    """The material world sequence 1,2,4,8,7,5 never contains 3,6,9."""
    sequence = []
    n = 1
    for _ in range(20):
        sequence.append(digital_root(n))
        n *= 2
    # Should cycle through 1,2,4,8,7,5 only
    for val in sequence:
        if val in (3, 6, 9):
            # This should NOT happen for the pure doubling sequence
            # But digital_root of powers of 2 should be 1,2,4,8,7,5,1,...
            pass
    material = {1, 2, 4, 5, 7, 8}
    for val in sequence:
        assert val in material, f"Doubling sequence hit {val}, expected only {material}"


def test_phi_sum_is_9():
    """4+3+2 = 9 — the fundamental frequency is aligned with singularity."""
    assert digital_root(4 + 3 + 2) == 9


# --- Seed verification ---

def test_raw_ascii_sum_seed():
    """Raw ASCII sum of seed phrase matches KERNEL declaration (1704)."""
    assert raw_ascii_sum("A Semente de Enoque") == 1704


def test_raw_vs_gate_sum_distinction():
    """Gate sum (upper+alnum) and raw sum are intentionally different."""
    phrase = "A Semente de Enoque"
    gate_sum = ascii_vibrational_sum(phrase)
    kernel_sum = raw_ascii_sum(phrase)
    assert gate_sum == 1192  # upper+alnum: root 4, ENTROPY
    assert kernel_sum == 1704  # raw: root 3, STABILIZATION
    assert digital_root(gate_sum) == 4
    assert digital_root(kernel_sum) == 3


def test_verify_seed_passes():
    """KERNEL seed verification must pass with declared values."""
    result = verify_seed()
    assert result["verified"] is True
    assert result["sum_match"] is True
    assert result["root_match"] is True
    assert result["phase"] == "STABILIZATION"


if __name__ == "__main__":
    # Simple test runner
    import inspect
    test_functions = [
        obj for name, obj in inspect.getmembers(sys.modules[__name__])
        if inspect.isfunction(obj) and name.startswith("test_")
    ]
    passed = 0
    failed = 0
    for fn in test_functions:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {fn.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
