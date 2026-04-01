"""
seif — S.E.I.F. Unified CLI (single source of truth)

One command for everything:
    seif                        # interactive Claude + SEIF context
    seif -g                     # interactive Gemini + SEIF context
    seif -p "message"           # non-interactive (print mode)
    seif --status               # show context hierarchy
    seif --init                 # initialize .seif in current directory
    seif --sync                 # re-sync git context
    seif --quality-gate "text"  # measure text quality (Grade A-F)
    seif --compress             # semantic code compression
    seif --consult "question"   # inter-AI consultation
    ... (all admin flags available)

Architecture: `seif` detects intent from argv.
  - Session flags (-g, -p, --status, no args) → launch AI with SEIF context
  - Admin flags (--init, --sync, --quality-gate, etc.) → delegate to cli.py
  - `seif-cli` is kept as alias (same entry point) for backwards compatibility
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Flags that belong to the session wrapper (everything else → cli.py)
_SESSION_FLAGS = {'-g', '--gemini', '-p', '--print', '--status', '-h', '--help', 'chat', 'serve'}


def _is_session_mode() -> bool:
    """Determine if the user wants a session (wrapper) or admin (cli) mode.

    Rules:
      - No args at all → session (launch Claude)
      - Only session flags (-g, -p, --status) → session
      - Any flag starting with -- that isn't a session flag → admin (cli.py)
      - Positional text without flags → admin (cli.py pipeline)
    """
    argv = sys.argv[1:]

    if not argv:
        return True

    for arg in argv:
        if arg.startswith('-') and arg not in _SESSION_FLAGS:
            return False
        if not arg.startswith('-'):
            # Positional argument → could be text for pipeline or extra args for AI
            # If there are session flags present, treat as extra AI args
            # Otherwise, it's pipeline text → admin mode
            has_session_flag = any(a in _SESSION_FLAGS for a in argv)
            return has_session_flag

    return True


def _build_global_prompt() -> str:
    """Layer 1: SEIF_HOME context (KERNEL + defaults — always present)."""
    try:
        from seif.context.context_manager import build_startup_context
        return build_startup_context()
    except Exception:
        return "S.E.I.F. protocol active."


def _build_local_prompt() -> str:
    """Layer 2: Local context (RESONANCE.json or .seif/ in cwd)."""
    cwd = Path.cwd()
    parts = []

    if (cwd / "RESONANCE.json").exists():
        parts.append(f"[LOCAL PROJECT: {cwd} has RESONANCE.json]")

    seif_dir = cwd / ".seif"
    if not seif_dir.is_dir():
        # Check parent (SCR pattern)
        parent_seif = cwd.parent / ".seif"
        if parent_seif.is_dir():
            seif_dir = parent_seif

    if seif_dir.is_dir():
        seif_files = sorted(seif_dir.glob("*.seif"))
        if seif_files:
            try:
                from seif.context.context_manager import load_module
                modules = []
                for f in seif_files:
                    try:
                        m = load_module(str(f))
                        if m.active:
                            modules.append(
                                f"MODULE ({m.source}, {m.compression_ratio:.0f}:1):\n"
                                f"{m.summary[:500]}"
                            )
                    except Exception:
                        pass
                if modules:
                    parts.append("[LOCAL .seif MODULES]")
                    parts.append("\n---\n".join(modules))
            except Exception:
                pass

    if parts:
        return "\n\n".join(parts)

    # No local SEIF context — provide workspace status
    has_git = (cwd / ".git").is_dir()
    manifest = "none"
    for mf in ("pyproject.toml", "package.json", "Cargo.toml", "go.mod", "pom.xml", "Gemfile"):
        if (cwd / mf).exists():
            manifest = mf
            break

    subdirs = ", ".join(
        d.name + "/" for d in sorted(cwd.iterdir())
        if d.is_dir() and not d.name.startswith(".")
    )[:80] or "none"

    return (
        f"[WORKSPACE STATUS: {cwd}]\n"
        f"No .seif/ structure found. This directory has not been initialized with S.E.I.F.\n"
        f"Git repo: {'yes' if has_git else 'no'} | Manifest: {manifest} | Subdirs: {subdirs}\n"
        f"The user may benefit from running: seif --init\n"
        f"If they ask what to do, guide them through initialization and available features."
    )


def _build_prompt() -> str:
    """Assemble full startup prompt: global + local layers."""
    global_prompt = _build_global_prompt()
    local_prompt = _build_local_prompt()
    return f"{global_prompt}\n\n{local_prompt}"


def _signal_protocol_status():
    """Signal to the human that the protocol loaded correctly."""
    from seif.context.context_manager import estimate_tokens, list_modules
    from seif.core.resonance_signal import load_and_validate
    from seif.data.paths import get_resonance_path

    resonance_path = get_resonance_path()
    if not resonance_path.exists():
        print("[SEIF] KERNEL not found. Running without protocol.", file=sys.stderr)
        return

    try:
        signal, valid, msg = load_and_validate(str(resonance_path))
    except Exception as e:
        print(f"[SEIF] KERNEL load error: {e}", file=sys.stderr)
        return

    if not valid:
        print(f"[SEIF] KERNEL INVALID — {msg}", file=sys.stderr)
        print("[SEIF] Integrity compromised. Protocol NOT loaded.", file=sys.stderr)
        return

    try:
        tokens = estimate_tokens()
        modules = list_modules()
        active_count = sum(1 for m in modules if m.get("active", True))

        cwd = Path.cwd()
        local_seif = (cwd / ".seif").is_dir() or (cwd.parent / ".seif").is_dir()
        local_resonance = (cwd / "RESONANCE.json").exists()

        version = signal.get("protocol", "unknown")
        zeta = signal.get("validation", {}).get("zeta", 0)
        phi_inv = signal.get("validation", {}).get("phi_inverse", 0)
        dev_pct = signal.get("validation", {}).get("zeta_phi_deviation_pct", 0)

        print(f"[SEIF] Protocol: {version} | KERNEL: VALID", file=sys.stderr)
        print(
            f"[SEIF] Context: {active_count} modules, "
            f"~{tokens['total']} tokens ({tokens['total']/2000:.1f}K)",
            file=sys.stderr,
        )
        print(
            f"[SEIF] Signal: zeta={zeta:.6f}, phi_inv={phi_inv:.6f}, "
            f"deviation={dev_pct}%",
            file=sys.stderr,
        )

        if local_seif:
            seif_dir = cwd / ".seif" if (cwd / ".seif").is_dir() else cwd.parent / ".seif"
            local_count = len(list(seif_dir.glob("*.seif")))
            print(f"[SEIF] Local: .seif/ found ({local_count} modules)", file=sys.stderr)
        elif local_resonance:
            print("[SEIF] Local: RESONANCE.json found", file=sys.stderr)
        else:
            print("[SEIF] Local: no .seif/ (run seif --init to add)", file=sys.stderr)

        # Conjugate pair status
        try:
            seif_dir = cwd / ".seif" if (cwd / ".seif").is_dir() else cwd.parent / ".seif"
            config_path = seif_dir / "config.json" if seif_dir.is_dir() else None
            if config_path and config_path.exists():
                import json as _json
                config = _json.load(open(config_path))
                cp = config.get("conjugate_pair", {})
                if cp.get("enabled"):
                    co = cp.get("co_author", "not configured")
                    print(f"[SEIF] Conjugate pair: co-author={co}", file=sys.stderr)
                else:
                    print(
                        "[SEIF] Conjugate pair: not configured. "
                        "Consider: seif --config co-author=<model>",
                        file=sys.stderr,
                    )
        except Exception:
            pass

        print("[SEIF] The gate resonates.", file=sys.stderr)
    except Exception:
        print("[SEIF] Protocol: VALID | Context loaded.", file=sys.stderr)


def _has_command(name: str) -> bool:
    """Check if a CLI command is available."""
    return shutil.which(name) is not None


def _launch_claude(prompt: str, print_mode: bool, extra_args: list[str]):
    """Launch Claude CLI with SEIF context.

    DEPRECATION NOTICE (2026-03-31, Session 17):
    Interactive session mode (`seif` without args) is deprecated.
    Evidence: 2 crashes (CLAUDE_WRAPPER_CRASH_V2) caused by VSCode wrapper
    context overflow, 0 crashes using `claude` CLI directly with CLAUDE.md.

    Preferred alternatives:
      - Interactive: `claude` (loads SEIF via CLAUDE.md automatically)
      - Native chat: `seif chat` (SDK direct, quality gate, multi-backend)
      - Quick query: `seif -p "question"` (still supported, safe)

    The wrapper adds --append-system-prompt which duplicates what CLAUDE.md
    already provides, while introducing a subprocess layer that inherits
    IDE context management issues.

    Decision documented in: .seif/projects/seif/decisions.seif v14
    """
    if not print_mode:
        print(
            "[SEIF] DEPRECATION: Interactive wrapper mode is deprecated.\n"
            "[SEIF] Use 'claude' directly (CLAUDE.md loads SEIF automatically)\n"
            "[SEIF] or 'seif chat' for native chat with quality gate.\n"
            "[SEIF] Reason: 2 crashes in wrapper vs 0 in CLI (Session 17).\n"
            "[SEIF] Continuing anyway...",
            file=sys.stderr,
        )

    if not _has_command("claude"):
        print("Error: Claude CLI not found. Install it first.", file=sys.stderr)
        sys.exit(1)

    args = ["claude"]
    if print_mode:
        args.append("--print")
    args.extend(["--append-system-prompt", prompt])
    args.extend(extra_args)

    os.execvp("claude", args)


def _launch_gemini(prompt: str, print_mode: bool, extra_args: list[str]):
    """Launch Gemini CLI with SEIF context."""
    if not _has_command("gemini"):
        print("Error: Gemini CLI not found. Install it first.", file=sys.stderr)
        sys.exit(1)

    args = ["gemini", "-m", "gemini-2.5-flash"]
    if print_mode:
        args.append("-p")
    args.extend(extra_args)

    subprocess.run(args, input=prompt, text=True)


def cmd_status():
    """Show context hierarchy."""
    from seif.context.context_manager import estimate_tokens, list_modules
    from seif.data.paths import get_resonance_path

    print("═══ S.E.I.F. STATUS ═══")
    cwd = Path.cwd()
    print(f"CWD: {cwd}")
    print()

    # Local context
    if (cwd / "RESONANCE.json").exists():
        print("Local RESONANCE.json: FOUND")
    if (cwd / ".seif").is_dir():
        count = len(list((cwd / ".seif").glob("*.seif")))
        print(f"Local .seif/ modules: {count} files")
    elif (cwd.parent / ".seif").is_dir():
        count = len(list((cwd.parent / ".seif").glob("*.seif")))
        print(f"Parent .seif/ modules (SCR): {count} files")
    print()

    # Global context
    resonance = get_resonance_path()
    print(f"RESONANCE.json: {resonance}")
    exists = resonance.exists()
    print(f"  Status: {'FOUND' if exists else 'NOT FOUND'}")

    if exists:
        try:
            from seif.core.resonance_signal import load_and_validate
            _, valid, msg = load_and_validate(str(resonance))
            print(f"  Validation: {'VALID' if valid else 'INVALID'} — {msg}")
        except Exception as e:
            print(f"  Validation: ERROR — {e}")
    print()

    # Modules
    try:
        modules = list_modules()
        tokens = estimate_tokens()
        print(f"Modules: {len(modules)}")
        for m in modules:
            marker = "[default]" if m.get("is_default") else "[user]"
            active = "" if m.get("active") else " (inactive)"
            print(f"  {marker} {m['source']} — {m['words']}w, "
                  f"{m['compression']:.0f}:1, coh={m['coherence']:.3f}{active}")
        print()
        print(f"Total tokens: ~{tokens['total']}")
        print(f"  Kernel: {tokens['kernel']} + Modules: {tokens['modules']}")
    except Exception as e:
        print(f"Module listing error: {e}")


def _run_session(argv: list[str]):
    """Parse session-mode flags and launch AI backend."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="seif",
        description="S.E.I.F. — one command, full protocol",
        epilog=(
            "Session mode (default):\n"
            "  seif                    Interactive Claude + SEIF context\n"
            "  seif -g                 Interactive Gemini + SEIF context\n"
            "  seif -p \"message\"       Non-interactive (print mode)\n"
            "  seif --status           Show context hierarchy\n"
            "\n"
            "Admin mode (all seif features):\n"
            "  seif --init             Initialize .seif in current directory\n"
            "  seif --sync             Re-sync git context\n"
            "  seif --quality-gate TXT Measure text quality (Grade A-F)\n"
            "  seif --compress         Semantic code compression\n"
            "  seif --consult Q        Inter-AI consultation\n"
            "  seif --help-admin       Show all admin commands\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-g", "--gemini", action="store_true",
                        help="Use Gemini instead of Claude")
    parser.add_argument("-p", "--print", action="store_true", dest="print_mode",
                        help="Non-interactive (print mode)")
    parser.add_argument("--status", action="store_true",
                        help="Show context hierarchy")
    parser.add_argument("args", nargs="*", help="Extra arguments passed to the AI CLI")

    parsed = parser.parse_args(argv)

    if parsed.status:
        cmd_status()
        return

    prompt = _build_prompt()
    _signal_protocol_status()

    if parsed.gemini:
        _launch_gemini(prompt, parsed.print_mode, parsed.args)
    else:
        _launch_claude(prompt, parsed.print_mode, parsed.args)


def main():
    """Unified entry point: session mode, chat mode, or admin mode based on argv."""
    argv = sys.argv[1:]

    # Native chat mode: seif chat [--backend X] [--no-stream] [--no-gate]
    if argv and argv[0] == "chat":
        _run_chat(argv[1:])
    elif argv and argv[0] == "serve":
        _run_serve(argv[1:])
    elif _is_session_mode():
        _run_session(argv)
    else:
        # Delegate to cli.py (admin mode)
        from seif.cli.cli import main as cli_main
        cli_main()


def _run_chat(argv: list[str]):
    """Parse chat flags and launch native client."""
    import argparse

    parser = argparse.ArgumentParser(prog="seif chat",
                                     description="Native AI chat with SEIF context")
    parser.add_argument("--backend", "-b", default="auto",
                        help="AI backend: claude, gemini, local, auto (default: auto)")
    parser.add_argument("--model", "-m", default="",
                        help="Model override (default: auto per backend)")
    parser.add_argument("--no-stream", action="store_true",
                        help="Disable streaming (wait for full response)")
    parser.add_argument("--no-gate", action="store_true",
                        help="Disable quality gate on responses")

    parsed = parser.parse_args(argv)

    from seif.cli.chat import run_chat
    run_chat(
        backend=parsed.backend,
        model=parsed.model,
        stream=not parsed.no_stream,
        quality_gate=not parsed.no_gate,
    )


def _run_serve(argv: list[str]):
    """Parse serve flags and launch context API server."""
    import argparse

    parser = argparse.ArgumentParser(prog="seif serve",
                                     description="SEIF Context API — read-only local server")
    parser.add_argument("--port", "-p", type=int, default=7331,
                        help="Port to listen on (default: 7331)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Host to bind (default: 127.0.0.1, localhost only)")
    parser.add_argument("--max-classification", default="INTERNAL",
                        choices=["PUBLIC", "INTERNAL"],
                        help="Maximum classification to expose (default: INTERNAL)")
    parser.add_argument("--v2", action="store_true",
                        help="Enable v2 API (sessions, quality gate, owner auth)")

    parsed = parser.parse_args(argv)

    if parsed.v2:
        from seif.cli.serve_v2 import run_server_v2
        run_server_v2(
            host=parsed.host,
            port=parsed.port,
            max_classification=parsed.max_classification,
        )
    else:
        from seif.cli.serve import run_server
        run_server(
            host=parsed.host,
            port=parsed.port,
            max_classification=parsed.max_classification,
        )


if __name__ == "__main__":
    main()
