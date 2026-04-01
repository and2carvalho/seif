# SEIF — Measure, Protect, and Triangulate AI Output

> One question. Multiple AIs debate it. You get the answer they all agree on — graded for accuracy, with your data protected.

[![PyPI](https://img.shields.io/pypi/v/seif-cli)](https://pypi.org/project/seif-cli/)
[![Tests](https://img.shields.io/badge/tests-626%20passing-brightgreen)]()
[![License](https://img.shields.io/badge/license-CC%20BY--NC--SA%204.0-blue)]()

---

## The Problem

1. **You don't know when AI is making things up.** There's no standard way to measure if a response is grounded in facts or drifting into speculation.
2. **Sensitive data leaks to AI APIs.** No guardrail prevents your code, credentials, or internal docs from being sent to external services.
3. **One AI can be wrong.** A single model has blind spots. There's no easy way to get multiple AIs to debate and converge on an answer.

## The Solution

```bash
pip install seif-cli
```

### 1. Quality Gate — Is the AI making things up?

```bash
seif --quality-gate "The framework uses quantum entanglement for data transfer" --role ai
# Grade: D | Stance: DRIFT | Verifiable: 12%
# Flags: [UNGROUNDED_CLAIMS]

seif --quality-gate "Python 3.11 added the tomllib module for TOML parsing" --role ai
# Grade: A | Stance: GROUNDED | Verifiable: 100%
```

Every response gets a grade (A-F) and a stance (GROUNDED, MIXED, or DRIFT). Verifiable claims are counted separately from speculation.

### 2. Classification Gate — Is sensitive data leaking?

```bash
seif --gate "password = hunter2; also the sky is blue"
# Classification: CONFIDENTIAL | Reason: keyword match (password)
```

Content is automatically classified as PUBLIC, INTERNAL, or CONFIDENTIAL. Keywords like `password`, `api_key`, `CVE` auto-escalate to CONFIDENTIAL. The classification gate blocks sensitive data from leaving your environment.

Works as a [Claude Code hook](#claude-code-plugin) — blocks writes containing credentials or classified markers in real-time.

### 3. Multi-AI Consensus — Let them debate *(requires seif-engine)*

```bash
seif --consensus "Should we use microservices or a monolith for a 3-person team?" \
     --backends claude,grok
# Claude: monolith (velocity, simplicity)
# Grok: monolith (team size, operational cost)
# Consensus: CONVERGED — monolith for teams < 5
```

One question goes to multiple AIs. They analyze independently, compare results, and converge. You get the answer they all agree on. Requires `seif-engine` (private, not included in `pip install seif-cli`).

---

## Quick Start

```bash
pip install seif-cli

# Grade AI output (works immediately)
seif --quality-gate "Python 3.11 added tomllib" --role ai
# Grade: A | Stance: GROUNDED | Verifiable: 100%

# Classify content (works immediately)
seif --gate "SELECT * FROM users WHERE api_key = 'sk-...'"
# Classification: CONFIDENTIAL

# Resonance encoding (works immediately)
seif --encode "any text"
seif --composite "any text"
```

No project setup required. These commands work standalone on any text.

## Claude Code Plugin

SEIF works as a plugin for [Claude Code](https://github.com/anthropics/claude-code):

```bash
# Copy skills to your project
cp -r plugins/claude-code/skills/* .claude/skills/

# Add hooks to .claude/settings.json (see plugins/claude-code/README.md)
```

**What it does:**
- **Session start**: loads your `.seif/` context automatically
- **Pre-write**: blocks classified data from being written outside `.seif/`
- **Slash commands**: `/gate`, `/sync`, `/status`

## CLI Commands

### Standalone (`pip install seif-cli`)

```bash
seif --quality-gate "text" --role ai # measure quality (Grade A-F, stance detection)
seif --gate "text"                   # classification gate (PUBLIC/INTERNAL/CONFIDENTIAL)
seif --encode "text"                 # resonance encoding
seif --composite "text"              # 8-layer resonance map
seif --fingerprint-verify FILE       # verify .seif module integrity
seif --constants                     # show mathematical constants
```

### Full (`seif-cli` + `seif-engine`)

These commands require the `seif-engine` backend (private, not on PyPI):

```bash
seif --init                          # scan project, extract git context, generate .seif/
seif --sync                          # re-sync git context after changes
seif --compress                      # compress project into .seif (93% reduction)
seif --ingest daily.txt              # filter meeting notes by project
seif --scan "git"                    # auto-generate CLI knowledge from --help
seif --workspace                     # multi-project discovery + sync
seif --autonomous enable             # AI persists knowledge autonomously
seif --export                        # export context as markdown

# Multi-AI
seif --consult "question"            # auto-route to best AI
seif --consensus "q" --backends claude,grok  # cross-AI consensus
seif --adversarial "question"        # WITH vs WITHOUT comparison
```

## How Quality Gate Works

The quality gate measures two things:

| Component | Weight | What it measures |
|-----------|--------|-----------------|
| **Stance Detector** | Primary | Counts verifiable vs interpretive claims. GROUNDED (≥80% verifiable), MIXED (40-80%), DRIFT (<40%) |
| **Resonance Gate** | Secondary | Structural coherence (experimental) |

Grades: **A** (≥0.85) → **B** (≥0.70) → **C** (≥0.55) → **D** (≥0.40) → **F** (<0.40)

## Context Persistence

SEIF also gives AI persistent memory across sessions — but so does ChatGPT Memory. The difference:

| | ChatGPT Memory | SEIF |
|-|---------------|------|
| Who controls it | OpenAI | You (local files) |
| Works with other AIs | No | Yes (any LLM) |
| Exportable | No | Yes (.seif → markdown) |
| Quality measured | No | Yes (stance A-F) |
| Data classified | No | Yes (PUBLIC/INTERNAL/CONFIDENTIAL) |
| Auditable | No | Yes (hash-chained provenance) |

## Project Stats

```
59 modules  |  626 tests (33 suites)  |  93% context compression
Classification: PUBLIC / INTERNAL / CONFIDENTIAL with auto-detection
Quality Gate: Stance detector + resonance gate → Grade A-F
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

CC BY-NC-SA 4.0 — [André Cunha Antero de Carvalho](https://github.com/and2carvalho)
