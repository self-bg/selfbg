# selfbg

Self-hosted background removal. A drop-in replacement for [remove.bg](https://www.remove.bg), which is [shutting down as a standalone service on December 1, 2026](https://www.remove.bg).

Upload an image, get a transparent PNG back. Runs on your own hardware, keeps your data on your own network. No credits, no rate limits you didn't set yourself, no third party in the loop.

> **Status:** v0.1 (Phase 1). Single-image sync API + web UI. Batch, video, and Immich integration on the roadmap below.

---

## Quickstart

You don't need to clone the repo — the images are published on GitHub Container Registry.

```bash
mkdir selfbg && cd selfbg

# Pull the compose file and env template
curl -O https://raw.githubusercontent.com/self-bg/selfbg/main/docker-compose.yml
curl -o .env https://raw.githubusercontent.com/self-bg/selfbg/main/.env.example

# Generate an API key and paste it into .env under SELFBG_API_KEY
openssl rand -hex 32

# Pull the images and start
docker compose pull
docker compose up -d
```

Open http://localhost:3000. The API is at http://localhost:8000; auto-generated OpenAPI docs at http://localhost:8000/docs.

To upgrade later:

```bash
docker compose pull && docker compose up -d
```

Pin a version by setting `SELFBG_TAG=v0.1.0` in `.env` so an upstream regression can't break your instance on the next pull.

### Building from source instead

If you'd rather build the images locally (contributing, or you don't want to pull from a public registry):

```bash
git clone https://github.com/self-bg/selfbg
cd selfbg
cp .env.example .env
# set SELFBG_API_KEY in .env
docker compose up -d --build
```

### Deploying on Proxmox

There's a full walkthrough for Proxmox + Nginx + Cloudflare in [docs/deploy-proxmox.md](docs/deploy-proxmox.md), including the LXC creation script, sizing recommendations, and the reverse-proxy config.

### Bindings default to `0.0.0.0`

Out of the box `selfbg` listens on every network interface of the host, so any device on your LAN can reach it once the containers are up. The API key is mandatory on every processing endpoint regardless of where the port is bound, so accidental network exposure never leaks anything — an unauthenticated request just gets a `401`.

To lock the ports to the host only (e.g. because a reverse proxy sits on the same box and you don't want the raw ports on the LAN), set `API_BIND=127.0.0.1:8000` and `WEB_BIND=127.0.0.1:3000` in `.env`.

### API key (required)

`selfbg` refuses to start without an API key of at least 16 characters. Generate one with `openssl rand -hex 32` and put it in `.env`:

```
SELFBG_API_KEY=<paste it here>
```

Every processing endpoint then requires the client to send:

```
X-API-Key: <the same value>
```

The web UI has a field for this — the key is stored in your browser's `localStorage` so you don't have to paste it on every visit.

---

## Using the API

### remove.bg-compatible endpoint

```bash
curl -X POST http://localhost:8000/v1.0/image-without-background \
  -H "X-API-Key: $SELFBG_API_KEY" \
  -F "image_file=@subject.jpg" \
  -o cutout.png
```

Existing scripts written against remove.bg's `POST /v1.0/removebg` need only their base URL swapped. Accepts `image_file`, `image_url`, or `image_file_b64` — same contract, minus paid-tier fields we don't need.

### Native endpoint

```bash
curl -X POST http://localhost:8000/remove \
  -H "X-API-Key: $SELFBG_API_KEY" \
  -F "file=@subject.jpg" \
  -F "model=birefnet-portrait" \
  -o cutout.png
```

The `model` field is optional; when omitted, the server default (`SELFBG_MODEL`) is used.

---

## Choosing a model

`selfbg` wraps [`rembg`](https://github.com/danielgatis/rembg), which supports a family of ONNX matting models. Change `SELFBG_MODEL` in `.env` and rebuild the API image, or override per-request via the `model` form field.

| Model | Best for | Notes |
|---|---|---|
| `birefnet-general` *(default)* | General subjects, products, animals | Near-SOTA open weights. Highest quality option here. |
| `birefnet-general-lite` | Same, on smaller machines | ~half the memory, still very good. |
| `birefnet-portrait` | People, portraits | Cleaner hair edges than general models. |
| `u2net` | Anything, quickly | Classic. Fast on CPU. Older architecture, softer edges. |
| `isnet-general-use` | Complex silhouettes | Strong on tricky outlines. |

Full list: https://github.com/danielgatis/rembg#models

---

## Compared to the alternatives

| | `selfbg` | [`withoutbg`](https://github.com/withoutbg) | [`rembg`](https://github.com/danielgatis/rembg) | remove.bg |
|---|---|---|---|---|
| **Deployment** | Docker Compose, one command | Docker or SDK | Docker or SDK | Cloud only (shutting down 2026-12-01) |
| **Web UI** | Included | Web variant | Community wrappers | Yes |
| **remove.bg-compatible API** | Yes — `/v1.0/image-without-background` | Yes | No | Yes (going away) |
| **Batch upload** | Roadmap (v1.1) | Single-image drag/drop only | CLI only | Yes |
| **Video** | Roadmap (v2.0, RVM) | No | No | No |
| **Immich integration** | Roadmap (v1.2) | No | No | No |
| **Model quality** | Depends on chosen rembg model | High (DINOv3-based) | Depends on chosen model | High |
| **License** | MIT | Apache-2.0 | MIT | Commercial |

`selfbg` doesn't try to beat `withoutbg` on model quality. It uses `rembg` under the hood — the same library much of the OSS ecosystem is built on — and competes on being easy to run on your own hardware, with the integrations self-hosters actually use.

---

## Roadmap

Every phase ships as a public release rather than a big-bang launch.

- [x] **v0.1 — Core.** Web UI, sync API (native + remove.bg-compatible), Docker Compose, MIT.
- [ ] **v1.1 — Batch + queue.** Multi-image upload, Redis + RQ task queue, progress bar, "download all as zip".
- [ ] **v1.2 — Immich plugin.** Userscript that adds a "Remove background" action to the Immich asset view; round-trips the cutout back into Immich as a new asset.
- [ ] **v2.0 — Video.** [Robust Video Matting](https://github.com/PeterL1n/RobustVideoMatting) + FFmpeg pipeline, WebM VP9 with alpha. GPU required.
- [ ] **v2.1 — Polish.** Per-user job history, admin UI, mobile responsiveness, model hot-swapping.

---

## Architecture

```
+--------------+      /api/*      +----------------------+
|   Next.js    |  --rewrite-->    |   FastAPI (uvicorn)  |
|  (Tailwind)  |                  |  rembg / ONNX        |
+--------------+                  +----------------------+
      :3000                              :8000
```

- **Backend:** FastAPI, `rembg` (ONNX Runtime), Pillow, `pydantic-settings`. Lifespan hook warms the chosen model at startup so the first request doesn't stall.
- **Frontend:** Next.js 15 App Router, React 19, Tailwind v4, TypeScript strict. Built as a standalone Node output for a small production image.
- **Deployment:** Docker Compose. The `api` service exposes port 8000; the `web` service exposes 3000 and proxies `/api/*` to `api` internally, so from the browser's perspective everything is same-origin — CORS only matters if you hit the API directly from another host.
- **Model cache:** Named Docker volume (`model-cache`) mounted at `~/.u2net` so model downloads survive rebuilds.
- **Security defaults:** Mandatory shared API key enforced by a FastAPI dependency (server refuses to start if it's unset); upload size capped at 25 MB and enforced before decoding; only common raster types accepted. Ports bind to `0.0.0.0` by default (LAN-reachable); the API key stays mandatory so exposure ≠ leak.

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

Frontend without Docker:

```bash
cd frontend
npm install
SELFBG_API_ORIGIN=http://localhost:8000 npm run dev
```

---

## License

MIT (c) 2026 Farhad Ahmed. See [LICENSE](./LICENSE).

Model weights are downloaded on demand by `rembg` and are licensed by their respective authors — check `rembg`'s documentation for the specific model you use.
