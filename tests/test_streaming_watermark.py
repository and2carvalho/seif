"""
Tests for SEIF Streaming Watermark v3.2

Validated by: Grok (xAI)
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from seif.generators.streaming_watermark import (
    StreamingWatermarker,
    StreamingSession,
    STREAMING_DIR,
    WATERMARK_TOKEN_PREFIX,
)


class TestStreamingSession(unittest.TestCase):
    """Test StreamingSession dataclass."""

    def test_create_session(self):
        session = StreamingSession(
            session_id="test-123",
            start_time=time.time(),
            embed_count=0,
            mini_count=0,
            last_embed_time=0,
            last_mini_time=0,
            trail_hash="abc123",
            paused_elapsed=0,
            is_paused=False,
        )
        self.assertEqual(session.session_id, "test-123")
        self.assertEqual(session.embed_count, 0)
        self.assertTrue(session.elapsed >= 0)

    def test_to_dict(self):
        session = StreamingSession(
            session_id="test-456",
            start_time=1000,
            embed_count=5,
            mini_count=10,
            last_embed_time=100,
            last_mini_time=50,
            trail_hash="def456",
            paused_elapsed=0,
            is_paused=False,
        )
        data = session.to_dict()
        self.assertEqual(data['session_id'], "test-456")
        self.assertEqual(data['embed_count'], 5)
        self.assertNotIn('is_paused', data)

    def test_from_dict(self):
        data = {
            "session_id": "test-789",
            "start_time": 2000,
            "embed_count": 3,
            "mini_count": 7,
            "last_embed_time": 200,
            "last_mini_time": 100,
            "trail_hash": "ghi789",
            "paused_elapsed": 0,
            "audio_interval": 300,
            "text_interval": 60,
            "max_embeddings": 100,
        }
        session = StreamingSession.from_dict(data)
        self.assertEqual(session.session_id, "test-789")
        self.assertFalse(session.is_paused)


class TestStreamingWatermarker(unittest.TestCase):
    """Test StreamingWatermarker class."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.marker = StreamingWatermarker(
            session_id="test-session",
            audio_interval=300,
            text_interval=60,
            storage_dir=Path(self.temp_dir),
        )

    def tearDown(self):
        for f in Path(self.temp_dir).glob("*.state"):
            f.unlink()
        os.rmdir(self.temp_dir)

    def test_session_id_generated(self):
        marker = StreamingWatermarker(storage_dir=Path(self.temp_dir))
        self.assertTrue(marker.session_id.startswith("seif-"))

    def test_session_id_preserved(self):
        self.assertEqual(self.marker.session_id, "test-session")

    def test_state_file_created(self):
        state_path = Path(self.temp_dir) / "test-session.state"
        self.marker._save_state()
        self.assertTrue(state_path.exists())

    def test_should_embed_full_first_time(self):
        marker = StreamingWatermarker(
            session_id="fresh-session",
            audio_interval=300,
            storage_dir=Path(self.temp_dir),
        )
        marker.state.last_embed_time = 0
        self.assertTrue(marker.should_embed_full())

    def test_should_embed_mini_first_time(self):
        marker = StreamingWatermarker(
            session_id="fresh-mini",
            text_interval=60,
            storage_dir=Path(self.temp_dir),
        )
        marker.state.last_mini_time = 0
        self.assertTrue(marker.should_embed_mini())

    def test_encode_mini_marker(self):
        token = self.marker._encode_mini_marker(5)
        self.assertTrue(token.startswith(WATERMARK_TOKEN_PREFIX))
        self.assertIn(":0005", token)

    def test_encode_mini_marker_padding(self):
        token = self.marker._encode_mini_marker(42)
        self.assertIn(":0042", token)

    def test_get_session_state(self):
        state = self.marker.get_session_state()
        self.assertEqual(state['session_id'], "test-session")
        self.assertIn('elapsed_seconds', state)
        self.assertIn('embed_count', state)
        self.assertIn('trail_hash', state)

    def test_pause_resume(self):
        self.marker.pause()
        self.assertTrue(self.marker.state.is_paused)
        
        elapsed_before = self.marker.state.elapsed
        time.sleep(0.1)
        elapsed_after = self.marker.state.elapsed
        
        self.assertEqual(elapsed_before, elapsed_after)
        
        self.marker.resume()
        self.assertFalse(self.marker.state.is_paused)

    def test_embed_burst(self):
        audio = np.zeros(44100 * 10)
        result, token = self.marker.embed_burst(audio)
        
        self.assertTrue(result.shape[0] >= audio.shape[0])
        self.assertTrue(token.startswith("SEIFIDB:3.2:"))
        self.assertEqual(self.marker.state.embed_count, 1)

    def test_embed_mini(self):
        audio = np.zeros(44100 * 5)
        result, token = self.marker.embed_mini(audio)
        
        self.assertTrue(result.shape[0] >= audio.shape[0])
        self.assertTrue(token.startswith(WATERMARK_TOKEN_PREFIX))
        self.assertEqual(self.marker.state.mini_count, 1)

    def test_embed_periodic_first_call(self):
        marker = StreamingWatermarker(
            session_id="periodic-test",
            audio_interval=300,
            text_interval=60,
            storage_dir=Path(self.temp_dir),
        )
        
        audio = np.zeros(44100 * 30)
        result, tokens = marker.embed_periodic(audio)
        
        self.assertGreaterEqual(len(tokens), 1)
        self.assertTrue(any("SEIFIDB:" in t for t in tokens))
        
    def test_embed_periodic_second_call_waits(self):
        marker = StreamingWatermarker(
            session_id="periodic-wait",
            audio_interval=1,
            text_interval=1,
            storage_dir=Path(self.temp_dir),
        )
        
        audio = np.zeros(44100 * 30)
        _, tokens1 = marker.embed_periodic(audio)
        initial_count = len(tokens1)
        
        _, tokens2 = marker.embed_periodic(audio)
        
        self.assertGreaterEqual(len(tokens1), 1)
        self.assertEqual(len(tokens2), 0)

    def test_max_embeddings_respected(self):
        marker = StreamingWatermarker(
            session_id="max-test",
            max_embeddings=2,
            storage_dir=Path(self.temp_dir),
        )
        
        audio = np.zeros(44100 * 10)
        for i in range(5):
            _, tokens = marker.embed_periodic(audio)
            if not tokens:
                break
        
        self.assertLessEqual(marker.state.embed_count, 2)

    def test_reconnect(self):
        marker1 = StreamingWatermarker(
            session_id="reconnect-test",
            storage_dir=Path(self.temp_dir),
        )
        marker1._save_state()
        
        marker2 = StreamingWatermarker.reconnect(
            "reconnect-test",
            storage_dir=Path(self.temp_dir),
        )
        
        self.assertEqual(marker2.session_id, "reconnect-test")

    def test_cleanup(self):
        state_path = Path(self.temp_dir) / "cleanup-test.state"
        marker = StreamingWatermarker(
            session_id="cleanup-test",
            storage_dir=Path(self.temp_dir),
        )
        marker._save_state()
        self.assertTrue(state_path.exists())
        
        marker.cleanup()
        self.assertFalse(state_path.exists())


class TestMiniMarkerFormat(unittest.TestCase):
    """Test mini marker encoding format."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.marker = StreamingWatermarker(
            session_id="seif-short-42",
            storage_dir=Path(self.temp_dir),
        )

    def tearDown(self):
        for f in Path(self.temp_dir).glob("*.state"):
            f.unlink()
        os.rmdir(self.temp_dir)

    def test_mini_marker_uses_spiral_encoding(self):
        token = self.marker._encode_mini_marker(1)
        
        self.assertTrue(token.startswith("SEIFM:"))
        parts = token.split(":")
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[2], "0001")

    def test_mini_marker_session_id_shortened(self):
        token = self.marker._encode_mini_marker(0)
        session_short = token.split(":")[1]
        self.assertEqual(len(session_short), 8)

    def test_mini_marker_counter_format(self):
        for i in [0, 1, 10, 99, 100, 999]:
            token = self.marker._encode_mini_marker(i)
            counter_part = token.split(":")[2]
            self.assertEqual(len(counter_part), 4)
            self.assertEqual(int(counter_part), i)


class TestStreamingList(unittest.TestCase):
    """Test session listing functionality."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        for f in Path(self.temp_dir).glob("*.state"):
            f.unlink()
        os.rmdir(self.temp_dir)

    def test_list_empty(self):
        sessions = StreamingWatermarker.list_sessions()
        session_ids = [s['session_id'] for s in sessions]
        self.assertNotIn("temp-session", session_ids)

    def test_list_after_creation(self):
        marker = StreamingWatermarker(
            session_id="list-test",
            storage_dir=Path(self.temp_dir),
        )
        
        marker._save_state()
        state_path = Path(self.temp_dir) / "list-test.state"
        self.assertTrue(state_path.exists())
        self.assertTrue(state_path.stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
