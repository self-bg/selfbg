"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const ACCEPT = "image/png,image/jpeg,image/webp,image/tiff,image/bmp";
const MAX_MB = 25;
const API_KEY_STORAGE = "selfbg.apiKey";

type Status = "idle" | "loading" | "done" | "error";

export default function Uploader() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(API_KEY_STORAGE);
      if (saved) setApiKey(saved);
    } catch {
      /* localStorage may be blocked in private mode */
    }
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      if (resultUrl) URL.revokeObjectURL(resultUrl);
    };
  }, [previewUrl, resultUrl]);

  const persistKey = (value: string) => {
    setApiKey(value);
    try {
      if (value) localStorage.setItem(API_KEY_STORAGE, value);
      else localStorage.removeItem(API_KEY_STORAGE);
    } catch {
      /* ignore */
    }
  };

  const chooseFile = useCallback((next: File | null) => {
    setError(null);
    setStatus("idle");
    setResultUrl((old) => {
      if (old) URL.revokeObjectURL(old);
      return null;
    });
    if (!next) {
      setFile(null);
      setPreviewUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return null;
      });
      return;
    }
    if (!ACCEPT.split(",").includes(next.type)) {
      setError(`Unsupported file type: ${next.type || "unknown"}.`);
      return;
    }
    if (next.size > MAX_MB * 1024 * 1024) {
      setError(`File is ${(next.size / 1024 / 1024).toFixed(1)} MB — max is ${MAX_MB} MB.`);
      return;
    }
    setFile(next);
    setPreviewUrl((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(next);
    });
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragOver(false);
      const dropped = event.dataTransfer.files?.[0] ?? null;
      chooseFile(dropped);
    },
    [chooseFile],
  );

  const submit = useCallback(async () => {
    if (!file) return;
    setStatus("loading");
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const resp = await fetch("/api/remove", {
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
          /* body may not be JSON */
        }
        setError(detail);
        setStatus("error");
        return;
      }
      const blob = await resp.blob();
      setResultUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return URL.createObjectURL(blob);
      });
      setStatus("done");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setStatus("error");
    }
  }, [file, apiKey]);

  const downloadName = file
    ? `${file.name.replace(/\.[^.]+$/, "")}-cutout.png`
    : "cutout.png";

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
          Drop an image here, or click to choose
        </p>
        <p className="mt-1 text-sm text-[color:var(--color-text-dim)]">
          PNG, JPEG, WebP, TIFF, or BMP — up to {MAX_MB} MB
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => chooseFile(e.target.files?.[0] ?? null)}
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

      {file && (
        <div className="grid gap-4 sm:grid-cols-2">
          <figure className="overflow-hidden rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-panel)]">
            <figcaption className="border-b border-[color:var(--color-border)] px-3 py-2 text-xs uppercase tracking-wide text-[color:var(--color-text-dim)]">
              Original
            </figcaption>
            {previewUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={previewUrl} alt="Original" className="max-h-96 w-full object-contain p-3" />
            )}
          </figure>
          <figure className="checkerboard overflow-hidden rounded-xl border border-[color:var(--color-border)]">
            <figcaption className="border-b border-[color:var(--color-border)] bg-[color:var(--color-panel)] px-3 py-2 text-xs uppercase tracking-wide text-[color:var(--color-text-dim)]">
              Result
            </figcaption>
            <div className="flex min-h-[8rem] items-center justify-center p-3">
              {status === "loading" && (
                <span className="text-sm text-[color:var(--color-text-dim)]">
                  Processing…
                </span>
              )}
              {resultUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={resultUrl} alt="Cutout" className="max-h-96 w-full object-contain" />
              )}
              {status === "idle" && !resultUrl && (
                <span className="text-sm text-[color:var(--color-text-dim)]">
                  Press <em>Remove background</em> to run.
                </span>
              )}
            </div>
          </figure>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={submit}
          disabled={!file || status === "loading"}
          className="rounded-lg bg-[color:var(--color-accent)] px-5 py-2 font-medium text-black transition-colors hover:bg-[color:var(--color-accent-hi)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {status === "loading" ? "Processing…" : "Remove background"}
        </button>
        {resultUrl && (
          <a
            href={resultUrl}
            download={downloadName}
            className="rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-panel)] px-5 py-2 text-sm hover:border-[color:var(--color-accent)]"
          >
            Download PNG
          </a>
        )}
        {file && (
          <button
            type="button"
            onClick={() => chooseFile(null)}
            className="text-sm text-[color:var(--color-text-dim)] hover:text-[color:var(--color-text)]"
          >
            Reset
          </button>
        )}
      </div>
    </section>
  );
}
