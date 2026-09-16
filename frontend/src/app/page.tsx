import Uploader from "@/components/Uploader";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      <header className="mb-10">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          selfbg
        </h1>
        <p className="mt-2 max-w-2xl text-[color:var(--color-text-dim)]">
          Self-hosted background removal. Upload an image, get a transparent
          PNG back. Nothing leaves your network.
        </p>
      </header>

      <Uploader />

      <footer className="mt-16 flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--color-border)] pt-6 text-sm text-[color:var(--color-text-dim)]">
        <span>
          A drop-in replacement for remove.bg — see the docs at{" "}
          <code className="rounded bg-[color:var(--color-panel-2)] px-1.5 py-0.5">
            /api/docs
          </code>
          .
        </span>
        <a
          className="hover:text-[color:var(--color-accent)]"
          href="https://github.com/self-bg/selfbg"
          target="_blank"
          rel="noreferrer"
        >
          github.com/self-bg/selfbg
        </a>
      </footer>
    </main>
  );
}
