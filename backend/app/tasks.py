"""RQ tasks. Kept as top-level functions with simple, serialisable arguments
so RQ can enqueue them and the worker can call them."""

from __future__ import annotations

from .matting import remove_background


def process_image(image_bytes: bytes, model_name: str | None = None) -> bytes:
    return remove_background(image_bytes, model_name=model_name)
