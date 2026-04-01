"""Tests for Context Ingest — filter external text by project relevance."""

import sys
import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from seif.context.ingest import (
    ingest, describe_ingest, _load_raw_text, IngestResult,
)
from seif.context.context_manager import create_module, save_module


def _create_temp_project_seif(summary="Project ACME: REST API for user auth. Stack: Python, FastAPI, PostgreSQL."):
    """Create a temporary project.seif for testing."""
    module = create_module("acme (git)", 5000, summary, author="test")
    tmp = Path(tempfile.mktemp(suffix=".seif"))
    save_module(module, target_path=tmp)
    return tmp


class TestLoadRawText(unittest.TestCase):

    def test_load_from_string(self):
        text, label = _load_raw_text("Some meeting notes here")
        self.assertEqual(text, "Some meeting notes here")
        self.assertEqual(label, "string")

    def test_load_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Meeting notes from file")
            tmp_path = f.name
        try:
            text, label = _load_raw_text(tmp_path)
            self.assertEqual(text, "Meeting notes from file")
            self.assertIn("file:", label)
        finally:
            os.unlink(tmp_path)

    def test_nonexistent_file_treated_as_string(self):
        text, label = _load_raw_text("/nonexistent/path/file.txt")
        self.assertIn("/nonexistent", text)
        self.assertEqual(label, "string")


class TestIngestEdgeCases(unittest.TestCase):

    def test_too_short_input(self):
        tmp = _create_temp_project_seif()
        try:
            result = ingest("Hi", str(tmp), author="test")
            self.assertFalse(result.relevant)
            self.assertFalse(result.contributed)
            self.assertIn("too short", result.error)
        finally:
            os.unlink(tmp)

    def test_invalid_project_path(self):
        result = ingest(
            "Some long meeting notes about the project and its features and progress",
            "/nonexistent/project.seif",
            author="test"
        )
        self.assertFalse(result.relevant)
        self.assertFalse(result.contributed)
        self.assertIn("Cannot load", result.error)

    @patch("seif.context.ingest._filter_via_ai")
    def test_no_relevant_content(self, mock_filter):
        mock_filter.return_value = ("NO_RELEVANT_CONTENT", True, "")
        tmp = _create_temp_project_seif()
        try:
            result = ingest(
                "The marketing team discussed Q3 budget for the Europe campaign.",
                str(tmp), author="test"
            )
            self.assertFalse(result.relevant)
            self.assertFalse(result.contributed)
            self.assertGreater(result.raw_words, 0)
        finally:
            os.unlink(tmp)

    @patch("seif.context.ingest._filter_via_ai")
    def test_relevant_content_contributed(self, mock_filter):
        mock_filter.return_value = (
            "### Decisions\n- Migrate auth to JWT with 24h expiry.\n"
            "### Action Items\n- Alice: update FastAPI middleware by Friday.\n"
            "### Context Updates\n- API latency p99 dropped to 45ms after Redis cache.",
            True, ""
        )
        tmp = _create_temp_project_seif()
        try:
            result = ingest(
                "Long daily standup transcript with lots of irrelevant content "
                "about other projects but also some ACME project updates.",
                str(tmp), author="daily-bot", via="daily"
            )
            self.assertTrue(result.relevant)
            self.assertTrue(result.contributed)
            self.assertGreater(result.filtered_words, 0)
            self.assertGreater(result.compression_ratio, 0)
            self.assertIn(result.quality_grade, ("A", "B", "C", "D", "F"))
            self.assertGreater(result.module_version, 0)
        finally:
            os.unlink(tmp)

    @patch("seif.context.ingest._filter_via_ai")
    def test_ai_failure(self, mock_filter):
        mock_filter.return_value = ("", False, "Backend timeout")
        tmp = _create_temp_project_seif()
        try:
            result = ingest(
                "Some meeting notes about the project features and timeline.",
                str(tmp), author="test"
            )
            self.assertFalse(result.contributed)
            self.assertIn("Backend timeout", result.error)
        finally:
            os.unlink(tmp)


class TestDescribeIngest(unittest.TestCase):

    def test_describe_no_relevant(self):
        r = IngestResult(
            source="stdin", raw_words=500, filtered_text="",
            filtered_words=0, compression_ratio=0, quality_score=0,
            quality_grade="-", relevant=False, contributed=False,
        )
        desc = describe_ingest(r)
        self.assertIn("No content relevant", desc)

    def test_describe_contributed(self):
        r = IngestResult(
            source="file:daily.txt", raw_words=2000,
            filtered_text="Some filtered content",
            filtered_words=50, compression_ratio=40.0,
            quality_score=0.72, quality_grade="B",
            relevant=True, contributed=True,
            module_version=3, module_hash="abc123",
        )
        desc = describe_ingest(r)
        self.assertIn("Grade B", desc)
        self.assertIn("version 3", desc)
        self.assertIn("40.0:1", desc)

    def test_describe_error(self):
        r = IngestResult(
            source="string", raw_words=3,
            filtered_text="", filtered_words=0,
            compression_ratio=0, quality_score=0,
            quality_grade="F", relevant=False, contributed=False,
            error="Input too short",
        )
        desc = describe_ingest(r)
        self.assertIn("FAILED", desc)


if __name__ == "__main__":
    unittest.main()
