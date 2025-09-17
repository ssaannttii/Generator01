"""High level rendering orchestrator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import random

from .config import SceneConfig
from .image import FloatImage
from .post import add_grain, apply_bloom, apply_chromatic_aberration, apply_vignette, tone_map_aces
from .sampling import downsample, generate_star_field, render_star_field
from .shapes import render_ui_layers


@dataclass
class RenderResult:
    image: FloatImage
    layers: Dict[str, FloatImage]

    def save(self, path: str) -> None:
        self.image.save_png(path)


def generate_star_chart(config: SceneConfig, *, seed: Optional[int] = None) -> RenderResult:
    rng = random.Random(seed if seed is not None else config.seed)

    stars = generate_star_field(config.stars, config.resolution, config.camera, rng)
    star_layer = render_star_field(stars, config.resolution)
    ui_core, ui_glow = render_ui_layers(config, config.resolution.supersampled())

    combined = star_layer.copy()
    combined.add_image(ui_core)
    combined.add_image(ui_glow)

    bloom = apply_bloom(
        combined,
        threshold=config.post.bloom.threshold,
        intensity=config.post.bloom.intensity,
        radius=config.post.bloom.radius,
    )
    aberrated = apply_chromatic_aberration(bloom, config.post.chromatic_aberration.k)
    vignetted = apply_vignette(aberrated, config.post.vignette)
    grained = add_grain(vignetted, config.post.grain, rng)
    final_linear = tone_map_aces(grained)

    ssaa = config.resolution.ssaa
    if ssaa > 1:
        star_layer = downsample(star_layer, ssaa)
        ui_core = downsample(ui_core, ssaa)
        ui_glow = downsample(ui_glow, ssaa)
        final_linear = downsample(final_linear, ssaa)

    final_linear.clamp(0.0, 1.0)

    layers = {
        "stars": star_layer,
        "ui_core": ui_core,
        "ui_glow": ui_glow,
        "final_linear": final_linear.copy(),
    }

    return RenderResult(image=final_linear, layers=layers)


__all__ = ["RenderResult", "generate_star_chart"]
