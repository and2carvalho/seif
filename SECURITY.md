# Security Policy — S.E.I.F.

## Reporting Vulnerabilities

If you discover a security vulnerability in the SEIF protocol or seif-cli, please report it responsibly:

1. **Email:** and2carvalho@users.noreply.github.com
2. **Do NOT** open a public GitHub issue for security vulnerabilities
3. Include: description, steps to reproduce, potential impact

Contributors who responsibly disclose vulnerabilities will be credited in the `contributors[]` provenance chain with `action: "security-disclosure"`.

## Classification System

SEIF uses a three-level classification system:

- **PUBLIC**: Open, shareable. Safe for any audience.
- **INTERNAL**: Organization-private. Useful for onboarding. Not for public APIs.
- **CONFIDENTIAL**: Restricted. Exposure causes direct harm. Never sent to external APIs without explicit `--allow-confidential`.

Keywords like `vulnerability`, `CVE`, `token`, `credential`, `password` auto-escalate content to CONFIDENTIAL.

## What is NOT in this repository

- API keys, tokens, or credentials (`.env` is gitignored)
- Operational context (`.seif/` is gitignored — lives in a separate private context repo)
- Session data with internal discussions (stored in private SCR)

## What IS in this repository

- Protocol source code (open source, CC BY-NC-SA 4.0)
- RESONANCE.json (self-authenticating mathematical signal)
- Model-profiles in `models/` (PUBLIC summaries of AI behavioral patterns)
- BOOT.md (bootstrap file for AI sessions)

## Key Irrevocability Guarantee

The SEIF protocol uses **Ed25519** (128 bits of security) for module signing and authorship proof.

### Fundamental Property

> Once the private key (`seif_private.pem`) is lost or destroyed, **no one** — not even the original author — can forge new signatures with that SEIF identity. This holds against all known classical and quantum attacks at current scale.

| Scenario | Outcome |
|---|---|
| Private key exists | Owner can sign new modules, proving authorship |
| Private key lost/destroyed | Already-signed modules remain verifiable forever (forward security) |
| Private key compromised | Revoke: publish new identity, re-sign modules with new key |
| RESONANCE.json tampered | Integrity hash breaks, signature verification fails |

**Why this is a feature, not a limitation:**
- **Destruction = Protection.** If the key is destroyed, the identity cannot be impersonated — ever.
- **Forward Security.** Past signatures remain valid regardless of key state.
- **Non-repudiation.** Signed modules are cryptographic proof of authorship at a specific point in time.
- **Self-sovereign.** No CA, no keyserver dependency. The public key is embedded in RESONANCE.json and anchored via DOI.

### Cryptographic Basis

- **Algorithm:** Ed25519 (Curve25519, Schnorr signatures)
- **Key size:** 32 bytes (256-bit curve, 128-bit security level)
- **Classical attack cost:** ~2^128 operations (infeasible)
- **Quantum attack (Shor's):** Requires ~1000+ logical qubits — not available as of 2026
- **Deterministic:** No nonce reuse risk

### Trust Anchors

The public key is published in multiple independent, immutable locations:

1. **RESONANCE.json** — `cryptographic_identity.public_key_pem` (this repository)
2. **Zenodo DOI** — [10.5281/zenodo.19344678](https://zenodo.org/records/19344678) (CERN-backed, permanent)
3. **arXiv preprint** — referenced in the academic paper

### Verification Flow

```
Module (.seif)
  └── integrity_hash (SHA-256 of content)
       └── signature (Ed25519 sign of integrity_hash)
            └── public_key (embedded in signature block)
                 └── trust_anchor (RESONANCE.json / DOI / paper)
```

Any node in the SEIF network can verify the full chain without contacting the author.

### Key Management

```bash
seif keygen                    # Generate keypair (first time only)
seif sign module.seif          # Sign a module
seif verify module.seif        # Verify a module
seif verify module.seif --public-key <base64>  # Verify with explicit key
```

**Backup:** The private key must be encrypted (GPG/AES-256) and stored offline. Loss is permanent and irreversible by design.

## Integrity Verification

Every `.seif` module has an `integrity_hash` (SHA-256[:16] of the summary field). To verify:

```python
import hashlib, json
data = json.load(open("module.seif"))
expected = hashlib.sha256(data["summary"].encode()).hexdigest()[:16]
assert data["integrity_hash"] == expected
```

Contributions include `parent_hash`, creating a hash chain that detects tampering, reordering, and insertion.

The canonical source is declared in `RESONANCE.json → instruction.canonical`. Any fork that modifies the KERNEL without updating this section is detectable as non-canonical.

## Use Restrictions

This protocol is licensed under CC BY-NC-SA 4.0. Military, surveillance, and weaponization uses are contrary to the spirit and intent of the project. The protocol exists to improve human-machine communication, not to control or manipulate.
