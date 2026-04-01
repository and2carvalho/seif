"""Tests for Dual-Layer QR Generator and QR Decoder/Verification Loop."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    from seif.generators.dual_qr import generate_dual_qr, save_dual_qr, _compute_seif_hash
    from seif.analysis.qr_decoder import decode_qr_image, verify, VerificationLevel
    from seif.core.resonance_gate import HarmonicPhase
except ImportError as _e:
    print(f"SKIP test_dual_qr: {_e}")
    sys.exit(0)


# --- Generation tests ---

def test_dual_qr_generates_image():
    """Dual QR produces a PIL Image."""
    spec = generate_dual_qr("Enoch Seed")
    assert spec.image is not None
    assert spec.image.size[0] > 0
    assert spec.image.size[1] > 0


def test_dual_qr_payload_structure():
    """Payload contains all required SEIF fields."""
    spec = generate_dual_qr("Enoch Seed")
    payload = spec.payload
    assert payload["protocol"] == "SEIF-QR-v1"
    assert payload["text"] == "Enoch Seed"
    assert "root" in payload
    assert "phase" in payload
    assert "gate" in payload
    assert "hash" in payload
    assert len(payload["hash"]) == 32


def test_seif_hash_deterministic():
    """Same text always produces same hash."""
    h1 = _compute_seif_hash("Enoch Seed")
    h2 = _compute_seif_hash("Enoch Seed")
    assert h1 == h2


def test_seif_hash_differs_for_different_text():
    """Different texts produce different hashes."""
    h1 = _compute_seif_hash("Enoch Seed")
    h2 = _compute_seif_hash("Fear and control")
    assert h1 != h2


def test_dual_qr_harmonic_gate_open():
    """Harmonic input produces gate OPEN."""
    spec = generate_dual_qr("O amor liberta e guia")  # root 9
    assert spec.gate_open is True
    assert spec.payload["gate"] == "OPEN"


def test_dual_qr_entropic_gate_closed():
    """Entropic input produces gate CLOSED."""
    spec = generate_dual_qr("Fear and control")  # root 7
    assert spec.gate_open is False
    assert spec.payload["gate"] == "CLOSED"


def test_dual_qr_includes_fractal():
    """Fractal spec is included and has cells."""
    spec = generate_dual_qr("Enoch Seed")
    assert spec.fractal_spec is not None
    assert spec.fractal_spec.cell_count > 0


# --- Round-trip decode tests ---

def test_round_trip_decode():
    """Generate → save → decode → verify full circuit."""
    spec = generate_dual_qr("Enoch Seed")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        spec.image.save(f.name)
        result = verify(f.name, original_text="Enoch Seed")

    assert result.decode.success, f"Decode failed: {result.decode.error}"
    assert result.decode.payload is not None
    assert result.decode.payload["text"] == "Enoch Seed"


def test_round_trip_integrity():
    """Text integrity verified after round-trip."""
    spec = generate_dual_qr("Enoch Seed")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        spec.image.save(f.name)
        result = verify(f.name, original_text="Enoch Seed")

    assert VerificationLevel.INTEGRITY in result.levels_passed


def test_round_trip_authenticity():
    """SEIF hash verified after round-trip."""
    spec = generate_dual_qr("Enoch Seed")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        spec.image.save(f.name)
        result = verify(f.name, original_text="Enoch Seed")

    assert result.hash_match is True
    assert VerificationLevel.AUTHENTICITY in result.levels_passed


def test_round_trip_coherence():
    """Phase and root coherence verified after round-trip."""
    spec = generate_dual_qr("Enoch Seed")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        spec.image.save(f.name)
        result = verify(f.name, original_text="Enoch Seed")

    assert result.root_match is True
    assert result.phase_match is True
    assert VerificationLevel.COHERENCE in result.levels_passed


def test_circuit_closed():
    """All 4 levels pass = circuit closed."""
    spec = generate_dual_qr("Enoch Seed")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        spec.image.save(f.name)
        result = verify(f.name, original_text="Enoch Seed")

    assert result.circuit_closed is True
    assert result.trust_score == 1.0


def test_round_trip_harmonic_phrase():
    """Round-trip with harmonic phrase (root 9)."""
    text = "O amor liberta e guia"
    spec = generate_dual_qr(text)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        spec.image.save(f.name)
        result = verify(f.name, original_text=text)

    assert result.circuit_closed is True
    assert result.decode.payload["phase"] == "SINGULARITY"


def test_round_trip_entropic_phrase():
    """Round-trip with entropic phrase (gate closed)."""
    text = "Fear and control"
    spec = generate_dual_qr(text)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        spec.image.save(f.name)
        result = verify(f.name, original_text=text)

    assert result.circuit_closed is True
    assert result.decode.payload["gate"] == "CLOSED"


def test_wrong_original_text_fails_integrity():
    """Wrong original text fails integrity check."""
    spec = generate_dual_qr("Enoch Seed")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        spec.image.save(f.name)
        result = verify(f.name, original_text="Wrong text")

    assert result.integrity_match is False
    assert VerificationLevel.INTEGRITY in result.levels_failed


def test_decode_from_pil_image():
    """Decode directly from PIL Image (no file I/O)."""
    spec = generate_dual_qr("Enoch Seed")
    result = verify(spec.image, original_text="Enoch Seed")

    assert result.decode.success, f"Decode failed: {result.decode.error}"
    assert result.circuit_closed is True


if __name__ == "__main__":
    import inspect
    tests = [obj for name, obj in inspect.getmembers(sys.modules[__name__])
             if inspect.isfunction(obj) and name.startswith("test_")]
    passed = failed = 0
    for fn in sorted(tests, key=lambda f: f.__name__):
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
