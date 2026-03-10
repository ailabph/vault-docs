# CI/CD

## Strategy

GitHub Actions deploys to the VPS on every push to `main`. The GPU server and SSH tunnel are not touched by the pipeline — they are managed independently via systemd on the VPS.

---

## Deployment Flow

```
Developer pushes to main
        │
        ▼
GitHub Actions triggered
        │
        ▼
Runner SSHs into VPS
        │
        ├── git pull origin main
        ├── docker compose build
        └── docker compose up -d
        │
        ▼
VPS serves updated app
(tunnel to GPU server unaffected)
```

---

## Workflow: Deploy on Push to Main

**Trigger:** Push to `main` branch
**Runner:** `ubuntu-latest` (GitHub-hosted)
**Target:** VPS via SSH

### Steps

1. Checkout repo (for any pre-deploy validation)
2. SSH into VPS
3. `git pull origin main`
4. `docker compose build` — rebuilds changed images
5. `docker compose up -d` — restarts services with zero-downtime where possible

### Secrets Required

Store these in GitHub → Settings → Secrets → Actions:

| Secret | Value |
|---|---|
| `VPS_HOST` | VPS IP address or domain |
| `VPS_USER` | SSH user (e.g. `root` or `deploy`) |
| `VPS_SSH_KEY` | Private SSH key authorized on VPS |
| `VPS_PORT` | SSH port (default `22`) |

---

## What the Pipeline Does NOT Do

- **Does not manage the GPU server** — Ollama and the SSH tunnel are infrastructure concerns, not deployment concerns
- **Does not run tests** — No automated test suite in v1; add when tests exist
- **Does not build frontend assets** — Frontend is vanilla JS, no build step required
- **Does not handle rollback** — Manual rollback via SSH for v1

---

## Rollback Procedure (Manual)

If a deployment breaks the app:

```bash
# SSH into VPS
ssh user@vps-host

# Roll back to previous commit
cd /path/to/vault-docs
git log --oneline -5          # find the last good commit
git checkout <commit-hash>
docker compose build
docker compose up -d
```

---

## Pre-Deployment Checklist (Manual, Before Merging to Main)

- [ ] `docker compose up` tested locally or on staging
- [ ] No secrets or API keys committed
- [ ] SSH tunnel to GPU server confirmed active on VPS before deploying

---

## Future Improvements

These are out of scope for v1 but worth considering as the project matures:

- **Automated tests** — pytest for backend, smoke test for health endpoint post-deploy
- **Staging environment** — Deploy to staging on PR, production on merge to main
- **Health check gate** — Workflow calls `GET /api/health` after deploy and fails if it returns non-200
- **Slack/Discord notification** — Post deploy status to team channel
- **Automated rollback** — Revert to previous image if health check fails
