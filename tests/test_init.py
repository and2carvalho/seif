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
        cmd_init(str(self.root), author="test")
        self.assertTrue((self.root / ".seif").exists())

    def test_creates_project_seif(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test")
        self.assertTrue((self.root / ".seif" / "project.seif").exists())

    def test_project_seif_has_git_data(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test")
        with open(self.root / ".seif" / "project.seif") as f:
            data = json.load(f)
        self.assertIn("init", data["summary"])
        self.assertGreater(data["compressed_words"], 0)

    def test_project_seif_has_contributor(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="alice")
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
        cmd_init(str(self.root), author="test")
        self.assertTrue((self.root / ".seif" / "workspace.json").exists())

    def test_creates_nucleus_seif(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test")
        self.assertTrue((self.root / ".seif" / "nucleus.seif").exists())

    def test_creates_all_project_seifs(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test")
        for name in ["api", "web", "lib"]:
            path = self.root / name / ".seif" / "project.seif"
            self.assertTrue(path.exists(), f"{name}/.seif/project.seif should exist")

    def test_registry_has_all_projects(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test")
        with open(self.root / ".seif" / "workspace.json") as f:
            reg = json.load(f)
        names = {p["name"] for p in reg["projects"]}
        self.assertEqual(names, {"api", "web", "lib"})

    def test_each_project_has_git_commits(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="test")
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
        cmd_init(str(self.root), author="test")


class TestInitIdempotent(unittest.TestCase):
    """Running init twice should not break anything."""

    def setUp(self):
        self.root = _create_single_project()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_double_init(self):
        from seif.cli.cli import cmd_init
        cmd_init(str(self.root), author="first")
        with open(self.root / ".seif" / "project.seif") as f:
            v1 = json.load(f)

        cmd_init(str(self.root), author="second")
        with open(self.root / ".seif" / "project.seif") as f:
            v2 = json.load(f)

        # Second init should increment version (contribute, not recreate)
        self.assertGreater(v2["version"], v1["version"])
        self.assertEqual(v2["parent_hash"], v1["integrity_hash"])


if __name__ == "__main__":
    unittest.main()
