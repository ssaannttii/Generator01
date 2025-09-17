"""Output helpers for star chart renders."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from PIL import Image

from .generate import RenderResult
from .post import tonemap_aces


def save_render(result: RenderResult, output_path: Path | str, save_layers: bool = True) -> Dict[str, Path]:
    base = Path(output_path)
    base.parent.mkdir(parents=True, exist_ok=True)
    if base.suffix:
        target_dir = base.parent
        stem = base.stem
    else:
        target_dir = base
        target_dir.mkdir(parents=True, exist_ok=True)
        stem = base.name
    outputs: Dict[str, Path] = {}

    tonemapped_path = (target_dir / stem).with_suffix(".png")
    result.tonemapped.save(tonemapped_path)
    outputs["tonemapped_png"] = tonemapped_path

    linear_img = _float_to_rgb16(result.linear)
    linear_path = (target_dir / f"{stem}_linear").with_suffix(".tiff")
    linear_img.save(linear_path)
    outputs["linear_tiff"] = linear_path

    if save_layers:
        for name, layer in result.layers.items():
            layer_img = tonemap_aces(layer)
            layer_path = (target_dir / f"{stem}_{name}").with_suffix(".png")
            layer_img.save(layer_path)
            outputs[f"layer_{name}"] = layer_path

    return outputs


def _float_to_rgb16(image) -> Image.Image:
    max_value = 0.0
    for channel in image.channels:
        extrema = channel.getextrema()
        if extrema is not None:
            max_value = max(max_value, extrema[1])
    if max_value <= 0:
        max_value = 1.0
    scale = 65535.0 / max_value
    pixels = [channel.load() for channel in image.channels]
    data = bytearray()
    for y in range(image.height):
        for x in range(image.width):
            for idx in range(3):
                value = int(max(0.0, min(65535.0, round(pixels[idx][x, y] * scale))))
                data.append((value >> 8) & 0xFF)
                data.append(value & 0xFF)
    return Image.frombytes("RGB", (image.width, image.height), bytes(data), "raw", "RGB;16B")


__all__ = ["save_render"]
