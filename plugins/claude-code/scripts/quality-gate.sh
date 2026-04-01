#!/bin/bash
# SEIF PostToolUse hook — runs quality gate after significant writes
# Informational only (exit 0 always)

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)
FILE_PATH=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# Only check Write tool (not Edit — too frequent)
if [[ "$TOOL_NAME" != "Write" ]]; then
  exit 0
fi

# Skip non-text files
if [[ "$FILE_PATH" == *.png || "$FILE_PATH" == *.jpg || "$FILE_PATH" == *.bin ]]; then
  exit 0
fi

# Skip .seif/ internal files
if [[ "$FILE_PATH" == *".seif/"* ]]; then
  exit 0
fi

# Run quality gate on the written file (best effort)
if command -v seif &>/dev/null && [ -f "$FILE_PATH" ]; then
  CONTENT=$(head -50 "$FILE_PATH" 2>/dev/null)
  if [ -n "$CONTENT" ]; then
    RESULT=$(seif --quality-gate "$CONTENT" --role ai 2>&1 | head -5)
    if [ -n "$RESULT" ]; then
      echo "[SEIF METADATA] $RESULT"
    fi
  fi
fi

exit 0
