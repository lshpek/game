# Deployment to Railway (recommended — permanent HTTPS domains)

Tunnel-based dev URLs (`*.loca.lt`, `*.trycloudflare.com`) are **not** usable for
production: they change on every restart, expire, and drop connections.

Railway gives each service a stable `*.up.railway.app` domain.

## 0. Prerequisites

```bash
npm i -g @railway/cli
railway login
```

## Where NUMORA lives today

| Piece | URL |
|---|---|
| Bot | https://t.me/NumoraAppBot |
| Mini App | https://frontend-production-d8fc.up.railway.app/numora |
| API | https://backend-production-74fd.up.railway.app |
| Repo | https://github.com/lshpek/game |

## Deploying an update (the order matters)

The two services are **not** deployed the same way. This asymmetry is the single most
important thing to know here, and getting it backwards either ships nothing or breaks a
working deployment:

| Service | Triggered by a GitHub push? | How to deploy |
|---|---|---|
| `backend` | **Yes** - build from the repository root | Push to `main`. Nothing to do. |
| `frontend` | **No** - no git trigger is attached | `cd frontend && railway up --service frontend` |
| `bot` | No | `cd bot && railway up --service bot` |

`VITE_API_BASE_URL` is **inlined at build time**, so the frontend must be rebuilt
after the backend domain is known.

```bash
git push origin main                              # backend picks this up on its own
cd frontend && railway up --service frontend       # the frontend does not
```

### Do not `railway up` the backend

`railway up` and `railway redeploy` upload a source snapshot, which makes Railway fall
back to Railpack. Railpack cannot build this monorepo - it sees `backend/`, `bot/` and
`frontend/` at the top level and refuses with *could not determine how to build the app*.
The deployment is marked FAILED even though the running container is untouched and
healthy, which makes a working backend look broken.

The backend builds from the repository root via `Dockerfile.backend` + the root
`railway.json`, and that path only runs on a git trigger. Confirm a push landed by
checking that a deployment appeared seconds after the commit:

```bash
git log -1 --format=%cI        # commit time
railway deployment ls --service backend
```

If no deployment appears, the git trigger is detached and has to be re-attached in the
Railway dashboard - there is no CLI workaround, because the upload path cannot build
this repository.

### The frontend must be uploaded, from inside its own directory

`frontend/railway.json` points at `frontend/Dockerfile` and expects `VITE_API_BASE_URL`
as a build arg, so the upload has to be rooted at `frontend/`:

```bash
cd frontend
railway variables set VITE_API_BASE_URL=https://backend-production-74fd.up.railway.app
railway up --service frontend
```

Verify it actually changed by looking for the new hashed bundle in the served HTML -
the same filename being served after a successful deploy means the build was cached or
the wrong source was uploaded:

```bash
curl -s https://frontend-production-d8fc.up.railway.app/numora | grep -o '/assets/[^"]*'
```

### Auto-deploy on push

The backend service has its Railway **root directory set to the repository root**,
while the code lives in `backend/`. A git-triggered build therefore saw only the top
level and Railpack refused it with *could not determine how to build the app*, so every
push produced a failed deployment. `Dockerfile.backend` + `railway.json` at the
repository root fix that: a push now builds the backend image from the root context.

If you ever point another service at the repository root, give it its own
`railway.json` — the root one builds the backend.

Migrations run on the backend container start (`AUTO_MIGRATE=true`). A change that
touches no model needs no migration and none is applied.

Afterwards:

1. Reopen the Mini App from a closed chat, or from another client - Telegram and
   the browser cache the previous JS bundle aggressively.
2. Send `/panelcheck` to the bot in a private chat. It prints the acting id, the
   admin allow list, whether the tokens are set, the backend URL, and whether a
   real panel call succeeds. That single command distinguishes "the bot is not
   deployed" from "the backend is unreachable" from "the service token is wrong".

## 1. Create the project and database

```bash
railway init
railway add --plugin postgresql
```

`DATABASE_URL` is injected automatically as `DATABASE_URL`.

## 2. Backend service

```bash
cd backend
railway up --service backend
railway variables set \
  SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  APP_ENV=production DEBUG=false \
  AUTO_MIGRATE=true AUTO_SEED=true \
  ALLOW_DEV_LOGIN=false \
  TELEGRAM_BOT_USERNAME=NumoraAppBot \
  MINI_APP_SHORT_NAME=numora \
  TELEGRAM_WEBHOOK_SECRET="$(python -c 'import secrets;print(secrets.token_hex(32))')" \
  SERVICE_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
```

Paste `BOT_TOKEN` and `POSTGRES_PASSWORD`-derived values in the dashboard — never
commit them. Then generate a domain:

```bash
railway domain --service backend
```

## 3. Frontend service

`VITE_API_BASE_URL` is inlined **at build time**, so set it *after* the backend
domain exists, then deploy:

```bash
BACKEND=https://<your-backend>.up.railway.app
railway variables set VITE_API_BASE_URL=$BACKEND
railway up --service frontend
railway domain --service frontend
```

## 4. Bot service

Run the bot as a service (it needs a long-running process, not one-shot):

```bash
cd bot
railway up --service bot
railway variables set \
  BOT_TOKEN=<token> BACKEND_URL=https://<your-backend>.up.railway.app \
  FRONTEND_URL=https://<your-frontend>.up.railway.app
```

Note: `railway up bot` uses `bot/Dockerfile`. Because the bot long-polls it must
run as a background worker; if the platform needs a healthcheck-free worker,
switch the Dockerfile CMD accordingly.

## 5. BotFather

```
/newapp  ->  NumoraAppBot
             Title:      NUMORA
             Short name: numora
             Web App URL: https://<your-frontend>.up.railway.app
```

Set the menu button (HTTPS URL required):

```bash
curl -X POST "https://api.telegram.org/bot$TOKEN/setChatMenuButton" \
  -d "menu_button={\"type\":\"web_app\",\"text\":\"Play\",\"web_app\":{\"url\":\"https://<your-frontend>.up.railway.app/numora\"}}"
```

The bot publishes its command list on every start: players see `/start` and
`/help`, and each configured admin additionally sees `/admin`, `/panel`, `/a` and
`/panelcheck` in their own chat. Because that list is scoped per chat, a newly
added `ADMIN_TELEGRAM_ID` only appears after the bot service restarts - which
`railway up bot` does.

## 6. Verify

```bash
curl https://<your-backend>.up.railway.app/health
curl -I https://<your-frontend>.up.railway.app/numora
```

Then open `https://t.me/NumoraAppBot/numora` in Telegram.

---

# Deployment to Render

1. **Postgres** — New > PostgreSQL, copy the *Internal Database URL*.
2. **Backend** — New > Web Service, connect the repo, root dir `backend`.
   Build: `pip install -r requirements.txt`
   Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`
   Set the environment variables from section 2.
3. **Frontend** — New > Static Site, root dir `frontend`.
   Build: `npm ci && npm run build`
   Publish dir: `dist`
   Set `VITE_API_BASE_URL=https://<backend>.onrender.com` **before** the first build.
4. **Bot** — Render does not run long-polling daemons well; run the bot from your
   machine or a small VM instead, pointing `BACKEND_URL`/`FRONTEND_URL` at the
   deployed domains.

## Telegram iframe note

`frontend/nginx.conf` must allow framing from `web.telegram.org`, otherwise the
Mini App renders blank in Telegram Desktop. The config sends:

```
Content-Security-Policy: frame-ancestors 'self' https://web.telegram.org https://*.telegram.org
```