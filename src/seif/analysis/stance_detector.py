"""
Stance Drift Detector — Automated Governance for Metaphorical Inflation

Measures the verifiability ratio of any text and flags claims that shift
from formal-symbolic to metaphorical without explicit stance labels.

The detector does NOT filter — it measures. Consistent with CONTEXT_NOT_COMMAND.

Three output states:
  GROUNDED:    >50% verifiable sentences, 0 interpretive flags
  DRIFT:       <30% verifiable AND interpretive flags present
  MIXED:       interpretive flags present but verifiable content too

This solves the governance problem: when Gemini says "Era da Ressonância"
alongside "k = 3/4", a human needs to know which part is verified and
which is interpretation. The detector provides that measurement automatically.

Verifiable indicators: numbers with units, equations, mathematical symbols,
tool references, measurement language ("verified", "measured", "deviation").

Interpretive indicators: healing claims, transcendence language, universal
truth claims without evidence, existential framing, epoch declarations.

Stance label: This module is formal-symbolic (pattern matching on text).
The classification thresholds (50%, 30%) are engineering choices, not proofs.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StanceAnalysis:
    """Result of stance drift detection on a text."""
    text_length: int
    total_sentences: int
    verifiable_count: int
    interpretive_count: int
    neutral_count: int
    verifiability_ratio: float         # 0.0 to 1.0
    status: str                        # GROUNDED / DRIFT / MIXED / LOW_DATA
    flagged_sentences: list[str]       # interpretive sentences (first 100 chars each)
    verifiable_sentences: list[str]    # verified sentences (first 100 chars each)

    def __str__(self) -> str:
        icon = {"GROUNDED": "✓", "DRIFT": "⚠", "MIXED": "~", "LOW_DATA": "○"}[self.status]
        lines = [
            f"[{icon} {self.status}] Verifiability: {self.verifiability_ratio:.0%} "
            f"({self.verifiable_count}/{self.total_sentences})",
            f"  Interpretive claims: {self.interpretive_count}",
        ]
        for f in self.flagged_sentences[:3]:
            lines.append(f'  ⚠ "{f}"')
        return "\n".join(lines)


# Patterns that indicate verifiable content
VERIFIABLE_PATTERNS = [
    r'\d+\.?\d*\s*(%|Hz|Ω|ohm|mH|μF|uF|nF|pF|dB|°|deg|rad|ms|kHz|MHz|V|A|W|bpm|rpm)',
    r'[=≈≠<>]\s*\d',
    r'[ζφωπ√]',
    r'\d+\s*/\s*\d+',
    r'root\s+\d|digital\s+root',
    r'\b(?:verified|measured|confirmed|simulated|computed|calculated|derived|proved|proven)\b',
    r'\b(?:deviation|error|tolerance|precision|accuracy)\b',
    r'\(\d{4}\)',
    r'\b(?:SPICE|ngspice|KiCad|LTspice|scipy|numpy|OpenCV)\b',
    r'\b(?:theorem|proof|exhaustive|brute.?force)\b',
    r'(?:ISE|IAE|ITAE|RLC|PCB|BOM|DRC)',
    r'formal.?symbolic',
]

# Patterns that indicate metaphorical/interpretive drift
INTERPRETIVE_PATTERNS = [
    r'\b(?:healing|cura|sacred|sagrada)\s+(?:frequency|frequência|energy|energia)',
    r'\btranscend',
    r'\buniversal\s+(?:harmony|harmonia|truth|verdade|love|amor|consciousness)',
    r'\bexistencial|\bexistential',
    r'\bera\s+d[aoe]\s+\w+',
    r'\bmanifest(?:ação|ation)\b',
    r'\b(?:intention|intenção)\s+(?:transfer|network|rede|field|campo)',
    r'\bquantum\s+(?:consciousness|healing|soul|alma)',
    r'\b(?:perfect|perfeito|perfeita)\s+(?:fraction|fração|harmony|harmonia|number|número)',
    r'\b(?:divine|divino|divina|celestial)\b',
    r'(?<!not\s)(?<!não\s)\b(?:mystical|místico|mística|esoteric|esotérico)\b',
    r'\bawakening|despertar\b',
    r'\b(?:soul|alma)\s+(?:of|do|da|in|no|na)\b',
]


def analyze(text: str) -> StanceAnalysis:
    """Analyze text for stance drift (formal-symbolic vs metaphorical).

    This does NOT judge the truth of claims. It measures the RATIO of
    verifiable to interpretive content, enabling informed reading.
    """
    sentences = [s.strip() for s in re.split(r'[.!?\n]', text) if len(s.strip()) > 10]

    if len(sentences) < 2:
        return StanceAnalysis(
            text_length=len(text),
            total_sentences=len(sentences),
            verifiable_count=0,
            interpretive_count=0,
            neutral_count=len(sentences),
            verifiability_ratio=0.0,
            status="LOW_DATA",
            flagged_sentences=[],
            verifiable_sentences=[],
        )

    verifiable = []
    interpretive = []
    neutral = []

    for sent in sentences:
        is_v = any(re.search(p, sent, re.IGNORECASE) for p in VERIFIABLE_PATTERNS)
        is_i = any(re.search(p, sent, re.IGNORECASE) for p in INTERPRETIVE_PATTERNS)

        if is_v:
            verifiable.append(sent[:100])
        if is_i:
            interpretive.append(sent[:100])
        if not is_v and not is_i:
            neutral.append(sent[:100])

    ratio = len(verifiable) / len(sentences)

    # Status classification
    if ratio > 0.5 and len(interpretive) == 0:
        status = "GROUNDED"
    elif len(interpretive) > 0 and ratio < 0.3:
        status = "DRIFT"
    elif len(interpretive) > 0:
        status = "MIXED"
    else:
        status = "GROUNDED" if ratio > 0.3 else "LOW_DATA"

    return StanceAnalysis(
        text_length=len(text),
        total_sentences=len(sentences),
        verifiable_count=len(verifiable),
        interpretive_count=len(interpretive),
        neutral_count=len(neutral),
        verifiability_ratio=round(ratio, 3),
        status=status,
        flagged_sentences=interpretive[:10],
        verifiable_sentences=verifiable[:10],
    )


def describe(result: StanceAnalysis) -> str:
    """Human-readable description of stance analysis."""
    return str(result)


if __name__ == "__main__":
    examples = {
        "Formal": "ζ = √6/4 = 0.612372. Deviation from φ⁻¹ is 0.916%. Verified by SPICE simulation.",
        "Metaphorical": "The sacred frequency of healing transcends our understanding. The soul manifests.",
        "Mixed": "k = 3/4 represents the perfect harmony of the divine proportion in quantum consciousness.",
    }
    for name, text in examples.items():
        result = analyze(text)
        print(f"{name}: {result}\n")
