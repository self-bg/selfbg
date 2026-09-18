"""The sync /remove endpoint — send one image and wait for the cutout in
the same request. Videos aren't supported here; use POST /jobs for those."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response

from ..auth import require_api_key
from ..matting import remove_background
from ..upload import read_upload

router = APIRouter(tags=["remove"])


@router.post(
    "/remove",
    responses={200: {"content": {"image/png": {}}}},
    dependencies=[Depends(require_api_key)],
)
async def remove_endpoint(
    file: UploadFile = File(..., description="Image to process."),
    model: str | None = Form(default=None, description="Override rembg model name."),
) -> Response:
    body, kind = await read_upload(file)
    if kind != "image":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The /remove endpoint only accepts images. Use POST /jobs for videos.",
        )
    try:
        png = remove_background(body, model_name=model)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to process image: {exc}",
        ) from exc
    return Response(content=png, media_type="image/png")
