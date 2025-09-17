#!/usr/bin/env python3
"""CLI entry point for the star chart generator."""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path
from typing import Dict

# Allow running the script directly from the repository root without installing the
# package by adding ``src`` to ``sys.path`` when available.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if SRC_PATH.exists():
    src_str = str(SRC_PATH)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

from star_chart_generator import SceneConfig, generate_star_chart
from star_chart_generator.image import FloatImage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a star chart from a YAML config")
    parser.add_argument("config", type=Path, help="Path to the scene YAML configuration")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        help="Destination image file (defaults to config name with .png)",
    )
    parser.add_argument(
        "--output",
        dest="output_override",
        type=Path,
        help="Explicit destination image path",
    )
    parser.add_argument("--seed", type=int, help="Override the RNG seed for rendering")
    parser.add_argument(
        "--layers-dir",
        type=Path,
        help="If provided, saves intermediate layers (PNG) into this directory",
    )
    parser.add_argument(
        "--compare",
        type=Path,
        help="Compute the mean absolute difference against a reference PNG",
    )
    return parser.parse_args()


def _save_layers(layers: Dict[str, FloatImage], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in layers.items():
        data.save_png(str(directory / f"{name}.png"))


def _load_png(path: Path) -> FloatImage:
    with path.open("rb") as fh:
        data = fh.read()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Unsupported PNG signature")
    offset = 8
    width = height = None
    pixels = b""
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        offset += 4
        tag = data[offset : offset + 4]
        offset += 4
        payload = data[offset : offset + length]
        offset += length
        crc = data[offset : offset + 4]
        offset += 4
        if tag == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", payload)
            if bit_depth != 8 or color_type != 2:
                raise ValueError("Only 8-bit RGB PNGs are supported")
        elif tag == b"IDAT":
            pixels += payload
        elif tag == b"IEND":
            break
    decompressed = zlib.decompress(pixels)
    image = FloatImage.new(width, height, 0.0)
    stride = width * 3 + 1
    for y in range(height):
        row = decompressed[y * stride : (y + 1) * stride]
        if row[0] != 0:
            raise ValueError("Only PNG filter 0 supported")
        for x in range(width):
            r = row[1 + 3 * x] / 255.0
            g = row[1 + 3 * x + 1] / 255.0
            b = row[1 + 3 * x + 2] / 255.0
            image.pixels[y][x][0] = r
            image.pixels[y][x][1] = g
            image.pixels[y][x][2] = b
    return image


def _mean_abs_diff(a: FloatImage, b: FloatImage) -> float:
    if a.width != b.width or a.height != b.height:
        raise ValueError("Images must share the same dimensions for comparison")
    total = 0.0
    count = a.width * a.height * 3
    for y in range(a.height):
        for x in range(a.width):
            pa = a.pixels[y][x]
            pb = b.pixels[y][x]
            total += abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) + abs(pa[2] - pb[2])
    return total / count


def main() -> None:
    args = parse_args()
    config = SceneConfig.load(args.config)
    result = generate_star_chart(config, seed=args.seed)

    output_path = args.output_override or args.output
    if output_path is None:
        output_path = args.config.with_suffix(".png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(str(output_path))

    if args.layers_dir:
        _save_layers(result.layers, args.layers_dir)

    if args.compare:
        reference = _load_png(args.compare)
        diff = _mean_abs_diff(result.image, reference)
        print(f"Mean absolute difference vs {args.compare}: {diff:.6f}")


if __name__ == "__main__":
    main()
