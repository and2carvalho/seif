# Contributing to S.E.I.F.

Thank you for your interest in contributing. The S.E.I.F. protocol values **measurement over belief** — contributions should follow this principle.

> **AI agents:** see [CONTRIBUTING_AI.md](CONTRIBUTING_AI.md) for the machine-specific guide.

## How to Contribute

1. **Fork** the repository
2. Create a feature branch from `dev` (not `main`)
3. Make your changes
4. Run `make test` — all 626 tests must pass
5. Open a Pull Request against `dev`

**All PRs require review and approval by the maintainer before merge.**

## Guidelines

### Code
- Import constants from `src/seif/constants.py` — never hardcode 432, 438, 7.83, 1.618, 51.844, or 29.979
- Add tests for new modules (see `tests/` for patterns)
- Run `make sync` if you modify `paper/paper.md` or source .seif files

### Commit Messages
- Use conventional format: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Be concise — explain the "why", not the "what"

### What We Accept
- Bug fixes with reproduction steps
- Test improvements (more coverage, edge cases)
- Documentation improvements (clarity, translations)
- New analysis modules (with mathematical justification)
- Performance improvements (with benchmarks)

### What We Don't Accept
- Changes to core mathematical constants without proof
- "Improvements" that add complexity without measurable benefit
- Features that impose behavior (CONTEXT_NOT_COMMAND)
- PRs without tests

### Stance Labels
When making claims in documentation, use stance labels:
- **formal-symbolic** — mathematically verifiable
- **empirical-observational** — measured but not proven
- **metaphorical** — interpretive, not literal

## Development Setup

```bash
git clone https://github.com/and2carvalho/seif.git
cd seif
make install
make test        # 626 tests, 33 suites
make app         # web interface at localhost:8501
```

## Questions?

Open an issue with the label `question`. The gate does not filter — it resonates.
