"""Configuration models and loader for the star chart generator."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Sequence, Tuple

from .yaml_loader import load_yaml

Color = Tuple[float, float, float]


@dataclass
class Resolution:
    width: int
    height: int
    ssaa: int = 1


@dataclass
class CameraSettings:
    tilt_deg: float = 30.0
    fov_deg: float = 35.0


@dataclass
class RingTickSpec:
    every_deg: float
    length: float = 0.02
    thickness: float = 0.0015
    color: Color = (1.0, 1.0, 1.0)
    intensity: float = 1.0
    phase_deg: float = 0.0


@dataclass
class RingLabelSpec:
    text: str
    sweep_deg: float = 60.0
    offset_deg: float = 0.0
    side: str = "outer"
    font_size: float = 28.0
    tracking: float = 0.0
    color: Color = (1.0, 1.0, 1.0)
    intensity: float = 1.0


@dataclass
class RingSpec:
    radius: float
    width: float
    core_color: Color
    core_intensity: float = 1.0
    glow_color: Color | None = None
    glow_intensity: float = 1.0
    glow_radius: float = 0.012
    dash: Sequence[float] | None = None
    ticks: RingTickSpec | None = None
    labels: List[RingLabelSpec] = field(default_factory=list)


@dataclass
class StarCoreSpec:
    count: int
    sigma: float
    alpha: float


@dataclass
class StarHaloSpec:
    count: int
    min_r: float
    max_r: float
    min_separation: float = 0.0


@dataclass
class StarSettings:
    core: StarCoreSpec
    halo: StarHaloSpec
    brightness_power: float = 1.8
    size_min: float = 0.002
    size_max: float = 0.009
    color_cool: Color = (0.117, 0.564, 1.0)
    color_warm: Color = (1.0, 0.325, 0.184)


@dataclass
class BloomSettings:
    threshold: float = 1.1
    intensity: float = 0.35
    radii: Sequence[float] = (2.5, 5.0, 10.0, 20.0)


@dataclass
class ChromaticAberrationSettings:
    strength: float = 0.002


@dataclass
class GrainSettings:
    strength: float = 0.015


@dataclass
class PostProcessingSettings:
    bloom: BloomSettings = field(default_factory=BloomSettings)
    chromatic_aberration: ChromaticAberrationSettings = field(default_factory=ChromaticAberrationSettings)
    vignette: float = 0.12
    grain: GrainSettings = field(default_factory=GrainSettings)


@dataclass
class FreeLabelSpec:
    text: str
    position_radius: float
    angle_deg: float
    font_size: float = 28.0
    tracking: float = 0.0
    color: Color = (1.0, 1.0, 1.0)
    intensity: float = 1.0


@dataclass
class TextSettings:
    font: str
    tabular_digits: bool = True


@dataclass
class GeneratorConfig:
    seed: int
    resolution: Resolution
    camera: CameraSettings
    rings: List[RingSpec]
    stars: StarSettings
    text: TextSettings
    post: PostProcessingSettings
    free_labels: List[FreeLabelSpec] = field(default_factory=list)


def load_config(path: Path | str) -> GeneratorConfig:
    raw = load_yaml(path)
    return parse_config(raw)


def parse_config(data: dict[str, Any]) -> GeneratorConfig:
    seed = int(data.get("seed", 0))
    resolution = _parse_resolution(data.get("resolution", {}))
    camera = _parse_camera(data.get("camera", {}))
    rings = [_parse_ring(entry) for entry in data.get("rings", [])]
    stars = _parse_stars(data.get("stars", {}))
    text = _parse_text(data.get("text", {}))
    post = _parse_post(data.get("post", {}))
    free_labels = [_parse_free_label(item) for item in data.get("labels", [])]
    return GeneratorConfig(
        seed=seed,
        resolution=resolution,
        camera=camera,
        rings=rings,
        stars=stars,
        text=text,
        post=post,
        free_labels=free_labels,
    )


def _parse_resolution(data: dict[str, Any]) -> Resolution:
    return Resolution(
        width=int(data.get("width", 4096)),
        height=int(data.get("height", 4096)),
        ssaa=int(data.get("ssaa", 1)),
    )


def _parse_camera(data: dict[str, Any]) -> CameraSettings:
    return CameraSettings(
        tilt_deg=float(data.get("tilt_deg", 30.0)),
        fov_deg=float(data.get("fov_deg", 35.0)),
    )


def _parse_ring(data: dict[str, Any]) -> RingSpec:
    ticks = data.get("ticks")
    labels = data.get("labels", [])
    return RingSpec(
        radius=float(data["radius"]),
        width=float(data["width"]),
        core_color=_parse_color(data.get("color") or data.get("core_color")),
        core_intensity=float(data.get("core_intensity", 1.2)),
        glow_color=_parse_optional_color(data.get("glow_color")),
        glow_intensity=float(data.get("glow_intensity", data.get("core_intensity", 1.2))),
        glow_radius=float(data.get("glow_radius", 0.012)),
        dash=[float(v) for v in data.get("dash", [])] or None,
        ticks=_parse_tick_spec(ticks) if ticks else None,
        labels=[_parse_ring_label(entry) for entry in labels],
    )


def _parse_tick_spec(data: dict[str, Any]) -> RingTickSpec:
    return RingTickSpec(
        every_deg=float(data.get("every_deg", 10.0)),
        length=float(data.get("length", 0.02)),
        thickness=float(data.get("thickness", 0.0015)),
        color=_parse_color(data.get("color", "#ffffff")),
        intensity=float(data.get("intensity", 1.0)),
        phase_deg=float(data.get("phase_deg", 0.0)),
    )


def _parse_ring_label(data: dict[str, Any]) -> RingLabelSpec:
    return RingLabelSpec(
        text=str(data.get("text", "")),
        sweep_deg=float(data.get("sweep_deg", 50.0)),
        offset_deg=float(data.get("offset_deg", 0.0)),
        side=str(data.get("side", "outer")),
        font_size=float(data.get("font_size", 32.0)),
        tracking=float(data.get("tracking", 0.0)),
        color=_parse_color(data.get("color", "#ffffff")),
        intensity=float(data.get("intensity", 1.0)),
    )


def _parse_stars(data: dict[str, Any]) -> StarSettings:
    core_data = data.get("core") or {}
    halo_data = data.get("halo") or {}
    return StarSettings(
        core=StarCoreSpec(
            count=int(core_data.get("count", 20000)),
            sigma=float(core_data.get("sigma", 0.2)),
            alpha=float(core_data.get("alpha", 3.2)),
        ),
        halo=StarHaloSpec(
            count=int(halo_data.get("count", 6000)),
            min_r=float(halo_data.get("min_r", 0.35)),
            max_r=float(halo_data.get("max_r", 1.0)),
            min_separation=float(halo_data.get("min_separation", 0.005)),
        ),
        brightness_power=float(data.get("brightness_power", 1.8)),
        size_min=float(data.get("size_min", 0.002)),
        size_max=float(data.get("size_max", 0.009)),
        color_cool=_parse_color(data.get("color_cool", "#1E90FF")),
        color_warm=_parse_color(data.get("color_warm", "#FF6A00")),
    )


def _parse_text(data: dict[str, Any]) -> TextSettings:
    font = str(data.get("font", "assets/fonts/Orbitron-Regular.ttf"))
    return TextSettings(
        font=font,
        tabular_digits=bool(data.get("tabular_digits", True)),
    )


def _parse_post(data: dict[str, Any]) -> PostProcessingSettings:
    bloom_data = data.get("bloom", {})
    ca_data = data.get("chromatic_aberration", {})
    return PostProcessingSettings(
        bloom=BloomSettings(
            threshold=float(bloom_data.get("threshold", 1.1)),
            intensity=float(bloom_data.get("intensity", 0.32)),
            radii=tuple(float(v) for v in bloom_data.get("radii", (2.5, 5.0, 10.0, 20.0))),
        ),
        chromatic_aberration=ChromaticAberrationSettings(
            strength=float(ca_data.get("k", ca_data.get("strength", 0.002))),
        ),
        vignette=float(data.get("vignette", 0.12)),
        grain=GrainSettings(strength=float((data.get("grain") or {}).get("strength", 0.015))),
    )


def _parse_free_label(data: dict[str, Any]) -> FreeLabelSpec:
    return FreeLabelSpec(
        text=str(data.get("text", "")),
        position_radius=float(data.get("radius", data.get("position_radius", 0.6))),
        angle_deg=float(data.get("angle_deg", 0.0)),
        font_size=float(data.get("font_size", 30.0)),
        tracking=float(data.get("tracking", 0.0)),
        color=_parse_color(data.get("color", "#ffffff")),
        intensity=float(data.get("intensity", 1.0)),
    )


def _parse_optional_color(value: Any) -> Color | None:
    if value is None:
        return None
    return _parse_color(value)


def _parse_color(value: Any) -> Color:
    if isinstance(value, (list, tuple)):
        values = [float(v) for v in value]
        if len(values) == 3:
            return tuple(values)  # type: ignore[return-value]
    if isinstance(value, dict):
        return (
            float(value.get("r", value.get("x", 1.0))),
            float(value.get("g", value.get("y", 1.0))),
            float(value.get("b", value.get("z", 1.0))),
        )
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("#"):
            value = value[1:]
            if len(value) == 6:
                r = int(value[0:2], 16) / 255.0
                g = int(value[2:4], 16) / 255.0
                b = int(value[4:6], 16) / 255.0
                return (r, g, b)
            if len(value) == 3:
                r = int(value[0], 16) / 15.0
                g = int(value[1], 16) / 15.0
                b = int(value[2], 16) / 15.0
                return (r, g, b)
    raise ValueError(f"Unsupported color value: {value!r}")


__all__ = [
    "GeneratorConfig",
    "Resolution",
    "CameraSettings",
    "RingSpec",
    "RingTickSpec",
    "RingLabelSpec",
    "StarSettings",
    "PostProcessingSettings",
    "TextSettings",
    "FreeLabelSpec",
    "load_config",
    "parse_config",
]
