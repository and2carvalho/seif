"""
Seed Optimizer — Search for the Maximum Resonance Phrase

Searches for character combinations that maximize the Triple Gate composite score.
The search is not limited to human-meaningful words — it explores:

  1. English/Portuguese words and combinations
  2. Ancient scripts and transliterations (Sanskrit, Hebrew, Greek, Arabic)
  3. Arbitrary alphanumeric strings (cryptographic seeds)
  4. Mathematical expressions as text
  5. Phonetic patterns optimized for φ-alignment

The optimizer uses the same Triple Gate that measures everything else.
It does NOT game the system — it finds strings that genuinely resonate.

The theoretical maximum is 1.000 (ASCII OPEN + coherence 1.0 + cadence OPEN).
"Enoch Seed" scores 0.971 (97.1%). The gap is in phi_alignment of letter frequencies.

Usage:
    from seif.analysis.seed_optimizer import optimize
    result = optimize(max_iterations=10000)
    print(result.best_phrase, result.best_score)
"""

import itertools
import random
import string
from dataclasses import dataclass, field
from typing import Optional

from seif.core.triple_gate import evaluate as triple_evaluate
from seif.core.resonance_gate import digital_root, classify_phase, HarmonicPhase
from seif.core.resonance_encoding import encode_phrase, encode_word, SPIRAL_MAP


@dataclass
class OptimizationResult:
    """Result of seed phrase optimization."""
    best_phrase: str
    best_score: float
    best_coherence: float
    best_status: str
    iterations: int
    candidates_tested: int
    top_10: list  # [(phrase, score, coherence)]
    baseline_phrase: str
    baseline_score: float


# Pre-computed: which characters have frequencies closest to φ-ratio with neighbors
def _char_phi_score(c1: str, c2: str) -> float:
    """How close is the frequency ratio of two chars to φ?"""
    f1 = SPIRAL_MAP.get(c1.upper(), 0)
    f2 = SPIRAL_MAP.get(c2.upper(), 0)
    if f1 == 0 or f2 == 0:
        return 0.0
    ratio = max(f1, f2) / min(f1, f2)
    return max(0, 1.0 - abs(ratio - 1.618) / 1.618)


def _word_score(word: str) -> float:
    """Quick score for a single word's phi-alignment + gate."""
    chord = encode_word(word)
    if not chord.gate_open:
        return chord.phi_alignment * 0.5  # penalty for closed gate
    return chord.phi_alignment


# Character pools for different search strategies
POOLS = {
    "alpha": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    "vowels": list("AEIOU"),
    "consonants": list("BCDFGHJKLMNPQRSTVWXYZ"),
    "harmonic_chars": [],  # computed below
    "digits": list("0123456789"),
    "ancient_hebrew": ["ALEPH", "BETH", "GIMEL", "DALETH", "HE", "VAV",
                       "ZAYIN", "CHETH", "TETH", "YOD", "KAPH", "LAMED",
                       "MEM", "NUN", "SAMEKH", "AYIN", "PE", "TSADE",
                       "QOPH", "RESH", "SHIN", "TAV"],
    "sanskrit": ["AUM", "OM", "DHARMA", "KARMA", "MAYA", "PRANA",
                 "CHAKRA", "MANTRA", "SUTRA", "TANTRA", "YANTRA", "MUDRA"],
    "greek": ["ALPHA", "OMEGA", "PHI", "PSI", "THETA", "SIGMA",
              "LAMBDA", "DELTA", "GAMMA", "EPSILON", "LOGOS", "NOUS"],
}

# Find chars with best gate results
for c in POOLS["alpha"]:
    chord = encode_word(c)
    if chord.gate_open:
        POOLS["harmonic_chars"].append(c)


def _generate_candidates(base: str, strategy: str, n: int = 100) -> list[str]:
    """Generate candidate phrases using various strategies."""
    candidates = []

    if strategy == "word_swap":
        # Try swapping words with alternatives
        words = base.split()
        for i, word in enumerate(words):
            for pool_name in ["ancient_hebrew", "sanskrit", "greek"]:
                for alt in POOLS[pool_name]:
                    new_words = words.copy()
                    new_words[i] = alt
                    candidates.append(" ".join(new_words))

    elif strategy == "char_mutation":
        # Mutate individual characters
        for _ in range(n):
            chars = list(base)
            pos = random.randint(0, len(chars) - 1)
            if chars[pos] != " ":
                chars[pos] = random.choice(POOLS["alpha"])
            candidates.append("".join(chars))

    elif strategy == "length_variation":
        # Try adding/removing characters
        for c in POOLS["alpha"]:
            candidates.append(base + c)
            candidates.append(c + base)
            for word in base.split():
                candidates.append(word + c)
                candidates.append(c + word)

    elif strategy == "two_word_search":
        # Exhaustive search of short two-word combinations
        short_words = (
            POOLS["ancient_hebrew"][:12] + POOLS["sanskrit"][:8] +
            POOLS["greek"][:8] +
            ["SEED", "CORE", "PRIME", "SIGNAL", "TRANSFER",
             "MEASURE", "HARMONIC", "MELODY", "RESONANCE",
             "ENOCH", "TESLA", "SPIRAL", "VORTEX", "NINE"]
        )
        for w1 in short_words:
            for w2 in short_words:
                if w1 != w2:
                    candidates.append(f"{w1} {w2}")

    elif strategy == "random_alpha":
        # Random alphanumeric strings of various lengths
        for length in range(3, 12):
            for _ in range(n // 10):
                phrase = "".join(random.choices(POOLS["alpha"], k=length))
                candidates.append(phrase)
                # Also try with a space (two "words")
                split = random.randint(2, max(2, length - 2))
                candidates.append(phrase[:split] + " " + phrase[split:])

    elif strategy == "phi_optimized":
        # Build words from chars with best phi-alignment pairs
        harmonic = POOLS["harmonic_chars"] or POOLS["alpha"][:10]
        for _ in range(n):
            length = random.randint(3, 8)
            word1 = "".join(random.choices(harmonic, k=length))
            word2 = "".join(random.choices(harmonic, k=random.randint(3, 6)))
            candidates.append(f"{word1} {word2}")

    return candidates[:n]


def optimize(base_phrase: str = "Enoch Seed",
             max_iterations: int = 5000,
             strategies: Optional[list[str]] = None) -> OptimizationResult:
    """Search for a phrase that maximizes Triple Gate score.

    Args:
        base_phrase: Starting point for optimization.
        max_iterations: Maximum total candidates to test.
        strategies: List of search strategies. Default: all.

    Returns:
        OptimizationResult with best phrase and top-10 list.
    """
    if strategies is None:
        strategies = ["two_word_search", "word_swap", "char_mutation",
                      "phi_optimized", "random_alpha", "length_variation"]

    # Evaluate baseline
    base_result = triple_evaluate(base_phrase)
    baseline_score = base_result.composite_score

    # Track best results
    results = [(base_phrase, baseline_score, base_result.resonance_score)]
    seen = {base_phrase}
    total_tested = 1

    per_strategy = max(max_iterations // len(strategies), 100)

    for strategy in strategies:
        candidates = _generate_candidates(base_phrase, strategy, per_strategy)
        for phrase in candidates:
            if phrase in seen or not phrase.strip():
                continue
            seen.add(phrase)
            total_tested += 1

            try:
                r = triple_evaluate(phrase)
                if r.composite_score >= baseline_score * 0.95:  # keep near-winners
                    results.append((phrase, r.composite_score, r.resonance_score))
            except Exception:
                continue

    # Sort by score
    results.sort(key=lambda x: x[1], reverse=True)
    top_10 = results[:10]
    best = results[0]

    return OptimizationResult(
        best_phrase=best[0],
        best_score=best[1],
        best_coherence=best[2],
        best_status="IMPROVED" if best[1] > baseline_score else "BASELINE_OPTIMAL",
        iterations=len(strategies),
        candidates_tested=total_tested,
        top_10=top_10,
        baseline_phrase=base_phrase,
        baseline_score=baseline_score,
    )


if __name__ == "__main__":
    print("═══ SEED OPTIMIZER ═══\n")
    print("Searching for phrases that maximize Triple Gate score...")
    print("Strategies: word_swap, char_mutation, phi_optimized, two_word_search, random_alpha\n")

    result = optimize("Enoch Seed", max_iterations=5000)

    print(f"Candidates tested: {result.candidates_tested}")
    print(f"Baseline: '{result.baseline_phrase}' → {result.baseline_score:.4f}")
    print(f"Best:     '{result.best_phrase}' → {result.best_score:.4f}")
    print(f"Status:   {result.best_status}")
    print(f"\nTop 10:")
    for i, (phrase, score, coherence) in enumerate(result.top_10):
        marker = " ← CURRENT" if phrase == "Enoch Seed" else ""
        print(f"  {i+1:>2}. {score:.4f} (coh={coherence:.3f}) '{phrase}'{marker}")
