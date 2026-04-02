"""
Project Reference — SEIF-REF-v1 protocol.

A ref.json file is a pointer from a SEIF context repository (SCR) to a source
code repository. It contains enough metadata for any AI to locate and understand
the project without cloning the code first.

Usage:
  from seif.context.ref import create_ref, save_ref, load_ref
  ref = create_ref("/path/to/project", "/path/to/context-repo")
  save_ref(ref, Path("context-repo/projects/myproject/ref.json"))
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from seif.context.git_context import _run_git


# Files that indicate useful AI entry points
AI_ENTRY_CANDIDATES = [
    "CLAUDE.md", "GEMINI.md", "AGENTS.md",
    "README.md", "readme.md",
    "RESONANCE.json",
    "src/", "lib/", "app/", "pkg/", "cmd/",
    "docs/", "paper/",
]


@dataclass
class ProjectRef:
    """Pointer from a context repo to a source code repository."""
    protocol: str = "SEIF-REF-v1"
    name: str = ""
    local_path: str = ""              # relative path from context repo to source
    remote_git: str = ""              # git remote URL (if available)
    branch: str = ""
    manifest_type: Optional[str] = None
    last_synced_commit: str = ""      # HEAD SHA at sync time
    last_synced_at: str = ""
    ai_entry_points: list[str] = field(default_factory=list)


def create_ref(project_dir: str, context_root: str) -> ProjectRef:
    """Build a ProjectRef by inspecting a project directory.

    Args:
        project_dir: Absolute path to the source project.
        context_root: Absolute path to the context repository root.

    Returns:
        ProjectRef with extracted metadata.
    """
    project = Path(project_dir).resolve()
    ctx_root = Path(context_root).resolve()

    # Relative path from context repo to project
    local_path = os.path.relpath(str(project), str(ctx_root))

    # Git metadata
    branch = _run_git(["branch", "--show-current"], str(project)) or ""
    head_sha = _run_git(["rev-parse", "HEAD"], str(project)) or ""
    remote_url = _run_git(["remote", "get-url", "origin"], str(project)) or ""

    # Manifest type
    from seif.context.git_context import _extract_manifest
    manifest_type, _ = _extract_manifest(project)

    # Detect AI entry points
    entry_points = []
    for candidate in AI_ENTRY_CANDIDATES:
        candidate_path = project / candidate
        if candidate_path.exists():
            entry_points.append(candidate)

    return ProjectRef(
        name=project.name,
        local_path=local_path,
        remote_git=remote_url,
        branch=branch,
        manifest_type=manifest_type,
        last_synced_commit=head_sha[:12] if head_sha else "",
        last_synced_at=datetime.now(timezone.utc).isoformat(),
        ai_entry_points=entry_points,
    )


def save_ref(ref: ProjectRef, target_path: Path) -> Path:
    """Write a ProjectRef as ref.json.

    Args:
        ref: The ProjectRef to save.
        target_path: Full path including filename (e.g., projects/api/ref.json).

    Returns:
        Path where the file was saved.
    """
    from seif.context.seif_io import atomic_write_json
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(target_path, asdict(ref))
    return target_path


def load_ref(ref_path: str) -> ProjectRef:
    """Load a ProjectRef from a ref.json file.

    Args:
        ref_path: Path to the ref.json file.

    Returns:
        ProjectRef with loaded data.
    """
    with open(ref_path, encoding="utf-8") as f:
        data = json.load(f)
    return ProjectRef(**{k: v for k, v in data.items()
                         if k in ProjectRef.__dataclass_fields__})


def update_ref_commit(ref: ProjectRef, project_dir: str) -> ProjectRef:
    """Update the synced commit SHA from current HEAD.

    Args:
        ref: Existing ProjectRef to update.
        project_dir: Path to the source project.

    Returns:
        Updated ProjectRef (same object, mutated).
    """
    head_sha = _run_git(["rev-parse", "HEAD"], str(project_dir)) or ""
    ref.last_synced_commit = head_sha[:12] if head_sha else ""
    ref.last_synced_at = datetime.now(timezone.utc).isoformat()
    return ref
