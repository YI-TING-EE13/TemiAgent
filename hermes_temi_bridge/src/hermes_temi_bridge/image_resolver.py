"""Image path translation and validation for Bridge-to-Hermes handoff."""

from __future__ import annotations

from pathlib import Path

from .event_models import VisionFrame


class ImageValidationError(ValueError):
    """Raised when an event references an unreadable or unsafe image path."""

    def __init__(self, reason: str, path: str):
        """Create an image validation error for a specific filesystem path."""
        super().__init__(f"{reason}: {path}")
        self.reason = reason
        self.path = path


def to_hermes_path(
    bridge_path: str,
    bridge_root: str = "/var/lib/temi_shared",
    hermes_root: str = "/shared/temi",
) -> str:
    """Convert a Bridge container path to the corresponding Hermes container path."""
    normalized_bridge = Path(bridge_path).as_posix()
    normalized_root = Path(bridge_root).as_posix().rstrip("/")
    normalized_hermes = Path(hermes_root).as_posix().rstrip("/")
    if normalized_bridge == normalized_root:
        return normalized_hermes
    prefix = normalized_root + "/"
    if not normalized_bridge.startswith(prefix):
        raise ValueError(f"path is outside bridge shared root: {bridge_path}")
    return normalized_hermes + "/" + normalized_bridge[len(prefix) :]


def validate_image_file(path: str, max_size_mb: int) -> None:
    """Ensure an event image exists, is readable, and is within size limits."""
    file_path = Path(path)
    if not file_path.exists():
        raise ImageValidationError("missing_image", path)
    if not file_path.is_file():
        raise ImageValidationError("image_not_file", path)
    try:
        with file_path.open("rb") as handle:
            handle.read(1)
    except OSError as exc:
        raise ImageValidationError("image_not_readable", path) from exc
    max_bytes = max_size_mb * 1024 * 1024
    if file_path.stat().st_size <= 0:
        raise ImageValidationError("image_empty", path)
    if file_path.stat().st_size > max_bytes:
        raise ImageValidationError("image_too_large", path)


def translate_frames(
    frames: tuple[VisionFrame, ...],
    bridge_root: str,
    hermes_root: str,
) -> list[dict[str, str | int | None]]:
    """Translate every frame path from the Bridge mount to the Hermes mount."""
    translated = []
    for frame in frames:
        translated.append(
            {
                "name": frame.name,
                "ts_ms": frame.ts_ms,
                "bridge_path": frame.path,
                "hermes_path": to_hermes_path(frame.path, bridge_root, hermes_root),
            }
        )
    return translated
