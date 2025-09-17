"""Minimal float RGB image utilities with PNG serialization."""
from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple


Color = Tuple[float, float, float]


@dataclass
class FloatImage:
    width: int
    height: int
    pixels: List[List[List[float]]]

    @classmethod
    def new(cls, width: int, height: int, fill: float = 0.0) -> "FloatImage":
        rows = [[[fill, fill, fill] for _ in range(width)] for _ in range(height)]
        return cls(width=width, height=height, pixels=rows)

    def copy(self) -> "FloatImage":
        return FloatImage(
            width=self.width,
            height=self.height,
            pixels=[[pixel[:] for pixel in row] for row in self.pixels],
        )

    def add_pixel(self, x: int, y: int, color: Color, intensity: float = 1.0) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            pixel = self.pixels[y][x]
            pixel[0] += color[0] * intensity
            pixel[1] += color[1] * intensity
            pixel[2] += color[2] * intensity

    def get_pixel(self, x: int, y: int) -> Color:
        pixel = self.pixels[y][x]
        return (pixel[0], pixel[1], pixel[2])

    def add_gaussian(self, cx: float, cy: float, sigma: float, intensity: float, color: Color) -> None:
        if sigma <= 0:
            return
        radius = max(1, int(sigma * 3.0))
        x0 = max(0, int(cx) - radius)
        x1 = min(self.width, int(cx) + radius + 1)
        y0 = max(0, int(cy) - radius)
        y1 = min(self.height, int(cy) + radius + 1)
        two_sigma_sq = 2.0 * sigma * sigma
        for y in range(y0, y1):
            dy = y - cy
            for x in range(x0, x1):
                dx = x - cx
                value = math.exp(-(dx * dx + dy * dy) / two_sigma_sq)
                self.add_pixel(x, y, color, intensity * value)

    def add_disc(self, cx: float, cy: float, radius: float, color: Color, intensity: float = 1.0) -> None:
        r2 = radius * radius
        x0 = max(0, int(cx - radius - 1))
        x1 = min(self.width, int(cx + radius + 2))
        y0 = max(0, int(cy - radius - 1))
        y1 = min(self.height, int(cy + radius + 2))
        for y in range(y0, y1):
            dy = y - cy
            for x in range(x0, x1):
                dx = x - cx
                if dx * dx + dy * dy <= r2:
                    self.add_pixel(x, y, color, intensity)

    def add_line(self, p0: Tuple[float, float], p1: Tuple[float, float], color: Color, width: int = 1, intensity: float = 1.0) -> None:
        x0, y0 = p0
        x1, y1 = p1
        dx = x1 - x0
        dy = y1 - y0
        length = max(abs(dx), abs(dy))
        if length == 0:
            self.add_disc(x0, y0, width * 0.5, color, intensity)
            return
        steps = int(length) + 1
        for i in range(steps + 1):
            t = i / max(steps, 1)
            x = x0 + dx * t
            y = y0 + dy * t
            self.add_disc(x, y, max(0.5, width * 0.5), color, intensity)

    def apply_map(self, func) -> None:
        for y in range(self.height):
            row = self.pixels[y]
            for x in range(self.width):
                r, g, b = row[x]
                row[x][0], row[x][1], row[x][2] = func(r, g, b)

    def multiply(self, factor: float) -> None:
        for y in range(self.height):
            row = self.pixels[y]
            for x in range(self.width):
                row[x][0] *= factor
                row[x][1] *= factor
                row[x][2] *= factor

    def add_image(self, other: "FloatImage") -> None:
        for row, other_row in zip(self.pixels, other.pixels):
            for pixel, other_pixel in zip(row, other_row):
                pixel[0] += other_pixel[0]
                pixel[1] += other_pixel[1]
                pixel[2] += other_pixel[2]

    def add_scaled_image(self, other: "FloatImage", scale: float) -> None:
        for row, other_row in zip(self.pixels, other.pixels):
            for pixel, other_pixel in zip(row, other_row):
                pixel[0] += other_pixel[0] * scale
                pixel[1] += other_pixel[1] * scale
                pixel[2] += other_pixel[2] * scale

    def clamp(self, lo: float = 0.0, hi: float = 1.0) -> None:
        for y in range(self.height):
            for x in range(self.width):
                pixel = self.pixels[y][x]
                pixel[0] = min(max(pixel[0], lo), hi)
                pixel[1] = min(max(pixel[1], lo), hi)
                pixel[2] = min(max(pixel[2], lo), hi)

    def downsample(self, factor: int) -> "FloatImage":
        if factor <= 1:
            return self.copy()
        new_width = self.width // factor
        new_height = self.height // factor
        output = FloatImage.new(new_width, new_height, 0.0)
        for y in range(new_height):
            for x in range(new_width):
                acc = [0.0, 0.0, 0.0]
                for yy in range(factor):
                    for xx in range(factor):
                        pixel = self.pixels[y * factor + yy][x * factor + xx]
                        acc[0] += pixel[0]
                        acc[1] += pixel[1]
                        acc[2] += pixel[2]
                scale = 1.0 / (factor * factor)
                output.pixels[y][x][0] = acc[0] * scale
                output.pixels[y][x][1] = acc[1] * scale
                output.pixels[y][x][2] = acc[2] * scale
        return output

    def to_uint8_rows(self) -> List[bytearray]:
        rows: List[bytearray] = []
        for y in range(self.height):
            row_bytes = bytearray()
            row_bytes.append(0)  # filter type 0
            for x in range(self.width):
                r, g, b = self.pixels[y][x]
                row_bytes.append(int(min(max(r, 0.0), 1.0) * 255.0 + 0.5))
                row_bytes.append(int(min(max(g, 0.0), 1.0) * 255.0 + 0.5))
                row_bytes.append(int(min(max(b, 0.0), 1.0) * 255.0 + 0.5))
            rows.append(row_bytes)
        return rows

    def to_png_bytes(self) -> bytes:
        """Return the image encoded as PNG bytes."""

        rows = self.to_uint8_rows()
        data = b"".join(rows)
        compressed = zlib.compress(data, level=6)

        def chunk(tag: bytes, payload: bytes) -> bytes:
            return (
                struct.pack(">I", len(payload))
                + tag
                + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
            )

        ihdr = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        png_bytes = bytearray()
        png_bytes.extend(b"\x89PNG\r\n\x1a\n")
        png_bytes.extend(chunk(b"IHDR", ihdr))
        png_bytes.extend(chunk(b"IDAT", compressed))
        png_bytes.extend(chunk(b"IEND", b""))
        return bytes(png_bytes)

    def save_png(self, path: str) -> None:
        with open(path, "wb") as fh:
            fh.write(self.to_png_bytes())

    def sample(self, x: float, y: float) -> Color:
        if x < 0 or x >= self.width - 1 or y < 0 or y >= self.height - 1:
            ix = min(max(int(x), 0), self.width - 1)
            iy = min(max(int(y), 0), self.height - 1)
            pixel = self.pixels[iy][ix]
            return pixel[0], pixel[1], pixel[2]
        x0 = int(math.floor(x))
        y0 = int(math.floor(y))
        x1 = x0 + 1
        y1 = y0 + 1
        wx = x - x0
        wy = y - y0
        p00 = self.pixels[y0][x0]
        p01 = self.pixels[y0][x1]
        p10 = self.pixels[y1][x0]
        p11 = self.pixels[y1][x1]
        top = [p00[c] * (1 - wx) + p01[c] * wx for c in range(3)]
        bottom = [p10[c] * (1 - wx) + p11[c] * wx for c in range(3)]
        return tuple(top[c] * (1 - wy) + bottom[c] * wy for c in range(3))


def gaussian_blur(image: FloatImage, sigma: float) -> FloatImage:
    if sigma <= 0:
        return image.copy()

    kernel, radius = gaussian_kernel(sigma)
    width, height = image.width, image.height

    temp = FloatImage.new(width, height, 0.0)
    source_pixels = image.pixels
    temp_pixels = temp.pixels
    for y in range(height):
        src_row = source_pixels[y]
        dst_row = temp_pixels[y]
        for x in range(width):
            acc0 = acc1 = acc2 = 0.0
            start = x - radius
            kernel_index = 0
            if start < 0:
                kernel_index = -start
                start = 0
            end = x + radius + 1
            if end > width:
                end = width
            for xx in range(start, end):
                weight = kernel[kernel_index]
                pixel = src_row[xx]
                acc0 += pixel[0] * weight
                acc1 += pixel[1] * weight
                acc2 += pixel[2] * weight
                kernel_index += 1
            dst_pixel = dst_row[x]
            dst_pixel[0] = acc0
            dst_pixel[1] = acc1
            dst_pixel[2] = acc2

    output = FloatImage.new(width, height, 0.0)
    output_pixels = output.pixels
    for y in range(height):
        dst_row = output_pixels[y]
        for x in range(width):
            acc0 = acc1 = acc2 = 0.0
            start = y - radius
            kernel_index = 0
            if start < 0:
                kernel_index = -start
                start = 0
            end = y + radius + 1
            if end > height:
                end = height
            for yy in range(start, end):
                weight = kernel[kernel_index]
                pixel = temp_pixels[yy][x]
                acc0 += pixel[0] * weight
                acc1 += pixel[1] * weight
                acc2 += pixel[2] * weight
                kernel_index += 1
            dst_pixel = dst_row[x]
            dst_pixel[0] = acc0
            dst_pixel[1] = acc1
            dst_pixel[2] = acc2

    return output


def gaussian_kernel(sigma: float) -> Tuple[List[float], int]:
    if sigma <= 0:
        return [1.0], 0
    radius = max(1, int(math.ceil(sigma * 3.0)))
    denom = 2.0 * sigma * sigma
    kernel = [math.exp(-(offset * offset) / denom) for offset in range(-radius, radius + 1)]
    total = sum(kernel)
    if total <= 0.0:
        return [1.0], 0
    inv_total = 1.0 / total
    return [value * inv_total for value in kernel], radius


__all__ = ["FloatImage", "gaussian_blur", "gaussian_kernel", "Color"]
