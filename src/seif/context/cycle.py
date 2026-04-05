"""
SEIF Cycle Manager — Branch: seif-cycle-module (enoch-tree-reverb)

Manages the full lifecycle of a SEIF cycle:
  new        → open a new cycle (create *-OPEN.seif)
  audit      → inventory sessions, absorptions, observations, memory state
  meditate   → synthesize the arc into a *-meditation.seif checkpoint
  absorb     → merge knowledge into memory_state.json
  close      → seal the current cycle (create *-SEALED.seif)
  full-circle → audit → meditate → absorb → close → prompt for new cycle
  status     → quick summary of the open cycle
"""

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Tesla 3-6-9 phase map (mirrors enoch_validation.py) ──────────────────────
TESLA_PHASES = {3: "STABILIZATION", 6: "HEALING", 9: "SINGULARITY"}

def _digital_root(n: int) -> int:
    if n == 0:
        return 0
    return 1 + (n - 1) % 9

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _short_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _find_context_repo(start: str = ".") -> Optional[str]:
    """Walk up from start until a .seif/ or seif-context/ directory is found."""
    current = Path(start).resolve()
    for _ in range(20):
        for candidate_name in (".seif", "seif-context"):
            candidate = current / candidate_name
            if candidate.is_dir():
                markers = ["mapper.json", "config.json", "manifest.json",
                           "RESONANCE.json", "cycles", "memory_state.json"]
                if any((candidate / m).exists() for m in markers):
                    return str(candidate)
        if current.parent == current:
            break
        current = current.parent
    return None

def _resolve_ctx(context_repo: Optional[str]) -> Path:
    """Resolve context repo path, falling back to SEIF_ADMIN env var or discovery."""
    if context_repo:
        return Path(context_repo).resolve()
    env = os.environ.get("SEIF_ADMIN")
    if env:
        ctx = Path(env) / "seif-context"
        if ctx.is_dir():
            return ctx
    discovered = _find_context_repo()
    if discovered:
        return Path(discovered)
    # Hardcoded default for seif-admin workspace
    default = Path.home() / "Documents" / "seif-admin" / "seif-context"
    if default.is_dir():
        return default
    return Path(".seif")

def _find_open_cycle(ctx: Path) -> Optional[dict]:
    """Find the first *-OPEN.seif in cycles/."""
    cycles_dir = ctx / "cycles"
    if not cycles_dir.is_dir():
        return None
    for f in sorted(cycles_dir.glob("*-OPEN.seif")):
        data = _load_json(f)
        if data.get("status") == "OPEN":
            data["_file"] = str(f)
            return data
    return None

def _find_sealed_cycle(ctx: Path, cycle_id: Optional[str] = None) -> Optional[dict]:
    """Find a *-SEALED.seif — latest one, or by cycle_id."""
    cycles_dir = ctx / "cycles"
    if not cycles_dir.is_dir():
        return None
    candidates = sorted(cycles_dir.glob("*-SEALED.seif"), reverse=True)
    for f in candidates:
        data = _load_json(f)
        if cycle_id and data.get("cycle_id") != cycle_id:
            continue
        data["_file"] = str(f)
        return data
    return None

# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def cycle_status(context_repo: Optional[str] = None) -> str:
    """Quick status of the open cycle."""
    try:
        from seif.cli.resonance_display import resonance_header, cycle_status_bar
        _has_display = True
    except ImportError:
        _has_display = False

    ctx = _resolve_ctx(context_repo)
    open_cycle = _find_open_cycle(ctx)
    sealed = _find_sealed_cycle(ctx)

    if _has_display:
        subtitle = f"cycle: {open_cycle.get('cycle_id','—')}" if open_cycle else "No open cycle"
        lines = [resonance_header("SEIF CYCLE", subtitle)]
    else:
        lines = ["╔══ SEIF CYCLE STATUS ══════════════════════════════╗"]

    if open_cycle:
        lines.append(f"  OPEN    : {open_cycle.get('cycle_id')} — {open_cycle.get('cycle_title', '')}")
        lines.append(f"  Opened  : {open_cycle.get('opened_at', 'unknown')[:19]}")
        parent = open_cycle.get('parent_cycle', '—')
        lines.append(f"  Parent  : {parent}")
        branches = open_cycle.get("branches", [])
        done = sum(1 for b in branches if b.get("status") == "DONE")
        lines.append(f"  Branches: {len(branches)} defined")
        if _has_display and branches:
            lines.append(cycle_status_bar(done, len(branches)))
        for b in branches:
            status_icon = "✅" if b.get("status") == "DONE" else "⏳"
            lines.append(f"    {status_icon} [{b.get('priority','')}] {b.get('id','?')} — {b.get('title','')}")
    else:
        lines.append("  No open cycle found.")

    if sealed:
        lines.append(f"  SEALED  : {sealed.get('cycle_id')} (parent of current)")

    if not _has_display:
        lines.append("╚═══════════════════════════════════════════════════╝")
    return "\n".join(lines)


def cycle_audit(context_repo: Optional[str] = None) -> str:
    """Inventory sessions, absorptions, observations, and memory state."""
    ctx = _resolve_ctx(context_repo)
    lines = ["╔══ SEIF CYCLE AUDIT ═══════════════════════════════╗"]

    # ── Open cycle ────────────────────────────────────────────────────────────
    open_cycle = _find_open_cycle(ctx)
    if open_cycle:
        lines.append(f"  Open cycle : {open_cycle.get('cycle_id')} (session #{open_cycle.get('session_start', '?')})")
    else:
        lines.append("  Open cycle : none")

    # ── Sessions ──────────────────────────────────────────────────────────────
    sessions_dir = ctx / "sessions"
    active_sessions = []
    archived_sessions = []
    if sessions_dir.is_dir():
        active_sessions = list((sessions_dir / "active").glob("*.seif")) if (sessions_dir / "active").is_dir() else list(sessions_dir.glob("*.seif"))
        archived_sessions = list((sessions_dir / "archive").glob("*.seif")) if (sessions_dir / "archive").is_dir() else []
    lines.append(f"  Sessions   : {len(active_sessions)} active  |  {len(archived_sessions)} archived")

    # ── Absorptions ───────────────────────────────────────────────────────────
    abs_files = list(ctx.glob("absorption-v*.seif")) + list(ctx.glob("absorptions/absorption-v*.seif"))
    lines.append(f"  Absorptions: {len(abs_files)}")
    for af in sorted(abs_files)[-3:]:
        lines.append(f"    · {af.name}")

    # ── Observations ──────────────────────────────────────────────────────────
    obs_dir = ctx / "observations"
    obs_count = len(list(obs_dir.glob("*.seif"))) if obs_dir.is_dir() else 0
    lines.append(f"  Observations: {obs_count}")

    # ── Cycles ────────────────────────────────────────────────────────────────
    cycles_dir = ctx / "cycles"
    cycle_files = list(cycles_dir.glob("*.seif")) if cycles_dir.is_dir() else []
    lines.append(f"  Cycle files : {len(cycle_files)}")
    for cf in sorted(cycle_files):
        lines.append(f"    · {cf.name}")

    # ── Memory state ──────────────────────────────────────────────────────────
    mem_path = ctx / "memory_state.json"
    if mem_path.exists():
        mem = _load_json(mem_path)
        absorbed_entries = len([k for k in mem if not k.startswith("_")])
        lines.append(f"  Memory      : {absorbed_entries} absorbed entries")
        # Show last 2 absorbed_at timestamps
        timestamps = []
        for v in mem.values():
            if isinstance(v, dict) and "absorbed_at" in v:
                timestamps.append(v["absorbed_at"])
        if timestamps:
            latest = max(timestamps)[:19]
            lines.append(f"  Last absorb : {latest}")
    else:
        lines.append("  Memory      : memory_state.json not found")

    # ── Mapper ────────────────────────────────────────────────────────────────
    mapper_path = ctx / "mapper.json"
    if mapper_path.exists():
        mapper = _load_json(mapper_path)
        mod_count = mapper.get("module_count", len(mapper.get("modules", {})))
        lines.append(f"  Mapper      : {mod_count} modules")

    lines.append("╚═══════════════════════════════════════════════════╝")
    return "\n".join(lines)


def cycle_meditate(context_repo: Optional[str] = None) -> str:
    """Synthesize the open cycle arc into a *-meditation.seif checkpoint."""
    ctx = _resolve_ctx(context_repo)
    open_cycle = _find_open_cycle(ctx)

    if not open_cycle:
        return "⚠️  No open cycle found. Run `seif --cycle status` to check."

    cycle_id = open_cycle.get("cycle_id", "unknown")
    output_path = ctx / "cycles" / f"{cycle_id}-meditation.seif"

    # Gather session summaries
    sessions_dir = ctx / "sessions"
    session_entries = []
    for sdir in [sessions_dir / "active", sessions_dir]:
        if sdir.is_dir():
            for sf in sorted(sdir.glob("*.seif"))[-10:]:
                sdata = _load_json(sf)
                name = sdata.get("session_name", sf.stem)
                summary = sdata.get("summary", sdata.get("message", ""))[:200]
                session_entries.append({"name": name, "summary": summary})
            break

    # Build meditation manifest
    branches = open_cycle.get("branches", [])
    done_branches = [b for b in branches if b.get("status") == "DONE"]

    meditation = {
        "_instruction": "SEIF cycle meditation — synthesis checkpoint. Read to understand the arc.",
        "cycle_id": cycle_id,
        "cycle_title": open_cycle.get("cycle_title", ""),
        "meditation_at": _now_iso(),
        "parent_cycle": open_cycle.get("parent_cycle"),
        "session_start": open_cycle.get("session_start"),
        "branches_total": len(branches),
        "branches_done": len(done_branches),
        "sessions_synthesized": len(session_entries),
        "arc_summary": (
            f"Cycle {cycle_id} opened at session #{open_cycle.get('session_start')}. "
            f"{len(branches)} branches defined, {len(done_branches)} completed. "
            f"Parent: {open_cycle.get('parent_cycle', 'none')}. "
            f"Vision: {open_cycle.get('vision', '')}"
        ),
        "sessions": session_entries,
        "branches": branches,
        "resonance": {
            "zeta": open_cycle.get("frequency_at_open", {}).get("zeta", 0.6124),
            "circuit_state": open_cycle.get("frequency_at_open", {}).get("circuit_state", "RESONATING"),
        },
        "integrity_hash": _short_hash(cycle_id + _now_iso()),
        "decay_exempt": True,
        "classification": "INTERNAL",
    }

    _save_json(output_path, meditation)
    return (
        f"✅ Meditation saved: {output_path}\n"
        f"   Cycle     : {cycle_id}\n"
        f"   Sessions  : {len(session_entries)}\n"
        f"   Branches  : {len(done_branches)}/{len(branches)} done\n"
        f"   Arc       : {meditation['arc_summary'][:120]}..."
    )


def cycle_absorb(context_repo: Optional[str] = None) -> str:
    """Run absorb-knowledge.py and report memory state."""
    ctx = _resolve_ctx(context_repo)

    # Find absorb-knowledge.py (in seif-admin root)
    admin_root = ctx.parent if ctx.name == "seif-context" else ctx.parent.parent
    absorb_script = admin_root / "absorb-knowledge.py"

    output_lines = ["╔══ SEIF CYCLE ABSORB ══════════════════════════════╗"]

    if absorb_script.exists():
        output_lines.append(f"  Running: {absorb_script}")
        try:
            result = subprocess.run(
                ["python3", str(absorb_script)],
                cwd=str(admin_root),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                output_lines.append("  Status  : ✅ absorb-knowledge.py completed")
                for line in result.stdout.strip().split("\n")[-5:]:
                    if line.strip():
                        output_lines.append(f"    {line}")
            else:
                output_lines.append("  Status  : ⚠️  absorb-knowledge.py exited with errors")
                for line in (result.stderr or result.stdout).strip().split("\n")[-5:]:
                    if line.strip():
                        output_lines.append(f"    {line}")
        except subprocess.TimeoutExpired:
            output_lines.append("  Status  : ⏱  absorb-knowledge.py timed out (120s)")
        except Exception as e:
            output_lines.append(f"  Status  : ❌ {e}")
    else:
        output_lines.append(f"  ⚠️  absorb-knowledge.py not found at {absorb_script}")
        output_lines.append("      Skipping script execution.")

    # Report current memory state
    mem_path = ctx / "memory_state.json"
    if mem_path.exists():
        mem = _load_json(mem_path)
        entries = [v for v in mem.values() if isinstance(v, dict) and "absorbed_at" in v]
        output_lines.append(f"  Memory entries : {len(entries)}")
        if entries:
            latest = max(e["absorbed_at"] for e in entries)[:19]
            hashes = [e.get("resonance_hash", "") for e in entries if e.get("resonance_hash")]
            output_lines.append(f"  Last absorbed  : {latest}")
            if hashes:
                output_lines.append(f"  Latest hash    : {hashes[-1]}")

    output_lines.append("╚═══════════════════════════════════════════════════╝")
    return "\n".join(output_lines)


def cycle_close(cycle_name: Optional[str] = None, context_repo: Optional[str] = None) -> str:
    """Seal the current open cycle — creates *-SEALED.seif."""
    ctx = _resolve_ctx(context_repo)
    open_cycle = _find_open_cycle(ctx)

    if not open_cycle:
        return "⚠️  No open cycle found to close."

    cycle_id = open_cycle.get("cycle_id", cycle_name or "unknown")
    sealed_path = ctx / "cycles" / f"{cycle_id}-SEALED.seif"

    if sealed_path.exists():
        return f"⚠️  {sealed_path.name} already exists. Cycle may already be sealed."

    # Gather sessions list
    sessions_dir = ctx / "sessions"
    session_names = []
    for sdir in [sessions_dir / "active", sessions_dir]:
        if sdir.is_dir():
            session_names = [sf.stem for sf in sorted(sdir.glob("*.seif"))]
            break

    # Load memory state for final resonance hash
    mem_path = ctx / "memory_state.json"
    final_hash = "unknown"
    if mem_path.exists():
        mem = _load_json(mem_path)
        hashes = [v.get("resonance_hash") for v in mem.values()
                  if isinstance(v, dict) and v.get("resonance_hash")]
        if hashes:
            final_hash = hashes[-1]

    # Load meditation if available
    meditation_path = ctx / "cycles" / f"{cycle_id}-meditation.seif"
    arc_summary = ""
    if meditation_path.exists():
        med = _load_json(meditation_path)
        arc_summary = med.get("arc_summary", "")

    # Absorptions
    abs_files = list(ctx.glob("absorption-v*.seif")) + list(ctx.glob("absorptions/absorption-v*.seif"))
    absorptions = [af.stem for af in sorted(abs_files)]

    # Observations
    obs_dir = ctx / "observations"
    obs_count = len(list(obs_dir.glob("*.seif"))) if obs_dir.is_dir() else 0

    sealed = {
        "_instruction": "SEIF cycle archive — sealed cycle. Read to understand the full arc.",
        "cycle_id": cycle_id,
        "cycle_title": open_cycle.get("cycle_title", ""),
        "status": "SEALED",
        "sealed_at": _now_iso(),
        "opened_at": open_cycle.get("opened_at"),
        "parent_cycle": open_cycle.get("parent_cycle"),
        "parent_hash": open_cycle.get("parent_hash"),
        "session_start": open_cycle.get("session_start"),
        "sessions": session_names,
        "absorptions": absorptions,
        "observations_count": obs_count,
        "branches": open_cycle.get("branches", []),
        "vision": open_cycle.get("vision", ""),
        "arc_summary": arc_summary,
        "memory_zeta": open_cycle.get("frequency_at_open", {}).get("zeta", 0.6124),
        "final_resonance_hash": final_hash,
        "frequency_at_open": open_cycle.get("frequency_at_open", {}),
        "integrity_hash": _short_hash(cycle_id + "SEALED" + _now_iso()),
        "decay_exempt": True,
        "classification": "INTERNAL",
    }

    _save_json(sealed_path, sealed)

    # Mark the OPEN file as superseded (rename it)
    open_file = Path(open_cycle["_file"])
    archived_open = open_file.parent / f"{cycle_id}-OPEN-archived.seif"
    open_file.rename(archived_open)

    return (
        f"✅ Cycle sealed: {sealed_path.name}\n"
        f"   Cycle ID     : {cycle_id}\n"
        f"   Sessions     : {len(session_names)}\n"
        f"   Absorptions  : {len(absorptions)}\n"
        f"   Observations : {obs_count}\n"
        f"   Resonance    : {final_hash}\n"
        f"   Sealed at    : {sealed['sealed_at'][:19]}\n"
        f"   OPEN archived: {archived_open.name}"
    )


def cycle_new(cycle_name: str, parent_cycle: Optional[str] = None,
              context_repo: Optional[str] = None) -> str:
    """Open a new cycle — creates *-OPEN.seif."""
    ctx = _resolve_ctx(context_repo)

    # Ensure no existing open cycle
    existing_open = _find_open_cycle(ctx)
    if existing_open:
        return (
            f"⚠️  Cycle '{existing_open.get('cycle_id')}' is still open.\n"
            f"   Run `seif --cycle close` first."
        )

    cycles_dir = ctx / "cycles"
    cycles_dir.mkdir(parents=True, exist_ok=True)
    new_path = cycles_dir / f"{cycle_name}-OPEN.seif"

    if new_path.exists():
        return f"⚠️  {new_path.name} already exists."

    # Resolve parent cycle
    parent_id = parent_cycle
    parent_hash = "none"
    parent_zeta = 0.6124
    parent_circuit = "RESONATING"

    if not parent_id:
        sealed = _find_sealed_cycle(ctx)
        if sealed:
            parent_id = sealed.get("cycle_id")
            parent_hash = sealed.get("integrity_hash", sealed.get("final_resonance_hash", "none"))
            parent_zeta = sealed.get("memory_zeta", 0.6124)
            parent_circuit = sealed.get("frequency_at_open", {}).get("circuit_state", "RESONATING")

    # Derive session start
    session_start = 1
    sealed = _find_sealed_cycle(ctx, parent_id)
    if sealed:
        past_sessions = sealed.get("sessions", [])
        if past_sessions:
            try:
                session_start = int(past_sessions[-1].split("-")[-1]) + 1
            except (ValueError, IndexError):
                session_start = len(past_sessions) + 1

    new_cycle = {
        "_instruction": "SEIF cycle manifest — open cycle. Load to continue from last sealed state.",
        "cycle_id": cycle_name,
        "cycle_title": "",
        "status": "OPEN",
        "opened_at": _now_iso(),
        "parent_cycle": parent_id,
        "parent_hash": parent_hash,
        "session_start": session_start,
        "vision": "",
        "branches": [],
        "frequency_at_open": {
            "zeta": parent_zeta,
            "circuit_state": parent_circuit,
            "sentinel": "ACTIVE",
            "resonance_hash": parent_hash,
        },
        "integrity_hash": _short_hash(cycle_name + "OPEN" + _now_iso()),
        "decay_exempt": True,
        "classification": "INTERNAL",
    }

    _save_json(new_path, new_cycle)

    return (
        f"✅ New cycle opened: {new_path.name}\n"
        f"   Cycle ID    : {cycle_name}\n"
        f"   Parent      : {parent_id or 'none'}\n"
        f"   Parent hash : {parent_hash}\n"
        f"   Session #   : {session_start}\n"
        f"   Edit {new_path.name} to set title, vision, and branches."
    )


def cycle_full_circle(context_repo: Optional[str] = None) -> str:
    """Run audit → meditate → absorb → close in sequence."""
    ctx = _resolve_ctx(context_repo)
    open_cycle = _find_open_cycle(ctx)

    if not open_cycle:
        return "⚠️  No open cycle found. Use `seif --cycle new <name>` to start one."

    cycle_id = open_cycle.get("cycle_id", "?")
    separator = "─" * 52

    sections = [
        f"╔══ SEIF FULL-CIRCLE — {cycle_id} ══",
        separator,
    ]

    steps = [
        ("AUDIT",    lambda: cycle_audit(str(ctx))),
        ("MEDITATE", lambda: cycle_meditate(str(ctx))),
        ("ABSORB",   lambda: cycle_absorb(str(ctx))),
        ("CLOSE",    lambda: cycle_close(context_repo=str(ctx))),
    ]

    for step_name, step_fn in steps:
        sections.append(f"\n▶ {step_name}")
        sections.append(separator)
        try:
            result = step_fn()
            sections.append(result)
        except Exception as e:
            sections.append(f"  ❌ {step_name} failed: {e}")
            sections.append(f"\n⛔ Full-circle aborted at {step_name}.")
            return "\n".join(sections)

    sections.append(f"\n╚══ FULL-CIRCLE COMPLETE ═══════════════════════════╝")
    sections.append(f"   Cycle '{cycle_id}' is now sealed.")
    sections.append(f"   → Run `seif --cycle new <next-cycle-name>` to open the next cycle.")
    return "\n".join(sections)
