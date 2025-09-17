"""High level rendering orchestrator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import random

from .camera import create_projection
from .config import SceneConfig
from .image import FloatImage
from .post import (
    add_grain,
    apply_anamorphic_streak,
    apply_bloom,
    apply_chromatic_aberration,
    apply_vignette,
    tone_map_aces,
)
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
    ssaa = max(1, config.resolution.ssaa)

    projection = create_projection(config.resolution, config.camera, config.rings)

    stars = generate_star_field(config.stars, projection, rng, ssaa=ssaa)
    star_layer = render_star_field(stars, projection)
    ui_core, ui_glow = render_ui_layers(config, projection, ssaa=ssaa)

    combined = star_layer.copy()
    combined.add_image(ui_core)
    combined.add_image(ui_glow)

    bloom, bright = apply_bloom(
        combined,
        threshold=config.post.bloom.threshold,
        sigmas=tuple(sigma * ssaa for sigma in config.post.bloom.sigmas),
        intensities=config.post.bloom.intensities,
    )

    if config.post.anamorphic.enabled:
        bloom = apply_anamorphic_streak(
            bloom,
            bright,
            length_px=config.post.anamorphic.length_px * ssaa,
            intensity=config.post.anamorphic.intensity,
        )

    aberrated = apply_chromatic_aberration(
        bloom,
        pixels=config.post.chromatic_aberration.pixels / ssaa,
        center=config.post.chromatic_aberration.center,
    )
    vignetted = apply_vignette(aberrated, config.post.vignette)
    grained = add_grain(vignetted, config.post.grain * ssaa, rng)
    final_linear = tone_map_aces(grained, gamma=config.post.gamma)

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
