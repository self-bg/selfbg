"""The async job endpoints — submit an image, get a job ID back, poll for
status, download the result when it's done.

    POST /jobs                 submit one or more images, get back job IDs
    GET  /jobs/{job_id}        current status of a job
    GET  /jobs/{job_id}/result the finished PNG (once the job is done)
    GET  /batches/{batch_id}   status of every job submitted together
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from ..auth import require_api_key
from ..jobs import (
    enqueue_job,
    get_batch,
    get_job,
    input_path,
    job_dir,
    new_id,
    result_path,
)
from ..upload import read_upload

router = APIRouter(tags=["jobs"])


@router.post(
    "/jobs",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
)
async def create_jobs(
    files: list[UploadFile] = File(..., description="One or more images to process."),
    model: str | None = Form(default=None, description="Override rembg model name."),
) -> dict:
    batch_id = new_id()
    submitted: list[dict[str, str]] = []

    for f in files:
        body = await read_upload(f)
        job_id = new_id()
        d = job_dir(job_id)
        d.mkdir(parents=True, exist_ok=True)
        suffix = Path(f.filename or "").suffix or ".bin"
        input_path(job_id, suffix).write_bytes(body)
        enqueue_job(
            job_id,
            filename=f.filename or "",
            batch_id=batch_id,
            model_name=model,
        )
        submitted.append({"job_id": job_id, "filename": f.filename or ""})

    return {"batch_id": batch_id, "jobs": submitted}


@router.get("/jobs/{job_id}", dependencies=[Depends(require_api_key)])
async def read_job(job_id: str) -> dict:
    j = get_job(job_id)
    if j is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return j.to_dict()


@router.get(
    "/jobs/{job_id}/result",
    dependencies=[Depends(require_api_key)],
    responses={200: {"content": {"image/png": {}}}},
)
async def read_job_result(job_id: str) -> FileResponse:
    j = get_job(job_id)
    if j is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if j.status == "failed":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=j.error or "Job failed.",
        )
    if j.status != "finished":
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Job is {j.status}.")
    path = result_path(job_id)
    if not path.exists():
        raise HTTPException(status.HTTP_410_GONE, detail="Result no longer available.")
    stem = Path(j.filename).stem or "cutout"
    return FileResponse(path, media_type="image/png", filename=f"{stem}-cutout.png")


@router.get("/batches/{batch_id}", dependencies=[Depends(require_api_key)])
async def read_batch(batch_id: str) -> dict:
    jobs = get_batch(batch_id)
    if jobs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Batch not found.")
    return {"batch_id": batch_id, "jobs": [j.to_dict() for j in jobs]}
