"""
SEIF Session Manager — Track and manage AI collaboration sessions.

A session is a single conversation/interaction between human and AI(s).
Sessions live inside cycles (macro) as the micro unit of work.

Lifecycle:
  create     → open a new session (SEIF-SESSION-v2)
  contribute → add a message/observation to the session
  close      → archive session, persist to owner-session-history.seif
  list       → list all sessions (open + archived)
  show       → describe a session
  log        → show session timeline
  sync       → create sync point between participants
  resume     → re-open interrupted session

Storage:
  .seif/sessions/<name>.json     — active sessions
  .seif/sessions/archive/<name>.json — closed sessions
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from seif.context.seif_io import (
    atomic_write_json,
    locked_read_modify_write,
    compute_hash,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def _resolve_ctx(context_repo) -> Path:
    """Resolve context repo path."""
    if context_repo:
        return Path(context_repo).resolve()
    # Walk up looking for .seif/
    current = Path.cwd()
    for _ in range(20):
        candidate = current / ".seif"
        if candidate.is_dir():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return Path(".seif")


def _sessions_dir(ctx: Path) -> Path:
    d = ctx / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _archive_dir(ctx: Path) -> Path:
    d = ctx / "sessions" / "archive"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_path(ctx: Path, name: str) -> Path:
    return _sessions_dir(ctx) / f"{name}.seif"


def _archived_path(ctx: Path, name: str) -> Path:
    return _archive_dir(ctx) / f"{name}.seif"


def _find_session(ctx: Path, name: str) -> Optional[Path]:
    """Find session file (active or archived)."""
    active = _session_path(ctx, name)
    if active.exists():
        return active
    archived = _archived_path(ctx, name)
    if archived.exists():
        return archived
    return None


def _load_session(ctx: Path, name: str) -> Optional[dict]:
    path = _find_session(ctx, name)
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _compute_integrity(data: dict) -> str:
    """Compute integrity hash excluding the hash field itself."""
    filtered = {k: v for k, v in data.items() if k != "integrity_hash"}
    raw = json.dumps(filtered, sort_keys=True, ensure_ascii=False)
    return compute_hash(raw)


# ── Public API ───────────────────────────────────────────────────────────────

def create_session(
    context_repo: str,
    name: str,
    author: str = "unknown",
    purpose: str = "",
) -> str:
    """Create a v1 session. Returns path to session file."""
    return create_session_v2(context_repo, name, author, purpose)


def create_session_v2(
    context_repo: str,
    name: str,
    author: str = "unknown",
    purpose: str = "",
) -> str:
    """Create a SEIF-SESSION-v2 session with mesh topology and auto-sync.

    Returns path to the created session file.
    """
    ctx = _resolve_ctx(context_repo)
    path = _session_path(ctx, name)

    if path.exists():
        raise FileExistsError(f"Session '{name}' already exists: {path}")

    now = _now_iso()
    session = {
        "schema": "SEIF-SESSION-v2",
        "name": name,
        "status": "OPEN",
        "purpose": purpose,
        "created_at": now,
        "updated_at": now,
        "version": 2,
        "participants": [
            {
                "id": author,
                "role": "creator",
                "channel": "cli",
                "joined_at": now,
            }
        ],
        "messages": [],
        "sync_points": [],
        "sync_threshold": 10,
        "deliverables": [],
        "decisions": [],
        "observations": [],
        "integrity_hash": "",
    }
    session["integrity_hash"] = _compute_integrity(session)
    atomic_write_json(path, session)
    return str(path)


def contribute_to_session(
    context_repo: str,
    name: str,
    content: str,
    author: str = "unknown",
    via: str = "cli",
    action: str = "contributed",
) -> dict:
    """Add a message to a session. Returns updated session."""
    ctx = _resolve_ctx(context_repo)
    path = _session_path(ctx, name)

    if not path.exists():
        # Check archive
        archived = _archived_path(ctx, name)
        if archived.exists():
            raise ValueError(f"Session '{name}' is closed. Use --session resume first.")
        raise FileNotFoundError(f"Session '{name}' not found.")

    def updater(data):
        now = _now_iso()
        data["messages"].append({
            "author": author,
            "content": content,
            "via": via,
            "action": action,
            "at": now,
        })
        data["updated_at"] = now
        data["integrity_hash"] = _compute_integrity(data)
        return data

    return locked_read_modify_write(path, updater)


def contribute_with_sync_check(
    context_repo: str,
    name: str,
    content: str,
    author: str = "unknown",
    via: str = "cli",
    auto_sync_author: str = "unknown",
) -> tuple:
    """Contribute and auto-sync if threshold reached. Returns (session, synced)."""
    ctx = _resolve_ctx(context_repo)
    path = _session_path(ctx, name)

    if not path.exists():
        raise FileNotFoundError(f"Session '{name}' not found.")

    synced = False

    def updater(data):
        nonlocal synced
        now = _now_iso()
        data["messages"].append({
            "author": author,
            "content": content,
            "via": via,
            "action": "contributed",
            "at": now,
        })
        data["updated_at"] = now

        # Check sync threshold
        threshold = data.get("sync_threshold", 10)
        last_sync_idx = 0
        for sp in data.get("sync_points", []):
            last_sync_idx = max(last_sync_idx, sp.get("message_index", 0))
        unsynced = len(data["messages"]) - last_sync_idx
        if unsynced >= threshold:
            data["sync_points"].append({
                "author": auto_sync_author,
                "at": now,
                "message_index": len(data["messages"]),
                "digest": f"Auto-sync at message #{len(data['messages'])}",
                "integrity_hash": _short_hash(json.dumps(data["messages"][-5:])),
            })
            synced = True

        data["integrity_hash"] = _compute_integrity(data)
        return data

    result = locked_read_modify_write(path, updater)
    return result, synced


def close_session(
    context_repo: str,
    name: str,
    author: str = "unknown",
) -> str:
    """Close a session: archive it and persist summary to owner-session-history.

    Returns path to the archived session file.
    """
    ctx = _resolve_ctx(context_repo)
    active_path = _session_path(ctx, name)

    if not active_path.exists():
        raise FileNotFoundError(f"Active session '{name}' not found.")

    with open(active_path, "r", encoding="utf-8") as f:
        session = json.load(f)

    now = _now_iso()
    session["status"] = "CLOSED"
    session["closed_at"] = now
    session["closed_by"] = author
    session["updated_at"] = now
    session["integrity_hash"] = _compute_integrity(session)

    # Move to archive
    archive_path = _archived_path(ctx, name)
    atomic_write_json(archive_path, session)
    active_path.unlink()

    # Persist summary to owner-session-history.seif
    _persist_to_session_history(ctx, session, author)

    return str(archive_path)


def _persist_to_session_history(ctx: Path, session: dict, author: str) -> None:
    """Append a closed session summary to .seif/modules/owner-session-history.seif."""
    history_path = ctx / "modules" / "owner-session-history.seif"
    if not history_path.exists():
        return  # No history module to update

    now = _now_iso()
    messages = session.get("messages", [])
    participants = [p.get("id", "?") for p in session.get("participants", [])]

    summary_entry = {
        "id": len(_load_history_sessions(history_path)) + 1,
        "date": session.get("created_at", now)[:10],
        "title": session.get("purpose") or session.get("name", "untitled"),
        "duration": _estimate_duration(session),
        "participants": participants,
        "status": "CLOSED",
        "messages_count": len(messages),
        "deliverables": session.get("deliverables", []),
        "decisions": session.get("decisions", []),
        "observations": session.get("observations", []),
        "created_at": session.get("created_at"),
        "closed_at": session.get("closed_at"),
    }

    def updater(data):
        data.setdefault("sessions", [])
        data["sessions"].append(summary_entry)
        data["updated_at"] = now
        # Update contributor log
        data.setdefault("contributors", [])
        data["contributors"].append({
            "author": author,
            "at": now,
            "via": "session-close",
            "action": f"persisted session '{session.get('name', '?')}' from close_session()",
        })
        data["integrity_hash"] = "pending_recalc"
        return data

    locked_read_modify_write(history_path, updater)


def _load_history_sessions(path: Path) -> list:
    """Load existing sessions from history module."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("sessions", [])
    except Exception:
        return []


def _estimate_duration(session: dict) -> str:
    """Estimate session duration from first/last message timestamps."""
    messages = session.get("messages", [])
    if len(messages) < 2:
        return "unknown"
    try:
        first = datetime.fromisoformat(messages[0]["at"])
        last = datetime.fromisoformat(messages[-1]["at"])
        delta = last - first
        hours = delta.total_seconds() / 3600
        if hours < 1:
            return f"~{int(delta.total_seconds() / 60)}min"
        return f"~{hours:.1f}h"
    except (KeyError, ValueError):
        return "unknown"


def list_sessions(context_repo: str) -> list:
    """List all sessions (active + archived)."""
    ctx = _resolve_ctx(context_repo)
    sessions = []

    # Active
    sessions_dir = ctx / "sessions"
    if sessions_dir.is_dir():
        for f in sorted(sessions_dir.glob("*.json")):
            if f.name == "archive":
                continue
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                sessions.append({
                    "name": data.get("name", f.stem),
                    "status": data.get("status", "UNKNOWN"),
                    "version": data.get("version", 1),
                    "contributors": len(data.get("participants", [])),
                    "updated": data.get("updated_at", "?")[:19],
                    "interrupted": data.get("status") == "INTERRUPTED",
                })
            except Exception:
                pass

    # Archived
    archive = ctx / "sessions" / "archive"
    if archive.is_dir():
        for f in sorted(archive.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                sessions.append({
                    "name": data.get("name", f.stem),
                    "status": data.get("status", "CLOSED"),
                    "version": data.get("version", 1),
                    "contributors": len(data.get("participants", [])),
                    "updated": data.get("updated_at", "?")[:19],
                    "interrupted": False,
                })
            except Exception:
                pass

    return sessions


def describe_session(context_repo: str, name: str) -> str:
    """Describe a session in human-readable format."""
    ctx = _resolve_ctx(context_repo)
    session = _load_session(ctx, name)
    if not session:
        return f"Session '{name}' not found."

    lines = [
        f"Session: {session.get('name', '?')}",
        f"  Schema  : {session.get('schema', '?')}",
        f"  Status  : {session.get('status', '?')}",
        f"  Purpose : {session.get('purpose', '')}",
        f"  Created : {session.get('created_at', '?')[:19]}",
        f"  Updated : {session.get('updated_at', '?')[:19]}",
    ]

    if session.get("closed_at"):
        lines.append(f"  Closed  : {session['closed_at'][:19]}")

    participants = session.get("participants", [])
    if participants:
        lines.append(f"  Participants ({len(participants)}):")
        for p in participants:
            lines.append(f"    - {p.get('id','?')} [{p.get('role','?')}] via {p.get('channel','?')}")

    messages = session.get("messages", [])
    lines.append(f"  Messages: {len(messages)}")

    sync_points = session.get("sync_points", [])
    if sync_points:
        lines.append(f"  Sync points: {len(sync_points)}")

    deliverables = session.get("deliverables", [])
    if deliverables:
        lines.append(f"  Deliverables ({len(deliverables)}):")
        for d in deliverables:
            lines.append(f"    - {d}")

    lines.append(f"  Hash    : {session.get('integrity_hash', '?')}")
    return "\n".join(lines)


def session_log(context_repo: str, name: str) -> str:
    """Show session message timeline."""
    ctx = _resolve_ctx(context_repo)
    session = _load_session(ctx, name)
    if not session:
        return f"Session '{name}' not found."

    lines = [f"Session log: {name}", ""]
    messages = session.get("messages", [])
    sync_indices = {sp.get("message_index", -1) for sp in session.get("sync_points", [])}

    for i, msg in enumerate(messages, 1):
        ts = msg.get("at", "?")[:19]
        author = msg.get("author", "?")
        action = msg.get("action", "")
        content = msg.get("content", "")
        # Truncate long content
        if len(content) > 200:
            content = content[:200] + "..."
        sync_marker = " [SYNC]" if i in sync_indices else ""
        lines.append(f"  [{ts}] {author} ({action}){sync_marker}")
        lines.append(f"    {content}")
        lines.append("")

    if not messages:
        lines.append("  (no messages)")

    return "\n".join(lines)


def add_participant(
    context_repo: str,
    name: str,
    participant_id: str,
    role: str = "contributor",
    channel: str = "cli",
    author: str = "unknown",
) -> dict:
    """Add a participant to a session."""
    ctx = _resolve_ctx(context_repo)
    path = _session_path(ctx, name)
    if not path.exists():
        raise FileNotFoundError(f"Session '{name}' not found.")

    def updater(data):
        now = _now_iso()
        # Check if already exists
        existing = [p for p in data.get("participants", []) if p.get("id") == participant_id]
        if existing:
            return data  # Already added

        data.setdefault("participants", [])
        data["participants"].append({
            "id": participant_id,
            "role": role,
            "channel": channel,
            "joined_at": now,
            "added_by": author,
        })
        data["updated_at"] = now
        data["integrity_hash"] = _compute_integrity(data)
        return data

    return locked_read_modify_write(path, updater)


def create_sync_point(
    context_repo: str,
    name: str,
    author: str = "unknown",
    digest: str = "",
) -> dict:
    """Create a sync point in the session."""
    ctx = _resolve_ctx(context_repo)
    path = _session_path(ctx, name)
    if not path.exists():
        raise FileNotFoundError(f"Session '{name}' not found.")

    def updater(data):
        now = _now_iso()
        data.setdefault("sync_points", [])
        data["sync_points"].append({
            "author": author,
            "at": now,
            "message_index": len(data.get("messages", [])),
            "digest": digest,
            "integrity_hash": _short_hash(json.dumps(data.get("messages", [])[-5:])),
        })
        data["updated_at"] = now
        data["integrity_hash"] = _compute_integrity(data)
        return data

    return locked_read_modify_write(path, updater)


def needs_sync(context_repo: str, name: str) -> tuple:
    """Check if session needs sync. Returns (needs_sync: bool, unsynced_count: int)."""
    ctx = _resolve_ctx(context_repo)
    session = _load_session(ctx, name)
    if not session:
        return False, 0

    threshold = session.get("sync_threshold", 10)
    messages = session.get("messages", [])
    sync_points = session.get("sync_points", [])

    last_sync_idx = 0
    for sp in sync_points:
        last_sync_idx = max(last_sync_idx, sp.get("message_index", 0))

    unsynced = len(messages) - last_sync_idx
    return unsynced >= threshold, unsynced


def generate_sync_prompt(context_repo: str, name: str, participant_id: str) -> str:
    """Generate a sync prompt for a participant to catch up."""
    ctx = _resolve_ctx(context_repo)
    session = _load_session(ctx, name)
    if not session:
        return f"Session '{name}' not found."

    messages = session.get("messages", [])
    participants = session.get("participants", [])

    lines = [
        f"# SEIF Session Sync — {name}",
        f"Purpose: {session.get('purpose', '')}",
        f"Status: {session.get('status', '?')}",
        f"Messages: {len(messages)}",
        f"Participants: {', '.join(p.get('id','?') for p in participants)}",
        "",
        "## Recent messages (last 10):",
    ]

    for msg in messages[-10:]:
        ts = msg.get("at", "?")[:19]
        author = msg.get("author", "?")
        content = msg.get("content", "")
        if len(content) > 300:
            content = content[:300] + "..."
        lines.append(f"  [{ts}] {author}: {content}")

    lines.append("")
    lines.append(f"You are joining as: {participant_id}")
    lines.append("Catch up on the above and continue the session.")

    return "\n".join(lines)


def update_session_status(
    context_repo: str,
    name: str,
    status: str,
    author: str = "unknown",
) -> dict:
    """Update session status (OPEN, INTERRUPTED, CLOSED)."""
    ctx = _resolve_ctx(context_repo)

    # Check active first, then archive
    path = _session_path(ctx, name)
    if not path.exists():
        # If resuming from archive, move back to active
        archived = _archived_path(ctx, name)
        if archived.exists() and status == "OPEN":
            import shutil
            shutil.move(str(archived), str(path))
        elif not archived.exists():
            raise FileNotFoundError(f"Session '{name}' not found.")

    def updater(data):
        now = _now_iso()
        data["status"] = status
        data["updated_at"] = now
        if status == "INTERRUPTED":
            data["interrupted"] = True
            data["interrupted_at"] = now
        elif status == "OPEN" and data.get("interrupted"):
            data["resumed_at"] = now
            data["interrupted"] = False
        data["integrity_hash"] = _compute_integrity(data)
        return data

    return locked_read_modify_write(path, updater)


def upgrade_to_v2(context_repo: str, name: str) -> dict:
    """Upgrade a v1 session to v2 (mesh topology, auto-sync)."""
    ctx = _resolve_ctx(context_repo)
    path = _find_session(ctx, name)
    if not path:
        raise FileNotFoundError(f"Session '{name}' not found.")

    def updater(data):
        if data.get("version", 1) >= 2:
            return data  # Already v2

        now = _now_iso()
        data["schema"] = "SEIF-SESSION-v2"
        data["version"] = 2
        data["updated_at"] = now

        # Migrate contributors to participants
        if "participants" not in data:
            data["participants"] = []
            for contrib in data.get("contributors", []):
                data["participants"].append({
                    "id": contrib.get("author", "unknown"),
                    "role": "contributor",
                    "channel": contrib.get("via", "cli"),
                    "joined_at": contrib.get("at", now),
                })

        data.setdefault("sync_points", [])
        data.setdefault("sync_threshold", 10)
        data.setdefault("deliverables", [])
        data.setdefault("decisions", [])
        data.setdefault("observations", [])
        data["integrity_hash"] = _compute_integrity(data)
        return data

    return locked_read_modify_write(path, updater)


# ── Auto-close & Stale Detection ─────────────────────────────────────────────

def close_all_open(
    context_repo: str = None,
    author: str = "session-hook",
    stale_hours: float = 0,
) -> list:
    """Close all open sessions in the workspace.

    If stale_hours > 0, only close sessions inactive for longer than that.
    Returns list of closed session names.

    This is the function called by:
      - SessionEnd hook (stale_hours=0, closes everything)
      - Heartbeat cron (stale_hours=N, closes only stale)
    """
    ctx = _resolve_ctx(context_repo)
    sessions_dir = ctx / "sessions"
    if not sessions_dir.is_dir():
        return []

    closed = []
    now = datetime.now(timezone.utc)

    for f in sorted(sessions_dir.glob("*.seif")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue

        if data.get("status") != "OPEN":
            continue

        # Stale check: skip if session is still fresh
        if stale_hours > 0:
            updated = data.get("updated_at") or data.get("created_at", "")
            try:
                last_activity = datetime.fromisoformat(updated)
                age_hours = (now - last_activity).total_seconds() / 3600
                if age_hours < stale_hours:
                    continue
            except (ValueError, TypeError):
                pass  # Can't parse timestamp — treat as stale

        name = data.get("name", f.stem)
        try:
            close_session(str(ctx), name, author=author)
            closed.append(name)
        except Exception:
            # If close fails, at least mark as interrupted
            try:
                update_session_status(str(ctx), name, "INTERRUPTED", author)
            except Exception:
                pass

    return closed


def close_stale(
    context_repo: str = None,
    timeout_hours: float = 4.0,
    author: str = "heartbeat",
) -> list:
    """Close sessions that have been inactive for longer than timeout_hours.

    Called by cron/heartbeat as a safety net.
    """
    return close_all_open(
        context_repo=context_repo,
        author=author,
        stale_hours=timeout_hours,
    )


# ── Convenience aliases ──────────────────────────────────────────────────────

def find_context_repo(start: str = ".") -> Optional[str]:
    """Walk up from start until a .seif/ directory is found.

    This is the canonical implementation — other modules that need
    find_context_repo should import from here.
    """
    current = Path(start).resolve()
    for _ in range(20):
        for candidate_name in (".seif", "seif-context"):
            candidate = current / candidate_name
            if candidate.is_dir():
                markers = ["mapper.json", "config.json", "manifest.json",
                           "RESONANCE.json", "cycles", "memory_state.json",
                           "modules", "sessions"]
                if any((candidate / m).exists() for m in markers):
                    return str(candidate)
        if current.parent == current:
            break
        current = current.parent
    return None
