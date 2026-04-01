"""Tests for Context Advisor — protocol-driven conversation optimization."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from seif.context.advisor import advise, describe_advice, _detect_independence, _detect_quality_decline


class TestDetectIndependence(unittest.TestCase):

    def test_independent_task(self):
        score = _detect_independence("verify and calculate and test this benchmark independently")
        self.assertGreater(score, 0.5)

    def test_dependent_task(self):
        score = _detect_independence("continue with the code above and modify the function")
        self.assertLess(score, 0.4)

    def test_search_task(self):
        score = _detect_independence("search for all files matching *.py")
        self.assertGreater(score, 0.4)

    def test_empty_task(self):
        score = _detect_independence("")
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestDetectQualityDecline(unittest.TestCase):

    def test_declining(self):
        declining, mag = _detect_quality_decline([0.8, 0.7, 0.6, 0.4, 0.3, 0.2])
        self.assertTrue(declining)
        self.assertGreater(mag, 0)

    def test_stable(self):
        declining, mag = _detect_quality_decline([0.7, 0.7, 0.7, 0.7])
        self.assertFalse(declining)

    def test_improving(self):
        declining, mag = _detect_quality_decline([0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        self.assertFalse(declining)

    def test_too_few_scores(self):
        declining, mag = _detect_quality_decline([0.5])
        self.assertFalse(declining)


class TestAdvise(unittest.TestCase):

    def test_continue_for_dependent_task(self):
        advice = advise(task_description="continue modifying the code above")
        self.assertEqual(advice.action, "CONTINUE")

    def test_spawn_for_independent_task(self):
        advice = advise(task_description="verify calculate test and benchmark the transfer function independently")
        self.assertEqual(advice.action, "SPAWN")

    def test_compress_at_high_context(self):
        advice = advise(context_usage_pct=85)
        self.assertEqual(advice.action, "COMPRESS")

    def test_confidence_bounded(self):
        advice = advise(task_description="test something")
        self.assertGreaterEqual(advice.confidence, 0.0)
        self.assertLessEqual(advice.confidence, 1.0)

    def test_default_is_continue(self):
        advice = advise(project_seif_path="/nonexistent/.seif/project.seif")
        self.assertEqual(advice.action, "CONTINUE")

    def test_suggestions_present_when_declining(self):
        advice = advise(
            recent_quality_scores=[0.9, 0.8, 0.7, 0.5, 0.3, 0.2],
        )
        self.assertGreater(len(advice.suggestions), 0)


class TestDescribeAdvice(unittest.TestCase):

    def test_describe_continue(self):
        advice = advise(task_description="fix the bug in main.py")
        desc = describe_advice(advice)
        self.assertIn("CONTINUE", desc)

    def test_describe_spawn(self):
        advice = advise(task_description="verify calculate test and benchmark the compression ratio independently")
        desc = describe_advice(advice)
        self.assertIn("SPAWN", desc)

    def test_describe_compress(self):
        advice = advise(context_usage_pct=90)
        desc = describe_advice(advice)
        self.assertIn("COMPRESS", desc)


if __name__ == "__main__":
    unittest.main()
