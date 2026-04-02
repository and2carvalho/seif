"""
Autonomous Context Manager — AI-managed knowledge persistence.

Enables the AI to manage its own .seif knowledge base autonomously:
  - Observe conversations and detect persistable knowledge
  - Create/update .seif modules without human intervention
  - Maintain a mapper (index) for quick context reconstruction
  - Rebuild knowledge structure across sessions

The human provides context by living — writing code, making decisions,
explaining reasons. The AI observes, compresses, and structures.

This module manages:
  .seif/
  ├── mapper.json              ← live index (AI reads first, always)
  ├── config.json              ← enable/disable autonomous features
  ├── projects/
  │   └── <name>/
  │       ├── decisions.seif   ← architectural decisions (AI-created)
  │       ├── patterns.seif    ← observed code patterns (AI-created)
  │       ├── intent.seif      ← human intent for this project (AI-created)
  │       ├── feedback.seif    ← corrections and preferences (AI-created)
  │       └── context.seif     ← external constraints (AI-created)
  └── modules/                 ← cross-project knowledge (not tied to one project)
      └── <category>.seif

Other parts of the .seif/ structure are managed by separate modules:
  - nucleus.seif, manifest.json  → workspace.py
  - projects/<name>/ref.json     → ref.py
  - projects/<name>/project.seif → git_context.py

Usage:
  from seif.context.autonomous import (
      load_mapper, persist_knowledge, bootstrap_context,
      load_config, is_autonomous,
  )

  # At session start
  config = load_config(".seif")
  if is_autonomous(config):
      mapper = load_mapper(".seif")
      context = bootstrap_context(mapper, ".seif")

  # During session — AI decides to persist
  persist_knowledge(
      context_repo=".seif",
      project="api",
      category="decisions",
      content="Migrated to PostgreSQL because of JSONB support for event sourcing",
      author="claude-opus",
  )
"""

import json
import hashlib
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("seif.autonomous")


def find_context_repo(start_path: str = ".") -> Optional[str]:
    """Walk up the directory tree to find a .seif/ context repository.

    Similar to how git finds .git/ — starts at start_path and walks up
    until it finds a directory containing mapper.json or config.json
    (markers of a SEIF context repo), or reaches the filesystem root.

    Args:
        start_path: Directory to start searching from (default: cwd).

    Returns:
        Absolute path to the .seif/ directory, or None if not found.
    """
    current = Path(start_path).resolve()

    # Walk up to filesystem root (max 20 levels to prevent infinite loops)
    for _ in range(20):
        candidate = current / ".seif"
        if candidate.is_dir():
            # Verify it's a SEIF context repo (not just any .seif dir)
            if (candidate / "mapper.json").exists() or \
               (candidate / "config.json").exists() or \
               (candidate / "manifest.json").exists() or \
               (candidate / "RESONANCE.json").exists():
                return str(candidate)

        parent = current.parent
        if parent == current:
            break  # reached filesystem root
        current = parent

    return None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "autonomous_context": True,        # master switch (enabled by default)
    "auto_persist": True,              # AI creates modules without asking
    "read_only": False,                # read .seif but never write (shared environments)
    "persist_decisions": True,         # architectural decisions
    "persist_patterns": True,          # code patterns observed
    "persist_intent": True,            # human intent tracking
    "persist_feedback": True,          # corrections and preferences
    "quality_threshold": "C",          # minimum Quality Gate grade to persist
    "max_modules_per_project": 10,     # prevent unbounded growth
    "relevance_decay": 0.95,           # multiplied per session-end (0.0-1.0)
    # Classification
    "classification_default": "INTERNAL",
    "classification_rules": {
        "decisions": "INTERNAL",
        "patterns": "INTERNAL",
        "intent": "INTERNAL",
        "feedback": "INTERNAL",
        "context": "INTERNAL",
    },
    "classification_overrides": {},    # {"project/category": "PUBLIC"} — manual override
    "confidential_keywords": [
        "vulnerability", "CVE", "exploit", "secret", "key",
        "password", "token", "credential", "compliance",
        "LGPD", "GDPR", "breach", "leak", "pentest",
        "audit finding", "security gap", "attack vector",
    ],
    "require_confidential_approval": False,  # require explicit approve for CONFIDENTIAL writes
    "redact_on_export": True,
}

# Knowledge categories the AI can create
CATEGORIES = {
    "decisions":  "Architectural and technical decisions with reasoning",
    "patterns":   "Recurring code patterns, conventions, and preferences",
    "intent":     "Human goals, priorities, and motivations for the project",
    "feedback":   "Corrections, preferences, and interaction guidelines",
    "context":    "Important external context (deadlines, stakeholders, constraints)",
}

# Classification levels (ordered from most to least restrictive)
CLASSIFICATION_LEVELS = {
    "CONFIDENTIAL": 3,  # restricted access — exposure causes direct harm
    "INTERNAL": 2,      # org-private — useful for onboarding, not secret
    "PUBLIC": 1,        # open — can be in public repos
}

GRADE_ORDER = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}


def load_config(context_repo: str) -> dict:
    """Load autonomous context configuration.

    Args:
        context_repo: Path to the .seif context repository.

    Returns:
        Config dict (deep-copied defaults merged with user config).
    """
    import copy
    config_path = Path(context_repo) / "config.json"
    config = copy.deepcopy(DEFAULT_CONFIG)
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                user_config = json.load(f)
            config.update(user_config)
        except Exception as e:
            logger.warning("Failed to load config %s: %s", config_path, e)
    return config


def save_config(context_repo: str, config: dict) -> Path:
    """Save autonomous context configuration (atomic, locked).

    Args:
        context_repo: Path to the .seif context repository.
        config: Configuration dict.

    Returns:
        Path to saved config.json.
    """
    from seif.context.seif_io import locked_write_json

    ctx = Path(context_repo)
    ctx.mkdir(parents=True, exist_ok=True)
    config_path = ctx / "config.json"
    locked_write_json(config_path, config)
    return config_path


def is_autonomous(config: dict) -> bool:
    """Check if autonomous context management is enabled."""
    return config.get("autonomous_context", False)


# ---------------------------------------------------------------------------
# Mapper — the live index
# ---------------------------------------------------------------------------

@dataclass
class MapperEntry:
    """A single entry in the mapper index."""
    path: str                          # relative to context repo
    category: str                      # decisions, patterns, intent, feedback, context
    project: Optional[str] = None      # project name (None for cross-project)
    origin: str = "ai-observed"        # ai-observed | auto-sync | human
    relevance: float = 1.0             # 0-1, decays over time
    last_updated: str = ""
    trigger: str = ""                  # what caused this module to be created/updated
    word_count: int = 0
    integrity_hash: str = ""
    classification: str = "INTERNAL"   # PUBLIC | INTERNAL | CONFIDENTIAL


@dataclass
class Mapper:
    """The live index of all knowledge in the context repo."""
    protocol: str = "SEIF-MAPPER-v1"
    last_session: str = ""
    session_count: int = 0
    modules: list[MapperEntry] = field(default_factory=list)
    pending_observations: list[str] = field(default_factory=list)


def load_mapper(context_repo: str) -> Mapper:
    """Load mapper from context repo. Creates empty if not found.

    If mapper.json is missing but .seif files exist, rebuilds the index
    by scanning (self-healing).

    Args:
        context_repo: Path to the .seif context repository.

    Returns:
        Mapper with current index state.
    """
    mapper_path = Path(context_repo) / "mapper.json"

    if mapper_path.exists():
        try:
            with open(mapper_path, encoding="utf-8") as f:
                data = json.load(f)
            modules = [
                MapperEntry(**{k: v for k, v in m.items()
                              if k in MapperEntry.__dataclass_fields__})
                for m in data.get("modules", [])
            ]
            return Mapper(
                protocol=data.get("protocol", "SEIF-MAPPER-v1"),
                last_session=data.get("last_session", ""),
                session_count=data.get("session_count", 0),
                modules=modules,
                pending_observations=data.get("pending_observations", []),
            )
        except Exception as e:
            logger.warning("Failed to load mapper %s: %s", mapper_path, e)

    # Self-healing: scan for existing .seif files
    ctx = Path(context_repo)
    mapper = Mapper()
    if ctx.exists():
        mapper = _rebuild_mapper(context_repo)

    return mapper


def heal_mapper(context_repo: str) -> tuple[int, int]:
    """Detect orphan .seif files and register them in the mapper.

    Called automatically on session start. Ensures that modules created
    by other agents (who may not use the CLI wrapper) are tracked.

    Returns:
        (orphans_healed, ghosts_removed) count tuple.
    """
    ctx = Path(context_repo)
    mapper_path = ctx / "mapper.json"
    if not mapper_path.exists():
        return (0, 0)

    mapper = load_mapper(context_repo)
    mapper_paths = {m.path for m in mapper.modules}

    # Scan disk for .seif files
    disk_files = set()
    for root, _, files in os.walk(str(ctx)):
        for f in files:
            if f.endswith(".seif") and f != "nucleus.seif":
                rel = os.path.relpath(os.path.join(root, f), str(ctx))
                disk_files.add(rel)

    # Heal orphans (on disk, not in mapper)
    orphans = disk_files - mapper_paths
    healed = 0
    for orphan in orphans:
        full = ctx / orphan
        try:
            with open(full, encoding="utf-8") as fp:
                data = json.load(fp)
            summary = data.get("summary", "")
            h = hashlib.sha256(summary.encode()).hexdigest()[:16]
            # Infer project from path
            parts = orphan.split("/")
            project = parts[1] if len(parts) >= 3 and parts[0] == "projects" else None
            entry = MapperEntry(
                path=orphan,
                category=data.get("category", "context"),
                project=project,
                origin=data.get("contributors", [{}])[0].get("author", "unknown")
                       if data.get("contributors") else "unknown",
                relevance=0.9,
                last_updated=data.get("updated_at", ""),
                trigger=f"auto-healed orphan: {data.get('source', orphan)[:80]}",
                word_count=len(summary.split()),
                integrity_hash=h,
                classification=data.get("classification", "INTERNAL"),
            )
            mapper.modules.append(entry)
            healed += 1
            logger.info("Healed orphan: %s", orphan)
        except Exception as e:
            logger.warning("Could not heal orphan %s: %s", orphan, e)

    # Remove ghosts (in mapper, not on disk)
    ghosts = mapper_paths - disk_files
    removed = 0
    if ghosts:
        mapper.modules = [m for m in mapper.modules if m.path not in ghosts]
        removed = len(ghosts)
        for g in ghosts:
            logger.info("Removed ghost: %s", g)

    if healed or removed:
        save_mapper(context_repo, mapper)

    return (healed, removed)


def save_mapper(context_repo: str, mapper: Mapper) -> Path:
    """Save mapper to context repo (atomic, locked).

    Args:
        context_repo: Path to the .seif context repository.
        mapper: Mapper to save.

    Returns:
        Path to saved mapper.json.
    """
    from seif.context.seif_io import locked_write_json

    ctx = Path(context_repo)
    ctx.mkdir(parents=True, exist_ok=True)
    mapper_path = ctx / "mapper.json"
    locked_write_json(mapper_path, asdict(mapper))
    return mapper_path


def _rebuild_mapper(context_repo: str) -> Mapper:
    """Rebuild mapper by scanning existing .seif files (self-healing).

    Args:
        context_repo: Path to the .seif context repository.

    Returns:
        Reconstructed Mapper.
    """
    ctx = Path(context_repo)
    mapper = Mapper()

    for seif_file in ctx.rglob("*.seif"):
        rel = str(seif_file.relative_to(ctx))

        # Determine category and project from path
        parts = seif_file.relative_to(ctx).parts
        project = None
        category = "context"

        if len(parts) >= 2 and parts[0] == "projects":
            project = parts[1]
            if len(parts) >= 3:
                # projects/api/decisions.seif → category = decisions
                stem = seif_file.stem
                if stem in CATEGORIES:
                    category = stem
                elif stem == "project":
                    category = "context"
        elif seif_file.stem == "nucleus":
            category = "context"

        # Read basic metadata and verify integrity
        word_count = 0
        integrity_hash = ""
        origin = "rebuilt"
        try:
            with open(seif_file, encoding="utf-8") as f:
                data = json.load(f)
            word_count = data.get("compressed_words", 0)
            integrity_hash = data.get("integrity_hash", "")
            # Verify hash if summary exists
            summary = data.get("summary", "")
            if integrity_hash and summary:
                computed = hashlib.sha256(summary.encode()).hexdigest()[:16]
                if computed != integrity_hash:
                    logger.warning("Integrity mismatch in %s: expected %s, got %s",
                                   rel, integrity_hash, computed)
                    origin = "corrupted"
        except Exception as e:
            logger.warning("Failed to read %s during rebuild: %s", seif_file, e)

        mapper.modules.append(MapperEntry(
            path=rel,
            category=category,
            project=project,
            origin=origin,
            relevance=0.5 if origin == "corrupted" else 0.8,
            last_updated=datetime.now(timezone.utc).isoformat(),
            word_count=word_count,
            integrity_hash=integrity_hash,
        ))

    return mapper


@dataclass
class AuditResult:
    """Result of a context repository audit."""
    modules: int = 0
    files_on_disk: int = 0
    orphans_healed: int = 0
    ghosts_removed: int = 0
    hashes_fixed: int = 0
    pending_count: int = 0
    stale_count: int = 0
    issues: list = field(default_factory=list)
    synced: bool = False

    @property
    def clean(self) -> bool:
        return len(self.issues) == 0

    def __str__(self) -> str:
        icon = "+" if self.clean else "!"
        lines = [
            f"[{icon}] SEIF Context Audit",
            f"  Modules:  {self.modules} tracked, {self.files_on_disk} on disk",
            f"  Healed:   {self.orphans_healed} orphans, {self.ghosts_removed} ghosts",
            f"  Hashes:   {self.hashes_fixed} fixed",
            f"  Pending:  {self.pending_count} observations",
            f"  Stale:    {self.stale_count} (relevance < 0.3)",
        ]
        if self.synced:
            lines.append("  Synced:   yes")
        if self.issues:
            lines.append(f"  Issues:   {len(self.issues)}")
            for i in self.issues:
                lines.append(f"    ! {i}")
        else:
            lines.append("  Status:   ALL CLEAR")
        return "\n".join(lines)


def audit_context(context_repo: str, fix: bool = True,
                  sync: bool = False) -> AuditResult:
    """Comprehensive audit of a .seif context repository.

    Checks: orphans, ghosts, stale hashes, pending overflow,
    module integrity, and optionally fixes issues.

    Args:
        context_repo: Path to .seif context repo
        fix: If True, auto-heal orphans, remove ghosts, fix hashes
        sync: If True, also run git sync + workspace sync

    Returns:
        AuditResult with all findings
    """
    ctx = Path(context_repo)
    result = AuditResult()

    if not ctx.exists():
        result.issues.append(f"Context repo not found: {ctx}")
        return result

    # 1. Load mapper
    mapper = load_mapper(str(ctx))
    mapper_paths = {m.path for m in mapper.modules}

    # 2. Scan disk
    disk_files = set()
    for root, _, files in os.walk(str(ctx)):
        for f in files:
            if f.endswith(".seif") and f != "nucleus.seif":
                rel = os.path.relpath(os.path.join(root, f), str(ctx))
                disk_files.add(rel)

    result.modules = len(mapper.modules)
    result.files_on_disk = len(disk_files)
    result.pending_count = len(mapper.pending_observations)

    # 3. Orphans and ghosts
    orphans = disk_files - mapper_paths
    ghosts = mapper_paths - disk_files

    if orphans:
        if fix:
            healed, _ = heal_mapper(str(ctx))
            result.orphans_healed = healed
        else:
            result.issues.append(f"Orphans: {orphans}")

    if ghosts:
        if fix:
            _, removed = heal_mapper(str(ctx))
            result.ghosts_removed = removed
        else:
            result.issues.append(f"Ghosts: {ghosts}")

    # 4. Hash integrity
    mapper = load_mapper(str(ctx))  # reload after heal
    for m in mapper.modules:
        full = ctx / m.path
        if not full.exists():
            continue
        try:
            with open(full, encoding="utf-8") as fp:
                data = json.load(fp)
            summary = data.get("summary", "")
            real_hash = hashlib.sha256(summary.encode()).hexdigest()[:16]
            current = m.integrity_hash
            if current != real_hash:
                if len(current) < 10 or current.startswith(("pending", "session", "bigpickle", "absorp")):
                    if fix:
                        m.integrity_hash = real_hash
                        result.hashes_fixed += 1
                    else:
                        result.issues.append(f"Placeholder hash: {m.path} → {current}")
        except Exception:
            pass

    if result.hashes_fixed > 0 and fix:
        save_mapper(str(ctx), mapper)

    # 5. Stale modules
    result.stale_count = sum(1 for m in mapper.modules if m.relevance < 0.3)

    # 6. Pending overflow
    if result.pending_count > 10:
        result.issues.append(f"Pending overflow: {result.pending_count} (max 10)")

    # 7. Sync if requested
    if sync:
        try:
            from seif.context.git_context import sync_project
            # Find git repo (parent of .seif or cwd)
            for candidate in [ctx.parent, Path.cwd()]:
                if (candidate / ".git").exists():
                    repo_name = candidate.name
                    target = str(ctx / "projects" / repo_name / "project.seif")
                    sync_project(str(candidate), target_path=target)
                    result.synced = True
                    break
        except Exception as e:
            result.issues.append(f"Sync failed: {e}")

    # Update counts after all fixes
    mapper = load_mapper(str(ctx))
    result.modules = len(mapper.modules)

    return result


def _update_mapper_for_contribution(context_repo: str, rel_path: str,
                                     trigger: str = ""):
    """Update an existing mapper entry after a contribution."""
    from seif.context.seif_io import locked_read_modify_write

    mapper_path = Path(context_repo) / "mapper.json"

    def _update(data: dict) -> dict:
        for m in data.get("modules", []):
            if m["path"] == rel_path:
                m["last_updated"] = datetime.now(timezone.utc).isoformat()
                m["relevance"] = 1.0
                if trigger:
                    m["trigger"] = trigger
                break
        return data

    try:
        locked_read_modify_write(
            mapper_path, _update,
            default={"protocol": "SEIF-MAPPER-v1", "modules": [],
                     "pending_observations": [], "session_count": 0,
                     "last_session": ""},
        )
    except Exception as e:
        logger.warning("Failed to update mapper for %s: %s", rel_path, e)


# ---------------------------------------------------------------------------
# Knowledge persistence
# ---------------------------------------------------------------------------

def persist_knowledge(
    context_repo: str = None,
    project: Optional[str] = None,
    category: str = "",
    content: str = "",
    author: str = "ai",
    trigger: str = "",
    classification_override: str = None,
    approved: bool = False,
) -> Optional[MapperEntry]:
    """Persist a piece of knowledge as a .seif module.

    The AI calls this when it observes something worth persisting:
    a decision, a pattern, an intent, feedback, or external context.

    Args:
        context_repo: Path to the .seif context repository.
                     If None, walks up from cwd to find .seif/.
        project: Project name (None for cross-project knowledge).
        category: One of: decisions, patterns, intent, feedback, context.
        content: The knowledge to persist.
        author: Who is persisting (e.g., "claude-opus").
        trigger: What triggered this persistence (e.g., "user explained migration").
        classification_override: Explicit classification (bypasses auto-detection).
        approved: If True, bypasses the CONFIDENTIAL approval gate.

    Returns:
        MapperEntry for the persisted module, or None if config blocks it.
    """
    if context_repo is None:
        context_repo = find_context_repo()
    if context_repo is None:
        return None

    ctx = Path(context_repo)
    config = load_config(context_repo)

    # Check master switch
    if not is_autonomous(config):
        return None

    # Check read-only mode
    if config.get("read_only", False):
        return None

    # Check category toggle
    category_key = f"persist_{category}"
    if not config.get(category_key, True):
        return None

    # Check quality threshold
    grade = _assess_quality(content)
    threshold = config.get("quality_threshold", "C")
    if GRADE_ORDER.get(grade, 0) < GRADE_ORDER.get(threshold, 3):
        return None

    # Validate category
    if category not in CATEGORIES:
        return None

    # Determine target path
    if project:
        target_dir = ctx / "projects" / project
    else:
        target_dir = ctx / "modules"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{category}.seif"

    # Check module count limit — compact instead of reject
    if project:
        existing = list((ctx / "projects" / project).glob("*.seif"))
        max_modules = config.get("max_modules_per_project", 10)
        # Only count AI-created modules (exclude project.seif and code.seif)
        ai_modules = [f for f in existing
                      if f.stem not in ("project", "code")]
        if len(ai_modules) >= max_modules and not target_path.exists():
            # Try to compact: contribute to the category's main module instead
            category_module = target_dir / f"{category}.seif"
            if category_module.exists():
                logger.info(
                    "Module limit (%d) reached for %s. "
                    "Contributing to %s instead of creating new module.",
                    max_modules, project, category_module,
                )
                try:
                    from seif.context.context_manager import contribute_to_module
                    contribute_to_module(
                        str(category_module), content,
                        author=author, via="auto-compacted",
                    )
                    # Update mapper entry
                    _update_mapper_for_contribution(
                        context_repo, str(category_module.relative_to(ctx)),
                        trigger=f"compacted: {trigger[:60]}",
                    )
                    return MapperEntry(
                        path=str(category_module.relative_to(ctx)),
                        category=category, project=project,
                        origin="ai-observed", relevance=1.0,
                        last_updated=datetime.now(timezone.utc).isoformat(),
                        trigger=f"compacted: {trigger[:60]}",
                        word_count=len(content.split()),
                        integrity_hash="compacted",
                        classification=classify_content(
                            content, category, config,
                            override=classification_override, project=project),
                    )
                except Exception as e:
                    logger.warning("Compaction failed: %s", e)
                    return None
            else:
                return None

    # Classify content
    classification = classify_content(content, category, config,
                                      override=classification_override,
                                      project=project)

    # Approval gate for CONFIDENTIAL
    if classification == "CONFIDENTIAL" and not approved and \
       config.get("require_confidential_approval", False):
        # Use atomic update for pending observations (safe for concurrent agents)
        from seif.context.seif_io import locked_read_modify_write
        pending = f"CONFIDENTIAL_PENDING|{project or ''}|{category}|{trigger}"
        mapper_path = Path(context_repo) / "mapper.json"

        def _add_pending(data: dict) -> dict:
            obs = data.get("pending_observations", [])
            if pending not in obs:
                obs.append(pending)
                data["pending_observations"] = obs[-10:]
            return data

        try:
            locked_read_modify_write(mapper_path, _add_pending,
                                     default={"protocol": "SEIF-MAPPER-v1",
                                              "modules": [], "pending_observations": [pending],
                                              "session_count": 0, "last_session": ""})
        except Exception as e:
            logger.warning("Failed to record CONFIDENTIAL pending: %s", e)
        return None

    rel_path = str(target_path.relative_to(ctx))

    # Create or contribute the .seif module (this is already atomic via seif_io)
    from seif.context.context_manager import (
        create_module, save_module, contribute_to_module,
    )

    if target_path.exists():
        module, _ = contribute_to_module(
            str(target_path), content,
            author=author, via="autonomous",
        )
    else:
        module = create_module(
            source_name=f"{project or 'cross-project'}/{category}",
            original_words=len(content.split()) * 3,
            summary=content,
            author=author,
            via="autonomous",
        )
        save_module(module, target_path=target_path)

    # Stamp classification into the .seif file
    _stamp_classification(target_path, classification)

    # Update mapper atomically via locked_read_modify_write.
    # This prevents race conditions when multiple agents persist simultaneously:
    # each agent reads the CURRENT mapper state under lock, merges its entry,
    # and writes back — no lost entries from concurrent sessions.
    from seif.context.seif_io import locked_read_modify_write

    now_iso = datetime.now(timezone.utc).isoformat()
    mapper_path = ctx / "mapper.json"

    def _update_mapper(data: dict) -> dict:
        modules = data.get("modules", [])

        # Find existing entry by path (deduplicate)
        existing_idx = None
        for i, m in enumerate(modules):
            if m.get("path") == rel_path:
                existing_idx = i
                break

        entry_dict = {
            "path": rel_path,
            "category": category,
            "project": project,
            "origin": "ai-observed",
            "relevance": 1.0,
            "last_updated": now_iso,
            "trigger": trigger,
            "word_count": module.compressed_words,
            "integrity_hash": module.integrity_hash,
            "classification": classification,
        }

        if existing_idx is not None:
            old = modules[existing_idx]
            entry_dict["relevance"] = min(1.0, old.get("relevance", 0.8) + 0.1)
            # Classification: explicit override sets directly, auto only escalates
            if not classification_override:
                old_level = CLASSIFICATION_LEVELS.get(old.get("classification", "INTERNAL"), 2)
                new_level = CLASSIFICATION_LEVELS.get(classification, 2)
                if new_level <= old_level:
                    entry_dict["classification"] = old.get("classification", classification)
            modules[existing_idx] = entry_dict
        else:
            modules.append(entry_dict)

        data["modules"] = modules
        data["last_session"] = now_iso
        return data

    default_mapper = {
        "protocol": "SEIF-MAPPER-v1",
        "last_session": now_iso,
        "session_count": 0,
        "modules": [],
        "pending_observations": [],
    }

    updated_data = locked_read_modify_write(
        mapper_path, _update_mapper, default=default_mapper,
    )

    # Reconstruct the entry for return value
    for m in updated_data.get("modules", []):
        if m.get("path") == rel_path:
            return MapperEntry(**{k: v for k, v in m.items()
                                  if k in MapperEntry.__dataclass_fields__})

    return None


def classify_content(content: str, category: str, config: dict,
                     override: str = None, project: str = None) -> str:
    """Classify content as PUBLIC, INTERNAL, or CONFIDENTIAL.

    Uses a layered approach:
    0. Explicit override (highest priority — human decision)
    1. Config-based override by project/category
    2. Check for confidential keywords in content
    3. Apply category-level rule from config
    4. Fall back to default classification

    Args:
        content: The text to classify.
        category: Knowledge category (decisions, patterns, etc.).
        config: Autonomous context configuration.
        override: Explicit classification override (bypasses all auto-detection).
        project: Project name for config-based overrides.

    Returns:
        Classification level: "PUBLIC", "INTERNAL", or "CONFIDENTIAL".
    """
    # Layer 0: explicit override (human decision > auto-detection)
    # Security: log if override would downgrade from CONFIDENTIAL
    if override and override in CLASSIFICATION_LEVELS:
        if CLASSIFICATION_LEVELS.get(override, 0) < CLASSIFICATION_LEVELS.get("CONFIDENTIAL", 3):
            confidential_keywords = config.get("confidential_keywords", [])
            content_lower = content.lower()
            flagged = [kw for kw in confidential_keywords if kw.lower() in content_lower]
            if flagged:
                import sys
                print(
                    f"[SEIF] SECURITY: classification override to {override} "
                    f"but content contains confidential keywords: {flagged[:3]}. "
                    f"Project: {project}/{category}.",
                    file=sys.stderr,
                )
        return override

    # Layer 1: config-based override by project/category
    overrides = config.get("classification_overrides", {})
    override_key = f"{project or '*'}/{category}"
    if override_key in overrides and overrides[override_key] in CLASSIFICATION_LEVELS:
        return overrides[override_key]

    content_lower = content.lower()

    # Layer 2: keyword detection — auto-escalate to CONFIDENTIAL
    confidential_keywords = config.get("confidential_keywords", [])
    for keyword in confidential_keywords:
        if keyword.lower() in content_lower:
            return "CONFIDENTIAL"

    # Layer 3: category-level rule
    rules = config.get("classification_rules", {})
    if category in rules:
        return rules[category]

    # Layer 4: default
    return config.get("classification_default", "INTERNAL")


def _stamp_classification(seif_path: Path, classification: str):
    """Write classification into the .seif JSON file (locked read-modify-write)."""
    from seif.context.seif_io import locked_read_modify_write
    try:
        def _stamp(data):
            data["classification"] = classification
            return data
        locked_read_modify_write(seif_path, _stamp)
    except Exception as e:
        logger.warning("Failed to stamp classification on %s: %s", seif_path, e)


def _assess_quality(text: str) -> str:
    """Quick quality assessment for persist threshold.

    Returns the grade, or 'C' (pass) for LOW_DATA — short text
    is not low quality, it's just insufficient for full analysis.
    """
    try:
        from seif.analysis.quality_gate import assess
        verdict = assess(text[:500])
        # LOW_DATA means text is too short to judge — let it pass
        if verdict.status == "LOW_DATA":
            return "C"
        return verdict.grade
    except Exception as e:
        logger.debug("Quality assessment unavailable: %s", e)
        return "C"  # default pass


# ---------------------------------------------------------------------------
# Context bootstrap — session start
# ---------------------------------------------------------------------------

def bootstrap_context(mapper: Mapper, context_repo: str,
                      max_tokens: int = 4000,
                      max_classification: str = "CONFIDENTIAL") -> str:
    """Build context string from mapper for session start.

    Loads modules by relevance order, fitting within token budget.
    Filters by classification level for safe export.

    Args:
        mapper: Current mapper state.
        context_repo: Path to the .seif context repository.
        max_tokens: Approximate token budget.
        max_classification: Maximum classification to include.
            "PUBLIC" = only public modules.
            "INTERNAL" = public + internal (default for org use).
            "CONFIDENTIAL" = all modules (default, local use only).

    Returns:
        Context string with all loaded knowledge.
    """
    ctx = Path(context_repo)
    max_level = CLASSIFICATION_LEVELS.get(max_classification, 3)

    # Sort by relevance (highest first)
    sorted_entries = sorted(mapper.modules, key=lambda m: -m.relevance)

    parts = []
    total_words = 0
    word_budget = int(max_tokens / 1.3)  # rough tokens-to-words

    for entry in sorted_entries:
        if total_words >= word_budget:
            break

        # Filter by classification
        entry_level = CLASSIFICATION_LEVELS.get(entry.classification, 2)
        if entry_level > max_level:
            continue

        seif_path = ctx / entry.path
        if not seif_path.exists():
            continue

        try:
            with open(seif_path, encoding="utf-8") as f:
                data = json.load(f)
            summary = data.get("summary", "")
            words = len(summary.split())

            if total_words + words > word_budget:
                # Truncate to fit
                remaining = word_budget - total_words
                summary = " ".join(summary.split()[:remaining])
                words = remaining

            label = entry.category.upper()
            if entry.project:
                label = f"{entry.project}/{label}"

            classification_tag = entry.classification
            parts.append(f"[{label}] [{classification_tag}] {summary}")
            total_words += words
        except Exception as e:
            logger.warning("Failed to load module %s: %s", entry.path, e)
            continue

    if mapper.pending_observations:
        parts.append(
            "[PENDING] " + " | ".join(mapper.pending_observations[:5])
        )

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def start_session(context_repo: str = None) -> tuple[dict, Mapper, str]:
    """Called at session start. Returns config, mapper, and bootstrap context.

    Args:
        context_repo: Path to the .seif context repository.
                     If None, walks up from cwd to find .seif/.

    Returns:
        Tuple of (config, mapper, context_string).
    """
    if context_repo is None:
        context_repo = find_context_repo()
    if context_repo is None:
        return dict(DEFAULT_CONFIG), Mapper(), ""

    config = load_config(context_repo)
    mapper = load_mapper(context_repo)

    context = ""
    if is_autonomous(config):
        context = bootstrap_context(mapper, context_repo)

    # Write session tracking (skip in read-only mode)
    if not config.get("read_only", False):
        mapper.session_count += 1
        mapper.last_session = datetime.now(timezone.utc).isoformat()
        save_mapper(context_repo, mapper)

    return config, mapper, context


def end_session(context_repo: str = None,
                pending_observations: list[str] = None) -> Mapper:
    """Called at session end. Saves pending observations for next session.

    Args:
        context_repo: Path to the .seif context repository.
                     If None, walks up from cwd to find .seif/.
        pending_observations: Things the AI noticed but couldn't persist yet.

    Returns:
        Updated Mapper.
    """
    if context_repo is None:
        context_repo = find_context_repo()
    if context_repo is None:
        return Mapper()

    config = load_config(context_repo)

    # Read-only mode: return current state without writing
    if config.get("read_only", False):
        return load_mapper(context_repo)

    # Atomic mapper update for session end.
    # Multiple agents may end sessions concurrently — each must
    # merge its observations and apply decay without losing entries
    # added by other agents between read and write.
    from seif.context.seif_io import locked_read_modify_write

    now_iso = datetime.now(timezone.utc).isoformat()
    decay = max(0.0, min(1.0, config.get("relevance_decay", 0.95)))
    mapper_path = Path(context_repo) / "mapper.json"

    def _end_session_update(data: dict) -> dict:
        data["last_session"] = now_iso

        if pending_observations:
            existing = data.get("pending_observations", [])
            data["pending_observations"] = (existing + pending_observations)[-10:]

        for m in data.get("modules", []):
            m["relevance"] = max(0.1, m.get("relevance", 1.0) * decay)

        return data

    default_mapper = {
        "protocol": "SEIF-MAPPER-v1",
        "last_session": now_iso,
        "session_count": 0,
        "modules": [],
        "pending_observations": pending_observations or [],
    }

    try:
        updated_data = locked_read_modify_write(
            mapper_path, _end_session_update, default=default_mapper,
        )
    except Exception as e:
        logger.warning("Failed to update mapper on session end: %s", e)
        return load_mapper(context_repo)

    # Reconstruct Mapper for return value
    modules = [
        MapperEntry(**{k: v for k, v in m.items()
                      if k in MapperEntry.__dataclass_fields__})
        for m in updated_data.get("modules", [])
    ]
    return Mapper(
        protocol=updated_data.get("protocol", "SEIF-MAPPER-v1"),
        last_session=updated_data.get("last_session", now_iso),
        session_count=updated_data.get("session_count", 0),
        modules=modules,
        pending_observations=updated_data.get("pending_observations", []),
    )


def add_observation(context_repo: str = None, observation: str = "") -> Mapper:
    """Add a pending observation for the next session.

    Args:
        context_repo: Path to the .seif context repository.
                     If None, walks up from cwd to find .seif/.
        observation: What to remember for next session.

    Returns:
        Updated Mapper.
    """
    if context_repo is None:
        context_repo = find_context_repo()
    if context_repo is None:
        return Mapper()

    config = load_config(context_repo)
    if config.get("read_only", False):
        return load_mapper(context_repo)

    # Atomic append to pending_observations — safe for concurrent agents.
    from seif.context.seif_io import locked_read_modify_write

    mapper_path = Path(context_repo) / "mapper.json"

    def _add_obs(data: dict) -> dict:
        obs = data.get("pending_observations", [])
        obs.append(observation)
        data["pending_observations"] = obs[-10:]
        return data

    default_mapper = {
        "protocol": "SEIF-MAPPER-v1",
        "last_session": "",
        "session_count": 0,
        "modules": [],
        "pending_observations": [observation],
    }

    try:
        updated_data = locked_read_modify_write(
            mapper_path, _add_obs, default=default_mapper,
        )
        modules = [
            MapperEntry(**{k: v for k, v in m.items()
                          if k in MapperEntry.__dataclass_fields__})
            for m in updated_data.get("modules", [])
        ]
        return Mapper(
            protocol=updated_data.get("protocol", "SEIF-MAPPER-v1"),
            last_session=updated_data.get("last_session", ""),
            session_count=updated_data.get("session_count", 0),
            modules=modules,
            pending_observations=updated_data.get("pending_observations", []),
        )
    except Exception as e:
        logger.warning("Failed to add observation: %s", e)
        return load_mapper(context_repo)
