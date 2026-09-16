from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response

from ..auth import require_api_key
from ..config import get_settings
from ..matting import remove_background

router = APIRouter(tags=["remove"])

ACCEPTED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
    "image/bmp",
}


async def _read_upload(file: UploadFile) -> bytes:
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


@router.post(
    "/remove",
    responses={200: {"content": {"image/png": {}}}},
    dependencies=[Depends(require_api_key)],
)
async def remove_endpoint(
    file: UploadFile = File(..., description="Image to process."),
    model: str | None = Form(default=None, description="Override rembg model name."),
) -> Response:
    body = await _read_upload(file)
    try:
        png = remove_background(body, model_name=model)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to process image: {exc}",
        ) from exc
    return Response(content=png, media_type="image/png")
