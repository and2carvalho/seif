"""
SEIF Context Registry — Global index of all .seif contexts on this machine.

Lives at ~/.seif/registry.json. Tracks every context the user has initialized,
enabling `seif list`, `seif status`, and future `seif push/pull/clone`.

Analogous to how git tracks repos, but for context.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from seif.data.paths import get_user_home


REGISTRY_PROTOCOL = "SEIF-REGISTRY-v1"


def get_registry_path() -> Path:
    """Return path to ~/.seif/registry.json."""
    return get_user_home() / "registry.json"


def _empty_registry() -> dict:
    """Create an empty registry structure."""
    return {
        "protocol": REGISTRY_PROTOCOL,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "contexts": [],
    }


def load_registry() -> dict:
    """Load the global registry. Creates it if it doesn't exist."""
    path = get_registry_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("protocol") == REGISTRY_PROTOCOL:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return _empty_registry()


def save_registry(registry: dict) -> Path:
    """Save the registry to ~/.seif/registry.json. Creates ~/.seif/ if needed."""
    path = get_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    # Secure permissions (owner-only read/write)
    os.chmod(path, 0o600)
    return path


def find_context_entry(registry: dict, seif_path: str) -> Optional[dict]:
    """Find a context entry by its .seif/ path."""
    resolved = str(Path(seif_path).resolve())
    for ctx in registry.get("contexts", []):
        if str(Path(ctx["path"]).resolve()) == resolved:
            return ctx
    return None


def find_context_by_name(registry: dict, name: str) -> Optional[dict]:
    """Find a context entry by name."""
    for ctx in registry.get("contexts", []):
        if ctx.get("name") == name:
            return ctx
    return None


def register_context(
    seif_path: str,
    name: Optional[str] = None,
    remote: Optional[str] = None,
    visibility: str = "private",
) -> dict:
    """Register a .seif context in the global registry.

    Args:
        seif_path: Absolute path to the .seif/ directory
        name: Human-friendly name (defaults to parent directory name)
        remote: Remote URL on seifprotocol.com (None = local-only)
        visibility: 'private', 'public', or 'local'

    Returns:
        The created/updated context entry.
    """
    registry = load_registry()
    resolved = str(Path(seif_path).resolve())

    # Derive name from parent directory if not given
    if not name:
        parent = Path(resolved).parent
        name = parent.name if parent.name != ".seif" else parent.parent.name

    # Check if already registered
    existing = find_context_entry(registry, resolved)
    if existing:
        existing["name"] = name
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        if remote is not None:
            existing["remote"] = remote
        if visibility:
            existing["visibility"] = visibility
        save_registry(registry)
        return existing

    # Create new entry
    entry = {
        "name": name,
        "path": resolved,
        "remote": remote,
        "visibility": visibility,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_sync": None,
    }
    registry["contexts"].append(entry)
    save_registry(registry)
    return entry


def unregister_context(seif_path: str) -> bool:
    """Remove a context from the registry."""
    registry = load_registry()
    resolved = str(Path(seif_path).resolve())
    original_len = len(registry.get("contexts", []))
    registry["contexts"] = [
        c for c in registry.get("contexts", [])
        if str(Path(c["path"]).resolve()) != resolved
    ]
    if len(registry["contexts"]) < original_len:
        save_registry(registry)
        return True
    return False


def list_contexts(registry: Optional[dict] = None) -> list[dict]:
    """List all registered contexts with health status."""
    if registry is None:
        registry = load_registry()

    results = []
    for ctx in registry.get("contexts", []):
        path = Path(ctx["path"])
        exists = path.exists()
        has_mapper = (path / "mapper.json").exists() if exists else False
        has_config = (path / "config.json").exists() if exists else False

        # Count modules
        module_count = 0
        if exists:
            for ext_file in path.rglob("*.seif"):
                module_count += 1

        results.append({
            **ctx,
            "exists": exists,
            "has_mapper": has_mapper,
            "has_config": has_config,
            "module_count": module_count,
        })
    return results


def update_sync_timestamp(seif_path: str) -> None:
    """Mark a context as just synced."""
    registry = load_registry()
    entry = find_context_entry(registry, seif_path)
    if entry:
        entry["last_sync"] = datetime.now(timezone.utc).isoformat()
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_registry(registry)


def detect_unregistered_contexts(scan_paths: Optional[list[str]] = None) -> list[Path]:
    """Scan specific directories for .seif/ dirs not in the registry.

    Only scans paths explicitly provided or configured in the registry.
    Never scans arbitrary user directories without consent.

    Args:
        scan_paths: Explicit list of directories to scan. If None, uses
                    paths from registry config (scan_roots field).
                    If neither exists, returns empty list (opt-in only).
    """
    registry = load_registry()
    registered_paths = {
        str(Path(c["path"]).resolve()) for c in registry.get("contexts", [])
    }

    # Determine scan roots: explicit > config > nothing (opt-in)
    if scan_paths:
        roots = [Path(p) for p in scan_paths]
    else:
        configured = registry.get("scan_roots", [])
        if not configured:
            return []
        roots = [Path(p).expanduser() for p in configured]

    candidates = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        # Only scan 2 levels deep, skip hidden dirs
        try:
            for child in root.iterdir():
                if not child.is_dir() or child.name.startswith("."):
                    continue
                seif_dir = child / ".seif"
                if seif_dir.is_dir() and str(seif_dir.resolve()) not in registered_paths:
                    candidates.append(seif_dir)
                # One more level
                try:
                    for grandchild in child.iterdir():
                        if not grandchild.is_dir() or grandchild.name.startswith("."):
                            continue
                        seif_dir = grandchild / ".seif"
                        if seif_dir.is_dir() and str(seif_dir.resolve()) not in registered_paths:
                            candidates.append(seif_dir)
                except PermissionError:
                    continue
        except PermissionError:
            continue

    return candidates
