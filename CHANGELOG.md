# Changelog

All notable changes to the SEIF project are documented here.

## [0.2.0] — 2026-03-31

### Added
- **Personal Nucleus** (`~/.seif/`): profile.json, sources.json, auto-discovery of GitHub repos, tools scanning, project extraction
- **Native Chat Client** (`seif chat`): Direct Anthropic SDK with streaming, multi-backend routing (Claude/Gemini/local), rich TUI, quality gate per response
- **File Extraction** (`seif --extract`): Scan arbitrary files/directories into .seif modules with auto-classification
- **Ed25519 Signing** (`seif keygen`, `seif sign`, `seif verify`): Cryptographic module signing with unforgeable provenance
- **OpenTimestamps** (`seif stamp`, `seif verify-stamp`): Bitcoin-anchored proof of existence for .seif modules
- **Context API** (`seif serve`): Hardened read-only HTTP server for browser integration (auth token, rate limiting, audit log, metadata-only)
- **Dia Browser Integration** (`seif --dia-skill`): Generate browser skill prompts from nucleus context
- **Model Auto-Tracking** (`seif --models`): Quality gate observations per backend, auto-generated behavioral profiles
- **Owner Fingerprint**: SHA-256 identity binding + consent gate for file extraction
- **Provenance Block**: Zenodo DOI (10.5281/zenodo.19344678) embedded in RESONANCE.json KERNEL

### Security
- 5-AI adversarial audit (Claude + Gemini + Grok + Kimi + DeepSeek/Z.AI)
- API token authentication for seif serve
- Rate limiting (10 req/min)
- Audit logging (~/.seif/serve_audit.log)
- Metadata-only exposure (no content, no summaries, no keys)
- Classification gate (CONFIDENTIAL never exposed)

### Changed
- Repository restructured: clean public repo (zero history exposure)
- Old repo archived as private (seif-archive)
- README rewritten for professional focus
- Evidence page sanitized (no detailed proofs)
- CLAUDE.md updated for restructured project

## [0.1.2] — 2026-03-30

### Added
- `--adversarial`: Compare WITH vs WITHOUT protocol
- `--consensus --mirror`: Clean mirror instance in multi-backend consensus
- `--scan`: CLI program scanner (--help → .seif knowledge module)
- `--generate`: .seif modules → structured documentation
- `--changelog`: decisions.seif → CHANGELOG.md

## [0.1.1] — 2026-03-29

### Added
- Watermark module (infrasound embedding in audio)
- Grok API backend
- Inter-AI consultation (`--consult`, `--consensus`)
- Relay tests
- Streaming watermark sessions
- Boot check (multi-LLM validation)
- Identity Declaration Block v3.1

## [0.1.0] — 2026-03-26

### Added
- Initial release on PyPI (`pip install seif-cli`)
- 59 Python modules, 626 tests, 33 test suites
- Quality Gate (Grade A-F: stance + resonance)
- Context compression (93% token reduction)
- Autonomous context management
- Classification (PUBLIC/INTERNAL/CONFIDENTIAL)
- Separate Context Repository (SCR) pattern
- Workspace multi-project support
- Web product site (Streamlit)
