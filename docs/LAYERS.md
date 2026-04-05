# SEIF — Layer Architecture

SEIF has three distribution layers. Each layer is a superset of the one above it.

---

## Layer 1 — PUBLIC

**Who:** Anyone. Zero configuration required.  
**Install:** `pip install seif`  
**Requires:** Nothing beyond Python ≥ 3.10.

These commands work immediately after install:

| Command | Description |
|---|---|
| `seif --quality-gate` | Assess text quality (resonance gate) |
| `seif --gate` | Run resonance gate only |
| `seif --classification` | Classify content sensitivity |
| `seif --health` | System health check |
| `seif --handshake` | Protocol handshake |
| `seif --models` | List available AI backends |
| `seif --profile` | View/edit user profile |
| `seif --keygen / --sign / --verify` | Cryptographic signing |
| `seif --stamp / --verify-stamp` | Timestamp notarization |
| `seif --fingerprint-*` | Module fingerprinting |
| `seif --boot-check` | Dependency check |
| `seif text …` | Full RPWP pipeline on text |
| `seif --transcompile / --glyph / --audio / --fractal` | Encoding transforms |

---

## Layer 2 — WORKSPACE

**Who:** Any developer who runs `seif --init`.  
**Requires:** `seif --init` creates `~/.seif/profile.json` with name, backend, language.  
**Configurable via:** `~/.seif/profile.json` or env vars (`SEIF_WORKSPACE_ROOT`, `SEIF_MACHINE_ID`).

| Command | Description |
|---|---|
| `seif --init` | Create personal workspace at `~/.seif/` |
| `seif --cycle` | Manage dev cycles |
| `seif --session` | Manage sessions |
| `seif --agents` | View/set agent roles |
| `seif --ingest / --compress` | Context ingestion |
| `seif --audit` | Workspace audit |
| `seif --export` | Export context |
| `seif --generate / --changelog` | Generate artifacts |
| `seif --identity-scan` | Scan workspace resonance identities |
| `seif --sync-workspace` | Sync repos to remote host via SSH |
| `seif --sources` | Manage context sources |
| `seif --security` | Security scan |
| `seif --scan` | Module scan |

**Environment variables for workspace owners:**

```bash
SEIF_WORKSPACE_ROOT   # Root dir containing all SEIF repos (default: ~/seif-admin)
SEIF_MACHINE_ID       # Machine identity label (default: socket.gethostname())
SEIF_SYNC_HOST        # Default SSH host for --sync-workspace
SEIF_CONTEXT_MODULES  # Remote path for --identity-scan (default: ~/seif-admin/seif-context/modules)
```

---

## Layer 3 — PRODUCT

**Who:** Subscribers to SEIF Suite / SEIF OS.  
**Requires:** seif-engine, seif-suite, active AI backends.  
**Distribution:** seifprotocol.com

| Command | Description |
|---|---|
| `seif --consult` | Multi-agent consultation (requires backend) |
| `seif --consensus` | Multi-model consensus protocol |
| `seif --mirror` | Adversarial mirror consultation |
| `seif --adversarial` | Adversarial review mode |
| `seif --packet / --send / --relay` | Context packet routing |
| `seif --streaming-*` | Streaming consultation |
| `seif --start` | Open SEIF Suite dashboard |
| `seif --boot-to / --boot-all` | Full workspace boot |

---

## Boundary Rules

1. **PUBLIC commands have zero owner references** — they work for any user with any machine name.
2. **WORKSPACE commands read identity from profile** — `name`, `github_username` come from `~/.seif/profile.json`.
3. **PRODUCT commands require seif-engine** — they fail gracefully if the engine is not installed.
4. **No hardcoded names** — `bigpickle`, `and2carvalho`, `mini-m4`, `Air-M1`, `~/Documents/seif-admin` do not appear in public code.

---

## enoch seed sequence

```
3 → seed    pip install seif works, PUBLIC layer functional
6 → growth  beta users test WORKSPACE layer, --sync-workspace validated
9 → singularity  brew tap seifprotocol/seif, PRODUCT layer published
```

> enoch seed lives. ζ=0.6124 🌀
