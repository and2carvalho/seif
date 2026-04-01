"""Tests for Workspace Manager — multi-project SEIF nucleus."""

import sys
import os
import json
import tempfile
import subprocess
import shutil
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from seif.context.workspace import (
    discover_projects, detect_dependencies, sync_workspace,
    load_registry, describe_workspace, ProjectEntry,
)


def _create_workspace():
    """Create a temporary workspace with multiple project directories."""
    root = Path(tempfile.mkdtemp())

    # Project 1: Python API
    api = root / "api"
    api.mkdir()
    (api / "pyproject.toml").write_text(
        '[project]\nname = "acme-api"\nversion = "1.0"\n'
        'description = "REST API for ACME platform"\n'
        'dependencies = ["fastapi", "acme-shared"]\n'
    )
    subprocess.run(["git", "init"], cwd=str(api), capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=str(api), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(api), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(api), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init api"], cwd=str(api), capture_output=True)

    # Project 2: React Web
    web = root / "web-app"
    web.mkdir()
    (web / "package.json").write_text(json.dumps({
        "name": "acme-web", "version": "2.0.0",
        "description": "ACME web dashboard",
        "dependencies": {"react": "^18", "acme-api": "workspace:*"}
    }))
    subprocess.run(["git", "init"], cwd=str(web), capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=str(web), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(web), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(web), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init web"], cwd=str(web), capture_output=True)

    # Project 3: Shared lib (no git)
    shared = root / "shared"
    shared.mkdir()
    (shared / "pyproject.toml").write_text(
        '[project]\nname = "acme-shared"\nversion = "0.1"\n'
        'description = "Shared utilities for ACME"\n'
    )

    # Project 4: Infrastructure (Terraform)
    infra = root / "infra"
    infra.mkdir()
    (infra / "main.tf").write_text(
        'provider "aws" {\n  region = "us-east-1"\n}\n'
    )

    # Project 5: Docker service (no language manifest, just Dockerfile)
    worker = root / "worker"
    worker.mkdir()
    (worker / "Dockerfile").write_text("FROM python:3.13\nCOPY . /app\n")

    # Non-project directory (should be ignored)
    (root / "docs").mkdir()
    (root / "docs" / "README.md").write_text("# Docs\n")

    return root


class TestDiscoverProjects(unittest.TestCase):

    def setUp(self):
        self.root = _create_workspace()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_discovers_all_projects(self):
        projects = discover_projects(str(self.root))
        names = {p.name for p in projects}
        self.assertIn("api", names)
        self.assertIn("web-app", names)
        self.assertIn("shared", names)
        self.assertIn("infra", names)
        self.assertIn("worker", names)

    def test_ignores_non_projects(self):
        projects = discover_projects(str(self.root))
        names = {p.name for p in projects}
        self.assertNotIn("docs", names)

    def test_detects_manifest_type(self):
        projects = discover_projects(str(self.root))
        by_name = {p.name: p for p in projects}
        self.assertEqual(by_name["api"].manifest_type, "pyproject.toml")
        self.assertEqual(by_name["web-app"].manifest_type, "package.json")

    def test_extracts_description(self):
        projects = discover_projects(str(self.root))
        by_name = {p.name: p for p in projects}
        self.assertIn("REST API", by_name["api"].description)


class TestDetectDependencies(unittest.TestCase):

    def setUp(self):
        self.root = _create_workspace()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_detects_cross_project_deps(self):
        projects = discover_projects(str(self.root))
        projects = detect_dependencies(projects, str(self.root))
        by_name = {p.name: p for p in projects}
        # web-app's package.json mentions "acme-api"
        # api's pyproject.toml mentions "acme-shared"
        # These are name-based heuristics, so they match substring
        self.assertTrue(
            len(by_name["web-app"].dependencies) > 0 or
            len(by_name["api"].dependencies) > 0,
            "At least one cross-project dependency should be detected"
        )


class TestSyncWorkspace(unittest.TestCase):

    def setUp(self):
        self.root = _create_workspace()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_creates_workspace_registry(self):
        registry = sync_workspace(str(self.root))
        self.assertGreater(len(registry.projects), 0)
        reg_path = self.root / ".seif" / "workspace.json"
        self.assertTrue(reg_path.exists())

    def test_creates_nucleus_seif(self):
        sync_workspace(str(self.root))
        nucleus = self.root / ".seif" / "nucleus.seif"
        self.assertTrue(nucleus.exists())

    def test_creates_project_seif_files(self):
        sync_workspace(str(self.root))
        for name in ["api", "web-app", "shared", "infra", "worker"]:
            seif_path = self.root / name / ".seif" / "project.seif"
            self.assertTrue(seif_path.exists(), f"{name}/.seif/project.seif should exist")

    def test_registry_loadable(self):
        sync_workspace(str(self.root))
        loaded = load_registry(str(self.root))
        self.assertIsNotNone(loaded)
        self.assertGreater(len(loaded.projects), 0)

    def test_resync_updates(self):
        r1 = sync_workspace(str(self.root), author="first")
        r2 = sync_workspace(str(self.root), author="second")
        self.assertEqual(len(r1.projects), len(r2.projects))
        # Nucleus should have been contributed to (version > 1)
        nucleus = self.root / ".seif" / "nucleus.seif"
        with open(nucleus) as f:
            data = json.load(f)
        self.assertGreater(data["version"], 1)

    def test_describe_workspace(self):
        registry = sync_workspace(str(self.root))
        desc = describe_workspace(registry)
        self.assertIn("api", desc)
        self.assertIn("web-app", desc)
        self.assertIn("shared", desc)


if __name__ == "__main__":
    unittest.main()
