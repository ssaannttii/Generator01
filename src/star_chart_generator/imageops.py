"""Utilities for working with floating-point RGB buffers using Pillow."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence, Tuple

from PIL import Image, ImageChops, ImageFilter


@dataclass
class FloatImage:
    width: int
    height: int
    channels: Tuple[Image.Image, Image.Image, Image.Image]

    @classmethod
    def blank(cls, width: int, height: int, fill: float = 0.0) -> "FloatImage":
        channels = tuple(Image.new("F", (width, height), fill) for _ in range(3))
        return cls(width=width, height=height, channels=channels)  # type: ignore[arg-type]

    def copy(self) -> "FloatImage":
        return FloatImage(
            width=self.width,
            height=self.height,
            channels=tuple(channel.copy() for channel in self.channels),  # type: ignore[arg-type]
        )

    def add(self, other: "FloatImage") -> None:
        self._ensure_same_size(other)
        updated = []
        for a, b in zip(self.channels, other.channels):
            updated.append(ImageChops.add(a, b))
        self.channels = tuple(updated)  # type: ignore[assignment]

    def add_scaled(self, other: "FloatImage", scale: float) -> None:
        if scale == 0.0:
            return
        self._ensure_same_size(other)
        updated = []
        for a, b in zip(self.channels, other.channels):
            scaled = b.point(lambda v, s=scale: v * s)
            updated.append(ImageChops.add(a, scaled))
        self.channels = tuple(updated)  # type: ignore[assignment]

    def add_mask(self, mask: Image.Image, color: Tuple[float, float, float], intensity: float) -> None:
        if intensity == 0.0:
            return
        for idx, (channel, value) in enumerate(zip(self.channels, color)):
            if value == 0.0:
                continue
            scaled = mask.point(lambda v, s=value * intensity: v * s)
            self.channels = _replace_index(self.channels, idx, ImageChops.add(channel, scaled))

    def add_patch(self, patch: Image.Image, color: Tuple[float, float, float], intensity: float, box: Tuple[int, int, int, int]) -> None:
        if intensity == 0.0:
            return
        x0, y0, x1, y1 = box
        if x0 >= x1 or y0 >= y1:
            return
        for idx, (channel, value) in enumerate(zip(self.channels, color)):
            if value == 0.0:
                continue
            region = channel.crop(box)
            scaled = patch.point(lambda v, s=value * intensity: v * s)
            region = ImageChops.add(region, scaled)
            channel.paste(region, box)
            self.channels = _replace_index(self.channels, idx, channel)

    def blur(self, radius: float) -> "FloatImage":
        if radius <= 0:
            return self.copy()
        blurred = tuple(channel.filter(ImageFilter.GaussianBlur(radius=radius)) for channel in self.channels)
        return FloatImage(width=self.width, height=self.height, channels=blurred)  # type: ignore[arg-type]

    def resize(self, new_width: int, new_height: int) -> "FloatImage":
        resized = tuple(
            channel.resize((new_width, new_height), resample=Image.Resampling.BOX)
            for channel in self.channels
        )
        return FloatImage(width=new_width, height=new_height, channels=resized)  # type: ignore[arg-type]

    def apply_point(self, func: Callable[[float], float]) -> "FloatImage":
        processed = tuple(channel.point(func) for channel in self.channels)
        return FloatImage(width=self.width, height=self.height, channels=processed)  # type: ignore[arg-type]

    def clone_blank(self) -> "FloatImage":
        return FloatImage.blank(self.width, self.height)

    def to_tuple(self) -> Tuple[Image.Image, Image.Image, Image.Image]:
        return self.channels

    def _ensure_same_size(self, other: "FloatImage") -> None:
        if self.width != other.width or self.height != other.height:
            raise ValueError("Image sizes do not match")


def merge_layers(layers: Sequence[FloatImage]) -> FloatImage:
    if not layers:
        raise ValueError("No layers to merge")
    base = layers[0].copy()
    for layer in layers[1:]:
        base.add(layer)
    return base


def _replace_index(seq: Tuple[Image.Image, Image.Image, Image.Image], index: int, value: Image.Image) -> Tuple[Image.Image, Image.Image, Image.Image]:
    lst = list(seq)
    lst[index] = value
    return tuple(lst)  # type: ignore[return-value]


__all__ = ["FloatImage", "merge_layers"]
