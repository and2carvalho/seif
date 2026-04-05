"""Tests for Context QR — .seif module encoding as QR sequences + round-trip."""
import json
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
pytest.importorskip("qrcode")

from seif.context.context_qr import (
    encode_module, save_sequence, decode_sequence, describe,
    _build_chunk_payload, _parse_chunk_payload,
)
from seif.context.context_manager import create_module, save_module, SeifModule

DEFAULTS_DIR = Path(__file__).resolve().parent.parent / "data" / "defaults"


def _create_temp_module(words: int = 200) -> str:
    """Create a temporary .seif module for testing."""
    summary = " ".join(["resonance"] * words)
    module = create_module("test_source.md", words * 10, summary)
    with tempfile.NamedTemporaryFile(suffix=".seif", delete=False, mode="w") as f:
        json.dump({
            "protocol": module.protocol,
            "source": module.source,
            "original_words": module.original_words,
            "compressed_words": module.compressed_words,
            "compression_ratio": module.compression_ratio,
            "summary": module.summary,
            "resonance": module.resonance,
            "verified_data": module.verified_data,
            "integrity_hash": module.integrity_hash,
            "active": module.active,
        }, f)
        return f.name


# --- Payload format tests ---

def test_chunk_payload_roundtrip():
    """Build and parse chunk payload."""
    data = b"test data for chunk"
    payload = _build_chunk_payload(0, 3, "abc123" * 6, data)
    parsed = _parse_chunk_payload(payload)
    assert parsed is not None
    index, total, h, recovered = parsed
    assert index == 0
    assert total == 3
    assert recovered == data


def test_parse_invalid_payload():
    """Invalid payloads return None."""
    assert _parse_chunk_payload("not a SEIF payload") is None
    assert _parse_chunk_payload("") is None
    assert _parse_chunk_payload("SEIF:bad") is None


# --- Encoding tests ---

def test_encode_small_module():
    """Small module encodes to 1 QR."""
    path = _create_temp_module(50)
    seq = encode_module(path)
    assert seq.qr_count >= 1
    assert seq.compressed_bytes > 0
    assert len(seq.chunks) == seq.qr_count
    assert all(c.image is not None for c in seq.chunks)


def test_encode_preserves_metadata():
    """Encoding preserves module metadata."""
    path = _create_temp_module(100)
    seq = encode_module(path)
    assert seq.source_module == "test_source.md"
    assert seq.original_words > 0
    assert seq.compression_ratio > 0


def test_encode_default_conversa():
    """Encode the real conversa_md.seif default."""
    path = DEFAULTS_DIR / "conversa_md.seif"
    if not path.exists():
        return  # skip if defaults not generated
    seq = encode_module(str(path))
    assert seq.qr_count >= 1  # conversa encodes to at least 1 QR
    assert seq.original_words >= 40000  # conversa is large (grows over time)
    assert seq.global_hash is not None


def test_save_sequence():
    """Save sequence creates PNG files."""
    path = _create_temp_module(100)
    seq = encode_module(path)
    with tempfile.TemporaryDirectory() as tmpdir:
        # Monkey-patch output dir
        import seif.context.context_qr as ctx_qr
        original_dir = ctx_qr.OUTPUT_DIR
        ctx_qr.OUTPUT_DIR = Path(tmpdir)
        try:
            paths = save_sequence(seq, prefix="test")
            assert len(paths) == seq.qr_count
            assert all(p.exists() for p in paths)
            assert all(p.suffix == ".png" for p in paths)
        finally:
            ctx_qr.OUTPUT_DIR = original_dir


# --- Round-trip tests (require seif-engine for QR decoding) ---

def test_round_trip_small():
    """Encode → images → decode → verify."""
    pytest.importorskip("seif.analysis.qr_decoder", reason="QR decode requires seif-engine")
    path = _create_temp_module(100)
    seq = encode_module(path, with_overlay=False)

    # Decode from PIL images
    images = [c.image for c in seq.chunks]
    result = decode_sequence(images)

    assert result.success, f"Decode failed: {result.error}"
    assert result.hash_verified
    assert result.module is not None
    assert result.module.source == "test_source.md"


def test_round_trip_preserves_summary():
    """Summary text survives encode → decode round-trip."""
    pytest.importorskip("seif.analysis.qr_decoder", reason="QR decode requires seif-engine")
    path = _create_temp_module(150)

    # Read original
    with open(path) as f:
        original = json.load(f)

    seq = encode_module(path, with_overlay=False)
    images = [c.image for c in seq.chunks]
    result = decode_sequence(images)

    assert result.success
    assert result.module.summary == original["summary"]
    assert result.module.integrity_hash == original["integrity_hash"]


def test_round_trip_default_conversa():
    """Round-trip the real conversa_md.seif."""
    path = DEFAULTS_DIR / "conversa_md.seif"
    if not path.exists():
        return

    with open(path) as f:
        original = json.load(f)

    seq = encode_module(str(path), with_overlay=False)
    images = [c.image for c in seq.chunks]
    result = decode_sequence(images)

    assert result.success, f"Decode failed: {result.error}"
    assert result.hash_verified
    assert result.module.source == original["source"]
    assert result.module.compressed_words == original["compressed_words"]


def test_missing_chunk_fails():
    """Missing a chunk produces a clear error."""
    path = _create_temp_module(300)
    seq = encode_module(path, with_overlay=False)

    if len(seq.chunks) < 2:
        return  # need multi-chunk for this test

    # Only provide first chunk
    images = [seq.chunks[0].image]
    result = decode_sequence(images)
    assert not result.success
    assert "Missing" in (result.error or "")


def test_describe_output():
    """Describe produces readable text."""
    path = _create_temp_module(100)
    seq = encode_module(path)
    text = describe(seq)
    assert "SEIF CONTEXT QR" in text
    assert "QR codes:" in text


if __name__ == "__main__":
    import inspect
    tests = [obj for name, obj in inspect.getmembers(sys.modules[__name__])
             if inspect.isfunction(obj) and name.startswith("test_")]
    passed = failed = skipped = 0
    for fn in sorted(tests, key=lambda f: f.__name__):
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {fn.__name__}: {e}")
            failed += 1
        except BaseException as e:
            # pytest.skip.Exception inherits BaseException — treat as skip
            print(f"  ~ {fn.__name__}: skipped ({e})")
            skipped += 1
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    sys.exit(1 if failed else 0)
