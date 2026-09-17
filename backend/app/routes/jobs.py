"""The async job endpoints — submit an image, get a job ID back, poll for
status, download the result when it's done.

    POST /jobs                    submit one or more images, get back job IDs
    GET  /jobs/{job_id}           current status of a job
    GET  /jobs/{job_id}/result    the finished PNG (once the job is done)
    GET  /batches/{batch_id}      status of every job submitted together
    GET  /batches/{batch_id}/zip  every finished cutout in the batch as one zip
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from stat import S_IFREG
from typing import Iterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from stream_zip import NO_COMPRESSION_64, stream_zip

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

ZIP_CHUNK_BYTES = 65536


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


@router.get(
    "/batches/{batch_id}/zip",
    dependencies=[Depends(require_api_key)],
    responses={200: {"content": {"application/zip": {}}}},
)
async def download_batch_zip(batch_id: str) -> StreamingResponse:
    jobs = get_batch(batch_id)
    if jobs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Batch not found.")

    pending = [j for j in jobs if j.status not in ("finished", "failed")]
    if pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"{len(pending)} of {len(jobs)} jobs are still processing.",
        )

    finished = sorted(
        (j for j in jobs if j.status == "finished"),
        key=lambda j: j.created_at,
    )
    if not finished:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No finished results in this batch.",
        )

    modified = datetime.now(timezone.utc)
    perms = S_IFREG | 0o600
    width = len(str(len(finished)))

    def _read_chunks(path: Path) -> Iterator[bytes]:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(ZIP_CHUNK_BYTES)
                if not chunk:
                    return
                yield chunk

    def _entries():
        for index, job in enumerate(finished, start=1):
            path = result_path(job.id)
            if not path.exists():
                continue
            base = Path(job.filename).stem or job.id
            name = f"{index:0{width}d}-{base}-cutout.png"
            yield (name, modified, perms, NO_COMPRESSION_64, _read_chunks(path))

    return StreamingResponse(
        stream_zip(_entries()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="selfbg-{batch_id}.zip"',
        },
    )
