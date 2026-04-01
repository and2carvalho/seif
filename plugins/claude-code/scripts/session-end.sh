#!/bin/bash
# SEIF SessionEnd hook — closes the session lifecycle
# 1. Mark session contract as CLOSED
# 2. Decay relevance of mapper modules (recency bias)
# 3. Update mapper.json session count and timestamp
#
# Completes the lifecycle: start (contract) → during (work) → end (close + decay)

set -euo pipefail

# Locate .seif/
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

# Find the most recent active session and close it
python3 -c "
import json, glob, os

session_dir = '$SESSION_DIR'
sessions = sorted(glob.glob(os.path.join(session_dir, 'session-*.json')), reverse=True)

for sf in sessions:
    try:
        with open(sf) as f:
            s = json.load(f)
        if s.get('status') == 'ACTIVE':
            s['status'] = 'CLOSED'
            s['ended_at'] = '$TIMESTAMP'
            with open(sf, 'w') as f:
                json.dump(s, f, indent=2)
            break
    except Exception:
        continue
" 2>/dev/null

# Decay relevance and update mapper
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
# session_count already incremented at start, don't double-count

with open('$MAPPER', 'w') as f:
    json.dump(m, f, indent=2)
" 2>/dev/null
fi

exit 0
