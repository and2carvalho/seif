"""Tests for Git Context Extractor — auto-generate .seif from git repos."""

import sys
import os
import tempfile
import subprocess
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from seif.context.git_context import (
    extract_git_context, context_to_summary, sync_project, GitContext,
    _extract_manifest, _extract_readme, _extract_structure,
)


def _create_temp_repo() -> Path:
    """Create a temporary git repo with some commits."""
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init"], cwd=str(tmp), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp), capture_output=True)

    # Create README
    (tmp / "README.md").write_text("# Test Project\nA test project for SEIF git context.\n")
    subprocess.run(["git", "add", "README.md"], cwd=str(tmp), capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit: add README"], cwd=str(tmp), capture_output=True)

    # Create manifest
    (tmp / "pyproject.toml").write_text(
        '[project]\nname = "test-proj"\nversion = "1.0.0"\n'
        'description = "A test project"\n'
    )
    subprocess.run(["git", "add", "pyproject.toml"], cwd=str(tmp), capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add pyproject.toml"], cwd=str(tmp), capture_output=True)

    # Create source file
    (tmp / "src").mkdir()
    (tmp / "src" / "main.py").write_text("print('hello')\n")
    subprocess.run(["git", "add", "src/main.py"], cwd=str(tmp), capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add main module with 432 Hz support"], cwd=str(tmp), capture_output=True)

    return tmp


def _cleanup_repo(tmp: Path):
    """Remove temporary repo."""
    import shutil
    shutil.rmtree(str(tmp), ignore_errors=True)


class TestExtractGitContext(unittest.TestCase):

    def setUp(self):
        self.repo = _create_temp_repo()

    def tearDown(self):
        _cleanup_repo(self.repo)

    def test_basic_extraction(self):
        ctx = extract_git_context(str(self.repo))
        self.assertEqual(ctx.repo_name, self.repo.name)
        self.assertEqual(ctx.total_commits, 3)
        self.assertIn("Test User", ctx.contributors)

    def test_recent_commits(self):
        ctx = extract_git_context(str(self.repo))
        self.assertEqual(len(ctx.recent_commits), 3)
        self.assertIn("main module", ctx.recent_commits[0]["message"])

    def test_manifest_detected(self):
        ctx = extract_git_context(str(self.repo))
        self.assertEqual(ctx.manifest_type, "pyproject.toml")
        self.assertIn("test-proj", ctx.manifest_summary)

    def test_readme_extracted(self):
        ctx = extract_git_context(str(self.repo))
        self.assertIn("Test Project", ctx.readme_summary)

    def test_structure_extracted(self):
        ctx = extract_git_context(str(self.repo))
        self.assertTrue(len(ctx.structure) > 0)

    def test_hot_files(self):
        ctx = extract_git_context(str(self.repo))
        hot_paths = [f for f, _ in ctx.hot_files]
        self.assertIn("README.md", hot_paths)

    def test_branch_detected(self):
        ctx = extract_git_context(str(self.repo))
        self.assertIn(ctx.branch, ["main", "master"])


class TestContextToSummary(unittest.TestCase):

    def setUp(self):
        self.repo = _create_temp_repo()

    def tearDown(self):
        _cleanup_repo(self.repo)

    def test_summary_contains_repo_name(self):
        ctx = extract_git_context(str(self.repo))
        summary = context_to_summary(ctx)
        self.assertIn(ctx.repo_name, summary)

    def test_summary_contains_commits(self):
        ctx = extract_git_context(str(self.repo))
        summary = context_to_summary(ctx)
        self.assertIn("Initial commit", summary)
        self.assertIn("pyproject.toml", summary)

    def test_summary_contains_manifest(self):
        ctx = extract_git_context(str(self.repo))
        summary = context_to_summary(ctx)
        self.assertIn("test-proj", summary)

    def test_summary_word_count(self):
        ctx = extract_git_context(str(self.repo))
        summary = context_to_summary(ctx)
        words = len(summary.split())
        self.assertGreater(words, 20)
        self.assertLess(words, 2000)


class TestSyncProject(unittest.TestCase):

    def setUp(self):
        self.repo = _create_temp_repo()

    def tearDown(self):
        _cleanup_repo(self.repo)

    def test_sync_creates_seif_dir(self):
        module, path = sync_project(str(self.repo), author="test")
        self.assertTrue((self.repo / ".seif").exists())
        self.assertTrue(path.exists())

    def test_sync_creates_project_seif(self):
        module, path = sync_project(str(self.repo), author="test")
        self.assertEqual(path.name, "project.seif")
        self.assertGreater(module.compressed_words, 0)

    def test_sync_contributor_tracked(self):
        module, _ = sync_project(str(self.repo), author="alice", via="claude")
        self.assertEqual(len(module.contributors), 1)
        self.assertEqual(module.contributors[0]["author"], "alice")
        self.assertEqual(module.contributors[0]["via"], "claude")

    def test_resync_contributes(self):
        m1, _ = sync_project(str(self.repo), author="alice")
        self.assertEqual(m1.version, 1)

        m2, _ = sync_project(str(self.repo), author="bob")
        self.assertEqual(m2.version, 2)
        self.assertIsNotNone(m2.parent_hash)
        self.assertEqual(m2.parent_hash, m1.integrity_hash)

    def test_resync_hash_chain(self):
        m1, _ = sync_project(str(self.repo), author="a")
        m2, _ = sync_project(str(self.repo), author="b")
        m3, _ = sync_project(str(self.repo), author="c")
        self.assertEqual(m2.parent_hash, m1.integrity_hash)
        self.assertEqual(m3.parent_hash, m2.integrity_hash)
        self.assertEqual(m3.version, 3)

    def test_sync_integrity_hash_present(self):
        module, _ = sync_project(str(self.repo), author="test")
        self.assertTrue(len(module.integrity_hash) > 0)


class TestManifestExtraction(unittest.TestCase):

    def test_pyproject_toml(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "pyproject.toml").write_text('[project]\nname = "my-pkg"\nversion = "1.0"\n')
        mtype, summary = _extract_manifest(tmp)
        self.assertEqual(mtype, "pyproject.toml")
        self.assertIn("my-pkg", summary)
        import shutil
        shutil.rmtree(str(tmp))

    def test_package_json(self):
        tmp = Path(tempfile.mkdtemp())
        import json
        (tmp / "package.json").write_text(json.dumps({
            "name": "my-app", "version": "2.0.0",
            "description": "A JS app",
            "dependencies": {"react": "^18", "next": "^14"}
        }))
        mtype, summary = _extract_manifest(tmp)
        self.assertEqual(mtype, "package.json")
        self.assertIn("my-app", summary)
        self.assertIn("react", summary)
        import shutil
        shutil.rmtree(str(tmp))

    def test_no_manifest(self):
        tmp = Path(tempfile.mkdtemp())
        mtype, summary = _extract_manifest(tmp)
        self.assertIsNone(mtype)
        import shutil
        shutil.rmtree(str(tmp))


if __name__ == "__main__":
    unittest.main()
