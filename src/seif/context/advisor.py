"""
Context Advisor — Protocol-driven conversation optimization.

Analyzes conversation state and recommends when to:
  1. CONTINUE in main thread (context-dependent task)
  2. SPAWN a sub-agent with minimal .seif context (independent verification)
  3. COMPRESS and refresh (context window pressure, quality degradation)
  4. SYNC context (stale project data)

The advisor does not act — it measures and recommends. CONTEXT_NOT_COMMAND.

Usage:
  from seif.context.advisor import advise, describe_advice

  advice = advise(
      task_description="verify this calculation independently",
      context_usage_pct=65,
      recent_quality_scores=[0.8, 0.7, 0.5, 0.4],
  )
  print(describe_advice(advice))
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from seif.constants import PHI_INVERSE


# Thresholds (derived from protocol constants)
CONTEXT_PRESSURE_THRESHOLD = 60      # % of context window → consider compression
QUALITY_DECLINE_THRESHOLD = 0.15     # score drop over last N messages → degradation
SPAWN_INDEPENDENCE_KEYWORDS = [
    "verify", "check", "validate", "calculate", "compare",
    "test", "benchmark", "measure", "count", "list",
    "search", "find", "grep", "look up", "summarize",
    "translate", "convert", "format", "generate",
]
MAIN_THREAD_KEYWORDS = [
    "continue", "based on what we", "as we discussed",
    "the code above", "the file we", "modify", "refactor",
    "update the", "fix the", "change the", "this function",
    "in the context of", "given our", "following up",
]


@dataclass
class ConversationState:
    """Current state of the conversation for the advisor."""
    task_description: str = ""
    context_usage_pct: float = 0       # 0-100, from Claude Code status
    recent_quality_scores: list[float] = field(default_factory=list)
    turns_count: int = 0
    last_stance: str = ""              # GROUNDED/DRIFT/MIXED
    project_seif_exists: bool = False
    project_seif_age_hours: float = 0  # hours since last sync


@dataclass
class Advice:
    """Recommendation from the context advisor."""
    action: str              # CONTINUE / SPAWN / COMPRESS / SYNC
    confidence: float        # 0-1 how confident in this recommendation
    reason: str
    spawn_context: Optional[str] = None  # minimal context for sub-agent
    suggestions: list[str] = field(default_factory=list)


def _detect_independence(task: str) -> float:
    """Score 0-1 how independent this task is from conversation context."""
    task_lower = task.lower()

    # Check for main-thread indicators (context-dependent)
    main_score = sum(1 for kw in MAIN_THREAD_KEYWORDS if kw in task_lower)
    if main_score > 0:
        return max(0.0, 0.3 - main_score * 0.1)

    # Check for independence indicators
    independence_score = sum(1 for kw in SPAWN_INDEPENDENCE_KEYWORDS if kw in task_lower)
    return min(1.0, 0.3 + independence_score * 0.15)


def _detect_quality_decline(scores: list[float]) -> tuple[bool, float]:
    """Detect if quality is declining over recent messages.

    Returns: (is_declining, magnitude of decline)
    """
    if len(scores) < 3:
        return False, 0.0

    recent = scores[-3:]
    older = scores[:-3] if len(scores) > 3 else scores[:1]

    recent_avg = sum(recent) / len(recent)
    older_avg = sum(older) / len(older)
    decline = older_avg - recent_avg

    return decline > QUALITY_DECLINE_THRESHOLD, round(decline, 3)


def _build_spawn_context(project_seif_path: str = ".seif/project.seif") -> Optional[str]:
    """Build minimal context for a sub-agent from .seif."""
    try:
        from seif.context.context_manager import load_module
        path = Path(project_seif_path)
        if not path.exists():
            return None
        module = load_module(str(path))
        # Minimal: just the summary (no full KERNEL)
        return (
            f"[SEIF PROJECT CONTEXT — {module.compressed_words} words, "
            f"hash:{module.integrity_hash}]\n"
            f"{module.summary[:1000]}"
        )
    except Exception:
        return None


def advise(
    task_description: str = "",
    context_usage_pct: float = 0,
    recent_quality_scores: list[float] = None,
    turns_count: int = 0,
    last_stance: str = "",
    project_seif_path: str = ".seif/project.seif",
) -> Advice:
    """Analyze conversation state and recommend optimization action.

    Args:
        task_description: What the user wants to do next.
        context_usage_pct: Percentage of context window used (0-100).
        recent_quality_scores: Quality gate scores of recent messages.
        turns_count: Number of conversation turns so far.
        last_stance: Last stance detection result.
        project_seif_path: Path to project .seif for spawn context.

    Returns:
        Advice with recommended action and reasoning.
    """
    scores = recent_quality_scores or []
    suggestions = []

    # 1. Check for context pressure
    if context_usage_pct > CONTEXT_PRESSURE_THRESHOLD:
        spawn_ctx = _build_spawn_context(project_seif_path)
        suggestions.append(
            f"Context at {context_usage_pct:.0f}% — consider starting fresh session "
            f"with .seif context ({len(spawn_ctx.split()) if spawn_ctx else 0} words)"
        )

        if context_usage_pct > 80:
            return Advice(
                action="COMPRESS",
                confidence=0.9,
                reason=f"Context window at {context_usage_pct:.0f}%. "
                       "Quality will degrade. Start new session with .seif context.",
                spawn_context=spawn_ctx,
                suggestions=suggestions,
            )

    # 2. Check for quality decline
    declining, magnitude = _detect_quality_decline(scores)
    if declining:
        suggestions.append(
            f"Quality declining by {magnitude:.3f} over last {len(scores)} messages"
        )
        if last_stance == "DRIFT":
            suggestions.append("Last response was DRIFT — re-ground with verifiable data")

    # 3. Check task independence
    independence = _detect_independence(task_description)

    if independence > 0.6:
        spawn_ctx = _build_spawn_context(project_seif_path)
        return Advice(
            action="SPAWN",
            confidence=round(independence, 2),
            reason=(
                f"Task appears independent (score: {independence:.2f}). "
                "A sub-agent with minimal .seif context can handle this "
                "without consuming main thread context."
            ),
            spawn_context=spawn_ctx,
            suggestions=suggestions + [
                "Sub-agent receives project .seif (~500 words) instead of full conversation",
                "Main thread context is preserved for dependent work"
            ],
        )

    # 4. Check if sync is needed
    seif_path = Path(project_seif_path)
    if seif_path.exists():
        import os
        age_hours = (
            (__import__("time").time() - os.path.getmtime(str(seif_path))) / 3600
        )
        if age_hours > 24:
            suggestions.append(
                f"Project .seif is {age_hours:.0f}h old — run /sync to update"
            )
            if not task_description:
                return Advice(
                    action="SYNC",
                    confidence=0.7,
                    reason=f"Project context is {age_hours:.0f} hours stale.",
                    suggestions=suggestions,
                )

    # 5. Default: continue in main thread
    confidence = 0.8
    if declining:
        confidence = 0.5
        suggestions.append("Quality is declining — consider more specific prompts")

    return Advice(
        action="CONTINUE",
        confidence=round(confidence, 2),
        reason="Task is context-dependent. Continue in main thread.",
        suggestions=suggestions,
    )


def describe_advice(a: Advice) -> str:
    """Human-readable advice report."""
    icons = {"CONTINUE": "▶", "SPAWN": "⑂", "COMPRESS": "⊘", "SYNC": "↻"}
    icon = icons.get(a.action, "?")

    lines = [f"{icon} Recommendation: {a.action} (confidence: {a.confidence:.0%})"]
    lines.append(f"  {a.reason}")

    if a.spawn_context:
        words = len(a.spawn_context.split())
        lines.append(f"  Sub-agent context: ~{words} words (vs full conversation)")

    if a.suggestions:
        lines.append("")
        for s in a.suggestions:
            lines.append(f"  + {s}")

    return "\n".join(lines)
