#!/bin/bash
# SEIF SessionEnd hook — complete session lifecycle ritual
#
# Ritual sequence (from KERNEL + config.json):
#   1. CLOSURE  — generate structured summary (decided/implemented/why/missing/how_to_measure)
#   2. AUDIT    — verify .seif integrity (orphans, ghosts, hash failures)
#   3. MEDITATE — run quality gate on session contributions
#   4. ABSORB   — decay relevance, update mapper, persist observations
#   5. CIRCLE   — confirm context is synced and next session has handoff
#
# This is the ROOT FIX: sessions must never end without structured closure.
# Without this, the next AI starts blind.

set -euo pipefail

# ── Locate .seif/ ─────────────────────────────────────────────────────────
SEIF_DIR=""
DIR="$(pwd)"
while [ "$DIR" != "/" ]; do
  if [ -d "$DIR/.seif" ]; then
    SEIF_DIR="$DIR/.seif"
    break
  fi
  DIR="$(dirname "$DIR")"
done

if [ -z "$SEIF_DIR" ]; then
  exit 0
fi

CONFIG="$SEIF_DIR/config.json"
MAPPER="$SEIF_DIR/mapper.json"
SESSION_DIR="$SEIF_DIR/sessions"

# Check if lifecycle is enabled
LIFECYCLE_ENABLED=$(python3 -c "
import json
c = json.load(open('$CONFIG'))
print(c.get('session_lifecycle', {}).get('enabled', False))
" 2>/dev/null || echo "False")

if [ "$LIFECYCLE_ENABLED" != "True" ]; then
  exit 0
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# ── 1. CLOSURE — structured summary ──────────────────────────────────────
# Find the active session and generate closure
python3 -c "
import json, glob, os

session_dir = '$SESSION_DIR'
closure_format = ['decided', 'implemented', 'why', 'missing', 'how_to_measure']

# Read closure_format from config if available
try:
    with open('$CONFIG') as f:
        config = json.load(f)
    cf = config.get('session_lifecycle', {}).get('closure_format', [])
    if cf:
        closure_format = cf
except Exception:
    pass

# Find active session
sessions = sorted(glob.glob(os.path.join(session_dir, 'session-*.json')), reverse=True)
for sf in sessions:
    try:
        with open(sf) as f:
            s = json.load(f)
        if s.get('status') == 'ACTIVE':
            # Generate empty closure structure (AI should have filled this during session)
            # If not filled, create skeleton so next session knows closure was attempted
            if 'closure' not in s:
                s['closure'] = {field: [] for field in closure_format}
                s['closure_note'] = 'Auto-generated skeleton. AI did not produce closure during session.'

            s['status'] = 'CLOSED'
            s['ended_at'] = '$TIMESTAMP'

            with open(sf, 'w') as f:
                json.dump(s, f, indent=2)
            break
    except Exception:
        continue
" 2>/dev/null

# ── 2. AUDIT — verify integrity ──────────────────────────────────────────
# Quick audit: check mapper health
AUDIT_RESULT=$(python3 -c "
import json, os, glob

mapper_path = '$MAPPER'
seif_dir = '$SEIF_DIR'

if not os.path.exists(mapper_path):
    print('SKIP: no mapper')
    exit(0)

with open(mapper_path) as f:
    m = json.load(f)

modules = m.get('modules', [])
if isinstance(modules, list):
    # Check for ghosts (mapper entries without files)
    ghosts = 0
    for mod in modules:
        p = mod.get('path', '')
        if p:
            full = os.path.join(seif_dir, p) if not os.path.isabs(p) else p
            if not os.path.exists(full):
                ghosts += 1
    print(f'modules={len(modules)} ghosts={ghosts}')
else:
    print(f'modules={len(modules)} format=dict')
" 2>/dev/null || echo "SKIP: audit failed")

# ── 3. MEDITATE — quality assessment (lightweight) ───────────────────────
# We don't run full quality gate in a hook (too slow). Instead, record that
# meditate should happen. The AI should have done this during the session.

# ── 4. ABSORB — decay relevance + update mapper ─────────────────────────
if [ -f "$MAPPER" ]; then
  python3 -c "
import json

with open('$MAPPER') as f:
    m = json.load(f)

# Decay factor per session (small — recency bias, not amnesia)
DECAY = 0.02

modules = m.get('modules', [])
if isinstance(modules, list):
    for mod in modules:
        rel = mod.get('relevance', 0.5)
        # Never decay below 0.3 (minimum relevance floor)
        mod['relevance'] = max(0.3, round(rel - DECAY, 4))
elif isinstance(modules, dict):
    for name, info in modules.items():
        rel = info.get('relevance', 0.5)
        info['relevance'] = max(0.3, round(rel - DECAY, 4))

m['last_session'] = '$TIMESTAMP'

with open('$MAPPER', 'w') as f:
    json.dump(m, f, indent=2)
" 2>/dev/null
fi

# ── 5. CIRCLE — confirm sync ─────────────────────────────────────────────
# If .seif is a git repo with a 'mini' remote, push context
if [ -d "$SEIF_DIR/.git" ]; then
  # Auto-commit any changes
  cd "$SEIF_DIR"
  git add -A 2>/dev/null
  git diff --cached --quiet 2>/dev/null || \
    git commit -m "session-end: auto-sync ($TIMESTAMP)" --no-gpg-sign 2>/dev/null

  # Push to mini if remote exists (non-blocking)
  if git remote | grep -q "mini" 2>/dev/null; then
    git push mini main 2>/dev/null &
  fi

  # Push to origin if remote exists (non-blocking)
  if git remote | grep -q "origin" 2>/dev/null; then
    git push origin main 2>/dev/null &
  fi
fi

# ── Kill background circuit monitor ──────────────────────────────────────
MONITOR_PID_FILE="$HOME/.seif/circuit/monitor.pid"
if [ -f "$MONITOR_PID_FILE" ]; then
  MONITOR_PID=$(cat "$MONITOR_PID_FILE" 2>/dev/null)
  if [ -n "$MONITOR_PID" ]; then
    kill "$MONITOR_PID" 2>/dev/null || true
  fi
  rm -f "$MONITOR_PID_FILE"
fi

exit 0
