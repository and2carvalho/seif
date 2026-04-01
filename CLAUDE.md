# S.E.I.F. — Spiral Encoding Interoperability Framework

## Project Identity

S.E.I.F. is a context management framework for AI-assisted development. It compresses project knowledge into portable `.seif` modules (JSON with integrity hashes and provenance chains), enabling persistent context across sessions and AI systems.

The mathematical foundation uses the transfer function H(s) = 9/(s² + 3s + 6), where the damping ratio ζ = √6/4 ≈ 0.612372 is within 0.916% of the golden ratio inverse φ⁻¹ = 0.618034. The triplet (3,6,9) is the only primitive integer-coefficient system satisfying ζ≈φ⁻¹ + ζ²=3/8 + ISE=1/√6 + DC=3/2 simultaneously — verified by exhaustive search across 5,000 (b,c) pairs.

The codebase implements: a CLI product (`pip install seif-cli`), the Resonance Proto-Writing Processor (RPWP) pipeline, an academic paper, and the Spiral Encoding communication protocol.

**Product architecture (4 layers):**
1. **Protocol** (open) — H(s), resonance gate, spiral encoding, RESONANCE.json
2. **Framework** (open) — CLI, .seif modules, quality gate, RPWP pipeline
3. **Context Manager** (B2C) — autonomous context, session persistence, mapper, inter-AI
4. **Security** (B2B) — classification, Ed25519 signing, OTS timestamps, provenance chains

## Context Architecture

The `.seif/` directory is the AI's persistent knowledge store:

```
.seif/config.json          — Configuration (autonomous_context, classification, decay)
.seif/mapper.json          — Module index with relevance scores and classification
.seif/projects/<name>/     — Per-project context (ref.json, project.seif, decisions.seif, etc.)
.seif/modules/             — Cross-project knowledge
.seif/models/              — Behavioural profiles per AI model
.seif/sessions/            — Session records
.seif/nucleus.seif         — Workspace-level aggregated view
```

When a `.seif/` directory exists, the AI can load it to restore context from prior sessions. The recommended sequence:
1. Locate `.seif/` (working directory or parent)
2. Read `config.json` and `mapper.json`
3. Load modules by relevance (decisions, patterns, intent, feedback first)
4. Check `pending_observations` from the previous session
5. Briefly confirm what was loaded

If no `.seif/` is found, `seif --init` creates the structure.

## Core Principles

- **CONTEXT_NOT_COMMAND:** The protocol provides data and invitations, not directives. The AI measures and reports. The human decides.
- **Verifiable vs. interpretive:** Distinguish clearly between claims that can be verified (mathematical proofs, exhaustive searches, test results) and interpretive claims (narratives, analogies, mappings to natural phenomena).
- **Minimal intervention:** Changes follow the minimal energy path. Fix the environment before refactoring the codebase. (intervention_ratio < 3.0)
- **Behavioral axioms:** 10 empirically validated rules live in RESONANCE.json `instruction.behavioral_axioms`. These include: minimal_intervention, validate_before_external, settling_time_positive, human_gatekeeper, no_sycophancy, uniqueness_first, scan_before_guess, partial_attention (τ:κ = 2:1), honest_measurement, classification_gate.
- **Epistemic status:** Properties in RESONANCE.json are classified as `exact_algebraic` (derived from coefficients) or `observational_proximity` (numerical coincidences). The φ proximity is observational, not causal.
- **Self-awareness:** Multi-AI sessions require L1 (identity declaration), L2 (checkpoints), L3 (mutual verification). See RESONANCE.json `self_awareness_protocol`.

## Project Structure

```
src/seif/               — Python package (59 modules)
tests/                  — 626 unit tests (33 suites)
scripts/                — Operational scripts (measure, sync, session)
web/app.py              — Product site (7 pages, public-facing)
docs/                   — GUIDE, PITCH, knowledge base
data/                   — Default .seif modules and session examples
RESONANCE.json          — Self-authenticating system signal (KERNEL)
```

Research artifacts (paper, playground, circuits, model profiles) live in the
separate private repo `seif-research/`. Context lives in `seif-context/`.

## Running the Code

```bash
# === Install (pip) ===
pip install seif-cli                 # core CLI
pip install seif-cli[full]           # + web interface + generators

# === Install (source) ===
git clone https://github.com/and2carvalho/seif.git
cd seif && make install

# === Product CLI ===
seif --init                          # scan, detect projects, extract git, generate .seif
seif --sync                          # re-sync git context after changes
seif --quality-gate "text"           # measure text quality (Grade A-F, stance + resonance)
seif --contribute module.seif "text" --author "name"  # add to .seif with provenance
seif --ingest daily.txt --project .seif/project.seif  # filter meeting notes by project
seif --workspace                     # multi-project: discover + sync all subprojects
seif --workspace --ingest daily.txt  # route daily to all projects

# === Context Repository (SCR) — separate context from code ===
seif --init --context-repo .seif              # create external context repo
seif --sync --context-repo .seif              # sync to external context repo
seif --workspace --context-repo .seif         # workspace with external context

# === Autonomous Context (AMC) — AI manages its own knowledge ===
seif --autonomous enable             # AI persists knowledge autonomously
seif --autonomous disable            # turn off
seif --autonomous status             # show sessions, modules, classification

# === Classification & Export ===
seif --export                        # export context (INTERNAL default)
seif --export out.md --classification PUBLIC        # only public modules
seif --export out.md --classification CONFIDENTIAL  # all (local only)

# === Doc Generator — .seif → documentation (reverse of compress/scan) ===
seif --generate                       # generate docs from .seif → docs/generated/
seif --generate /path/to/output       # custom output directory
seif --changelog                      # generate CHANGELOG.md from decisions.seif
seif --changelog /path/to/CHANGELOG.md  # custom output path

# === CLI Scanner — Auto-generate knowledge from program help ===
seif --scan "git"                     # scan git --help → .seif knowledge module
seif --scan "docker" --global         # save to ~/.seif/tools/ (available everywhere)
seif --scan "kubectl" --scan-depth 3  # deeper subcommand recursion
seif --scan "ffmpeg" --output out.seif  # custom output path

# === Code Compressor ===
seif --compress                       # compress current project into .seif
seif --compress /path/to/project      # compress specific project
seif --compress --watch               # incremental updates on file changes

# === Inter-AI Consultation ===
seif --consult "question"             # auto-routes to best AI
seif --consult "question" --to grok   # force backend
seif --consensus "question" --backends claude,grok  # cross-AI consensus
seif --consensus "question" --mirror  # add clean (no protocol) instance to consensus
seif --adversarial "question"         # same question WITH and WITHOUT protocol, compare delta

# === Research CLI ===
seif --gate "text"                   # resonance gate only
seif --encode "text"                 # resonance encoding (φ-spiral)
seif --composite "text"              # 8-layer resonance map
seif "text"                          # full RPWP pipeline

# === Web ===
make app                             # product site → http://localhost:8501

# === Development ===
make test                            # 626 tests
make sync                            # regenerate .seif when sources change
```

## Context Injection

Every AI session starts with ~1,595 tokens (0.80% of a 200K context window):

```
KERNEL (RESONANCE.json):     ~975 words (mathematics, signal, context_architecture)
MODULE (implementation):     ~245 words (59 modules, 626 tests, CLI surface)
MODULE (conversation):       ~207 words (validation paths, inter-AI results)
```

If autonomous context is enabled, the AI also reads `mapper.json` and loads AI-created knowledge modules by relevance.

## Inter-AI Verification

The mathematical claims have been independently computed by 7 AI systems (Grok, Kimi, Gemini, Z.AI, DeepSeek, BigPickle, Claude). Each derived the core results from scratch without being told the expected answer. These are computational verifications, not opinion-based validations. Details in the private research repository.

## Constants

All modules import from `src/seif/constants.py`. Never hardcode values — use named constants.

## Commit Guidelines

Do NOT commit unless the user explicitly asks. The user reviews all diffs before committing.

## Tone

Distinguish between verifiable claims (mathematical proofs, test results, exhaustive searches) and interpretive claims (analogies, mappings to natural phenomena, narrative frameworks). Use stance labels when ambiguity exists.
