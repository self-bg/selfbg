"""Checks on uploaded files. Makes sure the file is a supported image
or video type and not too big, before any endpoint uses it."""

from __future__ import annotations

from fastapi import HTTPException, UploadFile, status

from .config import get_settings

IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
    "image/bmp",
}

VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",  # .mov
    "video/webm",
    "video/x-matroska",  # .mkv
    "video/x-msvideo",   # .avi
}

ACCEPTED_TYPES = IMAGE_TYPES | VIDEO_TYPES


def is_video(content_type: str | None) -> bool:
    return bool(content_type and content_type in VIDEO_TYPES)


async def read_upload(file: UploadFile) -> tuple[bytes, str]:
    """Read the upload, enforce size and type limits, and return the bytes
    along with the kind — either "image" or "video".
    """
    content_type = file.content_type or ""
    if content_type not in ACCEPTED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {content_type or 'unknown'}",
        )

    settings = get_settings()
    kind = "video" if content_type in VIDEO_TYPES else "image"
    limit_bytes = settings.max_video_upload_bytes if kind == "video" else settings.max_upload_bytes
    limit_mb = settings.max_video_upload_mb if kind == "video" else settings.max_upload_mb

    body = await file.read(limit_bytes + 1)
    if len(body) > limit_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{kind.title()} exceeds {limit_mb} MB limit.",
        )
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    return body, kind
