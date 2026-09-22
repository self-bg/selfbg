# Deploying `selfbg` on Proxmox

This guide covers the setup used on my own homelab: an unprivileged Debian LXC running Docker, behind an existing Nginx reverse proxy with a Cloudflare wildcard TLS certificate. Adapt to taste.

## 1. Create a Docker-ready LXC

Run this on the Proxmox host (the shell where `pveversion` works), not on an existing VM or container:

```bash
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/docker.sh)"
```

This is the community-maintained fork of the original `tteck` scripts. It prompts for hostname, disk, RAM, CPU cores, and network settings, then creates an **unprivileged** LXC with:

- Debian 12 (bookworm)
- `nesting=1` and `keyctl=1` enabled (required for Docker inside LXC)
- Docker Engine + Docker Compose plugin installed
- Optional: Portainer, if you want a GUI

Suggested sizing for Phase 1:

| Resource | Value |
|---|---|
| CPU cores | 2 |
| RAM | 4 GB (birefnet-general peaks around 2 GB during inference) |
| Disk | 12 GB (the image itself + model cache is ~2.5 GB, rest is headroom) |
| Network | DHCP is fine, or set a static IP if your reverse proxy expects one |

Once the script finishes, note the LXC's IP address (the summary prints it).

## 2. Deploy `selfbg`

SSH into the LXC as root (or the user the script created):

```bash
ssh root@<lxc-ip>
```

Then, inside the LXC:

```bash
mkdir -p /opt/selfbg && cd /opt/selfbg

curl -O https://raw.githubusercontent.com/self-bg/selfbg/main/docker-compose.yml
curl -o .env https://raw.githubusercontent.com/self-bg/selfbg/main/.env.example
```

Open `.env` in an editor:

```bash
nano .env
```

In `.env`, set at minimum:

```
API_BIND=0.0.0.0:8000     # accept connections from your LAN so Nginx can reach it
WEB_BIND=0.0.0.0:3000
```

Pull and start:

```bash
docker compose pull
docker compose up -d
```

Watch the logs during first startup — the API container loads the ONNX model on boot, which takes 10–30 seconds depending on CPU. The web container waits until the API healthcheck passes.

```bash
docker compose logs -f
```

Verify from your laptop:

```bash
curl -f http://<lxc-ip>:3000                    # HTML page
curl -f http://<lxc-ip>:8000/healthz            # {"status":"ok","model":"birefnet-general"}
```

Test the round-trip with a real image:

```bash
curl -X POST http://<lxc-ip>:8000/remove \
  -F "file=@some-photo.jpg" \
  -o cutout.png
open cutout.png     # macOS; xdg-open on Linux; Explorer on Windows
```

## 3. Put it behind Nginx

Assuming Nginx runs elsewhere in your homelab (a separate reverse-proxy VM or LXC) and already terminates TLS with a Cloudflare wildcard certificate, drop a site file in — e.g. `/etc/nginx/sites-available/selfbg.conf`:

```nginx
server {
    listen 443 ssl http2;
    server_name selfbg.yourdomain.tld;

    # Reuse whatever wildcard cert paths the rest of your sites use
    ssl_certificate     /etc/nginx/ssl/yourdomain.tld.fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/yourdomain.tld.privkey.pem;

    client_max_body_size 30M;   # a little above SELFBG_MAX_UPLOAD_MB=25

    location / {
        proxy_pass http://<lxc-ip>:3000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

Enable and reload:

```bash
ln -s /etc/nginx/sites-available/selfbg.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

Add the DNS record (e.g. an A record `selfbg.yourdomain.tld` -> the public IP of the Nginx host, proxied through Cloudflare). If you're using Cloudflare Tunnels instead of exposing an IP, add the hostname in the Zero Trust dashboard pointing at `http://<nginx-host>:80` or `https://<nginx-host>:443` depending on your setup.

Only the frontend (`:3000`) needs to be reverse-proxied — Next.js proxies `/api/*` to the API container internally over the compose network. If you want to expose the API directly to other machines on your LAN (e.g. for scripts), point another Nginx `server` block at `http://<lxc-ip>:8000`.

## 4. Firewall

If you use Proxmox's firewall on the LXC, allow inbound TCP `3000` and `8000` from the Nginx host's IP only. If you use the Cloudflare Tunnel path there's nothing to allow — the LXC never accepts inbound connections from the internet directly.

## 5. Updating

```bash
cd /opt/selfbg
docker compose pull
docker compose up -d
```

Pin `SELFBG_TAG` in `.env` once a release proves itself so you're not implicitly tracking `:latest`.
