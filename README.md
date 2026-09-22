# selfbg

Self-hosted background removal for images and video. Made because [remove.bg is shutting down on December 1, 2026](https://www.remove.bg).

Drop images or a short video into the web UI (or hit the API from a script) and get transparent PNGs or WebM back. Everything runs on your own server, no credits, no upload limits and no sending images/videos to a server you don't own.

## What it does

- **Single images** — sync endpoint, wait a few seconds, get a transparent PNG.
- **Batches** — throw 30 photos in at once. They queue up, the UI shows each one's progress live, and you can download them individually or grab the whole batch as a zip.
- **Videos** — MP4 / MOV / WebM / MKV / AVI go in, WebM with a real alpha channel comes out. Plays with transparency in Chrome or Firefox directly. Uses [Robust Video Matting](https://github.com/PeterL1n/RobustVideoMatting) so edges stay stable — no per-frame flickering.
- **remove.bg-compatible API** — if you already have scripts pointing at `api.remove.bg`, swap the base URL and they'll keep working.

---

## Quickstart

You don't need to clone the repo. The images are on GitHub Container Registry.

```bash
mkdir selfbg && cd selfbg

# Grab the compose file and env template
curl -O https://raw.githubusercontent.com/self-bg/selfbg/main/docker-compose.yml
curl -o .env https://raw.githubusercontent.com/self-bg/selfbg/main/.env.example

# Make an API key and put it in .env under SELFBG_API_KEY
openssl rand -hex 32

# Pull and start
docker compose pull
docker compose up -d
```

Open it in a browser: **http://\<host\>:3000**, where `<host>` is `localhost` if you're on the same machine or the host's IP / hostname from any other device on your LAN. The API sits on port `8000` at the same host, and there's auto-generated API docs at `/docs`.

Upgrading later is the same two commands:

```bash
docker compose pull && docker compose up -d
```

If you want to pin a version so an upstream change can't surprise you, set `SELFBG_TAG=v0.3.0` in `.env`.

### Building from source

If you'd rather build the images yourself (contributing, or you just don't want to pull from a public registry):

```bash
git clone https://github.com/self-bg/selfbg
cd selfbg
cp .env.example .env
# set SELFBG_API_KEY in .env
docker compose up -d --build
```

### Running it on Proxmox

There's a full walkthrough for a Proxmox LXC behind Nginx with Cloudflare in [docs/deploy-proxmox.md](docs/deploy-proxmox.md) — LXC creation, sizing, the reverse-proxy config, all of it.

### The ports listen on `0.0.0.0` by default

That means any device on your LAN can reach it once the containers are up. That's fine because the API key is mandatory on every processing endpoint — an unauthenticated request just gets a `401` back, no matter where the port is exposed.

If you'd rather keep the ports on the host only (say, because you're putting a reverse proxy on the same box), set `API_BIND=127.0.0.1:8000` and `WEB_BIND=127.0.0.1:3000` in your `.env`.

### The API key is required

`selfbg` refuses to start without one. It has to be at least 16 characters:

```
SELFBG_API_KEY=<paste the openssl output here>
```

Then every processing endpoint expects that same value in an `X-API-Key` header. The web UI has a field for it and stores it in your browser's `localStorage`, so you're not typing it every time.

---

## Using the API

Three ways to submit work, depending on what you're doing.

### Sync — one image, wait for the answer

```bash
curl -X POST http://localhost:8000/remove \
  -H "X-API-Key: $SELFBG_API_KEY" \
  -F "file=@subject.jpg" \
  -F "model=birefnet-portrait" \
  -o cutout.png
```

Blocks until it's done (~15 seconds per image on the default model, CPU). This is the simplest thing to use for one-off images.

Videos aren't accepted here — you'll get a "use /jobs instead" message.

### remove.bg-compatible — for existing scripts

```bash
curl -X POST http://localhost:8000/v1.0/image-without-background \
  -H "X-API-Key: $SELFBG_API_KEY" \
  -F "image_file=@subject.jpg" \
  -o cutout.png
```

Same URL and request shape as remove.bg's paid API. Anything you already had pointing at `api.remove.bg/v1.0/removebg` should work with just a base-URL swap. Accepts `image_file`, `image_url`, or `image_file_b64`.

### Async — batches and videos

Submit one or many files, get a batch ID, poll each job until it's done, then download.

```bash
# submit
curl -X POST http://localhost:8000/jobs \
  -H "X-API-Key: $SELFBG_API_KEY" \
  -F "files=@photo1.jpg" \
  -F "files=@photo2.jpg" \
  -F "files=@clip.mp4"
# → { "batch_id": "abc123", "jobs": [ ... ] }

# check on a job
curl http://localhost:8000/jobs/<job_id> -H "X-API-Key: $SELFBG_API_KEY"
# → { "status": "queued" | "started" | "finished" | "failed", ... }

# download when it's ready
curl http://localhost:8000/jobs/<job_id>/result \
  -H "X-API-Key: $SELFBG_API_KEY" \
  -o result.png     # or result.webm for videos

# or grab every finished image in the batch as one zip
curl http://localhost:8000/batches/<batch_id>/zip \
  -H "X-API-Key: $SELFBG_API_KEY" \
  -o batch.zip
```

Image and video jobs run on separate internal queues so a long video doesn't hold up the image work.

---

## Choosing a model

### For images

The image side wraps [`rembg`](https://github.com/danielgatis/rembg), which lets you pick between several ONNX matting models. Set `SELFBG_MODEL` in `.env`, or override per-request with a `model` form field.

| Model | Best for | Notes |
|---|---|---|
| `birefnet-general` *(default)* | General subjects, products, animals | Near-SOTA open weights. Highest quality here. |
| `birefnet-general-lite` | Same, but on a smaller box | ~half the memory, still very good. |
| `birefnet-portrait` | People, portraits | Cleaner hair edges than the general models. |
| `u2net` | Anything, fast | Classic. Fast on CPU. Softer edges. |
| `isnet-general-use` | Complex silhouettes | Strong on tricky outlines. |

Full list: https://github.com/danielgatis/rembg#models

### For videos

The video worker uses [Robust Video Matting](https://github.com/PeterL1n/RobustVideoMatting), a model built specifically for video. It threads a hidden state from frame to frame, which is what stops per-frame flickering. The `mobilenetv3` variant is baked into the image for CPU inference — no knob for now, this is what you get.

Output is WebM VP9 with an alpha channel. It plays with transparency in Chrome and Firefox directly. Windows Media Player and most desktop players don't understand alpha video, so if you download a result and want to preview it locally, open it in VLC or a browser.

---

## Compared to the alternatives

| | `selfbg` | [`withoutbg`](https://github.com/withoutbg) | [`rembg`](https://github.com/danielgatis/rembg) | remove.bg |
|---|---|---|---|---|
| **How you run it** | Docker Compose, one command | Docker or SDK | Docker or SDK | Cloud only (going away 2026-12-01) |
| **Web UI** | Included, batch-aware, live progress | Web variant | Community wrappers | Yes |
| **remove.bg-compatible API** | Yes (`/v1.0/image-without-background`) | Yes | No | Yes (going away) |
| **Batch upload + zip download** | Yes | Single-image drag/drop only | CLI only | Yes |
| **Video** | Yes — WebM VP9 alpha | No | No | No |
| **License** | MIT | Apache-2.0 | MIT | Commercial |

I'm not trying to beat `withoutbg` on model quality. `selfbg` uses `rembg` and RVM under the hood — the same libraries a lot of the OSS ecosystem is already built on — and picks the fight on being easy to actually run and use.

---

## Current limits

Things it doesn't do (yet, might add them later):

- **Videos on GPU.** CPU only. That's why the caps are conservative — 30 seconds, 480p by default. Bump those in `.env` if your box can handle it. GPU support is a future addition.
- **Videos over 30 seconds.** Cap is configurable (`SELFBG_MAX_VIDEO_DURATION_SECONDS`), but the default keeps a single job under a couple of minutes on a modest CPU.
- **Any output format for video other than WebM VP9 alpha.** ProRes 4444 for editors may be added if someone asks for it.
- **User accounts, per-user history, anything multi-tenant.** Single shared API key, per-browser job history.

---

## Architecture

```
                  ┌──────────────┐   /api/*    ┌────────────────────────┐
    browser ────▶ │    web       │ ──rewrite▶ │       api (FastAPI)    │
                  │  (Next.js)   │             │  sync /remove          │
                  └──────────────┘             │  async /jobs           │
                       :3000                    │  remove.bg /v1.0/…     │
                                                └────────────┬───────────┘
                                                              │
                                                    enqueue  │  poll
                                                              ▼
                                                       ┌──────────┐
                                                       │  redis   │◀──── auto-expire job records
                                                       └────┬─────┘
                                                            │
                                       ┌────────────────────┼───────────────────────┐
                                       ▼                     ▼                       ▼
                            ┌────────────────┐    ┌──────────────────┐     ┌───────────────┐
                            │     worker     │    │  video-worker    │     │    cleaner    │
                            │  rembg / ONNX  │    │  RVM + FFmpeg    │     │  disk sweep   │
                            └────────────────┘    └──────────────────┘     └───────────────┘
                                       └──────── shared job-data volume ───────┘
```

Six services:

| Service | What it does |
|---|---|
| `web` | Next.js. Serves the UI and proxies `/api/*` to `api`. |
| `api` | FastAPI. Handles uploads, enqueues jobs, serves results. |
| `worker` | Image job runner. Pulls from the `default` queue, runs `rembg`. |
| `video-worker` | Video job runner. Pulls from the `video` queue, runs RVM through FFmpeg. |
| `redis` | Backs the job queue and job metadata. Not exposed on any host port. |
| `cleaner` | Sweeps expired job folders off disk on a loop. |

- **Backend:** FastAPI, `rembg`, RVM (ONNX Runtime), FFmpeg, RQ, Pillow, `pydantic-settings`.
- **Frontend:** Next.js 15 App Router, React 19, Tailwind v4, TypeScript strict. Standalone Node output for a small production image.
- **Deployment:** Docker Compose. `web` proxies `/api/*` to `api` internally, so from the browser's point of view everything is same-origin.
- **Persistence:** Named volumes for the model cache, Redis data, and job files. Job files auto-expire after `SELFBG_RESULT_TTL_SECONDS` (24 h default).
- **Security:** API key is mandatory (server won't start without one). Uploads capped at 25 MB for images / 200 MB for videos, and the size check happens before decoding. Only common raster and video types get through the door. Ports bind to `0.0.0.0` by default — the key stays mandatory, so exposure ≠ leak.

---

## Development

Backend without Docker:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
export SELFBG_API_KEY=$(openssl rand -hex 32)
uvicorn app.main:app --reload
```

The workers and cleaner are individual scripts. Run whichever ones you need:

```bash
python -m app.workers.image      # image job runner
python -m app.workers.video      # video job runner (needs ffmpeg installed)
python -m app.workers.cleaner    # data folder sweeper
```

Frontend without Docker:

```bash
cd frontend
npm install
SELFBG_API_ORIGIN=http://localhost:8000 npm run dev
```

---

## License

MIT (c) 2026 Farhad Ahmed. See [LICENSE](./LICENSE).

Model weights are downloaded on demand and licensed by their respective authors — see [rembg](https://github.com/danielgatis/rembg) and [Robust Video Matting](https://github.com/PeterL1n/RobustVideoMatting).
