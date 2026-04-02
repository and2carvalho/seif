"""
Personal Nucleus — ~/.seif/ as the user's global context layer.

Manages:
  - profile.json: user identity, preferences, default backend
  - sources.json: GitHub repos with .seif context the user has access to
  - nucleus aggregation: combine all sources into a single context block
"""

import json
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from seif.data.paths import get_user_home, get_profile_path, get_sources_path


# ── Defaults ──────────────────────────────────────────────────────

DEFAULT_PROFILE = {
    "name": "",
    "email": "",
    "github_username": "",
    "default_backend": "claude",
    "language": "en",
    "classification_default": "INTERNAL",
    "auto_fetch": True,
    "created_at": "",
    "updated_at": "",
}

VALID_BACKENDS = {"claude", "gemini", "grok", "local", "auto"}
VALID_LANGUAGES = {"en", "pt_br"}
VALID_CLASSIFICATIONS = {"PUBLIC", "INTERNAL", "CONFIDENTIAL"}


# ── Data classes ──────────────────────────────────────────────────

@dataclass
class Source:
    repo: str                          # e.g. "github.com/and2carvalho/seif-context"
    type: str = "context"              # context | research | project
    local_path: str = ""               # ~/.seif/cache/<name>
    last_synced: str = ""
    classification: str = "INTERNAL"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Source":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Profile ───────────────────────────────────────────────────────

def load_profile(path: Optional[Path] = None) -> dict:
    """Load profile from ~/.seif/profile.json. Returns defaults if missing."""
    p = path or get_profile_path()
    if p.exists():
        try:
            with open(p) as f:
                data = json.load(f)
            # Merge with defaults for any missing keys
            merged = {**DEFAULT_PROFILE, **data}
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_PROFILE)


def save_profile(profile: dict, path: Optional[Path] = None) -> Path:
    """Save profile to ~/.seif/profile.json."""
    p = path or get_profile_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    if not profile.get("created_at"):
        profile["created_at"] = profile["updated_at"]
    with open(p, "w") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    return p


def init_profile(name: str = "", email: str = "", github_username: str = "",
                 default_backend: str = "claude", language: str = "en") -> Path:
    """Create or update ~/.seif/profile.json."""
    profile = load_profile()
    if name:
        profile["name"] = name
    if email:
        profile["email"] = email
    if github_username:
        profile["github_username"] = github_username
    if default_backend in VALID_BACKENDS:
        profile["default_backend"] = default_backend
    if language in VALID_LANGUAGES:
        profile["language"] = language
    return save_profile(profile)


# ── Sources ───────────────────────────────────────────────────────

def load_sources(path: Optional[Path] = None) -> list[Source]:
    """Load sources from ~/.seif/sources.json. Returns empty list if missing."""
    p = path or get_sources_path()
    if p.exists():
        try:
            with open(p) as f:
                data = json.load(f)
            return [Source.from_dict(s) for s in data if isinstance(s, dict)]
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_sources(sources: list[Source], path: Optional[Path] = None) -> Path:
    """Save sources to ~/.seif/sources.json."""
    p = path or get_sources_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump([s.to_dict() for s in sources], f, indent=2)
    return p


def add_source(repo: str, source_type: str = "context",
               classification: str = "INTERNAL") -> Source:
    """Add a new source repo to ~/.seif/sources.json."""
    sources = load_sources()
    # Avoid duplicates
    for s in sources:
        if s.repo == repo:
            return s

    # Derive cache path from repo name
    repo_name = repo.rstrip("/").split("/")[-1]
    cache_dir = get_user_home() / "cache" / repo_name

    source = Source(
        repo=repo,
        type=source_type,
        local_path=str(cache_dir),
        classification=classification,
    )
    sources.append(source)
    save_sources(sources)
    return source


def remove_source(repo: str) -> bool:
    """Remove a source from ~/.seif/sources.json."""
    sources = load_sources()
    original = len(sources)
    sources = [s for s in sources if s.repo != repo]
    if len(sources) < original:
        save_sources(sources)
        return True
    return False


# ── Sync ──────────────────────────────────────────────────────────

def sync_source(source: Source) -> bool:
    """Git fetch/clone a source repo to its local_path. Returns True on success."""
    local = Path(source.local_path)

    try:
        if local.exists() and (local / ".git").exists():
            # Fetch latest
            result = subprocess.run(
                ["git", "-C", str(local), "fetch", "--depth=1", "--quiet"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                # Fast-forward to origin/main or origin/HEAD
                subprocess.run(
                    ["git", "-C", str(local), "reset", "--hard", "FETCH_HEAD"],
                    capture_output=True, text=True, timeout=10,
                )
        else:
            # Clone shallow
            local.parent.mkdir(parents=True, exist_ok=True)
            # Convert repo shorthand to full URL
            url = _resolve_repo_url(source.repo)
            result = subprocess.run(
                ["git", "clone", "--depth=1", "--quiet", url, str(local)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                return False

        source.last_synced = datetime.now(timezone.utc).isoformat()
        return True
    except (subprocess.TimeoutExpired, OSError):
        return False


def sync_all_sources(auto_fetch: bool = True) -> list[dict]:
    """Sync all sources. Returns list of {repo, success, last_synced}."""
    if not auto_fetch:
        return []

    sources = load_sources()
    results = []
    for source in sources:
        ok = sync_source(source)
        results.append({
            "repo": source.repo,
            "success": ok,
            "last_synced": source.last_synced,
        })

    # Save updated timestamps
    if sources:
        save_sources(sources)

    return results


def _resolve_repo_url(repo: str) -> str:
    """Convert repo shorthand to full git URL."""
    if repo.startswith("http://") or repo.startswith("https://") or repo.startswith("git@"):
        return repo
    # Assume github shorthand: "user/repo" or "github.com/user/repo"
    repo = repo.removeprefix("github.com/")
    return f"https://github.com/{repo}.git"


# ── Nucleus Aggregation ───────────────────────────────────────────

def build_personal_nucleus(profile: Optional[dict] = None,
                           sources: Optional[list[Source]] = None,
                           max_classification: str = "INTERNAL") -> str:
    """Aggregate user identity + context from all sources into text."""
    profile = profile or load_profile()
    sources = sources or load_sources()

    parts = []

    # User identity
    if profile.get("name"):
        parts.append(f"User: {profile['name']}")
    if profile.get("default_backend"):
        parts.append(f"Default backend: {profile['default_backend']}")
    if profile.get("language"):
        parts.append(f"Language: {profile['language']}")

    # Source context
    for source in sources:
        # Respect classification
        if _classification_level(source.classification) > _classification_level(max_classification):
            continue

        local = Path(source.local_path)
        if not local.exists():
            continue

        # Load nucleus or mapper from source
        nucleus_path = local / ".seif" / "nucleus.seif"
        mapper_path = local / ".seif" / "mapper.json"

        if nucleus_path.exists():
            try:
                with open(nucleus_path) as f:
                    data = json.load(f)
                summary = data.get("summary", "")
                if summary:
                    parts.append(f"\n[Source: {source.repo} ({source.type})]")
                    parts.append(summary[:2000])  # Cap per source
            except (json.JSONDecodeError, OSError):
                pass
        elif mapper_path.exists():
            try:
                with open(mapper_path) as f:
                    data = json.load(f)
                module_count = len(data.get("modules", []))
                last_session = data.get("last_session", "unknown")
                parts.append(f"\n[Source: {source.repo} ({source.type})]")
                parts.append(f"  {module_count} modules, last session: {last_session}")
            except (json.JSONDecodeError, OSError):
                pass

    if not parts:
        return ""

    return "PERSONAL NUCLEUS\n" + "\n".join(parts)


def _classification_level(c: str) -> int:
    """Map classification to numeric level."""
    return {"PUBLIC": 1, "INTERNAL": 2, "CONFIDENTIAL": 3}.get(c, 2)
