"""Checks on uploaded files. Makes sure the file is a supported image
type and not too big before any endpoint uses it."""

from __future__ import annotations

from fastapi import HTTPException, UploadFile, status

from .config import get_settings

ACCEPTED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
    "image/bmp",
}


async def read_upload(file: UploadFile) -> bytes:
    if file.content_type and file.content_type not in ACCEPTED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {file.content_type}",
        )
    limit = get_settings().max_upload_bytes
    body = await file.read(limit + 1)
    if len(body) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {get_settings().max_upload_mb} MB limit.",
        )
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    return body
