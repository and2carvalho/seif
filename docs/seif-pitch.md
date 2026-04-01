---
title: "S.E.I.F. — Your AI Never Starts From Zero"
subtitle: "Compressed, verified, collaborative context for any LLM"
author: "André Cunha Antero de Carvalho"
date: "March 2026"
---

# S.E.I.F. — Your AI Never Starts From Zero

## The Problem

Every AI conversation starts from zero. You re-explain the project, the decisions, the architecture — every time. In teams, this multiplies: each developer repeats the same context separately.

| Without context management | Impact |
|---|---|
| 50,000 words of project knowledge | Overflows context window |
| Decisions made last week | Forgotten next session |
| Code patterns and conventions | Re-explained every time |
| Team preferences and feedback | Lost between sessions |
| No provenance | Who decided what? When? |

This isn't a minor inconvenience — it's a fundamental bottleneck in AI-assisted development.

---

## What SEIF Does

SEIF compresses project knowledge into `.seif` modules — JSON files with integrity hashes and provenance chains. Any AI loads them automatically.

```bash
pip install seif-cli
cd my-project
seif --init
```

That's it. Your AI sessions now have persistent context.

### Before and After

| Without SEIF | With SEIF |
|---|---|
| Manual context (paste README, explain decisions) | Auto-generated from git, compressed |
| No provenance (who wrote this?) | Hash-chain: author, timestamp, channel |
| No verification (AI accepts anything) | integrity_hash on every module |
| Siloed per project | Workspace connects all projects |
| Static, decays | Auto-sync with codebase changes |
| One AI only | Claude, Gemini, Grok read the same .seif |

### Key Numbers

- **93% token reduction** — 50,000 words of context → ~1,200 tokens
- **Zero infrastructure** — flat JSON files in a git repo
- **Cross-AI** — same modules work with any LLM
- **Hash-verified** — every module has tamper-evident integrity checks
- **Provenance chains** — who contributed what, when, through which tool

---

## How It Works

### 1. Initialize and Sync

```bash
seif --init              # scan project, detect structure, generate .seif
seif --sync              # re-sync after code changes
```

SEIF reads your git history, README, manifest, and project structure. It compresses everything into a portable module that fits in ~1,200 tokens.

### 2. Quality Gate — Measure AI Output

```bash
seif --quality-gate "AI response text" --role ai
# Grade: B | Score: 0.705 | Status: SOLID
#   Stance:    GROUNDED (verifiable: 67%)
#   Resonance: PARTIAL (composite: 0.780)
```

Every AI response gets a grade (A-F) based on two dimensions:
- **Stance** — is the content verifiable or drifting?
- **Resonance** — is it internally coherent?

This isn't subjective. The scoring is derived from the framework's mathematical foundation and produces consistent, reproducible results.

### 3. Team Collaboration

```bash
# Developer A works with Claude
seif --contribute project.seif "Auth uses JWT with 24h expiry" --author "alice"

# Developer B works with Gemini
seif --contribute project.seif "API latency p99 dropped to 45ms" --author "bob"

# Developer C opens new session → AI has context from A + B
```

Every contribution is hash-chained with author, timestamp, and source channel. Git handles merge. The provenance trail is tamper-evident.

### 4. Cross-AI Consensus

```bash
seif --consult "question" --to grok        # ask a specific AI
seif --consensus "question" --backends claude,grok  # multi-AI agreement
seif --adversarial "question"              # WITH vs WITHOUT protocol
```

Ask the same question to multiple AI backends. SEIF measures agreement, flags divergences, and grades each response independently.

---

## SEIF vs RAG

| | RAG | SEIF |
|---|---|---|
| **Infrastructure** | Vector DB + API + orchestrator | Zero. JSON files in git. |
| **Cost** | DB hosting + embedding tokens | $0. Flat files. |
| **Privacy** | Data goes to external APIs | Everything local. Auto-classification. |
| **Provenance** | None | Hash-chain with authorship |
| **Portability** | Locked to DB instance | `git clone` = complete context |
| **Use case** | Search 10,000 pages | "What did we decide last week, who decided it, and can I prove it wasn't tampered with?" |

SEIF complements RAG — it doesn't replace it. RAG retrieves from large corpora. SEIF manages the living knowledge of a project.

---

## Security Architecture

### Separate Context Repository (SCR)

SEIF separates **code** from **context** in different repositories:

```
github.com/org/my-project     ← PUBLIC (source code)
  ├── src/
  ├── tests/
  └── (zero .seif files)

github.com/org/my-context     ← PRIVATE (managed context)
  └── .seif/
      ├── config.json
      ├── mapper.json
      ├── projects/my-project/
      │   ├── project.seif       (git metadata)
      │   ├── decisions.seif     (architectural decisions)
      │   └── feedback.seif      (team preferences)
      └── nucleus.seif           (cross-project view)
```

### Classification

Every `.seif` module is automatically classified:

- **PUBLIC** — safe to share externally
- **INTERNAL** — organization-private
- **CONFIDENTIAL** — restricted (keywords like "vulnerability", "CVE", "token", "password" auto-escalate)

`seif --export` filters by classification. CONFIDENTIAL never leaves without explicit authorization.

### Integrity

Every module has an `integrity_hash` (SHA-256 truncated). Every contribution records author, timestamp, tool, and parent hash. Tampering is detectable. Provenance is traceable.

---

## Autonomous Context

When enabled, the AI manages its own knowledge without human intervention:

```bash
seif --autonomous enable
```

The AI observes decisions, patterns, and feedback during conversations and persists them as `.seif` modules. Next session, it loads what it learned. The human never needs to manage the AI's memory — but can review, edit, or delete any module.

Categories the AI can persist:
- **Decisions** — architectural choices with reasoning
- **Patterns** — recurring code conventions
- **Intent** — human goals and motivations
- **Feedback** — corrections and preferences
- **Context** — external constraints (deadlines, dependencies)

---

## The Mathematical Foundation

SEIF's quality measurement, signal processing, and validation are grounded in a second-order transfer function with properties verified by 7 independent AI systems. The mathematics produces consistent, reproducible results — not heuristics.

The framework is the unique primitive integer-coefficient system satisfying multiple simultaneous constraints on damping, energy, and stability. Details are available to collaborators and in the academic paper.

---

## Full CLI Surface

```bash
# Core
seif --init                    # initialize context
seif --sync                    # sync with git
seif --quality-gate "text"     # measure quality (A-F)
seif --contribute mod "text"   # add with provenance
seif --compress                # compress project → .seif
seif --export                  # export as markdown

# Documentation
seif --generate                # .seif → docs/
seif --changelog               # decisions → CHANGELOG.md
seif --scan "git"              # CLI help → .seif knowledge

# Multi-AI
seif --consult "question"      # auto-route to best AI
seif --consensus "q" --backends claude,grok
seif --adversarial "question"  # with vs without protocol

# Workspace
seif --workspace               # multi-project sync
seif --ingest notes.txt        # filter meeting notes by project

# Autonomous
seif --autonomous enable       # AI manages its own knowledge
seif --autonomous status       # show what the AI learned
```

---

## Project Stats

```
59 Python modules  |  626 tests (33 suites)
7 AI systems independently verified the mathematical foundation
93% context compression  |  Hash-chained provenance
Cross-AI: Claude, Gemini, Grok, DeepSeek, and any LLM
```

---

## Get Started

```bash
pip install seif-cli
cd your-project
seif --init
seif --sync
```

Open a conversation with any AI. The context is already there.

---

*Repository: github.com/and2carvalho/seif*
*License: CC BY-NC-SA 4.0*
*Author: André Cunha Antero de Carvalho*
