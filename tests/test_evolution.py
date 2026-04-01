"""Tests for Evolution Tracker and Session Resonance Score."""

import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from seif.context import evolution
from seif.context.telemetry import _compute_session_score, TurnRecord


# === Session Resonance Score tests ===

def _make_turn(user_coherence, asst_coherence, user_gate="OPEN", asst_gate="OPEN"):
    """Helper to create a minimal TurnRecord."""
    return TurnRecord(
        session_id="test",
        turn_number=1,
        timestamp="2026-01-01T00:00:00Z",
        user_text="test",
        user_ascii_root=9,
        user_ascii_phase="SINGULARITY",
        user_ascii_gate=user_gate,
        user_resonance_coherence=user_coherence,
        user_resonance_gate=user_gate,
        user_mode="PLENITUDE",
        user_cosmic_anchors=[],
        user_asymmetry="test",
        assistant_text="test",
        assistant_resonance_coherence=asst_coherence,
        assistant_resonance_gate=asst_gate,
    )


def test_session_score_bounded():
    """Score must be between 0 and 1."""
    turns = [_make_turn(0.9, 0.9) for _ in range(5)]
    coherences_u = [0.9] * 5
    coherences_a = [0.9] * 5
    result = _compute_session_score(turns, coherences_u, coherences_a)
    assert 0 <= result["score"] <= 1.0


def test_session_score_empty():
    """Empty turns return NO_DATA."""
    result = _compute_session_score([], [], [])
    assert result["status"] == "NO_DATA"
    assert result["score"] == 0.0


def test_session_score_high_coherence():
    """All gates open + high coherence → high score."""
    turns = [_make_turn(0.95, 0.95) for _ in range(6)]
    result = _compute_session_score(turns, [0.95]*6, [0.95]*6)
    assert result["score"] > 0.5
    assert result["gate_ratio"] == 1.0


def test_session_score_low_coherence():
    """All gates closed + low coherence → low score."""
    turns = [_make_turn(0.1, 0.1, "CLOSED", "CLOSED") for _ in range(6)]
    result = _compute_session_score(turns, [0.1]*6, [0.1]*6)
    assert result["score"] < 0.5
    assert result["gate_ratio"] == 0.0


def test_session_score_has_all_fields():
    """Result has score, gate_ratio, coherence, evolution, status."""
    turns = [_make_turn(0.7, 0.7) for _ in range(4)]
    result = _compute_session_score(turns, [0.7]*4, [0.7]*4)
    assert "score" in result
    assert "gate_ratio" in result
    assert "coherence" in result
    assert "evolution" in result
    assert "status" in result


def test_session_score_evolution_neutral():
    """Flat coherence → evolution ≈ 0.5 (neutral)."""
    turns = [_make_turn(0.7, 0.7) for _ in range(8)]
    result = _compute_session_score(turns, [0.7]*8, [0.7]*8)
    assert abs(result["evolution"] - 0.5) < 0.01


def test_session_score_evolution_ascending():
    """Rising coherence → evolution > 0.5."""
    coherences = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    turns = [_make_turn(c, c) for c in coherences]
    result = _compute_session_score(turns, coherences, coherences)
    assert result["evolution"] > 0.5


# === Evolution Tracker tests ===

def test_evolution_record_and_trend():
    """Record sessions and check trend analysis."""
    # Use temp file
    original = evolution.EVOLUTION_FILE
    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            evolution.EVOLUTION_FILE = type(original)(f.name)

        # Record 4 sessions with ascending scores
        for i, score_val in enumerate([0.3, 0.4, 0.6, 0.8]):
            evolution.record_session(
                session_id=f"test_{i}",
                score={"score": score_val, "gate_ratio": 0.5, "coherence": 0.5, "evolution": 0.5, "status": "DEVELOPING"},
                total_turns=5,
            )

        trend = evolution.get_evolution_trend()
        assert trend["total_sessions"] == 4
        assert trend["trend"] == "ASCENDING"
        assert trend["avg_score"] > 0
        assert trend["best_session"]["session_id"] == "test_3"
    finally:
        evolution.EVOLUTION_FILE = original
        try:
            os.unlink(f.name)
        except:
            pass


def test_evolution_human_intentions():
    """Human intentions are recorded and retrievable."""
    original = evolution.EVOLUTION_FILE
    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            evolution.EVOLUTION_FILE = type(original)(f.name)

        evolution.record_session(
            session_id="intent_test",
            score={"score": 0.7, "gate_ratio": 0.5, "coherence": 0.5, "evolution": 0.5, "status": "RESONANT"},
            total_turns=10,
            human_intention="Validar a prova de unicidade do sistema 3-6-9",
        )

        intentions = evolution.get_human_intentions()
        assert len(intentions) == 1
        assert "unicidade" in intentions[0]["intention"]
        assert intentions[0]["score"] == 0.7
    finally:
        evolution.EVOLUTION_FILE = original
        try:
            os.unlink(f.name)
        except:
            pass


def test_evolution_empty():
    """Empty evolution returns NO_DATA."""
    original = evolution.EVOLUTION_FILE
    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            evolution.EVOLUTION_FILE = type(original)(f.name)
        # Write empty array
        with open(f.name, "w") as fh:
            json.dump([], fh)

        trend = evolution.get_evolution_trend()
        assert trend["trend"] == "NO_DATA"
        assert trend["total_sessions"] == 0
    finally:
        evolution.EVOLUTION_FILE = original
        try:
            os.unlink(f.name)
        except:
            pass


# === Intent Drift tests ===

def test_intent_drift_no_history():
    """No prior intentions → no_history."""
    original = evolution.EVOLUTION_FILE
    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            evolution.EVOLUTION_FILE = type(original)(f.name)
        with open(f.name, "w") as fh:
            json.dump([], fh)

        result = evolution.measure_intent_drift("test intention")
        assert result["resonance"] == "no_history"
        assert result["similarity"] == 1.0
    finally:
        evolution.EVOLUTION_FILE = original
        try:
            os.unlink(f.name)
        except:
            pass


def test_intent_drift_persistent():
    """Same intention text → persistent."""
    original = evolution.EVOLUTION_FILE
    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            evolution.EVOLUTION_FILE = type(original)(f.name)

        intention = "Validar a prova de unicidade do sistema 3-6-9"
        evolution.record_session(
            session_id="drift_test_1",
            score={"score": 0.8, "status": "RESONANT"},
            total_turns=5,
            human_intention=intention,
        )

        result = evolution.measure_intent_drift(intention)
        assert result["resonance"] == "persistent"
        assert result["similarity"] == 1.0
    finally:
        evolution.EVOLUTION_FILE = original
        try:
            os.unlink(f.name)
        except:
            pass


def test_intent_drift_shifted():
    """Completely different intention → shifted."""
    original = evolution.EVOLUTION_FILE
    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            evolution.EVOLUTION_FILE = type(original)(f.name)

        evolution.record_session(
            session_id="drift_test_2",
            score={"score": 0.8, "status": "RESONANT"},
            total_turns=5,
            human_intention="Validar a prova de unicidade do sistema 3-6-9",
        )

        result = evolution.measure_intent_drift("Comprar leite no mercado")
        assert result["resonance"] == "shifted"
        assert result["similarity"] < 0.4
    finally:
        evolution.EVOLUTION_FILE = original
        try:
            os.unlink(f.name)
        except:
            pass


def test_intent_hash_stored():
    """Intent hash is stored when intention is provided."""
    original = evolution.EVOLUTION_FILE
    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            evolution.EVOLUTION_FILE = type(original)(f.name)

        evolution.record_session(
            session_id="hash_test",
            score={"score": 0.7, "status": "DEVELOPING"},
            total_turns=3,
            human_intention="Test intention",
        )

        intentions = evolution.get_human_intentions()
        assert intentions[0]["intent_hash"] is not None
        assert len(intentions[0]["intent_hash"]) == 64  # sha256 hex
    finally:
        evolution.EVOLUTION_FILE = original
        try:
            os.unlink(f.name)
        except:
            pass


def test_rolling_window():
    """Records beyond MAX_HISTORY are trimmed."""
    original = evolution.EVOLUTION_FILE
    original_max = evolution.MAX_HISTORY
    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            evolution.EVOLUTION_FILE = type(original)(f.name)
        evolution.MAX_HISTORY = 5  # small window for testing

        for i in range(8):
            evolution.record_session(
                session_id=f"window_{i}",
                score={"score": 0.5 + i * 0.05, "status": "DEVELOPING"},
                total_turns=3,
            )

        records = evolution._load_evolution()
        assert len(records) <= 5
        # Most recent should be preserved
        assert records[-1]["session_id"] == "window_7"
    finally:
        evolution.EVOLUTION_FILE = original
        evolution.MAX_HISTORY = original_max
        try:
            os.unlink(f.name)
        except:
            pass


# === Runner ===

if __name__ == "__main__":
    passed = 0
    failed = 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {test_fn.__name__}: {e}")

    print(f"{passed} passed, {failed} failed")
