"""Upload validation — content-type whitelist and size cap, before any decode."""

import io

import pytest
from fastapi import HTTPException
from fastapi.datastructures import UploadFile
from starlette.datastructures import Headers

from app.config import get_settings
from app.upload import read_upload


def make_upload(content: bytes, content_type: str, filename: str = "x") -> UploadFile:
    return UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


async def test_accepts_image_jpeg():
    body, kind = await read_upload(make_upload(b"jpeg-bytes", "image/jpeg"))
    assert body == b"jpeg-bytes"
    assert kind == "image"


@pytest.mark.parametrize(
    "mime",
    ["image/png", "image/webp", "image/tiff", "image/bmp"],
)
async def test_accepts_other_image_types(mime: str):
    _, kind = await read_upload(make_upload(b"data", mime))
    assert kind == "image"


@pytest.mark.parametrize(
    "mime",
    ["video/mp4", "video/quicktime", "video/webm", "video/x-matroska", "video/x-msvideo"],
)
async def test_accepts_video_types(mime: str):
    _, kind = await read_upload(make_upload(b"data", mime))
    assert kind == "video"


@pytest.mark.parametrize(
    "mime", ["application/pdf", "text/html", "audio/mpeg", "application/zip"]
)
async def test_rejects_unknown_type(mime: str):
    with pytest.raises(HTTPException) as exc:
        await read_upload(make_upload(b"data", mime))
    assert exc.value.status_code == 415


async def test_rejects_empty_upload():
    with pytest.raises(HTTPException) as exc:
        await read_upload(make_upload(b"", "image/jpeg"))
    assert exc.value.status_code == 400


async def test_rejects_oversize_image(monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    oversize = b"x" * (2 * 1024 * 1024)  # 2 MB
    with pytest.raises(HTTPException) as exc:
        await read_upload(make_upload(oversize, "image/jpeg"))
    assert exc.value.status_code == 413


async def test_video_uses_separate_limit(monkeypatch):
    """A 30 MB video is fine even when the image limit is 25 MB."""
    monkeypatch.setattr(get_settings(), "max_upload_mb", 25)
    monkeypatch.setattr(get_settings(), "max_video_upload_mb", 200)
    thirty_mb = b"x" * (30 * 1024 * 1024)
    _, kind = await read_upload(make_upload(thirty_mb, "video/mp4"))
    assert kind == "video"
