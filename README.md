# SwiftDeploy

> Declarative deployment CLI — manifest.yaml is the single source of truth.

**HNG Internship 14 · DevOps Track · Stage 4A**
**Username:** hngstage4a

---

## What It Does

You write one file (`manifest.yaml`). SwiftDeploy generates all configs, builds the stack, manages modes, and keeps everything running.

```
manifest.yaml  →  swiftdeploy init  →  nginx.conf + docker-compose.yml
                  swiftdeploy deploy →  running stack
                  swiftdeploy promote canary  →  canary mode
                  swiftdeploy teardown  →  clean shutdown
```

---

## Project Structure

```
swiftdeploy/
├── manifest.yaml              ← edit this only
├── swiftdeploy                ← CLI executable
├── Dockerfile                 ← API service image
├── app/
│   ├── main.py                ← Flask API (stable + canary)
│   └── requirements.txt
├── templates/
│   ├── nginx.conf.tmpl        ← Nginx template
│   └── docker-compose.yml.tmpl ← Compose template
└── README.md
```

Generated (do not edit — recreated by `init`):
```
├── nginx.conf
└── docker-compose.yml
```

---

## Prerequisites

- Docker Engine 24+
- Docker Compose v2 (`docker compose`)
- Python 3 (for YAML parsing in the CLI)
- `curl`, `ss` or `netstat` (for validate)

---

## Quick Start

```bash
# 1. Clone / enter the project
cd swiftdeploy

# 2. Make the CLI executable
chmod +x swiftdeploy

# 3. Build the service image
docker build -t swift-deploy-1-node:latest .

# 4. Validate everything is ready
./swiftdeploy validate

# 5. Deploy
./swiftdeploy deploy

# 6. Test
curl http://localhost:8080/
curl http://localhost:8080/healthz
```

---

## Subcommand Walkthrough

### `init` — Generate configs from manifest

```bash
./swiftdeploy init
```

Reads `manifest.yaml` and writes:
- `nginx.conf` — from `templates/nginx.conf.tmpl`
- `docker-compose.yml` — from `templates/docker-compose.yml.tmpl`

The grader deletes these files and re-runs `init` to verify they regenerate correctly.

---

### `validate` — Pre-flight checks

```bash
./swiftdeploy validate
```

Runs 5 checks and prints PASS/FAIL for each:

```
SwiftDeploy Pre-flight Validation
──────────────────────────────────
  [1] manifest.yaml exists and is valid YAML ... PASS
  [2] All required fields present and non-empty ... PASS
  [3] Docker image 'swift-deploy-1-node:latest' exists locally ... PASS
  [4] Nginx port 8080 is free on host ... PASS
  [5] nginx.conf syntax is valid ... PASS
──────────────────────────────────
All checks passed. Ready to deploy.
```

Exits non-zero on any failure.

---

### `deploy` — Bring up the stack

```bash
./swiftdeploy deploy
```

1. Runs `init` (regenerates configs)
2. Runs `docker compose up -d`
3. Polls health checks every 5s
4. Exits success when healthy or fails after 60s timeout

---

### `promote` — Switch deployment mode

```bash
# Switch to canary
./swiftdeploy promote canary

# Switch back to stable
./swiftdeploy promote stable
```

Each promote call:
1. Updates `mode` in `manifest.yaml` in-place
2. Regenerates `docker-compose.yml` with new `MODE` env var
3. Restarts **only the app container** (Nginx stays up, no downtime)
4. Confirms new mode by hitting `/healthz`

**Canary mode** adds `X-Mode: canary` to every response and activates `/chaos`.

---

### `teardown` — Shut down and clean up

```bash
# Remove containers, networks, volumes
./swiftdeploy teardown

# Also delete generated nginx.conf and docker-compose.yml
./swiftdeploy teardown --clean
```

---

## API Endpoints

All traffic routes through Nginx on port **8080**. The service port (3000) is never exposed directly.

### `GET /`
```json
{
  "message": "Welcome to SwiftDeploy API",
  "mode": "stable",
  "version": "1.0.0",
  "timestamp": "2026-05-03T10:00:00+00:00",
  "username": "hngstage4a"
}
```

### `GET /healthz`
```json
{
  "status": "ok",
  "uptime_seconds": 42.3,
  "mode": "stable",
  "version": "1.0.0"
}
```

### `POST /chaos` *(canary mode only)*

```bash
# Slow responses
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"slow","duration":3}'

# Error injection (50% rate)
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"error","rate":0.5}'

# Recover
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"recover"}'
```

---

## Nginx Access Log Format

```
2026-05-03T10:00:00+00:00 | 200 | 0.001s | 172.18.0.2:3000 | GET / HTTP/1.1
```

View logs:
```bash
docker logs swiftdeploy-nginx
```

---

## Security

- App runs as non-root user (`appuser`)
- All Linux capabilities dropped (`cap_drop: ALL`), only `NET_BIND_SERVICE` re-added
- `no-new-privileges` security option set
- Service port never exposed to host — only Nginx port (8080) is published
- Images use Alpine base (well under 300MB)

---

## manifest.yaml Fields Reference

| Field | Description | Default |
|-------|-------------|---------|
| `services.image` | Docker image for the API | required |
| `services.port` | Internal service port | required |
| `services.mode` | `stable` or `canary` | `stable` |
| `services.version` | App version string | `1.0.0` |
| `services.restart_policy` | Docker restart policy | `unless-stopped` |
| `services.log_volume` | Named volume for logs | `swiftdeploy-logs` |
| `nginx.image` | Nginx Docker image | required |
| `nginx.port` | Host-exposed Nginx port | required |
| `nginx.proxy_timeout` | Upstream timeout in seconds | `30` |
| `network.name` | Docker network name | required |
| `network.driver_type` | Network driver | required |
| `meta.contact` | Contact shown in error JSON | optional |