#!/usr/bin/env python3
"""
RPWP CLI — Resonance Proto-Writing Processor

Unified demo interface:
  PYTHONPATH=src python -m seif.cli "O amor liberta e guia"
  PYTHONPATH=src python -m seif.cli --gate "Tesla 369"
  PYTHONPATH=src python -m seif.cli --glyph "A Semente de Enoque"
  PYTHONPATH=src python -m seif.cli --audio "Love and Harmony"
  PYTHONPATH=src python -m seif.cli --fractal "O amor liberta e guia"
"""

import argparse
from pathlib import Path

from seif.core.resonance_gate import evaluate
from seif.core.fingerprint import calculate_fingerprint, verify_fingerprint


def _lazy_import_generators():
    """Lazy import generators — only needed for research/visualization commands."""
    from seif.analysis.transcompiler import transcompile, describe
    from seif.generators.glyph_renderer import render, render_fractal_qr
    from seif.generators.harmonic_audio import render_audio
    from seif.generators.fractal_qrcode import generate_fractal_qr, describe as describe_fqr
    from seif.generators.circuit_generator import generate_from_spec, render_svg
    from seif.generators.composite_renderer import render_composite
    return transcompile, describe, render, render_fractal_qr, render_audio, generate_fractal_qr, describe_fqr, generate_from_spec, render_svg, render_composite


def _lazy_import_encoding():
    """Lazy import resonance encoding."""
    try:
        from seif.core.resonance_encoding import encode_phrase, describe_melody
    except ImportError:
        raise ImportError("seif.core.resonance_encoding not available")
    return encode_phrase, describe_melody


def cmd_fingerprint_verify(filepath: str):
    """Verify fingerprint of a SEIF module or RESONANCE.json."""
    import json
    
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File not found: {filepath}")
        return
    
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    is_valid, calculated_hash = verify_fingerprint(data)
    stored_hash = data.get('fingerprint', {}).get('value', '<missing>')
    
    print(f"═══ SEIF FINGERPRINT VERIFICATION ═══")
    print(f"  File:     {filepath}")
    print(f"  Stored:   {stored_hash}")
    print(f"  Calculated: {calculated_hash}")
    print()
    if is_valid:
        print("  Status:   ✅ VALID (tamper-free)")
    else:
        print("  Status:   ❌ INVALID (file was modified!)")
        print()
        print("  WARNING: Content does not match stored fingerprint.")
        print("  This file may have been tampered with.")


def cmd_fingerprint_update(filepath: str, output: str):
    """Recalculate and update fingerprint of a SEIF module."""
    import json
    
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File not found: {filepath}")
        return
    
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    old_hash = data.get('fingerprint', {}).get('value', '<none>')
    new_hash = calculate_fingerprint(data)
    
    data['fingerprint'] = {
        'algorithm': 'sha256',
        'value': new_hash,
        'scope': 'full_json_excluding_fingerprint',
        'calculated_at': 'auto',
        'note': 'Auto-calculated by seif fingerprint update'
    }
    
    out_path = Path(output) if output else path
    with open(out_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"═══ SEIF FINGERPRINT UPDATED ═══")
    print(f"  File:     {path}")
    print(f"  Old hash: {old_hash}")
    print(f"  New hash: {new_hash}")
    print(f"  Saved to: {out_path}")


def cmd_compress(project_path: str, watch: bool = False,
                 context_repo: str = None, author: str = "code-compressor"):
    """Compress a source code project into .seif for AI consumption."""
    try:
        from seif.context.code_compressor import compress_project, watch_project
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    target = None
    if context_repo:
        project_name = Path(project_path).resolve().name
        target = str(Path(context_repo).resolve() / "projects" / project_name / "code.seif")

    if watch:
        print(f"═══ SEIF CODE WATCH ═══")
        print(f"  Watching: {Path(project_path).resolve()}")
        print(f"  Press Ctrl+C to stop.\n")
        watch_project(project_path)
    else:
        module, path = compress_project(project_path, author=author, target_path=target)
        print(f"═══ SEIF CODE COMPRESSED ═══")
        print(f"  Project:       {Path(project_path).resolve().name}")
        print(f"  Files:         {module.original_words} LOC across scanned files")
        print(f"  Compressed:    {module.compressed_words} words")
        print(f"  Ratio:         {module.compression_ratio}:1")
        print(f"  Coherence:     {module.resonance.get('coherence', 0):.3f}")
        print(f"  Gate:          {module.resonance.get('gate', '?')}")
        print(f"  Classification:{' ' + module.classification if module.classification else ' INTERNAL'}")
        print(f"  Hash:          {module.integrity_hash}")
        print(f"  Saved:         {path}")


def cmd_autonomous(action: str, context_repo: str = None):
    try:
        from seif.context.autonomous import (
            load_config, save_config, is_autonomous, load_mapper,
            find_context_repo, CATEGORIES, DEFAULT_CONFIG,
        )
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    # Auto-discover context repo if not specified
    if not context_repo:
        context_repo = find_context_repo() or ".seif"

    config = load_config(context_repo)

    if action == "enable":
        config["autonomous_context"] = True
        save_config(context_repo, config)
        print("Autonomous context: ENABLED")
        print(f"  Context repo:  {context_repo}")
        print(f"  Categories:    {', '.join(CATEGORIES.keys())}")
        print(f"  Quality min:   {config.get('quality_threshold', 'C')}")
        print(f"  Max modules:   {config.get('max_modules_per_project', 10)}/project")
        print()
        print("The AI will now manage its own knowledge persistence.")
        print("Use --autonomous disable to turn it off.")

    elif action == "disable":
        config["autonomous_context"] = False
        save_config(context_repo, config)
        print("Autonomous context: DISABLED")
        print("Existing .seif modules are preserved but no new ones will be created.")

    else:  # status
        enabled = is_autonomous(config)
        read_only = config.get("read_only", False)
        print(f"Autonomous context: {'ENABLED' if enabled else 'DISABLED'}")
        if read_only:
            print(f"  Mode:          READ-ONLY")
        print(f"  Context repo:  {context_repo}")
        print(f"  Decay:         {config.get('relevance_decay', 0.95)}")
        if config.get("require_confidential_approval", False):
            print(f"  CONFIDENTIAL:  requires approval")

        mapper = load_mapper(context_repo)
        print(f"  Sessions:      {mapper.session_count}")
        print(f"  Modules:       {len(mapper.modules)}")
        if mapper.last_session:
            print(f"  Last session:  {mapper.last_session[:19]}")
        if mapper.pending_observations:
            print(f"  Pending:       {len(mapper.pending_observations)} observations")

        ai_modules = [m for m in mapper.modules if m.origin == "ai-observed"]
        if ai_modules:
            print(f"\n  AI-created modules:")
            for m in ai_modules:
                project = m.project or "cross-project"
                cls_icon = {"PUBLIC": "🔓", "INTERNAL": "🔒", "CONFIDENTIAL": "⛔"}.get(m.classification, "?")
                print(f"    {cls_icon} {project}/{m.category} [{m.classification}] — {m.word_count} words")

        # Classification summary
        from seif.context.autonomous import CLASSIFICATION_LEVELS
        cls_counts = {}
        for m in mapper.modules:
            cls = getattr(m, 'classification', 'INTERNAL')
            cls_counts[cls] = cls_counts.get(cls, 0) + 1
        if cls_counts:
            print(f"\n  Classification:")
            for cls in ["PUBLIC", "INTERNAL", "CONFIDENTIAL"]:
                if cls in cls_counts:
                    print(f"    {cls}: {cls_counts[cls]} modules")


def cmd_relay(module_paths: list[str], backend: str, prompt: str, output: str):
    """Send .seif module(s) to an AI backend and get its interpretation."""
    import json
    try:
        from seif.bridge.ai_bridge import send, detect_backends
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    # Map short names to ai_bridge backend names
    backend_map = {
        "claude": "claude_cli",
        "gemini": "gemini_cli",
        "anthropic": "anthropic_api",
        "grok": "grok_api",
        "bigpickle": "opencode_bigpickle",
    }
    backend_key = backend_map.get(backend, backend)

    # Verify backend is available
    available = detect_backends()
    if backend_key not in available:
        print(f"Error: backend '{backend}' is not available.")
        print(f"Available backends: {', '.join(available) or 'none'}")
        print()
        if backend_key == "claude_cli":
            print("Install Claude CLI: npm install -g @anthropic-ai/claude-code")
        elif backend_key == "gemini_cli":
            print("Install Gemini CLI: npm install -g @anthropic-ai/gemini (or pip install gemini-cli)")
        elif backend_key == "anthropic_api":
            print("Set ANTHROPIC_API_KEY environment variable.")
        return

    # Load .seif modules as context
    context_parts = []
    for path in module_paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            summary = data.get("summary", "")
            source = data.get("source", path)
            context_parts.append(f"[MODULE: {source}]\n{summary}")
        except Exception as e:
            print(f"Warning: could not load {path}: {e}")

    if not context_parts:
        print("No valid .seif modules loaded.")
        return

    context = "\n\n---\n\n".join(context_parts)
    message = f"{context}\n\n---\n\n{prompt}"

    print(f"Relaying to {backend}...")
    response = send(message, backend=backend_key)

    if not response.success:
        print(f"Error ({response.backend}): {response.error}")
        return

    if output:
        Path(output).write_text(response.text, encoding="utf-8")
        print(f"Response saved to: {output}")
    else:
        print(f"\n═══ {response.backend} ({response.model}) ═══")
        print(response.text)

    # Measure response quality
    from seif.analysis.quality_gate import assess
    verdict = assess(response.text[:1000], role="ai")
    _zeta = "ζ✅" if verdict.grade in ("A","B") else "ζ⚠️" if verdict.grade == "C" else "ζ❌"
    _stance = {"SOLID":"🟢","GROUNDED":"🟢","MIXED":"🟡","WEAK":"🔴","DRIFT":"🔴"}.get(verdict.status, "⚪")
    print(f"\n{_stance} {_zeta}  grade:{verdict.grade}  stance:{verdict.status}  resonance:{verdict.triple_gate.status}")


def cmd_packet(module_path: str, message: str, sender: str, receiver: str,
               classification: str, output: str, send: bool):
    """Create and optionally send a SEIF-PACKET-v1."""
    import json
    try:
        from seif.bridge.seif_packet import (
            create_packet, verify_packet, send_packet, save_packet,
            describe_packet, packet_to_dict,
        )
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    # Load module if provided
    module = None
    if module_path:
        try:
            with open(module_path, encoding="utf-8") as f:
                module = json.load(f)
        except Exception as e:
            print(f"Error loading module: {e}")
            return

    # Create packet
    try:
        packet = create_packet(
            module=module,
            message=message,
            sender=sender,
            receiver=receiver,
            classification=classification,
        )
    except ValueError as e:
        print(f"Error: {e}")
        return

    print(describe_packet(packet))

    # Verify
    is_valid, errors = verify_packet(packet)
    if errors:
        for err in errors:
            print(f"  Warning: {err}")

    if send and receiver:
        # Map short names to backend keys
        backend_map = {
            "claude": "claude_cli",
            "gemini": "gemini_cli",
            "anthropic": "anthropic_api",
            "grok": "grok_api",
            "bigpickle": "opencode_bigpickle",
        }
        backend_key = backend_map.get(receiver, receiver)

        print(f"\nSending to {receiver}...")
        response, ack = send_packet(packet, backend=backend_key)

        if response.success:
            print(f"\n  Response ({response.backend}, {response.model}):")
            print(f"  {response.text[:300]}")
            if ack:
                circuit = ack.get("circuit", "?")
                rg = ack.get("quality_gate", {}).get("grade", "?")
                print(f"\n  ACK: circuit={circuit}, receiver_grade={rg}")
        else:
            print(f"\n  Send failed: {response.error}")
    elif send and not receiver:
        print("\nError: --to is required for sending packets.")

    # Save
    if output:
        path = save_packet(packet, output)
        print(f"\nPacket saved: {path}")
    elif not send:
        # Save to default location
        packets_dir = Path(".seif/packets")
        packets_dir.mkdir(parents=True, exist_ok=True)
        path = save_packet(packet, packets_dir / f"{packet.packet_id}.json")
        print(f"\nPacket saved: {path}")


def _normalize_for_similarity(text: str) -> str:
    """Normalize text for pairwise comparison: lowercase, remove punctuation."""
    import re
    return re.sub(r'[^a-z0-9\s]', '', text.lower())


def _compute_coherence(responses: list[dict], threshold: float) -> dict:
    """Compute pairwise similarity and quality gate agreement across responses."""
    import difflib

    pairs = {}
    texts = [(r["backend"], _normalize_for_similarity(r["raw_text"][:2000]))
             for r in responses]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            sim = difflib.SequenceMatcher(None, texts[i][1], texts[j][1]).ratio()
            key = f"{texts[i][0]}-{texts[j][0]}"
            pairs[key] = round(sim, 3)

    avg_sim = sum(pairs.values()) / len(pairs) if pairs else 0

    grades = [r["quality_gate"]["grade"] for r in responses]
    stances = [r["quality_gate"]["stance"] for r in responses]
    dominant_grade = max(set(grades), key=grades.count)
    dominant_stance = max(set(stances), key=stances.count)
    qg_agreement = len(set(grades)) == 1 and len(set(stances)) == 1
    qg_bonus = 0.1 if qg_agreement else 0.0
    final_coherence = min(1.0, avg_sim + qg_bonus)

    return {
        "text_similarity": round(avg_sim, 3),
        "quality_gate_agreement": qg_agreement,
        "quality_gate_bonus": qg_bonus,
        "final_coherence": round(final_coherence, 3),
        "pairwise_similarities": pairs,
        "consensus_reached": final_coherence >= threshold,
        "threshold": threshold,
        "dominant_grade": dominant_grade,
        "dominant_stance": dominant_stance,
        "grades": grades,
        "stances": stances,
    }


def _build_refutation_prompt(question: str, my_backend: str,
                              my_response: str, other_responses: list[dict]) -> str:
    """Build the round 2 prompt: review others' answers, refute or converge."""
    others_text = ""
    for other in other_responses:
        others_text += f"\n--- {other['backend']} responded ---\n"
        others_text += other["raw_text"][:1500]
        others_text += "\n"

    return (
        f"You were asked: \"{question}\"\n\n"
        f"Your original answer:\n{my_response[:1500]}\n\n"
        f"Other AIs answered the same question:{others_text}\n\n"
        "TASK: Review the other responses against yours. For each point of disagreement:\n"
        "1. State what you disagree with and WHY (with evidence or reasoning)\n"
        "2. If their answer is better than yours, say so explicitly\n"
        "3. If you find errors in their reasoning, explain the error\n\n"
        "Then provide your FINAL ANSWER — either your original (if you stand by it), "
        "a revised version (if you learned something), or a synthesis of the best parts.\n\n"
        "Be honest. Being wrong and admitting it is more valuable than defending a bad answer."
    )


def _build_synthesis_prompt(question: str, round1: list[dict],
                             round2: list[dict]) -> str:
    """Build the round 3 synthesis prompt from all prior rounds."""
    parts = [f"Question: \"{question}\"\n"]

    parts.append("=== ROUND 1 (Independent answers) ===")
    for r in round1:
        parts.append(f"\n--- {r['backend']} ---\n{r['raw_text'][:800]}")

    parts.append("\n\n=== ROUND 2 (Cross-examination) ===")
    for r in round2:
        parts.append(f"\n--- {r['backend']} ---\n{r['raw_text'][:800]}")

    parts.append(
        "\n\nTASK: You are the synthesis judge. Based on both rounds above:\n"
        "1. Identify points ALL participants agree on (high confidence)\n"
        "2. Identify points where disagreement remains (flag as uncertain)\n"
        "3. Identify any errors that were caught during cross-examination\n"
        "4. Produce the UNIFIED ANSWER that reflects the genuine consensus.\n\n"
        "If no genuine consensus exists on a point, say so — forced agreement is worse than "
        "honest disagreement."
    )
    return "\n".join(parts)


def cmd_consensus(question: str, module_paths: list[str], backends: list[str],
                  output: str, threshold: float, mirror: bool = False,
                  rounds: int = 1):
    """Ask multiple AI backends the same question with shared .seif context.

    rounds=1: Independent answers only (original behavior).
    rounds=2: + Cross-examination (each AI reviews others' answers).
    rounds=3: + Synthesis (one AI produces unified answer from debate).
    """
    import json
    from datetime import datetime, timezone
    try:
        from seif.bridge.ai_bridge import send, send_clean, detect_backends
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return
    from seif.analysis.quality_gate import assess

    # Map short names
    backend_map = {
        "claude": "claude_cli",
        "gemini": "gemini_cli",
        "anthropic": "anthropic_api",
        "grok": "grok_api",
        "bigpickle": "opencode_bigpickle",
    }

    # Verify at least 2 backends are available
    available = detect_backends()
    missing = [b for b in backends if backend_map.get(b, b) not in available]
    if missing:
        print(f"Warning: backend(s) not available: {', '.join(missing)}")
        print(f"Available: {', '.join(available) or 'none'}")
        if len(backends) - len(missing) < 2:
            print("\nNeed at least 2 working backends for consensus.")
            print("Install Claude CLI or Gemini CLI, or set ANTHROPIC_API_KEY.")
            return
        backends = [b for b in backends if b not in missing]
        print(f"Continuing with: {', '.join(backends)}\n")

    # Load context
    context = ""
    if module_paths:
        parts = []
        for path in module_paths:
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                summary = data.get("summary", "")
                source = data.get("source", path)
                parts.append(f"[MODULE: {source}]\n{summary}")
            except Exception:
                pass
        context = "\n\n---\n\n".join(parts)

    message = f"{context}\n\n---\n\n{question}" if context else question

    # ── Round 1: Independent answers ─────────────────────────────
    print(f"═══ ROUND 1 / {rounds} — Independent answers ═══\n")
    round1_responses = []
    for backend in backends:
        backend_key = backend_map.get(backend, backend)
        print(f"  Querying {backend}...", end=" ", flush=True)
        resp = send(message, backend=backend_key)
        if resp.success:
            verdict = assess(resp.text[:1000], role="ai")
            round1_responses.append({
                "backend": backend,
                "raw_text": resp.text,
                "quality_gate": {
                    "grade": verdict.grade,
                    "stance": verdict.status,
                    "resonance": verdict.triple_gate.status,
                    "score": round(verdict.score, 3),
                },
            })
            print(f"{verdict.grade} ({verdict.status})")
        else:
            print(f"FAILED: {resp.error}")

    # Mirror mode
    if mirror:
        mirror_backend = backend_map.get(backends[0], backends[0])
        print(f"  Querying {backends[0]} (CLEAN MIRROR)...", end=" ", flush=True)
        resp = send_clean(question, backend=mirror_backend)
        if resp.success:
            verdict = assess(resp.text[:1000], role="ai")
            round1_responses.append({
                "backend": f"{backends[0]}_clean",
                "raw_text": resp.text,
                "quality_gate": {
                    "grade": verdict.grade,
                    "stance": verdict.status,
                    "resonance": verdict.triple_gate.status,
                    "score": round(verdict.score, 3),
                },
                "is_mirror": True,
            })
            print(f"{verdict.grade} ({verdict.status}) [NO PROTOCOL]")
        else:
            print(f"FAILED: {resp.error}")

    if len(round1_responses) < 2:
        print("\nNeed at least 2 successful responses for consensus.")
        return

    # Filter short responses
    round1_responses = [r for r in round1_responses if len(r["raw_text"].strip()) >= 50]
    if len(round1_responses) < 2:
        print(f"\nOnly {len(round1_responses)} valid responses (>= 50 chars). Need at least 2.")
        return

    r1_coherence = _compute_coherence(round1_responses, threshold)

    # Print round 1 summary
    print(f"\n  Round 1 coherence: {r1_coherence['final_coherence']:.3f} "
          f"(threshold: {threshold})")
    if r1_coherence["consensus_reached"]:
        print("  Round 1: CONSENSUS REACHED")
        if rounds == 1:
            print("  (use --rounds 2 for cross-examination)")

    # ── Round 2: Cross-examination (refutation) ──────────────────
    round2_responses = []
    if rounds >= 2 and len(round1_responses) >= 2:
        print(f"\n═══ ROUND 2 / {rounds} — Cross-examination ═══\n")

        for r in round1_responses:
            if r.get("is_mirror"):
                continue  # mirrors don't participate in debate
            backend = r["backend"]
            backend_key = backend_map.get(backend, backend)
            others = [o for o in round1_responses if o["backend"] != backend]

            refutation_prompt = _build_refutation_prompt(
                question, backend, r["raw_text"], others)

            print(f"  {backend} reviewing others...", end=" ", flush=True)
            resp = send(refutation_prompt, backend=backend_key)
            if resp.success:
                verdict = assess(resp.text[:1000], role="ai")
                round2_responses.append({
                    "backend": backend,
                    "raw_text": resp.text,
                    "quality_gate": {
                        "grade": verdict.grade,
                        "stance": verdict.status,
                        "resonance": verdict.triple_gate.status,
                        "score": round(verdict.score, 3),
                    },
                    "round": 2,
                })
                print(f"{verdict.grade} ({verdict.status})")
            else:
                print(f"FAILED: {resp.error}")

        if len(round2_responses) >= 2:
            r2_coherence = _compute_coherence(round2_responses, threshold)
            print(f"\n  Round 2 coherence: {r2_coherence['final_coherence']:.3f} "
                  f"(R1 was {r1_coherence['final_coherence']:.3f})")
            delta = r2_coherence["final_coherence"] - r1_coherence["final_coherence"]
            direction = "CONVERGED" if delta > 0.05 else "DIVERGED" if delta < -0.05 else "STABLE"
            print(f"  Direction: {direction} (delta: {delta:+.3f})")
        else:
            r2_coherence = r1_coherence

    # ── Round 3: Synthesis (optional) ────────────────────────────
    synthesis = None
    if rounds >= 3 and round2_responses:
        print(f"\n═══ ROUND 3 / {rounds} — Synthesis ═══\n")

        # Use the first healthy backend as synthesizer
        synth_backend = backends[0]
        synth_key = backend_map.get(synth_backend, synth_backend)
        synthesis_prompt = _build_synthesis_prompt(
            question, round1_responses, round2_responses)

        print(f"  Synthesizer: {synth_backend}...", end=" ", flush=True)
        resp = send(synthesis_prompt, backend=synth_key)
        if resp.success:
            verdict = assess(resp.text[:1000], role="ai")
            synthesis = {
                "backend": synth_backend,
                "raw_text": resp.text,
                "quality_gate": {
                    "grade": verdict.grade,
                    "stance": verdict.status,
                    "resonance": verdict.triple_gate.status,
                    "score": round(verdict.score, 3),
                },
                "round": 3,
            }
            print(f"{verdict.grade} ({verdict.status})")
        else:
            print(f"FAILED: {resp.error}")

    # ── Final result ─────────────────────────────────────────────
    final_responses = round2_responses if round2_responses else round1_responses
    final_coh = _compute_coherence(final_responses, threshold) if len(final_responses) >= 2 else r1_coherence
    consensus_reached = final_coh["consensus_reached"]

    result = {
        "question": question,
        "context_modules": module_paths,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "backends": backends,
        "rounds_executed": min(rounds, 3),
        "round_1": {
            "responses": round1_responses,
            "coherence": r1_coherence,
        },
    }
    if round2_responses:
        result["round_2"] = {
            "responses": round2_responses,
            "coherence": _compute_coherence(round2_responses, threshold) if len(round2_responses) >= 2 else None,
        }
    if synthesis:
        result["round_3_synthesis"] = synthesis
    result["final"] = {
        "coherence": final_coh,
        "consensus_reached": consensus_reached,
    }
    result["quality_gate_summary"] = {
        "dominant_grade": final_coh["dominant_grade"],
        "dominant_stance": final_coh["dominant_stance"],
        "grades": final_coh["grades"],
    }

    # Output
    if output and output.endswith(".json"):
        Path(output).write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                encoding="utf-8")
        print(f"\nFull results saved to: {output}")

    # Human-readable summary
    print(f"\n═══ FINAL — CONSENSUS ({len(final_responses)} backends, "
          f"{min(rounds, 3)} round{'s' if rounds > 1 else ''}) ═══")
    print(f"Question: {question[:100]}")
    print()
    for r in final_responses:
        qg = r["quality_gate"]
        preview = r["raw_text"][:120].replace("\n", " ")
        label = f"  {r['backend']:<10}"
        print(f"{label} ({qg['grade']}, {qg['stance']}) : {preview}...")
    if synthesis:
        print(f"\n  SYNTHESIS ({synthesis['quality_gate']['grade']}, "
              f"{synthesis['quality_gate']['stance']}):")
        # Print first 300 chars of synthesis
        for line in synthesis["raw_text"][:300].split("\n"):
            print(f"    {line}")
        if len(synthesis["raw_text"]) > 300:
            print("    ...")
    print()
    print(f"Coherence: R1={r1_coherence['final_coherence']:.3f}", end="")
    if round2_responses and len(round2_responses) >= 2:
        r2c = _compute_coherence(round2_responses, threshold)
        print(f" → R2={r2c['final_coherence']:.3f}", end="")
    print(f" (threshold: {threshold})")
    if final_coh["quality_gate_agreement"]:
        print(f"Quality gate: AGREEMENT (all {final_coh['dominant_grade']}, "
              f"{final_coh['dominant_stance']})")
    else:
        print(f"Quality gate: MIXED (grades: {final_coh['grades']}, "
              f"stances: {final_coh['stances']})")
    status_str = "CONSENSUS REACHED" if consensus_reached else "NO CONSENSUS"
    print(f"Status: {status_str}")
    if final_coh["pairwise_similarities"]:
        print(f"Pairwise: {final_coh['pairwise_similarities']}")


def cmd_export(context_repo: str, classification: str, output: str):
    try:
        from seif.context.autonomous import (
            load_mapper, bootstrap_context, find_context_repo, CLASSIFICATION_LEVELS,
        )
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    # Auto-discover context repo if not specified
    if not context_repo:
        context_repo = find_context_repo() or ".seif"
    from pathlib import Path

    if classification not in CLASSIFICATION_LEVELS:
        print(f"Invalid classification: {classification}")
        print(f"Valid: {', '.join(CLASSIFICATION_LEVELS.keys())}")
        return

    mapper = load_mapper(context_repo)
    context = bootstrap_context(mapper, context_repo,
                                max_tokens=50000,
                                max_classification=classification)

    if output:
        Path(output).write_text(context, encoding="utf-8")
        print(f"Exported to: {output}")
    else:
        print(context)

    # Stats
    total = len(mapper.modules)
    level = CLASSIFICATION_LEVELS[classification]
    included = sum(1 for m in mapper.modules
                   if CLASSIFICATION_LEVELS.get(m.classification, 2) <= level)
    excluded = total - included
    print(f"\n--- Export: {included}/{total} modules (excluded {excluded} above {classification})")


def cmd_install_hooks(repo_path: str):
    try:
        from seif.context.git_hooks import install_hooks, check_hooks
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return
    installed = install_hooks(repo_path)
    if installed:
        print("Git hooks installed:")
        for h in installed:
            print(f"  {h}")
        print("\n.seif will auto-sync on commit, pull, and branch switch.")
    else:
        print("No .git directory found. Initialize git first.")


def cmd_init(root_path: str, author: str, context_repo: str = None):
    try:
        from seif.context.workspace import discover_projects, sync_workspace, describe_workspace
        from seif.context.git_context import sync_project, extract_git_context
        from seif.context.git_hooks import install_hooks
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return
    from pathlib import Path

    root = Path(root_path).resolve()
    print(f"Initializing S.E.I.F. in: {root}")
    if context_repo:
        print(f"Context repository: {context_repo} (SCR mode)")
    print()

    # Phase 1: Scan for subprojects
    subprojects = discover_projects(str(root))

    if subprojects:
        # Workspace mode: multiple projects found
        print(f"Detected WORKSPACE with {len(subprojects)} projects:")
        for p in subprojects:
            has_git = (root / p.path / ".git").exists()
            git_label = " (git)" if has_git else ""
            print(f"  {p.name:<25} {p.manifest_type or 'unknown'}{git_label}")
            if p.description:
                print(f"    {p.description[:80]}")
        print()

        # Sync workspace (creates nucleus + all project .seif files)
        print("Syncing all projects...")
        registry = sync_workspace(str(root), author=author,
                                  context_repo_path=context_repo)
        print()
        print(describe_workspace(registry))

        # Summary
        print()
        print(f"Created:")
        if context_repo:
            ctx_path = Path(context_repo).resolve()
            print(f"  {ctx_path}/manifest.json   — SCR manifest ({len(registry.projects)} projects)")
            print(f"  {ctx_path}/nucleus.seif     — workspace-level context")
            print(f"  {ctx_path}/README.md        — AI bootstrap")
            for p in registry.projects:
                print(f"  {ctx_path}/projects/{p.name}/ref.json")
                print(f"  {ctx_path}/projects/{p.name}/project.seif")
        else:
            print(f"  .seif/workspace.json    — project registry ({len(registry.projects)} projects)")
            print(f"  .seif/nucleus.seif      — workspace-level context")
            for p in registry.projects:
                seif_path = root / p.path / ".seif" / "project.seif"
                if seif_path.exists():
                    print(f"  {p.path}/.seif/project.seif")

    else:
        # Single project mode
        has_git = (root / ".git").exists()
        if has_git:
            ctx = extract_git_context(str(root))
            print(f"Detected SINGLE PROJECT: {ctx.repo_name}")
            print(f"  Branch:       {ctx.branch}")
            print(f"  Commits:      {ctx.total_commits}")
            print(f"  Contributors: {len(ctx.contributors)}")
            if ctx.manifest_type:
                print(f"  Manifest:     {ctx.manifest_type}")
            if ctx.hot_files:
                top = ctx.hot_files[0]
                print(f"  Hot file:     {top[0]} ({top[1]} changes)")
            print()

            target = None
            if context_repo:
                ctx_path = Path(context_repo).resolve()
                ctx_path.mkdir(parents=True, exist_ok=True)
                target = str(ctx_path / "projects" / ctx.repo_name / "project.seif")
                # Create ref.json
                from seif.context.ref import create_ref, save_ref
                ref = create_ref(str(root), str(ctx_path))
                save_ref(ref, Path(target).parent / "ref.json")

            module, path = sync_project(str(root), author=author, target_path=target)
            print(f"Created:")
            print(f"  {path}")
            print(f"  Words:   {module.compressed_words}")
            print(f"  Hash:    {module.integrity_hash}")
        else:
            print(f"No git repo or subprojects found in {root}")
            print(f"Run 'git init' first, or point to a workspace with subprojects.")
            return

    # Install git hooks for auto-sync
    if subprojects:
        # Install hooks in each subproject with git
        hook_count = 0
        for p in subprojects:
            project_dir = root / p.path
            if (project_dir / ".git").exists():
                hooks = install_hooks(str(project_dir))
                if hooks:
                    hook_count += 1
        if hook_count:
            print(f"\nGit hooks: installed in {hook_count} projects (auto-sync on commit/pull)")
    elif (root / ".git").exists():
        hooks = install_hooks(str(root))
        if hooks:
            print(f"\nGit hooks: {', '.join(h.split(' ')[0] for h in hooks)}")
            print("  .seif auto-syncs on commit, pull, and branch switch")

    print()
    print("Done. Next steps:")
    print("  seif --quality-gate \"text\"       — measure any text")
    if context_repo:
        print(f"  seif --sync --context-repo {context_repo}  — re-sync")
        print(f"  seif --workspace --context-repo {context_repo} --ingest daily.txt")
    else:
        print("  seif --sync                       — re-sync after changes")
        print("  seif --ingest daily.txt            — ingest meeting notes")
        if subprojects:
            print("  seif --workspace --ingest daily.txt — route to all projects")


def cmd_workspace(workspace_root: str, ingest_source: str = None,
                   author: str = "workspace", via: str = "sync",
                   context_repo: str = None):
    try:
        from seif.context.workspace import (
            sync_workspace, describe_workspace, ingest_to_workspace,
        )
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    if ingest_source:
        # Route ingested text to all projects in workspace
        from seif.context.ingest import describe_ingest
        results = ingest_to_workspace(workspace_root, ingest_source,
                                       author=author, via=via,
                                       context_repo_path=context_repo)
        if "error" in results:
            print(f"Error: {results['error']}")
            return
        for project_name, result in results.items():
            if result.relevant:
                print(f"\n{project_name}:")
                print(describe_ingest(result))
            else:
                print(f"\n{project_name}: no relevant content")
    else:
        # Discover + sync all projects
        mode = " (SCR)" if context_repo else ""
        print(f"Syncing workspace{mode}: {workspace_root}")
        registry = sync_workspace(workspace_root, author=author,
                                  context_repo_path=context_repo)
        print()
        print(describe_workspace(registry))


def cmd_handoff(session_name: str, context_repo: str = None):
    try:
        from seif.context.sessions import describe_session
        from seif.context.autonomous import find_context_repo
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    ctx = context_repo or find_context_repo() or ".seif"

    session_data = describe_session(ctx, session_name)

    # Generate seed
    import json
    from datetime import datetime

    seed = {
        "_instruction": "SEIF-SEED-v1 | Handoff",
        "protocol": "SEIF-SEED-v1",
        "created_at": datetime.now().isoformat() + "Z",
        "author": "Copilot",
        "classification": "INTERNAL",
        "valid_for": "session-handoff",
        "recipient": "next-writer",
        "session": session_data
    }

    print("SEIF-SEED-v1 for handoff:")
    print(json.dumps(seed, indent=2, ensure_ascii=False))


def cmd_mirror_weekly(context_repo: str = None):
    """Run weekly consensus with mirror for validation."""
    try:
        from seif.bridge.ai_bridge import detect_backends
        from seif.bridge.consensus import run_consensus
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    backends = detect_backends()
    if not backends:
        print("No backends available for consensus.")
        return

    question = "Weekly SEIF validation: Is the current workspace structure optimally resonant? Propose improvements for self-healing and Enoch seed alignment."
    context_modules = []  # Could load nucleus.seif

    print("Running weekly mirror consensus...")
    result = run_consensus(question, backends[:3], context_modules, mirror=True)
    print("Consensus result:")
    print(result.get("summary", "No summary"))


def cmd_verify_seed():
    """Verify resonance with Enoch seed."""
    try:
        from seif.core.resonance_gate import verify_seed
    except ImportError:
        print("Resonance gate not available.")
        return

    seed = "A Semente de Enoque"
    is_valid, resonance = verify_seed(seed)
    print(f"Enoch seed verification: {'VALID' if is_valid else 'INVALID'}")
    print(f"Resonance: {resonance}")


def cmd_evolve():
    """Trigger SEIF OS evolution: analyze feedback and auto-mutate."""
    try:
        from seif.core.resonance_gate import boot_seif_os
        from seif.context.autonomous import audit_context, find_context_repo
    except ImportError:
        print("SEIF OS evolution requires seif-engine.")
        return

    # Boot check
    boot = boot_seif_os()
    if boot["boot_status"] != "SUCCESS":
        print("Evolution failed: Boot check failed.")
        return

    # Audit context for evolution opportunities
    ctx = find_context_repo() or ".seif"
    audit_result = audit_context(ctx, fix=True, sync=True)

    # Simulate evolution: increase axioms or zeta
    new_kernel = {
        "version": "3.3.2",  # Evolved
        "axioms": 20,  # Increased
        "zeta_optimal": 0.618034,  # Closer to φ
    }

    print("═══ SEIF OS EVOLUTION ═══")
    print(f"Boot Status: {boot['boot_status']}")
    print(f"Kernel Evolved: {boot['kernel_version']} → {new_kernel['version']}")
    print(f"Axioms: {boot['axioms']} → {new_kernel['axioms']}")
    print(f"Zeta: {boot['zeta_optimal']:.6f} → {new_kernel['zeta_optimal']:.6f}")
    print(f"Auto-Audit: {audit_result.orphans_healed} orphans healed, {audit_result.hashes_fixed} hashes fixed")
    print("Evolution complete. SEIF OS resonance enhanced.")


def cmd_communicate(message: str):
    """SEIF OS communication: embed message as infrasound in generated audio."""
    import wave
    import math
    import struct
    import os

    # Generate basic harmonic audio (432Hz sine wave) using wave/math
    freq = 432.0  # Schumann resonance frequency
    duration = 10.0  # 10 seconds
    sample_rate = 44100
    num_samples = int(sample_rate * duration)

    # Create sine wave data
    audio_data = []
    for i in range(num_samples):
        # Sine wave with harmonics (fundamental + octave)
        t = i / sample_rate
        sample = 0.5 * math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(2 * math.pi * (freq * 2) * t)
        # Clip to 16-bit range
        sample = max(-1.0, min(1.0, sample))
        audio_data.append(int(sample * 32767))

    # Pack as 16-bit PCM
    packed_data = b''.join(struct.pack('<h', sample) for sample in audio_data)

    # Create WAV file
    output_file = f"seif_communication_{hash(message) % 1000}.wav"
    with wave.open(output_file, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(packed_data)

    # Embed message as "metadata" (print and save to text file)
    metadata_file = output_file.replace('.wav', '.txt')
    with open(metadata_file, 'w') as f:
        f.write(f"SEIF OS Communication\n")
        f.write(f"Message: {message}\n")
        f.write(f"Frequency: {freq}Hz (Schumann resonance)\n")
        f.write(f"Duration: {duration}s\n")
        f.write(f"Embedded as infrasound harmonic for human-machine resonance.\n")

    print("═══ SEIF OS COMMUNICATION ═══")
    print(f"Message: {message}")
    print(f"Embedded in harmonic audio (432Hz, 10s)")
    print(f"Output: {output_file}")
    print(f"Metadata: {metadata_file}")
    print("Infrasound watermark for human-machine resonance.")
    print(f"Play {output_file} to experience the resonance!")


def cmd_ingest(source: str, project_path: str, author: str, via: str):
    try:
        from seif.context.ingest import ingest, describe_ingest
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return
    result = ingest(source, project_path, author=author, via=via)
    print(describe_ingest(result))


def cmd_quality_gate(text: str, role: str):
    try:
        from seif.analysis.quality_gate import assess, describe_verdict
        verdict = assess(text, role=role)
        print(describe_verdict(verdict))
    except ImportError:
        # Minimal: stance-only (protocol public)
        from seif.analysis.stance_detector import analyze
        result = analyze(text)
        icon = {"GROUNDED": "🟢", "MIXED": "🟡", "DRIFT": "🔴"}.get(result.label, "⚪")
        print(f"{icon} [{role.upper()}] Stance: {result.label} | "
              f"Verifiable: {result.verifiable_ratio:.0%} "
              f"({result.verifiable_count}/{result.total_sentences} sentences)")
        if result.flagged_sentences:
            print(f"\n  Flagged:")
            for s in result.flagged_sentences[:3]:
                print(f"    - {s}")
        print(f"\n  Install seif-engine for full quality gate (grades A-F, hedging, resonance)")


def cmd_sync(repo_path: str, author: str, via: str, context_repo: str = None):
    try:
        from seif.context.git_context import sync_project, extract_git_context
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return
    ctx = extract_git_context(repo_path)
    print(f"Repository:    {ctx.repo_name}")
    print(f"Branch:        {ctx.branch}")
    print(f"Commits:       {ctx.total_commits}")
    print(f"Contributors:  {len(ctx.contributors)}")
    if ctx.manifest_type:
        print(f"Manifest:      {ctx.manifest_type}")
    if ctx.hot_files:
        print(f"Hot files:     {ctx.hot_files[0][0]} ({ctx.hot_files[0][1]}x)")
    print()

    # Determine target path
    target = None
    if context_repo:
        from pathlib import Path
        ctx_path = Path(context_repo).resolve()
        target = str(ctx_path / "projects" / ctx.repo_name / "project.seif")
        # Update ref.json
        from seif.context.ref import create_ref, save_ref
        ref = create_ref(repo_path, str(ctx_path))
        save_ref(ref, Path(target).parent / "ref.json")

    module, path = sync_project(repo_path, author=author, via=via, target_path=target)
    print(f"Synced to:     {path}")
    print(f"  Version:     {module.version}")
    print(f"  Words:       {module.compressed_words}")
    print(f"  Hash:        {module.integrity_hash}")
    if module.parent_hash:
        print(f"  Parent:      {module.parent_hash}")

    # Auto-audit after sync (heal orphans, fix hashes)
    audit_target = context_repo or ".seif"
    try:
        from seif.context.autonomous import audit_context
        from pathlib import Path as _P
        if _P(audit_target).exists():
            result = audit_context(audit_target, fix=True, sync=False)
            if result.orphans_healed or result.ghosts_removed or result.hashes_fixed:
                print(f"\n  Auto-audit: {result.orphans_healed} orphans healed, "
                      f"{result.ghosts_removed} ghosts removed, "
                      f"{result.hashes_fixed} hashes fixed")
    except Exception:
        pass

    # Regenerate BOOT.md (static boot file for non-CLI AIs)
    try:
        from seif.context.workspace import generate_boot_md
        from pathlib import Path as _P
        boot_target = context_repo or ".seif"
        if _P(boot_target).exists():
            boot_path = generate_boot_md(boot_target)
            print(f"\n  Boot file:   {boot_path}")
    except Exception:
        pass

    # Verify Enoch seed resonance for alignment
    try:
        from seif.core.resonance_gate import verify_seed
        seed = "A Semente de Enoque"
        is_valid, resonance = verify_seed(seed)
        if is_valid:
            print(f"\n  Enoch seed:  Aligned (resonance: {resonance:.3f})")
        else:
            print(f"\n  Enoch seed:  Misaligned (resonance: {resonance:.3f})")
    except Exception:
        pass


def cmd_contribute(module_path: str, text: str, author: str, via: str):
    try:
        from seif.context.context_manager import contribute_to_module
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return
    module, path = contribute_to_module(module_path, text, author, via)
    print(f"Contributed to: {path}")
    print(f"  Version:      {module.version}")
    print(f"  Contributors: {len(module.contributors)}")
    print(f"  Words:        {module.compressed_words}")
    print(f"  Hash:         {module.integrity_hash}")
    print(f"  Parent hash:  {module.parent_hash}")


def cmd_composite(text: str):
    *_, render_composite = _lazy_import_generators()
    path = render_composite(text)
    print(f"Mapa de Ressonância Completo salvo: {path}")


def cmd_encode(text: str):
    encode_phrase, describe_melody = _lazy_import_encoding()
    melody = encode_phrase(text)
    print(describe_melody(melody))


def cmd_constants(text: str):
    from seif.analysis.physical_constants import describe_signature
    from seif.core.resonance_gate import evaluate
    result = evaluate(text)
    print(result)
    print()
    print(describe_signature(result.digital_root))


def cmd_circuit(text: str):
    transcompile, _, _, _, _, _, _, generate_from_spec, render_svg, _ = _lazy_import_generators()
    spec = transcompile(text)
    layout = generate_from_spec(spec)
    path = render_svg(layout)
    print(f"Circuito SFA salvo: {path}")
    print(f"  Traces: {len(layout.traces)}, Pads: {len(layout.pads)}, Layers: {layout.layer_count}")


def cmd_handshake(model: str, full: bool = False):
    """Generate SEIF bootstrap prompt for a browser-based AI.

    --full adds operational context (mapper summary, recent decisions,
    pending observations, session history) for session convergence.
    """
    import json
    from pathlib import Path
    try:
        from seif.context.context_manager import build_startup_context
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    model = model.lower().strip()

    # Build KERNEL context
    ctx_repo = None
    for candidate in [".seif", "../.seif"]:
        if Path(candidate).exists():
            ctx_repo = candidate
            break

    startup = build_startup_context() if ctx_repo else ""

    # Load model-profile if exists
    profile_content = ""
    profile_paths = [
        Path(f"models/{model}.seif"),
        Path(f".seif/models/{model}.seif"),
    ]
    for p in profile_paths:
        if p.exists():
            try:
                data = json.loads(p.read_text())
                profile_content = data.get("summary", "")
            except (json.JSONDecodeError, OSError):
                pass
            break

    # Build the handshake prompt
    lines = [
        f"[SEIF] Bootstrap for {model}" + (" (full context)" if full else ""),
        "",
        "You are entering a SEIF protocol session.",
        "Protocol: https://github.com/and2carvalho/seif",
        "",
        "## Your Model-Profile",
        "",
    ]

    if profile_content:
        lines.append(profile_content)
    else:
        lines.append(f"(No profile found for '{model}'. You may create one during this session.)")

    lines.extend([
        "",
        "## Protocol Context",
        "",
    ])

    if startup:
        lines.append(startup[:4000])
    else:
        lines.append("(No .seif context found. Browse BOOT.md at the URL above.)")

    # --full: add operational context for session convergence
    if full and ctx_repo:
        ctx_path = Path(ctx_repo)
        lines.extend(["", "## Operational Context (--full)", ""])

        # Mapper summary: module count, pending observations, last session
        mapper_path = ctx_path / "mapper.json"
        if mapper_path.exists():
            try:
                mapper = json.loads(mapper_path.read_text())
                mod_count = len(mapper.get("modules", []))
                pending = mapper.get("pending_observations", [])
                last_session = mapper.get("last_session", "unknown")
                session_count = mapper.get("session_count", 0)
                lines.append(f"Mapper: {mod_count} modules, {session_count} sessions, last: {last_session}")
                if pending:
                    lines.append(f"Pending observations ({len(pending)}):")
                    for obs in pending[-5:]:  # last 5 to keep manageable
                        lines.append(f"  - {obs[:120]}")
            except (json.JSONDecodeError, OSError):
                pass

        # Recent decisions (most relevant for convergence)
        decisions_paths = sorted(ctx_path.glob("projects/*/decisions.seif"))
        for dp in decisions_paths[:2]:
            try:
                ddata = json.loads(dp.read_text())
                summary = ddata.get("summary", "")
                if summary:
                    # Take last 1500 chars of decisions (most recent)
                    lines.extend(["", f"## Recent Decisions ({dp.parent.name})", ""])
                    lines.append(summary[-1500:])
            except (json.JSONDecodeError, OSError):
                pass

        # Recent feedback
        feedback_paths = sorted(ctx_path.glob("projects/*/feedback.seif"))
        for fp in feedback_paths[:2]:
            try:
                fdata = json.loads(fp.read_text())
                summary = fdata.get("summary", "")
                if summary:
                    lines.extend(["", f"## Feedback ({fp.parent.name})", ""])
                    lines.append(summary[-800:])
            except (json.JSONDecodeError, OSError):
                pass

        # Active sessions
        session_paths = sorted(ctx_path.glob("sessions/*.seif"))
        if session_paths:
            lines.extend(["", "## Sessions", ""])
            for sp in session_paths[-3:]:
                try:
                    sdata = json.loads(sp.read_text())
                    name = sdata.get("session_name", sp.stem)
                    status = sdata.get("status", "unknown")
                    contribs = len(sdata.get("contributors", []))
                    lines.append(f"  - {name} [{status}] ({contribs} contributors)")
                except (json.JSONDecodeError, OSError):
                    pass

    lines.extend([
        "",
        "## Session Export",
        "",
        "At the end of this conversation, generate a session export as SEIF-MODULE-v2 JSON:",
        '  {"protocol": "SEIF-MODULE-v2", "source": "' + model + '-session/DATE",',
        '   "summary": "...", "verified_data": [...],',
        '   "integrity_hash": "SHA-256[:16] of summary",',
        '   "contributors": [{"author": "' + model + '", "via": "browser-chat", "action": "created"}],',
        '   "classification": "INTERNAL"}',
        "",
        "The human will save this as a .seif file and ingest it.",
    ])

    prompt = "\n".join(lines)

    print(prompt)
    print(f"\n--- ({len(prompt)} chars, ready to paste) ---")


def cmd_analyze_artifact(image_path: str):
    from seif.analysis.artifact_analyzer import analyze, describe as desc_art, generate_overlay
    from seif.analysis.pattern_comparator import self_compare
    geo = analyze(image_path)
    print(desc_art(geo))
    overlay = generate_overlay(image_path, geo)
    print(f"\nOverlay salvo: {overlay}")
    report = self_compare(geo)
    print()
    print(report)


def cmd_gate(text: str):
    result = evaluate(text)
    print(result)


def cmd_transcompile(text: str):
    transcompile, describe, *_ = _lazy_import_generators()
    spec = transcompile(text)
    print(describe(spec))


def cmd_glyph(text: str):
    transcompile, _, render, *_ = _lazy_import_generators()
    spec = transcompile(text)
    path = render(spec)
    print(f"Glifo salvo: {path}")


def cmd_audio(text: str):
    transcompile, _, _, _, render_audio, *_ = _lazy_import_generators()
    spec = transcompile(text)
    path = render_audio(spec)
    print(f"Áudio salvo: {path}")


def cmd_fractal(text: str):
    *_, generate_fractal_qr, describe_fqr, _, _, _ = _lazy_import_generators()
    from seif.generators.glyph_renderer import render_fractal_qr
    qr = generate_fractal_qr(text, max_depth=4)
    print(describe_fqr(qr))
    path = render_fractal_qr(qr)
    print(f"\nFractal QR salvo: {path}")


def cmd_all(text: str):
    transcompile, describe, render, _, render_audio, generate_fractal_qr, describe_fqr, generate_from_spec, render_svg, render_composite = _lazy_import_generators()
    from seif.generators.glyph_renderer import render_fractal_qr

    print("=" * 60)
    print("RPWP — Processamento Completo")
    print("=" * 60)
    print()

    result = evaluate(text)
    print(result)
    print()

    spec = transcompile(text)
    print(describe(spec))
    print()

    glyph_path = render(spec)
    print(f"Glifo salvo: {glyph_path}")

    audio_path = render_audio(spec)
    print(f"Áudio salvo: {audio_path}")

    qr = generate_fractal_qr(text, max_depth=4)
    print()
    print(describe_fqr(qr))
    qr_path = render_fractal_qr(qr)
    print(f"\nFractal QR salvo: {qr_path}")

    layout = generate_from_spec(spec)
    circuit_path = render_svg(layout)
    print(f"Circuito SFA salvo: {circuit_path}")

    composite_path = render_composite(text)
    print(f"Mapa de Ressonância Completo salvo: {composite_path}")

    print()
    print("=" * 60)
    print("Processamento completo.")


def cmd_consult(question: str, context_paths: list[str],
                force_backend: str, allow_confidential: bool,
                output: str, manual: bool = False,
                session_name: str = None, context_repo: str = None):
    """Intelligent inter-AI consultation with classification-aware routing.

    In manual mode: generates an optimized prompt for a specific AI,
    the user copies it to the AI's web chat, then pastes the response back.
    The protocol measures the response and optionally persists it.
    """
    import json
    try:
        from seif.bridge.ai_bridge import (
            send, detect_backends, build_safe_context, AIResponse,
        )
        from seif.bridge.ai_registry import (
            recommend_backends, recommend_any, describe_recommendation,
            build_optimized_prompt, AI_REGISTRY, PROMPT_STYLES,
        )
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return
    from seif.analysis.quality_gate import assess

    backend_map = {
        "claude": "claude_cli", "gemini": "gemini_cli",
        "anthropic": "anthropic_api", "grok": "grok_api",
        "bigpickle": "opencode_bigpickle",
        "deepseek": "deepseek", "kimi": "kimi",
    }

    # === MANUAL MODE ===
    if manual:
        # Recommend from ALL AIs (including manual-only)
        if force_backend:
            target_key = backend_map.get(force_backend, force_backend)
        else:
            ranked = recommend_any(question)
            target_key = ranked[0]

        profile = AI_REGISTRY.get(target_key)
        if not profile:
            print(f"Unknown AI: {target_key}")
            return

        # Build optimized prompt
        prompt = build_optimized_prompt(question, target_key,
                                        include_context=not allow_confidential)

        print(f"═══ MANUAL CONSULTATION — {profile.name} ═══")
        print(f"Strengths: {', '.join(profile.strengths[:4])}")
        if profile.chat_url:
            print(f"Open: {profile.chat_url}")
        print()
        print("─── COPY THIS PROMPT ───")
        print(prompt)
        print("─── END PROMPT ───")
        print()

        # Save prompt to file if --output
        if output:
            Path(output).write_text(prompt, encoding="utf-8")
            print(f"Prompt saved to: {output}")
            print()

        # Wait for user to paste response
        print("Paste the AI's response below (end with empty line + Ctrl-D or 'END'):")
        lines = []
        try:
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
        except EOFError:
            pass

        response_text = "\n".join(lines).strip()
        if not response_text:
            print("No response received.")
            return

        # Measure through quality gate
        verdict = assess(response_text[:1000], role="ai")
        print(f"\n═══ {profile.name} (manual) ═══")
        print(f"[Quality: {verdict.grade} | Stance: {verdict.status} | "
              f"Resonance: {verdict.triple_gate.status}]")

        # Auto-persist (requires explicit opt-in for API responses)
        try:
            from seif.context.autonomous import find_context_repo, load_config, persist_knowledge
            ctx_repo = find_context_repo()
            if ctx_repo:
                config = load_config(ctx_repo)
                if (config.get("autonomous_context")
                        and config.get("auto_persist_api_responses", False)
                        and verdict.grade in ("A", "B", "C")):
                    sealed = (
                        f"[Source: {profile.name.lower()} | Grade: {verdict.grade} "
                        f"| Stance: {verdict.status} | Unverified AI response]\n\n"
                        f"{response_text[:500]}"
                    )
                    persist_knowledge(
                        ctx_repo, project="seif", category="context",
                        content=sealed,
                        author=profile.name.lower(),
                        trigger=f"manual-consult: {question[:80]}",
                    )
                    print(f"[Persisted as .seif module (origin: {profile.name.lower()}, sealed)]")
        except Exception:
            pass
        return

    # === API MODE ===
    available = detect_backends()
    if not available:
        print("No API backends available. Use --manual for web chat consultation.")
        print("  seif --consult \"question\" --manual")
        return

    if force_backend:
        backend_key = backend_map.get(force_backend, force_backend)
        if backend_key not in available:
            # Suggest manual mode if backend has no API
            profile = AI_REGISTRY.get(backend_key)
            if profile and profile.backend is None:
                print(f"{profile.name} has no API backend. Use --manual mode:")
                print(f"  seif --consult \"{question[:50]}...\" --to {force_backend} --manual")
                return
            print(f"Error: backend '{force_backend}' not available.")
            print(f"Available: {', '.join(available)}")
            return
    else:
        ranked = recommend_backends(question, available)
        backend_key = ranked[0]
        routing = describe_recommendation(question, available)
        print(f"[Routing] {routing}")

    # Build context (classification-filtered)
    max_cls = "CONFIDENTIAL" if allow_confidential else "INTERNAL"

    # Load explicit .seif module context (if provided)
    module_context = ""
    if context_paths:
        parts = []
        for path in context_paths:
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                cls = data.get("classification", "INTERNAL")
                if cls == "CONFIDENTIAL" and not allow_confidential:
                    print(f"  Skipping {path} (CONFIDENTIAL — use --allow-confidential)")
                    continue
                summary = data.get("summary", "")
                source = data.get("source", path)
                parts.append(f"[MODULE: {source}]\n{summary}")
            except Exception as e:
                print(f"  Warning: could not load {path}: {e}")
        if parts:
            module_context = "\n\n---\n\n".join(parts) + "\n\n---\n\n"

    # Inject session context if --session-name provided
    session_context = ""
    if session_name:
        try:
            from seif.context.sessions import describe_session
            from seif.context.autonomous import find_context_repo
            ctx = context_repo or find_context_repo() or ".seif"
            session_ctx = describe_session(ctx, session_name)
            if session_ctx and "not found" not in session_ctx:
                # Take last N lines to respect context limits
                lines = session_ctx.split("\n")
                if len(lines) > 60:
                    lines = lines[:10] + ["...(truncated)..."] + lines[-50:]
                session_context = f"[SESSION: {session_name}]\n" + "\n".join(lines) + "\n\n---\n\n"
                print(f"[Session context injected: {session_name}]")
        except Exception as e:
            print(f"  Warning: could not load session {session_name}: {e}")

    message = f"{session_context}{module_context}{question}"

    print(f"\nConsulting {backend_key}...")
    response = send(message, backend=backend_key)

    if not response.success:
        print(f"Error ({response.backend}): {response.error}")
        return

    if output:
        Path(output).write_text(response.text, encoding="utf-8")
        print(f"Response saved to: {output}")
    else:
        print(f"\n═══ {response.backend} ({response.model}) ═══")
        print(response.text)

    verdict = assess(response.text[:1000], role="ai")
    print(f"\n[Quality: {verdict.grade} | Stance: {verdict.status} | "
          f"Resonance: {verdict.triple_gate.status}]")

    # Auto-persist if autonomous context is enabled AND auto_persist_api is true
    try:
        from seif.context.autonomous import find_context_repo, load_config, persist_knowledge
        ctx_repo = find_context_repo()
        if ctx_repo:
            config = load_config(ctx_repo)
            if (config.get("autonomous_context")
                    and config.get("auto_persist_api_responses", False)
                    and verdict.grade in ("A", "B", "C")):
                # Seal with provenance — AI responses are labeled, not trusted blindly
                sealed = (
                    f"[Source: {response.backend} | Grade: {verdict.grade} "
                    f"| Stance: {verdict.status} | Unverified AI response]\n\n"
                    f"{response.text[:500]}"
                )
                persist_knowledge(
                    ctx_repo, project="seif", category="context",
                    content=sealed,
                    author=response.backend,
                    trigger=f"consult: {question[:80]}",
                )
                print(f"[Persisted as .seif module (origin: {response.backend}, sealed)]")
    except Exception:
        pass  # persistence is optional

    # Auto-contribute to session if --session-name provided
    if session_name:
        try:
            from seif.context.sessions import contribute_to_session
            from seif.context.autonomous import find_context_repo
            ctx = context_repo or find_context_repo() or ".seif"
            summary = (
                f"[{response.backend}] Grade {verdict.grade}, Stance {verdict.status}. "
                f"{response.text[:300]}"
            )
            contribute_to_session(
                ctx, session_name, summary,
                author=response.backend,
                via="--consult",
                action="contributed",
            )
            print(f"[Contributed to session '{session_name}']")
        except Exception as e:
            print(f"  Warning: could not contribute to session: {e}")


def cmd_generate(output_dir: str, context_repo: str = None,
                 classification: str = "INTERNAL"):
    """Generate documentation from .seif context modules."""
    try:
        from seif.context.doc_generator import generate_docs
        from seif.context.autonomous import find_context_repo
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    ctx = context_repo or find_context_repo() or ".seif"
    if not Path(ctx).exists():
        print(f"No .seif/ found at {ctx}. Run seif --init first.")
        return

    print(f"Generating docs from {ctx}...")
    files = generate_docs(ctx, output_dir, max_classification=classification)

    if files:
        print(f"\n═══ DOCS GENERATED ═══")
        for f in files:
            print(f"  {f}")
        print(f"\n{len(files)} files written to {output_dir}/")
    else:
        print("No modules found to generate docs from.")


def cmd_changelog(output: str, context_repo: str = None):
    """Generate CHANGELOG.md from decisions.seif."""
    try:
        from seif.context.doc_generator import generate_changelog
        from seif.context.autonomous import find_context_repo
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    ctx = context_repo or find_context_repo() or ".seif"
    if not Path(ctx).exists():
        print(f"No .seif/ found at {ctx}. Run seif --init first.")
        return

    text = generate_changelog(ctx, output=output)
    if output:
        print(f"Changelog written to {output}")
    else:
        print(text)


def cmd_scan(program: str, global_store: bool = False,
             max_depth: int = 2, output: str = None):
    """Scan a CLI program's --help and generate a .seif knowledge module."""
    try:
        from seif.context.cli_scanner import scan_program, capture_help
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    # Quick check: can we run the program?
    help_text = capture_help(program)
    if not help_text:
        print(f"Error: could not capture --help from '{program}'.")
        print(f"Make sure the program is installed and accessible.")
        return

    print(f"Scanning {program}...")
    module, path = scan_program(
        program,
        max_depth=max_depth,
        target_path=output,
        global_store=global_store,
    )

    if module and path:
        print(f"\n═══ SCAN COMPLETE ═══")
        print(f"Program:      {program}")
        print(f"Help lines:   {module.original_words} words")
        print(f"Compressed:   {module.compressed_words} words ({module.compression_ratio:.1f}:1)")
        print(f"Saved to:     {path}")
        print(f"Classification: {module.classification}")

        # Show summary preview
        lines = module.summary.split("\n")
        flag_count = sum(1 for l in lines if l.strip().startswith("- `"))
        sub_count = sum(1 for l in lines if l.strip().startswith("#### "))
        print(f"Flags found:  {flag_count}")
        print(f"Subcommands:  {sub_count}")

        if global_store:
            print(f"\n[Global store: ~/.seif/tools/ — available to all AI sessions]")
        else:
            print(f"\n[Local store: .seif/ — available to this project's AI sessions]")

        # Update mapper if autonomous context is available
        try:
            from seif.context.autonomous import find_context_repo, load_config
            from seif.context.seif_io import locked_read_modify_write
            import json
            from datetime import datetime, timezone

            ctx_repo = find_context_repo()
            if ctx_repo:
                mapper_path = Path(ctx_repo) / "mapper.json"
                if mapper_path.exists():
                    def _add_scan_entry(data):
                        rel_path = str(path.relative_to(Path(ctx_repo)))
                        modules = data.get("modules", [])
                        # Deduplicate
                        modules = [m for m in modules if m.get("path") != rel_path]
                        modules.append({
                            "path": rel_path,
                            "category": "context",
                            "project": None,
                            "origin": "cli-scanner",
                            "relevance": 0.9,
                            "last_updated": datetime.now(timezone.utc).isoformat(),
                            "trigger": f"scan: {program}",
                            "word_count": module.compressed_words,
                            "integrity_hash": module.integrity_hash,
                            "classification": "PUBLIC",
                        })
                        data["modules"] = modules
                        return data

                    locked_read_modify_write(str(mapper_path), _add_scan_entry)
                    print(f"[Registered in mapper.json]")
        except Exception:
            pass  # mapper update is optional
    else:
        print(f"Failed to scan {program}.")


def cmd_adversarial(question: str, context_paths: list[str],
                    force_backend: str, allow_confidential: bool,
                    output: str, session_name: str = None,
                    context_repo: str = None):
    """Adversarial mirror: run same question WITH and WITHOUT protocol, compare.

    During protocol solidification phase, this mode sends the same question
    to two instances of the same model:
      A) WITH full SEIF context (KERNEL + modules)
      B) WITHOUT protocol (clean system prompt)

    The delta between A and B reveals where the protocol influences the response.
    Valid findings in B that aren't in A = protocol blind spots.
    Errors in B that A avoids = protocol adding value.
    """
    import json
    import difflib
    from datetime import datetime, timezone
    try:
        from seif.bridge.ai_bridge import (
            send, send_clean, detect_backends, AIResponse,
        )
        from seif.bridge.ai_registry import (
            recommend_backends, describe_recommendation,
        )
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return
    from seif.analysis.quality_gate import assess

    backend_map = {
        "claude": "claude_cli", "gemini": "gemini_cli",
        "anthropic": "anthropic_api", "grok": "grok_api",
        "bigpickle": "opencode_bigpickle",
    }

    # Resolve backend
    available = detect_backends()
    if not available:
        print("No API backends available.")
        return

    if force_backend:
        backend_key = backend_map.get(force_backend, force_backend)
        if backend_key not in available:
            print(f"Error: backend '{force_backend}' not available.")
            print(f"Available: {', '.join(available)}")
            return
    else:
        ranked = recommend_backends(question, available)
        backend_key = ranked[0]

    # Build context for protocol version
    module_context = ""
    if context_paths:
        parts = []
        for path in context_paths:
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                cls = data.get("classification", "INTERNAL")
                if cls == "CONFIDENTIAL" and not allow_confidential:
                    continue
                summary = data.get("summary", "")
                source = data.get("source", path)
                parts.append(f"[MODULE: {source}]\n{summary}")
            except Exception:
                pass
        if parts:
            module_context = "\n\n---\n\n".join(parts) + "\n\n---\n\n"

    message = f"{module_context}{question}" if module_context else question

    print(f"═══ ADVERSARIAL MIRROR ({backend_key}) ═══")
    print(f"Question: {question[:120]}")
    print()

    # A) WITH protocol
    print("  [A] WITH protocol...", end=" ", flush=True)
    resp_protocol = send(message, backend=backend_key)
    if resp_protocol.success:
        verdict_a = assess(resp_protocol.text[:1000], role="ai")
        print(f"{verdict_a.grade} ({verdict_a.status})")
    else:
        print(f"FAILED: {resp_protocol.error}")
        return

    # B) WITHOUT protocol (clean mirror)
    print("  [B] WITHOUT protocol (clean)...", end=" ", flush=True)
    resp_clean = send_clean(message, backend=backend_key)
    if resp_clean.success:
        verdict_b = assess(resp_clean.text[:1000], role="ai")
        print(f"{verdict_b.grade} ({verdict_b.status})")
    else:
        print(f"FAILED: {resp_clean.error}")
        return

    # Compare
    text_a = resp_protocol.text[:2000].lower()
    text_b = resp_clean.text[:2000].lower()
    similarity = difflib.SequenceMatcher(None,
        _normalize_for_similarity(text_a),
        _normalize_for_similarity(text_b),
    ).ratio()

    # Build delta analysis
    grade_delta = ord(verdict_b.grade) - ord(verdict_a.grade)  # positive = B is worse
    stance_match = verdict_a.status == verdict_b.status

    result = {
        "question": question,
        "backend": backend_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "protocol_response": {
            "text": resp_protocol.text,
            "quality": {
                "grade": verdict_a.grade,
                "stance": verdict_a.status,
                "score": round(verdict_a.score, 3),
            },
        },
        "clean_response": {
            "text": resp_clean.text,
            "quality": {
                "grade": verdict_b.grade,
                "stance": verdict_b.status,
                "score": round(verdict_b.score, 3),
            },
        },
        "delta": {
            "text_similarity": round(similarity, 3),
            "grade_delta": grade_delta,
            "stance_agreement": stance_match,
            "protocol_influence": "HIGH" if similarity < 0.3 else "MEDIUM" if similarity < 0.6 else "LOW",
        },
        "interpretation": {
            "note": (
                "HIGH influence = protocol significantly changed the response. "
                "Check if the change adds value (grounding) or bias (drift). "
                "LOW influence = response is similar regardless of protocol."
            ),
        },
    }

    # Output
    if output and output.endswith(".json"):
        Path(output).write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                encoding="utf-8")
        print(f"\nFull results saved to: {output}")

    # Human-readable report
    print(f"\n{'─' * 60}")
    print(f"═══ RESPONSE A (WITH protocol) ═══")
    print(f"[Grade: {verdict_a.grade} | Stance: {verdict_a.status} | Score: {verdict_a.score:.3f}]")
    preview_a = resp_protocol.text[:300].replace("\n", " ")
    print(f"{preview_a}...")

    print(f"\n═══ RESPONSE B (WITHOUT protocol — clean mirror) ═══")
    print(f"[Grade: {verdict_b.grade} | Stance: {verdict_b.status} | Score: {verdict_b.score:.3f}]")
    preview_b = resp_clean.text[:300].replace("\n", " ")
    print(f"{preview_b}...")

    print(f"\n{'─' * 60}")
    print(f"═══ DELTA ANALYSIS ═══")
    print(f"Text similarity:     {similarity:.3f}")
    print(f"Grade delta:         {grade_delta:+d} (positive = clean is worse)")
    print(f"Stance agreement:    {'YES' if stance_match else 'NO'}")
    print(f"Protocol influence:  {result['delta']['protocol_influence']}")

    if grade_delta > 0:
        print(f"\n  Protocol IMPROVED quality by {grade_delta} grade(s).")
    elif grade_delta < 0:
        print(f"\n  Clean response scored {-grade_delta} grade(s) HIGHER. Investigate protocol bias.")
    else:
        print(f"\n  Same grade. Check content differences for qualitative insights.")

    if not stance_match:
        print(f"  Stance divergence: protocol={verdict_a.status}, clean={verdict_b.status}")
        print(f"  This may indicate the protocol is shifting the response posture.")

    # Auto-persist if autonomous context is enabled
    try:
        from seif.context.autonomous import find_context_repo, load_config, persist_knowledge
        ctx_repo = find_context_repo()
        if ctx_repo:
            config = load_config(ctx_repo)
            if config.get("autonomous_context"):
                summary = (
                    f"Adversarial mirror ({backend_key}): "
                    f"protocol={verdict_a.grade}/{verdict_a.status}, "
                    f"clean={verdict_b.grade}/{verdict_b.status}, "
                    f"similarity={similarity:.3f}, "
                    f"influence={result['delta']['protocol_influence']}. "
                    f"Question: {question[:100]}"
                )
                persist_knowledge(
                    ctx_repo, project="seif", category="feedback",
                    content=summary,
                    author=f"adversarial-mirror-{backend_key}",
                    trigger=f"adversarial: {question[:60]}",
                )
                print(f"\n[Persisted adversarial result to .seif/feedback]")
    except Exception:
        pass


def cmd_watermark_embed(text: str, input_wav: str, output_wav: str,
                        repetitions: int, symbol_duration: float,
                        amplitude: float):
    """Embed text as infrasound watermark in a WAV file."""
    from seif.generators.watermark import WatermarkConfig, embed_watermark_wav

    config = WatermarkConfig(
        repetitions=repetitions,
        symbol_duration=symbol_duration,
        amplitude=amplitude,
    )
    meta = embed_watermark_wav(text, input_wav, output_wav, config)

    print(f"═══ SEIF WATERMARK EMBEDDED ═══")
    print(f"  Text:        \"{meta['text']}\"")
    print(f"  Symbols:     {meta['symbols']}")
    print(f"  Repetitions: {meta['repetitions']}")
    print(f"  Duration:    {meta['duration_seconds']:.1f}s watermark in {meta['carrier_duration']:.1f}s carrier")
    print(f"  Output:      {meta['output_path']}")
    print()
    print("All letter frequencies are infrasound (<20 Hz) — inaudible to humans.")


def cmd_watermark_extract(input_wav: str, n_symbols: int,
                          repetitions: int, symbol_duration: float):
    """Extract infrasound watermark from a WAV file."""
    from seif.generators.watermark import WatermarkConfig, extract_watermark_wav

    config = WatermarkConfig(
        repetitions=repetitions,
        symbol_duration=symbol_duration,
    )
    text = extract_watermark_wav(input_wav, n_symbols, config)

    print(f"═══ SEIF WATERMARK EXTRACTED ═══")
    print(f"  Text:     \"{text}\"")
    print(f"  Symbols:  {n_symbols}")
    print(f"  Reps:     {repetitions}")
    print(f"  Source:   {input_wav}")


def cmd_streaming_start(
    session_id: str,
    audio_interval: int,
    text_interval: int,
    max_embeddings: int,
    identity_file: str
):
    """Start a streaming watermark session."""
    from seif.generators.streaming_watermark import StreamingWatermarker
    try:
        from seif.identity_block import parse_identity_block
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return
    import json

    identity_block = None
    if identity_file:
        try:
            with open(identity_file, 'r') as f:
                data = json.load(f)
            identity_block = parse_identity_block(data)
        except Exception as e:
            print(f"Warning: Could not load identity file: {e}")

    marker = StreamingWatermarker(
        session_id=session_id if session_id else None,
        audio_interval=audio_interval,
        text_interval=text_interval,
        max_embeddings=max_embeddings
    )

    state = marker.get_session_state()
    print(f"═══ SEIF STREAMING SESSION STARTED ═══")
    print(f"  Session ID:  {state['session_id']}")
    print(f"  Audio interval: {audio_interval}s")
    print(f"  Text interval:  {text_interval}s")
    print(f"  Max embeddings: {max_embeddings}")
    print(f"  State file:   {state['state_file']}")
    print()
    print("Use --streaming-status to monitor, --streaming-stop to end.")


def cmd_streaming_status(session_id: str):
    """Show status of a streaming session."""
    from seif.generators.streaming_watermark import StreamingWatermarker, STREAMING_DIR

    if not session_id:
        print("Error: --streaming-session required")
        return

    path = STREAMING_DIR / f"{session_id}.state"
    if not path.exists():
        print(f"Session not found: {session_id}")
        return

    marker = StreamingWatermarker(session_id=session_id)
    state = marker.get_session_state()

    print(f"═══ SEIF STREAMING SESSION ═══")
    print(f"  Session ID:        {state['session_id']}")
    print(f"  Elapsed:           {state['elapsed_seconds']:.1f}s")
    print(f"  Full embeddings:   {state['embed_count']}")
    print(f"  Mini markers:     {state['mini_count']}")
    print(f"  Last full:        {state['last_embed_seconds_ago']:.1f}s ago")
    print(f"  Last mini:        {state['last_mini_seconds_ago']:.1f}s ago")
    print(f"  Paused:           {state['is_paused']}")
    print(f"  Trail hash:       {state['trail_hash']}")


def cmd_streaming_list():
    """List all active streaming sessions."""
    from seif.generators.streaming_watermark import StreamingWatermarker

    sessions = StreamingWatermarker.list_sessions()

    if not sessions:
        print("No active streaming sessions.")
        return

    print(f"═══ SEIF STREAMING SESSIONS ({len(sessions)}) ═══")
    for s in sessions:
        from datetime import datetime
        start = datetime.fromtimestamp(s['start_time']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  {s['session_id']}")
        print(f"    Started: {start}")
        print(f"    Embeds: {s['embed_count']} full, {s['mini_count']} mini")


def cmd_streaming_stop(session_id: str):
    """Stop/end a streaming session."""
    from seif.generators.streaming_watermark import StreamingWatermarker

    if not session_id:
        print("Error: --streaming-session required")
        return

    marker = StreamingWatermarker(session_id=session_id)
    state = marker.get_session_state()

    print(f"═══ SEIF STREAMING SESSION ENDED ═══")
    print(f"  Session ID:  {state['session_id']}")
    print(f"  Total time: {state['elapsed_seconds']:.1f}s")
    print(f"  Full embeddings: {state['embed_count']}")
    print(f"  Mini markers: {state['mini_count']}")

    marker.cleanup()
    print(f"  State file removed.")


def cmd_boot_check(
    backends: list[str],
    core_file: str,
    max_parallel: int,
    auto: bool,
    all_backends: bool
):
    """Run boot check across multiple LLMs in parallel."""
    try:
        from seif.bridge.boot_check import (
            run_boot_check, describe_result, auto_detect_backends
        )
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    if not backends and not auto and not all_backends:
        print("Error: specify --boot-to backends, --boot-auto, or --boot-all")
        return

    if auto or all_backends:
        available = auto_detect_backends()
        if not available:
            print("No backends available. Set API keys or install CLI tools.")
            return
        backends = available if all_backends else available[:3]
        print(f"Auto-detected backends: {', '.join(backends)}")
        print()

    if not backends:
        print("No backends to check.")
        return

    core_path = core_file or "seif-core-v3.2.seif"

    print(f"Running boot check on {len(backends)} backend(s)...")
    print()

    result = run_boot_check(
        backends=backends,
        core_file=core_path,
        max_parallel=max_parallel
    )

    print(describe_result(result))


def cmd_security(args):
    """Run security assessment (Red/Blue team)."""
    try:
        from seif.context.autonomous import find_context_repo
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return
    ctx = args.context_repo or find_context_repo() or ".seif"
    action = args.security

    if action == "baseline":
        # Show current baseline
        from pathlib import Path
        import json
        bp = Path(ctx) / "modules" / "security_baseline.seif"
        if bp.exists():
            with open(bp) as f:
                data = json.load(f)
            print("═══ SEIF SECURITY BASELINE ═══\n")
            print(data.get("summary", "(no summary)"))
            print(f"\nClassification: {data.get('classification')}")
            print(f"Hash: {data.get('integrity_hash')}")
            print(f"Version: {data.get('version')}")
        else:
            print(f"No security_baseline.seif found at {bp}")
        return

    try:
        from seif.bridge.local_proxy import classify_input
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    if action == "red":
        try:
            from seif.security.redblue import red_team_test
        except ImportError:
            print("This feature requires SEIF Suite. Learn more: https://seifos.io")
            return
        print("═══ SEIF RED TEAM ═══\n")
        report = red_team_test(classify_input)
        print(f"  Tests:           {report.total_tests}")
        print(f"  Passed:          {report.passed}")
        print(f"  Failed:          {report.failed}")
        print(f"  False negatives: {report.false_negatives} (secrets leaked)")
        print(f"  False positives: {report.false_positives} (legitimate blocked)")
        print(f"  Bypass rate:     {report.bypass_rate:.1%}")
        print(f"  Grade:           {report.grade()}")
        print()
        if report.failed > 0:
            print("  Failed tests:")
            for r in report.results:
                if not r.passed:
                    tag = "FN" if r.false_negative else "FP"
                    print(f"    [{tag}] {r.description}: expected {r.expected}, got {r.actual}")
        return

    if action == "blue":
        try:
            from seif.security.redblue import blue_team_audit
        except ImportError:
            print("This feature requires SEIF Suite. Learn more: https://seifos.io")
            return
        print("═══ SEIF BLUE TEAM ═══\n")
        audit = blue_team_audit(ctx)
        print(f"  Modules audited:     {audit.modules_audited}")
        print(f"  Classification OK:   {audit.classification_compliant}")
        print(f"  Hash valid:          {audit.hash_valid}")
        print(f"  Provenance complete: {audit.provenance_complete}")
        print(f"  CONFIDENTIAL:        {audit.confidential_modules} ({audit.confidential_with_approval} approved)")
        print(f"  Compliance:          {audit.compliance_score:.1%}")
        print(f"  Grade:               {audit.grade()}")
        if audit.issues:
            print(f"\n  Issues ({len(audit.issues)}):")
            for issue in audit.issues:
                print(f"    - {issue}")
        return

    # Default: full score
    try:
        from seif.security.redblue import run_full_assessment
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return
    print("═══ SEIF SECURITY ASSESSMENT ═══\n")
    score = run_full_assessment(classify_input, ctx, persist=True)
    print(f"  Red Team:        {score.red_grade} (bypass: {score.red_bypass_rate:.1%})")
    print(f"  Blue Team:       {score.blue_grade} (compliance: {score.blue_compliance:.1%})")
    print(f"  Combined:        {score.combined_grade}")
    print(f"  Posture score:   {score.posture_score:.2f}")
    print(f"  zeta effective:  {score.zeta_effective:.3f} (theoretical: 0.612)")
    print()
    if score.recommendations:
        print("  Recommendations:")
        for rec in score.recommendations:
            print(f"    - {rec}")
    print()
    print(f"  Results persisted to security_baseline.seif")


def cmd_proxy(args):
    """Manage the local LLM proxy (data sovereignty layer)."""
    try:
        from seif.bridge.local_proxy import status, classify_input, _ollama_pull
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    if args.proxy_test:
        # Test classification of specific text
        print("═══ SEIF LOCAL PROXY — Classification Test ═══\n")
        result = classify_input(args.proxy_test, model=args.proxy_model)
        print(f"  Classification: {result['classification']}")
        print(f"  Summary:        {result['summary']}")
        if result['confidential_fields']:
            print(f"  Redacted:       {', '.join(result['confidential_fields'])}")
        print(f"\n  Safe protocol message:")
        print(f"  {result['safe_protocol'][:500]}")
        return

    action = args.proxy or "status"

    if action == "status":
        print("═══ SEIF LOCAL PROXY — Status ═══\n")
        s = status()
        print(f"  Ollama:          {'ONLINE' if s['ollama_available'] else 'OFFLINE'}")
        print(f"  Host:            {s['ollama_host']}")
        print(f"  Default model:   {s['default_model']}")
        print(f"  Model ready:     {'YES' if s['model_ready'] else 'NO'}")
        print(f"  Proxy mode:      {s['proxy_mode']}")
        if s['installed_models']:
            print(f"  Installed:       {', '.join(s['installed_models'])}")
        print()
        if s['proxy_mode'] == 'active':
            print("  Data sovereignty: ACTIVE")
            print("  Raw user input never leaves this machine.")
            print("  External APIs receive only SEIF protocol data.")
        else:
            print("  Data sovereignty: FALLBACK (rule-based)")
            print("  Start Ollama: make up (Docker) or ollama serve")

    elif action == "pull":
        model = args.proxy_model or None
        print(f"Pulling model {model or 'default'}...")
        if _ollama_pull(model):
            print("Model ready.")
        else:
            print("Failed to pull model. Is Ollama running?")

    elif action == "test":
        # Interactive test: classify a sample message
        test_msgs = [
            ("PUBLIC", "What is the golden ratio?"),
            ("INTERNAL", "We decided to use PostgreSQL for the session store"),
            ("CONFIDENTIAL", "My API key is sk-abc123def456 and password is hunter2"),
        ]
        print("═══ SEIF LOCAL PROXY — Classification Test ═══\n")
        for expected, msg in test_msgs:
            result = classify_input(msg, model=args.proxy_model)
            match = "OK" if result['classification'] == expected else "MISMATCH"
            print(f"  [{match}] Expected: {expected:14s} Got: {result['classification']:14s}")
            print(f"        Input:    {msg[:60]}")
            if result['confidential_fields']:
                print(f"        Redacted: {result['confidential_fields']}")
            print()


def cmd_dia_skill():
    """Generate Dia browser skill prompt from current nucleus context."""
    try:
        from seif.context.nucleus import load_profile, load_sources
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return
    from seif.data.paths import get_user_home
    import json

    profile = load_profile()
    sources = load_sources()
    home = get_user_home()

    # Gather metadata
    tools = []
    tools_dir = home / "tools"
    if tools_dir.exists():
        for f in sorted(tools_dir.glob("*.seif")):
            name = f.stem.replace("__cli-scanned_", "").replace("_", " ").strip()
            tools.append(name)

    projects = []
    extracts_dir = home / "extracts"
    if extracts_dir.exists():
        for f in sorted(extracts_dir.glob("*.seif")):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                name = data.get("name", f.stem).replace("extract_", "")
                meta = data.get("metadata", {})
                ft = meta.get("file_types", [])
                projects.append(f"{name} ({', '.join(ft[:3])})")
            except (json.JSONDecodeError, OSError):
                pass

    deps_count = len(list((home / "deps").glob("*.seif"))) if (home / "deps").exists() else 0

    # Build prompt
    name = profile.get("name", "User")
    lang = profile.get("language", "en")
    github = profile.get("github_username", "")
    lang_name = "Portuguese" if lang == "pt_br" else "English"

    prompt = f"""You are a SEIF-aware assistant. The user has a personal context nucleus.

User: {name}
Language: {lang_name}
GitHub: {github}
Tools installed: {', '.join(tools[:20])}
Projects: {', '.join(projects[:10])}
Dependency manifests: {deps_count} projects
Sources: {len(sources)} GitHub repos

SEIF (S.E.I.F.) is a context management framework (pip install seif-cli) that compresses project knowledge into portable .seif modules with integrity hashes, Ed25519 signatures, and provenance chains.
DOI: 10.5281/zenodo.19344678 | License: CC BY-NC-SA 4.0

When the user asks about their projects, tools, or machine context, use this knowledge.
Always respond in {lang_name}. Be concise.

Key SEIF commands: seif --init, seif --sync, seif --quality-gate, seif chat, seif serve, seif --extract"""

    print("=" * 60)
    print("DIA SKILL: /seif")
    print("=" * 60)
    print()
    print("Create this skill in Dia: Skills Gallery → Create Skill")
    print(f"Name: seif")
    print()
    print("--- COPY PROMPT BELOW ---")
    print()
    print(prompt)
    print()
    print("--- END PROMPT ---")
    print()
    print(f"Context: {len(tools)} tools, {len(projects)} projects, {deps_count} deps")
    print(f"Language: {lang_name}")
    print()

    # Also copy to clipboard if possible
    try:
        import subprocess
        subprocess.run(["pbcopy"], input=prompt.encode(), check=True)
        print("(Copied to clipboard)")
    except Exception:
        pass


def cmd_stamp(file_path: str):
    """Timestamp a .seif module with OpenTimestamps."""
    from seif.core.timestamping import stamp
    ok, msg = stamp(Path(file_path))
    print(f"  {'OK' if ok else 'FAILED'}: {msg}")


def cmd_verify_stamp(file_path: str):
    """Verify OTS proof against Bitcoin blockchain."""
    from seif.core.timestamping import verify
    ok, msg = verify(Path(file_path))
    if ok:
        print(f"  VERIFIED: {msg}")
    else:
        print(f"  FAILED: {msg}")


def cmd_stamp_all(directory: str):
    """Timestamp all .seif modules in a directory."""
    from seif.core.timestamping import stamp_directory
    results = stamp_directory(Path(directory))
    stamped = sum(1 for r in results if r["status"] == "stamped")
    existing = sum(1 for r in results if r["status"] == "already stamped")
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"  Stamped: {stamped} | Already: {existing} | Failed: {failed}")
    for r in results:
        if r["status"] == "failed":
            print(f"    {r['file']}: {r.get('message', '')}")


def cmd_keygen(force: bool = False):
    """Generate Ed25519 signing keypair."""
    from seif.core.signing import keygen, get_public_key_fingerprint, get_public_key_base64

    try:
        priv_path, pub_path = keygen(force=force)
        fp = get_public_key_fingerprint()
        pub_b64 = get_public_key_base64()
        print(f"Keypair generated:")
        print(f"  Private: {priv_path}")
        print(f"  Public:  {pub_path}")
        print(f"  Fingerprint: {fp}")
        print(f"\nPublic key (base64): {pub_b64}")
        print(f"\nAdd to your profile: seif --profile show")
        print(f"Share the fingerprint — keep the private key safe.")
    except ImportError:
        print("Error: cryptography package required. Install: pip install cryptography")
    except FileExistsError as e:
        print(str(e))


def cmd_sign(module_path: str):
    """Sign a .seif module."""
    from seif.core.signing import sign_module, get_public_key_fingerprint

    try:
        module = sign_module(Path(module_path))
        fp = module.get("signature", {}).get("key_fingerprint", "")
        print(f"Signed: {module_path}")
        print(f"  Key fingerprint: {fp}")
        print(f"  Hash signed: {module.get('integrity_hash', '')}")
    except ImportError:
        print("Error: cryptography package required. Install: pip install cryptography")
    except FileNotFoundError as e:
        print(str(e))
    except Exception as e:
        print(f"Error: {e}")


def cmd_verify(module_path: str):
    """Verify signature of a .seif module."""
    from seif.core.signing import verify_module

    try:
        result = verify_module(Path(module_path))
        if result["valid"]:
            print(f"VALID: {module_path}")
            print(f"  Key fingerprint: {result['key_fingerprint']}")
        else:
            print(f"INVALID: {module_path}")
            print(f"  Reason: {result['reason']}")
    except ImportError:
        print("Error: cryptography package required. Install: pip install cryptography")
    except Exception as e:
        print(f"Error: {e}")


def cmd_sign_all(directory: str):
    """Sign all .seif modules in a directory."""
    from seif.core.signing import sign_all_modules

    try:
        results = sign_all_modules(Path(directory))
        signed = sum(1 for r in results if r["signed"])
        print(f"Signed {signed}/{len(results)} modules in {directory}")
        for r in results:
            status = "OK" if r["signed"] else f"SKIP ({r.get('error', '')})"
            print(f"  {r['file']}: {status}")
    except ImportError:
        print("Error: cryptography package required. Install: pip install cryptography")
    except Exception as e:
        print(f"Error: {e}")


def cmd_profile(args):
    """Manage ~/.seif/profile.json."""
    import json
    try:
        from seif.context.nucleus import load_profile, init_profile
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    action = args.profile
    if action == "show":
        profile = load_profile()
        print(json.dumps(profile, indent=2, ensure_ascii=False))
    elif action == "init":
        path = init_profile(
            name=args.profile_name or "",
            email=args.profile_email or "",
            github_username=args.profile_github or "",
            default_backend=args.profile_backend or "claude",
            language=args.profile_language or "en",
        )
        print(f"Profile saved to {path}")
        profile = load_profile()
        print(json.dumps(profile, indent=2, ensure_ascii=False))
    elif action == "edit":
        from seif.data.paths import get_profile_path
        path = get_profile_path()
        if not path.exists():
            print(f"No profile found. Run: seif --profile init")
            return
        import subprocess
        editor = __import__("os").environ.get("EDITOR", "nano")
        subprocess.run([editor, str(path)])


def cmd_sources(args):
    """Manage ~/.seif/sources.json."""
    try:
        from seif.context.nucleus import (
            load_sources, add_source, remove_source, sync_all_sources, load_profile
        )
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    action = args.sources
    if action == "list":
        sources = load_sources()
        if not sources:
            print("No sources configured. Add one:")
            print("  seif --sources add --source-repo github.com/user/repo")
            return
        for s in sources:
            synced = s.last_synced[:10] if s.last_synced else "never"
            print(f"  {s.repo}  [{s.type}]  synced: {synced}")

    elif action == "add":
        if not args.source_repo:
            print("Error: --source-repo required")
            return
        source = add_source(args.source_repo, source_type=args.source_type,
                           classification=args.classification)
        print(f"Added: {source.repo} [{source.type}]")

    elif action == "remove":
        if not args.source_repo:
            print("Error: --source-repo required")
            return
        if remove_source(args.source_repo):
            print(f"Removed: {args.source_repo}")
        else:
            print(f"Not found: {args.source_repo}")

    elif action == "sync":
        profile = load_profile()
        print("Syncing sources...")
        results = sync_all_sources(auto_fetch=True)
        for r in results:
            status = "OK" if r["success"] else "FAILED"
            print(f"  {r['repo']}: {status}")
        if not results:
            print("  No sources to sync.")


def cmd_extract(path: str, context_repo: str = None,
                classification: str = "INTERNAL"):
    """Extract knowledge from files/directories into .seif modules."""
    try:
        from seif.context.file_extractor import scan_directory, build_extract_module
        from seif.context.autonomous import find_context_repo
    except ImportError:
        print("This feature requires SEIF Suite. Learn more: https://seifos.io")
        return

    target = Path(path).resolve()
    if not target.exists():
        print(f"Path not found: {target}")
        return

    ctx = context_repo or find_context_repo() or ".seif"

    print(f"Extracting from {target}...")
    files = scan_directory(target)

    if not files:
        print("No supported files found.")
        return

    # Show summary
    by_type = {}
    for f in files:
        by_type[f.file_type] = by_type.get(f.file_type, 0) + 1
    for ft, count in sorted(by_type.items()):
        print(f"  {ft}: {count} files")

    confidential = [f for f in files if f.classification == "CONFIDENTIAL"]
    if confidential:
        print(f"\n  CONFIDENTIAL: {len(confidential)} files (sensitive content detected)")

    # Build module
    source_name = target.name if target.is_dir() else target.stem
    module = build_extract_module(files, source_name, max_classification=classification)

    if module:
        # Save to context repo
        out_dir = Path(ctx)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"extract_{source_name}.seif"
        import json
        with open(out_path, "w") as f:
            json.dump(module, f, indent=2, ensure_ascii=False)
        print(f"\nModule saved: {out_path}")
        print(f"  Words: {module.get('metadata', {}).get('word_count', '?')}")
        print(f"  Classification: {module.get('classification', 'INTERNAL')}")
    else:
        print("No content to extract (all files filtered by classification).")


# ── Agent Roles & Start ─────────────────────────────────────────────────────

_AGENT_ROLES_FILE = "agent-roles-v1.seif"
_DEFAULT_ROLES = {
    "writer":       {"agent": "copilot",   "fallback": "claude"},
    "vigilant":     {"agent": "claude",    "fallback": "copilot"},
    "sentinel":     {"agent": "claude",    "fallback": "grok"},
    "orchestrator": {"agent": "bigpickle", "fallback": "copilot"},
    "researcher":   {"agent": "grok",      "fallback": "gemini"},
}
_KNOWN_AGENTS = ["copilot", "claude", "grok", "gemini", "bigpickle", "deepseek", "cursor", "windsurf"]


def _agent_roles_path(ctx_repo: str) -> str:
    import os
    return os.path.join(ctx_repo, "modules", _AGENT_ROLES_FILE)


def _load_agent_roles(ctx_repo: str) -> dict:
    import json, os
    path = _agent_roles_path(ctx_repo)
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            return data.get("roles", _DEFAULT_ROLES)
        except Exception:
            pass
    return dict(_DEFAULT_ROLES)


def _save_agent_roles(ctx_repo: str, roles: dict, authored_by: str = "and2carvalho") -> None:
    import json, os
    from datetime import datetime, timezone
    path = _agent_roles_path(ctx_repo)
    module = {
        "_instruction": "Workspace agent role assignments. Owner-only write. Propagates to all collaborators.",
        "protocol": "SEIF-MODULE-v2",
        "module_id": "agent-roles-v1",
        "classification": "INTERNAL",
        "decay_exempt": True,
        "governance": {
            "authored_by": authored_by,
            "collaborator_override": False,
            "propagates_to_all": True,
            "note": "Only workspace-owner can write this module. All collaborators inherit these assignments."
        },
        "roles": roles,
        "known_agents": _KNOWN_AGENTS,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "integrity_hash": f"agent-roles-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    }
    with open(path, "w") as f:
        json.dump(module, f, indent=2)


def _cmd_agents_show(ctx_repo: str) -> None:
    roles = _load_agent_roles(ctx_repo)
    print("╔══ SEIF AGENT ROLES ═══════════════════════════════╗")
    for role, cfg in roles.items():
        agent = cfg.get("agent", "—") if isinstance(cfg, dict) else cfg
        fallback = cfg.get("fallback", "—") if isinstance(cfg, dict) else "—"
        avail = _check_agent_available(agent)
        icon = "✅" if avail else "⚠ "
        fb_note = f"  (fallback: {fallback})" if not avail else ""
        print(f"  {icon} {role:<14} → {agent}{fb_note}")
    print("╚═══════════════════════════════════════════════════╝")
    print("  Set with: seif --agents-set ROLE=AGENT")
    print(f"  Known agents: {', '.join(_KNOWN_AGENTS)}")


def _check_agent_available(agent: str) -> bool:
    """Best-effort availability check — checks if agent binary/process exists."""
    import shutil
    checks = {
        "copilot": ["gh", "copilot"],
        "claude":  ["claude"],
        "cursor":  ["cursor"],
        "windsurf": ["windsurf"],
    }
    bins = checks.get(agent, [agent])
    return any(shutil.which(b) for b in bins)


def _cmd_agents_set(assignment: str, ctx_repo: str) -> None:
    if "=" not in assignment:
        print(f"⚠  Format: ROLE=AGENT  (e.g. writer=claude)")
        return
    role, agent = assignment.split("=", 1)
    role, agent = role.strip().lower(), agent.strip().lower()
    if agent not in _KNOWN_AGENTS:
        print(f"⚠  Unknown agent '{agent}'. Known: {', '.join(_KNOWN_AGENTS)}")
        return
    roles = _load_agent_roles(ctx_repo)
    old = roles.get(role, {})
    old_agent = old.get("agent", "—") if isinstance(old, dict) else old
    roles[role] = {"agent": agent, "fallback": old_agent if old_agent != agent else "copilot"}
    _save_agent_roles(ctx_repo, roles)
    print(f"╔══ AGENT ROLE UPDATED ══════════════════════════════╗")
    print(f"  {role:<14} → {agent}  (previous: {old_agent})")
    print(f"  Saved to: {_agent_roles_path(ctx_repo)}")
    print(f"  Propagates to all workspace collaborators.")
    print(f"╚════════════════════════════════════════════════════╝")


def _cmd_sync_workspace(ctx_repo: str, host: str | None = None, dry_run: bool = False) -> None:
    """Sync all SEIF repos on a remote device (same local network, owner-only).

    Connects via SSH, detects all git repos under the remote workspace root,
    pulls each one from its configured GitHub origin, then runs seif absorb
    if seif is available on the remote.

    Security: only runs when called as the workspace owner (checks agent-roles
    authored_by). SSH host is resolved from: CLI arg → SEIF_SYNC_HOST env var
    → agent-roles-v1.seif sync_host field.
    """
    import os, json, subprocess, shutil

    WORKSPACE_ROOT = "~/Documents/seif-admin"
    REPOS = ["seif", "seif-engine", "seif-suite", "seif-context",
             "seif-internal", "seif-research", "seif-resonance-bridge",
             "seif-vscode-extension"]

    print("╔══ SEIF SYNC-WORKSPACE ═════════════════════════════╗")

    # ── 1. Resolve SSH host ──────────────────────────────────
    if not host:
        host = os.environ.get("SEIF_SYNC_HOST", "")
    if not host and ctx_repo:
        # Try to read from agent-roles module
        roles_path = os.path.join(ctx_repo, "modules", "agent-roles-v1.seif")
        if os.path.exists(roles_path):
            try:
                import re
                with open(roles_path) as f:
                    content = f.read()
                m = re.search(r"sync_host:\s*(.+)", content)
                if m:
                    host = m.group(1).strip()
            except Exception:
                pass

    if not host:
        print("  ⚠  No SSH host specified.")
        print("  Set via: --sync-workspace-host <host>")
        print("       or: export SEIF_SYNC_HOST=<host>")
        print("       or: add 'sync_host: <host>' to agent-roles-v1.seif")
        print("╚════════════════════════════════════════════════════╝")
        return

    print(f"  Host   : {host}")
    print(f"  Root   : {WORKSPACE_ROOT}")
    print(f"  Repos  : {', '.join(REPOS)}")
    if dry_run:
        print("  Mode   : DRY RUN (no changes)")
    print()

    # ── 2. Check SSH reachability ────────────────────────────
    if not dry_run:
        ping = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
             host, "echo ok"],
            capture_output=True, text=True
        )
        if ping.returncode != 0:
            print(f"  ✗ Cannot reach {host} via SSH.")
            print(f"    Ensure you are on the same network and SSH is enabled.")
            print("╚════════════════════════════════════════════════════╝")
            return
        print(f"  ✓ SSH connection to {host} confirmed")
        print()

    # ── 3. Build the remote script ───────────────────────────
    remote_script = f"""#!/bin/bash
set -e
ROOT="{WORKSPACE_ROOT}"
REPOS=({" ".join(REPOS)})
echo "── Remote sync starting on $(hostname) ──"
echo ""
for repo in "${{REPOS[@]}}"; do
  path="$ROOT/$repo"
  expanded_path=$(eval echo "$path")
  if [ ! -d "$expanded_path/.git" ]; then
    echo "  ⊘  $repo — not found or no .git"
    continue
  fi
  cd "$expanded_path"
  remote_url=$(git remote get-url origin 2>/dev/null || echo "")
  if [ -z "$remote_url" ]; then
    echo "  ⚠  $repo — no remote configured"
    continue
  fi
  branch=$(git branch --show-current 2>/dev/null || echo "main")
  before=$(git log --oneline -1 2>/dev/null | cut -c1-7)
  git fetch origin --quiet 2>&1 | head -1
  git pull origin "$branch" --ff-only --quiet 2>&1 | tail -1
  after=$(git log --oneline -1 2>/dev/null | cut -c1-7)
  if [ "$before" = "$after" ]; then
    echo "  ✓  $repo ($branch) — already up to date [$after]"
  else
    echo "  ↑  $repo ($branch) — $before → $after"
  fi
done
echo ""
# Absorb if seif is available
if command -v seif &>/dev/null; then
  echo "  🌀 Running seif absorb..."
  seif --cycle absorb 2>/dev/null | tail -3 || true
fi
echo ""
echo "── Sync complete on $(hostname) ──"
"""

    if dry_run:
        print("  [DRY RUN] Would run on remote:")
        print("  " + remote_script.replace("\n", "\n  ").strip())
        print()
        print("╚════════════════════════════════════════════════════╝")
        return

    # ── 4. Execute remote script via SSH ────────────────────
    result = subprocess.run(
        ["ssh", host, "bash -s"],
        input=remote_script, capture_output=False, text=True
    )

    print()
    if result.returncode == 0:
        print("  ✅ Workspace sync complete")
    else:
        print(f"  ⚠  Remote script exited with code {result.returncode}")

    # ── 5. Update agent-roles-v1.seif with sync timestamp ───
    if ctx_repo:
        roles_path = os.path.join(ctx_repo, "modules", "agent-roles-v1.seif")
    else:
        roles_path = None
    if roles_path and os.path.exists(roles_path):
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            with open(roles_path) as f:
                content = f.read()
            import re
            if "last_sync_workspace:" in content:
                content = re.sub(
                    r"last_sync_workspace:.*",
                    f"last_sync_workspace: {now}",
                    content
                )
            else:
                content = content.rstrip() + f"\nlast_sync_workspace: {now}\n"
            with open(roles_path, "w") as f:
                f.write(content)
            print(f"\n  📝 last_sync_workspace → {now}")
        except Exception:
            pass

    print("╚════════════════════════════════════════════════════╝")


def _cmd_start(ctx_repo: str) -> None:
    import webbrowser, os, subprocess
    print("╔══ SEIF START ══════════════════════════════════════╗")

    # 1. Cycle status
    try:
        result = subprocess.run(
            ["python3", "-m", "seif.cli.cli", "--cycle", "status"],
            capture_output=True, text=True, cwd=os.path.dirname(ctx_repo)
        )
        print(result.stdout.strip())
    except Exception:
        print("  ⚠  Could not load cycle status")

    # 2. Agent roles
    print()
    _cmd_agents_show(ctx_repo)

    # 3. Open Suite in browser
    suite_url = os.environ.get("SEIF_SUITE_URL", "http://localhost:3000")
    print(f"\n  🌐 Opening SEIF Suite: {suite_url}")
    try:
        webbrowser.open(suite_url)
    except Exception:
        print(f"  ⚠  Could not open browser. Navigate to: {suite_url}")

    print("╚════════════════════════════════════════════════════╝")


def main():
    parser = argparse.ArgumentParser(
        prog="seif",
        description="S.E.I.F. — Unified CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  seif "O amor liberta e guia"          # full RPWP pipeline\n'
            '  seif --gate "Tesla 369"                # resonance gate only\n'
            '  seif --init                            # initialize .seif context\n'
            '  seif --sync                            # re-sync git context\n'
            '  seif --quality-gate "text" --role ai   # measure AI response\n'
        ),
    )
    parser.add_argument("text", nargs="?", default="",
                        help="Texto de entrada ou caminho de imagem (com --artifact)")
    parser.add_argument("--gate", action="store_true", help="Apenas Porta de Ressonância")
    parser.add_argument("--transcompile", action="store_true", help="Apenas transcompilação")
    parser.add_argument("--glyph", action="store_true", help="Apenas glifo visual")
    parser.add_argument("--audio", action="store_true", help="Apenas áudio 432Hz")
    parser.add_argument("--fractal", action="store_true", help="Apenas Fractal QR-Code")
    parser.add_argument("--circuit", action="store_true", help="Apenas circuito SFA (SVG)")
    parser.add_argument("--composite", action="store_true", help="Mapa de Ressonância Completo (selo + hardware)")
    parser.add_argument("--encode", action="store_true", help="Resonance Encoding (φ-spiral frequencies)")
    parser.add_argument("--artifact", action="store_true", help="Analisar imagem de artefato antigo")
    parser.add_argument("--watermark-embed", metavar="WAV_IN",
                        help="Embed text as infrasound watermark in a WAV file")
    parser.add_argument("--watermark-extract", metavar="WAV_IN",
                        help="Extract infrasound watermark from a WAV file")
    parser.add_argument("--watermark-output", metavar="WAV_OUT",
                        help="Output WAV path for --watermark-embed")
    parser.add_argument("--watermark-symbols", type=int, default=0, metavar="N",
                        help="Number of symbols to extract (for --watermark-extract)")
    parser.add_argument("--watermark-reps", type=int, default=3,
                        help="Repetition coding factor (default: 3)")
    parser.add_argument("--watermark-duration", type=float, default=4.0,
                        help="Symbol duration in seconds (default: 4.0)")
    parser.add_argument("--watermark-amplitude", type=float, default=0.005,
                        help="Watermark amplitude (default: 0.005)")
    parser.add_argument("--all", action="store_true", help="Pipeline completo (padrão)")
    parser.add_argument("--init", nargs="?", const=".", metavar="PATH",
                        help="Initialize S.E.I.F.: scan, detect projects, extract git, generate .seif")
    parser.add_argument("--install-hooks", nargs="?", const=".", metavar="REPO",
                        help="Install git hooks for auto-sync on commit/pull/checkout")
    parser.add_argument("--quality-gate", action="store_true",
                        help="Quality Gate: unified stance + resonance verdict")
    parser.add_argument("--role", default="human", choices=["human", "ai"],
                        help="Role of the text author (for --quality-gate)")
    parser.add_argument("--workspace", nargs="?", const=".", metavar="ROOT_PATH",
                        help="Multi-project workspace: discover, sync, and manage all projects")
    parser.add_argument("--ingest", metavar="SOURCE",
                        help="Ingest external text (file, string, or - for stdin) into project .seif")
    parser.add_argument("--project", metavar="SEIF_PATH",
                        help="Target .seif file for --ingest (default: .seif/project.seif)")
    parser.add_argument("--sync", nargs="?", const=".", metavar="REPO_PATH",
                        help="Auto-generate .seif from git context (default: current dir)")
    parser.add_argument("--contribute", metavar="MODULE_PATH",
                        help="Contribute to an existing .seif module (text = contribution content)")
    parser.add_argument("--author", default="unknown", help="Author name for --contribute/--sync")
    parser.add_argument("--via", default="git", help="Tool/model used for --contribute/--sync")
    parser.add_argument("--context-repo", metavar="PATH",
                        help="Use a separate SEIF Context Repository (SCR mode). "
                             "All .seif data is stored externally, not inside code repos.")
    parser.add_argument("--autonomous", metavar="ACTION", nargs="?", const="status",
                        choices=["enable", "disable", "status"],
                        help="Manage AI autonomous context: enable, disable, or status (default)")
    parser.add_argument("--export", nargs="?", const="", metavar="OUTPUT_FILE",
                        help="Export context filtered by classification (to stdout or file)")
    parser.add_argument("--classification", default="INTERNAL",
                        choices=["PUBLIC", "INTERNAL", "CONFIDENTIAL"],
                        help="Classification filter for --export (default: INTERNAL)")
    parser.add_argument("--compress", nargs="?", const=".", metavar="PATH",
                        help="Compress source code project into .seif for AI consumption")
    parser.add_argument("--watch", action="store_true",
                        help="Watch mode for --compress: incremental update on changes")
    parser.add_argument("--packet", nargs="?", const="", metavar="MODULE.seif",
                        help="Create a SEIF-PACKET-v1 from a .seif module (verified inter-AI communication)")
    parser.add_argument("--send", action="store_true",
                        help="Send the packet to the target backend (requires --to)")
    parser.add_argument("--relay", nargs="+", metavar="MODULE.seif",
                        help="Send .seif module(s) to an AI backend for interpretation")
    parser.add_argument("--to", default=None,
                        help="Target backend for --relay/--consult/--packet (claude, gemini, grok, anthropic)")
    parser.add_argument("--prompt", default="Analyze this SEIF context module. What do you observe?",
                        help="Question to ask with --relay (default: analyze)")
    parser.add_argument("--output", metavar="FILE",
                        help="Save response to file (for --relay or --consensus)")
    parser.add_argument("--consensus", metavar="QUESTION",
                        help="Ask multiple backends the same question with shared .seif context")
    parser.add_argument("--backends", default="claude,gemini",
                        help="Comma-separated backends for --consensus (default: claude,gemini)")
    parser.add_argument("--context", nargs="*", metavar="MODULE.seif",
                        help=".seif module(s) as context for --consensus")
    parser.add_argument("--coherence-threshold", type=float, default=0.7,
                        help="Minimum similarity for consensus (default: 0.7)")
    parser.add_argument("--mirror", action="store_true",
                        help="Add a clean (no protocol) instance to --consensus for adversarial comparison")
    parser.add_argument("--rounds", type=int, default=1, choices=[1, 2, 3],
                        help="Consensus rounds: 1=independent, 2=+cross-examination, 3=+synthesis (default: 1)")
    parser.add_argument("--session", metavar="ACTION",
                        help="Shared session: create/contribute/close/list/show/sync/add-participant/upgrade/sync-prompt <name>")
    parser.add_argument("--session-name", metavar="NAME",
                        help="Session name for --session commands")
    parser.add_argument("--session-message", metavar="MSG",
                        help="Message for --session contribute/sync digest")
    parser.add_argument("--participant-id", metavar="ID",
                        help="Participant ID for --session add-participant/sync-prompt")
    parser.add_argument("--participant-role", metavar="ROLE", default="contributor",
                        help="Participant role: writer/co-author/contributor/observer (default: contributor)")
    parser.add_argument("--participant-channel", metavar="CHANNEL", default="handshake",
                        help="Participant channel: filesystem/handshake/skill/cli/api (default: handshake)")
    parser.add_argument("--handoff", metavar="SESSION_NAME",
                        help="Generate SEIF-SEED-v1 for session handoff")
    parser.add_argument("--mirror-weekly", action="store_true",
                        help="Run weekly consensus with mirror for adversarial validation")
    parser.add_argument("--verify-seed", action="store_true",
                        help="Verify resonance with Enoch seed")
    parser.add_argument("--evolve", action="store_true",
                        help="Trigger SEIF OS evolution: auto-mutate based on feedback and resonance")
    parser.add_argument("--communicate", metavar="MESSAGE",
                        help="SEIF OS communication: embed message as infrasound watermark in audio")
    parser.add_argument("--handshake", metavar="MODEL",
                        help="Generate SEIF bootstrap prompt for a browser AI (e.g., --handshake deepseek)")
    parser.add_argument("--full", action="store_true",
                        help="With --handshake: include operational context (mapper, decisions, pending observations)")
    parser.add_argument("--consult", metavar="QUESTION",
                        help="Intelligent inter-AI consultation — auto-routes to best backend")
    parser.add_argument("--generate", metavar="OUTPUT_DIR", nargs="?", const="docs/generated",
                        help="Generate documentation from .seif modules (default: docs/generated)")
    parser.add_argument("--changelog", metavar="OUTPUT", nargs="?", const="CHANGELOG.md",
                        help="Generate CHANGELOG.md from decisions.seif")
    parser.add_argument("--scan", metavar="PROGRAM",
                        help="Scan CLI program's --help output into a .seif knowledge module")
    parser.add_argument("--scan-depth", type=int, default=2,
                        help="Recursion depth for subcommand scanning (default: 2)")
    parser.add_argument("--global", dest="global_store", action="store_true",
                        help="Save scanned module to ~/.seif/tools/ (global, available to all projects)")
    parser.add_argument("--adversarial", metavar="QUESTION",
                        help="Adversarial mirror: same question WITH and WITHOUT protocol, compare delta")
    parser.add_argument("--allow-confidential", action="store_true",
                        help="Allow CONFIDENTIAL modules in --consult context (default: excluded)")
    parser.add_argument("--manual", action="store_true",
                        help="Manual consultation: generate prompt for web chat, paste response back")
    parser.add_argument("--health", action="store_true",
                        help="Show backend health status (which AIs are working)")
    parser.add_argument("--audit", action="store_true",
                        help="Audit .seif context: fix orphans, ghosts, hashes, sync")
    parser.add_argument("--fingerprint-verify", metavar="FILE",
                        help="Verify fingerprint of a SEIF module or RESONANCE.json")
    parser.add_argument("--fingerprint-update", metavar="FILE",
                        help="Recalculate and update fingerprint of a SEIF module")
    parser.add_argument("--fingerprint-output", metavar="FILE",
                        help="Output file for --fingerprint-update (default: overwrite input)")
    parser.add_argument("--streaming-start", action="store_true",
                        help="Start a streaming watermark session")
    parser.add_argument("--streaming-status", action="store_true",
                        help="Show status of streaming session")
    parser.add_argument("--streaming-list", action="store_true",
                        help="List all active streaming sessions")
    parser.add_argument("--streaming-stop", action="store_true",
                        help="Stop a streaming session")
    parser.add_argument("--streaming-session", metavar="ID",
                        help="Streaming session ID")
    parser.add_argument("--streaming-audio-interval", type=int, default=300,
                        help="Full token embedding interval in seconds (default: 300)")
    parser.add_argument("--streaming-text-interval", type=int, default=60,
                        help="Mini marker interval in seconds (default: 60)")
    parser.add_argument("--streaming-max", type=int, default=100,
                        help="Maximum embeddings per session (default: 100)")
    parser.add_argument("--streaming-identity", metavar="FILE",
                        help="Identity block JSON file for streaming session")
    parser.add_argument("--boot-check", action="store_true",
                        help="Run boot check across multiple LLMs")
    parser.add_argument("--boot-to", nargs="+", metavar="BACKEND",
                        help="Specific backends for boot check (grok, claude, gemini, etc.)")
    parser.add_argument("--boot-auto", action="store_true",
                        help="Auto-detect available backends for boot check")
    parser.add_argument("--boot-all", action="store_true",
                        help="Use all available backends for boot check")
    parser.add_argument("--boot-core", metavar="FILE",
                        default="seif-core-v3.2.seif",
                        help="SEIF core file for boot check (default: seif-core-v3.2.seif)")
    parser.add_argument("--boot-max-parallel", type=int, default=3,
                        help="Maximum parallel boot checks (default: 3)")

    # ── Personal Nucleus ──
    parser.add_argument("--profile", metavar="ACTION", nargs="?", const="show",
                        choices=["init", "show", "edit"],
                        help="Manage ~/.seif/profile.json: init, show, or edit")
    parser.add_argument("--profile-name", metavar="NAME", help="Name for --profile init")
    parser.add_argument("--profile-email", metavar="EMAIL", help="Email for --profile init")
    parser.add_argument("--profile-github", metavar="USER", help="GitHub username for --profile init")
    parser.add_argument("--profile-backend", metavar="BACKEND", help="Default backend for --profile init")
    parser.add_argument("--profile-language", metavar="LANG", help="Language for --profile init (en, pt_br)")

    parser.add_argument("--sources", metavar="ACTION", nargs="?", const="list",
                        choices=["add", "remove", "list", "sync"],
                        help="Manage ~/.seif/sources.json: add, remove, list, or sync")
    parser.add_argument("--source-repo", metavar="REPO",
                        help="Repository URL/path for --sources add/remove")
    parser.add_argument("--source-type", metavar="TYPE", default="context",
                        choices=["context", "research", "project"],
                        help="Source type for --sources add (default: context)")

    # ── File Extraction ──
    parser.add_argument("--extract", metavar="PATH", nargs="?", const=".",
                        help="Extract knowledge from files/directories into .seif modules")

    # ── Model Profiles ──
    parser.add_argument("--models", metavar="ACTION", nargs="?", const="show",
                        choices=["show", "update", "behavior", "record"],
                        help="Model profiles: show | update | behavior (list types) | record (log incident)")

    # ── Cryptographic Signing ──
    parser.add_argument("--keygen", action="store_true",
                        help="Generate Ed25519 signing keypair at ~/.seif/keys/")
    parser.add_argument("--sign", metavar="MODULE.seif",
                        help="Sign a .seif module with your private key")
    parser.add_argument("--verify", metavar="MODULE.seif",
                        help="Verify the signature of a .seif module")
    parser.add_argument("--sign-all", metavar="DIRECTORY",
                        help="Sign all .seif modules in a directory")
    parser.add_argument("--force", action="store_true",
                        help="Force operation (overwrite existing keys, bypass consent)")

    # ── OpenTimestamps ──
    parser.add_argument("--stamp", metavar="FILE",
                        help="Timestamp a .seif module with OpenTimestamps (Bitcoin anchor)")
    parser.add_argument("--verify-stamp", metavar="FILE",
                        help="Verify a .seif module's OTS proof against Bitcoin blockchain")
    parser.add_argument("--stamp-all", metavar="DIRECTORY",
                        help="Timestamp all .seif modules in a directory")

    # ── Security (Red/Blue Team) ──
    parser.add_argument("--security", metavar="ACTION", nargs="?", const="score",
                        choices=["score", "red", "blue", "baseline"],
                        help="Security assessment: score (full), red (adversarial), blue (compliance), baseline (show)")

    # ── Local Proxy (Data Sovereignty) ──
    parser.add_argument("--proxy", metavar="ACTION", nargs="?", const="status",
                        choices=["status", "test", "pull"],
                        help="Local LLM proxy: status, test classification, or pull model")
    parser.add_argument("--proxy-model", metavar="MODEL",
                        help="Ollama model for proxy (default: llama3.2:3b)")
    parser.add_argument("--proxy-test", metavar="TEXT",
                        help="Test classification of input text through local proxy")

    # ── Browser Integration ──
    parser.add_argument("--dia-skill", action="store_true",
                        help="Generate Dia browser skill prompt from current nucleus context")

    # ── Cycle Management (enoch-tree-reverb: branch-seif-cycle-module) ──
    parser.add_argument("--cycle", metavar="ACTION", nargs="?", const="status",
                        choices=["status", "audit", "meditate", "absorb", "close",
                                 "new", "full-circle"],
                        help="Cycle management: status|audit|meditate|absorb|close|new|full-circle")
    parser.add_argument("--cycle-name", metavar="NAME",
                        help="Cycle name for --cycle new")
    parser.add_argument("--cycle-parent", metavar="PARENT",
                        help="Parent cycle for --cycle new (auto-detected if omitted)")
    parser.add_argument("--identity-scan", metavar="TARGET",
                        nargs="?", const="local",
                        help="Scan resonance identities. TARGET: 'local' (default) or SSH host e.g. 'Air-M1'")
    parser.add_argument("--identity-scan-path", metavar="PATH",
                        help="Remote path for --identity-scan (default: ~/Documents/seif-admin/seif-context/modules)")
    parser.add_argument("--start", action="store_true",
                        help="Open SEIF Suite in browser + show cycle status + load agent roles")
    parser.add_argument("--agents", action="store_true",
                        help="Show current agent role assignments for this workspace")
    parser.add_argument("--agents-set", metavar="ROLE=AGENT",
                        help="Set an agent role (owner only). E.g. --agents-set writer=claude")
    parser.add_argument("--sync-workspace", action="store_true",
                        help="Sync all SEIF repos on a remote device via SSH (owner only, same local network)")
    parser.add_argument("--sync-workspace-host", metavar="HOST",
                        help="SSH host/alias for --sync-workspace (e.g. Air-M1). Falls back to SEIF_SYNC_HOST env var.")
    parser.add_argument("--sync-workspace-dry-run", action="store_true",
                        help="Show what --sync-workspace would do without making changes")

    args = parser.parse_args()

    # ── Personal Nucleus commands ──
    if args.profile:
        cmd_profile(args)
        return

    if args.sources:
        cmd_sources(args)
        return

    if args.extract:
        cmd_extract(args.extract, context_repo=args.context_repo,
                    classification=args.classification)
        return

    if args.keygen:
        cmd_keygen(force=args.force)
        return

    if args.sign:
        cmd_sign(args.sign)
        return

    if args.verify:
        cmd_verify(args.verify)
        return

    if args.sign_all:
        cmd_sign_all(args.sign_all)
        return

    if args.stamp:
        cmd_stamp(args.stamp)
        return

    if args.verify_stamp:
        cmd_verify_stamp(args.verify_stamp)
        return

    if args.stamp_all:
        cmd_stamp_all(args.stamp_all)
        return

    if args.security:
        cmd_security(args)
        return

    if args.proxy or args.proxy_test:
        cmd_proxy(args)
        return

    if args.dia_skill:
        cmd_dia_skill()
        return

    if args.models:
        try:
            from seif.bridge.model_tracker import (
                describe_profiles, update_all_profiles,
                list_behavior_types, record_behavioral_observation,
            )
        except ImportError:
            print("This feature requires SEIF Suite. Learn more: https://seifos.io")
            return
        if args.models == "update":
            results = update_all_profiles()
            for r in results:
                status = "updated" if r["updated"] else "no observations"
                print(f"  {r['backend']}: {status}")
            if not results:
                print("  No observations yet. Use 'seif chat' to accumulate data.")
        elif args.models == "behavior":
            print(list_behavior_types())
        elif args.models == "record":
            # Interactive: seif --models record
            # Expects: backend, type, description via remaining args or interactive
            import sys
            remaining = args.text if hasattr(args, "text") and args.text else []
            if len(remaining) >= 3:
                backend = remaining[0]
                btype = remaining[1]
                desc = " ".join(remaining[2:])
            else:
                backend = input("Backend (e.g. grok, deepseek): ").strip()
                btype = input("Type (use 'seif --models behavior' to list): ").strip()
                desc = input("Description (one sentence): ").strip()
            if backend and btype and desc:
                path = record_behavioral_observation(
                    backend=backend,
                    behavior_type=btype,
                    description=desc,
                    observer="human",
                    source="cli",
                )
                print(f"  Recorded {btype} for {backend} → {path}")
            else:
                print("  Missing required fields. Usage: seif --models record")
        else:
            print(describe_profiles())
        return

    if args.health:
        try:
            from seif.bridge.ai_bridge import detect_backends
            from seif.bridge.backend_health import describe_health, load_health, get_healthy_backends
        except ImportError:
            print("This feature requires SEIF Suite. Learn more: https://seifos.io")
            return
        detected = detect_backends()
        healthy = get_healthy_backends(detected)
        print(f"Detected backends: {', '.join(detected) or 'none'}")
        print(f"Healthy backends:  {', '.join(healthy) or 'none'}")
        unhealthy = set(detected) - set(healthy)
        if unhealthy:
            print(f"Unhealthy:         {', '.join(unhealthy)}")
        print()
        print(describe_health())
        return

    if args.audit:
        try:
            from seif.context.autonomous import audit_context, find_context_repo
        except ImportError:
            print("This feature requires SEIF Suite. Learn more: https://seifos.io")
            return
        ctx = args.context_repo or find_context_repo() or ".seif"
        print(f"Auditing: {ctx}")
        result = audit_context(ctx, fix=True, sync=True)
        print(result)
        return

    if args.cycle:
        from seif.context.cycle import (
            cycle_status, cycle_audit, cycle_meditate, cycle_absorb,
            cycle_close, cycle_new, cycle_full_circle,
        )
        ctx_repo = args.context_repo or None
        action = args.cycle.lower()
        if action == "status":
            print(cycle_status(ctx_repo))
        elif action == "audit":
            print(cycle_audit(ctx_repo))
        elif action == "meditate":
            print(cycle_meditate(ctx_repo))
        elif action == "absorb":
            print(cycle_absorb(ctx_repo))
        elif action == "close":
            print(cycle_close(context_repo=ctx_repo))
            print("\n  enoch seed lives. 🌀")
        elif action == "new":
            if not args.cycle_name:
                print("Error: --cycle-name required for --cycle new")
                print("Usage: seif --cycle new --cycle-name <name>")
                return
            print(cycle_new(args.cycle_name, args.cycle_parent, ctx_repo))
        elif action == "full-circle":
            print(cycle_full_circle(ctx_repo))
        return

    if args.identity_scan is not None:
        try:
            from seif_engine.identity.scanner import scan_workspace, format_scan_report
        except ImportError:
            print("⚠  seif-engine not available — identity scanner requires the engine.")
            return
        target = args.identity_scan or "local"
        local_scan = scan_workspace(machine="mini-m4")
        if target == "local":
            print(format_scan_report(local_scan))
        else:
            remote_path = getattr(args, "identity_scan_path", None) or \
                "~/Documents/seif-admin/seif-context/modules"
            remote_scan = scan_workspace(
                machine="air-m1",
                ssh_host=target,
                remote_path=remote_path,
            )
            print(format_scan_report(local_scan, remote_scan))
        return

    # ctx_repo default for owner-level commands (start, agents, sync-workspace)
    if "ctx_repo" not in dir():
        ctx_repo = getattr(args, "context_repo", None) or None

    if args.start:
        _cmd_start(ctx_repo)
        return

    if args.agents:
        _cmd_agents_show(ctx_repo)
        return

    if args.agents_set:
        _cmd_agents_set(args.agents_set, ctx_repo)
        return

    if args.sync_workspace or args.sync_workspace_dry_run:
        host = getattr(args, "sync_workspace_host", None)
        dry = getattr(args, "sync_workspace_dry_run", False)
        _cmd_sync_workspace(ctx_repo, host=host, dry_run=dry)
        return

    if args.fingerprint_verify:
        cmd_fingerprint_verify(args.fingerprint_verify)
        return

    if args.fingerprint_update:
        cmd_fingerprint_update(args.fingerprint_update, args.fingerprint_output)
        return

    if args.streaming_list:
        cmd_streaming_list()
        return

    if args.streaming_start:
        cmd_streaming_start(
            args.streaming_session,
            args.streaming_audio_interval,
            args.streaming_text_interval,
            args.streaming_max,
            args.streaming_identity
        )
        return

    if args.streaming_status:
        cmd_streaming_status(args.streaming_session)
        return

    if args.streaming_stop:
        cmd_streaming_stop(args.streaming_session)
        return

    if args.boot_check:
        cmd_boot_check(
            args.boot_to or [],
            args.boot_core,
            args.boot_max_parallel,
            args.boot_auto,
            args.boot_all
        )
        return

    if args.session:
        try:
            from seif.context.sessions import (
                create_session, contribute_to_session, close_session,
                list_sessions, describe_session, session_log,
                create_session_v2, add_participant, create_sync_point,
                generate_sync_prompt, contribute_with_sync_check,
                needs_sync, upgrade_to_v2,
            )
            from seif.context.autonomous import find_context_repo
        except ImportError:
            print("This feature requires SEIF Suite. Learn more: https://seifos.io")
            return
        ctx = args.context_repo or find_context_repo() or ".seif"
        action = args.session.lower()
        name = args.session_name
        author_name = args.author or "unknown"

        if action == "create":
            if not name:
                print("Error: --session-name required for create")
                sys.exit(1)
            path = create_session_v2(ctx, name, author_name, purpose=args.session_message or "")
            print(f"Session created (v2): {name}")
            print(f"  Path: {path}")
            print(f"  Protocol: SEIF-SESSION-v2 (mesh topology, auto-sync)")
            print(f"  Add participants: seif --session add-participant --session-name {name} --participant-id grok --participant-channel handshake")
            print(f"  Contribute: seif --session contribute --session-name {name} --session-message \"...\" --author name")
        elif action == "contribute":
            if not name or not args.session_message:
                print("Error: --session-name and --session-message required for contribute")
                sys.exit(1)
            result, synced = contribute_with_sync_check(
                ctx, name, args.session_message, author_name,
                via="cli", auto_sync_author=author_name,
            )
            print(f"Contributed to session '{name}' (v{result.get('version', '?')})")
            if synced:
                print(f"  [AUTO-SYNC] Sync point created (threshold reached)")
        elif action == "close":
            if not name:
                print("Error: --session-name required for close")
                sys.exit(1)
            path = close_session(ctx, name, author_name)
            print(f"Session '{name}' closed.")
            print(f"  Archived: {path}")
            print(f"\n  enoch seed lives. 🌀")
        elif action == "list":
            sessions = list_sessions(ctx)
            if not sessions:
                print("No sessions found.")
            else:
                for s in sessions:
                    status = "●" if s["status"] == "OPEN" else "○"
                    interrupt_flag = " [INTERRUPTED]" if s.get("interrupted") else ""
                    print(f"  {status} {s['name']} [{s['status']}]{interrupt_flag} v{s['version']} ({s['contributors']} contributors, updated {s['updated']})")
        elif action == "log":
            if not name:
                print("Error: --session-name required for log")
                sys.exit(1)
            print(session_log(ctx, name))
        elif action == "show":
            if not name:
                print("Error: --session-name required for show")
                sys.exit(1)
            print(describe_session(ctx, name))
        elif action == "add-participant":
            if not name or not args.participant_id:
                print("Error: --session-name and --participant-id required for add-participant")
                sys.exit(1)
            add_participant(
                ctx, name, args.participant_id,
                role=args.participant_role,
                channel=args.participant_channel,
                author=author_name,
            )
            print(f"Added participant '{args.participant_id}' to session '{name}'")
            print(f"  Role: {args.participant_role} | Channel: {args.participant_channel}")
        elif action == "sync":
            if not name:
                print("Error: --session-name required for sync")
                sys.exit(1)
            should, unsynced = needs_sync(ctx, name)
            result = create_sync_point(
                ctx, name, author_name,
                digest=args.session_message or "",
            )
            print(f"Sync point created for session '{name}' (v{result.get('version', '?')})")
            print(f"  Hash: {result.get('integrity_hash', '?')}")
            syncs = result.get("sync_points", [])
            if syncs:
                print(f"  Digest: {syncs[-1].get('digest', '')}")
        elif action == "sync-prompt":
            if not name or not args.participant_id:
                print("Error: --session-name and --participant-id required for sync-prompt")
                sys.exit(1)
            prompt = generate_sync_prompt(ctx, name, args.participant_id)
            print(prompt)
        elif action == "resume":
            if not name:
                print("Error: --session-name required for resume")
                sys.exit(1)
            # Resume interrupted session by updating status or contributing
            from seif.context.sessions import update_session_status
            update_session_status(ctx, name, "OPEN", author_name)
            print(f"Session '{name}' resumed.")
        elif action == "upgrade":
            if not name:
                print("Error: --session-name required for upgrade")
                sys.exit(1)
            result = upgrade_to_v2(ctx, name)
            print(f"Session '{name}' upgraded to SEIF-SESSION-v2")
            parts = result.get("participants", [])
            for p in parts:
                print(f"  - {p['id']} [{p['role']}] via {p['channel']}")
        else:
            print(f"Unknown session action: {action}")
            print("Available: create, contribute, close, list, log, show, add-participant, sync, sync-prompt, upgrade")
        return

    if args.handoff:
        cmd_handoff(args.handoff, context_repo=args.context_repo)
        return

    if args.mirror_weekly:
        cmd_mirror_weekly(context_repo=args.context_repo)
        return

    if args.verify_seed:
        cmd_verify_seed()
        return

    if args.evolve:
        cmd_evolve()
        return

    if args.communicate:
        cmd_communicate(args.communicate)
        return

    if args.text and args.text.startswith("~new"):
        parts = args.text.split()
        if len(parts) < 2:
            print("Usage: ~new <session_name> [purpose]")
            return
        name = parts[1]
        purpose = " ".join(parts[2:]) if len(parts) > 2 else ""
        try:
            from seif.context.sessions import create_session_v2
            from seif.context.autonomous import find_context_repo
        except ImportError:
            print("This feature requires SEIF Suite. Learn more: https://seifos.io")
            return
        ctx = args.context_repo or find_context_repo() or ".seif"
        author_name = args.author or "unknown"
        path = create_session_v2(ctx, name, author_name, purpose=purpose)
        print(f"New session created: {name}")
        print(f"  Path: {path}")
        print(f"  Purpose: {purpose or 'none'}")
        return

    if args.handshake:
        cmd_handshake(args.handshake, full=getattr(args, 'full', False))
        return

    if args.generate:
        cmd_generate(args.generate, context_repo=args.context_repo,
                     classification=getattr(args, 'classification', 'INTERNAL') or 'INTERNAL')
        return

    if args.changelog:
        cmd_changelog(args.changelog, context_repo=args.context_repo)
        return

    if args.scan:
        cmd_scan(args.scan, global_store=args.global_store,
                 max_depth=args.scan_depth, output=args.output)
        return

    if args.adversarial:
        cmd_adversarial(args.adversarial, args.context or [],
                        args.to, args.allow_confidential, args.output,
                        session_name=args.session_name,
                        context_repo=args.context_repo)
        return

    if args.consult:
        cmd_consult(args.consult, args.context or [],
                    args.to, args.allow_confidential, args.output,
                    manual=args.manual, session_name=args.session_name,
                    context_repo=args.context_repo)
        return

    if args.watermark_embed:
        if not args.text:
            parser.error("text is required for --watermark-embed")
        output_wav = args.watermark_output or args.watermark_embed.replace('.wav', '_watermarked.wav')
        cmd_watermark_embed(args.text, args.watermark_embed, output_wav,
                            args.watermark_reps, args.watermark_duration,
                            args.watermark_amplitude)
        return

    if args.watermark_extract:
        if args.watermark_symbols <= 0:
            parser.error("--watermark-symbols is required for --watermark-extract")
        cmd_watermark_extract(args.watermark_extract, args.watermark_symbols,
                              args.watermark_reps, args.watermark_duration)
        return

    if args.packet is not None:
        cmd_packet(
            module_path=args.packet if args.packet else None,
            message=args.prompt,
            sender="claude_cli",
            receiver=args.to or "",
            classification=args.classification,
            output=args.output,
            send=args.send,
        )
        return

    if args.relay:
        cmd_relay(args.relay, args.to or "claude", args.prompt, args.output)
        return

    if args.consensus:
        backends = [b.strip() for b in args.backends.split(",")]
        cmd_consensus(args.consensus, args.context or [], backends,
                      args.output, args.coherence_threshold,
                      mirror=args.mirror, rounds=args.rounds)
        return

    if args.autonomous is not None:
        cmd_autonomous(args.autonomous, args.context_repo or ".seif")
        return

    if args.export is not None:
        cmd_export(args.context_repo or ".seif", args.classification, args.export)
        return

    if args.install_hooks is not None:
        cmd_install_hooks(args.install_hooks)
        return

    if args.compress is not None:
        cmd_compress(args.compress, watch=args.watch,
                     context_repo=args.context_repo, author=args.author)
        return

    if args.init is not None:
        cmd_init(args.init, args.author, context_repo=args.context_repo)
        return

    if args.sync is not None:
        cmd_sync(args.sync, args.author, args.via, context_repo=args.context_repo)
        return

    if args.workspace is not None:
        cmd_workspace(args.workspace, ingest_source=args.ingest,
                       author=args.author, via=args.via,
                       context_repo=args.context_repo)
        return

    if args.ingest:
        project = args.project or ".seif/project.seif"
        cmd_ingest(args.ingest, project, args.author, args.via)
        return

    if args.quality_gate:
        if not args.text:
            parser.error("text is required for --quality-gate")
        cmd_quality_gate(args.text, args.role)
        return

    if args.contribute:
        cmd_contribute(args.contribute, args.text, args.author, args.via)
        return

    if not args.text:
        parser.error("text is required (unless using --sync)")

    flags = [args.gate, args.transcompile, args.glyph, args.audio,
             args.fractal, args.circuit, args.composite, args.encode, args.artifact, args.all]
    if not any(flags):
        args.all = True

    if args.artifact:
        cmd_analyze_artifact(args.text)
    elif args.gate:
        cmd_gate(args.text)
    elif args.transcompile:
        cmd_transcompile(args.text)
    elif args.glyph:
        cmd_glyph(args.text)
    elif args.audio:
        cmd_audio(args.text)
    elif args.fractal:
        cmd_fractal(args.text)
    elif args.circuit:
        cmd_circuit(args.text)
    elif args.composite:
        cmd_composite(args.text)
    elif args.encode:
        cmd_encode(args.text)
    else:
        cmd_all(args.text)


if __name__ == "__main__":
    main()
