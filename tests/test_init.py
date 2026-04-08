"""Tests for seif --init: project detection, git extraction, workspace setup."""

import sys
import os
import json
import tempfile
import subprocess
import shutil
import unittest
from pathlib import Path
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
pytest.importorskip("seif.cli.cli", reason="seif CLI not installed")

from seif.cli.cli import cmd_init  # noqa: F401 — validate import chain


def _create_single_project():
    """Create a single git project."""
    root = Path(tempfile.mkdtemp())
    (root / "pyproject.toml").write_text(
        '[project]\nname = "my-tool"\nversion = "1.0"\n'
        'description = "A CLI tool"\n'
    )
    (root / "README.md").write_text("# My Tool\nA simple tool.\n")
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("print('hello')\n")
    subprocess.run(["git", "init"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(root), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init: add project"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(root), capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add main module", "--allow-empty"],
                   cwd=str(root), capture_output=True)
    return root


def _create_workspace():
    """Create a workspace with 3 subprojects."""
    root = Path(tempfile.mkdtemp(prefix="workspace_"))
    for name, mtype in [("api", "pyproject.toml"), ("web", "package.json"), ("lib", "pyproject.toml")]:
        d = root / name
        d.mkdir()
        if mtype == "pyproject.toml":
            (d / mtype).write_text(f'[project]\nname = "{name}"\nversion = "1.0"\ndescription = "The {name}"\n')
        else:
            (d / mtype).write_text(json.dumps({"name": name, "version": "1.0", "description": f"The {name}"}))
        subprocess.run(["git", "init"], cwd=str(d), capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=str(d), capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=str(d), capture_output=True)
        subprocess.run(["git", "add", "."], cwd=str(d), capture_output=True)
        subprocess.run(["git", "commit", "-m", f"init {name}"], cwd=str(d), capture_output=True)
    return root


def _create_empty_dir():
    """Create an empty directory (no git, no projects)."""
    return Path(tempfile.mkdtemp())


class TestInitSingleProject(unittest.TestCase):

    def setUp(self):
        self.root = _create_single_project()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_creates_seif_dir(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test", auto_yes=True)
        self.assertTrue((self.root / ".seif").exists())

    def test_creates_project_seif(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test", auto_yes=True)
        self.assertTrue((self.root / ".seif" / "project.seif").exists())

    def test_project_seif_has_git_data(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test", auto_yes=True)
        with open(self.root / ".seif" / "project.seif") as f:
            data = json.load(f)
        self.assertIn("init", data["summary"])
        self.assertGreater(data["compressed_words"], 0)

    def test_project_seif_has_contributor(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="alice", auto_yes=True)
        with open(self.root / ".seif" / "project.seif") as f:
            data = json.load(f)
        self.assertEqual(data["contributors"][0]["author"], "alice")


class TestInitWorkspace(unittest.TestCase):

    def setUp(self):
        self.root = _create_workspace()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_creates_workspace_json(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test", auto_yes=True)
        self.assertTrue((self.root / ".seif" / "workspace.json").exists())

    def test_creates_nucleus_seif(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test", auto_yes=True)
        self.assertTrue((self.root / ".seif" / "nucleus.seif").exists())

    def test_creates_all_project_seifs(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test", auto_yes=True)
        for name in ["api", "web", "lib"]:
            path = self.root / name / ".seif" / "project.seif"
            self.assertTrue(path.exists(), f"{name}/.seif/project.seif should exist")

    def test_registry_has_all_projects(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test", auto_yes=True)
        with open(self.root / ".seif" / "workspace.json") as f:
            reg = json.load(f)
        names = {p["name"] for p in reg["projects"]}
        self.assertEqual(names, {"api", "web", "lib"})

    def test_each_project_has_git_commits(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test", auto_yes=True)
        for name in ["api", "web", "lib"]:
            with open(self.root / name / ".seif" / "project.seif") as f:
                data = json.load(f)
            self.assertIn(f"init {name}", data["summary"])


class TestInitEmptyDir(unittest.TestCase):

    def setUp(self):
        self.root = _create_empty_dir()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_empty_dir_no_crash(self):
        from seif.cli.cli import cmd_init
        # Should not raise — cmd_init now bootstraps git + .seif even on empty dirs
        cmd_init(str(self.root), author="test", auto_yes=True)


class TestInitIdempotent(unittest.TestCase):
    """Running init twice should not break anything."""

    def setUp(self):
        self.root = _create_single_project()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_double_init(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="first", auto_yes=True)
        with open(self.root / ".seif" / "project.seif") as f:
            v1 = json.load(f)

        cmd_init(str(self.root), author="second", auto_yes=True)
        with open(self.root / ".seif" / "project.seif") as f:
            v2 = json.load(f)

        # Second init should increment version (contribute, not recreate)
        self.assertGreater(v2["version"], v1["version"])
        self.assertEqual(v2["parent_hash"], v1["integrity_hash"])


class TestOwnerModules(unittest.TestCase):
    """Owner module templates created on init."""

    def setUp(self):
        self.root = _create_single_project()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_creates_owner_feedback_rules(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="alice", auto_yes=True)
        path = self.root / ".seif" / "modules" / "owner-feedback-rules.seif"
        self.assertTrue(path.exists())
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data["schema"], "SEIF-MODULE-v2")
        self.assertEqual(data["classification"], "INTERNAL")
        self.assertEqual(data["category"], "feedback")
        self.assertEqual(data["author"], "alice")
        self.assertIsInstance(data["rules"], list)
        self.assertIn("integrity_hash", data)

    def test_creates_owner_decisions(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="alice", auto_yes=True)
        path = self.root / ".seif" / "modules" / "owner-decisions.seif"
        self.assertTrue(path.exists())
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data["category"], "decisions")
        self.assertIsInstance(data["decisions"], list)

    def test_creates_owner_active_projects(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="alice", auto_yes=True)
        path = self.root / ".seif" / "modules" / "owner-active-projects.seif"
        self.assertTrue(path.exists())
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data["category"], "context")
        self.assertIsInstance(data["projects"], list)

    def test_creates_owner_session_history(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="alice", auto_yes=True)
        path = self.root / ".seif" / "modules" / "owner-session-history.seif"
        self.assertTrue(path.exists())
        with open(path) as f:
            data = json.load(f)
        self.assertIsInstance(data["sessions"], list)

    def test_creates_owner_profile(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="alice", auto_yes=True)
        path = self.root / ".seif" / "private" / "owner" / "profile.seif"
        self.assertTrue(path.exists())
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data["profile"]["name"], "alice")
        self.assertEqual(data["category"], "identity")
        self.assertIn("integrity_hash", data)

    def test_owner_modules_idempotent(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="alice", auto_yes=True)
        path = self.root / ".seif" / "modules" / "owner-feedback-rules.seif"
        with open(path) as f:
            v1 = json.load(f)

        # Second init should NOT overwrite existing modules
        cmd_init(str(self.root), author="bob", auto_yes=True)
        with open(path) as f:
            v2 = json.load(f)

        self.assertEqual(v1["integrity_hash"], v2["integrity_hash"])
        self.assertEqual(v1["author"], "alice")  # not overwritten to bob

    def test_all_five_modules_created(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test", auto_yes=True)
        expected = [
            self.root / ".seif" / "modules" / "owner-feedback-rules.seif",
            self.root / ".seif" / "modules" / "owner-decisions.seif",
            self.root / ".seif" / "modules" / "owner-active-projects.seif",
            self.root / ".seif" / "modules" / "owner-session-history.seif",
            self.root / ".seif" / "private" / "owner" / "profile.seif",
        ]
        for p in expected:
            self.assertTrue(p.exists(), f"Missing: {p.name}")


class TestOwnerModulesUnit(unittest.TestCase):
    """Unit tests for create_owner_modules (no git needed)."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(str(self.tmpdir), ignore_errors=True)

    def test_creates_from_scratch(self):
        from seif.context.workspace import create_owner_modules
        count = create_owner_modules(self.tmpdir, owner_name="test-user")
        self.assertEqual(count, 5)

    def test_skips_existing(self):
        from seif.context.workspace import create_owner_modules
        create_owner_modules(self.tmpdir, owner_name="first")
        count = create_owner_modules(self.tmpdir, owner_name="second")
        self.assertEqual(count, 0)

    def test_integrity_hash_present(self):
        from seif.context.workspace import create_owner_modules
        create_owner_modules(self.tmpdir, owner_name="x")
        with open(self.tmpdir / "modules" / "owner-feedback-rules.seif") as f:
            data = json.load(f)
        self.assertEqual(len(data["integrity_hash"]), 24)

    def test_default_owner_name(self):
        from seif.context.workspace import create_owner_modules
        create_owner_modules(self.tmpdir)
        with open(self.tmpdir / "modules" / "owner-feedback-rules.seif") as f:
            data = json.load(f)
        self.assertEqual(data["author"], "workspace-owner")


if __name__ == "__main__":
    unittest.main()
