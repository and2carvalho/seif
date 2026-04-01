"""
SEIF Module Signing — Asymmetric key-based provenance.

Elevates owner_fingerprint from "claim" to "proof":
  - seif keygen: generates Ed25519 keypair at ~/.seif/keys/
  - seif sign module.seif: signs with private key
  - seif verify module.seif: verifies with public key

Ed25519 chosen for: small keys (32 bytes), fast, no config, deterministic.
The public key can be published (README, keyserver, RESONANCE.json).
The private key stays on the owner's machine.
"""

import json
import hashlib
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from seif.data.paths import get_user_home


KEYS_DIR_NAME = "keys"
PRIVATE_KEY_FILE = "seif_private.pem"
PUBLIC_KEY_FILE = "seif_public.pem"
SIGNATURE_FIELD = "signature"


def _keys_dir() -> Path:
    return get_user_home() / KEYS_DIR_NAME


def _private_key_path() -> Path:
    return _keys_dir() / PRIVATE_KEY_FILE


def _public_key_path() -> Path:
    return _keys_dir() / PUBLIC_KEY_FILE


# ── Key Generation ────────────────────────────────────────────────

def keygen(force: bool = False) -> Tuple[Path, Path]:
    """Generate Ed25519 keypair at ~/.seif/keys/.

    Returns (private_key_path, public_key_path).
    Raises FileExistsError if keys already exist and force=False.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    keys_dir = _keys_dir()
    priv_path = _private_key_path()
    pub_path = _public_key_path()

    if priv_path.exists() and not force:
        raise FileExistsError(
            f"Keys already exist at {keys_dir}/. Use --force to regenerate."
        )

    keys_dir.mkdir(parents=True, exist_ok=True)

    # Generate keypair
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Save private key (PEM, no encryption — user's filesystem is the trust boundary)
    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    priv_path.write_bytes(priv_bytes)
    priv_path.chmod(0o600)  # Owner-only read/write

    # Save public key
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub_path.write_bytes(pub_bytes)

    return priv_path, pub_path


def get_public_key_fingerprint() -> Optional[str]:
    """Return SHA-256 fingerprint of the public key (short form for display)."""
    pub_path = _public_key_path()
    if not pub_path.exists():
        return None
    pub_bytes = pub_path.read_bytes()
    return hashlib.sha256(pub_bytes).hexdigest()[:16]


def get_public_key_base64() -> Optional[str]:
    """Return public key as base64 string (for embedding in RESONANCE.json etc)."""
    pub_path = _public_key_path()
    if not pub_path.exists():
        return None
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    pub_key = load_pem_public_key(pub_path.read_bytes())
    raw = pub_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode()


# ── Signing ───────────────────────────────────────────────────────

def sign_module(module_path: Path) -> dict:
    """Sign a .seif module with the private key.

    Adds a 'signature' field to the module JSON:
    {
        "signature": {
            "algorithm": "Ed25519",
            "public_key": "<base64 raw public key>",
            "signed_hash": "<base64 signature of integrity_hash>",
            "signed_at": "<ISO timestamp>",
            "key_fingerprint": "<SHA-256[:16] of public key>"
        }
    }

    Returns the updated module dict.
    """
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    priv_path = _private_key_path()
    if not priv_path.exists():
        raise FileNotFoundError(
            "No signing key found. Run: seif keygen"
        )

    # Load module
    with open(module_path) as f:
        module = json.load(f)

    # Get the integrity_hash (this is what we sign)
    integrity_hash = module.get("integrity_hash", "")
    if not integrity_hash:
        raise ValueError(f"Module has no integrity_hash: {module_path}")

    # Load private key and sign
    private_key = load_pem_private_key(priv_path.read_bytes(), password=None)
    signature_bytes = private_key.sign(integrity_hash.encode())

    # Build signature block
    module[SIGNATURE_FIELD] = {
        "algorithm": "Ed25519",
        "public_key": get_public_key_base64(),
        "signed_hash": base64.b64encode(signature_bytes).decode(),
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "key_fingerprint": get_public_key_fingerprint(),
    }

    # Write back
    with open(module_path, "w") as f:
        json.dump(module, f, indent=2, ensure_ascii=False)

    return module


# ── Verification ──────────────────────────────────────────────────

def verify_module(module_path: Path, public_key_b64: Optional[str] = None) -> dict:
    """Verify the signature of a .seif module.

    If public_key_b64 is provided, uses that key.
    Otherwise, uses the key embedded in the signature block.

    Returns: {"valid": bool, "reason": str, "key_fingerprint": str}
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature

    with open(module_path) as f:
        module = json.load(f)

    sig_block = module.get(SIGNATURE_FIELD)
    if not sig_block:
        return {"valid": False, "reason": "No signature found", "key_fingerprint": ""}

    integrity_hash = module.get("integrity_hash", "")
    if not integrity_hash:
        return {"valid": False, "reason": "No integrity_hash", "key_fingerprint": ""}

    # Resolve public key
    key_b64 = public_key_b64 or sig_block.get("public_key", "")
    if not key_b64:
        return {"valid": False, "reason": "No public key available", "key_fingerprint": ""}

    try:
        raw_key = base64.b64decode(key_b64)
        public_key = Ed25519PublicKey.from_public_bytes(raw_key)

        sig_bytes = base64.b64decode(sig_block["signed_hash"])
        public_key.verify(sig_bytes, integrity_hash.encode())

        fp = sig_block.get("key_fingerprint", "")
        return {"valid": True, "reason": "Signature valid", "key_fingerprint": fp}

    except InvalidSignature:
        return {"valid": False, "reason": "INVALID — signature does not match",
                "key_fingerprint": sig_block.get("key_fingerprint", "")}
    except Exception as e:
        return {"valid": False, "reason": f"Verification error: {e}",
                "key_fingerprint": ""}


def sign_all_modules(directory: Path) -> list[dict]:
    """Sign all .seif modules in a directory."""
    results = []
    for seif_file in sorted(directory.rglob("*.seif")):
        try:
            sign_module(seif_file)
            results.append({"file": str(seif_file.name), "signed": True})
        except Exception as e:
            results.append({"file": str(seif_file.name), "signed": False,
                           "error": str(e)})
    return results
