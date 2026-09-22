"use client";

import { useEffect, useState } from "react";

export type Job = {
  id: string;
  job_type: string;
  filename: string;
  status: string;
  batch_id: string | null;
  model: string;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  error: string | null;
};

type Props = {
  job: Job;
};

const STATUS_LABEL: Record<string, string> = {
  queued: "Waiting…",
  started: "Processing…",
  finished: "Done",
  failed: "Failed",
};

export default function JobCard({ job }: Props) {
  const [resultUrl, setResultUrl] = useState<string | null>(null);

  // Fetch the result as a blob once the job finishes so we can control the
  // URL lifecycle and swap the preview in cleanly.
  useEffect(() => {
    if (job.status !== "finished") {
      setResultUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return null;
      });
      return;
    }

    let cancelled = false;
    let localUrl: string | null = null;

    fetch(`/api/jobs/${job.id}/result`)
      .then((r) => {
        if (!r.ok) throw new Error(`Fetch failed: ${r.status}`);
        return r.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        localUrl = URL.createObjectURL(blob);
        setResultUrl(localUrl);
      })
      .catch(() => {
        // Result may already have been cleaned up on the server; just skip.
      });

    return () => {
      cancelled = true;
      if (localUrl) URL.revokeObjectURL(localUrl);
    };
  }, [job.status, job.id]);

  const isVideo = job.job_type === "video";
  const ext = isVideo ? "webm" : "png";
  const downloadName = job.filename
    ? `${job.filename.replace(/\.[^.]+$/, "")}-cutout.${ext}`
    : `${job.id}-cutout.${ext}`;

  const label = STATUS_LABEL[job.status] ?? job.status;
  const isFailed = job.status === "failed";
  const isProcessing = job.status === "started" || job.status === "queued";

  return (
    <div className="flex items-center gap-3 rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-panel)] p-3">
      <div className="checkerboard flex h-20 w-20 flex-none items-center justify-center overflow-hidden rounded-lg border border-[color:var(--color-border)]">
        {resultUrl ? (
          isVideo ? (
            <video
              src={resultUrl}
              muted
              loop
              autoPlay
              playsInline
              className="h-full w-full object-contain"
            />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={resultUrl} alt="" className="h-full w-full object-contain" />
          )
        ) : isProcessing ? (
          <span className="text-xs text-[color:var(--color-text-dim)]">…</span>
        ) : isFailed ? (
          <span className="text-lg text-[color:var(--color-danger)]">!</span>
        ) : (
          <span className="text-xs text-[color:var(--color-text-dim)]">·</span>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="truncate font-medium">{job.filename || job.id}</div>
        <div className="mt-0.5 flex flex-wrap gap-x-2 text-xs text-[color:var(--color-text-dim)]">
          <span className={isFailed ? "text-[color:var(--color-danger)]" : undefined}>
            {label}
          </span>
          {job.error && (
            <span className="text-[color:var(--color-danger)] truncate">
              {job.error}
            </span>
          )}
        </div>
      </div>

      {resultUrl && (
        <a
          href={resultUrl}
          download={downloadName}
          className="rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-panel-2)] px-3 py-1.5 text-xs hover:border-[color:var(--color-accent)]"
        >
          Download
        </a>
      )}
    </div>
  );
}
