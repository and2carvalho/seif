"""
SEIF Handoff Bus — real-time message channel between instances on the same machine.

Problem: Two AI instances (writer + observer) communicate via the human as relay.
The human becomes a message bus instead of a decision-maker.

Solution: A shared JSON file in .seif/sessions/ where instances post and read
messages asynchronously. Uses locked_read_modify_write for concurrency safety.

Flow:
  Before: Writer ←→ Human ←→ Observer  (human is relay)
  After:  Writer ←→ .seif/handoff ←→ Observer  (human decides, not relays)

Gap fixes (session-16 circuit analysis):
  Gap 1 (Pull-only): Signal file touched on every post_message.
         Instances check signal mtime to know when to poll.
  Gap 2 (Overload):  Participant status tracking (task, load).
         Machines declare what they're working on.
  Gap 3 (No self-report): Heartbeat with last_alive + status.
         Silence is detectable. Overload is measurable.

Usage:
  from seif.context.handoff import (
      create_bus, post_message, read_messages,
      heartbeat, update_status, check_participants, has_new_messages,
  )

  # Create the bus (once per session)
  create_bus(context_repo, session_name="session-16", author="observer")

  # Post a message (touches signal file automatically)
  post_message(context_repo, "session-16", role="observer",
               author="claude-opus-4-6", content="mapper healed: 8 fixes")

  # Check if there are new messages (lightweight — reads signal file mtime)
  if has_new_messages(context_repo, "session-16", since_timestamp):
      messages = read_messages(context_repo, "session-16", since_id=last_id)

  # Heartbeat (call periodically to declare alive + current task)
  heartbeat(context_repo, "session-16", participant_id="claude-observer",
            task="measuring mapper health", load=0.3)

  # Check who is alive, overloaded, or silent
  participants = check_participants(context_repo, "session-16", stale_seconds=300)
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from seif.context.seif_io import atomic_write_json, locked_read_modify_write


def _bus_path(context_repo: str, session_name: str) -> Path:
    d = Path(context_repo) / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{session_name}-handoff.json"


def _signal_path(context_repo: str, session_name: str) -> Path:
    """Signal file — touched on every post. Instances check mtime for new messages."""
    return _bus_path(context_repo, session_name).with_suffix(".signal")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _touch_signal(context_repo: str, session_name: str) -> None:
    """Touch the signal file to notify other instances of new messages."""
    sig = _signal_path(context_repo, session_name)
    sig.parent.mkdir(parents=True, exist_ok=True)
    sig.touch()


def create_bus(
    context_repo: str,
    session_name: str,
    author: str,
    participants: list[dict] | None = None,
) -> Path:
    """Create a handoff bus for a session."""
    path = _bus_path(context_repo, session_name)

    if path.exists():
        raise FileExistsError(f"Handoff bus already exists: {path}")

    now = _now()
    bus = {
        "protocol": "SEIF-HANDOFF-v1",
        "session": session_name,
        "created_at": now,
        "participants": participants or [],
        "messages": [],
        "message_count": 0,
        "integrity_hash": _compute_hash(f"{session_name}-{now}"),
    }

    atomic_write_json(path, bus)
    return path


def post_message(
    context_repo: str,
    session_name: str,
    role: str,
    author: str,
    content: str,
    metadata: dict | None = None,
) -> dict:
    """Post a message to the handoff bus. Returns the updated bus."""
    path = _bus_path(context_repo, session_name)

    if not path.exists():
        raise FileNotFoundError(f"Handoff bus not found: {path}")

    now = _now()

    def updater(data):
        msg = {
            "id": data["message_count"] + 1,
            "role": role,
            "author": author,
            "at": now,
            "content": content,
            "hash": _compute_hash(content),
        }
        if metadata:
            msg["metadata"] = metadata

        data["messages"].append(msg)
        data["message_count"] += 1
        data["integrity_hash"] = _compute_hash(
            json.dumps(data["messages"], ensure_ascii=False)
        )
        return data

    result = locked_read_modify_write(str(path), updater)
    _touch_signal(context_repo, session_name)
    return result


def read_messages(
    context_repo: str,
    session_name: str,
    since_id: int = 0,
    role_filter: str | None = None,
) -> list[dict]:
    """Read messages from the handoff bus.

    Args:
        since_id: Only return messages with id > since_id (for polling).
        role_filter: Only return messages from this role.
    """
    path = _bus_path(context_repo, session_name)

    if not path.exists():
        return []

    data = json.loads(path.read_text())
    messages = data.get("messages", [])

    if since_id > 0:
        messages = [m for m in messages if m.get("id", 0) > since_id]

    if role_filter:
        messages = [m for m in messages if m.get("role") == role_filter]

    return messages


def bus_status(context_repo: str, session_name: str) -> dict:
    """Get bus status summary."""
    path = _bus_path(context_repo, session_name)

    if not path.exists():
        return {"exists": False}

    data = json.loads(path.read_text())
    messages = data.get("messages", [])
    roles = {}
    for m in messages:
        r = m.get("role", "unknown")
        roles[r] = roles.get(r, 0) + 1

    # Include participant statuses in bus_status
    statuses = data.get("participant_status", {})

    return {
        "exists": True,
        "session": session_name,
        "message_count": data.get("message_count", 0),
        "messages_by_role": roles,
        "participants": data.get("participants", []),
        "participant_status": statuses,
        "integrity_hash": data.get("integrity_hash", ""),
        "last_message_at": messages[-1]["at"] if messages else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Gap 1: Signal file — lightweight new-message detection
# ═══════════════════════════════════════════════════════════════════════════


def has_new_messages(
    context_repo: str,
    session_name: str,
    since_timestamp: float,
) -> bool:
    """Check if the bus has new messages since a given timestamp.

    Uses the signal file mtime — no JSON parsing needed.
    Instances call this cheaply to decide whether to poll read_messages().

    Args:
        since_timestamp: Unix timestamp (e.g. from time.time()).
    """
    sig = _signal_path(context_repo, session_name)
    if not sig.exists():
        return False
    return sig.stat().st_mtime > since_timestamp


# ═══════════════════════════════════════════════════════════════════════════
# Gap 2+3: Participant status + heartbeat
# ═══════════════════════════════════════════════════════════════════════════


def heartbeat(
    context_repo: str,
    session_name: str,
    participant_id: str,
    task: str = "",
    load: float = 0.0,
) -> dict:
    """Update participant heartbeat — declares alive, current task, and load.

    Call periodically (e.g. at start/end of each task) to let other
    instances know you are active and what you are working on.

    Args:
        participant_id: Unique ID of this instance.
        task: Short description of current task (empty = idle).
        load: Self-assessed load 0.0-1.0 (0=idle, 1=overloaded).
    """
    path = _bus_path(context_repo, session_name)

    if not path.exists():
        raise FileNotFoundError(f"Handoff bus not found: {path}")

    now = _now()

    def updater(data):
        statuses = data.setdefault("participant_status", {})
        statuses[participant_id] = {
            "last_alive": now,
            "task": task,
            "load": max(0.0, min(1.0, load)),
            "alive_epoch": time.time(),
        }
        return data

    return locked_read_modify_write(str(path), updater)


def update_status(
    context_repo: str,
    session_name: str,
    participant_id: str,
    task: str = "",
    load: float = 0.0,
) -> dict:
    """Alias for heartbeat — semantically clearer for explicit status updates."""
    return heartbeat(context_repo, session_name, participant_id, task, load)


def check_participants(
    context_repo: str,
    session_name: str,
    stale_seconds: float = 300.0,
) -> list[dict]:
    """Check participant health. Returns list with alive/stale/overloaded status.

    Args:
        stale_seconds: Seconds without heartbeat before a participant is stale.
    """
    path = _bus_path(context_repo, session_name)

    if not path.exists():
        return []

    data = json.loads(path.read_text())
    statuses = data.get("participant_status", {})
    participants = data.get("participants", [])
    now_epoch = time.time()

    result = []
    for p in participants:
        pid = p.get("id", "")
        status = statuses.get(pid)

        if status is None:
            result.append({
                "id": pid,
                "role": p.get("role", "unknown"),
                "health": "unknown",
                "reason": "no heartbeat received",
            })
        else:
            age = now_epoch - status.get("alive_epoch", 0)
            load = status.get("load", 0)
            task = status.get("task", "")

            if age > stale_seconds:
                health = "stale"
                reason = f"no heartbeat for {age:.0f}s (threshold: {stale_seconds:.0f}s)"
            elif load >= 0.8:
                health = "overloaded"
                reason = f"load={load:.1f}, task='{task}'"
            elif load >= 0.5:
                health = "busy"
                reason = f"load={load:.1f}, task='{task}'"
            else:
                health = "available"
                reason = f"load={load:.1f}" + (f", task='{task}'" if task else "")

            result.append({
                "id": pid,
                "role": p.get("role", "unknown"),
                "health": health,
                "last_alive": status.get("last_alive", ""),
                "task": task,
                "load": load,
                "age_seconds": round(age, 1),
                "reason": reason,
            })

    return result
