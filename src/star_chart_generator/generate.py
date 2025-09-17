"""High-level star chart generation pipeline (Pillow implementation)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .config import GeneratorConfig, RingLabelSpec, RingSpec
from .imageops import FloatImage, merge_layers
from .post import apply_postprocessing, tonemap_aces
from .sampling import sample_annulus, sample_powerlaw_brightness, sample_sersic


@dataclass
class RenderResult:
    linear: FloatImage
    tonemapped: Image.Image
    layers: Dict[str, FloatImage]


def generate_chart(config: GeneratorConfig) -> RenderResult:
    renderer = _StarChartRenderer(config)
    return renderer.render()


class _StarChartRenderer:
    def __init__(self, config: GeneratorConfig) -> None:
        self.cfg = config
        self.ssaa = max(1, config.resolution.ssaa)
        self.width = int(config.resolution.width * self.ssaa)
        self.height = int(config.resolution.height * self.ssaa)
        self.center_x = (self.width - 1) * 0.5
        self.center_y = (self.height - 1) * 0.5
        self.radius_px = min(self.width, self.height) * 0.5
        self.rng = random.Random(config.seed)
        self.layers: Dict[str, FloatImage] = {
            "stars": FloatImage.blank(self.width, self.height),
            "ui_core": FloatImage.blank(self.width, self.height),
            "ui_glow": FloatImage.blank(self.width, self.height),
            "labels": FloatImage.blank(self.width, self.height),
        }
        self.font_path = Path(self.cfg.text.font)
        self._font_cache: Dict[int, ImageFont.ImageFont] = {}
        self._glyph_cache: Dict[Tuple[int, str], Image.Image] = {}

    def render(self) -> RenderResult:
        self._render_stars()
        self._render_rings()
        self._render_free_labels()
        combined = merge_layers(list(self.layers.values()))
        post_processed = apply_postprocessing(combined, self.cfg.post, self.rng)
        layers_final: Dict[str, FloatImage] = {}
        if self.ssaa > 1:
            for name, layer in self.layers.items():
                layers_final[name] = layer.resize(self.cfg.resolution.width, self.cfg.resolution.height)
            post_processed = post_processed.resize(self.cfg.resolution.width, self.cfg.resolution.height)
        else:
            layers_final = self.layers
        tonemapped = tonemap_aces(post_processed)
        return RenderResult(linear=post_processed, tonemapped=tonemapped, layers=layers_final)

    # Rendering helpers -------------------------------------------------

    def _render_stars(self) -> None:
        cfg = self.cfg.stars
        core_radii = sample_sersic(cfg.core.count, cfg.core.sigma, cfg.core.alpha, self.rng)
        core_angles = [self.rng.uniform(0.0, 2 * math.pi) for _ in range(cfg.core.count)]
        halo_radii, halo_angles = sample_annulus(
            cfg.halo.count,
            cfg.halo.min_r,
            cfg.halo.max_r,
            self.rng,
            cfg.halo.min_separation,
        )
        radii = core_radii + halo_radii
        angles = core_angles + halo_angles
        brightness = sample_powerlaw_brightness(len(radii), cfg.brightness_power, self.rng)
        size_levels = _linspace(cfg.size_min, cfg.size_max, 4)
        colors_cool = _hex_to_rgb(cfg.color_cool)
        colors_warm = _hex_to_rgb(cfg.color_warm)
        for radius, angle, weight in zip(radii, angles, brightness):
            size = size_levels[int(min(len(size_levels) - 1, weight * (len(size_levels) - 1)))]
            color = _lerp_color(colors_cool, colors_warm, min(max(weight, 0.0), 1.0))
            intensity = 0.6 + 1.4 * weight
            self._draw_star(radius, angle, size, color, intensity)

    def _draw_star(self, radius: float, angle: float, size_norm: float, color: Tuple[float, float, float], intensity: float) -> None:
        px = self.center_x + math.cos(angle) * radius * self.radius_px
        py = self.center_y + math.sin(angle) * radius * self.radius_px
        sigma_px = max(1.5, size_norm * self.radius_px)
        patch = _GaussianKernelCache.get_kernel(sigma_px)
        half = patch.width // 2
        x0 = int(round(px)) - half
        y0 = int(round(py)) - half
        x1 = x0 + patch.width
        y1 = y0 + patch.height
        clip_x0 = max(0, x0)
        clip_y0 = max(0, y0)
        clip_x1 = min(self.width, x1)
        clip_y1 = min(self.height, y1)
        if clip_x0 >= clip_x1 or clip_y0 >= clip_y1:
            return
        if clip_x0 != x0 or clip_y0 != y0 or clip_x1 != x1 or clip_y1 != y1:
            patch_left = clip_x0 - x0
            patch_top = clip_y0 - y0
            patch_right = patch_left + (clip_x1 - clip_x0)
            patch_bottom = patch_top + (clip_y1 - clip_y0)
            patch_cropped = patch.crop((patch_left, patch_top, patch_right, patch_bottom))
        else:
            patch_cropped = patch
        self.layers["stars"].add_patch(
            patch_cropped,
            color,
            intensity,
            (clip_x0, clip_y0, clip_x0 + patch_cropped.width, clip_y0 + patch_cropped.height),
        )

    def _render_rings(self) -> None:
        for ring in self.cfg.rings:
            self._draw_ring(ring)
            for label in ring.labels:
                self._draw_ring_label(ring, label)

    def _draw_ring(self, ring: RingSpec) -> None:
        mask = Image.new("L", (self.width, self.height), 0)
        draw = ImageDraw.Draw(mask)
        radius_px = ring.radius * self.radius_px
        width_px = max(1, int(round(ring.width * self.radius_px)))
        bbox = [
            self.center_x - radius_px,
            self.center_y - radius_px,
            self.center_x + radius_px,
            self.center_y + radius_px,
        ]
        if ring.dash:
            pattern = list(ring.dash)
            if len(pattern) % 2 == 1:
                pattern.append(pattern[-1])
            angle = 0.0
            idx = 0
            while angle < 360.0:
                on = pattern[idx % len(pattern)]
                off = pattern[(idx + 1) % len(pattern)]
                draw.arc(bbox, start=angle, end=min(360.0, angle + on), fill=255, width=width_px)
                angle += on + off
                idx += 2
        else:
            draw.arc(bbox, start=0.0, end=360.0, fill=255, width=width_px)
        mask_f = mask.convert("F")
        self.layers["ui_core"].add_mask(mask_f, _hex_to_rgb(ring.core_color), ring.core_intensity)
        glow_color = _hex_to_rgb(ring.glow_color if ring.glow_color is not None else ring.core_color)
        blur_radius = max(1.0, ring.glow_radius * self.radius_px)
        glow_mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius)).convert("F")
        self.layers["ui_glow"].add_mask(glow_mask, glow_color, ring.glow_intensity)
        if ring.ticks:
            self._draw_ring_ticks(ring, radius_px)

    def _draw_ring_ticks(self, ring: RingSpec, radius_px: float) -> None:
        tick = ring.ticks
        if not tick:
            return
        mask = Image.new("L", (self.width, self.height), 0)
        draw = ImageDraw.Draw(mask)
        tick_len = tick.length * self.radius_px
        tick_width = max(1, int(round(tick.thickness * self.radius_px)))
        angle = tick.phase_deg
        while angle < 360.0:
            angle_rad = math.radians(angle)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            inner = radius_px - tick_len * 0.4
            outer = radius_px + tick_len * 0.6
            x0 = self.center_x + cos_a * inner
            y0 = self.center_y + sin_a * inner
            x1 = self.center_x + cos_a * outer
            y1 = self.center_y + sin_a * outer
            draw.line((x0, y0, x1, y1), fill=255, width=tick_width)
            angle += tick.every_deg
        mask_f = mask.convert("F")
        tick_color = _hex_to_rgb(tick.color)
        self.layers["ui_core"].add_mask(mask_f, tick_color, tick.intensity)
        glow = mask.filter(ImageFilter.GaussianBlur(radius=max(1.0, ring.glow_radius * self.radius_px * 0.75))).convert("F")
        self.layers["ui_glow"].add_mask(glow, tick_color, tick.intensity)

    def _draw_ring_label(self, ring: RingSpec, label: RingLabelSpec) -> None:
        font_size = max(8, int(label.font_size * self.ssaa))
        font = self._get_font(font_size)
        advances = [_glyph_advance(font, char) for char in label.text]
        if not advances:
            return
        tracking = label.tracking * self.ssaa
        total_length = sum(advances) + tracking * (len(advances) - 1)
        radius_px = ring.radius * self.radius_px
        path_radius = radius_px + (font_size * 0.55 if label.side == "outer" else -font_size * 0.55)
        arc_needed = total_length / max(path_radius, 1e-6)
        start_angle = math.radians(label.offset_deg) - arc_needed * 0.5
        mask = Image.new("L", (self.width, self.height), 0)
        cursor = 0.0
        for advance, char in zip(advances, label.text):
            center_offset = cursor + advance * 0.5
            angle = start_angle + center_offset / max(path_radius, 1e-6)
            rotation = math.degrees(angle) - 90.0
            if label.side == "inner":
                rotation += 180.0
            x = self.center_x + math.cos(angle) * path_radius
            y = self.center_y + math.sin(angle) * path_radius
            glyph = self._get_glyph_image(font, char)
            rotated = glyph.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=True)
            pos = (int(round(x - rotated.width * 0.5)), int(round(y - rotated.height * 0.5)))
            mask.paste(rotated, pos, rotated)
            cursor += advance + tracking
        mask_f = mask.convert("F")
        color = _hex_to_rgb(label.color)
        self.layers["labels"].add_mask(mask_f, color, label.intensity)
        glow = mask.filter(ImageFilter.GaussianBlur(radius=max(1.0, font_size * 0.35))).convert("F")
        self.layers["ui_glow"].add_mask(glow, color, label.intensity * 0.6)

    def _draw_free_labels(self) -> None:
        for label in self.cfg.free_labels:
            font_size = max(8, int(label.font_size * self.ssaa))
            font = self._get_font(font_size)
            advances = [_glyph_advance(font, char) for char in label.text]
            if not advances:
                continue
            tracking = label.tracking * self.ssaa
            total_length = sum(advances) + tracking * (len(advances) - 1)
            angle = math.radians(label.angle_deg)
            normal = (math.cos(angle), math.sin(angle))
            tangent = (-normal[1], normal[0])
            radius = label.position_radius * self.radius_px
            origin = (self.center_x + normal[0] * radius, self.center_y + normal[1] * radius)
            baseline_offset = (normal[0] * font_size * 0.35, normal[1] * font_size * 0.35)
            start_offset = -0.5 * total_length
            cursor = 0.0
            rotation = math.degrees(math.atan2(tangent[1], tangent[0]))
            mask = Image.new("L", (self.width, self.height), 0)
            for advance, char in zip(advances, label.text):
                glyph = self._get_glyph_image(font, char)
                offset = start_offset + cursor + advance * 0.5
                position = (
                    origin[0] + tangent[0] * offset + baseline_offset[0],
                    origin[1] + tangent[1] * offset + baseline_offset[1],
                )
                rotated = glyph.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=True)
                pos = (int(round(position[0] - rotated.width * 0.5)), int(round(position[1] - rotated.height * 0.5)))
                mask.paste(rotated, pos, rotated)
                cursor += advance + tracking
            mask_f = mask.convert("F")
            color = _hex_to_rgb(label.color)
            self.layers["labels"].add_mask(mask_f, color, label.intensity)
            glow = mask.filter(ImageFilter.GaussianBlur(radius=max(1.0, font_size * 0.35))).convert("F")
            self.layers["ui_glow"].add_mask(glow, color, label.intensity * 0.6)

    def _get_font(self, size: int) -> ImageFont.ImageFont:
        font = self._font_cache.get(size)
        if font is not None:
            return font
        try:
            layout = getattr(ImageFont, "LAYOUT_RAQM", getattr(ImageFont, "LAYOUT_BASIC", 0))
            font = ImageFont.truetype(str(self.font_path), size=size, layout_engine=layout)
        except OSError:
            font = ImageFont.load_default()
        self._font_cache[size] = font
        return font

    def _get_glyph_image(self, font: ImageFont.ImageFont, char: str) -> Image.Image:
        key = (id(font), char)
        cached = self._glyph_cache.get(key)
        if cached is not None:
            return cached
        if hasattr(font, "getbbox"):
            bbox = font.getbbox(char)
            width = max(1, bbox[2] - bbox[0])
            height = max(1, bbox[3] - bbox[1])
            offset = (-bbox[0], -bbox[1])
        else:
            mask = font.getmask(char)
            width, height = mask.size
            offset = (0, 0)
        glyph_img = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(glyph_img)
        draw.text(offset, char, font=font, fill=255)
        self._glyph_cache[key] = glyph_img
        return glyph_img


def _glyph_advance(font: ImageFont.ImageFont, char: str) -> float:
    if hasattr(font, "getlength"):
        return max(1.0, font.getlength(char))
    return max(1.0, font.getsize(char)[0])


class _GaussianKernelCache:
    _cache: Dict[int, Image.Image] = {}

    @classmethod
    def get_kernel(cls, sigma_px: float) -> Image.Image:
        sigma_px = max(0.5, sigma_px)
        key = int(round(sigma_px * 64))
        if key in cls._cache:
            return cls._cache[key]
        radius = int(max(2, math.ceil(sigma_px * 3)))
        size = radius * 2 + 1
        data: List[float] = []
        for y in range(size):
            for x in range(size):
                dx = x - radius
                dy = y - radius
                value = math.exp(-(dx * dx + dy * dy) / (2.0 * sigma_px * sigma_px))
                data.append(value)
        patch = Image.new("F", (size, size))
        patch.putdata(data)
        cls._cache[key] = patch
        return patch


def _linspace(start: float, end: float, count: int) -> List[float]:
    if count <= 1:
        return [start]
    step = (end - start) / (count - 1)
    return [start + step * i for i in range(count)]


def _lerp_color(a: Tuple[float, float, float], b: Tuple[float, float, float], t: float) -> Tuple[float, float, float]:
    return (
        a[0] * (1.0 - t) + b[0] * t,
        a[1] * (1.0 - t) + b[1] * t,
        a[2] * (1.0 - t) + b[2] * t,
    )


def _hex_to_rgb(value: Tuple[float, float, float] | str) -> Tuple[float, float, float]:
    if isinstance(value, tuple):
        return value
    value = value.strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) == 6:
        return (int(value[0:2], 16) / 255.0, int(value[2:4], 16) / 255.0, int(value[4:6], 16) / 255.0)
    if len(value) == 3:
        return (int(value[0], 16) / 15.0, int(value[1], 16) / 15.0, int(value[2], 16) / 15.0)
    raise ValueError(f"Invalid color value: {value}")


__all__ = ["generate_chart", "RenderResult"]
