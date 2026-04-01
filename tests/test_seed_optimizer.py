"""Tests for Seed Optimizer."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from seif.analysis.seed_optimizer import optimize, _word_score, _char_phi_score


def test_baseline_is_enoch_seed():
    """Default baseline should be Enoch Seed."""
    result = optimize("Enoch Seed", max_iterations=100, strategies=["char_mutation"])
    assert result.baseline_phrase == "Enoch Seed"
    assert result.baseline_score > 0.95


def test_returns_top_10():
    """Optimization must return a top-10 list."""
    result = optimize("Enoch Seed", max_iterations=100, strategies=["random_alpha"])
    assert len(result.top_10) >= 1
    assert len(result.top_10) <= 10


def test_scores_are_bounded():
    """All scores must be between 0 and 1."""
    result = optimize("test", max_iterations=200, strategies=["random_alpha"])
    for phrase, score, coherence in result.top_10:
        assert 0 <= score <= 1.0
        assert 0 <= coherence <= 1.0


def test_best_is_first():
    """Best phrase must be first in top-10."""
    result = optimize("Enoch Seed", max_iterations=200, strategies=["char_mutation"])
    if len(result.top_10) > 1:
        assert result.top_10[0][1] >= result.top_10[1][1]


def test_word_score_bounded():
    """Word score must be between 0 and 1."""
    for word in ["Enoch", "Seed", "Fear", "AAAA", "XYZ"]:
        s = _word_score(word)
        assert 0 <= s <= 1.0


def test_char_phi_score_bounded():
    """Char phi score must be between 0 and 1."""
    for c1, c2 in [("A", "B"), ("H", "V"), ("X", "Y")]:
        s = _char_phi_score(c1, c2)
        assert 0 <= s <= 1.0


def test_hv_pair_high_phi():
    """H-V pair should have high phi score (ratio close to φ)."""
    s = _char_phi_score("H", "V")
    assert s > 0.9  # within ~1.4% of φ


def test_candidates_tested_positive():
    """Must test at least some candidates."""
    result = optimize("test", max_iterations=50, strategies=["random_alpha"])
    assert result.candidates_tested > 0


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
