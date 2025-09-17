"""Drawing helpers for UI elements using the custom image buffer."""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import math

from .config import SceneConfig
from .image import FloatImage, gaussian_blur
from .labels import LabelSpec, draw_label_layers, layout_labels
from .utils import hex_to_rgb


def _draw_arc(image: FloatImage, center: Tuple[float, float], rx: float, ry: float, start_deg: float, end_deg: float, width: float, color: Tuple[float, float, float], intensity: float) -> None:
    steps = max(12, int(abs(end_deg - start_deg) * max(rx, ry) * 0.05))
    for i in range(steps + 1):
        t = start_deg + (end_deg - start_deg) * (i / max(steps, 1))
        angle = math.radians(t)
        x = center[0] + rx * math.cos(angle)
        y = center[1] + ry * math.sin(angle)
        image.add_disc(x, y, max(0.5, width / 2.0), color, intensity)


def _draw_dashed_ring(image: FloatImage, center: Tuple[float, float], rx: float, ry: float, width: float, dash: Tuple[float, float], color: Tuple[float, float, float], intensity: float) -> None:
    dash_len, gap_len = dash
    angle = 0.0
    while angle < 360.0:
        start = angle
        end = min(angle + dash_len, 360.0)
        _draw_arc(image, center, rx, ry, start, end, width, color, intensity)
        angle += dash_len + gap_len


def _draw_ticks(image: FloatImage, center: Tuple[float, float], rx: float, ry: float, tick_spacing: float, tick_length: float, color: Tuple[float, float, float], width: float) -> None:
    count = max(1, int(360.0 / tick_spacing))
    cx, cy = center
    for i in range(count):
        angle = math.radians(i * tick_spacing)
        x_inner = cx + rx * math.cos(angle)
        y_inner = cy + ry * math.sin(angle)
        x_outer = cx + (rx + tick_length) * math.cos(angle)
        y_outer = cy + (ry + tick_length) * math.sin(angle)
        image.add_line((x_inner, y_inner), (x_outer, y_outer), color, int(max(1, width)), 1.0)


def render_ui_layers(config: SceneConfig, resolution: Tuple[int, int]) -> Tuple[FloatImage, FloatImage]:
    width, height = resolution
    center = (width / 2.0, height / 2.0)
    ellipse_ratio = config.camera.ellipse_ratio
    base_radius = min(width, height) * 0.5 * 0.92

    core = FloatImage.new(width, height, 0.0)
    glow = FloatImage.new(width, height, 0.0)

    label_specs: List[LabelSpec] = []
    label_scale = max(1.0, config.text.size_px / (7 * 2.0))

    for index, ring in enumerate(config.rings):
        rx = base_radius * ring.r
        ry = rx * ellipse_ratio
        stroke = max(1.0, ring.width * base_radius)
        tick_length = max(stroke * 1.5, base_radius * 0.01)

        color = hex_to_rgb(ring.color)
        halo_color = hex_to_rgb(ring.halo_color or ring.color)

        if ring.dash:
            dash = (float(ring.dash[0]), float(ring.dash[1] if len(ring.dash) > 1 else ring.dash[0]))
            _draw_dashed_ring(core, center, rx, ry, stroke, dash, color, 1.0)
            _draw_dashed_ring(glow, center, rx, ry, stroke * 1.8, dash, halo_color, 0.35 * ring.glow)
        else:
            _draw_arc(core, center, rx, ry, 0.0, 360.0, stroke, color, 1.0)
            _draw_arc(glow, center, rx, ry, 0.0, 360.0, stroke * 1.8, halo_color, 0.35 * ring.glow)

        if ring.ticks_every_deg:
            _draw_ticks(core, center, rx, ry, ring.ticks_every_deg, tick_length, color, stroke * 0.5)

        if ring.label:
            label_radius = ring.r + ring.width * 0.5 + ring.label_offset
            label_rx = base_radius * label_radius
            label_ry = label_rx * ellipse_ratio
            angle = math.radians(ring.label_angle_deg) if ring.label_angle_deg is not None else math.pi / 2
            label_specs.append(
                LabelSpec(
                    ring_index=index,
                    text=ring.label,
                    center=center,
                    radius_x=label_rx,
                    radius_y=label_ry,
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
            label_radius = readout.placement.radius
        else:
            label_radius = ring.r + readout.placement.radial_offset
        label_rx = base_radius * label_radius
        label_ry = label_rx * ellipse_ratio
        angle = math.radians(readout.placement.angle_deg)
        baseline = "linear" if readout.placement.kind == "linear" else "arc"
        label_specs.append(
            LabelSpec(
                ring_index=ring_index,
                text=readout.text,
                center=center,
                radius_x=label_rx,
                radius_y=label_ry,
                initial_angle=angle,
                tracking=config.text.tracking,
                scale=label_scale,
                alignment=readout.alignment,
                baseline=baseline,
            )
        )

    if label_specs:
        placements = layout_labels(label_specs)
        label_core, label_glow = draw_label_layers((width, height), placements, config.text)
        core.add_image(label_core)
        glow.add_image(gaussian_blur(label_glow, 2.0))

    glow = gaussian_blur(glow, 3.0)
    return core, glow


__all__ = ["render_ui_layers"]
