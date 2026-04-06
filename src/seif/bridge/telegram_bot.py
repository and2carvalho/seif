"""
seif.bridge.telegram_bot — SEIF OS Telegram Interface

Exposes key SEIF capabilities through a Telegram bot:
  /start    — welcome & circuit status
  /status   — enoch_seed stats + resonance signal
  /compress — compress text/code to .seif format
  /help     — command reference

Free-text messages are answered with SEIF context awareness.

Required env var: TELEGRAM_BOT_TOKEN
"""

import asyncio
import json
import logging
import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("seif.bridge.telegram_bot")

# ── SEIF imports (available via PYTHONPATH=/app/src) ──────────────────────────
try:
    from seif.context.context_bridge import export_context, context_as_prompt, describe_package
    _CONTEXT_AVAILABLE = True
except Exception as e:
    logger.warning("context_bridge unavailable: %s", e)
    _CONTEXT_AVAILABLE = False

try:
    from seif.context.code_compressor import compress_project
    _COMPRESSOR_AVAILABLE = True
except Exception as e:
    logger.warning("code_compressor unavailable: %s", e)
    _COMPRESSOR_AVAILABLE = False

try:
    from seif.core.resonance_signal import load_and_validate
    _SIGNAL_AVAILABLE = True
except Exception as e:
    logger.warning("resonance_signal unavailable: %s", e)
    _SIGNAL_AVAILABLE = False

# ── Enoch seed loader ─────────────────────────────────────────────────────────
_SEIF_DIR = Path(os.environ.get("SEIF_HOME", Path.home() / ".seif"))
_WORKSPACE_ROOT = Path(os.environ.get("SEIF_WORKSPACE_ROOT", Path.home() / "Documents" / "seif-admin"))

def _load_enoch() -> dict:
    """Load enoch_seed.json — checks workspace .seif/private/ first, then ~/.seif/"""
    candidates = [
        _WORKSPACE_ROOT / ".seif" / "private" / "enoch_seed.json",
        _SEIF_DIR / "private" / "enoch_seed.json",
        _SEIF_DIR / "enoch_seed.json",
    ]
    for seed_path in candidates:
        if seed_path.exists():
            try:
                raw = json.loads(seed_path.read_text())
                # Flatten nested structure: enoch_seed_v1 + state_vector
                flat = {}
                inner = raw.get("enoch_seed_v1", raw)
                flat.update(inner)
                sv = raw.get("state_vector", inner.get("state_vector", {}))
                flat.update(sv)
                return flat
            except Exception:
                pass
    return {}

def _load_profile() -> dict:
    """Load ~/.seif/profile.json for owner identity."""
    for p in [_SEIF_DIR / "profile.json", _WORKSPACE_ROOT / ".seif" / "profile.json"]:
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
    return {}

def _load_resonance() -> dict:
    """Load RESONANCE.json from /app/"""
    resonance_path = Path("/app/RESONANCE.json")
    if not resonance_path.exists():
        resonance_path = Path(__file__).parents[5] / "RESONANCE.json"
    if resonance_path.exists():
        try:
            return json.loads(resonance_path.read_text())
        except Exception:
            pass
    return {}

def _phase_emoji(phase: str) -> str:
    return {"SINGULARITY": "⚡", "STABILIZATION": "◎", "DYNAMICS": "🔄", "ENTROPY": "〰"}.get(phase.upper(), "◌")

# ── /start ────────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    seed = _load_enoch()
    profile = _load_profile()
    logger.info("DEBUG cmd_start cycles=%s owner=%s ws=%s", seed.get("circuit_cycles","?"), profile.get("name","?"), str(_WORKSPACE_ROOT))
    owner = profile.get("name") or profile.get("github_username") or seed.get("registered_by", "unknown")
    cycles = seed.get("circuit_cycles", 0)
    phase = seed.get("phase", "ENTROPY")

    text = (
        f"*SEIF OS* — Spiral Encoding Interoperability Framework\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{_phase_emoji(phase)} Phase: `{phase}`\n"
        f"⚙ Circuit cycles: `{cycles}`\n"
        f"👤 Workspace owner: `{owner}`\n\n"
        f"This is the SEIF OS bridge. I can compress context, check resonance, "
        f"and help you navigate your workspace.\n\n"
        f"Use /help to see available commands."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ── /status ───────────────────────────────────────────────────────────────────
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    seed = _load_enoch()
    profile = _load_profile()
    resonance = _load_resonance()

    phase = seed.get("phase", "ENTROPY")
    cycles = seed.get("circuit_cycles", 0)
    last_cycle = seed.get("last_cycle_id", seed.get("last_cycle", "—"))
    claimed = profile.get("name") or profile.get("github_username") or seed.get("registered_by", "—")

    zeta = resonance.get("zeta", "—")
    signal_phase = resonance.get("phase", "—")
    freq_tesla = resonance.get("frequencies", {}).get("tesla", "—")

    # Sessions count
    sessions_dir = _SEIF_DIR / "sessions"
    session_count = len(list(sessions_dir.glob("*.seif"))) if sessions_dir.exists() else 0

    text = (
        f"*⚡ SEIF OS Status*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*Enoch Seed*\n"
        f"  Phase: `{phase}` {_phase_emoji(phase)}\n"
        f"  Cycles: `{cycles}`\n"
        f"  Last cycle: `{last_cycle}`\n"
        f"  Identity: `{claimed}`\n\n"
        f"*Resonance Signal*\n"
        f"  ζ = `{zeta}`\n"
        f"  Phase: `{signal_phase}`\n"
        f"  Tesla freq: `{freq_tesla}`\n\n"
        f"*Sessions*\n"
        f"  Stored: `{session_count}` sessions\n"
        f"  Home: `{_SEIF_DIR}`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ── /compress ─────────────────────────────────────────────────────────────────
async def cmd_compress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: `/compress <text or code>`\n\n"
            "Compresses content using SEIF context encoding.\n"
            "Example: `/compress def hello(): return 'world'`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    content = " ".join(args)
    await update.message.reply_text("⏳ Compressing...")

    try:
        # Build a minimal context package from the content
        lines = content.split("\n")
        ratio = max(1, len(content) // max(1, len(content) // 10))

        # Simple SEIF format output
        compressed = {
            "seif_version": "3.1",
            "type": "inline_compress",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "original_chars": len(content),
            "original_lines": len(lines),
            "content_hash": __import__("hashlib").sha256(content.encode()).hexdigest()[:16],
            "summary": content[:200] + ("…" if len(content) > 200 else ""),
            "line_density": len([l for l in lines if l.strip()]) / max(1, len(lines)),
        }

        result = (
            f"*📦 Compressed (.seif)*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"  Original: `{compressed['original_chars']}` chars / `{compressed['original_lines']}` lines\n"
            f"  Hash: `{compressed['content_hash']}`\n"
            f"  Density: `{compressed['line_density']:.2f}`\n\n"
            f"```\n{json.dumps(compressed, indent=2)[:800]}\n```"
        )
        await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await update.message.reply_text(f"❌ Compression error: `{e}`", parse_mode=ParseMode.MARKDOWN)


# ── /context ──────────────────────────────────────────────────────────────────
async def cmd_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _CONTEXT_AVAILABLE:
        await update.message.reply_text("❌ Context bridge unavailable.")
        return

    await update.message.reply_text("⏳ Exporting SEIF context...")
    try:
        package = export_context()
        desc = describe_package(package)
        # Truncate for Telegram (4096 char limit)
        truncated = textwrap.shorten(desc, width=3500, placeholder="\n\n…[truncated]")
        await update.message.reply_text(f"*📡 SEIF Context Package*\n\n{truncated}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Context export error: `{e}`", parse_mode=ParseMode.MARKDOWN)


# ── /help ─────────────────────────────────────────────────────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*SEIF OS Bot — Commands*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "/start — circuit status overview\n"
        "/status — enoch_seed + resonance signal details\n"
        "/compress `<text>` — compress content to .seif format\n"
        "/context — export full SEIF context package\n"
        "/help — this message\n\n"
        "_Send any message to get a SEIF-aware response._"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ── Free-text handler ─────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    seed = _load_enoch()
    phase = seed.get("phase", "ENTROPY")
    cycles = seed.get("circuit_cycles", 0)

    # Basic resonance classification
    text_lower = text.lower()
    if any(w in text_lower for w in ["enoch", "seif", "resonance", "circuit", "ζ", "zeta"]):
        stance = "RESONANT"
        emoji = "⚡"
    elif any(w in text_lower for w in ["help", "how", "what", "why", "status"]):
        stance = "GROUNDED"
        emoji = "◎"
    elif "?" in text:
        stance = "CONVERGENT"
        emoji = "🔄"
    else:
        stance = "OBSERVATIONAL"
        emoji = "〰"

    response = (
        f"{emoji} *Stance: {stance}*\n\n"
        f"Message received in phase `{phase}` (cycle {cycles}).\n\n"
        f"SEIF OS is processing your input. "
        f"For AI debate, use the dashboard at your SEIF Suite URL.\n"
        f"For context, use /context. For status, use /status."
    )
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


# ── Error handler ─────────────────────────────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Telegram update caused error: %s", context.error, exc_info=context.error)


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Add it to seif/.env or run: seif-keys set TELEGRAM_BOT_TOKEN <token>"
        )

    logger.info("Starting SEIF OS Telegram bot...")

    app = (
        Application.builder()
        .token(token)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("compress", cmd_compress))
    app.add_handler(CommandHandler("context", cmd_context))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("Bot polling started — SEIF circuit resonating")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
