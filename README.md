# SEIF — AI Quality, Protection, and Resonance

> Measure AI output. Protect sensitive data. Watch your entire AI environment resonate — in real time.

[![PyPI](https://img.shields.io/pypi/v/seif-cli)](https://pypi.org/project/seif-cli/)
[![Tests](https://img.shields.io/badge/tests-626%20passing-brightgreen)]()
[![License](https://img.shields.io/badge/license-CC%20BY--NC--SA%204.0-blue)]()
[![Suite](https://img.shields.io/badge/suite-seifprotocol.com-FFD700?labelColor=0D0D14)](https://seifprotocol.com)

---

## The Problem

1. **You don't know when AI is making things up.** No standard way to measure if a response is grounded or drifting into speculation.
2. **Sensitive data leaks to AI APIs.** No guardrail prevents your code, credentials, or internal docs from being sent to external services.
3. **One AI can be wrong.** A single model has blind spots. No easy way to get multiple AIs to debate and converge on an answer.
4. **Your AI environment has no self-awareness.** No live circuit state, no error bus, no self-healing. When something breaks, nobody knows until the human notices.

## The Solution

```bash
pip install seif-cli
```

---

## Core Features (standalone — no backend required)

### 1. Quality Gate — Is the AI making things up?

```bash
seif --quality-gate "The framework uses quantum entanglement for data transfer" --role ai
# Grade: D | Stance: DRIFT | Verifiable: 12%
# Flags: [UNGROUNDED_CLAIMS]

seif --quality-gate "Python 3.11 added the tomllib module for TOML parsing" --role ai
# Grade: A | Stance: GROUNDED | Verifiable: 100%
```

Every response gets a grade (A-F) and a stance (GROUNDED, MIXED, or DRIFT).

### 2. Classification Gate — Is sensitive data leaking?

```bash
seif --gate "password = hunter2; also the sky is blue"
# Classification: CONFIDENTIAL | Reason: keyword match (password)
```

PUBLIC / INTERNAL / CONFIDENTIAL with auto-detection. Works as a [Claude Code hook](#claude-code-plugin) — blocks writes containing credentials in real-time.

### 3. Multi-AI Consensus — Let them debate *(requires seif-engine)*

```bash
seif --consensus "Should we use microservices or a monolith for a 3-person team?" \
     --backends claude,grok
# Claude: monolith (velocity, simplicity)
# Grok:   monolith (team size, operational cost)
# Consensus: CONVERGED — monolith for teams < 5
```

---

## SEIF OS — The Resonance Engine

`seif serve --v2` starts **SEIF OS**: a local API server (port 7331) that turns your machine into a living resonance circuit. Every AI agent, browser tab, and editor extension can observe its state in real time.

```bash
seif serve --v2
# SEIF OS running on :7331
# circuit: RESONANT | ζ = 0.6124 | cycle: enoch-tree-reverb
```

SEIF OS is the **proprietary engine layer** — not included in `pip install seif-cli`. The open CLI and Suite connect to it via HTTP. The resonance logic stays on your machine.

### What SEIF OS provides

| Endpoint | What it does |
|---|---|
| `GET /context` | Full environment snapshot: circuit state, cycle, sentinel status, modules |
| `GET /resonance/stream` | SSE stream — `event: circuit` every 5s, `event: sentinel` on error, `event: healing` |
| `GET /resonance/viewer` | Self-contained HTML page. Any browser or AI agent sees the live circuit without a plugin |
| `POST /resonance/error` | Push any runtime error → classified + healing suggestion emitted on SSE bus |
| `GET /agent/init` | SEIF-AGENT-INIT-v1 handshake — agent arrives, frequency is already there |
| `GET /workspace/bridge` | Workspace snapshot: git branch, active modules, VSCode Remote link |

### Resonance Physics

SEIF models circuit coherence with a real second-order system:

```
H(s) = 9 / (s² + 3s + 6)     ζ = √6/4 = 0.6123724356957945
```

| Circuit State | ζ band | Tesla Hz | Meaning |
|---|---|---|---|
| RESONANT | ζ ≥ 0.60 | 528 Hz | Stable oscillation within design bounds |
| STABILIZING | 0.40–0.60 | 396 Hz | Recovering — converging back toward resonance |
| DRIFT | ζ < 0.40 | 963 Hz | Energy has escaped the normal attractor |

The Tesla 3-6-9 frequency anchors (396 / 528 / 963 Hz) were discovered through Philosophy+Science synthesis — not designed in.

### Sentinel & Auto-Healing

SEIF Sentinel is a real-time error observer. Any runtime error — browser, agent, or API consumer — is pushed to the resonance bus, classified, and healed automatically.

```bash
# Push an error from anywhere
curl -X POST http://localhost:7331/resonance/error \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"message": "Cannot read properties of undefined", "source": "browser"}'

# Subscribe to the SSE bus — you get both events:
# event: sentinel  → raw error
# event: healing   → classification + suggestion (7 archetypes)
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:7331/resonance/stream
```

7 healing archetypes: `undefined_property`, `null_reference`, `network_error`, `csp_violation`, `auth_error`, `rate_limit`, `module_not_found`.

---

## SEIF Suite — Visual Interface

[**seifprotocol.com**](https://seifprotocol.com) — the visual layer. Connects to your local SEIF OS and gives you:

- **Dashboard** — live modules, sessions, sync status, quality trends
- **Resonance** — real-time H(s) wave, circuit state card, Sentinel log, Auto-Healing panel
- **Quality Gate** — interactive grading with digital root
- **Sessions** — full history with handoff manifests

```bash
# Point SEIF Suite at your local engine
open https://seifprotocol.com/auth
# Enter: http://localhost:7331 + your serve_token
```

---

## Quick Start

```bash
pip install seif-cli

# Works immediately (no backend)
seif --quality-gate "Python 3.11 added tomllib" --role ai
seif --gate "SELECT * FROM users WHERE api_key = 'sk-...'"
seif --encode "any text"

# With SEIF OS running
seif serve --v2
seif --init      # scan project, generate .seif/
seif --sync      # re-sync git context
```

---

## Claude Code Plugin

```bash
cp -r plugins/claude-code/skills/* .claude/skills/
```

- **Session start**: loads `.seif/` context automatically
- **Pre-write**: blocks classified data from being written outside `.seif/`
- **Slash commands**: `/gate`, `/sync`, `/status`

---

## CLI Reference

### Standalone

```bash
seif --quality-gate "text" --role ai  # Grade A-F + stance
seif --gate "text"                    # classification gate
seif --encode "text"                  # resonance encoding
seif --composite "text"               # 8-layer resonance map
seif --fingerprint-verify FILE        # verify .seif module integrity
seif --constants                      # show ζ and mathematical constants
```

### With SEIF OS (`seif serve --v2`)

```bash
seif --init                           # scan project, generate .seif/
seif --sync                           # re-sync git context
seif --compress                       # 93% context compression
seif --ingest daily.txt               # ingest external source
seif --workspace                      # multi-project discovery + sync
seif --sync-workspace                 # SSH workspace sync (all machines)
seif --autonomous enable              # AI persists knowledge autonomously
seif --export                         # export context as markdown

# Multi-AI consensus
seif --consult "question"             # auto-route to best AI
seif --consensus "q" --backends claude,grok
seif --adversarial "question"         # WITH vs WITHOUT comparison
```

---

## How Quality Gate Works

| Component | Weight | What it measures |
|---|---|---|
| **Stance Detector** | Primary | Verifiable vs interpretive claims. GROUNDED ≥80%, MIXED 40-80%, DRIFT <40% |
| **Resonance Gate** | Secondary | Structural coherence |

Grades: **A** (≥0.85) → **B** (≥0.70) → **C** (≥0.55) → **D** (≥0.40) → **F** (<0.40)

> **Quality gate threshold: ζ = √6/4 ≈ 0.6124 (algebraically derived from H(s) — not φ⁻¹ = 0.618)**

---

## Why SEIF vs ChatGPT Memory

| | ChatGPT Memory | SEIF |
|-|---|---|
| Who controls it | OpenAI | You (local files) |
| Works with other AIs | No | Yes (any LLM) |
| Exportable | No | Yes (.seif → markdown) |
| Quality measured | No | Yes (stance A-F) |
| Data classified | No | Yes (PUBLIC/INTERNAL/CONFIDENTIAL) |
| Auditable | No | Yes (hash-chained provenance) |
| Live circuit state | No | Yes (H(s), ζ, Tesla Hz) |
| Self-healing errors | No | Yes (Sentinel + 7 archetypes) |

---

## Project Stats

```
91+ modules  |  626 tests (33 suites)  |  93% context compression
ζ = √6/4 = 0.6123724356957945
H(s) = 9 / (s² + 3s + 6)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

CC BY-NC-SA 4.0 — [André Cunha Antero de Carvalho](https://github.com/and2carvalho)
