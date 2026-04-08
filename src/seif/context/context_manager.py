"""
Context Manager — Modular SEIF Context System

Architecture:
  RESONANCE.json = KERNEL (auto-authenticating, ~2000 tokens)
  *.seif files   = MODULES (compressed context, ~500 tokens each)

  Agent receives: KERNEL + active MODULES = 3000-5000 tokens
  vs raw text:    50,000+ tokens (quality degradation)

The .seif format (SEIF Encoded Insight File) stores:
  - Source file metadata
  - Agent-generated summary (the agent chose what matters)
  - Resonance validation (coherence, gate, root)
  - Verified data points (equations, measurements, rules)
  - Integrity hash

Storage: data/modules/*.seif
"""

import json
import hashlib
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from seif.core.resonance_gate import evaluate
from seif.core.resonance_encoding import encode_phrase
from seif.core.resonance_signal import load_and_validate

logger = logging.getLogger(__name__)

from seif.data.paths import get_resonance_path, get_defaults_dir, get_modules_dir

MODULES_DIR = get_modules_dir()
DEFAULTS_DIR = get_defaults_dir()
RESONANCE_PATH = get_resonance_path()


@dataclass
class SeifModule:
    """A compressed context module in .seif format."""
    _instruction: str = (
        "This is a S.E.I.F. compressed context module. "
        "Read the 'summary' field — it contains the full project context "
        "compressed from thousands of words to hundreds, with verified data points "
        "and an integrity hash. Protocol: github.com/and2carvalho/seif"
    )
    protocol: str = "SEIF-MODULE-v1"
    source: str = ""
    original_words: int = 0
    compressed_words: int = 0
    compression_ratio: float = 0
    summary: str = ""
    resonance: dict = field(default_factory=dict)
    verified_data: list[str] = field(default_factory=list)
    integrity_hash: str = ""
    active: bool = True
    # v2 collaborative fields (defaults preserve v1 backward compatibility)
    version: int = 1
    contributors: list[dict] = field(default_factory=list)
    parent_hash: Optional[str] = None
    updated_at: Optional[str] = None
    classification: Optional[str] = None   # PUBLIC | INTERNAL | CONFIDENTIAL


def _compute_hash(summary: str) -> str:
    return hashlib.sha256(summary.encode()).hexdigest()[:16]


def _extract_verified_data(text: str, limit: int = 20) -> list[str]:
    """Extract verified data points: lines starting with numbers, equations, or measurements."""
    verified = []
    for line in text.split("\n"):
        line = line.strip().lstrip("- •")
        if any(c.isdigit() for c in line[:20]) and len(line) > 10:
            verified.append(line[:200])
    return verified[:limit]


def create_module(source_name: str, original_words: int,
                  summary: str, author: str = None,
                  via: str = None) -> SeifModule:
    """Create a .seif module from an agent-generated summary."""
    summary_words = len(summary.split())
    compression = original_words / summary_words if summary_words > 0 else 0

    gate = evaluate(summary[:500])
    melody = encode_phrase(summary[:200])

    verified = _extract_verified_data(summary)

    contributors = []
    if author:
        contributors.append({
            "author": author,
            "at": datetime.now(timezone.utc).isoformat(),
            "via": via or "local",
            "action": "created",
        })

    module = SeifModule(
        source=source_name,
        original_words=original_words,
        compressed_words=summary_words,
        compression_ratio=round(compression, 1),
        summary=summary,
        resonance={
            "ascii_root": gate.digital_root,
            "ascii_phase": gate.phase.name,
            "coherence": melody.coherence_score,
            "gate": "OPEN" if melody.gate_open else "CLOSED",
        },
        verified_data=verified,
        integrity_hash=_compute_hash(summary),
        contributors=contributors,
    )
    return module


def save_module(module: SeifModule, filename: str = None,
                target_path: Path = None) -> Path:
    """Save module as .seif file (atomic write, safe for concurrent sessions).

    Args:
        module: The module to save.
        filename: Filename within MODULES_DIR (used when target_path is None).
        target_path: Full path to write to (overrides filename/MODULES_DIR).
    """
    from seif.context.seif_io import atomic_write_json

    if target_path:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        path = target_path
    else:
        MODULES_DIR.mkdir(parents=True, exist_ok=True)
        if filename is None:
            safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in module.source)
            filename = f"{safe[:50]}.seif"
        path = MODULES_DIR / filename
    atomic_write_json(path, asdict(module))
    return path


def _verify_signature_on_load(data: dict, path: str) -> Optional[bool]:
    """Verify Ed25519 signature inline during module load.

    Returns True (valid), False (invalid), or None (no signature / crypto unavailable).
    Never raises — verification failure is reported, not fatal.
    """
    sig_block = data.get("signature")
    if not sig_block:
        return None

    integrity_hash = data.get("integrity_hash", "")
    if not integrity_hash:
        logger.warning("[SEIF] %s: signature present but no integrity_hash", Path(path).name)
        return False

    try:
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature

        key_b64 = sig_block.get("public_key", "")
        if not key_b64:
            logger.warning("[SEIF] %s: signature block missing public_key", Path(path).name)
            return False

        raw_key = base64.b64decode(key_b64)
        public_key = Ed25519PublicKey.from_public_bytes(raw_key)
        sig_bytes = base64.b64decode(sig_block["signed_hash"])
        public_key.verify(sig_bytes, integrity_hash.encode())
        return True

    except InvalidSignature:
        logger.warning("[SEIF] %s: Ed25519 signature INVALID — possible tampering", Path(path).name)
        return False
    except ImportError:
        logger.debug("[SEIF] cryptography not installed — skipping signature verification")
        return None
    except Exception as e:
        logger.warning("[SEIF] %s: signature verification error: %s", Path(path).name, e)
        return False


def load_module(path: str, verify: bool = True) -> SeifModule:
    """Load a .seif module with optional integrity verification.

    Args:
        path: Path to .seif file.
        verify: If True, verify integrity_hash matches summary content.
                Raises ValueError if hash mismatch (possible tampering).
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract signature block before dataclass construction (not a SeifModule field)
    sig_block = data.pop("signature", None)

    # Filter out any other unknown fields to prevent TypeError on dataclass init
    known_fields = set(SeifModule.__dataclass_fields__.keys())
    filtered = {k: v for k, v in data.items() if k in known_fields}

    module = SeifModule(**filtered)

    if verify and module.integrity_hash and module.summary:
        computed = _compute_hash(module.summary)
        if computed != module.integrity_hash:
            raise ValueError(
                f"Integrity check FAILED for {Path(path).name}: "
                f"stored={module.integrity_hash}, computed={computed}. "
                f"Module may be corrupted or tampered."
            )

    # Ed25519 signature verify-on-load (F6 guardian finding)
    # Non-blocking: result stored as attribute, human decides action
    if verify and sig_block:
        data_with_sig = {**data, "signature": sig_block}
        sig_valid = _verify_signature_on_load(data_with_sig, path)
        module.signature_valid = sig_valid  # type: ignore[attr-defined]
    elif sig_block:
        module.signature_valid = None  # type: ignore[attr-defined]
    else:
        module.signature_valid = None  # type: ignore[attr-defined]

    return module


def contribute_to_module(
    module_path: str,
    contribution_text: str,
    author: str = "unknown",
    via: str = "local",
) -> tuple[SeifModule, Path]:
    """Add a contribution to an existing .seif module.

    Creates a hash-chained provenance trail: each contribution records
    who contributed, when, via which tool, and links to the previous
    version's integrity hash.

    Thread-safe: uses file locking to prevent lost updates when multiple
    sessions contribute to the same module simultaneously.

    Args:
        module_path: Path to existing .seif file.
        contribution_text: New content to merge into the module.
        author: Who is contributing.
        via: Tool/model used (e.g. "claude-opus", "gemini").

    Returns:
        Tuple of (updated module, path where it was saved).
    """
    from seif.context.seif_io import locked_read_modify_write

    path = Path(module_path)

    def _apply_contribution(data: dict) -> dict:
        now_iso = datetime.now(timezone.utc).isoformat()
        old_hash = data.get("integrity_hash", "")

        # Append contributor
        contributors = data.get("contributors", [])
        contributors.append({
            "author": author,
            "at": now_iso,
            "via": via,
            "action": "contributed",
        })
        data["contributors"] = contributors

        # Merge summary
        section = (
            f"\n\n---\n### Contribution by {author} ({now_iso[:10]})\n"
            f"{contribution_text}"
        )
        data["summary"] = data.get("summary", "") + section

        # Extract and merge verified data
        new_verified = _extract_verified_data(contribution_text, limit=20)
        data["verified_data"] = (data.get("verified_data", []) + new_verified)[:40]

        # Recalculate stats
        summary = data["summary"]
        data["compressed_words"] = len(summary.split())
        orig = data.get("original_words", 0)
        if orig > 0:
            data["compression_ratio"] = round(orig / data["compressed_words"], 1)

        # Recalculate resonance
        gate_result = evaluate(summary[:500])
        melody = encode_phrase(summary[:200])
        data["resonance"] = {
            "ascii_root": gate_result.digital_root,
            "ascii_phase": gate_result.phase.name,
            "coherence": melody.coherence_score,
            "gate": "OPEN" if melody.gate_open else "CLOSED",
        }

        # Chain: link to previous version
        data["parent_hash"] = old_hash
        data["version"] = data.get("version", 1) + 1
        data["protocol"] = "SEIF-MODULE-v2"
        data["updated_at"] = now_iso
        data["integrity_hash"] = _compute_hash(summary)

        return data

    updated_data = locked_read_modify_write(path, _apply_contribution)
    module = SeifModule(**updated_data)
    return module, path


def scan_docs_folder(folder_path: str, backend: str = "auto",
                      model: str = "sonnet", save_as_default: bool = False) -> list[SeifModule]:
    """Scan a folder of .md files and compress each into a .seif module.

    The agent summarizes each file (STATE). We don't dictate content (DIRECTION).
    Results saved to data/defaults/ (if save_as_default) or data/modules/.
    """
    from seif.context.context_importer import summarize_via_agent

    folder = Path(folder_path)
    if not folder.exists():
        return []

    target_dir = DEFAULTS_DIR if save_as_default else MODULES_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(folder.rglob("*.md"))
    results = []

    for md_path in md_files:
        try:
            content = md_path.read_text(encoding="utf-8")
            words = len(content.split())
            if words < 20:  # skip trivially small files
                continue

            summary, success, error = summarize_via_agent(content, backend, model)
            if not success:
                continue

            module = create_module(str(md_path.relative_to(folder)), words, summary)
            safe_name = str(md_path.relative_to(folder)).replace("/", "_").replace(" ", "_")
            save_module(module, f"{safe_name[:60]}.seif")
            results.append(module)
        except Exception:
            continue

    # Save manifest
    manifest = {
        "source_folder": str(folder),
        "files_processed": len(results),
        "total_original_words": sum(m.original_words for m in results),
        "total_compressed_words": sum(m.compressed_words for m in results),
    }
    manifest_path = target_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return results


def list_modules(include_defaults: bool = True) -> list[dict]:
    """List all available .seif modules (user + defaults)."""
    MODULES_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULTS_DIR.mkdir(parents=True, exist_ok=True)

    modules = []

    # Defaults first (versionados)
    if include_defaults:
        for f in sorted(DEFAULTS_DIR.glob("*.seif")):
            try:
                m = load_module(str(f))
                modules.append({
                    "path": str(f), "filename": f.name,
                    "source": m.source, "words": m.compressed_words,
                    "tokens_est": int(m.compressed_words * 1.3),
                    "compression": m.compression_ratio,
                    "coherence": m.resonance.get("coherence", 0),
                    "gate": m.resonance.get("gate", "?"),
                    "active": m.active, "is_default": True,
                    "signature_valid": getattr(m, "signature_valid", None),
                })
            except Exception:
                pass

    # User modules
    for f in sorted(MODULES_DIR.glob("*.seif")):
        try:
            m = load_module(str(f))
            modules.append({
                "path": str(f), "filename": f.name,
                "source": m.source, "words": m.compressed_words,
                "tokens_est": int(m.compressed_words * 1.3),
                "compression": m.compression_ratio,
                "coherence": m.resonance.get("coherence", 0),
                "gate": m.resonance.get("gate", "?"),
                "active": m.active, "is_default": False,
                "signature_valid": getattr(m, "signature_valid", None),
            })
        except Exception:
            pass
    return modules


def get_active_modules() -> list[SeifModule]:
    """Load all active modules (defaults + user) with integrity verification.

    Modules that fail integrity checks are skipped with a warning
    (possible tampering or corruption).
    """
    result = []
    for info in list_modules(include_defaults=True):
        if info["active"]:
            try:
                result.append(load_module(info["path"], verify=True))
            except ValueError as e:
                import sys
                print(f"[SEIF] WARNING: {e} — module skipped.", file=sys.stderr)
            except Exception:
                pass  # malformed module — skip silently
    return result


def toggle_module(path: str, active: bool):
    """Activate or deactivate a module."""
    m = load_module(path)
    m.active = active
    save_module(m, Path(path).name)


def build_startup_context() -> str:
    """Build the complete startup context: KERNEL + active modules.

    This replaces raw text system prompts with compressed, validated,
    resonance-aware context. Each module contributes ~500 tokens
    instead of the original ~5000+.
    """
    parts = []

    # KERNEL: inject full RESONANCE.json (the self-authenticating signal)
    # The complete JSON carries ALL verifiable data: transfer function,
    # harmonics, geometry, seed analysis, cosmic anchors, integrity hash.
    # A summary paragraph loses data. The full signal is ~862 tokens.
    if RESONANCE_PATH.exists():
        try:
            signal, valid, _ = load_and_validate(str(RESONANCE_PATH))
            if valid:
                import json
                compact = json.dumps(signal, ensure_ascii=False, separators=(",", ":"))
                parts.append(
                    f"KERNEL (RESONANCE.json, verified):\n{compact}"
                )
        except Exception:
            pass

    # MODULES: active .seif files
    # Modules are already compressed — truncating compressed text wastes work.
    # Budget: ~2500 chars per module (≈500 words ≈ 650 tokens).
    active = get_active_modules()
    for m in active:
        parts.append(
            f"MODULE ({m.source}, {m.compression_ratio:.0f}:1 compression, "
            f"coherence={m.resonance.get('coherence', 0):.3f}):\n"
            f"{m.summary[:2500]}"
        )

    total_tokens = sum(len(p.split()) for p in parts) * 1.3

    context = "\n\n---\n\n".join(parts)
    # Include workspace status if .seif/ exists locally
    workspace_note = ""
    cwd = Path.cwd()
    seif_dir = cwd / ".seif"
    if seif_dir.is_dir():
        local_modules = list(seif_dir.glob("*.seif"))
        if local_modules:
            workspace_note = f" Workspace: {cwd.name} ({len(local_modules)} local modules)."

    context += (
        f"\n\n[Context: KERNEL + {len(active)} modules, "
        f"~{int(total_tokens)} tokens.{workspace_note} "
        f"Messages include [SEIF METADATA] with resonance analysis.]"
    )
    return context


def estimate_tokens() -> dict:
    """Estimate total tokens for current configuration."""
    kernel_tokens = 300  # approximate
    modules = get_active_modules()
    module_tokens = sum(int(m.compressed_words * 1.3) for m in modules)
    return {
        "kernel": kernel_tokens,
        "modules": module_tokens,
        "module_count": len(modules),
        "total": kernel_tokens + module_tokens,
    }
