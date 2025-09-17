"""Configuration structures for the star chart generator."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import ast
import math

try:  # pragma: no cover - optional dependency
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback to pure python parser
    yaml = None


@dataclass(frozen=True)
class Resolution:
    """Output resolution configuration."""

    width: int
    height: int
    ssaa: int = 1

    def supersampled(self) -> tuple[int, int]:
        """Return the supersampled resolution (width, height)."""
        return self.width * self.ssaa, self.height * self.ssaa


@dataclass(frozen=True)
class Camera:
    """Camera orientation and projection settings."""

    pitch_deg: float = 83.0
    yaw_deg: float = 0.0
    fov_deg: float = 35.0
    z_near: float = 0.1
    z_far: float = 6.0

    @property
    def tilt_deg(self) -> float:
        """Legacy accessor for configurations using ``tilt_deg``."""

        return self.pitch_deg

    @property
    def pitch_radians(self) -> float:
        return math.radians(self.pitch_deg)

    @property
    def ellipse_ratio(self) -> float:
        """Approximate squish factor retained for backwards compatibility."""

        return math.cos(self.pitch_radians)


@dataclass(frozen=True)
class RingTickConfig:
    """Tick placement parameters for a ring."""

    every_deg: Tuple[float, ...]
    length_px: Tuple[float, float]
    alpha: float = 0.8
    weight: float = 1.0


@dataclass(frozen=True)
class RingConfig:
    """Parameters describing a single UI ring."""

    r: float
    width: float
    color: str
    dash: Optional[Sequence[float]] = None
    ticks_every_deg: Optional[float] = None
    label: Optional[str] = None
    label_angle_deg: Optional[float] = None
    label_offset: float = 0.015
    glow: float = 1.0
    halo_color: Optional[str] = None
    tick: Optional[RingTickConfig] = None


@dataclass(frozen=True)
class ReadoutPlacement:
    """Placement description for a numeric readout."""

    kind: str
    ring_index: int
    angle_deg: float
    radius: Optional[float] = None
    radial_offset: float = 0.0


@dataclass(frozen=True)
class ReadoutConfig:
    """Configuration for a numeric readout rendered near a ring."""

    text: str
    alignment: str
    placement: ReadoutPlacement


@dataclass(frozen=True)
class BulgeDistribution:
    """Configuration for the dense stellar bulge."""

    count: int
    sigma: float
    falloff_alpha: float
    size_px: Tuple[float, float]


@dataclass(frozen=True)
class BackgroundDistribution:
    """Configuration for the sparse background stars."""

    count: int
    size_px: Tuple[float, float]
    jitter: float = 0.3
    min_r: float = 0.0
    max_r: float = 1.0


@dataclass(frozen=True)
class StarConfig:
    """Aggregate settings for star sampling."""

    bulge: BulgeDistribution
    background: BackgroundDistribution
    warm_color: str = "#E8B551"
    hot_color: str = "#FFFFFF"
    background_color: str = "#CFA05A"


@dataclass(frozen=True)
class TextConfig:
    """Typography settings."""

    font: Optional[str] = None
    size_px: int = 26
    color: str = "#e6f5ff"
    tracking: float = -0.5
    tabular_digits: bool = True


@dataclass(frozen=True)
class HUDReadout:
    """Configuration for a HUD readout displayed along the bottom band."""

    text: str
    position: float
    alignment: str = "center"


@dataclass(frozen=True)
class HUDConfig:
    """Settings controlling the bottom HUD overlay."""

    enabled: bool = False
    height_px: int = 180
    font: Optional[str] = None
    emissive: float = 1.3
    readouts: Tuple[HUDReadout, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class BloomConfig:
    threshold: float = 0.75
    sigmas: Tuple[float, ...] = (2.0, 6.0, 12.0)
    intensities: Tuple[float, ...] = (0.7, 0.4, 0.2)


@dataclass(frozen=True)
class ChromaticAberrationConfig:
    pixels: float = 1.2
    center: Optional[Tuple[float, float]] = None


@dataclass(frozen=True)
class AnamorphicConfig:
    enabled: bool = True
    length_px: float = 80.0
    intensity: float = 0.15


@dataclass(frozen=True)
class PostConfig:
    bloom: BloomConfig = field(default_factory=BloomConfig)
    chromatic_aberration: ChromaticAberrationConfig = field(
        default_factory=ChromaticAberrationConfig
    )
    anamorphic: AnamorphicConfig = field(default_factory=AnamorphicConfig)
    vignette: float = 0.25
    grain: float = 0.03
    tonemap: str = "filmic"
    gamma: float = 2.2


@dataclass(frozen=True)
class SceneConfig:
    """Top level configuration for a star chart scene."""

    seed: int
    resolution: Resolution
    camera: Camera
    rings: List[RingConfig]
    stars: StarConfig
    readouts: List[ReadoutConfig] = field(default_factory=list)
    text: TextConfig = field(default_factory=TextConfig)
    post: PostConfig = field(default_factory=PostConfig)
    hud: HUDConfig = field(default_factory=HUDConfig)
    lut: Optional[str] = None
    name: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, base_path: Optional[Path] = None) -> "SceneConfig":
        """Construct a :class:`SceneConfig` from a dictionary."""

        resolution_data = data.get("resolution", {})
        resolution = Resolution(
            width=int(resolution_data["width"]),
            height=int(resolution_data["height"]),
            ssaa=int(resolution_data.get("ssaa", 1)),
        )

        camera_data = data.get("camera", {})
        pitch_value = camera_data.get("pitch_deg", camera_data.get("tilt_deg", 83.0))
        camera = Camera(
            pitch_deg=float(pitch_value),
            yaw_deg=float(camera_data.get("yaw_deg", 0.0)),
            fov_deg=float(camera_data.get("fov_deg", 35.0)),
            z_near=float(camera_data.get("z_near", 0.1)),
            z_far=float(camera_data.get("z_far", 6.0)),
        )

        rings: List[RingConfig] = []
        for item in data.get("rings", []):
            if not isinstance(item, dict):
                continue
            if "r" not in item or "color" not in item:
                continue
            tick_spec: Optional[RingTickConfig] = None
            tick_data = item.get("tick")
            if isinstance(tick_data, dict):
                every_raw = tick_data.get("every_deg", tick_data.get("spacing"))
                every: List[float] = []
                if isinstance(every_raw, (int, float)):
                    every.append(float(every_raw))
                elif isinstance(every_raw, (list, tuple)):
                    for value in every_raw:
                        try:
                            every.append(float(value))
                        except (TypeError, ValueError):
                            continue
                every = [value for value in every if value > 0]
                length_raw = tick_data.get("length_px", tick_data.get("length"))
                lengths: Tuple[float, float]
                if isinstance(length_raw, (int, float)):
                    length_value = float(length_raw)
                    lengths = (length_value, length_value)
                elif isinstance(length_raw, (list, tuple)) and length_raw:
                    first = float(length_raw[0])
                    second = float(length_raw[1] if len(length_raw) > 1 else length_raw[0])
                    lengths = (first, second)
                else:
                    lengths = (8.0, 14.0)
                if every:
                    lo, hi = min(lengths), max(lengths)
                    tick_spec = RingTickConfig(
                        every_deg=tuple(sorted(every)),
                        length_px=(lo, hi),
                        alpha=float(tick_data.get("alpha", 0.8)),
                        weight=float(tick_data.get("weight", 1.0)),
                    )

            rings.append(
                RingConfig(
                    r=float(item.get("r", 0.0)),
                    width=float(item.get("width", 0.006)),
                    color=str(item.get("color", "#ffffff")),
                    dash=tuple(item.get("dash", [])) or None,
                    ticks_every_deg=float(item["ticks_every_deg"])
                    if "ticks_every_deg" in item
                    else None,
                    label=item.get("label"),
                    label_angle_deg=float(item["label_angle_deg"])
                    if "label_angle_deg" in item
                    else None,
                    label_offset=float(item.get("label_offset", 0.015)),
                    glow=float(item.get("glow", 1.0)),
                    halo_color=str(item.get("halo_color", item.get("color", "#ffffff"))),
                    tick=tick_spec,
                )
            )

        readouts: List[ReadoutConfig] = []
        for item in data.get("readouts", []):
            if not isinstance(item, dict):
                continue
            if "text" not in item:
                continue
            text_value = str(item.get("text", ""))
            alignment_raw = str(item.get("alignment", "center")).lower()
            alignment_map = {
                "center": "center",
                "middle": "center",
                "start": "start",
                "left": "start",
                "begin": "start",
                "end": "end",
                "right": "end",
            }
            alignment = alignment_map.get(alignment_raw, "center")
            placement_data = item.get("placement", {})
            if not isinstance(placement_data, dict):
                continue
            kind = str(placement_data.get("type", placement_data.get("kind", "arc"))).lower()
            if kind not in {"arc", "linear"}:
                kind = "arc"
            ring_index = int(placement_data.get("ring", placement_data.get("ring_index", 0)))
            angle_deg = float(placement_data.get("angle_deg", 90.0))
            radius_value = placement_data.get("radius")
            radius = float(radius_value) if radius_value is not None else None
            radial_offset = float(
                placement_data.get("offset", placement_data.get("radial_offset", 0.0))
            )
            readouts.append(
                ReadoutConfig(
                    text=text_value,
                    alignment=alignment,
                    placement=ReadoutPlacement(
                        kind=kind,
                        ring_index=ring_index,
                        angle_deg=angle_deg,
                        radius=radius,
                        radial_offset=radial_offset,
                    ),
                )
            )

        def _pair(value: Any, default: Tuple[float, float]) -> Tuple[float, float]:
            if isinstance(value, (list, tuple)) and value:
                if len(value) == 1:
                    val = float(value[0])
                    return (val, val)
                return (float(value[0]), float(value[1]))
            if value is not None:
                try:
                    val = float(value)
                except (TypeError, ValueError):
                    return default
                return (val, val)
            return default

        stars_data = data.get("stars", {})
        bulge_data = stars_data.get("bulge", stars_data.get("core", {}))
        background_data = stars_data.get(
            "background", stars_data.get("bg", stars_data.get("halo", {}))
        )

        size_default = (
            float(stars_data.get("min_size_px", 0.6)),
            float(stars_data.get("max_size_px", 2.6)),
        )
        bulge_size = _pair(bulge_data.get("size_px", size_default), (1.0, 2.5))
        background_size = _pair(
            background_data.get("size_px", size_default), (0.6, 1.6)
        )

        stars = StarConfig(
            bulge=BulgeDistribution(
                count=int(bulge_data.get("count", 12000)),
                sigma=float(bulge_data.get("sigma", 0.14)),
                falloff_alpha=float(
                    bulge_data.get("falloff_alpha", bulge_data.get("alpha", 1.8))
                ),
                size_px=bulge_size,
            ),
            background=BackgroundDistribution(
                count=int(background_data.get("count", 3500)),
                size_px=background_size,
                jitter=float(background_data.get("jitter", 0.3)),
                min_r=float(background_data.get("min_r", 0.0)),
                max_r=float(background_data.get("max_r", 1.0)),
            ),
            warm_color=str(stars_data.get("warm_color", "#E8B551")),
            hot_color=str(stars_data.get("hot_color", "#FFFFFF")),
            background_color=str(stars_data.get("background_color", "#CFA05A")),
        )

        text_data = data.get("text", {})
        text = TextConfig(
            font=text_data.get("font"),
            size_px=int(text_data.get("size_px", 26)),
            color=str(text_data.get("color", "#e6f5ff")),
            tracking=float(text_data.get("tracking", -0.5)),
            tabular_digits=bool(text_data.get("tabular_digits", True)),
        )

        post_data = data.get("post", {})
        bloom_data = post_data.get("bloom", {})

        def _as_floats(value: Any) -> Tuple[float, ...]:
            if isinstance(value, (list, tuple)):
                result: List[float] = []
                for item in value:
                    try:
                        result.append(float(item))
                    except (TypeError, ValueError):
                        continue
                return tuple(result)
            if value is not None:
                try:
                    return (float(value),)
                except (TypeError, ValueError):
                    return tuple()
            return tuple()

        bloom_sigmas = _as_floats(
            bloom_data.get("sigma_px")
            or bloom_data.get("sigmas")
            or bloom_data.get("radius")
        )
        if not bloom_sigmas:
            bloom_sigmas = (2.0, 6.0, 12.0)

        bloom_intensities = _as_floats(
            bloom_data.get("intensity") or bloom_data.get("intensities")
        )
        if not bloom_intensities:
            bloom_intensities = (0.7, 0.4, 0.2)
        if len(bloom_intensities) == 1 and len(bloom_sigmas) > 1:
            bloom_intensities = tuple(bloom_intensities[0] for _ in bloom_sigmas)
        elif len(bloom_sigmas) != len(bloom_intensities):
            bloom_intensities = tuple(
                bloom_intensities[i % len(bloom_intensities)]
                for i in range(len(bloom_sigmas))
            )

        chroma_data = post_data.get("chromab", post_data.get("chromatic_aberration", {}))
        center_value = chroma_data.get("center")
        if isinstance(center_value, (list, tuple)) and len(center_value) >= 2:
            chroma_center: Optional[Tuple[float, float]] = (
                float(center_value[0]),
                float(center_value[1]),
            )
        else:
            chroma_center = None
        if isinstance(center_value, str) and center_value.strip().lower() not in {
            "image_center",
            "centre",
            "center",
        }:
            try:
                parts = [float(part) for part in center_value.split(",")]
                if len(parts) >= 2:
                    chroma_center = (parts[0], parts[1])
            except Exception:  # pragma: no cover - defensive
                chroma_center = None

        anamorphic_data = post_data.get("anamorphic", {})

        post = PostConfig(
            bloom=BloomConfig(
                threshold=float(bloom_data.get("threshold", 0.75)),
                sigmas=bloom_sigmas,
                intensities=bloom_intensities,
            ),
            chromatic_aberration=ChromaticAberrationConfig(
                pixels=float(chroma_data.get("pixels", chroma_data.get("k", 1.2))),
                center=chroma_center,
            ),
            anamorphic=AnamorphicConfig(
                enabled=bool(anamorphic_data.get("enabled", True)),
                length_px=float(anamorphic_data.get("length_px", anamorphic_data.get("length", 80.0))),
                intensity=float(anamorphic_data.get("intensity", 0.15)),
            ),
            vignette=float(post_data.get("vignette", 0.25)),
            grain=float(post_data.get("grain", 0.03)),
            tonemap=str(post_data.get("tonemap", "filmic")),
            gamma=float(post_data.get("gamma", 2.2)),
        )

        hud_data = data.get("hud", {})
        hud_readouts: List[HUDReadout] = []
        for item in hud_data.get("readouts", []):
            if not isinstance(item, dict):
                continue
            text_value = str(item.get("text", "")).strip()
            if not text_value:
                continue
            position_raw = item.get("position", item.get("x", item.get("u", 0.5)))
            try:
                position = float(position_raw)
            except (TypeError, ValueError):
                position = 0.5
            position = max(0.0, min(1.0, position))
            alignment_raw = str(item.get("alignment", "center")).lower()
            alignment = {
                "center": "center",
                "middle": "center",
                "start": "start",
                "left": "start",
                "end": "end",
                "right": "end",
            }.get(alignment_raw, "center")
            hud_readouts.append(
                HUDReadout(text=text_value, position=position, alignment=alignment)
            )

        hud = HUDConfig(
            enabled=bool(hud_data.get("enabled", True)),
            height_px=int(hud_data.get("height_px", hud_data.get("height", 180))),
            font=hud_data.get("font"),
            emissive=float(hud_data.get("emissive", 1.3)),
            readouts=tuple(hud_readouts),
        )

        seed = int(data.get("seed", 1))
        name = data.get("name")
        lut = data.get("lut") or data.get("post", {}).get("lut")

        return cls(
            seed=seed,
            resolution=resolution,
            camera=camera,
            rings=rings,
            readouts=readouts,
            stars=stars,
            text=text,
            post=post,
            hud=hud,
            lut=lut,
            name=name,
        )

    @classmethod
    def load(cls, path: Path) -> "SceneConfig":
        """Load configuration from a YAML file."""
        text = Path(path).read_text(encoding="utf8")
        data = _load_yaml(text)
        if not isinstance(data, dict):
            raise ValueError("Configuration root must be a mapping")
        return cls.from_dict(data, base_path=Path(path).parent)


def _load_yaml(text: str) -> Any:
    if yaml is not None:  # pragma: no cover - exercised when PyYAML is available
        return yaml.safe_load(text)
    return _simple_yaml_load(text)


def _simple_yaml_load(text: str) -> Any:
    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, stripped))
    value, _ = _parse_block(lines, 0, 0)
    return value


def _parse_block(lines: List[Tuple[int, str]], index: int, indent: int) -> Tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    level, content = lines[index]
    if content.startswith("- ") and level == indent:
        return _parse_list(lines, index, indent)
    result: Dict[str, Any] = {}
    while index < len(lines):
        level, content = lines[index]
        if level < indent or content.startswith("- "):
            break
        if ":" not in content:
            index += 1
            continue
        key, remainder = content.split(":", 1)
        key = key.strip()
        remainder = remainder.strip()
        index += 1
        if remainder:
            result[key] = _parse_scalar(remainder)
        else:
            value, index = _parse_block(lines, index, indent + 2)
            result[key] = value
    return result, index


def _parse_list(lines: List[Tuple[int, str]], index: int, indent: int) -> Tuple[List[Any], int]:
    items: List[Any] = []
    while index < len(lines):
        level, content = lines[index]
        if level < indent or not content.startswith("- "):
            break
        remainder = content[2:].strip()
        index += 1
        if remainder:
            if ":" in remainder:
                key, value_part = remainder.split(":", 1)
                key = key.strip()
                value_part = value_part.strip()
                item: Dict[str, Any] = {}
                item[key] = _parse_scalar(value_part) if value_part else None
                if value_part == "":
                    subvalue, index = _parse_block(lines, index, indent + 2)
                    item[key] = subvalue
                else:
                    subvalue, index = _parse_block(lines, index, indent + 2)
                    if isinstance(subvalue, dict):
                        item.update(subvalue)
                items.append(item)
            else:
                items.append(_parse_scalar(remainder))
        else:
            value, index = _parse_block(lines, index, indent + 2)
            items.append(value)
    return items, index


def _parse_scalar(token: str) -> Any:
    if token.startswith("\"") and token.endswith("\""):
        return token[1:-1]
    if token.startswith("'") and token.endswith("'"):
        return token[1:-1]
    lowered = token.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    if token.startswith("[") or token.startswith("{"):
        return ast.literal_eval(token)
    try:
        if token.startswith("0x"):
            return int(token, 16)
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


__all__ = [
    "Resolution",
    "Camera",
    "RingConfig",
    "ReadoutPlacement",
    "ReadoutConfig",
    "CoreDistribution",
    "HaloDistribution",
    "StarConfig",
    "TextConfig",
    "BloomConfig",
    "ChromaticAberrationConfig",
    "PostConfig",
    "SceneConfig",
]
