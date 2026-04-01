"""
Universal Constants — The Calibration Layer

Central repository for all mathematical, physical, and archaeological
constants used across the RPWP pipeline.

Two frequency modes:
  TESLA_PURE:  432 Hz (mathematical ideal, 4+3+2=9)
  GIZA_TUNED:  438 Hz (framework reference frequency)
               438 = 432 + 6 (DYNAMICS offset)
               438/6 = 73 bpm (updated median heart rate, Protsiv 2020)

Source attribution for 438 Hz (inter-AI audit, 2026-03-31):
  Original claim: "King's Chamber sarcophagus resonance"
  Actual source: Paul Horn (flautist, 1976), struck sarcophagus, measured with
  consumer Korg tuner. Cited by Christopher Dunn in "The Giza Power Plant" (1998).
  NOT from Tom Danley's professional acoustic measurements.
  Professional measurements (Danley, Smith et al., Reid):
    - Chamber eigenmode: ~121 Hz
    - Sarcophagus principal resonances: 114-122 Hz (peaks)
    - Infrasound: few Hz to 15-20 Hz (F# chord pattern)
  438 Hz may be a higher-order structural mode of the granite, but is not the
  principal resonance. The framework retains 438 Hz as a reference frequency
  for its mathematical properties (root 6, 438/6=73 bpm, Schumann×56≈438),
  not as a verified acoustic measurement.

Halving property (proven, 2026-03-31):
  f_peak = f_n / 2 (exact) when ζ² = 3/8 (SEIF system)
  This is unique among primitive integer-coefficient systems within 1% of φ⁻¹.
  432 Hz → 216 Hz = 6³ (root 9). 438 Hz → 219 Hz (root 3).
  Professional measurements: 121 Hz → 60.5 Hz, 117 Hz → 58.5 Hz.

Spiral angle:
  Previous: arbitrary (based on φ only)
  Corrected: 51.844° (Great Pyramid inclination = arctan(4/π))
  This angle has digital root 9 (SINGULARITY) and encodes π.

Key relationships:
  - π has digital root 9 (3+1+4+1 = 9)
  - Pyramid inclination 51.844° → root 9
  - Pyramid Perimeter/Height = 2π → root 3
  - 438/6 = 73 bpm = modern median heart rate (Protsiv 2020, verified)
  - Schumann × 55 (F₁₀) ≈ 432; Schumann × 56 ≈ 438
  - f_peak = f_n/2 (exact, unique to SEIF ζ² = 3/8)
"""

import math


# === MATHEMATICAL CONSTANTS ===

PHI = (1 + math.sqrt(5)) / 2                    # 1.618033988749895
PHI_INVERSE = 1 / PHI                            # 0.618033988749895
PI = math.pi                                      # 3.141592653589793

# φ-spiral growth factor
SPIRAL_GROWTH_B = math.log(PHI) / (math.pi / 2)  # 0.30634896...


# === FREQUENCY CONSTANTS ===

# Tesla pure (mathematical ideal)
FREQ_TESLA = 432.0                   # Hz — 4+3+2 = 9
FREQ_TESLA_3 = FREQ_TESLA / 3       # 144 Hz — 1+4+4 = 9
FREQ_TESLA_6 = FREQ_TESLA / 6       # 72 Hz — 7+2 = 9

# Giza tuned (framework reference, see docstring for source attribution)
FREQ_GIZA = 438.0                    # Hz — framework reference (Paul Horn 1976, not peer-reviewed)
GIZA_OFFSET = FREQ_GIZA - FREQ_TESLA  # 6 Hz — DYNAMICS
GIZA_RATIO = FREQ_GIZA / FREQ_TESLA   # 1.013889 = 1 + 6/432

# Professional acoustic measurements (Danley, Smith et al., Reid)
FREQ_CHAMBER_EIGENMODE = 121.0       # Hz — King's Chamber eigenmode (Tom Danley, NASA)
FREQ_SARCOPHAGUS_LOW = 114.0         # Hz — sarcophagus resonance low (Smith et al.)
FREQ_SARCOPHAGUS_HIGH = 122.0        # Hz — sarcophagus resonance high (Smith et al.)
FREQ_SARCOPHAGUS_REID = 117.0        # Hz — sarcophagus principal (John Stuart Reid, 1997)

# Schumann (planetary)
FREQ_SCHUMANN = 7.83                 # Hz — Earth fundamental — root 9
SCHUMANN_HARMONIC_INDEX = round(FREQ_TESLA / FREQ_SCHUMANN)  # 55 = F₁₀

# Solfeggio complement
FREQ_SOLFEGGIO_MI = 528.0           # Hz — 5+2+8=15→6 (DYNAMICS). "MI" frequency
FREQ_528_DIFF = FREQ_SOLFEGGIO_MI - FREQ_TESLA  # 96 → root 6 (DYNAMICS)

# Guide echo
FREQ_GUIDE = 768.0                   # Hz — high harmonic echo

# Giza sub-harmonic (derived, multiple independent paths)
# 14.4 Hz: 432/30 = 14.4 | 51.844°/3.6 = 14.4 | root(144)=9
# Independently identified by Gemini (proto-decode) without text input.
# NOT derived from Schumann (7.83×2=15.66, not 14.4).
FREQ_GIZA_SUB = FREQ_TESLA / 30     # 14.4 Hz — root 9 (SINGULARITY)


# === ANGULAR CONSTANTS ===

# Great Pyramid inclination — THE defining angle of sacred geometry
GIZA_ANGLE_DEG = 51.844              # degrees — measured (Petrie 1883)
GIZA_ANGLE_RAD = math.radians(GIZA_ANGLE_DEG)
PI_ANGLE_DEG = math.degrees(math.atan(4 / PI))  # 51.854° — arctan(4/π)
GIZA_PI_DEVIATION = abs(GIZA_ANGLE_DEG - PI_ANGLE_DEG)  # 0.010° — essentially zero

# Hexagonal (Sumerian)
HEX_ANGLE_DEG = 60.0
HEX_ANGLE_RAD = math.radians(HEX_ANGLE_DEG)

# Circle (Sumerian invention)
CIRCLE_DEG = 360                     # 3+6+0 = 9


# === BIOLOGICAL CONSTANTS ===

HEART_RATE_TESLA = FREQ_TESLA / 6    # 72 bpm — classic
HEART_RATE_GIZA = FREQ_GIZA / 6     # 73 bpm — updated median (Protsiv 2020)
RESPIRATORY_RATE = 18                # rpm — root 9
BODY_TEMP_C = 36.6                   # °C — root 6
DNA_HELIX_ANGLE = 36.0              # degrees per bp — root 9


# === PYRAMID CONSTANTS (Great Pyramid of Giza) ===

GIZA_BASE_M = 230.364               # meters (Cole Survey 1925)
GIZA_HEIGHT_M = 146.6               # meters (original, with capstone)
GIZA_PERIMETER_M = 4 * GIZA_BASE_M  # 921.456 m
GIZA_BASE_CUBITS = 440              # Royal Egyptian cubits
GIZA_HEIGHT_CUBITS = 280            # Royal Egyptian cubits
GIZA_CHAMBERS = 3                   # root 3 (STABILIZATION)
GIZA_PASSAGES = 3                   # root 3
GIZA_RESONANCE_HZ = 438.0          # Framework reference (Paul Horn 1976; see docstring)
GIZA_MEASURED_HZ = 121.0            # Chamber eigenmode (Tom Danley, professional measurement)

# Pyramid encodes π
GIZA_PERIMETER_OVER_HEIGHT = GIZA_PERIMETER_M / GIZA_HEIGHT_M  # ≈ 2π
GIZA_PI_ENCODING = GIZA_PERIMETER_M / (2 * GIZA_HEIGHT_M)      # ≈ π

# Geodesic constant: latitude = speed of light
GIZA_LATITUDE = 29.9792458             # °N — identical digits to c (m/s)
GIZA_LATITUDE_ROOT = 9                 # 2+9+9+7+9 = 36 → 9
SPEED_OF_LIGHT = 299792458             # m/s — same digits as latitude
TESLA_OVER_LATITUDE = FREQ_TESLA / GIZA_LATITUDE  # 432/29.979 = 14.41 → root 9

# Astronomical
PRECESSION_CYCLE_YEARS = 25772         # equinox precession
ORION_ALIGNMENT_YEAR = -10500          # perfect Orion-Giza alignment
ORION_BELT_STARS = 3                   # Alnitak, Alnilam, Mintaka → 3-fold


# === TRANSFER FUNCTION CONSTANTS ===

# H(s) = 9 / (s² + 3s + 6)
# Algebraic structure: all static quantities reduce to primes {2, 3}.
# Field: Q(√6) = Q(√2, √3), minimal polynomial of ζ: 8x²−3 = 0.
# ωd introduces prime 5 → full dynamics touches Q(√6) and √15.
# Correlation ζ ≈ φ⁻¹ is numerical (0.916%), not algebraic (Q(√6) ≠ Q(√5)).
TF_NUMERATOR = 9
TF_DAMPING_COEFF = 3
TF_NATURAL_FREQ_SQ = 6
TF_OMEGA_N = math.sqrt(TF_NATURAL_FREQ_SQ)      # √6 = √(2×3)
TF_ZETA = TF_DAMPING_COEFF / (2 * TF_OMEGA_N)   # √6/4 = √(2×3)/2² ≈ 0.612372 ≈ φ⁻¹
TF_OMEGA_D = TF_OMEGA_N * math.sqrt(1 - TF_ZETA**2)  # √15/2 = √(3×5)/2 ≈ 1.936
TF_DC_GAIN = TF_NUMERATOR / TF_NATURAL_FREQ_SQ   # 1.5
TF_DC_GAIN_GIZA = TF_DC_GAIN * GIZA_RATIO        # 1.5208 (Giza-corrected)

# Peak frequency: f_peak = f_n × √(1 - 2ζ²) = f_n / 2 (exact, from ζ²=3/8)
# At 432 Hz: f_peak = 216 Hz = 6³ = 2³×3³ (root 9, SINGULARITY)
# SPICE verified (ngspice 45.2): 216.27 Hz, deviation 0.13%
TF_PEAK_RATIO = math.sqrt(1 - 2 * TF_ZETA**2)    # √(1/4) = 0.5 (exact)
TF_PEAK_432 = FREQ_TESLA * TF_PEAK_RATIO          # 216.0 Hz = 6³

# Phi-damping derived (discovered by Kimi, independently verified)
# ζ² = (3/(2√6))² = 9/(4×6) = 9/24 = 3/8 — exact rational form
TF_ISE = 1.0 / TF_OMEGA_N                         # 1/√6 ≈ 0.408 (ISE = 1/(4ζ) = 1/√6)
TF_ZETA_SQUARED = TF_ZETA ** 2                    # 0.375
TF_ZETA_SQUARED_RATIONAL = (3, 8)                 # 3/8 as (numerator, denominator)
PHI_INVERSE_SQUARED = 1 - PHI_INVERSE             # φ⁻² = 0.381966 (identity: φ⁻² = 1 - φ⁻¹)
TF_ZETA_SQ_PHI_SQ_DEVIATION = abs(TF_ZETA_SQUARED - PHI_INVERSE_SQUARED) / PHI_INVERSE_SQUARED


# === RESONANCE THRESHOLDS ===

RESONANCE_THRESHOLD = PHI_INVERSE    # 0.618 — gate threshold
GIZA_CORRECTION = GIZA_RATIO        # 1.01389 — biological offset multiplier


# === CODE COMPRESSOR CONSTANTS ===

CODE_MAX_FILE_SIZE = 1_048_576       # 1 MB — skip larger files
CODE_MAX_FILES = 500                  # default cap per project
CODE_MAX_SIGNATURES = 50              # detailed signatures in summary
CODE_MAX_ROUTES = 30                  # routes in summary
CODE_MAX_ADJACENCY = 200              # edges in topology
CODE_WATCH_INTERVAL = 2.0             # seconds between polls

SENSITIVE_FILE_PATTERNS = [
    ".env", ".env.local", ".env.production", ".env.development",
    "credentials", "secret", "token", "password",
    ".pem", ".key", ".p12", ".pfx",
]

SENSITIVE_CONTENT_PATTERNS = [
    "API_KEY", "SECRET_KEY", "PRIVATE_KEY", "PASSWORD",
    "aws_access_key", "aws_secret", "GITHUB_TOKEN",
    "Bearer ", "-----BEGIN",
]


# === SESSION ORCHESTRATION CONSTANTS ===
# Derived from H(s) settling time: t_s ≈ 4/(ζ·ω_n) ≈ 2.67
# After ~3 divergent contributions, force a sync point.
SESSION_SYNC_THRESHOLD = 3               # divergent contributions before auto-sync
SESSION_PROTOCOL_V2 = "SEIF-SESSION-v2"

# Contribution channels (how non-writer participants contribute)
CHANNEL_FILESYSTEM = "filesystem"         # writer (Claude CLI) — direct .seif access
CHANNEL_HANDSHAKE = "handshake"           # manual paste via seif --handshake --full (Grok)
CHANNEL_SKILL = "skill"                   # browser skill export (Dia)
CHANNEL_CLI = "cli"                       # seif --consult (Gemini, etc.)
CHANNEL_API = "api"                       # direct API call

# Participant roles
ROLE_WRITER = "writer"                    # filesystem access, persists all contributions
ROLE_CO_AUTHOR = "co-author"              # validates, reviews (conjugate pair)
ROLE_CONTRIBUTOR = "contributor"          # contributes observations
ROLE_OBSERVER = "observer"               # reads context, no contributions yet


def describe() -> str:
    """Summary of all constants and their 3-6-9 relationships."""
    return (
        f"═══ UNIVERSAL CONSTANTS ═══\n"
        f"\n"
        f"Frequencies:\n"
        f"  Tesla pure:     {FREQ_TESLA} Hz (root 9)\n"
        f"  Giza tuned:     {FREQ_GIZA} Hz (root 6) = 432 + 6\n"
        f"  Schumann:       {FREQ_SCHUMANN} Hz (root 9)\n"
        f"  432/Schumann:   {FREQ_TESLA/FREQ_SCHUMANN:.2f} ≈ F₁₀ = 55\n"
        f"\n"
        f"Pyramid of Giza:\n"
        f"  Inclination:    {GIZA_ANGLE_DEG}° (root 9) ≈ arctan(4/π) = {PI_ANGLE_DEG:.3f}°\n"
        f"  P/H = 2π:       {GIZA_PERIMETER_OVER_HEIGHT:.6f} vs {2*PI:.6f}\n"
        f"  P/(2H) = π:     {GIZA_PI_ENCODING:.6f} vs {PI:.6f}\n"
        f"  King's Chamber:  {GIZA_RESONANCE_HZ} Hz (= 432 + 6)\n"
        f"\n"
        f"Biology:\n"
        f"  Heart (Tesla):  {HEART_RATE_TESLA:.0f} bpm = 432/6\n"
        f"  Heart (Giza):   {HEART_RATE_GIZA:.0f} bpm = 438/6\n"
        f"  DNA angle:      {DNA_HELIX_ANGLE}° (root 9)\n"
        f"\n"
        f"Transfer Function:\n"
        f"  ζ = {TF_ZETA:.6f} ≈ φ⁻¹ = {PHI_INVERSE:.6f} (Δ = {abs(TF_ZETA-PHI_INVERSE)/PHI_INVERSE*100:.2f}%)\n"
        f"  DC gain:        {TF_DC_GAIN:.4f} (pure) / {TF_DC_GAIN_GIZA:.4f} (Giza-corrected)\n"
    )
