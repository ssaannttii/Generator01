"""Perspective projection helpers shared across rendering passes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

import math

from .config import Camera, Resolution, RingConfig


@dataclass(frozen=True)
class ProjectionParams:
    """Pre-computed camera parameters used for projecting ring geometry."""

    width: int
    height: int
    center_x: float
    center_y: float
    base_radius: float
    focal_length: float
    distance: float
    unit_scale: float
    pixel_to_radius: float
    pitch: float

    def project(self, radius: float, angle: float) -> Tuple[float, float, float]:
        """Project a point on a ring with ``radius`` and ``angle`` in radians."""

        radius = max(0.0, radius)
        x_world = math.cos(angle) * radius * self.unit_scale
        y_world = math.sin(angle) * radius * self.unit_scale
        y_prime = y_world * math.cos(self.pitch)
        z_prime = -y_world * math.sin(self.pitch)
        z_camera = self.distance - z_prime
        if z_camera <= 1e-5:
            z_camera = 1e-5
        screen_x = self.center_x + (self.focal_length * x_world) / z_camera
        screen_y = self.center_y + (self.focal_length * y_prime) / z_camera
        return screen_x, screen_y, z_camera

    def ellipse_parameters(self, radius: float) -> Tuple[float, float, float]:
        """Return the vertical center and radii of the projected ellipse."""

        if radius <= 0:
            return self.center_y, 0.0, 0.0
        side_x, side_y, _ = self.project(radius, 0.0)
        near_x, near_y, _ = self.project(radius, math.pi / 2.0)
        far_x, far_y, _ = self.project(radius, -math.pi / 2.0)
        center_y = (near_y + far_y) * 0.5
        radius_x = abs(side_x - self.center_x)
        radius_y = abs(near_y - center_y)
        return center_y, radius_x, radius_y


def create_projection(
    resolution: Resolution, camera: Camera, rings: Sequence[RingConfig]
) -> ProjectionParams:
    """Build :class:`ProjectionParams` for the current scene configuration."""

    width, height = resolution.supersampled()
    center_x = width / 2.0
    center_y = height / 2.0
    base_radius = min(width, height) * 0.5 * 0.92

    fov = max(1e-3, math.radians(camera.fov_deg))
    focal_length = (height / 2.0) / math.tan(fov / 2.0)

    distance = max(camera.z_near + 1e-3, camera.z_far)

    max_radius = 0.0
    for ring in rings:
        radius = ring.r + max(ring.width * 0.75, 0.0)
        if radius > max_radius:
            max_radius = radius
    if max_radius <= 1e-6:
        max_radius = 1.0

    unit_scale = base_radius * distance / (focal_length * max_radius)
    pixel_to_radius = distance / (focal_length * unit_scale)

    return ProjectionParams(
        width=width,
        height=height,
        center_x=center_x,
        center_y=center_y,
        base_radius=base_radius,
        focal_length=focal_length,
        distance=distance,
        unit_scale=unit_scale,
        pixel_to_radius=pixel_to_radius,
        pitch=math.radians(camera.pitch_deg),
    )


__all__ = ["ProjectionParams", "create_projection"]
