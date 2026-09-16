from __future__ import annotations

import base64
import binascii

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response

from ..auth import require_api_key
from ..config import get_settings
from ..matting import remove_background

router = APIRouter(prefix="/v1.0", tags=["remove.bg-compatible"])


async def _fetch_url(url: str) -> bytes:
    limit = get_settings().max_upload_bytes
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not fetch image_url: {exc}",
            ) from exc
    if len(resp.content) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fetched image exceeds {get_settings().max_upload_mb} MB limit.",
        )
    return resp.content


@router.post(
    "/image-without-background",
    responses={200: {"content": {"image/png": {}}}},
    dependencies=[Depends(require_api_key)],
)
async def image_without_background(
    image_file: UploadFile | None = File(default=None),
    image_url: str | None = Form(default=None),
    image_file_b64: str | None = Form(default=None),
    size: str | None = Form(default=None),
    format: str | None = Form(default="png"),
) -> Response:
    """Drop-in for remove.bg's POST /v1.0/removebg.

    Accepts exactly one of image_file / image_url / image_file_b64. Ignores
    size / bg_color / channels for now — parity with the free tier is enough
    to let existing scripts point at this service without code changes.
    """
    provided = sum(bool(x) for x in (image_file, image_url, image_file_b64))
    if provided != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of image_file, image_url, image_file_b64.",
        )

    if image_file is not None:
        body = await image_file.read(get_settings().max_upload_bytes + 1)
        if len(body) > get_settings().max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {get_settings().max_upload_mb} MB limit.",
            )
    elif image_url is not None:
        body = await _fetch_url(image_url)
    else:
        assert image_file_b64 is not None
        try:
            body = base64.b64decode(image_file_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64: {exc}",
            ) from exc
        if len(body) > get_settings().max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Decoded image exceeds {get_settings().max_upload_mb} MB limit.",
            )

    if format and format.lower() != "png":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PNG output is supported in v1.",
        )

    try:
        png = remove_background(body)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to process image: {exc}",
        ) from exc
    return Response(content=png, media_type="image/png")
