"""
SEIF Watermark — Infrasound Text Embedding in Audio Files

Embeds SEIF-encoded text as infrasound tones (7.83–18.95 Hz) inside audio files.
All letter frequencies are below 20 Hz = inaudible to humans.

Encoding:
  - Each character maps to a frequency via the φ-spiral (resonance_encoding.SPIRAL_MAP)
  - Letters: 7.83 Hz (A) to 18.95 Hz (Z) — all infrasound
  - Digits: 48–432 Hz (Tesla harmonics) — audible, placed at low amplitude
  - Symbol duration: configurable (default 4s for reliable FFT extraction)
  - Repetition coding: each symbol repeated N times for noise resilience

Design trade-off (documented, Grok session 4):
  The φ-spiral is informationally sub-optimal for watermarking (linear spacing
  gives better BER for same SNR). The φ-spiral is kept because:
  1. It reuses the existing SEIF encoding (no second alphabet)
  2. The coherence measurement IS the protocol's purpose
  3. A future 2D encoding (freq + phase) could exploit the spiral geometry

Detection:
  - FFT per symbol window → peak frequency → nearest SPIRAL_MAP entry
  - Repetition decoding: majority vote across N repetitions per symbol
  - Robust against music, 50 Hz hum, and mild noise (σ ≤ 0.01)

Output: modified WAV file with infrasound layer added to carrier audio.
"""

import wave
from dataclasses import dataclass
from typing import Optional

import numpy as np

from seif.core.resonance_encoding import SPIRAL_MAP


# Inverse map: frequency → character (for decoding)
_FREQ_TO_CHAR = {freq: char for char, freq in SPIRAL_MAP.items()}
_FREQ_LIST = sorted(SPIRAL_MAP.values())
_CHAR_BY_FREQ = sorted(SPIRAL_MAP.items(), key=lambda x: x[1])

# Only infrasound characters (letters A-Z, all below 20 Hz)
INFRASOUND_CHARS = {ch: freq for ch, freq in SPIRAL_MAP.items()
                    if freq < 20.0 and ch.isalpha()}

SAMPLE_RATE = 44100


@dataclass
class WatermarkConfig:
    """Configuration for watermark embedding/extraction."""
    symbol_duration: float = 4.0      # seconds per symbol
    repetitions: int = 3              # repeat each symbol N times for resilience
    amplitude: float = 0.005          # infrasound amplitude (very low — inaudible)
    sample_rate: int = SAMPLE_RATE
    fade_samples: int = 200           # crossfade between symbols to avoid clicks
    digits_enabled: bool = False      # digits are audible (48-432 Hz) — off by default


def _nearest_char(freq: float, config: WatermarkConfig) -> Optional[str]:
    """Find the nearest character for a detected frequency."""
    best_char = None
    best_dist = float('inf')
    for char, char_freq in SPIRAL_MAP.items():
        if not config.digits_enabled and char.isdigit():
            continue
        dist = abs(freq - char_freq)
        if dist < best_dist:
            best_dist = dist
            best_char = char
    # Reject if too far from any known frequency (> 50% of min spacing)
    if best_dist > 0.3:
        return None
    return best_char


def _text_to_symbols(text: str, config: WatermarkConfig) -> list[str]:
    """Convert text to a list of encodable symbols (uppercase, filtered)."""
    symbols = []
    for ch in text.upper():
        if ch == ' ':
            continue  # spaces are implicit (not encoded)
        if ch in SPIRAL_MAP:
            if ch.isdigit() and not config.digits_enabled:
                continue
            symbols.append(ch)
    return symbols


def encode_watermark(text: str, carrier: np.ndarray,
                     config: WatermarkConfig = None) -> np.ndarray:
    """Embed text as infrasound watermark into a carrier audio signal.

    Args:
        text: Text to embed (will be uppercased, spaces removed)
        carrier: Audio signal as numpy array (mono, float64)
        config: Watermark configuration

    Returns:
        Modified carrier with infrasound watermark added
    """
    if config is None:
        config = WatermarkConfig()

    symbols = _text_to_symbols(text, config)
    if not symbols:
        return carrier.copy()

    # Total duration needed for the watermark
    samples_per_symbol = int(config.symbol_duration * config.sample_rate)
    total_symbols = len(symbols) * config.repetitions
    total_samples = total_symbols * samples_per_symbol

    # Generate watermark signal (full length — carrier extended if needed)
    watermark = np.zeros(total_samples)

    for rep in range(config.repetitions):
        for i, sym in enumerate(symbols):
            idx = (rep * len(symbols) + i) * samples_per_symbol
            end = idx + samples_per_symbol
            if end > len(watermark):
                break

            freq = SPIRAL_MAP[sym]
            t = np.arange(samples_per_symbol) / config.sample_rate
            tone = config.amplitude * np.sin(2 * np.pi * freq * t)

            # Apply fade in/out to prevent clicks
            fade = config.fade_samples
            if fade > 0 and samples_per_symbol > 2 * fade:
                tone[:fade] *= np.linspace(0, 1, fade)
                tone[-fade:] *= np.linspace(1, 0, fade)

            watermark[idx:end] += tone

    # Add watermark to carrier (extend carrier if needed)
    result = carrier.copy()
    wm_len = len(watermark)
    if wm_len <= len(result):
        result[:wm_len] += watermark
    else:
        # Carrier is shorter than watermark — extend with silence + watermark
        extended = np.zeros(wm_len)
        extended[:len(result)] = result
        extended += watermark
        result = extended

    return result


def decode_watermark(audio: np.ndarray, n_symbols: int,
                     config: WatermarkConfig = None) -> str:
    """Extract watermark text from audio signal.

    Args:
        audio: Audio signal as numpy array (mono, float64)
        n_symbols: Number of unique symbols to extract (before repetition)
        config: Watermark configuration (must match encoding config)

    Returns:
        Extracted text (uppercase, no spaces)
    """
    if config is None:
        config = WatermarkConfig()

    samples_per_symbol = int(config.symbol_duration * config.sample_rate)

    # Extract each repetition and vote
    decoded_reps = []
    for rep in range(config.repetitions):
        rep_symbols = []
        for i in range(n_symbols):
            idx = (rep * n_symbols + i) * samples_per_symbol
            end = idx + samples_per_symbol
            if end > len(audio):
                break

            segment = audio[idx:end]

            # FFT to find dominant frequency in the infrasound/low-freq band
            fft = np.fft.rfft(segment)
            freqs = np.fft.rfftfreq(len(segment), 1.0 / config.sample_rate)

            # Search range: slightly below Schumann to above max letter freq
            if config.digits_enabled:
                f_max = 450.0  # include Tesla harmonics
            else:
                f_max = 25.0   # letters only (infrasound)
            f_min = 5.0

            mask = (freqs >= f_min) & (freqs <= f_max)
            if not np.any(mask):
                rep_symbols.append(None)
                continue

            magnitudes = np.abs(fft[mask])
            peak_idx = np.argmax(magnitudes)
            peak_freq = freqs[mask][peak_idx]

            char = _nearest_char(peak_freq, config)
            rep_symbols.append(char)

        decoded_reps.append(rep_symbols)

    # Majority vote across repetitions
    result = []
    for i in range(n_symbols):
        votes = {}
        for rep in decoded_reps:
            if i < len(rep) and rep[i] is not None:
                votes[rep[i]] = votes.get(rep[i], 0) + 1
        if votes:
            winner = max(votes, key=votes.get)
            result.append(winner)
        else:
            result.append('?')

    return ''.join(result)


def embed_watermark_wav(text: str, input_path: str, output_path: str,
                        config: WatermarkConfig = None) -> dict:
    """Embed watermark into a WAV file.

    Args:
        text: Text to embed
        input_path: Path to input WAV file
        output_path: Path to output WAV file
        config: Watermark configuration

    Returns:
        Dict with embedding metadata
    """
    if config is None:
        config = WatermarkConfig()

    # Read input WAV
    with wave.open(input_path, 'rb') as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    # Convert to float64 mono
    config.sample_rate = framerate
    if sampwidth == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
        samples /= 32768.0
    elif sampwidth == 4:
        samples = np.frombuffer(raw, dtype=np.int32).astype(np.float64)
        samples /= 2147483648.0
    else:
        samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float64)
        samples = (samples - 128.0) / 128.0

    # Take first channel if stereo
    if n_channels > 1:
        samples = samples[::n_channels]

    # Embed
    symbols = _text_to_symbols(text, config)
    result = encode_watermark(text, samples, config)

    # Convert back to int16
    result_int = np.clip(result * 32768.0, -32768, 32767).astype(np.int16)

    # Write output WAV (mono)
    with wave.open(output_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(result_int.tobytes())

    return {
        'text': text,
        'symbols': len(symbols),
        'repetitions': config.repetitions,
        'duration_seconds': len(symbols) * config.repetitions * config.symbol_duration,
        'carrier_duration': len(samples) / framerate,
        'output_path': output_path,
    }


def extract_watermark_wav(input_path: str, n_symbols: int,
                          config: WatermarkConfig = None) -> str:
    """Extract watermark from a WAV file.

    Args:
        input_path: Path to WAV file with embedded watermark
        n_symbols: Number of unique symbols to extract
        config: Watermark configuration (must match embedding config)

    Returns:
        Extracted text
    """
    if config is None:
        config = WatermarkConfig()

    with wave.open(input_path, 'rb') as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    config.sample_rate = framerate
    if sampwidth == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
        samples /= 32768.0
    elif sampwidth == 4:
        samples = np.frombuffer(raw, dtype=np.int32).astype(np.float64)
        samples /= 2147483648.0
    else:
        samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float64)
        samples = (samples - 128.0) / 128.0

    if n_channels > 1:
        samples = samples[::n_channels]

    return decode_watermark(samples, n_symbols, config)
