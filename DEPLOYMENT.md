# Deploying IntelliDocs AI

Two ways to run the full stack: locally with Docker Compose (works today,
verified by hand), or live on Render via the Blueprint in `render.yaml`
(written from Render's docs, not yet verified against a live account — see
"Rough edges" below before assuming a red first deploy means the config is
wrong).

## Locally, with Docker Compose

```bash
cp backend/.env.example backend/.env        # fill in ANTHROPIC_API_KEY at least
cp mcp-server/.env.example mcp-server/.env  # set JWT_SECRET_KEY / INTERNAL_API_KEY
                                             # to match the values in backend/.env
docker compose up -d --build
```

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs
- MCP server health: http://localhost:8001/health

`docker compose down` stops everything; add `-v` to also drop the named
volumes (Qdrant's index, Redis's data, the SQLite file) if you want a clean
slate.

## Live, on Render

Render's free tier is what `render.yaml` targets: **zero cost**, at the
price of an ephemeral filesystem — Qdrant's vector index and the SQLite
database (users, documents) reset on every restart, redeploy, or
spin-down-from-15-minutes-idle, and the first request after a spin-down
takes about a minute to wake the service back up. That's a deliberate
trade-off for a portfolio demo (register, upload, chat all work fine in one
sitting), not a bug — see the comment at the top of `render.yaml` for the
one-line path to real persistence (a paid plan + a `disk:` block) if you
want it later.

### Steps

1. Push this repo to GitHub (already set up if you're reading this from a
   clone — `git remote -v` should show `origin`).
2. In the Render dashboard: **New +** → **Blueprint**, connect the repo.
   Render reads `render.yaml` and proposes five services: `qdrant`,
   `redis` (a Key Value instance), `mcp-server`, `backend`, `frontend`.
3. Render prompts for every env var marked `sync: false` in the blueprint
   before the first deploy. Fill in:
   - `ANTHROPIC_API_KEY` (backend) — from console.anthropic.com
   - `JWT_SECRET_KEY` (backend) — any long random string, e.g.
     `python -c "import secrets; print(secrets.token_urlsafe(64))"`
   - `INTERNAL_API_KEY` (backend **and** mcp-server) — same value in both;
     any long random string, different from `JWT_SECRET_KEY`
   - `CORS_ALLOW_ORIGINS` (backend) and `VITE_API_BASE_URL` (frontend) —
     leave a placeholder for now (e.g. `["http://localhost:5173"]` and
     `http://localhost:8000`); you don't know the real URLs until step 4.
4. Deploy. Once it finishes, note the public URLs Render assigned to
   `backend` and `frontend` (something like
   `https://intellidocs-backend-xxxx.onrender.com`).
5. Go back into each service's **Environment** tab and fix the two
   placeholders from step 3:
   - `backend`'s `CORS_ALLOW_ORIGINS` → `["https://<frontend-url>"]`
   - `frontend`'s `VITE_API_BASE_URL` → `https://<backend-url>`
   Saving `VITE_API_BASE_URL` should trigger a rebuild on its own — Vite
   bakes it into the JS bundle at build time, so a restart alone won't pick
   up the change. If it doesn't rebuild automatically, trigger a manual
   deploy on the `frontend` service.
6. Visit the frontend URL, register an account, upload a document, ask it
   a question.

### Rough edges (things I couldn't verify without a live Render account or Docker on this machine)

- **`qdrant`'s port routing.** It's a bare `runtime: image` pull
  (`qdrant/qdrant:latest`), not a service built from a Dockerfile Render
  can read an `EXPOSE` from. Render's docs don't fully spell out how it
  picks a port in that case. It should pick up Qdrant's default (6333)
  automatically; if the backend's `/api/health` reports `qdrant:
  "unreachable"` after deploy, check the `qdrant` service's logs and port
  settings in the dashboard first.
- **Build-time env vars on `runtime: static` services.** Render's docs
  confirm `envVars` work for Docker/native services but don't explicitly
  say whether they're injected during a *static site's* build step, which
  is what `VITE_API_BASE_URL` needs. If the deployed frontend calls
  `localhost:8000` instead of the real backend URL, this is why — the fix
  is the same either way (set the var, force a rebuild), just confirming
  it's expected to work automatically vs. always needing a manual nudge.
- **Nothing here has actually been deployed yet.** Every step above is
  reasoned from Render's current documentation, not a working deployment —
  treat the first real attempt as the actual test, the same way you'd treat
  this repo's first CI run (see Phase 9): read what actually fails rather
  than assuming the whole approach is broken over one red step.

### Cheaper alternative to debugging Render blind

If any of the above turns out wrong and you'd rather not iterate against a
live account by trial and error, `docker compose up -d --build` runs the
exact same images locally first — anything that works there but not on
Render is specifically a Render-configuration problem, not an application
bug, which narrows down where to look considerably.
