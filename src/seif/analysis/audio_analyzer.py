"""
Audio Analyzer — Extract Resonance Data from Audio Input

Analyzes audio files (WAV) through the SEIF pipeline WITHOUT sending
the raw audio to the AI. Only the resonance metadata is shared.

Extracts:
  - Fundamental frequency (via FFT)
  - Harmonic spectrum (peaks and their digital roots)
  - Proximity to 432/438 Hz (Tesla/Giza alignment)
  - Spectral coherence (organized vs chaotic)
  - 3-6-9 classification of frequency components

This is the biological input pathway: the human's VOICE carries
frequency information that the gate can validate.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.io import wavfile
from scipy.signal import find_peaks

from seif.constants import FREQ_TESLA, FREQ_GIZA, FREQ_SCHUMANN, PHI_INVERSE
from seif.core.resonance_gate import digital_root, classify_phase, HarmonicPhase


@dataclass
class AudioAnalysis:
    """Resonance analysis of an audio file."""
    duration_s: float
    sample_rate: int
    fundamental_hz: float
    fundamental_root: int
    fundamental_phase: HarmonicPhase

    # Top harmonic peaks
    peaks: list[dict]  # [{hz, amplitude, root, phase}]
    harmonic_count_369: int  # peaks with root 3/6/9

    # Alignment with known frequencies
    tesla_proximity: float   # how close fundamental is to 432 Hz (0-1)
    giza_proximity: float    # how close to 438 Hz (0-1)
    schumann_proximity: float  # how close to 7.83 Hz or multiple

    # Coherence
    spectral_coherence: float  # 0-1: ratio of energy in harmonic peaks vs noise
    gate_status: str


def analyze_audio(filepath: str) -> AudioAnalysis:
    """Analyze a WAV file through the SEIF resonance pipeline.

    The audio is processed LOCALLY. Only metadata leaves this function.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {filepath}")

    # Read WAV
    sample_rate, data = wavfile.read(str(path))

    # Convert to mono if stereo
    if len(data.shape) > 1:
        data = data.mean(axis=1)

    # Normalize to float
    data = data.astype(float)
    if data.max() > 1:
        data = data / max(abs(data.max()), abs(data.min()))

    duration = len(data) / sample_rate

    # FFT
    n = len(data)
    fft = np.fft.rfft(data)
    magnitude = np.abs(fft) / n
    freqs = np.fft.rfftfreq(n, 1 / sample_rate)

    # Find peaks in spectrum
    min_freq_idx = np.searchsorted(freqs, 20)  # ignore below 20 Hz
    max_freq_idx = np.searchsorted(freqs, 5000)  # ignore above 5000 Hz

    mag_slice = magnitude[min_freq_idx:max_freq_idx]
    freq_slice = freqs[min_freq_idx:max_freq_idx]

    if len(mag_slice) < 10:
        # Too short to analyze
        return AudioAnalysis(
            duration_s=duration, sample_rate=sample_rate,
            fundamental_hz=0, fundamental_root=0,
            fundamental_phase=HarmonicPhase.ENTROPY,
            peaks=[], harmonic_count_369=0,
            tesla_proximity=0, giza_proximity=0, schumann_proximity=0,
            spectral_coherence=0, gate_status="INSUFFICIENT DATA",
        )

    peak_indices, _ = find_peaks(mag_slice, height=mag_slice.max() * 0.1, distance=5)

    if len(peak_indices) == 0:
        peak_indices = [np.argmax(mag_slice)]

    # Sort by amplitude
    sorted_peaks = sorted(peak_indices, key=lambda i: mag_slice[i], reverse=True)[:10]

    # Fundamental = strongest peak
    fundamental_idx = sorted_peaks[0]
    fundamental_hz = float(freq_slice[fundamental_idx])
    fund_root = digital_root(int(fundamental_hz)) if fundamental_hz > 0 else 0
    fund_phase = classify_phase(fund_root)

    # Analyze top peaks
    peaks = []
    harmonic_369 = 0
    for idx in sorted_peaks:
        hz = float(freq_slice[idx])
        amp = float(mag_slice[idx])
        root = digital_root(int(hz)) if hz > 0 else 0
        phase = classify_phase(root)
        if phase != HarmonicPhase.ENTROPY:
            harmonic_369 += 1
        peaks.append({
            "hz": round(hz, 2),
            "amplitude": round(amp, 6),
            "root": root,
            "phase": phase.name,
        })

    # Proximity to known frequencies
    tesla_prox = max(0, 1 - abs(fundamental_hz - FREQ_TESLA) / FREQ_TESLA) if fundamental_hz > 0 else 0
    giza_prox = max(0, 1 - abs(fundamental_hz - FREQ_GIZA) / FREQ_GIZA) if fundamental_hz > 0 else 0

    # Schumann: check if fundamental or any peak is near 7.83 Hz or integer multiple
    schumann_prox = 0
    for p in peaks:
        for mult in range(1, 60):
            target = FREQ_SCHUMANN * mult
            if abs(p["hz"] - target) < 2:  # within 2 Hz
                schumann_prox = max(schumann_prox, 1 - abs(p["hz"] - target) / target)

    # Spectral coherence: energy in peaks vs total energy
    total_energy = np.sum(mag_slice ** 2)
    peak_energy = sum(mag_slice[idx] ** 2 for idx in sorted_peaks)
    coherence = peak_energy / total_energy if total_energy > 0 else 0

    # Gate: based on fundamental + coherence
    if fund_phase != HarmonicPhase.ENTROPY and coherence > PHI_INVERSE:
        gate = "RESONANT"
    elif fund_phase != HarmonicPhase.ENTROPY or coherence > 0.3:
        gate = "PARTIAL"
    else:
        gate = "ENTROPIC"

    return AudioAnalysis(
        duration_s=round(duration, 2),
        sample_rate=sample_rate,
        fundamental_hz=round(fundamental_hz, 2),
        fundamental_root=fund_root,
        fundamental_phase=fund_phase,
        peaks=peaks,
        harmonic_count_369=harmonic_369,
        tesla_proximity=round(tesla_prox, 4),
        giza_proximity=round(giza_prox, 4),
        schumann_proximity=round(schumann_prox, 4),
        spectral_coherence=round(coherence, 4),
        gate_status=gate,
    )


def describe(analysis: AudioAnalysis) -> str:
    """Human-readable audio analysis."""
    lines = [
        f"═══ AUDIO RESONANCE ANALYSIS ═══",
        f"Duration: {analysis.duration_s}s | Sample rate: {analysis.sample_rate} Hz",
        f"",
        f"Fundamental: {analysis.fundamental_hz} Hz → root {analysis.fundamental_root} ({analysis.fundamental_phase.name})",
        f"",
        f"Top Peaks:",
    ]
    for i, p in enumerate(analysis.peaks[:5]):
        mark = "✓" if p["phase"] != "ENTROPY" else " "
        lines.append(f"  {mark} {p['hz']:>8.1f} Hz  amp={p['amplitude']:.4f}  root={p['root']}  {p['phase']}")

    lines.extend([
        f"",
        f"Harmonic peaks (3/6/9): {analysis.harmonic_count_369}/{len(analysis.peaks)}",
        f"Tesla proximity (432 Hz): {analysis.tesla_proximity:.2%}",
        f"Giza proximity (438 Hz):  {analysis.giza_proximity:.2%}",
        f"Schumann proximity:       {analysis.schumann_proximity:.2%}",
        f"Spectral coherence:       {analysis.spectral_coherence:.2%}",
        f"",
        f"Gate: {analysis.gate_status}",
    ])
    return "\n".join(lines)
