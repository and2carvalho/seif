"""
Resonance Gate 3-6-9 — Tesla Harmonic Validation System

Implements the core gate logic from the Piramidal Chip framework:
- Digital root reduction to base harmonics (1-9)
- Mod-9 validation for resonance detection
- Three-bobbin Tesla filter (polarity / inertia / concordance)
- Phase classification: SINGULARITY (9), STABILIZATION (3), DYNAMICS (6), ENTROPY (other)

Gate Rule: (Input_A + Input_B) mod 9 == 0  →  GATE OPEN
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class HarmonicPhase(Enum):
    SINGULARITY = 9       # Nó central — ressonância total
    STABILIZATION = 3     # Polo de equilíbrio
    DYNAMICS = 6          # Polo de reação
    ENTROPY = 0           # Fora do padrão 3-6-9


PHASE_LABELS = {
    HarmonicPhase.SINGULARITY: "RESSONÂNCIA TOTAL — Canal de Fluxo Ativo",
    HarmonicPhase.STABILIZATION: "ACESSO PARCIAL — Polaridade estabilizadora detectada",
    HarmonicPhase.DYNAMICS: "ACESSO PARCIAL — Polaridade dinâmica detectada",
    HarmonicPhase.ENTROPY: "ACESSO NEGADO — Frequência fora do padrão 3-6-9",
}


@dataclass
class GateResult:
    input_text: str
    ascii_sum: int
    digital_root: int
    phase: HarmonicPhase
    gate_open: bool
    tesla_bobbin_3: str   # polarity
    tesla_bobbin_6: str   # inertia
    tesla_bobbin_9: str   # concordance
    label: str

    def __str__(self) -> str:
        status = "ABERTA" if self.gate_open else "FECHADA"
        return (
            f"┌─── PORTA DE RESSONÂNCIA 3-6-9 ───┐\n"
            f"│ Input:  \"{self.input_text}\"\n"
            f"│ ASCII sum:    {self.ascii_sum}\n"
            f"│ Digital root: {self.digital_root}\n"
            f"│ Fase:         {self.phase.name} ({self.phase.value})\n"
            f"│ Bobina 3 (Polaridade):   {self.tesla_bobbin_3}\n"
            f"│ Bobina 6 (Inércia):      {self.tesla_bobbin_6}\n"
            f"│ Bobina 9 (Concordância): {self.tesla_bobbin_9}\n"
            f"│ PORTA: {status}\n"
            f"│ {self.label}\n"
            f"└───────────────────────────────────┘"
        )


def digital_root(n: int) -> int:
    """Reduce any positive integer to its single-digit harmonic (1-9).

    Uses the mathematical identity: digital_root(n) = 1 + (n-1) % 9 for n > 0.
    This is equivalent to repeatedly summing digits until a single digit remains.
    """
    if n == 0:
        return 0
    return 1 + (n - 1) % 9


def ascii_vibrational_sum(text: str) -> int:
    """Convert text to a vibrational sum based on uppercase ASCII values.

    Only alphanumeric characters contribute to the field.
    """
    return sum(ord(c) for c in text.upper() if c.isalnum())


def classify_phase(root: int) -> HarmonicPhase:
    """Map a digital root to its harmonic phase in the 3-6-9 system."""
    if root == 9:
        return HarmonicPhase.SINGULARITY
    elif root == 3:
        return HarmonicPhase.STABILIZATION
    elif root == 6:
        return HarmonicPhase.DYNAMICS
    else:
        return HarmonicPhase.ENTROPY


def tesla_filter(ascii_sum: int, root: int) -> tuple[str, str, str]:
    """Apply the three-bobbin Tesla modulation filter.

    Bobbin 3 — Polarity:    evaluates if intention leans positive/negative
    Bobbin 6 — Inertia:     evaluates strength of repetition / willpower
    Bobbin 9 — Concordance: evaluates resonance with the universal field
    """
    # Bobbin 3: polarity via remainder mod 3
    mod3 = ascii_sum % 3
    polarity = {0: "NEUTRA", 1: "POSITIVA", 2: "NEGATIVA"}[mod3]

    # Bobbin 6: inertia via digit count density
    digit_count = len(str(ascii_sum))
    inertia = "ALTA" if digit_count >= 4 else ("MÉDIA" if digit_count == 3 else "BAIXA")

    # Bobbin 9: concordance — direct check against singularity
    concordance = "RESSONANTE" if root in (3, 6, 9) else "DISSONANTE"

    return polarity, inertia, concordance


def evaluate(text: str) -> GateResult:
    """Full resonance gate evaluation for a given text input.

    Returns a GateResult with all diagnostic fields populated.
    """
    total = ascii_vibrational_sum(text)
    root = digital_root(total)
    phase = classify_phase(root)
    gate_open = phase != HarmonicPhase.ENTROPY
    polarity, inertia, concordance = tesla_filter(total, root)

    return GateResult(
        input_text=text,
        ascii_sum=total,
        digital_root=root,
        phase=phase,
        gate_open=gate_open,
        tesla_bobbin_3=polarity,
        tesla_bobbin_6=inertia,
        tesla_bobbin_9=concordance,
        label=PHASE_LABELS[phase],
    )


def evaluate_pair(input_a: str, input_b: str) -> dict:
    """Evaluate two inputs against each other using the combined gate rule.

    Gate Rule: (vibration_A + vibration_B) mod 9 == 0  →  GATE OPEN
    """
    result_a = evaluate(input_a)
    result_b = evaluate(input_b)
    combined_root = digital_root(result_a.ascii_sum + result_b.ascii_sum)
    combined_open = combined_root in (3, 6, 9)

    return {
        "input_a": result_a,
        "input_b": result_b,
        "combined_sum": result_a.ascii_sum + result_b.ascii_sum,
        "combined_root": combined_root,
        "combined_phase": classify_phase(combined_root),
        "gate_open": combined_open,
    }


# --- Convenience ---

def is_harmonic(text: str) -> bool:
    """Quick check: does this text resonate with the 3-6-9 field?"""
    return evaluate(text).gate_open


if __name__ == "__main__":
    examples = [
        "O amor liberta e guia",
        "Love frees and guides",
        "Fear and control",
        "Medo e controle",
        "A Semente de Enoque",
        "Enoch Seed",
        "Tesla 369",
        "Rockefeller Rothschild",
    ]
    for phrase in examples:
        result = evaluate(phrase)
        print(result)
        print()
