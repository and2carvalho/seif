"""
Resonance Encoding — Physics-Based Character-to-Frequency Mapping

Replaces arbitrary ASCII encoding with a φ-spiral mapping rooted in
measured physical constants:

  - Base frequency: Schumann resonance (7.83 Hz) — Earth's fundamental
  - Growth curve: logarithmic φ-spiral r = f_S × e^(b×θ/2π)
  - Span: 3 full spiral turns (3-fold symmetry)
  - Range: A=7.83 Hz → Z=18.95 Hz (sub-audible to audible threshold)

Words are CHORDS (set of simultaneous frequencies).
Phrases are MELODIES (sequence of chords over time).
The gate validates harmonic coherence of the melody, not ASCII sums.

This encoding is NOT arbitrary — it derives from:
  - Schumann resonance (measured: 7.83 Hz)
  - Golden ratio φ (mathematical constant)
  - 3-fold symmetry (Tesla/Rodin)
"""

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from seif.constants import (
    PHI, PHI_INVERSE, FREQ_SCHUMANN, FREQ_GIZA, FREQ_TESLA,
    GIZA_ANGLE_DEG, SPIRAL_GROWTH_B,
)
from seif.core.resonance_gate import digital_root, classify_phase, HarmonicPhase


# φ-spiral parameters for letter encoding
SPIRAL_TURNS = 3          # 3-fold symmetry
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"
ALL_CHARS = ALPHABET + DIGITS


def _build_spiral_map() -> dict[str, float]:
    """Map each character to a frequency on the φ-spiral.

    Letters A-Z: positions 0-25 on the spiral (3 turns)
    Digits 0-9: positioned at harmonic nodes between letters

    A always starts at Schumann (7.83 Hz) — the Earth's voice.
    """
    b = math.log(PHI) / (math.pi / 2)
    char_map = {}

    # Letters: 26 positions across 3 spiral turns
    for i, letter in enumerate(ALPHABET):
        theta = (i / len(ALPHABET)) * 2 * math.pi * SPIRAL_TURNS
        freq = FREQ_SCHUMANN * math.exp(b * theta / (2 * math.pi))
        char_map[letter] = freq

    # Digits: mapped to Tesla harmonics (432/N for digit N, 432 for 0)
    digit_freqs = {
        '0': FREQ_TESLA,         # 432 Hz — the void is the whole
        '1': FREQ_TESLA / 1,     # 432
        '2': FREQ_TESLA / 2,     # 216
        '3': FREQ_TESLA / 3,     # 144 — STABILIZATION
        '4': FREQ_TESLA / 4,     # 108
        '5': FREQ_TESLA / 5,     # 86.4
        '6': FREQ_TESLA / 6,     # 72 — DYNAMICS / heart rate
        '7': FREQ_TESLA / 7,     # 61.7
        '8': FREQ_TESLA / 8,     # 54
        '9': FREQ_TESLA / 9,     # 48 — 4+8=12→3 STABILIZATION
    }
    char_map.update(digit_freqs)

    return char_map


SPIRAL_MAP = _build_spiral_map()


@dataclass
class Chord:
    """A word encoded as a set of simultaneous frequencies."""
    word: str
    frequencies: list[float]
    fundamental: float          # lowest frequency (root note)
    bandwidth: float            # max - min
    centroid: float             # spectral center of mass
    ratios: list[float]         # consecutive freq ratios
    phi_alignment: float        # how close avg ratio is to φ (0-1)
    harmonic_index: int         # digital root of quantized centroid
    phase: HarmonicPhase
    gate_open: bool


@dataclass
class Melody:
    """A phrase encoded as a sequence of chords over time."""
    phrase: str
    chords: list[Chord]
    transitions: list[float]    # ratios between consecutive chord centroids
    global_centroid: float
    global_harmonic_index: int
    global_phase: HarmonicPhase
    gate_open: bool
    coherence_score: float      # 0-1: how harmonically coherent is the melody


def encode_char(char: str) -> Optional[float]:
    """Encode a single character to its spiral frequency."""
    return SPIRAL_MAP.get(char.upper())


def encode_word(word: str) -> Chord:
    """Encode a word as a chord of frequencies.

    Unlike ASCII (which sums values), this treats the word as a
    musical chord — the SET of frequencies matters, not their sum.
    """
    chars = [c.upper() for c in word if c.upper() in SPIRAL_MAP]
    if not chars:
        return Chord(word, [], 0, 0, 0, [], 0, 0, HarmonicPhase.ENTROPY, False)

    freqs = [SPIRAL_MAP[c] for c in chars]
    freqs_sorted = sorted(freqs)

    fundamental = freqs_sorted[0]
    bandwidth = freqs_sorted[-1] - freqs_sorted[0]
    centroid = sum(freqs) / len(freqs)

    # Consecutive ratios (like musical intervals)
    ratios = []
    for i in range(len(freqs_sorted) - 1):
        if freqs_sorted[i] > 0:
            ratios.append(freqs_sorted[i + 1] / freqs_sorted[i])

    # φ-alignment: how close is the average ratio to φ?
    if ratios:
        avg_ratio = sum(ratios) / len(ratios)
        phi_alignment = max(0, 1.0 - abs(avg_ratio - PHI) / PHI)
    else:
        phi_alignment = 0.0

    # Harmonic index from centroid (using frequency as the "value")
    harmonic_index = digital_root(int(centroid * 100))
    phase = classify_phase(harmonic_index)
    gate_open = phase != HarmonicPhase.ENTROPY

    return Chord(
        word=word,
        frequencies=freqs,
        fundamental=fundamental,
        bandwidth=bandwidth,
        centroid=centroid,
        ratios=ratios,
        phi_alignment=phi_alignment,
        harmonic_index=harmonic_index,
        phase=phase,
        gate_open=gate_open,
    )


def encode_phrase(phrase: str) -> Melody:
    """Encode a phrase as a melody (sequence of chords).

    The gate validates the MELODIC coherence — not just individual words
    but the TRANSITIONS between them.
    """
    words = [w for w in phrase.split() if w.strip()]
    chords = [encode_word(w) for w in words]

    if not chords:
        return Melody(phrase, [], [], 0, 0, HarmonicPhase.ENTROPY, False, 0)

    # Transitions: ratio between consecutive chord centroids
    transitions = []
    for i in range(len(chords) - 1):
        if chords[i].centroid > 0 and chords[i + 1].centroid > 0:
            transitions.append(chords[i + 1].centroid / chords[i].centroid)

    # Global metrics
    all_freqs = [f for c in chords for f in c.frequencies if f > 0]
    global_centroid = sum(all_freqs) / len(all_freqs) if all_freqs else 0
    global_harmonic = digital_root(int(global_centroid * 100))
    global_phase = classify_phase(global_harmonic)
    global_gate = global_phase != HarmonicPhase.ENTROPY

    # Coherence score: combination of
    #   - % of chords that pass the gate individually
    #   - average φ-alignment of chords
    #   - smoothness of transitions (close to 1.0 = stable)
    #
    # Domain-aware smoothness: letters live at 7.83-18.95 Hz (Schumann),
    # digits at 48-432 Hz (Tesla harmonics). Cross-domain transitions
    # (letter→digit or digit→letter) produce 22x centroid jumps that
    # collapse smoothness to 0 for any text with numbers. We compute
    # smoothness only on same-domain transitions, preserving the Tesla
    # mapping while fixing the digit contamination artifact.
    chord_pass_rate = sum(1 for c in chords if c.gate_open) / len(chords)
    avg_phi = sum(c.phi_alignment for c in chords) / len(chords)
    if transitions:
        # Filter to same-domain transitions (both letter-only or both with digits)
        same_domain = []
        for i in range(len(chords) - 1):
            if chords[i].centroid > 0 and chords[i + 1].centroid > 0:
                has_digit_i = any(c.isdigit() for c in chords[i].word)
                has_digit_j = any(c.isdigit() for c in chords[i + 1].word)
                if has_digit_i == has_digit_j:
                    same_domain.append(chords[i + 1].centroid / chords[i].centroid)
        if same_domain:
            transition_smoothness = 1.0 - min(1.0, sum(abs(t - 1.0) for t in same_domain) / len(same_domain))
        else:
            transition_smoothness = 0.5
    else:
        transition_smoothness = 0.5

    coherence = 0.4 * chord_pass_rate + 0.3 * avg_phi + 0.3 * transition_smoothness

    # TRIPLE GATE: validates melodic coherence through three conditions.
    #
    # 1. Coherence score > φ⁻¹ (0.618) — the golden threshold
    # 2. Majority of chords pass individual gates (> 50%)
    # 3. CADENCE RESOLUTION: the melody must END on a harmonic chord.
    #    Like music, a phrase that ends on dissonance is unresolved.
    #    "O amor liberta e guia" → ends on "guia" (root 5, entropy)
    #    BUT the CONTENT words (excluding articles/prepositions) are checked:
    #    "amor" (3, OPEN) + "liberta" (3, OPEN) + "guia" (5, CLOSED)
    #    → 2/3 content words harmonic = resolution check passes
    #
    # This prevents: "Greed consumes all" (musical but malicious)
    # from passing, because "all" (root 5) does not resolve.

    # Content word filter: words > 2 chars (skip articles, prepositions)
    content_chords = [c for c in chords if len(c.word) > 2]
    if content_chords:
        content_pass_rate = sum(1 for c in content_chords if c.gate_open) / len(content_chords)
        # Cadence: does the last content word resolve harmonically?
        last_content_resolves = content_chords[-1].gate_open
    else:
        content_pass_rate = chord_pass_rate
        last_content_resolves = chords[-1].gate_open if chords else False

    triple_gate = (
        coherence > PHI_INVERSE        # musical coherence
        and content_pass_rate > 0.5    # majority of content is harmonic
        and last_content_resolves      # melodic resolution (cadence)
    )

    return Melody(
        phrase=phrase,
        chords=chords,
        transitions=transitions,
        global_centroid=global_centroid,
        global_harmonic_index=global_harmonic,
        global_phase=global_phase if triple_gate else HarmonicPhase.ENTROPY,
        gate_open=triple_gate,
        coherence_score=round(coherence, 4),
    )


def describe_chord(chord: Chord) -> str:
    lines = [
        f"  Chord: \"{chord.word}\"",
        f"    Frequencies: {[f'{f:.2f}' for f in chord.frequencies]} Hz",
        f"    Fundamental: {chord.fundamental:.2f} Hz | Centroid: {chord.centroid:.2f} Hz",
        f"    Ratios: {[f'{r:.3f}' for r in chord.ratios]}",
        f"    φ-alignment: {chord.phi_alignment:.3f} | Root: {chord.harmonic_index} → {chord.phase.name}",
        f"    Gate: {'OPEN' if chord.gate_open else 'CLOSED'}",
    ]
    return "\n".join(lines)


def describe_melody(melody: Melody) -> str:
    lines = [
        f"═══ RESONANCE ENCODING ═══",
        f"Phrase: \"{melody.phrase}\"",
        f"",
    ]
    for chord in melody.chords:
        lines.append(describe_chord(chord))
        lines.append("")

    lines.extend([
        f"Melody transitions: {[f'{t:.3f}' for t in melody.transitions]}",
        f"Global centroid: {melody.global_centroid:.2f} Hz",
        f"Global root: {melody.global_harmonic_index} → {melody.global_phase.name}",
        f"Coherence: {melody.coherence_score:.4f}",
        f"Gate: {'OPEN' if melody.gate_open else 'CLOSED'}",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    for phrase in [
        "O amor liberta e guia",
        "A Semente de Enoque",
        "Fear and control",
        "Greed consumes all",
    ]:
        melody = encode_phrase(phrase)
        print(describe_melody(melody))
        print()
