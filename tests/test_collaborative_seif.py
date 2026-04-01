"""Tests for collaborative .seif v2 — contributor tracking, hash chaining, backward compatibility."""

import sys
import os
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from seif.context.context_manager import (
    SeifModule, create_module, save_module, load_module,
    contribute_to_module, _compute_hash,
)


class TestV1BackwardCompatibility(unittest.TestCase):
    """v1 files must load without error, v2 fields get defaults."""

    def test_v1_dict_loads_with_defaults(self):
        """SeifModule(**v1_data) should work — missing v2 fields get defaults."""
        v1_data = {
            "_instruction": "test",
            "protocol": "SEIF-MODULE-v1",
            "source": "test_source",
            "original_words": 1000,
            "compressed_words": 100,
            "compression_ratio": 10.0,
            "summary": "Test summary with 3 data points.",
            "resonance": {"ascii_root": 3, "ascii_phase": "STABILIZATION",
                          "coherence": 0.5, "gate": "CLOSED"},
            "verified_data": ["3 data points"],
            "integrity_hash": "abc123",
            "active": True,
        }
        module = SeifModule(**v1_data)
        self.assertEqual(module.version, 1)
        self.assertEqual(module.contributors, [])
        self.assertIsNone(module.parent_hash)
        self.assertIsNone(module.updated_at)

    def test_v1_file_roundtrip(self):
        """Write v1 JSON, load, verify v2 defaults applied."""
        v1_json = {
            "_instruction": "test",
            "protocol": "SEIF-MODULE-v1",
            "source": "roundtrip",
            "original_words": 500,
            "compressed_words": 50,
            "compression_ratio": 10.0,
            "summary": "Roundtrip test summary.",
            "resonance": {"ascii_root": 6, "ascii_phase": "DYNAMICS",
                          "coherence": 0.4, "gate": "CLOSED"},
            "verified_data": [],
            "integrity_hash": "5f905ff8a9a7c406",  # SHA-256[:16] of summary
            "active": True,
        }
        with tempfile.NamedTemporaryFile(suffix=".seif", mode="w",
                                          delete=False) as f:
            json.dump(v1_json, f)
            tmp_path = f.name
        try:
            module = load_module(tmp_path)
            self.assertEqual(module.version, 1)
            self.assertEqual(module.contributors, [])
            self.assertIsNone(module.parent_hash)
        finally:
            os.unlink(tmp_path)


class TestCreateModuleV2(unittest.TestCase):
    """create_module with author/via populates v2 fields."""

    def test_create_with_author(self):
        module = create_module("test", 1000, "Summary with 42 measurements.",
                               author="André", via="claude-opus")
        self.assertEqual(len(module.contributors), 1)
        self.assertEqual(module.contributors[0]["author"], "André")
        self.assertEqual(module.contributors[0]["via"], "claude-opus")
        self.assertEqual(module.contributors[0]["action"], "created")
        self.assertIn("at", module.contributors[0])

    def test_create_without_author(self):
        module = create_module("test", 1000, "Summary without author.")
        self.assertEqual(module.contributors, [])
        self.assertEqual(module.version, 1)


class TestContributeToModule(unittest.TestCase):
    """contribute_to_module: merge, chain, version increment."""

    def _create_temp_module(self, summary="Original summary with 9 data points."):
        module = create_module("collab_test", 5000, summary, author="alice", via="gemini")
        with tempfile.NamedTemporaryFile(suffix=".seif", delete=False,
                                          dir=tempfile.gettempdir()) as f:
            tmp_path = Path(f.name)
        save_module(module, target_path=tmp_path)
        return tmp_path, module

    def test_contribute_adds_contributor(self):
        tmp, original = self._create_temp_module()
        try:
            updated, _ = contribute_to_module(str(tmp), "New findings about 14.4 Hz.",
                                               author="bob", via="claude")
            self.assertEqual(len(updated.contributors), 2)
            self.assertEqual(updated.contributors[0]["author"], "alice")
            self.assertEqual(updated.contributors[1]["author"], "bob")
            self.assertEqual(updated.contributors[1]["action"], "contributed")
        finally:
            os.unlink(tmp)

    def test_contribute_parent_hash_chain(self):
        tmp, original = self._create_temp_module()
        try:
            original_hash = original.integrity_hash
            updated, _ = contribute_to_module(str(tmp), "First contribution.",
                                               author="bob")
            self.assertEqual(updated.parent_hash, original_hash)

            # Second contribution chains to first
            hash_after_first = updated.integrity_hash
            updated2, _ = contribute_to_module(str(tmp), "Second contribution.",
                                                author="carol")
            self.assertEqual(updated2.parent_hash, hash_after_first)
        finally:
            os.unlink(tmp)

    def test_contribute_integrity_hash_changes(self):
        tmp, original = self._create_temp_module()
        try:
            updated, _ = contribute_to_module(str(tmp), "Different content.",
                                               author="bob")
            self.assertNotEqual(updated.integrity_hash, original.integrity_hash)
        finally:
            os.unlink(tmp)

    def test_contribute_version_increments(self):
        tmp, _ = self._create_temp_module()
        try:
            m1, _ = contribute_to_module(str(tmp), "V2.", author="bob")
            self.assertEqual(m1.version, 2)
            m2, _ = contribute_to_module(str(tmp), "V3.", author="carol")
            self.assertEqual(m2.version, 3)
        finally:
            os.unlink(tmp)

    def test_contribute_summary_appended(self):
        tmp, original = self._create_temp_module("Original content here.")
        try:
            updated, _ = contribute_to_module(str(tmp), "New findings here.",
                                               author="bob")
            self.assertIn("Original content here.", updated.summary)
            self.assertIn("New findings here.", updated.summary)
            self.assertIn("Contribution by bob", updated.summary)
        finally:
            os.unlink(tmp)

    def test_contribute_verified_data_grows(self):
        tmp, original = self._create_temp_module()
        try:
            original_count = len(original.verified_data)
            updated, _ = contribute_to_module(
                str(tmp), "Found 432 Hz and 438 Hz measurements.\n216 Hz peak confirmed.",
                author="bob")
            self.assertGreaterEqual(len(updated.verified_data), original_count)
        finally:
            os.unlink(tmp)

    def test_contribute_protocol_becomes_v2(self):
        tmp, _ = self._create_temp_module()
        try:
            updated, _ = contribute_to_module(str(tmp), "Update.", author="bob")
            self.assertEqual(updated.protocol, "SEIF-MODULE-v2")
        finally:
            os.unlink(tmp)

    def test_contribute_updated_at_set(self):
        tmp, _ = self._create_temp_module()
        try:
            updated, _ = contribute_to_module(str(tmp), "Update.", author="bob")
            self.assertIsNotNone(updated.updated_at)
        finally:
            os.unlink(tmp)

    def test_multiple_contributions_full_chain(self):
        """3 contributions: verify complete parent_hash chain None -> h1 -> h2."""
        tmp, original = self._create_temp_module()
        try:
            h0 = original.integrity_hash
            self.assertIsNone(original.parent_hash)

            m1, _ = contribute_to_module(str(tmp), "C1.", author="a")
            self.assertEqual(m1.parent_hash, h0)
            h1 = m1.integrity_hash

            m2, _ = contribute_to_module(str(tmp), "C2.", author="b")
            self.assertEqual(m2.parent_hash, h1)
            h2 = m2.integrity_hash

            m3, _ = contribute_to_module(str(tmp), "C3.", author="c")
            self.assertEqual(m3.parent_hash, h2)
            self.assertEqual(m3.version, 4)
            self.assertEqual(len(m3.contributors), 4)  # alice + a + b + c
        finally:
            os.unlink(tmp)

    def test_v1_file_upgrade_via_contribute(self):
        """A v1 file on disk upgrades to v2 after contribution."""
        v1_json = {
            "_instruction": "test",
            "protocol": "SEIF-MODULE-v1",
            "source": "legacy",
            "original_words": 2000,
            "compressed_words": 100,
            "compression_ratio": 20.0,
            "summary": "Legacy v1 content with 3 items.",
            "resonance": {"ascii_root": 3, "ascii_phase": "STABILIZATION",
                          "coherence": 0.3, "gate": "CLOSED"},
            "verified_data": ["3 items"],
            "integrity_hash": "legacy_hash",
            "active": True,
        }
        with tempfile.NamedTemporaryFile(suffix=".seif", mode="w",
                                          delete=False) as f:
            json.dump(v1_json, f)
            tmp_path = f.name
        try:
            updated, _ = contribute_to_module(tmp_path, "Upgrade content.",
                                               author="dev", via="claude")
            self.assertEqual(updated.protocol, "SEIF-MODULE-v2")
            self.assertEqual(updated.version, 2)
            self.assertEqual(updated.parent_hash, "legacy_hash")
            self.assertEqual(len(updated.contributors), 1)

            # Reload from disk to verify persistence
            reloaded = load_module(tmp_path)
            self.assertEqual(reloaded.version, 2)
            self.assertEqual(reloaded.protocol, "SEIF-MODULE-v2")
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()
