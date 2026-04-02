"""
SEIF Shared Sessions — async multi-party context accumulation.

A session is a .seif module in .seif/sessions/ where multiple participants
(humans + AIs) contribute asynchronously with full provenance.

v1: create → contribute → close. No real-time, no server.
v2: participants[], sync_points[], auto-sync (mesh topology).

Uses existing primitives: locked_read_modify_write, contributors[], integrity_hash.
"""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from seif.constants import (
    SESSION_SYNC_THRESHOLD,
    SESSION_PROTOCOL_V2,
    CHANNEL_FILESYSTEM,
    ROLE_WRITER,
    ROLE_CONTRIBUTOR,
)
from seif.context.seif_io import atomic_write_json, locked_read_modify_write


def _sessions_dir(context_repo: str) -> Path:
    d = Path(context_repo) / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def create_session(
    context_repo: str,
    name: str,
    author: str,
    purpose: str = "",
    writer: str = "claude-opus-4-6",
) -> Path:
    """Create a new shared session."""
    sessions_dir = _sessions_dir(context_repo)
    path = sessions_dir / f"{name}.seif"

    if path.exists():
        raise FileExistsError(f"Session '{name}' already exists: {path}")

    now = datetime.now(timezone.utc).isoformat()
    summary = f"## Session: {name}\nCreated: {now}\nPurpose: {purpose or 'collaborative session'}\n\n### Contributions\n"

    module = {
        "_instruction": (
            "This is a SEIF shared session. Multiple participants contribute "
            "asynchronously. Read 'summary' for accumulated context. "
            "Protocol: github.com/and2carvalho/seif"
        ),
        "protocol": "SEIF-SESSION-v1",
        "source": f"session/{name}",
        "session_name": name,
        "writer": writer,
        "status": "OPEN",
        "summary": summary,
        "verified_data": [],
        "integrity_hash": _compute_hash(summary),
        "active": True,
        "version": 1,
        "contributors": [
            {
                "author": author,
                "at": now,
                "via": "session-create",
                "action": "created",
            }
        ],
        "parent_hash": None,
        "updated_at": now,
        "classification": "INTERNAL",
    }

    atomic_write_json(path, module)
    return path


def contribute_to_session(
    context_repo: str,
    name: str,
    message: str,
    author: str,
    via: str = "cli",
    action: str = "contributed",
) -> dict:
    """Add a contribution to an open session."""
    path = _sessions_dir(context_repo) / f"{name}.seif"

    if not path.exists():
        raise FileNotFoundError(f"Session '{name}' not found: {path}")

    now = datetime.now(timezone.utc).isoformat()

    def updater(data):
        if data.get("status") != "OPEN":
            raise ValueError(f"Session '{name}' is {data.get('status')}, not OPEN")

        # Append contribution to summary
        contribution = f"\n**{author}** ({now[:16]}, via {via}):\n{message}\n"
        data["summary"] += contribution

        # Update metadata
        data["parent_hash"] = data["integrity_hash"]
        data["integrity_hash"] = _compute_hash(data["summary"])
        data["version"] = data.get("version", 1) + 1
        data["updated_at"] = now

        # Add contributor
        data.setdefault("contributors", []).append({
            "author": author,
            "at": now,
            "via": via,
            "action": action,
        })

        # Add to verified_data if factual
        if len(message) < 200:
            data.setdefault("verified_data", []).append(
                f"{author}: {message[:100]}"
            )

        return data

    result = locked_read_modify_write(str(path), updater)
    return result


def close_session(
    context_repo: str,
    name: str,
    author: str,
) -> Path:
    """Close session: finalize, audit, and archive."""
    sessions_dir = _sessions_dir(context_repo)
    path = sessions_dir / f"{name}.seif"

    if not path.exists():
        raise FileNotFoundError(f"Session '{name}' not found: {path}")

    now = datetime.now(timezone.utc).isoformat()

    def updater(data):
        if data.get("status") != "OPEN":
            raise ValueError(f"Session '{name}' is already {data.get('status')}")

        data["status"] = "CLOSED"
        data["summary"] += f"\n---\n**Session closed** by {author} at {now[:16]}\n"
        data["parent_hash"] = data["integrity_hash"]
        data["integrity_hash"] = _compute_hash(data["summary"])
        data["version"] = data.get("version", 1) + 1
        data["updated_at"] = now
        data.setdefault("contributors", []).append({
            "author": author,
            "at": now,
            "via": "session-close",
            "action": "closed",
        })
        return data

    locked_read_modify_write(str(path), updater)

    # Archive: copy to projects if it exists
    archive_dir = Path(context_repo) / "projects" / "seif"
    if archive_dir.exists():
        archive_path = archive_dir / f"session-{name}.seif"
        shutil.copy2(path, archive_path)

    return path


def list_sessions(context_repo: str) -> list[dict]:
    """List all sessions with status."""
    sessions_dir = _sessions_dir(context_repo)
    sessions = []
    for p in sorted(sessions_dir.glob("*.seif")):
        try:
            data = json.loads(p.read_text())
            contributors = data.get("contributors", [])
            unique_authors = len(set(c.get("author", "") for c in contributors))
            sessions.append({
                "name": data.get("session_name", p.stem),
                "status": data.get("status", "UNKNOWN"),
                "version": data.get("version", 1),
                "contributors": unique_authors,
                "updated": data.get("updated_at", "?")[:16],
                "path": str(p),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return sessions


def session_log(context_repo: str, name: str) -> str:
    """Generate human-readable markdown log of session."""
    path = _sessions_dir(context_repo) / f"{name}.seif"
    if not path.exists():
        return f"Session '{name}' not found."

    data = json.loads(path.read_text())
    contributors = data.get("contributors", [])
    unique = sorted(set(c.get("author", "") for c in contributors))
    status = data.get("status", "?")
    version = data.get("version", 1)
    classification = data.get("classification", "?")
    created = data.get("contributors", [{}])[0].get("at", "?")[:16]

    writer = data.get("writer", "unassigned")
    lines = [
        f"# Session: {name}",
        "",
        f"**Status:** {status} | **Version:** {version} | **Classification:** {classification}",
        f"**Created:** {created} | **Writer:** {writer}",
        f"**Participants:** {', '.join(unique)}",
        f"**Hash:** `{data.get('integrity_hash', '?')}`",
        "",
        "---",
        "",
    ]

    # Parse contributions from summary
    summary = data.get("summary", "")
    for line in summary.split("\n"):
        stripped = line.strip()
        if stripped.startswith("**") and "via" in stripped:
            # Contribution header — format as markdown heading
            lines.append(f"### {stripped}")
        elif stripped.startswith("---"):
            lines.append("")
            lines.append("---")
            lines.append("")
        elif stripped:
            lines.append(stripped)
        else:
            lines.append("")

    # Hash corrections log
    corrections = [
        c for c in contributors
        if c.get("action") == "hash-corrected"
    ]
    if corrections:
        lines.extend(["", "## Hash Corrections", ""])
        for c in corrections:
            lines.append(
                f"- `{c.get('original_hash', '?')}` → `{c.get('corrected_hash', '?')}` "
                f"(by {c.get('author', '?')} at {c.get('at', '?')[:16]})"
            )

    # Provenance summary
    lines.extend(["", "## Provenance", ""])
    for c in contributors:
        action = c.get("action", "?")
        icon = {"created": "+", "contributed": "→", "directed": "◆",
                "closed": "×", "hash-corrected": "⚠"}.get(action, "·")
        lines.append(
            f"- {icon} **{c.get('author', '?')}** [{action}] "
            f"({c.get('at', '?')[:16]}, via {c.get('via', '?')})"
        )

    return "\n".join(lines)


def verify_and_contribute(
    context_repo: str,
    name: str,
    message: str,
    author: str,
    claimed_hash: str = None,
    via: str = "cli",
    action: str = "contributed",
) -> tuple[dict, str]:
    """Contribute with hash verification. Returns (result, alert_message)."""
    alert = ""

    # If a hash was claimed, verify it
    if claimed_hash:
        actual = _compute_hash(message)
        if claimed_hash != actual:
            alert = (
                f"[HASH FIX] Export de {author}: claimed {claimed_hash}, "
                f"actual {actual}. Corrigido automaticamente."
            )

    result = contribute_to_session(context_repo, name, message, author, via, action)

    # Log hash correction in contributors if needed
    if alert:
        path = _sessions_dir(context_repo) / f"{name}.seif"

        def add_correction(data):
            data.setdefault("contributors", []).append({
                "author": "seif-hash-verifier",
                "at": datetime.now(timezone.utc).isoformat(),
                "via": "auto-verification",
                "action": "hash-corrected",
                "original_hash": claimed_hash,
                "corrected_hash": _compute_hash(message),
            })
            return data

        locked_read_modify_write(str(path), add_correction)

    return result, alert


def describe_session(context_repo: str, name: str) -> str:
    """Get full session content."""
    path = _sessions_dir(context_repo) / f"{name}.seif"
    if not path.exists():
        return f"Session '{name}' not found."
    data = json.loads(path.read_text())
    contributors = data.get("contributors", [])
    unique = set(c.get("author", "") for c in contributors)
    lines = [
        f"Session: {name} [{data.get('status', '?')}]",
        f"Version: {data.get('version', 1)} | Contributors: {len(unique)} | Hash: {data.get('integrity_hash', '?')}",
        f"Classification: {data.get('classification', '?')}",
        "",
        data.get("summary", "(empty)"),
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# SEIF-SESSION-v2 — Multi-machine mesh orchestration
# ═══════════════════════════════════════════════════════════════════════════


def create_session_v2(
    context_repo: str,
    name: str,
    author: str,
    purpose: str = "",
    writer: str = "claude-opus-4-6",
    participants: list[dict] | None = None,
) -> Path:
    """Create a v2 session with participant topology and auto-sync.

    participants: list of {"id": str, "role": str, "channel": str}
    If not provided, writer is added as sole participant.
    """
    sessions_dir = _sessions_dir(context_repo)
    path = sessions_dir / f"{name}.seif"

    if path.exists():
        raise FileExistsError(f"Session '{name}' already exists: {path}")

    now = datetime.now(timezone.utc).isoformat()
    summary = (
        f"## Session: {name}\n"
        f"Created: {now}\n"
        f"Purpose: {purpose or 'multi-machine collaborative session'}\n"
        f"\n### Contributions\n"
    )

    if participants is None:
        participants = [
            {"id": writer, "role": ROLE_WRITER, "channel": CHANNEL_FILESYSTEM}
        ]

    module = {
        "_instruction": (
            "SEIF-SESSION-v2: multi-machine mesh session. "
            "Participants contribute via typed channels. "
            "Sync points consolidate divergent context. "
            "Protocol: github.com/and2carvalho/seif"
        ),
        "protocol": SESSION_PROTOCOL_V2,
        "source": f"session/{name}",
        "session_name": name,
        "writer": writer,
        "topology": "mesh",
        "status": "OPEN",
        "summary": summary,
        "verified_data": [],
        "integrity_hash": _compute_hash(summary),
        "active": True,
        "version": 1,
        "participants": participants,
        "sync_points": [],
        "divergence_log": [],
        "contributors": [
            {
                "author": author,
                "at": now,
                "via": "session-create",
                "action": "created",
            }
        ],
        "parent_hash": None,
        "updated_at": now,
        "classification": "INTERNAL",
    }

    atomic_write_json(path, module)
    return path


def add_participant(
    context_repo: str,
    name: str,
    participant_id: str,
    role: str = ROLE_CONTRIBUTOR,
    channel: str = CHANNEL_FILESYSTEM,
    author: str = "orchestrator",
) -> dict:
    """Register a participant in a v2 session."""
    path = _sessions_dir(context_repo) / f"{name}.seif"

    if not path.exists():
        raise FileNotFoundError(f"Session '{name}' not found: {path}")

    now = datetime.now(timezone.utc).isoformat()

    def updater(data):
        if data.get("status") != "OPEN":
            raise ValueError(f"Session '{name}' is {data.get('status')}, not OPEN")

        parts = data.setdefault("participants", [])
        existing_ids = {p["id"] for p in parts}
        if participant_id in existing_ids:
            raise ValueError(f"Participant '{participant_id}' already in session")

        parts.append({"id": participant_id, "role": role, "channel": channel})

        data.setdefault("contributors", []).append({
            "author": author,
            "at": now,
            "via": "session-add-participant",
            "action": f"added-participant:{participant_id}",
        })
        data["version"] = data.get("version", 1) + 1
        data["updated_at"] = now
        return data

    return locked_read_modify_write(str(path), updater)


def _count_unsynced(data: dict) -> int:
    """Count contributions since the last sync point."""
    sync_points = data.get("sync_points", [])
    contributors = data.get("contributors", [])

    if not sync_points:
        return sum(1 for c in contributors if c.get("action") == "contributed")

    last_sync_ts = sync_points[-1].get("at", "")
    return sum(
        1 for c in contributors
        if c.get("action") == "contributed" and c.get("at", "") > last_sync_ts
    )


def needs_sync(context_repo: str, name: str) -> tuple[bool, int]:
    """Check if session needs a sync point. Returns (needs_sync, unsynced_count)."""
    path = _sessions_dir(context_repo) / f"{name}.seif"
    if not path.exists():
        return False, 0

    data = json.loads(path.read_text())
    if data.get("status") != "OPEN":
        return False, 0

    unsynced = _count_unsynced(data)
    return unsynced >= SESSION_SYNC_THRESHOLD, unsynced


def create_sync_point(
    context_repo: str,
    name: str,
    author: str,
    digest: str = "",
) -> dict:
    """Create a sync point: snapshot of current state for all participants.

    The digest is a human/AI-written summary of what happened since last sync.
    If empty, auto-generated from recent contributions.
    """
    path = _sessions_dir(context_repo) / f"{name}.seif"

    if not path.exists():
        raise FileNotFoundError(f"Session '{name}' not found: {path}")

    now = datetime.now(timezone.utc).isoformat()

    def updater(data):
        if data.get("status") != "OPEN":
            raise ValueError(f"Session '{name}' is {data.get('status')}, not OPEN")

        # Auto-generate digest from recent contributions if empty
        auto_digest = digest
        if not auto_digest:
            sync_points = data.get("sync_points", [])
            last_sync_version = (
                sync_points[-1]["at_version"] if sync_points else 0
            )
            recent = [
                c for c in data.get("contributors", [])
                if c.get("action") == "contributed"
            ]
            # Only contributions after last sync
            if last_sync_version > 0:
                recent = recent[last_sync_version:]
            if recent:
                authors = sorted(set(c.get("author", "?") for c in recent))
                auto_digest = (
                    f"{len(recent)} contributions from {', '.join(authors)}"
                )
            else:
                auto_digest = "sync checkpoint (no new contributions)"

        sync_point = {
            "id": _compute_hash(f"{name}-{now}-{data.get('version', 1)}"),
            "at": now,
            "at_version": data.get("version", 1),
            "digest": auto_digest,
            "hash": data.get("integrity_hash", ""),
            "participants_snapshot": [
                p["id"] for p in data.get("participants", [])
            ],
            "author": author,
        }

        data.setdefault("sync_points", []).append(sync_point)

        # Mark in summary
        data["summary"] += (
            f"\n---\n**[SYNC #{len(data['sync_points'])}]** "
            f"by {author} at {now[:16]}\n"
            f"Digest: {auto_digest}\n"
            f"Hash: `{data.get('integrity_hash', '')}`\n---\n"
        )

        data["parent_hash"] = data["integrity_hash"]
        data["integrity_hash"] = _compute_hash(data["summary"])
        data["version"] = data.get("version", 1) + 1
        data["updated_at"] = now

        data.setdefault("contributors", []).append({
            "author": author,
            "at": now,
            "via": "session-sync",
            "action": "sync-point",
        })

        return data

    return locked_read_modify_write(str(path), updater)


def generate_sync_prompt(context_repo: str, name: str, target_id: str) -> str:
    """Generate a sync prompt for a specific participant.

    This produces a text block that can be sent to a participant
    via their channel (paste into Grok, send to Dia skill, etc.)
    to bring them up to speed with the current session state.
    """
    path = _sessions_dir(context_repo) / f"{name}.seif"
    if not path.exists():
        return f"Session '{name}' not found."

    data = json.loads(path.read_text())
    participants = data.get("participants", [])
    target = next((p for p in participants if p["id"] == target_id), None)

    if not target:
        return f"Participant '{target_id}' not in session '{name}'."

    sync_points = data.get("sync_points", [])
    last_sync = sync_points[-1] if sync_points else None

    lines = [
        f"[SEIF SESSION SYNC] {name}",
        f"Protocol: {data.get('protocol', 'SEIF-SESSION-v2')}",
        f"Version: {data.get('version', 1)} | Hash: {data.get('integrity_hash', '?')}",
        f"Your role: {target.get('role', '?')} | Channel: {target.get('channel', '?')}",
        "",
    ]

    if last_sync:
        lines.extend([
            f"## Last sync: #{len(sync_points)}",
            f"Digest: {last_sync.get('digest', '')}",
            f"Hash at sync: {last_sync.get('hash', '')}",
            "",
        ])

    # Include recent contributions since last sync (or all if no sync)
    last_version = last_sync["at_version"] if last_sync else 0
    recent_contribs = []
    for line in data.get("summary", "").split("\n"):
        stripped = line.strip()
        if stripped.startswith("**") and "via" in stripped:
            recent_contribs.append(stripped)

    if recent_contribs:
        # Show last N contributions (keep prompt manageable)
        show = recent_contribs[-6:]
        lines.append("## Recent contributions")
        lines.extend(show)
        lines.append("")

    # Participant roster
    lines.append("## Participants")
    for p in participants:
        marker = " (you)" if p["id"] == target_id else ""
        lines.append(f"  - {p['id']} [{p['role']}] via {p['channel']}{marker}")

    lines.extend([
        "",
        "## Expected response",
        "Contribute your observations/analysis as structured text.",
        "The writer will persist your contribution with full provenance.",
        f"Format: plain text or SEIF-MODULE-v2 JSON (if you prefer structured export).",
    ])

    return "\n".join(lines)


def contribute_with_sync_check(
    context_repo: str,
    name: str,
    message: str,
    author: str,
    via: str = "cli",
    action: str = "contributed",
    auto_sync_author: str = "orchestrator",
) -> tuple[dict, bool]:
    """Contribute and auto-create sync point if threshold reached.

    Returns (result, sync_created).
    """
    result = contribute_to_session(context_repo, name, message, author, via, action)

    should_sync, unsynced = needs_sync(context_repo, name)
    if should_sync:
        create_sync_point(context_repo, name, auto_sync_author)
        return result, True

    return result, False


def upgrade_to_v2(context_repo: str, name: str) -> dict:
    """Upgrade a v1 session to v2 (adds participants, sync_points, topology)."""
    path = _sessions_dir(context_repo) / f"{name}.seif"

    if not path.exists():
        raise FileNotFoundError(f"Session '{name}' not found: {path}")

    now = datetime.now(timezone.utc).isoformat()

    def updater(data):
        if data.get("protocol") == SESSION_PROTOCOL_V2:
            return data  # Already v2

        writer = data.get("writer", "claude-opus-4-6")
        data["protocol"] = SESSION_PROTOCOL_V2
        data["topology"] = "mesh"

        # Add writer as first participant
        participants = [
            {"id": writer, "role": ROLE_WRITER, "channel": CHANNEL_FILESYSTEM}
        ]
        seen = {writer}

        # Derive other participants from contributors
        for c in data.get("contributors", []):
            aid = c.get("author", "")
            if aid and aid not in seen:
                seen.add(aid)
                via = c.get("via", "cli")
                participants.append({"id": aid, "role": ROLE_CONTRIBUTOR, "channel": via})

        data["participants"] = participants
        data.setdefault("sync_points", [])
        data.setdefault("divergence_log", [])

        data.setdefault("contributors", []).append({
            "author": "seif-upgrade",
            "at": now,
            "via": "auto",
            "action": "upgraded-to-v2",
        })
        data["version"] = data.get("version", 1) + 1
        data["updated_at"] = now
        return data

    return locked_read_modify_write(str(path), updater)
