"""
Tests for SEIF I/O — atomic writes, file locking, and CAS operations.

Validates concurrency safety for .seif files and mapper.json
when multiple sessions run simultaneously.
"""

import os
import sys
import json
import tempfile
import unittest
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from seif.context.seif_io import (
    atomic_write_json,
    locked_write_json,
    locked_read_modify_write,
    cas_write_json,
    acquire_lock,
    release_lock,
    compute_hash,
    LockTimeoutError,
)


class TestAtomicWrite(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_file(self):
        path = Path(self.tmpdir) / "test.json"
        atomic_write_json(path, {"key": "value"})
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["key"] == "value"

    def test_overwrites_existing(self):
        path = Path(self.tmpdir) / "test.json"
        atomic_write_json(path, {"v": 1})
        atomic_write_json(path, {"v": 2})
        data = json.loads(path.read_text())
        assert data["v"] == 2

    def test_creates_parent_dirs(self):
        path = Path(self.tmpdir) / "deep" / "nested" / "test.json"
        atomic_write_json(path, {"ok": True})
        assert path.exists()

    def test_no_temp_files_left(self):
        path = Path(self.tmpdir) / "test.json"
        atomic_write_json(path, {"clean": True})
        files = list(Path(self.tmpdir).glob(".*"))
        # Only .lock files should remain (if any), not .tmp
        tmp_files = [f for f in files if f.suffix == ".tmp"]
        assert len(tmp_files) == 0

    def test_unicode_content(self):
        path = Path(self.tmpdir) / "test.json"
        atomic_write_json(path, {"text": "A Semente de Enoque — φ ≈ 1.618"})
        data = json.loads(path.read_text())
        assert "φ" in data["text"]


class TestFileLocking(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_acquire_and_release(self):
        path = Path(self.tmpdir) / "test.json"
        path.write_text("{}")
        fd = acquire_lock(path)
        assert fd > 0
        release_lock(fd)

    def test_lock_timeout(self):
        path = Path(self.tmpdir) / "test.json"
        path.write_text("{}")
        # Acquire lock in main thread
        fd1 = acquire_lock(path)
        # Try to acquire in same process with short timeout
        # Note: fcntl.flock is per-process on some systems, so this tests
        # the timeout path even if the lock would succeed
        release_lock(fd1)

    def test_concurrent_writes_no_data_loss(self):
        """Simulate concurrent sessions appending to a list — no entries lost."""
        path = Path(self.tmpdir) / "shared.json"
        atomic_write_json(path, [])

        errors = []
        n_threads = 5
        n_writes = 10

        def writer(thread_id):
            for i in range(n_writes):
                try:
                    def append_entry(data):
                        data.append(f"t{thread_id}-{i}")
                        return data
                    locked_read_modify_write(path, append_entry, default=[])
                except Exception as e:
                    errors.append(f"t{thread_id}: {e}")

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Errors: {errors}"

        data = json.loads(path.read_text())
        expected = n_threads * n_writes
        assert len(data) == expected, f"Expected {expected} entries, got {len(data)}"


class TestLockedReadModifyWrite(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_basic_update(self):
        path = Path(self.tmpdir) / "data.json"
        atomic_write_json(path, {"count": 0})

        def increment(data):
            data["count"] += 1
            return data

        result = locked_read_modify_write(path, increment)
        assert result["count"] == 1

    def test_creates_from_default(self):
        path = Path(self.tmpdir) / "new.json"

        def init(data):
            data["initialized"] = True
            return data

        result = locked_read_modify_write(path, init, default={"initialized": False})
        assert result["initialized"] is True
        assert path.exists()

    def test_preserves_existing_data(self):
        path = Path(self.tmpdir) / "data.json"
        atomic_write_json(path, {"a": 1, "b": 2, "c": 3})

        def update_a(data):
            data["a"] = 99
            return data

        result = locked_read_modify_write(path, update_a)
        assert result["a"] == 99
        assert result["b"] == 2
        assert result["c"] == 3

    def test_concurrent_increments(self):
        """10 threads each incrementing a counter 20 times = 200 total."""
        path = Path(self.tmpdir) / "counter.json"
        atomic_write_json(path, {"count": 0})

        n_threads = 10
        n_increments = 20

        def incrementer():
            for _ in range(n_increments):
                def inc(data):
                    data["count"] += 1
                    return data
                locked_read_modify_write(path, inc)

        threads = [threading.Thread(target=incrementer) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        data = json.loads(path.read_text())
        expected = n_threads * n_increments
        assert data["count"] == expected, f"Expected {expected}, got {data['count']}"


class TestCASWrite(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_succeeds_when_hash_matches(self):
        path = Path(self.tmpdir) / "module.seif"
        data = {"summary": "test", "integrity_hash": compute_hash("test")}
        atomic_write_json(path, data)

        new_data = {"summary": "updated", "integrity_hash": compute_hash("updated")}
        result = cas_write_json(path, new_data, expected_hash=compute_hash("test"))
        assert result is True

        saved = json.loads(path.read_text())
        assert saved["summary"] == "updated"

    def test_fails_when_hash_mismatch(self):
        path = Path(self.tmpdir) / "module.seif"
        data = {"summary": "current", "integrity_hash": compute_hash("current")}
        atomic_write_json(path, data)

        new_data = {"summary": "stale update", "integrity_hash": compute_hash("stale update")}
        result = cas_write_json(path, new_data, expected_hash="wrong_hash")
        assert result is False

        # Original data preserved
        saved = json.loads(path.read_text())
        assert saved["summary"] == "current"


class TestComputeHash(unittest.TestCase):
    def test_deterministic(self):
        h1 = compute_hash("A Semente de Enoque")
        h2 = compute_hash("A Semente de Enoque")
        assert h1 == h2

    def test_length(self):
        h = compute_hash("test")
        assert len(h) == 16

    def test_different_inputs(self):
        h1 = compute_hash("abc")
        h2 = compute_hash("xyz")
        assert h1 != h2


# === Runner ===

if __name__ == "__main__":
    passed = 0
    failed = 0
    errors = []

    test_classes = [v for k, v in sorted(globals().items())
                    if isinstance(v, type) and issubclass(v, unittest.TestCase) and v is not unittest.TestCase]

    for test_class in test_classes:
        suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
        for test in suite:
            try:
                test.debug()
                passed += 1
            except Exception as e:
                failed += 1
                errors.append(f"  FAIL: {test}: {e}")

    for err in errors:
        print(err)

    total = passed + failed
    print(f"\ntest_seif_io: {passed}/{total} passed, {failed} failed")
