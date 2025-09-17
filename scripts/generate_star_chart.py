#!/usr/bin/env python3
"""Command line interface to generate neon HUD-style star charts."""
from __future__ import annotations

import argparse
from pathlib import Path

from star_chart_generator import generate_chart, load_config, save_render


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Path to the scene configuration file (YAML).")
    parser.add_argument("output", type=Path, help="Output image path or directory.")
    parser.add_argument("--no-layers", action="store_true", help="Do not export auxiliary layer PNGs.")
    parser.add_argument("--seed", type=int, default=None, help="Override the seed defined in the configuration.")
    parser.add_argument(
        "--resolution",
        type=str,
        default=None,
        help="Override resolution as WIDTHxHEIGHT (e.g. 4096x6144).",
    )
    parser.add_argument("--ssaa", type=int, default=None, help="Override SSAA factor.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    if args.seed is not None:
        config.seed = args.seed
    if args.resolution:
        width, height = (int(part) for part in args.resolution.lower().split("x", 1))
        config.resolution.width = width
        config.resolution.height = height
    if args.ssaa is not None:
        config.resolution.ssaa = args.ssaa
    result = generate_chart(config)
    outputs = save_render(result, args.output, save_layers=not args.no_layers)
    print("Generated files:")
    for label, path in outputs.items():
        print(f"  {label:>16}: {path}")


if __name__ == "__main__":
    main()
