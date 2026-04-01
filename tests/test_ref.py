"""Tests for Project Reference — SEIF-REF-v1 protocol."""

import sys
import os
import json
import tempfile
import subprocess
import shutil
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from seif.context.ref import (
    ProjectRef, create_ref, save_ref, load_ref, update_ref_commit,
)


def _create_temp_repo(name="test-project"):
    """Create a temporary git repo with a manifest and README."""
    root = Path(tempfile.mkdtemp()) / name
    root.mkdir()

    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "1.0"\n'
        f'description = "Test project"\n'
    )
    (root / "README.md").write_text(f"# {name}\nA test project.\n")
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("print('hello')\n")

    subprocess.run(["git", "init"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(root), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(root), capture_output=True)

    return root


class TestCreateRef(unittest.TestCase):

    def setUp(self):
        self.project = _create_temp_repo("my-api")
        self.context_root = Path(tempfile.mkdtemp()) / ".seif"
        self.context_root.mkdir()

    def tearDown(self):
        shutil.rmtree(str(self.project.parent), ignore_errors=True)
        shutil.rmtree(str(self.context_root.parent), ignore_errors=True)

    def test_protocol(self):
        ref = create_ref(str(self.project), str(self.context_root))
        self.assertEqual(ref.protocol, "SEIF-REF-v1")

    def test_name(self):
        ref = create_ref(str(self.project), str(self.context_root))
        self.assertEqual(ref.name, "my-api")

    def test_branch(self):
        ref = create_ref(str(self.project), str(self.context_root))
        # Git default branch varies, but should not be empty
        self.assertTrue(len(ref.branch) > 0)

    def test_manifest_type(self):
        ref = create_ref(str(self.project), str(self.context_root))
        self.assertEqual(ref.manifest_type, "pyproject.toml")

    def test_head_commit(self):
        ref = create_ref(str(self.project), str(self.context_root))
        self.assertTrue(len(ref.last_synced_commit) > 0)
        self.assertLessEqual(len(ref.last_synced_commit), 12)

    def test_local_path_is_relative(self):
        ref = create_ref(str(self.project), str(self.context_root))
        self.assertFalse(ref.local_path.startswith("/"))
        self.assertIn("..", ref.local_path)

    def test_ai_entry_points(self):
        ref = create_ref(str(self.project), str(self.context_root))
        self.assertIn("README.md", ref.ai_entry_points)
        self.assertIn("src/", ref.ai_entry_points)

    def test_synced_at_populated(self):
        ref = create_ref(str(self.project), str(self.context_root))
        self.assertTrue(len(ref.last_synced_at) > 0)


class TestSaveLoadRef(unittest.TestCase):

    def setUp(self):
        self.project = _create_temp_repo("roundtrip")
        self.context_root = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(str(self.project.parent), ignore_errors=True)
        shutil.rmtree(str(self.context_root), ignore_errors=True)

    def test_roundtrip(self):
        ref = create_ref(str(self.project), str(self.context_root))
        ref_path = self.context_root / "ref.json"
        save_ref(ref, ref_path)

        loaded = load_ref(str(ref_path))
        self.assertEqual(loaded.protocol, ref.protocol)
        self.assertEqual(loaded.name, ref.name)
        self.assertEqual(loaded.local_path, ref.local_path)
        self.assertEqual(loaded.branch, ref.branch)
        self.assertEqual(loaded.last_synced_commit, ref.last_synced_commit)

    def test_save_creates_parent_dirs(self):
        ref = create_ref(str(self.project), str(self.context_root))
        deep_path = self.context_root / "projects" / "roundtrip" / "ref.json"
        save_ref(ref, deep_path)
        self.assertTrue(deep_path.exists())

    def test_json_valid(self):
        ref = create_ref(str(self.project), str(self.context_root))
        ref_path = self.context_root / "ref.json"
        save_ref(ref, ref_path)

        with open(ref_path) as f:
            data = json.load(f)
        self.assertEqual(data["protocol"], "SEIF-REF-v1")
        self.assertIsInstance(data["ai_entry_points"], list)


class TestUpdateRefCommit(unittest.TestCase):

    def setUp(self):
        self.project = _create_temp_repo("evolving")
        self.context_root = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(str(self.project.parent), ignore_errors=True)
        shutil.rmtree(str(self.context_root), ignore_errors=True)

    def test_commit_updates_after_new_commit(self):
        ref = create_ref(str(self.project), str(self.context_root))
        old_commit = ref.last_synced_commit

        # Make a new commit
        (self.project / "new_file.txt").write_text("change")
        subprocess.run(["git", "add", "."], cwd=str(self.project), capture_output=True)
        subprocess.run(["git", "commit", "-m", "second"],
                       cwd=str(self.project), capture_output=True)

        update_ref_commit(ref, str(self.project))
        self.assertNotEqual(ref.last_synced_commit, old_commit)


class TestRefNoGit(unittest.TestCase):

    def test_non_git_dir(self):
        """Non-git directories should produce a ref with empty git fields."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / "pyproject.toml").write_text('[project]\nname = "nogit"\n')
        ctx = Path(tempfile.mkdtemp())

        ref = create_ref(str(tmp), str(ctx))
        self.assertEqual(ref.name, tmp.name)
        self.assertEqual(ref.branch, "")
        self.assertEqual(ref.last_synced_commit, "")
        self.assertEqual(ref.remote_git, "")

        shutil.rmtree(str(tmp), ignore_errors=True)
        shutil.rmtree(str(ctx), ignore_errors=True)


class TestRefWithRemote(unittest.TestCase):

    def test_remote_url_extracted(self):
        project = _create_temp_repo("with-remote")
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
            cwd=str(project), capture_output=True,
        )
        ctx = Path(tempfile.mkdtemp())

        ref = create_ref(str(project), str(ctx))
        self.assertEqual(ref.remote_git, "https://github.com/test/repo.git")

        shutil.rmtree(str(project.parent), ignore_errors=True)
        shutil.rmtree(str(ctx), ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
