#!/usr/bin/env python3
"""
SEIF Circuit Monitor — mid-session circuit visibility for AI writers.

Queries circuitd /events endpoint, compares with last known state,
and outputs alerts when circuit stability degrades.

Designed for:
  - Background polling (every 30s from session-start.sh)
  - Direct invocation by the AI to check circuit health
  - Hook integration (PreToolUse / PostToolUse)

Execution budget: <1 second (single HTTP GET + file compare).
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────

CIRCUIT_URL = "http://127.0.0.1:7333"
SEIF_HOME = Path.home() / ".seif"
CIRCUIT_DIR = SEIF_HOME / "circuit"
MONITOR_STATE_FILE = CIRCUIT_DIR / "monitor-state.json"
ALERTS_FILE = CIRCUIT_DIR / "alerts.txt"

# Models affected when circuit goes down (remote delegation targets)
REMOTE_MODELS = [
    "OpenCode (Mini M4)",
    "Copilot (Mini M4)",
    "Ollama (Mini M4)",
]


def _http_get(url: str, timeout: float = 2) -> dict | None:
    """Quick HTTP GET, returns parsed JSON or None."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _load_last_state() -> dict:
    """Load last known monitor state from disk."""
    if MONITOR_STATE_FILE.exists():
        try:
            return json.loads(MONITOR_STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: dict):
    """Persist current monitor state."""
    CIRCUIT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        MONITOR_STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def _append_alert(message: str):
    """Append alert to alerts file (for background mode)."""
    CIRCUIT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with ALERTS_FILE.open("a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _format_alert(prev_stability: str, curr_stability: str,
                  events: list, current: dict) -> str:
    """Format a human-readable alert for the AI writer."""
    lines = []

    # Header
    lines.append(f"[CIRCUIT ALERT] Stability changed: {prev_stability} -> {curr_stability}")

    # Show latest event detail
    if events:
        last = events[-1]
        from_t = last.get("from", "?")
        to_t = last.get("to", "?")
        reason = last.get("reason", "?")
        lines.append(f"  Transport: {from_t} -> {to_t} ({reason})")

    # Impact assessment
    if curr_stability == "disconnected":
        lines.append("  Impact: Remote model delegation UNAVAILABLE. Local models only.")
        affected = ", ".join(REMOTE_MODELS)
        lines.append(f"  Affected: {affected}")
    elif curr_stability == "degraded":
        transport = current.get("transport", "?")
        lines.append(f"  Impact: Connected via {transport} — may be unstable.")
        lines.append("  Recommendation: Prefer local operations, avoid large file transfers.")
    elif curr_stability == "stable":
        lines.append("  Circuit recovered. Full delegation capability restored.")

    return "\n".join(lines)


def monitor(quiet: bool = False) -> int:
    """
    Main monitor function.

    Returns:
        0 — no change
        1 — stability changed (alert emitted)
        2 — circuitd unreachable
    """
    # Query events endpoint
    data = _http_get(f"{CIRCUIT_URL}/events")

    if data is None:
        # circuitd not running — check if this is a new condition
        prev = _load_last_state()
        if prev.get("circuitd_reachable", True):
            msg = "[CIRCUIT ALERT] circuitd not reachable at 127.0.0.1:7333 — circuit monitoring offline"
            if not quiet:
                print(msg, file=sys.stderr)
            _append_alert(msg)
            _save_state({
                "circuitd_reachable": False,
                "session_stability": "disconnected",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            })
            return 2
        return 0

    # Extract current state
    curr_stability = data.get("session_stability", "disconnected")
    current = data.get("current", {})
    events = data.get("events", [])
    changes_count = data.get("changes_since_session", 0)

    # Load previous state
    prev = _load_last_state()
    prev_stability = prev.get("session_stability", None)
    prev_changes = prev.get("changes_since_session", 0)

    # Save current state
    _save_state({
        "circuitd_reachable": True,
        "session_stability": curr_stability,
        "connected": current.get("connected", False),
        "transport": current.get("transport", "?"),
        "changes_since_session": changes_count,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })

    # Detect change
    if prev_stability is not None and curr_stability != prev_stability:
        alert = _format_alert(prev_stability, curr_stability, events, current)
        if not quiet:
            print(alert)
        _append_alert(alert)
        return 1

    # Also detect new events even if stability label didn't change
    if changes_count > prev_changes and not quiet:
        new_events = events[-(changes_count - prev_changes):]
        for ev in new_events:
            print(f"[CIRCUIT] {ev['from']} -> {ev['to']} ({ev['reason']})")

    return 0


def status():
    """Print current circuit status (for direct invocation by AI)."""
    data = _http_get(f"{CIRCUIT_URL}/events")
    if data is None:
        print("[CIRCUIT STATUS] circuitd not reachable")
        return

    stability = data.get("session_stability", "?")
    current = data.get("current", {})
    changes = data.get("changes_since_session", 0)
    events = data.get("events", [])

    print(f"[CIRCUIT STATUS] {stability.upper()}")
    print(f"  Connected: {current.get('connected', False)}")
    print(f"  Transport: {current.get('transport', '?')}")
    print(f"  Changes this session: {changes}")

    if events:
        print(f"  Last event: {events[-1].get('from')} -> {events[-1].get('to')} ({events[-1].get('reason')})")
        print(f"  Last event at: {events[-1].get('timestamp', '?')}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SEIF Circuit Monitor")
    parser.add_argument("--status", action="store_true", help="Print full status")
    parser.add_argument("--quiet", action="store_true", help="Only write to alerts file")
    parser.add_argument("--clear-alerts", action="store_true", help="Clear alerts file")
    args = parser.parse_args()

    if args.clear_alerts:
        if ALERTS_FILE.exists():
            ALERTS_FILE.unlink()
            print("Alerts cleared.")
        return

    if args.status:
        status()
        return

    exit_code = monitor(quiet=args.quiet)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
