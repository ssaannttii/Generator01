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
    """Camera orientation used for ring projection."""

    tilt_deg: float = 32.0
    fov_deg: float = 35.0

    @property
    def tilt_radians(self) -> float:
        return math.radians(self.tilt_deg)

    @property
    def ellipse_ratio(self) -> float:
        """Approximate squish factor for the vertical axis of the rings."""
        return math.cos(self.tilt_radians)


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
class CoreDistribution:
    """Configuration for the dense stellar core."""

    sigma: float
    alpha: float
    count: int


@dataclass(frozen=True)
class HaloDistribution:
    """Configuration for the sparse halo of stars."""

    count: int
    min_r: float
    max_r: float


@dataclass(frozen=True)
class StarConfig:
    """Aggregate settings for star sampling."""

    core: CoreDistribution
    halo: HaloDistribution
    brightness_power: float = 1.8
    min_size_px: float = 0.6
    max_size_px: float = 2.8
    color_jitter: float = 0.08


@dataclass(frozen=True)
class TextConfig:
    """Typography settings."""

    font: Optional[str] = None
    size_px: int = 26
    color: str = "#e6f5ff"
    tracking: float = -0.5
    tabular_digits: bool = True


@dataclass(frozen=True)
class BloomConfig:
    threshold: float = 1.1
    intensity: float = 0.32
    radius: float = 18.0


@dataclass(frozen=True)
class ChromaticAberrationConfig:
    k: float = 0.0015


@dataclass(frozen=True)
class PostConfig:
    bloom: BloomConfig = field(default_factory=BloomConfig)
    chromatic_aberration: ChromaticAberrationConfig = field(
        default_factory=ChromaticAberrationConfig
    )
    vignette: float = 0.12
    grain: float = 0.015


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
        camera = Camera(
            tilt_deg=float(camera_data.get("tilt_deg", 32.0)),
            fov_deg=float(camera_data.get("fov_deg", 35.0)),
        )

        rings = [
            RingConfig(
                r=float(item["r"]),
                width=float(item.get("width", 0.006)),
                color=str(item["color"]),
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
            )
            for item in data.get("rings", [])
        ]

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

        stars_data = data.get("stars", {})
        core_data = stars_data.get("core", {})
        halo_data = stars_data.get("halo", {})
        stars = StarConfig(
            core=CoreDistribution(
                sigma=float(core_data.get("sigma", 0.18)),
                alpha=float(core_data.get("alpha", 3.2)),
                count=int(core_data.get("count", 18000)),
            ),
            halo=HaloDistribution(
                count=int(halo_data.get("count", 6000)),
                min_r=float(halo_data.get("min_r", 0.35)),
                max_r=float(halo_data.get("max_r", 1.0)),
            ),
            brightness_power=float(stars_data.get("brightness_power", 1.8)),
            min_size_px=float(stars_data.get("min_size_px", 0.6)),
            max_size_px=float(stars_data.get("max_size_px", 2.8)),
            color_jitter=float(stars_data.get("color_jitter", 0.08)),
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
        chromatic_data = post_data.get("chromatic_aberration", {})
        post = PostConfig(
            bloom=BloomConfig(
                threshold=float(bloom_data.get("threshold", 1.1)),
                intensity=float(bloom_data.get("intensity", 0.32)),
                radius=float(bloom_data.get("radius", 18.0)),
            ),
            chromatic_aberration=ChromaticAberrationConfig(
                k=float(chromatic_data.get("k", 0.0015))
            ),
            vignette=float(post_data.get("vignette", 0.12)),
            grain=float(post_data.get("grain", 0.015)),
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
