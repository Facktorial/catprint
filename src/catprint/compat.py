"""Compatibility helpers for Python/Pillow versions used in tests.

Provides `batched` for older Python versions and constants for image
resampling/transpose that work across Pillow releases.
"""
from __future__ import annotations

import itertools
import typing

try:
    import PIL.Image as _PILImage
except Exception:  # pragma: no cover - tests will import PIL
    _PILImage = None


def batched(iterable: typing.Iterable, n: int):
    it = iter(iterable)
    while True:
        chunk = list(itertools.islice(it, n))
        if not chunk:
            break
        yield chunk


def _pillow_attr(name: str, default=None):
    if _PILImage is None:
        return default
    return getattr(getattr(_PILImage, name, None) or _PILImage, name, default)


LANCZOS = None
FLIP_LEFT_RIGHT = None
ROTATE_270 = None
DITHER_FLOYD = None
try:
    # Pillow >= 9.1
    LANCZOS = getattr(_PILImage, "Resampling").LANCZOS
    FLIP_LEFT_RIGHT = getattr(_PILImage, "Transpose").FLIP_LEFT_RIGHT
    ROTATE_270 = getattr(_PILImage, "Transpose").ROTATE_270
    DITHER_FLOYD = getattr(_PILImage, "Dither").FLOYDSTEINBERG
except Exception:
    # older Pillow
    if _PILImage is not None:
        LANCZOS = getattr(_PILImage, "LANCZOS", getattr(_PILImage, "ANTIALIAS", None))
        FLIP_LEFT_RIGHT = getattr(_PILImage, "FLIP_LEFT_RIGHT", None)
        ROTATE_270 = getattr(_PILImage, "ROTATE_270", None)
        DITHER_FLOYD = getattr(_PILImage, "FLOYDSTEINBERG", None)
