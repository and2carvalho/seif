"""
Path resolution for SEIF data assets.

Works in both environments:
  - pip install: uses importlib.resources (assets inside site-packages)
  - git clone:   falls back to PROJECT_ROOT relative paths
"""

from pathlib import Path
from importlib import resources


# Git clone root (4 levels up from this file: data/ → seif/ → src/ → repo/)
_GIT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _package_data_dir() -> Path | None:
    """Try to resolve the seif.data package directory via importlib."""
    try:
        ref = resources.files("seif.data")
        # resources.files() may return a Traversable; convert to Path
        p = Path(str(ref))
        if p.is_dir():
            return p
    except (TypeError, ModuleNotFoundError):
        pass
    return None


def get_resonance_path() -> Path:
    """Return path to RESONANCE.json, preferring package data."""
    pkg = _package_data_dir()
    if pkg:
        candidate = pkg / "RESONANCE.json"
        if candidate.exists():
            return candidate
    return _GIT_ROOT / "RESONANCE.json"


def get_defaults_dir() -> Path:
    """Return path to defaults/ directory with .seif files."""
    pkg = _package_data_dir()
    if pkg:
        candidate = pkg / "defaults"
        if candidate.is_dir():
            return candidate
    return _GIT_ROOT / "data" / "defaults"


def get_modules_dir() -> Path:
    """Return path to user modules directory (always under git root or cwd)."""
    git_modules = _GIT_ROOT / "data" / "modules"
    if git_modules.parent.exists():
        return git_modules
    # Fallback: cwd-relative (for pip-installed usage outside repo)
    return Path.cwd() / ".seif" / "modules"


def get_user_home() -> Path:
    """Return path to ~/.seif/ (personal nucleus directory)."""
    return Path.home() / ".seif"


def get_profile_path() -> Path:
    """Return path to ~/.seif/profile.json."""
    return get_user_home() / "profile.json"


def get_sources_path() -> Path:
    """Return path to ~/.seif/sources.json."""
    return get_user_home() / "sources.json"
