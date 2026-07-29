from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image


class PngContractError(ValueError):
    pass


def validate_png_bytes(data: bytes) -> tuple[int, int]:
    if not isinstance(data, bytes) or not data:
        raise PngContractError("PNG bytes are empty or invalid")
    try:
        with Image.open(BytesIO(data), formats=["PNG"]) as probe:
            if probe.format != "PNG":
                raise PngContractError("image content is not PNG")
            probe.verify()
        with Image.open(BytesIO(data), formats=["PNG"]) as decoded:
            if decoded.format != "PNG" or getattr(decoded, "n_frames", 1) != 1:
                raise PngContractError("image content is not a single-frame PNG")
            orientation = decoded.getexif().get(274, 1)
            if orientation not in (None, 1):
                raise PngContractError(
                    "PNG EXIF orientation must be absent or equal to 1"
                )
            width, height = decoded.size
            if (
                isinstance(width, bool)
                or isinstance(height, bool)
                or not isinstance(width, int)
                or not isinstance(height, int)
                or width <= 0
                or height <= 0
            ):
                raise PngContractError("PNG dimensions must be positive")
            decoded.load()
        return width, height
    except PngContractError:
        raise
    except Exception as error:
        raise PngContractError(f"PNG decode failed: {error}") from error


def read_validated_png(path: Path) -> tuple[bytes, int, int]:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise PngContractError(f"PNG could not be read: {error}") from error
    width, height = validate_png_bytes(data)
    return data, width, height


def validate_png_file(path: Path) -> tuple[int, int]:
    _, width, height = read_validated_png(path)
    return width, height
