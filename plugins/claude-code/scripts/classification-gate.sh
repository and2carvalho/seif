#!/bin/bash
# SEIF PreToolUse hook — blocks classified data from leaving the session
# Exit 0 = allow, Exit 2 = block (reason on stderr)

INPUT=$(cat)

# Build restricted word dynamically to avoid self-triggering the gate
_RESTRICTED_WORD="CONFID""ENTIAL"

# Parse all fields in a single python call (robust against partial parse failures)
eval "$(echo "$INPUT" | python3 -c "
import json, sys, shlex
try:
    d = json.load(sys.stdin)
    tool = d.get('tool_name', '')
    ti = d.get('tool_input', {})
    fp = ti.get('file_path', '')
    c = str(ti.get('content', '') or '')[:16000]
    old = str(ti.get('old_string', '') or '')[:16000]
    new = str(ti.get('new_string', '') or '')[:16000]
    cmd = str(ti.get('command', '') or '')[:16000]
    print(f'TOOL_NAME={shlex.quote(tool)}')
    print(f'FILE_PATH={shlex.quote(fp)}')
    print(f'CONTENT={shlex.quote(c)}')
    print(f'OLD_STRING={shlex.quote(old)}')
    print(f'NEW_STRING={shlex.quote(new)}')
    print(f'COMMAND={shlex.quote(cmd)}')
except Exception:
    print('TOOL_NAME=\"\"')
    print('FILE_PATH=\"\"')
    print('CONTENT=\"\"')
    print('OLD_STRING=\"\"')
    print('NEW_STRING=\"\"')
    print('COMMAND=\"\"')
" 2>/dev/null)"

# ─── Bash tool: intercept dangerous commands ───
if [[ "$TOOL_NAME" == "Bash" ]]; then

  # Block: writing to files via shell redirects or utilities
  if echo "$COMMAND" | grep -qE '(>\s*\S|>>\s*\S|\btee\b|\bcp\b.*\.(env|pem|key|crt|p12|pfx|secret)|cat\s+.*>\s*\S)'; then
    # Allow writes targeting .seif/ or .claude/memory/
    if echo "$COMMAND" | grep -qE '\.(seif|claude/.*memory)/'; then
      : # pass through
    else
      echo "[SEIF GATE] Blocked: Bash command writes to file via redirect/tee/cp. Use Write/Edit tools instead." >&2
      exit 2
    fi
  fi

  # Block: reading secrets via Bash
  if echo "$COMMAND" | grep -qE '\b(cat|less|more|head|tail|bat)\b.*\.(env|pem|key|crt|p12|pfx|secret)\b'; then
    echo "[SEIF GATE] Blocked: Bash command reads sensitive file (.env/.pem/.key/.crt/.p12/.pfx/.secret)." >&2
    exit 2
  fi

  # Block: exfiltration — posting data to network
  if echo "$COMMAND" | grep -qE '(curl\s+.*(-d|--data|--data-raw|--data-binary|-F|--form)\b|wget\s+.*--post|nc\s+-|ncat\s+-|\|\s*(curl|wget|nc|ncat|socat)\b)'; then
    echo "[SEIF GATE] Blocked: Bash command may exfiltrate data via network." >&2
    exit 2
  fi

  # Block: Python/Ruby/Node one-liners that write files
  if echo "$COMMAND" | grep -qE "(python3?\s+-c\s+.*open\(|ruby\s+-e\s+.*File\.(write|open)|node\s+-e\s+.*fs\.(write|append))"; then
    # Allow if targeting .seif/ or .claude/memory/
    if echo "$COMMAND" | grep -qE '\.(seif|claude/.*memory)/'; then
      : # pass through
    else
      echo "[SEIF GATE] Blocked: Bash command uses scripting language to write files. Use Write/Edit tools instead." >&2
      exit 2
    fi
  fi

  # Bash commands that don't match dangerous patterns pass through
  exit 0
fi

# ─── Only check Write/Edit tools beyond this point ───
if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]]; then
  exit 0
fi

# Allow writes to .seif/ directory and .claude/memory
if [[ "$FILE_PATH" == *".seif/"* || "$FILE_PATH" == *".claude/"*"/memory/"* ]]; then
  exit 0
fi

# Aggregate all text content to scan (Write content + Edit old/new strings)
SCAN_TEXT="$CONTENT
$OLD_STRING
$NEW_STRING"

# ─── Classification markers ───
# Matches YAML/JSON assignment patterns like:
#   classification: <restricted>
#   "classification": "<restricted>"
#   level: <restricted>
RESTRICTED_MARKER="(classification|level|cls)[\"']?\\s*[:=]\\s*[\"']?${_RESTRICTED_WORD}"
if echo "$SCAN_TEXT" | grep -qE "$RESTRICTED_MARKER"; then
  echo "[SEIF GATE] Blocked: content has restricted classification marker. Cannot write to $FILE_PATH" >&2
  exit 2
fi

# ─── Credential patterns ───
CRED_PATTERNS=(
  # Private keys (PEM)
  '-----BEGIN (PRIVATE|RSA|EC) KEY-----'
  # Hardcoded passwords
  'password\s*[:=]\s*["'"'"'][^"'"'"']{4,}'
  # API keys with sk- prefix
  'api_key\s*[:=]\s*["'"'"']sk-'
  # Telegram bot tokens: 8+ digits : 35+ alphanum
  '[0-9]{8,}:[A-Za-z0-9_-]{35}'
  # MongoDB connection strings
  'mongodb\+srv://'
  # Cloudflare tokens
  'cfut_[A-Za-z0-9]'
  # Bearer tokens (20+ chars)
  'Bearer [A-Za-z0-9._-]{20,}'
  # JWT tokens (two base64url segments starting with eyJ)
  'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+'
  # Generic env-style secrets: TOKEN=, SECRET=, API_KEY=, APIKEY=
  '(TOKEN|SECRET|API_KEY|APIKEY)\s*[:=]\s*["'"'"']?[A-Za-z0-9_-]{16,}'
)

# Build combined regex (joined by |)
CRED_REGEX=""
for p in "${CRED_PATTERNS[@]}"; do
  if [[ -z "$CRED_REGEX" ]]; then
    CRED_REGEX="$p"
  else
    CRED_REGEX="$CRED_REGEX|$p"
  fi
done

if echo "$SCAN_TEXT" | grep -qE "$CRED_REGEX"; then
  echo "[SEIF GATE] Blocked: potential credential detected in write to $FILE_PATH" >&2
  exit 2
fi

exit 0
