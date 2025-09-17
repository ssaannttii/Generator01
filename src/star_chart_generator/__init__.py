"""Star chart generator package."""

from .config import GeneratorConfig, load_config

try:  # pragma: no cover - optional dependency wiring
    from .generate import RenderResult, generate_chart
    from .io import save_render
except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
    _IMPORT_ERROR = exc

    class RenderResult:  # type: ignore[redeclaration]
        """Placeholder used when Pillow is missing."""

        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - defensive
            raise RuntimeError("Pillow is required to use the star chart generator") from exc

    def generate_chart(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("Pillow is required to use the star chart generator") from exc

    def save_render(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("Pillow is required to save renders") from exc

__all__ = [
    "GeneratorConfig",
    "load_config",
    "generate_chart",
    "RenderResult",
    "save_render",
]
