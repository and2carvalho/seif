"""
Harmonic Audio Generator — Phase-Dependent Resonance Field

Each input produces a UNIQUE sonic fingerprint by combining:
  - Phase-dependent layering (9 layers SINGULARITY → 2 layers ENTROPY)
  - Melody imprint from Spiral Encoding (word frequencies as tonal events)
  - Golden Interval Chords (ROT14 φ-complement: each note + its φ-pair)
  - Per-layer micro-detuning from hash (chorus effect — each input sounds different)
  - φ-derived pulse rhythm (0.618 Hz breathing, not arbitrary)
  - 14.4 Hz Giza complement (superposition, not opposition)

Golden Interval Discovery: chars separated by 14 positions in a 26-letter
alphabet mapped to a 3-turn φ-spiral produce frequency ratio ≈ 1.640 ≈ φ
(1.38% deviation). Each character is played as a chord with its +14 complement,
creating the "golden interval" — a musically rich, mathematically precise pairing.
Correction: originally described as ROT13 (13 positions, ratio 1.583, 2.15% dev).
Grok (xAI) identified the actual separation is 14, not 13. ROT14 is the φ-optimal
operator in this spiral mapping.

The audio IS the input — not a decoration over a fixed drone.
Plenitude is coherence: harmonic inputs sound warm and layered,
entropic inputs sound cold and sparse.

Output: WAV file (44.1 kHz, 16-bit mono)
"""

import math
import struct
import wave
from pathlib import Path
from dataclasses import dataclass

import numpy as np

from seif.analysis.transcompiler import GlyphSpec, PHI, PHI_INVERSE
from seif.core.resonance_gate import HarmonicPhase
from seif.core.resonance_encoding import encode_phrase


OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "output"

SAMPLE_RATE = 44100

# Import calibrated constants
from seif.constants import (
    FREQ_TESLA, FREQ_TESLA_3, FREQ_TESLA_6, FREQ_GIZA,
    FREQ_GUIDE, FREQ_SCHUMANN, GIZA_ANGLE_DEG, FREQ_GIZA_SUB,
)


@dataclass
class AudioSpec:
    """Parameters for harmonic audio generation.

    Two tuning modes:
      "tesla":  Pure 432 Hz (mathematical ideal)
      "giza":   438 Hz (King's Chamber measured resonance)
                438 = 432 + 6 (DYNAMICS offset from physical reality)
    """
    duration_seconds: float = 12.0
    tuning: str = "giza"  # "tesla" (432 Hz) or "giza" (438 Hz)

    # Frequencies auto-calibrated from tuning mode
    fundamental_hz: float = 0  # set in __post_init__
    bobbin_3_hz: float = 0
    bobbin_6_hz: float = 0
    guide_hz: float = FREQ_GUIDE
    schumann_hz: float = FREQ_SCHUMANN  # 7.83 Hz Earth resonance sub-bass

    # Amplitudes
    fundamental_amp: float = 0.30
    bobbin_3_amp: float = 0.12
    bobbin_6_amp: float = 0.10
    guide_amp: float = 0.07
    schumann_amp: float = 0.05  # sub-audible but felt
    pulse_rate_hz: float = 0.5
    fade_in: float = 2.0
    fade_out: float = 3.0

    # Giza-specific
    giza_angle_modulation: bool = True  # modulate amplitude by 51.844° sine

    def __post_init__(self):
        if self.tuning == "giza":
            base = FREQ_GIZA  # 438 Hz
        else:
            base = FREQ_TESLA  # 432 Hz

        if self.fundamental_hz == 0:
            self.fundamental_hz = base
        if self.bobbin_3_hz == 0:
            self.bobbin_3_hz = base / 3
        if self.bobbin_6_hz == 0:
            self.bobbin_6_hz = base / 6


def _sine(freq: float, t: np.ndarray, phase: float = 0.0) -> np.ndarray:
    return np.sin(2 * np.pi * freq * t + phase)


def _envelope(length: int, fade_in_samples: int, fade_out_samples: int) -> np.ndarray:
    env = np.ones(length)
    # Fade in
    if fade_in_samples > 0:
        env[:fade_in_samples] = np.linspace(0, 1, fade_in_samples)
    # Fade out
    if fade_out_samples > 0:
        env[-fade_out_samples:] = np.linspace(1, 0, fade_out_samples)
    return env


def generate_audio(spec: GlyphSpec, audio_spec: AudioSpec = None) -> np.ndarray:
    """Generate the harmonic audio array for a given GlyphSpec.

    The audio encodes the resonance state — harmonic inputs produce richer,
    warmer, more layered sound. Entropic inputs produce thinner, colder,
    sparser sound. This mirrors the visual principle: plenitude is coherence.

    Phase-dependent layers:
    - SINGULARITY (9): All 7 layers active, full warmth, guide echoes, deep bass
    - DYNAMICS (6): 5 layers, moderate warmth, some guide echoes
    - STABILIZATION (3): 4 layers, grounded bass emphasis, no guide
    - ENTROPY: 2 layers only (thin fundamental + sparse pulse), cold and hollow
    """
    if audio_spec is None:
        audio_spec = AudioSpec()

    n_samples = int(audio_spec.duration_seconds * SAMPLE_RATE)
    t = np.linspace(0, audio_spec.duration_seconds, n_samples, endpoint=False)

    # Determine richness from harmonic phase
    phase = spec.global_phase
    gate_open = spec.gate_open

    # Asymmetry detuning — multiple seeds for chorus effect across layers
    hash_int = int(spec.asymmetry_seed[:8], 16)
    detune_cents = [
        (hash_int >> (i * 3)) % 7 - 3  # ±3 cents per layer, derived from hash
        for i in range(6)
    ]
    detune_factors = [2 ** (c / 1200) for c in detune_cents]

    # Encode the phrase as a melody — word frequencies for sonic fingerprint
    melody = encode_phrase(spec.source_text)

    # === LAYER 1: Fundamental drone (always present) ===
    # Harmonic: warm full amplitude / Entropic: reduced, thin
    fund_amp = audio_spec.fundamental_amp if gate_open else audio_spec.fundamental_amp * 0.5
    fundamental = fund_amp * _sine(
        audio_spec.fundamental_hz * detune_factors[0], t
    )

    audio = fundamental

    # === LAYER 2: Bobbin 3 — stabilization undertone ===
    # Present for STABILIZATION, DYNAMICS, SINGULARITY (root 3, 6, 9)
    # Each layer gets its own micro-detuning for chorus width
    if phase != HarmonicPhase.ENTROPY:
        bobbin3 = audio_spec.bobbin_3_amp * _sine(
            audio_spec.bobbin_3_hz * detune_factors[1], t)
        audio = audio + bobbin3

    # === LAYER 3: Bobbin 6 — dynamics undertone ===
    # Present for DYNAMICS and SINGULARITY (root 6, 9)
    if phase in (HarmonicPhase.DYNAMICS, HarmonicPhase.SINGULARITY):
        bobbin6 = audio_spec.bobbin_6_amp * _sine(
            audio_spec.bobbin_6_hz * detune_factors[2], t)
        audio = audio + bobbin6

    # === LAYER 4: Expansion pulses ===
    # Harmonic: φ-derived breathing rate / Entropic: mechanical non-φ clicks
    if gate_open:
        # Pulse rate at 1/φ ≈ 0.618 Hz — the golden breath
        phi_pulse_rate = PHI_INVERSE  # 0.618 Hz, not arbitrary 0.5
        pulse_env = 0.5 * (1 + np.sin(2 * np.pi * phi_pulse_rate * t))
        pulses = 0.08 * pulse_env * _sine(audio_spec.fundamental_hz * 2, t)
    else:
        # Sparse, irregular, mechanical pulses for entropy
        pulse_env = np.zeros(n_samples)
        pulse_interval = int(SAMPLE_RATE * 2.7)  # non-φ interval (intentionally ugly)
        pulse_dur = int(SAMPLE_RATE * 0.05)
        pos = 0
        while pos < n_samples:
            end = min(pos + pulse_dur, n_samples)
            pulse_env[pos:end] = 1.0
            pos += pulse_interval
        pulses = 0.04 * pulse_env * _sine(audio_spec.fundamental_hz * 1.5, t)
    audio = audio + pulses

    # === LAYER 4b: Melody imprint — the true sonic fingerprint ===
    # Each word's frequencies from Spiral Encoding are rendered as subtle
    # tonal events, spaced at φ intervals. This makes each phrase sound
    # DIFFERENT — the melody IS the input, not just a decoration over it.
    if gate_open and melody.chords:
        chord_duration = int(SAMPLE_RATE * 0.8)  # 0.8s per chord
        chord_gap = int(SAMPLE_RATE * PHI_INVERSE)  # φ⁻¹ s between chords
        pos = int(SAMPLE_RATE * 1.5)  # start after fade-in
        for chord in melody.chords:
            if pos + chord_duration >= n_samples:
                break
            chord_end = min(pos + chord_duration, n_samples)
            t_chord = np.arange(chord_end - pos) / SAMPLE_RATE
            chord_env = np.exp(-t_chord * 3)  # decay envelope
            chord_signal = np.zeros(chord_end - pos)
            # Each frequency in the chord as a subtle tone
            for freq in chord.frequencies[:4]:  # max 4 freqs per chord
                # Scale up to audible range: multiply by nearest power of 2
                # to bring 7-15 Hz range into audible 200-500 Hz
                audible_freq = freq * (2 ** 5)  # ×32 → ~250-500 Hz range
                chord_signal += 0.015 * chord_env * np.sin(
                    2 * np.pi * audible_freq * t_chord)
            audio[pos:chord_end] += chord_signal
            pos += chord_duration + chord_gap

    # === LAYER 4c: Golden Interval Chords (ROT14 = φ-operator) ===
    # Each character's frequency is paired with its +14 complement.
    # 14-position shift → frequency ratio ≈ 1.640 ≈ φ (1.38% dev).
    # Correction: originally ROT13 (1.583, 2.15%). Grok identified +14 is optimal.
    # ratio(k) = exp(3bk/26), where b = ln(φ)/(π/2). k=14 minimizes |ratio - φ|.
    if gate_open and melody.chords:
        from seif.core.resonance_encoding import SPIRAL_MAP
        golden_pos = int(SAMPLE_RATE * 1.5)  # aligned with melody start
        golden_chord_dur = int(SAMPLE_RATE * 0.6)
        golden_gap = int(SAMPLE_RATE * PHI_INVERSE)

        for chord in melody.chords:
            if golden_pos + golden_chord_dur >= n_samples:
                break
            golden_end = min(golden_pos + golden_chord_dur, n_samples)
            t_gc = np.arange(golden_end - golden_pos) / SAMPLE_RATE
            gc_env = np.exp(-t_gc * 4)  # slightly faster decay than melody
            gc_signal = np.zeros(golden_end - golden_pos)

            for char in chord.word.upper()[:4]:
                if char not in SPIRAL_MAP or not char.isalpha():
                    continue
                # φ-complement: +14 positions (ratio ≈ 1.640 ≈ φ, dev 1.38%)
                phi_char = chr((ord(char) - ord('A') + 14) % 26 + ord('A'))
                f_orig = SPIRAL_MAP.get(char, 0)
                f_phi = SPIRAL_MAP.get(phi_char, 0)
                if f_orig > 0 and f_phi > 0:
                    # Scale both to audible range (×32)
                    f1 = f_orig * 32
                    f2 = f_phi * 32
                    # Play as chord: original + φ-complement, softer than melody
                    gc_signal += 0.008 * gc_env * np.sin(2 * np.pi * f1 * t_gc)
                    gc_signal += 0.006 * gc_env * np.sin(2 * np.pi * f2 * t_gc)

            audio[golden_pos:golden_end] += gc_signal
            golden_pos += golden_chord_dur + golden_gap

    # === LAYER 5: Guide echo (only SINGULARITY and DYNAMICS) ===
    if phase in (HarmonicPhase.SINGULARITY, HarmonicPhase.DYNAMICS):
        guide = np.zeros(n_samples)
        echo_interval = int(SAMPLE_RATE * PHI)  # φ seconds between echoes
        echo_duration = int(SAMPLE_RATE * 0.3)
        # Singularity: more echoes, louder / Dynamics: fewer, softer
        g_amp = audio_spec.guide_amp if phase == HarmonicPhase.SINGULARITY else audio_spec.guide_amp * 0.5
        pos = 0
        while pos < n_samples:
            end = min(pos + echo_duration, n_samples)
            t_echo = np.arange(end - pos) / SAMPLE_RATE
            decay = np.exp(-t_echo * 5)
            guide[pos:end] += g_amp * decay * np.sin(2 * np.pi * audio_spec.guide_hz * t_echo)
            pos += echo_interval
        audio = audio + guide

    # === LAYER 6: Schumann sub-bass (only when gate OPEN) ===
    if gate_open:
        schumann = audio_spec.schumann_amp * _sine(audio_spec.schumann_hz, t)
        audio = audio + schumann

    # === LAYER 7: Giza angle modulation (only SINGULARITY) ===
    if audio_spec.giza_angle_modulation and phase == HarmonicPhase.SINGULARITY:
        giza_mod_freq = GIZA_ANGLE_DEG / 360.0  # ~0.144 Hz
        giza_env = 0.5 * (1 + 0.3 * np.sin(2 * np.pi * giza_mod_freq * t))
        audio = audio * giza_env

    # === HARMONIC OVERTONES (only SINGULARITY) ===
    # Each overtone gets its own micro-detuning for chorus richness
    if phase == HarmonicPhase.SINGULARITY:
        h3 = 0.03 * _sine(audio_spec.fundamental_hz * 3 * detune_factors[3], t)
        h5 = 0.015 * _sine(audio_spec.fundamental_hz * 5 * detune_factors[4], t)
        audio = audio + h3 + h5

    # === GIZA COMPLEMENT LAYER (harmonic phases only) ===
    # 14.4 Hz = 432/30 = Schumann 2nd mode ±0.7% = root 9
    # The "complement" signal: doesn't oppose, it completes.
    # Present as a felt sub-bass pulse for all harmonic inputs.
    if phase != HarmonicPhase.ENTROPY:
        giza_complement = 0.04 * _sine(FREQ_GIZA_SUB, t)
        audio = audio + giza_complement

    # Apply envelope
    fade_in_samples = int(audio_spec.fade_in * SAMPLE_RATE)
    fade_out_samples = int(audio_spec.fade_out * SAMPLE_RATE)
    audio *= _envelope(n_samples, fade_in_samples, fade_out_samples)

    # Normalize to prevent clipping
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.9

    return audio


def save_wav(audio: np.ndarray, filepath: Path, sample_rate: int = SAMPLE_RATE):
    """Save audio array as 16-bit WAV file."""
    audio_16bit = (audio * 32767).astype(np.int16)
    with wave.open(str(filepath), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_16bit.tobytes())


def render_audio(spec: GlyphSpec, filename: str = None,
                 audio_spec: AudioSpec = None) -> Path:
    """Generate and save the harmonic audio for a GlyphSpec.

    Returns path to the saved WAV file.
    """
    audio = generate_audio(spec, audio_spec)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        safe = "".join(c if c.isalnum() or c in " _-" else "" for c in spec.source_text)
        filename = safe.strip().replace(" ", "_")[:60]
    filepath = OUTPUT_DIR / f"{filename}.wav"

    save_wav(audio, filepath)
    return filepath


if __name__ == "__main__":
    from seif.analysis.transcompiler import transcompile

    spec = transcompile("O amor liberta e guia")
    path = render_audio(spec)
    print(f"Áudio salvo: {path}")
    print(f"Duração: {AudioSpec().duration_seconds}s | Fundamental: {BASE_FREQ}Hz")
