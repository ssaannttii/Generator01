import math
import random

import pytest

try:  # pragma: no cover - dependency probe
    import PIL  # type: ignore  # noqa: F401
    PIL_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency probe
    PIL_AVAILABLE = False

pytestmark = pytest.mark.skipif(not PIL_AVAILABLE, reason="Pillow is required for rendering tests")

if PIL_AVAILABLE:  # pragma: no branch - guarded import
    from star_chart_generator import load_config
    from star_chart_generator.generate import generate_chart
    from star_chart_generator.sampling import sample_annulus, sample_powerlaw_brightness, sample_sersic


def test_sersic_distribution_more_dense_at_core():
    rng = random.Random(123)
    radii = sample_sersic(5000, sigma=0.25, alpha=3.0, rng=rng)
    inner = [r for r in radii if r < 0.1]
    outer = [r for r in radii if r > 0.4]
    assert len(inner) > len(outer)


def test_annulus_minimum_separation_effect():
    rng = random.Random(321)
    radii, angles = sample_annulus(400, 0.4, 1.0, rng, min_separation=0.02)
    points = [(_pol_to_cart(r, a)) for r, a in zip(radii, angles)]
    min_dist = min(
        math.dist(points[i], points[j])
        for i in range(len(points))
        for j in range(i + 1, len(points))
    )
    assert min_dist > 0.004


def _pol_to_cart(r: float, angle: float) -> tuple[float, float]:
    return (r * math.cos(angle), r * math.sin(angle))


def test_powerlaw_bias():
    rng = random.Random(99)
    brightness = sample_powerlaw_brightness(2000, power=2.0, rng=rng)
    assert max(brightness) <= 1.0
    assert min(brightness) >= 0.0
    mean_value = sum(brightness) / len(brightness)
    assert mean_value < 0.5


def test_generate_chart_runs(tmp_path):
    config = load_config("configs/sparse.yaml")
    config.resolution.width = 320
    config.resolution.height = 480
    config.resolution.ssaa = 1
    config.stars.core.count = 200
    config.stars.halo.count = 120
    result = generate_chart(config)
    assert result.linear.width == 320
    assert result.linear.height == 480
    channels = [channel.getextrema()[1] for channel in result.linear.channels]
    assert max(channels) > 0
    assert result.tonemapped.size == (320, 480)
