# SEIF Plugin for Claude Code

Persistent memory + quality gate + classification for Claude Code.

## What it does

- **Session Start**: Loads your `.seif/` context so Claude remembers who you are, what you decided, and where you left off
- **Classification Gate**: Blocks CONFIDENTIAL data from being written to non-SEIF targets
- **Quality Gate**: Measures AI output stance (GROUNDED vs DRIFT) after writes
- **Slash Commands**: `/gate`, `/sync`, `/status`

## Install

### Prerequisites

```bash
pip install seif-cli
cd your-project
seif --init
```

### Option A: Project-level (recommended)

Copy the hooks configuration to your project's `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "path/to/plugins/claude-code/scripts/session-start.sh",
            "timeout": 10000
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "path/to/plugins/claude-code/scripts/classification-gate.sh",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

Copy skills to your project:

```bash
cp -r plugins/claude-code/skills/* .claude/skills/
```

### Option B: Global

Copy skills to `~/.claude/skills/` and hooks to `~/.claude/settings.json`.

## Usage

```
/gate "some AI response"    # Check quality (A-F grade)
/sync                       # Re-sync .seif/ context
/status                     # Show loaded modules
```

## How it works

1. `seif --init` scans your project and generates `.seif/` context (git history, structure, README)
2. On Claude Code session start, the hook loads relevant `.seif/` modules into context
3. Claude now knows your project, your decisions, your preferences
4. The quality gate detects when responses drift from verifiable claims
5. The classification gate prevents sensitive data from leaking

## Without SEIF vs With SEIF

| Without | With |
|---------|------|
| Every session starts from zero | Claude remembers your context |
| No way to detect AI hallucination | Quality gate flags DRIFT |
| Confidential data can leak anywhere | Classification blocks CONFIDENTIAL |
| You repeat yourself across sessions | Feedback persists automatically |
