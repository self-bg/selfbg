"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import JobCard, { type Job } from "./JobCard";

const ACCEPT = "image/png,image/jpeg,image/webp,image/tiff,image/bmp";
const ACCEPT_SET = new Set(ACCEPT.split(","));
const MAX_MB = 25;
const API_KEY_STORAGE = "selfbg.apiKey";
const POLL_MS = 1000;

type Batch = {
  id: string;
  jobs: Job[];
};

type SubmittedJob = { job_id: string; filename: string };
type CreateResponse = { batch_id: string; jobs: SubmittedJob[] };

export default function Uploader() {
  const [apiKey, setApiKey] = useState("");
  const [batches, setBatches] = useState<Batch[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadingBatchId, setDownloadingBatchId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const batchesRef = useRef<Batch[]>([]);

  useEffect(() => {
    batchesRef.current = batches;
  }, [batches]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(API_KEY_STORAGE);
      if (saved) setApiKey(saved);
    } catch {
      /* localStorage may be blocked in private mode */
    }
  }, []);

  const persistKey = (value: string) => {
    setApiKey(value);
    try {
      if (value) localStorage.setItem(API_KEY_STORAGE, value);
      else localStorage.removeItem(API_KEY_STORAGE);
    } catch {
      /* ignore */
    }
  };

  const validate = (files: File[]): string | null => {
    for (const f of files) {
      if (!ACCEPT_SET.has(f.type)) {
        return `Unsupported file type: ${f.name} (${f.type || "unknown"})`;
      }
      if (f.size > MAX_MB * 1024 * 1024) {
        return `${f.name} is ${(f.size / 1024 / 1024).toFixed(1)} MB — max is ${MAX_MB} MB`;
      }
    }
    return null;
  };

  const submit = useCallback(
    async (files: File[]) => {
      if (!files.length) return;
      const validationError = validate(files);
      if (validationError) {
        setError(validationError);
        return;
      }
      setSubmitting(true);
      setError(null);

      const form = new FormData();
      for (const f of files) form.append("files", f);

      try {
        const resp = await fetch("/api/jobs", {
          method: "POST",
          body: form,
          headers: apiKey ? { "X-API-Key": apiKey } : undefined,
        });
        if (!resp.ok) {
          let detail = `Request failed with ${resp.status}`;
          try {
            const body = await resp.json();
            if (body?.detail) detail = String(body.detail);
          } catch {
            /* not JSON */
          }
          setError(detail);
          return;
        }
        const data: CreateResponse = await resp.json();
        const nowIso = new Date().toISOString();
        const jobs: Job[] = data.jobs.map((j) => ({
          id: j.job_id,
          filename: j.filename,
          status: "queued",
          batch_id: data.batch_id,
          model: "",
          created_at: nowIso,
          started_at: null,
          ended_at: null,
          error: null,
        }));
        setBatches((prev) => [{ id: data.batch_id, jobs }, ...prev]);
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : String(exc));
      } finally {
        setSubmitting(false);
      }
    },
    [apiKey],
  );

  // Poll every second. If nothing is pending, the tick returns immediately.
  useEffect(() => {
    const tick = async () => {
      const pending = batchesRef.current.filter((b) =>
        b.jobs.some((j) => j.status !== "finished" && j.status !== "failed"),
      );
      if (!pending.length) return;
      for (const batch of pending) {
        try {
          const r = await fetch(`/api/batches/${batch.id}`, {
            headers: apiKey ? { "X-API-Key": apiKey } : undefined,
          });
          if (!r.ok) continue;
          const data: { batch_id: string; jobs: Job[] } = await r.json();
          setBatches((prev) =>
            prev.map((b) => (b.id === batch.id ? { id: batch.id, jobs: data.jobs } : b)),
          );
        } catch {
          /* transient — try again next tick */
        }
      }
    };
    const id = window.setInterval(tick, POLL_MS);
    return () => window.clearInterval(id);
  }, [apiKey]);

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragOver(false);
      const dropped = Array.from(event.dataTransfer.files ?? []);
      submit(dropped);
    },
    [submit],
  );

  const onPick = useCallback(
    (files: FileList | null) => {
      if (!files) return;
      submit(Array.from(files));
    },
    [submit],
  );

  const clearBatch = (batchId: string) => {
    setBatches((prev) => prev.filter((b) => b.id !== batchId));
  };

  const downloadZip = useCallback(
    async (batchId: string) => {
      setDownloadingBatchId(batchId);
      setError(null);
      try {
        const resp = await fetch(`/api/batches/${batchId}/zip`, {
          headers: apiKey ? { "X-API-Key": apiKey } : undefined,
        });
        if (!resp.ok) {
          let detail = `Download failed with ${resp.status}`;
          try {
            const body = await resp.json();
            if (body?.detail) detail = String(body.detail);
          } catch {
            /* not JSON */
          }
          setError(detail);
          return;
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `selfbg-${batchId}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        // Small delay so the browser has a chance to start the download before
        // we revoke the object URL.
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : String(exc));
      } finally {
        setDownloadingBatchId(null);
      }
    },
    [apiKey],
  );

  return (
    <section className="space-y-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
          dragOver
            ? "border-[color:var(--color-accent)] bg-[color:var(--color-panel-2)]"
            : "border-[color:var(--color-border)] bg-[color:var(--color-panel)] hover:border-[color:var(--color-accent)]"
        }`}
      >
        <p className="text-lg font-medium">
          {submitting ? "Uploading…" : "Drop images here, or click to choose"}
        </p>
        <p className="mt-1 text-sm text-[color:var(--color-text-dim)]">
          PNG, JPEG, WebP, TIFF, or BMP — up to {MAX_MB} MB each. Multiple files at once are fine.
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          className="hidden"
          onChange={(e) => onPick(e.target.files)}
        />
      </div>

      <details
        open={!apiKey}
        className="rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-panel)] px-4 py-3 text-sm"
      >
        <summary className="cursor-pointer text-[color:var(--color-text-dim)]">
          API key {apiKey ? "(stored in this browser)" : "— required"}
        </summary>
        <input
          type="password"
          autoComplete="off"
          value={apiKey}
          onChange={(e) => persistKey(e.target.value)}
          placeholder="X-API-Key header value"
          className="mt-3 w-full rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-panel-2)] px-3 py-2 outline-none focus:border-[color:var(--color-accent)]"
        />
      </details>

      {error && (
        <div className="rounded-xl border border-[color:var(--color-danger)]/50 bg-[color:var(--color-danger)]/10 px-4 py-3 text-sm text-[color:var(--color-danger)]">
          {error}
        </div>
      )}

      {batches.map((batch) => {
        const doneCount = batch.jobs.filter(
          (j) => j.status === "finished" || j.status === "failed",
        ).length;
        const allDone = doneCount === batch.jobs.length;
        const anyFinished = batch.jobs.some((j) => j.status === "finished");
        const canDownloadZip = allDone && anyFinished && batch.jobs.length > 1;
        const isDownloading = downloadingBatchId === batch.id;

        return (
          <div key={batch.id} className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs uppercase tracking-wide text-[color:var(--color-text-dim)]">
              <span>
                Batch of {batch.jobs.length} — {doneCount} done
              </span>
              <div className="flex items-center gap-3">
                {canDownloadZip && (
                  <button
                    type="button"
                    onClick={() => downloadZip(batch.id)}
                    disabled={isDownloading}
                    className="rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-panel-2)] px-3 py-1 normal-case tracking-normal text-[color:var(--color-text)] hover:border-[color:var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {isDownloading ? "Downloading…" : "Download all as zip"}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => clearBatch(batch.id)}
                  className="hover:text-[color:var(--color-text)]"
                >
                  Clear
                </button>
              </div>
            </div>
            <div className="space-y-2">
              {batch.jobs.map((job) => (
                <JobCard key={job.id} job={job} apiKey={apiKey} />
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}
