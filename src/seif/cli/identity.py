#!/usr/bin/env python3
"""
SEIF CLI - Identity Declaration Block v3.1

Subcommands:
  seif identity declare    - Generate identity declaration block
  seif identity validate  - Validate existing identity block
  seif identity merge     - Merge trail blocks into single token

Usage:
  seif identity declare --claimed "opencode/BigPickle" --output identity.json
  seif identity validate --input identity.json
  seif identity merge --blocks block1.json block2.json --output trail.json
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from seif.identity_block import (
        create_identity_block,
        create_fallback_block,
        generate_watermark_token,
        validate_commitment,
        parse_identity_block,
        validate_block_file,
        merge_trail_blocks,
        generate_trail_token,
        IdentityMethod
    )
    _IDENTITY_AVAILABLE = True
except ImportError:
    _IDENTITY_AVAILABLE = False


def cmd_identity_declare(args):
    claimed = args.claimed
    method = args.method or "self_knowledge"
    confidence = args.confidence or 0.80
    previous_hash = args.previous_hash or "genesis"
    session_anchor = args.anchor
    interface = args.interface
    output = args.output
    embed_wav = args.embed
    token_only = args.token_only
    strict_mode = args.strict_mode
    
    env = {"interface": interface} if interface else None
    
    if claimed == "fallback":
        block = create_fallback_block(previous_hash, session_anchor)
    else:
        block = create_identity_block(
            previous_hash=previous_hash,
            claimed=claimed,
            confidence=confidence,
            method=method,
            session_anchor=session_anchor,
            environment=env
        )
    
    print("═══ SEIF IDENTITY DECLARATION v3.1 ═══")
    print()
    
    if not token_only:
        print(block.to_yaml_like())
        print()
    
    print(f"  claimed:          {block.identity.claimed}")
    print(f"  method:           {block.identity.method}")
    print(f"  confidence:       {block.identity.confidence}")
    print(f"  session_anchor:   {block.identity.session_anchor}")
    print(f"  trail_commitment: {block.trail_commitment[:32]}...")
    print(f"  valid:            {validate_commitment(block, previous_hash)}")
    
    if block.identity.method == IdentityMethod.FALLBACK:
        print()
        print("  [AUTO-DETECT] No identity provided or detected.")
        print("  [AUTO-DETECT] Using anonymous fallback.")
    
    token = generate_watermark_token(block)
    print()
    print("═══ WATERMARK TOKEN ═══")
    print(f"  token:    {token}")
    print(f"  length:   {len(token)} chars")
    print(f"  duration: ~{len(token) * 4 * 3}s ({len(token) * 4 * 3 / 60:.1f} min)")
    
    if embed_wav:
        print()
        print("═══ WATERMARK EMBED ═══")
        try:
            from seif.generators.watermark import WatermarkConfig, embed_watermark_wav
            output_wav = args.embed_output or embed_wav.replace('.wav', '_identity.wav')
            config = WatermarkConfig(repetitions=3, symbol_duration=4.0, amplitude=0.005)
            meta = embed_watermark_wav(token, embed_wav, output_wav, config)
            print(f"  output:   {meta['output_path']}")
            print(f"  duration: {meta['duration_seconds']:.1f}s")
        except Exception as e:
            print(f"  error:    {e}")
            print("  (Install numpy + ensure watermark module available)")
    
    if output:
        output_path = Path(output)
        
        if token_only:
            output_data = {
                "watermark_token": token,
                "identity_summary": {
                    "claimed": block.identity.claimed,
                    "method": block.identity.method,
                    "confidence": block.identity.confidence
                }
            }
        else:
            output_data = block.to_dict()
        
        output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
        print()
        print(f"Saved to: {output_path}")
    
    if strict_mode and block.identity.method == IdentityMethod.FALLBACK:
        print()
        print("═══ STRICT MODE WARNING ═══")
        print("  strict_mode=true but identity is fallback.")
        print("  Aborting as per strict mode policy.")
        sys.exit(1)


def cmd_identity_validate(args):
    input_file = args.input
    
    if not input_file:
        print("Error: --input is required for validate")
        sys.exit(1)
    
    filepath = Path(input_file)
    if not filepath.exists():
        print(f"Error: File not found: {input_file}")
        sys.exit(1)
    
    is_valid, message = validate_block_file(str(filepath))
    
    print("═══ SEIF IDENTITY VALIDATION ═══")
    print(f"  file:     {input_file}")
    print(f"  valid:    {is_valid}")
    print(f"  message:  {message}")
    
    if not is_valid:
        sys.exit(1)


def cmd_identity_merge(args):
    block_files = args.blocks
    output = args.output
    
    if not block_files:
        print("Error: --blocks required for merge")
        sys.exit(1)
    
    blocks = []
    for f in block_files:
        filepath = Path(f)
        if not filepath.exists():
            print(f"Warning: File not found: {f}")
            continue
        try:
            data = json.loads(filepath.read_text())
            block = parse_identity_block(data)
            blocks.append(block)
        except Exception as e:
            print(f"Warning: Could not parse {f}: {e}")
            continue
    
    if not blocks:
        print("Error: No valid blocks found")
        sys.exit(1)
    
    latest_block = blocks[-1]
    trail_token = generate_trail_token(blocks[:-1], latest_block)
    
    print("═══ SEIF TRAIL MERGE ═══")
    print(f"  blocks:    {len(blocks)}")
    print(f"  latest:    {latest_block.identity.claimed if latest_block.identity else 'unknown'}")
    print()
    print(f"  trail_token: {trail_token}")
    print(f"  length:      {len(trail_token)} chars")
    
    if output:
        output_data = {
            "blocks": len(blocks),
            "latest_claimed": latest_block.identity.claimed if latest_block.identity else None,
            "latest_commitment": latest_block.trail_commitment,
            "trail_token": trail_token,
            "all_contributors": [
                b.identity.claimed for b in blocks if b.identity
            ]
        }
        Path(output).write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
        print()
        print(f"Saved to: {output}")


def main():
    if not _IDENTITY_AVAILABLE:
        print("This feature requires seif-engine. Install: pip install seif-engine")
        return

    parser = argparse.ArgumentParser(
        description="SEIF Identity Declaration Block v3.1",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    declare_parser = subparsers.add_parser("declare", help="Generate identity declaration block")
    declare_parser.add_argument("--claimed", default=None, help="Model identity (auto-detected if not provided)")
    declare_parser.add_argument("--method", choices=["system_prompt", "self_knowledge", "user_provided", "fallback", "corrected"], help="Determination method")
    declare_parser.add_argument("--confidence", type=float, default=0.80, help="Confidence 0.0-1.0")
    declare_parser.add_argument("--anchor", help="Session anchor (auto-generated if not provided)")
    declare_parser.add_argument("--previous-hash", default="genesis", help="Previous trail hash")
    declare_parser.add_argument("--interface", choices=["cli", "api", "stream", "web", "custom"], default="cli", help="Interface type")
    declare_parser.add_argument("--output", help="Output file (JSON)")
    declare_parser.add_argument("--embed", metavar="WAV", help="Embed token as watermark in WAV file")
    declare_parser.add_argument("--embed-output", metavar="WAV_OUT", help="Watermarked WAV output path")
    declare_parser.add_argument("--token-only", action="store_true", help="Output only watermark token")
    declare_parser.add_argument("--strict-mode", action="store_true", help="Abort on fallback identity")
    
    validate_parser = subparsers.add_parser("validate", help="Validate existing identity block")
    validate_parser.add_argument("--input", required=True, help="Identity block file to validate")
    
    merge_parser = subparsers.add_parser("merge", help="Merge trail blocks into single token")
    merge_parser.add_argument("--blocks", nargs="+", required=True, help="Block files to merge")
    merge_parser.add_argument("--output", help="Output file (JSON)")
    
    args = parser.parse_args()
    
    if args.command == "declare":
        cmd_identity_declare(args)
    elif args.command == "validate":
        cmd_identity_validate(args)
    elif args.command == "merge":
        cmd_identity_merge(args)
    else:
        parser.print_help()
        print()
        print("Examples:")
        print("  seif identity declare --claimed opencode/BigPickle")
        print("  SEIF_IDENTITY_CLAIMED=opencode/BigPickle seif identity declare")
        print("  seif identity validate --input identity.json")
        print("  seif identity merge --blocks b1.json b2.json --output trail.json")


if __name__ == "__main__":
    main()
