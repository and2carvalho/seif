"""
Git Context Extractor — Auto-generate .seif modules from git repository metadata.

Extracts structured context from any git repo without requiring AI:
  - Recent commits (who, when, what, why)
  - Branch info and status
  - Project manifest (pyproject.toml, package.json, Cargo.toml, etc.)
  - README summary (first section)
  - Directory structure overview
  - File change frequency (hot files)

Usage:
  from seif.context.git_context import extract_git_context, sync_project
  context = extract_git_context("/path/to/repo")
  module, path = sync_project("/path/to/repo", author="alice")
"""

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Project manifest files (in priority order)
MANIFEST_FILES = [
    "pyproject.toml", "setup.py", "setup.cfg",          # Python
    "package.json",                                       # Node.js
    "Cargo.toml",                                         # Rust
    "go.mod",                                             # Go
    "pom.xml", "build.gradle", "build.gradle.kts",       # Java/Kotlin
    "Gemfile",                                            # Ruby
    "composer.json",                                      # PHP
    "CMakeLists.txt",                                     # C/C++
    "mix.exs",                                            # Elixir
    "pubspec.yaml",                                       # Flutter/Dart
    "Package.swift",                                      # Swift
    "docker-compose.yml", "docker-compose.yaml",          # Docker Compose
    "Dockerfile",                                         # Docker
    "main.tf",                                            # Terraform
    "Chart.yaml",                                         # Helm
    "kustomization.yaml",                                 # Kustomize
    "nx.json", "turbo.json",                              # Monorepo
    "Makefile",                                           # Generic
]

# Files to ignore in structure listing
IGNORE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".egg-info", ".eggs", "target", "vendor",
}


@dataclass
class GitContext:
    """Structured context extracted from a git repository."""
    repo_path: str
    repo_name: str
    branch: str
    total_commits: int
    contributors: list[str]
    recent_commits: list[dict]      # [{hash, author, date, message}]
    hot_files: list[tuple[str, int]]  # [(filepath, change_count)]
    manifest_type: Optional[str] = None
    manifest_summary: str = ""
    readme_summary: str = ""
    structure: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    uncommitted_changes: int = 0
    extracted_at: str = ""


def _run_git(args: list[str], cwd: str, timeout: int = 10) -> str:
    """Run a git command and return stdout."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True,
            cwd=cwd, timeout=timeout,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _extract_manifest(repo: Path) -> tuple[Optional[str], str]:
    """Find and summarize the project manifest."""
    for mf in MANIFEST_FILES:
        mpath = repo / mf
        if mpath.exists():
            try:
                content = mpath.read_text(encoding="utf-8", errors="ignore")
                # Extract key fields based on type
                if mf == "pyproject.toml":
                    lines = []
                    for line in content.split("\n"):
                        line_s = line.strip()
                        if any(line_s.startswith(k) for k in [
                            "name", "version", "description", "dependencies",
                            "requires-python", "python"
                        ]):
                            lines.append(line_s)
                    return mf, "\n".join(lines[:15])
                elif mf == "package.json":
                    try:
                        pkg = json.loads(content)
                        parts = []
                        for k in ["name", "version", "description"]:
                            if k in pkg:
                                parts.append(f"{k}: {pkg[k]}")
                        if "dependencies" in pkg:
                            deps = list(pkg["dependencies"].keys())[:10]
                            parts.append(f"dependencies: {', '.join(deps)}")
                        return mf, "\n".join(parts)
                    except json.JSONDecodeError:
                        return mf, content[:500]
                elif mf in ("Cargo.toml", "go.mod"):
                    return mf, content[:500]
                else:
                    return mf, content[:300]
            except Exception:
                continue
    return None, ""


def _extract_readme(repo: Path) -> str:
    """Extract first meaningful section of README."""
    for name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
        rpath = repo / name
        if rpath.exists():
            try:
                content = rpath.read_text(encoding="utf-8", errors="ignore")
                # Take first ~500 words (usually title + description + quick start)
                words = content.split()
                return " ".join(words[:500])
            except Exception:
                continue
    return ""


def _extract_structure(repo: Path, max_depth: int = 3, max_items: int = 50) -> list[str]:
    """Extract directory structure overview (top N items)."""
    items = []

    def _walk(path: Path, depth: int, prefix: str):
        if depth > max_depth or len(items) >= max_items:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return
        for entry in entries:
            if entry.name in IGNORE_DIRS or entry.name.startswith("."):
                continue
            rel = str(entry.relative_to(repo))
            if entry.is_dir():
                items.append(f"{prefix}{entry.name}/")
                _walk(entry, depth + 1, prefix + "  ")
            elif entry.is_file() and len(items) < max_items:
                items.append(f"{prefix}{entry.name}")

    _walk(repo, 0, "")
    return items


def extract_git_context(repo_path: str, max_commits: int = 30,
                        max_hot_files: int = 15) -> GitContext:
    """Extract structured context from a git repository.

    Args:
        repo_path: Path to the git repository root.
        max_commits: Number of recent commits to include.
        max_hot_files: Number of most-changed files to track.

    Returns:
        GitContext with all extracted metadata.
    """
    repo = Path(repo_path).resolve()

    # Basic info
    repo_name = repo.name
    branch = _run_git(["branch", "--show-current"], str(repo)) or "unknown"

    # Commit count
    total_str = _run_git(["rev-list", "--count", "HEAD"], str(repo))
    total_commits = int(total_str) if total_str.isdigit() else 0

    # Contributors
    authors_raw = _run_git(
        ["log", "--format=%aN", f"--max-count={200}"],
        str(repo)
    )
    contributors = sorted(set(authors_raw.split("\n"))) if authors_raw else []

    # Recent commits
    log_raw = _run_git(
        ["log", f"--max-count={max_commits}",
         "--format=%H|%aN|%aI|%s"],
        str(repo)
    )
    recent_commits = []
    if log_raw:
        for line in log_raw.split("\n"):
            parts = line.split("|", 3)
            if len(parts) == 4:
                recent_commits.append({
                    "hash": parts[0][:8],
                    "author": parts[1],
                    "date": parts[2][:10],
                    "message": parts[3][:200],
                })

    # Hot files (most frequently changed)
    hotfiles_raw = _run_git(
        ["log", "--max-count=100", "--name-only", "--format="],
        str(repo)
    )
    file_counts: dict[str, int] = {}
    if hotfiles_raw:
        for line in hotfiles_raw.split("\n"):
            line = line.strip()
            if line and not line.startswith("."):
                file_counts[line] = file_counts.get(line, 0) + 1
    hot_files = sorted(file_counts.items(), key=lambda x: -x[1])[:max_hot_files]

    # Tags
    tags_raw = _run_git(["tag", "--sort=-creatordate"], str(repo))
    tags = tags_raw.split("\n")[:5] if tags_raw else []

    # Uncommitted changes
    status_raw = _run_git(["status", "--porcelain"], str(repo))
    uncommitted = len([l for l in status_raw.split("\n") if l.strip()]) if status_raw else 0

    # Manifest
    manifest_type, manifest_summary = _extract_manifest(repo)

    # README
    readme_summary = _extract_readme(repo)

    # Structure
    structure = _extract_structure(repo)

    return GitContext(
        repo_path=str(repo),
        repo_name=repo_name,
        branch=branch,
        total_commits=total_commits,
        contributors=contributors,
        recent_commits=recent_commits,
        hot_files=hot_files,
        manifest_type=manifest_type,
        manifest_summary=manifest_summary,
        readme_summary=readme_summary,
        structure=structure,
        tags=tags,
        uncommitted_changes=uncommitted,
        extracted_at=datetime.now(timezone.utc).isoformat(),
    )


def context_to_summary(ctx: GitContext) -> str:
    """Convert GitContext into a compressed markdown summary for .seif module."""
    parts = []

    # Header
    parts.append(f"## {ctx.repo_name} (git context)")
    parts.append(f"Branch: {ctx.branch} | Commits: {ctx.total_commits} | "
                 f"Contributors: {len(ctx.contributors)}")
    if ctx.tags:
        parts.append(f"Tags: {', '.join(ctx.tags[:3])}")

    # Manifest
    if ctx.manifest_type:
        parts.append(f"\n### Project ({ctx.manifest_type})")
        parts.append(ctx.manifest_summary[:300])

    # Recent activity
    parts.append("\n### Recent commits")
    for c in ctx.recent_commits[:15]:
        parts.append(f"- [{c['date']}] {c['author']}: {c['message']}")

    # Hot files
    if ctx.hot_files:
        parts.append("\n### Most changed files")
        for filepath, count in ctx.hot_files[:10]:
            parts.append(f"- {filepath} ({count}x)")

    # Structure
    if ctx.structure:
        parts.append("\n### Structure")
        parts.append("```")
        for item in ctx.structure[:30]:
            parts.append(item)
        parts.append("```")

    # README excerpt
    if ctx.readme_summary:
        parts.append("\n### README (excerpt)")
        # Take first 200 words of README
        words = ctx.readme_summary.split()[:200]
        parts.append(" ".join(words))

    if ctx.uncommitted_changes:
        parts.append(f"\n**{ctx.uncommitted_changes} uncommitted changes**")

    return "\n".join(parts)


def sync_project(repo_path: str = ".", author: str = "seif-sync",
                 via: str = "git", target_path: str = None) -> tuple:
    """Auto-generate or update a .seif module from git context.

    This is the main entry point for `seif --sync`. It:
    1. Extracts git context (commits, manifest, README, structure)
    2. Compresses into a summary
    3. Creates or contributes to a project.seif module

    Args:
        repo_path: Path to git repository (default: current directory).
        author: Author name for the contribution.
        via: Tool identifier.
        target_path: Optional external path for project.seif (SCR mode).
                     When set, .seif is NOT created inside the repo.

    Returns:
        Tuple of (SeifModule, Path) where the module was saved.
    """
    from seif.context.context_manager import (
        create_module, save_module, contribute_to_module, load_module,
    )

    repo = Path(repo_path).resolve()
    ctx = extract_git_context(str(repo))
    summary = context_to_summary(ctx)

    # Estimate original words from git content
    original_words = ctx.total_commits * 50  # rough estimate: 50 words per commit context

    # Determine where to save
    if target_path:
        project_seif = Path(target_path)
        project_seif.parent.mkdir(parents=True, exist_ok=True)
    else:
        seif_dir = repo / ".seif"
        seif_dir.mkdir(exist_ok=True)
        project_seif = seif_dir / "project.seif"

    if project_seif.exists():
        # Contribute to existing module
        module, path = contribute_to_module(
            str(project_seif), summary,
            author=author, via=via,
        )
    else:
        # Create new module
        module = create_module(
            source_name=f"{ctx.repo_name} (git)",
            original_words=max(original_words, len(summary.split()) * 2),
            summary=summary,
            author=author,
            via=via,
        )
        path = save_module(module, target_path=project_seif)

    return module, path
