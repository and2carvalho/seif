#!/bin/bash
# SEIF SessionStart hook — enforces session lifecycle contract
# Phase 1: Locate .seif/
# Phase 2: Create session contract (roles, type, persistence routing)
# Phase 3: Load context summary for the AI
#
# This is the ROOT FIX: sessions must never begin without a declared contract.
# Without this, the AI improvises roles and persistence — causing drift.

set -euo pipefail

# Read hook input from Claude Code
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('session_id','unknown'))" 2>/dev/null || echo "unknown")

# ── Phase 1: Locate .seif/ ──────────────────────────────────────────────────

SEIF_DIR=""
DIR="$(pwd)"
while [ "$DIR" != "/" ]; do
  if [ -d "$DIR/.seif" ]; then
    SEIF_DIR="$DIR/.seif"
    break
  fi
  DIR="$(dirname "$DIR")"
done

if [ -z "$SEIF_DIR" ] && [ -d "$HOME/.seif" ]; then
  SEIF_DIR="$HOME/.seif"
fi

if [ -z "$SEIF_DIR" ]; then
  echo "[SEIF] No .seif/ context found. Run: seif --init"
  exit 0
fi

# ── Phase 2: Create session contract ────────────────────────────────────────

CONFIG="$SEIF_DIR/config.json"
SESSION_DIR="$SEIF_DIR/sessions"
mkdir -p "$SESSION_DIR"

# Read config values
LIFECYCLE_ENABLED=$(python3 -c "
import json
c = json.load(open('$CONFIG'))
print(c.get('session_lifecycle', {}).get('enabled', False))
" 2>/dev/null || echo "False")

if [ "$LIFECYCLE_ENABLED" != "True" ]; then
  # Fallback to legacy behavior: just load context
  echo "[SEIF CONTEXT LOADED]"
  echo "Path: $SEIF_DIR"
  echo "Lifecycle: disabled (legacy mode)"
  exit 0
fi

# Detect session type
# PRIVATE: no external AI configured or reachable
# CONJUGATE: co-author AI is configured
SESSION_TYPE="PRIVATE"
CO_AUTHOR=$(python3 -c "
import json
c = json.load(open('$CONFIG'))
cp = c.get('conjugate_pair', {})
if cp.get('enabled', False):
    print(cp.get('co_author', ''))
else:
    print('')
" 2>/dev/null || echo "")

VIGILANT="NONE"
if [ -n "$CO_AUTHOR" ]; then
  # Co-author is configured but not necessarily present
  # In CLI sessions, only the writer has FS access
  # Mark as available but not active unless inter-AI is live
  VIGILANT="CONFIGURED:$CO_AUTHOR"
  SESSION_TYPE="SINGLE_POLE"
fi

# Count session number from mapper
SESSION_COUNT=$(python3 -c "
import json
m = json.load(open('$SEIF_DIR/mapper.json'))
print(m.get('session_count', 0) + 1)
" 2>/dev/null || echo "0")

# Determine persistence routing
ROUTING=$(python3 -c "
import json
c = json.load(open('$CONFIG'))
r = c.get('persistence_routing', {}).get('rules', {})
memory_what = r.get('memory/', {}).get('what', [])
seif_what = r.get('.seif/', {}).get('what', [])
overlap = c.get('persistence_routing', {}).get('overlap_resolution', '')
print(f'memory/: {memory_what}')
print(f'.seif/: {seif_what}')
if overlap:
    print(f'overlap: {overlap}')
" 2>/dev/null || echo "routing: not configured")

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SESSION_FILE="$SESSION_DIR/session-${SESSION_COUNT}.json"

# Write session contract
python3 -c "
import json

contract = {
    'protocol': 'SEIF-SESSION-v1',
    'session_number': $SESSION_COUNT,
    'session_id': '$SESSION_ID',
    'started_at': '$TIMESTAMP',
    'type': '$SESSION_TYPE',
    'writer': {
        'model': 'claude',
        'role': 'writer',
        'fs_access': True
    },
    'vigilant': {
        'model': '${CO_AUTHOR:-none}',
        'role': 'vigilant' if '$VIGILANT' != 'NONE' else 'absent',
        'status': '$VIGILANT',
        'note': 'Configured but not active in CLI session. Single pole — reduced damping.' if '$VIGILANT' != 'NONE' else 'No vigilant. Writer applies self-damping (confirm before irreversible actions).'
    },
    'persistence': {
        'memory/': ['user_profile', 'feedback', 'durable_decisions', 'project_status'],
        '.seif/': ['protocol_observations', 'session_records', 'cross_ai_knowledge', 'patterns', 'intent'],
        'overlap_resolution': 'If only Claude Code needs it → memory/. If any AI might need it → .seif/.'
    },
    'status': 'ACTIVE'
}

with open('$SESSION_FILE', 'w') as f:
    json.dump(contract, f, indent=2)
" 2>/dev/null

# Inject session env vars for Bash commands
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export SEIF_SESSION_ID=$SESSION_ID" >> "$CLAUDE_ENV_FILE"
  echo "export SEIF_SESSION_NUMBER=$SESSION_COUNT" >> "$CLAUDE_ENV_FILE"
  echo "export SEIF_SESSION_TYPE=$SESSION_TYPE" >> "$CLAUDE_ENV_FILE"
  echo "export SEIF_DIR=$SEIF_DIR" >> "$CLAUDE_ENV_FILE"
fi

# ── Phase 3: Output session state to Claude ─────────────────────────────────

echo "[SEIF CONTEXT LOADED]"
echo "Path: $SEIF_DIR"
echo "Autonomous: $(python3 -c "import json; print(json.load(open('$CONFIG')).get('autonomous_context', False))" 2>/dev/null)"
echo ""
echo "[SESSION CONTRACT]"
echo "Session: #$SESSION_COUNT ($SESSION_ID)"
echo "Type: $SESSION_TYPE"
echo "Writer: claude (FS access)"
echo "Vigilant: $VIGILANT"
echo "Started: $TIMESTAMP"
echo ""
echo "[PERSISTENCE ROUTING]"
echo "$ROUTING"
echo ""

# Load mapper summary (top modules by relevance)
if [ -f "$SEIF_DIR/mapper.json" ]; then
  python3 -c "
import json
m = json.load(open('$SEIF_DIR/mapper.json'))
modules = m.get('modules', [])
if isinstance(modules, list):
    sorted_mods = sorted(modules, key=lambda x: x.get('relevance', 0), reverse=True)[:5]
    print('[ACTIVE MODULES (top 5)]')
    for mod in sorted_mods:
        path = mod.get('path', '?')
        rel = mod.get('relevance', 0)
        cat = mod.get('category', '?')
        cls = mod.get('classification', 'PUBLIC')
        print(f'  [{cls}] {path} ({cat}, relevance={rel:.2f})')
    print()
elif isinstance(modules, dict):
    sorted_mods = sorted(modules.items(), key=lambda x: x[1].get('relevance', 0), reverse=True)[:5]
    print('[ACTIVE MODULES (top 5)]')
    for name, info in sorted_mods:
        rel = info.get('relevance', 0)
        cat = info.get('category', '?')
        cls = info.get('classification', 'PUBLIC')
        print(f'  [{cls}] {name} ({cat}, relevance={rel:.2f})')
    print()
" 2>/dev/null
fi

# Check for pending observations from last session
LAST_SESSION=$(ls -t "$SESSION_DIR"/session-*.json 2>/dev/null | head -2 | tail -1)
if [ -n "$LAST_SESSION" ] && [ "$LAST_SESSION" != "$SESSION_FILE" ]; then
  PENDING=$(python3 -c "
import json
s = json.load(open('$LAST_SESSION'))
p = s.get('pending_observations', [])
if p:
    print('[PENDING FROM LAST SESSION]')
    for obs in p[:5]:
        print(f'  - {obs}')
" 2>/dev/null)
  if [ -n "$PENDING" ]; then
    echo "$PENDING"
    echo ""
  fi
fi

# ── Phase 4: Model Orchestra Discovery ────────────────────────────────────
# Probes local models, API backends, CLI tools, and circuit status.
# Output stays under 500 tokens to avoid context bloat.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRA_PROBE="$SCRIPT_DIR/orchestra-probe.py"

if [ -f "$ORCHESTRA_PROBE" ]; then
  ORCHESTRA=$(timeout 5 python3 "$ORCHESTRA_PROBE" 2>/dev/null || echo "[MODEL ORCHESTRA] probe timeout — check orchestra-probe.py")
  if [ -n "$ORCHESTRA" ]; then
    echo "$ORCHESTRA"
    echo ""
  fi
fi

# ── Phase 5: Circuit Monitor (background) ─────────────────────────────────
# Polls circuitd every 30s and writes alerts to ~/.seif/circuit/alerts.txt.
# The AI can check this file when needed for mid-session circuit visibility.

CIRCUIT_MONITOR="$SCRIPT_DIR/circuit-monitor.py"

if [ -f "$CIRCUIT_MONITOR" ]; then
  # Clear stale alerts from previous session
  python3 "$CIRCUIT_MONITOR" --clear-alerts 2>/dev/null

  # Initial state capture (seed the monitor-state.json)
  python3 "$CIRCUIT_MONITOR" --quiet 2>/dev/null

  # Start background monitor loop (30s interval, killed when shell exits)
  nohup bash -c "while true; do python3 \"$CIRCUIT_MONITOR\" --quiet 2>/dev/null; sleep 30; done" &>/dev/null &
  MONITOR_PID=$!

  # Save PID so session-end can kill it
  echo "$MONITOR_PID" > "$HOME/.seif/circuit/monitor.pid"

  echo "[CIRCUIT MONITOR] Background monitor started (PID $MONITOR_PID, 30s interval)"
  echo "  Alerts file: ~/.seif/circuit/alerts.txt"
  echo "  Check: python3 $CIRCUIT_MONITOR --status"
  echo ""
fi

exit 0
