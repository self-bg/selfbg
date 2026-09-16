from __future__ import annotations

from functools import lru_cache
from io import BytesIO

from PIL import Image
from rembg import new_session, remove

from .config import get_settings


@lru_cache(maxsize=4)
def _session(model_name: str):
    return new_session(model_name)


def warmup() -> None:
    _session(get_settings().model)


def remove_background(image_bytes: bytes, model_name: str | None = None) -> bytes:
    model = model_name or get_settings().model
    with Image.open(BytesIO(image_bytes)) as src:
        src.load()
        cutout = remove(src, session=_session(model))
        buf = BytesIO()
        cutout.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
