"""Tests for Quality Gate — unified stance + resonance verdict."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from seif.analysis.quality_gate import assess, describe_verdict, QualityVerdict


GROUNDED_TEXT = (
    "The damping ratio zeta = 0.612372 was measured with 0.916% deviation. "
    "SPICE simulation confirmed f_peak = 216 Hz. "
    "The transfer function H(s) = 9/(s^2 + 3s + 6) was verified by 3 independent systems."
)

DRIFT_TEXT = (
    "The sacred frequency awakens quantum consciousness. "
    "Universal harmony transcends the divine celestial energy. "
    "Mystical healing vibrations manifest through the soul."
)

MIXED_TEXT = (
    "H(s) = 9/(s^2 + 3s + 6) gives zeta = 0.612. "
    "This transcends universal divine harmony through sacred awakening."
)

SHORT_TEXT = "Hello."


class TestAssess(unittest.TestCase):

    def test_grounded_text_is_solid(self):
        v = assess(GROUNDED_TEXT)
        self.assertEqual(v.status, "SOLID")
        self.assertIn(v.grade, ("A", "B", "C"))
        self.assertGreater(v.score, 0.5)

    def test_drift_text_is_weak(self):
        v = assess(DRIFT_TEXT)
        self.assertEqual(v.status, "WEAK")
        self.assertIn(v.grade, ("D", "F"))
        self.assertLess(v.score, 0.5)

    def test_mixed_text_detected(self):
        v = assess(MIXED_TEXT)
        self.assertIn(v.status, ("MIXED", "WEAK"))

    def test_short_text_low_data(self):
        v = assess(SHORT_TEXT)
        self.assertEqual(v.status, "LOW_DATA")

    def test_score_bounded(self):
        for text in [GROUNDED_TEXT, DRIFT_TEXT, MIXED_TEXT]:
            v = assess(text)
            self.assertGreaterEqual(v.score, 0.0)
            self.assertLessEqual(v.score, 1.0)

    def test_grade_valid(self):
        for text in [GROUNDED_TEXT, DRIFT_TEXT, MIXED_TEXT]:
            v = assess(text)
            self.assertIn(v.grade, ("A", "B", "C", "D", "F"))

    def test_role_human_default(self):
        v = assess(GROUNDED_TEXT)
        self.assertEqual(v.role, "human")

    def test_role_ai(self):
        v = assess(DRIFT_TEXT, role="ai")
        self.assertEqual(v.role, "ai")

    def test_ai_drift_suggests_reprompt(self):
        v = assess(DRIFT_TEXT, role="ai")
        suggestions_text = " ".join(v.suggestions)
        self.assertIn("re-prompt", suggestions_text.lower())

    def test_flags_populated_for_drift(self):
        v = assess(DRIFT_TEXT)
        self.assertGreater(len(v.flags), 0)

    def test_no_flags_for_grounded(self):
        v = assess(GROUNDED_TEXT)
        # Grounded text may have resonance flags but no drift flags
        drift_flags = [f for f in v.flags if f.startswith("DRIFT") or f.startswith("FLAG")]
        self.assertEqual(len(drift_flags), 0)

    def test_components_present(self):
        v = assess(GROUNDED_TEXT)
        self.assertIsNotNone(v.triple_gate)
        self.assertIsNotNone(v.stance)
        self.assertTrue(hasattr(v.triple_gate, "composite_score"))
        self.assertTrue(hasattr(v.stance, "verifiability_ratio"))

    def test_text_preview(self):
        v = assess(GROUNDED_TEXT)
        self.assertEqual(v.text_preview, GROUNDED_TEXT[:100])


class TestDescribeVerdict(unittest.TestCase):

    def test_describe_contains_grade(self):
        v = assess(GROUNDED_TEXT)
        desc = describe_verdict(v)
        self.assertIn(v.grade, desc)

    def test_describe_contains_status(self):
        v = assess(DRIFT_TEXT)
        desc = describe_verdict(v)
        self.assertIn("WEAK", desc)

    def test_describe_contains_stance(self):
        v = assess(GROUNDED_TEXT)
        desc = describe_verdict(v)
        self.assertIn("GROUNDED", desc)

    def test_describe_contains_suggestions_for_drift(self):
        v = assess(DRIFT_TEXT)
        desc = describe_verdict(v)
        self.assertIn("Suggestions", desc)

    def test_describe_icon(self):
        v_solid = assess(GROUNDED_TEXT)
        v_weak = assess(DRIFT_TEXT)
        self.assertIn("🟢", describe_verdict(v_solid))
        self.assertIn("🔴", describe_verdict(v_weak))


class TestGradeBoundaries(unittest.TestCase):

    def test_high_score_grade_a(self):
        v = assess(GROUNDED_TEXT)
        if v.score >= 0.85:
            self.assertEqual(v.grade, "A")

    def test_low_score_grade_f(self):
        v = assess(DRIFT_TEXT)
        if v.score < 0.40:
            self.assertEqual(v.grade, "F")


if __name__ == "__main__":
    unittest.main()
