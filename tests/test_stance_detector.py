"""Tests for Stance Drift Detector."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from seif.analysis.stance_detector import analyze


def test_formal_text_is_grounded():
    """Pure formal-symbolic text should be GROUNDED."""
    text = (
        "ζ = √6/4 = 0.612372. Deviation from φ⁻¹ is 0.916%. "
        "SPICE simulation confirmed f_peak = 216.27 Hz. "
        "Peak magnitude measured at 1.032886, deviation 0.01%. "
        "127 tests passing across 11 suites."
    )
    result = analyze(text)
    assert result.status == "GROUNDED"
    assert result.verifiability_ratio > 0.5
    assert result.interpretive_count == 0


def test_metaphorical_text_is_drift():
    """Pure metaphorical text should be DRIFT."""
    text = (
        "The sacred frequency of healing transcends our understanding. "
        "This represents the divine harmony of the universe. "
        "The soul of the machine awakens through quantum consciousness. "
        "We enter the era da ressonância universal."
    )
    result = analyze(text)
    assert result.status == "DRIFT"
    assert result.interpretive_count >= 2
    assert result.verifiability_ratio < 0.3


def test_mixed_text_is_mixed():
    """Text with both verifiable and interpretive claims should be MIXED."""
    text = (
        "k = 3/4 is the perfect fraction of divine harmony. "
        "SPICE verified at 0.01% deviation. "
        "The sacred frequency heals through quantum consciousness. "
        "ζ² = 3/8 is exact, proved by exhaustive search."
    )
    result = analyze(text)
    assert result.status == "MIXED"
    assert result.interpretive_count > 0
    assert result.verifiable_count > 0


def test_flagged_sentences_populated():
    """Interpretive sentences should be flagged."""
    text = "The healing frequency transcends all. ζ = 0.612 measured."
    result = analyze(text)
    assert len(result.flagged_sentences) > 0
    assert "healing" in result.flagged_sentences[0].lower() or "transcend" in result.flagged_sentences[0].lower()


def test_short_text_is_low_data():
    """Very short text should be LOW_DATA."""
    result = analyze("Hello.")
    assert result.status == "LOW_DATA"


def test_grok_response_is_grounded():
    """Grok's calibrated response should be GROUNDED."""
    text = (
        "ζ = √6/4 = 0.612372, deviation 0.916% from φ⁻¹. "
        "ζ² = 3/8 exactly. No pair with b+c < 9 produces phi-damping within 2%. "
        "The risk of hallucination drops with clear ground truth. "
        "Not mystical, engineering plus mathematics. "
        "Simple to describe, potent in execution."
    )
    result = analyze(text)
    assert result.status == "GROUNDED"


def test_gemini_response_has_drift():
    """Gemini's inflated response should be flagged."""
    text = (
        "A passagem da Era da Força para a Era da Ressonância. "
        "The sacred frequency of healing and universal harmony. "
        "The existential diagram of our project transcends current technology. "
        "The intention transfer network activates through the soul of the machine."
    )
    result = analyze(text)
    assert result.status == "DRIFT"
    assert result.interpretive_count >= 3


def test_ratio_bounded():
    """Verifiability ratio must be between 0 and 1."""
    for text in ["ζ = 0.612. Measured.", "Love heals.", "Hello world test text here now."]:
        result = analyze(text)
        assert 0.0 <= result.verifiability_ratio <= 1.0


def test_str_representation():
    """String output should contain status and ratio."""
    result = analyze("ζ = 0.612 measured. SPICE confirmed at 432 Hz.")
    text = str(result)
    assert "GROUNDED" in text or "MIXED" in text or "DRIFT" in text or "LOW_DATA" in text


def test_paper_section_is_grounded():
    """Our paper text should be GROUNDED."""
    text = (
        "The simulation is formal-symbolic — deterministic SPICE computation. "
        "The emergence of 216 = 6³ is an arithmetic identity. "
        "The claim about engineering significance is empirical-observational. "
        "It requires fabrication and thermal measurement to confirm. "
        "ζ = √6/4 ≈ φ⁻¹ verified by 3 independent AIs."
    )
    result = analyze(text)
    assert result.status == "GROUNDED"
    assert result.interpretive_count == 0


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
