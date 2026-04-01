"""Tests for SEIF Context Repository (SCR) — external context storage."""

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
    discover_projects, sync_workspace, load_registry, describe_workspace,
    init_context_repo, create_scr_readme, create_scr_manifest,
)
from seif.context.ref import load_ref


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
    (api / "README.md").write_text("# ACME API\nBackend service.\n")
    (api / "src").mkdir()
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

    # Project 5: Docker service
    worker = root / "worker"
    worker.mkdir()
    (worker / "Dockerfile").write_text("FROM python:3.13\nCOPY . /app\n")

    # Non-project directory (should be ignored)
    (root / "docs").mkdir()
    (root / "docs" / "README.md").write_text("# Docs\n")

    return root


class TestInitContextRepo(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_creates_directory(self):
        ctx = init_context_repo(str(self.tmp / "ctx"))
        self.assertTrue(ctx.exists())

    def test_git_init(self):
        ctx = init_context_repo(str(self.tmp / "ctx"))
        self.assertTrue((ctx / ".git").exists())

    def test_gitignore_created(self):
        ctx = init_context_repo(str(self.tmp / "ctx"))
        self.assertTrue((ctx / ".gitignore").exists())

    def test_idempotent(self):
        ctx1 = init_context_repo(str(self.tmp / "ctx"))
        ctx2 = init_context_repo(str(self.tmp / "ctx"))
        self.assertEqual(ctx1, ctx2)


class TestSyncWorkspaceSCR(unittest.TestCase):
    """Test sync_workspace with context_repo_path (SCR mode)."""

    def setUp(self):
        self.root = _create_workspace()
        self.ctx_repo = self.root / ".seif"

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_creates_context_repo_with_git(self):
        sync_workspace(str(self.root), context_repo_path=str(self.ctx_repo))
        self.assertTrue((self.ctx_repo / ".git").exists())

    def test_creates_ref_json_for_each_project(self):
        sync_workspace(str(self.root), context_repo_path=str(self.ctx_repo))
        for name in ["api", "web-app", "shared"]:  # core projects
            ref_path = self.ctx_repo / "projects" / name / "ref.json"
            self.assertTrue(ref_path.exists(), f"ref.json missing for {name}")

    def test_ref_json_has_correct_protocol(self):
        sync_workspace(str(self.root), context_repo_path=str(self.ctx_repo))
        ref = load_ref(str(self.ctx_repo / "projects" / "api" / "ref.json"))
        self.assertEqual(ref.protocol, "SEIF-REF-v1")
        self.assertEqual(ref.name, "api")

    def test_ref_json_has_commit_for_git_projects(self):
        sync_workspace(str(self.root), context_repo_path=str(self.ctx_repo))
        ref = load_ref(str(self.ctx_repo / "projects" / "api" / "ref.json"))
        self.assertTrue(len(ref.last_synced_commit) > 0)

    def test_creates_project_seif_in_context_repo(self):
        sync_workspace(str(self.root), context_repo_path=str(self.ctx_repo))
        for name in ["api", "web-app", "shared"]:  # core projects
            seif_path = self.ctx_repo / "projects" / name / "project.seif"
            self.assertTrue(seif_path.exists(), f"project.seif missing for {name}")

    def test_no_seif_inside_code_repos(self):
        sync_workspace(str(self.root), context_repo_path=str(self.ctx_repo))
        for name in ["api", "web-app", "shared"]:  # core projects
            internal_seif = self.root / name / ".seif"
            self.assertFalse(internal_seif.exists(),
                             f".seif should NOT exist inside {name}/ in SCR mode")

    def test_creates_nucleus_seif(self):
        sync_workspace(str(self.root), context_repo_path=str(self.ctx_repo))
        self.assertTrue((self.ctx_repo / "nucleus.seif").exists())

    def test_creates_workspace_json(self):
        sync_workspace(str(self.root), context_repo_path=str(self.ctx_repo))
        self.assertTrue((self.ctx_repo / "workspace.json").exists())

    def test_creates_manifest_json(self):
        sync_workspace(str(self.root), context_repo_path=str(self.ctx_repo))
        manifest_path = self.ctx_repo / "manifest.json"
        self.assertTrue(manifest_path.exists())
        with open(manifest_path) as f:
            data = json.load(f)
        self.assertEqual(data["protocol"], "SEIF-SCR-v1")
        self.assertEqual(len(data["projects"]), 5)

    def test_creates_readme(self):
        sync_workspace(str(self.root), context_repo_path=str(self.ctx_repo))
        readme = self.ctx_repo / "README.md"
        self.assertTrue(readme.exists())
        content = readme.read_text()
        self.assertIn("SEIF Context Repository", content)
        self.assertIn("api", content)

    def test_registry_has_context_repo_field(self):
        sync_workspace(str(self.root), context_repo_path=str(self.ctx_repo))
        registry = load_registry(str(self.root), context_repo_path=str(self.ctx_repo))
        self.assertIsNotNone(registry)
        self.assertIsNotNone(registry.context_repo)

    def test_resync_updates_versions(self):
        sync_workspace(str(self.root), author="first",
                       context_repo_path=str(self.ctx_repo))
        sync_workspace(str(self.root), author="second",
                       context_repo_path=str(self.ctx_repo))

        # Nucleus should have version > 1
        with open(self.ctx_repo / "nucleus.seif") as f:
            data = json.load(f)
        self.assertGreater(data["version"], 1)

    def test_describe_shows_scr(self):
        registry = sync_workspace(str(self.root),
                                  context_repo_path=str(self.ctx_repo))
        desc = describe_workspace(registry)
        self.assertIn("SCR", desc)


class TestBackwardCompatibility(unittest.TestCase):
    """Ensure embedded mode still works when no context_repo_path is given."""

    def setUp(self):
        self.root = _create_workspace()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_embedded_mode_creates_seif_inside_projects(self):
        sync_workspace(str(self.root))
        for name in ["api", "web-app", "shared", "infra", "worker"]:
            seif_path = self.root / name / ".seif" / "project.seif"
            self.assertTrue(seif_path.exists(),
                            f"{name}/.seif/project.seif should exist in embedded mode")

    def test_embedded_mode_creates_nucleus(self):
        sync_workspace(str(self.root))
        self.assertTrue((self.root / ".seif" / "nucleus.seif").exists())

    def test_embedded_registry_loadable(self):
        sync_workspace(str(self.root))
        registry = load_registry(str(self.root))
        self.assertIsNotNone(registry)
        self.assertIsNone(registry.context_repo)

    def test_no_manifest_json_in_embedded_mode(self):
        sync_workspace(str(self.root))
        self.assertFalse((self.root / ".seif" / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
