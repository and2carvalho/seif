"""Tests for Git Hooks — auto-sync .seif on git events."""

import sys
import os
import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from seif.context.git_hooks import install_hooks, uninstall_hooks, check_hooks, SEIF_MARKER


def _create_git_repo():
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init"], cwd=str(tmp), capture_output=True)
    return tmp


class TestInstallHooks(unittest.TestCase):

    def setUp(self):
        self.repo = _create_git_repo()

    def tearDown(self):
        shutil.rmtree(str(self.repo), ignore_errors=True)

    def test_installs_three_hooks(self):
        result = install_hooks(str(self.repo))
        self.assertEqual(len(result), 3)
        for r in result:
            self.assertIn("created", r)

    def test_hooks_are_executable(self):
        install_hooks(str(self.repo))
        for hook in ["post-commit", "post-merge", "post-checkout"]:
            path = self.repo / ".git" / "hooks" / hook
            self.assertTrue(os.access(str(path), os.X_OK))

    def test_hooks_contain_seif_marker(self):
        install_hooks(str(self.repo))
        for hook in ["post-commit", "post-merge", "post-checkout"]:
            content = (self.repo / ".git" / "hooks" / hook).read_text()
            self.assertIn(SEIF_MARKER, content)
            self.assertIn("seif --sync", content)

    def test_idempotent(self):
        install_hooks(str(self.repo))
        result2 = install_hooks(str(self.repo))
        for r in result2:
            self.assertIn("already installed", r)

    def test_appends_to_existing_hook(self):
        hook_path = self.repo / ".git" / "hooks" / "post-commit"
        hook_path.write_text("#!/bin/sh\necho 'existing hook'\n")
        hook_path.chmod(0o755)

        install_hooks(str(self.repo))
        content = hook_path.read_text()
        self.assertIn("existing hook", content)
        self.assertIn(SEIF_MARKER, content)

    def test_no_git_dir(self):
        tmp = Path(tempfile.mkdtemp())
        result = install_hooks(str(tmp))
        self.assertEqual(result, [])
        shutil.rmtree(str(tmp))


class TestUninstallHooks(unittest.TestCase):

    def setUp(self):
        self.repo = _create_git_repo()

    def tearDown(self):
        shutil.rmtree(str(self.repo), ignore_errors=True)

    def test_uninstall_removes_seif(self):
        install_hooks(str(self.repo))
        cleaned = uninstall_hooks(str(self.repo))
        self.assertGreater(len(cleaned), 0)

        for hook in ["post-commit", "post-merge", "post-checkout"]:
            path = self.repo / ".git" / "hooks" / hook
            if path.exists():
                self.assertNotIn(SEIF_MARKER, path.read_text())

    def test_preserves_existing_content(self):
        hook_path = self.repo / ".git" / "hooks" / "post-commit"
        hook_path.write_text("#!/bin/sh\necho 'keep this'\n")
        hook_path.chmod(0o755)

        install_hooks(str(self.repo))
        uninstall_hooks(str(self.repo))

        self.assertTrue(hook_path.exists())
        content = hook_path.read_text()
        self.assertIn("keep this", content)
        self.assertNotIn(SEIF_MARKER, content)


class TestCheckHooks(unittest.TestCase):

    def setUp(self):
        self.repo = _create_git_repo()

    def tearDown(self):
        shutil.rmtree(str(self.repo), ignore_errors=True)

    def test_not_installed(self):
        status = check_hooks(str(self.repo))
        for v in status.values():
            self.assertEqual(v, "not installed")

    def test_installed(self):
        install_hooks(str(self.repo))
        status = check_hooks(str(self.repo))
        for v in status.values():
            self.assertEqual(v, "installed")


if __name__ == "__main__":
    unittest.main()
