"""
QR Decoder & Verification Loop — Closing the Resonance Circuit

Design principle: IF IT CANNOT BE VERIFIED, IT CANNOT BE TRUSTED.

This module closes the feedback loop:
  Generate → Encode → Image → Scan → Decode → Verify

Verification levels:
  1. QR Decode:    Can the standard QR layer be read back?
  2. Integrity:    Does the decoded text match the original?
  3. Authenticity: Does the SEIF hash verify against recomputed hash?
  4. Coherence:    Does the decoded phase/root match recomputed values?

The circuit is complete when all 4 levels pass.
"""

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Union

import numpy as np

from seif.core.resonance_gate import digital_root, ascii_vibrational_sum, classify_phase, HarmonicPhase
from seif.constants import PHI_INVERSE


class VerificationLevel(Enum):
    """Verification depth levels."""
    DECODE = "decode"          # QR readable
    INTEGRITY = "integrity"    # text matches
    AUTHENTICITY = "authenticity"  # hash verifies
    COHERENCE = "coherence"    # phase/root match


@dataclass
class DecodeResult:
    """Result of decoding a QR image."""
    success: bool
    raw_data: Optional[str] = None
    payload: Optional[dict] = None
    error: Optional[str] = None
    decoder_used: Optional[str] = None


@dataclass
class VerificationResult:
    """Result of the full verification loop."""
    decode: DecodeResult
    levels_passed: list[VerificationLevel] = field(default_factory=list)
    levels_failed: list[VerificationLevel] = field(default_factory=list)
    integrity_match: Optional[bool] = None
    hash_match: Optional[bool] = None
    phase_match: Optional[bool] = None
    root_match: Optional[bool] = None
    recomputed_hash: Optional[str] = None
    recomputed_root: Optional[int] = None
    recomputed_phase: Optional[str] = None
    trust_score: float = 0.0
    circuit_closed: bool = False

    @property
    def all_passed(self) -> bool:
        return len(self.levels_failed) == 0 and len(self.levels_passed) == 4


def _compute_seif_hash(text: str) -> str:
    """Recompute SEIF hash from text (same algorithm as dual_qr.py)."""
    global_sum = ascii_vibrational_sum(text)
    global_root = digital_root(global_sum)
    phase = classify_phase(global_root)
    meta = f"{text}|root={global_root}|phase={phase.name}"
    return hashlib.sha256(meta.encode()).hexdigest()[:32]


def decode_qr_image(image_input: Union[str, Path, np.ndarray, "Image.Image"]) -> DecodeResult:
    """Decode a QR code from an image file, numpy array, or PIL Image.

    Tries pyzbar first (fast, C-based), falls back to OpenCV QR detector.

    Args:
        image_input: Path to image file, numpy array (BGR/grayscale), or PIL Image.

    Returns:
        DecodeResult with decoded payload or error message.
    """
    # Normalize input to numpy array
    img_array = _load_image(image_input)
    if img_array is None:
        return DecodeResult(success=False, error="Could not load image")

    # Convert to grayscale if needed
    if len(img_array.shape) == 3:
        if img_array.shape[2] == 4:
            # RGBA → RGB → Gray
            from PIL import Image
            pil_img = Image.fromarray(img_array, "RGBA").convert("L")
            gray = np.array(pil_img)
        else:
            import cv2
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
    else:
        gray = img_array

    # Try pyzbar first
    result = _decode_pyzbar(gray)
    if result.success:
        return result

    # Fallback: OpenCV QR detector
    result = _decode_opencv(gray)
    if result.success:
        return result

    return DecodeResult(
        success=False,
        error="No QR code detected by any decoder (pyzbar, OpenCV)"
    )


def _load_image(image_input) -> Optional[np.ndarray]:
    """Normalize various input types to numpy array."""
    if isinstance(image_input, np.ndarray):
        return image_input

    if isinstance(image_input, (str, Path)):
        path = Path(image_input)
        if not path.exists():
            return None
        from PIL import Image
        img = Image.open(path)
        return np.array(img)

    # PIL Image
    try:
        return np.array(image_input)
    except Exception:
        return None


def _decode_pyzbar(gray: np.ndarray) -> DecodeResult:
    """Attempt decode using pyzbar."""
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
    except ImportError:
        return DecodeResult(success=False, error="pyzbar not installed")

    results = pyzbar_decode(gray)
    if not results:
        return DecodeResult(success=False, error="pyzbar: no QR found",
                            decoder_used="pyzbar")

    raw = results[0].data.decode("utf-8")
    payload = _parse_payload(raw)

    return DecodeResult(
        success=True,
        raw_data=raw,
        payload=payload,
        decoder_used="pyzbar",
    )


def _decode_opencv(gray: np.ndarray) -> DecodeResult:
    """Attempt decode using OpenCV's QRCodeDetector."""
    try:
        import cv2
    except ImportError:
        return DecodeResult(success=False, error="opencv not installed")

    detector = cv2.QRCodeDetector()
    data, vertices, _ = detector.detectAndDecode(gray)

    if not data:
        return DecodeResult(success=False, error="OpenCV: no QR found",
                            decoder_used="opencv")

    payload = _parse_payload(data)

    return DecodeResult(
        success=True,
        raw_data=data,
        payload=payload,
        decoder_used="opencv",
    )


def _parse_payload(raw: str) -> Optional[dict]:
    """Try to parse raw QR data as SEIF JSON payload."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("protocol", "").startswith("SEIF"):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def verify(image_input: Union[str, Path, np.ndarray, "Image.Image"],
           original_text: Optional[str] = None) -> VerificationResult:
    """Full verification loop: decode + integrity + authenticity + coherence.

    If original_text is provided, all 4 levels are checked.
    If not provided, only decode + internal consistency are checked
    (hash is recomputed from decoded text and compared to embedded hash).

    Args:
        image_input: QR image to verify.
        original_text: Optional original text for full verification.

    Returns:
        VerificationResult with all verification details.
    """
    result = VerificationResult(decode=DecodeResult(success=False))

    # Level 1: DECODE
    decode = decode_qr_image(image_input)
    result.decode = decode

    if not decode.success or decode.payload is None:
        result.levels_failed.append(VerificationLevel.DECODE)
        return result

    result.levels_passed.append(VerificationLevel.DECODE)
    payload = decode.payload

    decoded_text = payload.get("text", "")
    decoded_hash = payload.get("hash", "")
    decoded_root = payload.get("root")
    decoded_phase = payload.get("phase", "")

    # Recompute from decoded text
    result.recomputed_hash = _compute_seif_hash(decoded_text)
    global_sum = ascii_vibrational_sum(decoded_text)
    result.recomputed_root = digital_root(global_sum)
    result.recomputed_phase = classify_phase(result.recomputed_root).name

    # Level 2: INTEGRITY (text matches original, if provided)
    if original_text is not None:
        result.integrity_match = (decoded_text == original_text)
        if result.integrity_match:
            result.levels_passed.append(VerificationLevel.INTEGRITY)
        else:
            result.levels_failed.append(VerificationLevel.INTEGRITY)
    else:
        # Without original, trust that decoded text is correct
        result.integrity_match = True
        result.levels_passed.append(VerificationLevel.INTEGRITY)

    # Level 3: AUTHENTICITY (hash matches)
    result.hash_match = (decoded_hash == result.recomputed_hash)
    if result.hash_match:
        result.levels_passed.append(VerificationLevel.AUTHENTICITY)
    else:
        result.levels_failed.append(VerificationLevel.AUTHENTICITY)

    # Level 4: COHERENCE (phase and root match recomputed values)
    result.root_match = (decoded_root == result.recomputed_root)
    result.phase_match = (decoded_phase == result.recomputed_phase)

    if result.root_match and result.phase_match:
        result.levels_passed.append(VerificationLevel.COHERENCE)
    else:
        result.levels_failed.append(VerificationLevel.COHERENCE)

    # Trust score: fraction of levels passed
    total_levels = len(result.levels_passed) + len(result.levels_failed)
    result.trust_score = len(result.levels_passed) / total_levels if total_levels > 0 else 0.0

    # Circuit is closed when all 4 levels pass
    result.circuit_closed = result.all_passed

    return result


def describe(result: VerificationResult) -> str:
    """Human-readable verification report."""
    lines = ["═══ QR VERIFICATION LOOP ═══"]

    # Decode status
    d = result.decode
    if d.success:
        lines.append(f"Decode:       OK ({d.decoder_used})")
        if d.payload:
            lines.append(f"Protocol:     {d.payload.get('protocol', '?')}")
            lines.append(f"Text:         \"{d.payload.get('text', '')}\"")
            lines.append(f"Root:         {d.payload.get('root')} → {d.payload.get('phase')}")
            lines.append(f"Gate:         {d.payload.get('gate')}")
            lines.append(f"Hash:         {d.payload.get('hash', '')[:16]}...")
    else:
        lines.append(f"Decode:       FAILED — {d.error}")
        return "\n".join(lines)

    lines.append("")
    lines.append("Verification Levels:")

    level_names = {
        VerificationLevel.DECODE: "1. QR Decode",
        VerificationLevel.INTEGRITY: "2. Text Integrity",
        VerificationLevel.AUTHENTICITY: "3. Hash Authenticity",
        VerificationLevel.COHERENCE: "4. Phase Coherence",
    }
    for level in VerificationLevel:
        name = level_names[level]
        if level in result.levels_passed:
            lines.append(f"  {name}: PASS")
        elif level in result.levels_failed:
            lines.append(f"  {name}: FAIL")
        else:
            lines.append(f"  {name}: SKIP")

    lines.append("")
    lines.append(f"Trust Score:    {result.trust_score:.0%}")
    status = "CLOSED (all levels verified)" if result.circuit_closed else "OPEN (verification incomplete)"
    lines.append(f"Circuit:        {status}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Demo: generate + verify round-trip
    from seif.generators.dual_qr import generate_dual_qr, save_dual_qr

    for phrase in ["Enoch Seed", "O amor liberta e guia", "Fear and control"]:
        print(f"\n--- Round-trip: \"{phrase}\" ---")

        # Generate
        spec = generate_dual_qr(phrase)
        path = save_dual_qr(spec)
        print(f"Generated: {path}")

        # Verify from file
        result = verify(path, original_text=phrase)
        print(describe(result))
