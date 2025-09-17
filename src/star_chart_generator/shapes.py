"""Drawing helpers for UI elements using the custom image buffer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

import math

from .camera import ProjectionParams
from .config import HUDReadout, RingTickConfig, SceneConfig
from .image import FloatImage, gaussian_blur
from .labels import LabelSpec, draw_label_layers, draw_text_line, layout_labels
from .utils import clamp, hex_to_rgb


@dataclass
class RingPoint:
    x: float
    y: float
    scale: float
    angle: float


_DEFAULT_HUD_READOUTS: Tuple[HUDReadout, ...] = (
    HUDReadout(text="NAV 214.37", position=0.18, alignment="start"),
    HUDReadout(text="ΔV 0.993C", position=0.52, alignment="center"),
    HUDReadout(text="SYNC 02:47:15", position=0.84, alignment="end"),
)


def _sample_ring_points(
    projection: ProjectionParams, radius: float, *, samples: int
) -> List[RingPoint]:
    points: List[RingPoint] = []
    for index in range(samples):
        angle = (index / samples) * math.tau
        x, y, depth = projection.project(radius, angle)
        scale = clamp(depth / projection.distance, 0.4, 2.2)
        points.append(RingPoint(x=x, y=y, scale=scale, angle=angle))
    return points


def _draw_polyline(
    image: FloatImage,
    points: Sequence[RingPoint],
    base_width: float,
    color: Tuple[float, float, float],
    intensity_scale: float,
) -> None:
    count = len(points)
    if count < 2:
        return
    for index, current in enumerate(points):
        nxt = points[(index + 1) % count]
        dx = nxt.x - current.x
        dy = nxt.y - current.y
        distance = max(1.0, math.hypot(dx, dy))
        steps = max(1, int(distance / max(1.0, base_width * 0.45)))
        for step in range(steps + 1):
            t = step / steps
            x = current.x + dx * t
            y = current.y + dy * t
            scale = current.scale * (1.0 - t) + nxt.scale * t
            width = max(0.55, base_width * scale)
            intensity = min(1.6, 0.75 + 0.35 * min(scale, 1.6)) * intensity_scale
            image.add_disc(x, y, width * 0.5, color, intensity)


def _draw_ring(
    core: FloatImage,
    glow: FloatImage,
    points: Sequence[RingPoint],
    base_width: float,
    color: Tuple[float, float, float],
    halo_color: Tuple[float, float, float],
    glow_strength: float,
) -> None:
    _draw_polyline(core, points, base_width, color, 1.0)
    halo_width = base_width * 1.35
    glow_intensity = clamp(glow_strength * 0.25, 0.05, 0.6)
    _draw_polyline(glow, points, halo_width, halo_color, glow_intensity)


def _iter_tick_spacings(config: RingTickConfig) -> Iterable[Tuple[float, float]]:
    spacings = sorted((value for value in config.every_deg if value > 0), reverse=True)
    if not spacings:
        return []
    low, high = config.length_px
    count = max(len(spacings) - 1, 1)
    for index, spacing in enumerate(spacings):
        factor = index / count
        length = high - (high - low) * factor
        yield spacing, length


def _draw_ticks(
    core: FloatImage,
    glow: FloatImage,
    projection: ProjectionParams,
    radius: float,
    base_width: float,
    color: Tuple[float, float, float],
    halo_color: Tuple[float, float, float],
    config: RingTickConfig,
    ssaa: int,
) -> None:
    for spacing, length in _iter_tick_spacings(config):
        length_px = max(2.0, length * ssaa)
        delta_radius = length_px * projection.pixel_to_radius
        offset_radius = radius + (base_width * 0.5) * projection.pixel_to_radius
        inner = offset_radius
        outer = offset_radius + delta_radius
        if spacing <= 0:
            continue
        count = max(1, int(round(360.0 / spacing)))
        for index in range(count):
            angle = math.radians(index * spacing)
            x0, y0, depth0 = projection.project(inner, angle)
            x1, y1, depth1 = projection.project(outer, angle)
            scale = clamp((depth0 + depth1) * 0.5 / projection.distance, 0.5, 1.8)
            width = max(1.0, base_width * 0.45 * config.weight * scale)
            intensity = config.alpha * (0.7 + 0.3 * min(scale, 1.4))
            core.add_line((x0, y0), (x1, y1), color, int(max(1, round(width))), intensity)
            glow.add_line(
                (x0, y0),
                (x1, y1),
                halo_color,
                int(max(1, round(width * 1.4))),
                intensity * 0.4,
            )


def _ellipse_parameters(
    projection: ProjectionParams, radius: float
) -> Tuple[float, float, float]:
    center_y, radius_x, radius_y = projection.ellipse_parameters(radius)
    if radius_x <= 0.0:
        radius_x = projection.base_radius * radius
    if radius_y <= 0.0:
        radius_y = max(radius_x * 0.12, 1.0)
    return center_y, radius_x, radius_y


def _build_label_specs(
    config: SceneConfig,
    projection: ProjectionParams,
    ssaa: int,
) -> List[LabelSpec]:
    label_specs: List[LabelSpec] = []
    label_scale = max(1.0, config.text.size_px / 18.0) * ssaa

    for index, ring in enumerate(config.rings):
        if not ring.label:
            continue
        label_radius = ring.r + ring.width * 0.5 + ring.label_offset
        center_y, radius_x, radius_y = _ellipse_parameters(projection, label_radius)
        angle = (
            math.radians(ring.label_angle_deg)
            if ring.label_angle_deg is not None
            else math.pi / 2.0
        )
        label_specs.append(
            LabelSpec(
                ring_index=index,
                text=ring.label,
                center=(projection.center_x, center_y),
                radius_x=radius_x,
                radius_y=radius_y,
                initial_angle=angle,
                tracking=config.text.tracking,
                scale=label_scale,
            )
        )

    for readout in config.readouts:
        ring_index = readout.placement.ring_index
        if ring_index < 0 or ring_index >= len(config.rings):
            continue
        ring = config.rings[ring_index]
        if readout.placement.radius is not None:
            label_radius = float(readout.placement.radius)
        else:
            label_radius = ring.r + readout.placement.radial_offset
        center_y, radius_x, radius_y = _ellipse_parameters(projection, label_radius)
        angle = math.radians(readout.placement.angle_deg)
        baseline = "linear" if readout.placement.kind == "linear" else "arc"
        label_specs.append(
            LabelSpec(
                ring_index=ring_index,
                text=readout.text,
                center=(projection.center_x, center_y),
                radius_x=radius_x,
                radius_y=radius_y,
                initial_angle=angle,
                tracking=config.text.tracking,
                scale=label_scale,
                alignment=readout.alignment,
                baseline=baseline,
            )
        )

    return label_specs


def _draw_hud(
    core: FloatImage,
    glow: FloatImage,
    projection: ProjectionParams,
    hud_config: Sequence[HUDReadout],
    text_color: Tuple[float, float, float],
    emissive: float,
    ssaa: int,
    tracking: float,
) -> None:
    band_height = max(24 * ssaa, int(ssaa * 1.0 * projection.height * 0.08))
    baseline_y = projection.height - band_height * 0.4
    line_color = hex_to_rgb("#4384CE")
    glow_color = hex_to_rgb("#295a92")
    line_width = max(1, int(2 * ssaa))
    core.add_line((0.0, baseline_y), (projection.width, baseline_y), line_color, line_width, 0.9)
    glow.add_line((0.0, baseline_y), (projection.width, baseline_y), line_color, line_width + 2, 0.35 * emissive)

    tick_spacing = max(48.0 * ssaa, projection.width / 20.0)
    major_length = band_height * 0.55
    minor_length = band_height * 0.32

    tick_count = int(math.ceil(projection.width / tick_spacing)) + 1
    for index in range(tick_count):
        x = index * tick_spacing
        length = major_length if index % 5 == 0 else minor_length
        x0, y0 = x, baseline_y
        x1, y1 = x, baseline_y + length
        width = max(1, int(ssaa * (1.2 if index % 5 == 0 else 0.8)))
        core.add_line((x0, y0), (x1, y1), line_color, width, 0.8)
        glow.add_line((x0, y0), (x1, y1), glow_color, width + 1, 0.25 * emissive)

    text_scale = max(1.0, (band_height / (7.0 * ssaa)) * 0.85)
    baseline_offset = baseline_y + major_length + 6.0 * ssaa
    glow_strength = 0.5 * emissive

    for readout in hud_config:
        x = clamp(readout.position, 0.0, 1.0) * projection.width
        draw_text_line(
            core,
            glow,
            readout.text,
            (x, baseline_offset),
            scale=text_scale,
            color=text_color,
            glow_color=line_color,
            emissive=glow_strength,
            alignment=readout.alignment,
            tracking=tracking,
        )


def render_ui_layers(
    config: SceneConfig,
    projection: ProjectionParams,
    ssaa: int,
) -> Tuple[FloatImage, FloatImage]:
    width, height = projection.width, projection.height
    core = FloatImage.new(width, height, 0.0)
    glow = FloatImage.new(width, height, 0.0)

    for index, ring in enumerate(config.rings):
        radius = max(1e-4, ring.r)
        base_width = max(1.0, ring.width * projection.base_radius)
        samples = max(240, int(360 * clamp(radius, 0.25, 1.0)))
        points = _sample_ring_points(projection, radius, samples=samples)
        color = hex_to_rgb(ring.color)
        halo_color = hex_to_rgb(ring.halo_color or ring.color)
        _draw_ring(core, glow, points, base_width, color, halo_color, ring.glow)

        if ring.tick or ring.ticks_every_deg:
            if ring.tick is not None:
                tick_config = RingTickConfig(
                    every_deg=tuple(ring.tick.every_deg),
                    length_px=ring.tick.length_px,
                    alpha=ring.tick.alpha,
                    weight=ring.tick.weight,
                )
            else:
                tick_config = RingTickConfig(
                    every_deg=(float(ring.ticks_every_deg),),
                    length_px=(6.0, 12.0),
                    alpha=0.85,
                    weight=1.0,
                )
            _draw_ticks(
                core,
                glow,
                projection,
                radius,
                base_width,
                color,
                halo_color,
                tick_config,
                ssaa,
            )

    label_specs = _build_label_specs(config, projection, ssaa)
    if label_specs:
        placements = layout_labels(label_specs)
        label_core, label_glow = draw_label_layers((width, height), placements, config.text)
        core.add_image(label_core)
        glow.add_image(gaussian_blur(label_glow, 2.0 * ssaa))

    if config.hud.use_default_readouts and not config.hud.readouts:
        hud_readouts: Sequence[HUDReadout] = _DEFAULT_HUD_READOUTS
    else:
        hud_readouts = config.hud.readouts

    if config.hud.enabled and hud_readouts:
        text_color = hex_to_rgb(config.text.color)
        _draw_hud(
            core,
            glow,
            projection,
            hud_readouts,
            text_color,
            config.hud.emissive,
            ssaa,
            config.text.tracking,
        )

    glow = gaussian_blur(glow, 3.0 * ssaa)
    return core, glow


__all__ = ["render_ui_layers"]
