# Deployment to Railway (recommended — permanent HTTPS domains)

Tunnel-based dev URLs (`*.loca.lt`, `*.trycloudflare.com`) are **not** usable for
production: they change on every restart, expire, and drop connections.

Railway gives each service a stable `*.up.railway.app` domain.

## 0. Prerequisites

```bash
npm i -g @railway/cli
railway login
```

## 1. Create the project and database

```bash
railway init
railway add --plugin postgresql
```

`DATABASE_URL` is injected automatically as `DATABASE_URL`.

## 2. Backend service

```bash
railway up backend
railway variables set --service backend \
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
railway variables set --service frontend VITE_API_BASE_URL=$BACKEND
railway up frontend
railway domain --service frontend
```

## 4. Bot service

Run the bot as a service (it needs a long-running process, not one-shot):

```bash
railway up bot
railway variables set --service bot \
  BOT_TOKEN=<token> BACKEND_URL=https://<your-backend>.up.railway.app \
  FRONTEND_URL=https://<your-frontend>.up.railway.app
```

Note: `railway up bot` uses `bot/Dockerfile`. Because the bot long-polls it must
run as a background worker; if the platform needs a healthcheck-free worker,
switch the Dockerfile CMD accordingly.

## 5. BotFather

```
/newapp  ->  NumoraAppBot
            Title:      Number Collector
            Short name: numora
            Web App URL: https://<your-frontend>.up.railway.app
```

Set the menu button (HTTPS URL required):

```bash
curl -X POST "https://api.telegram.org/bot$TOKEN/setChatMenuButton" \
  -d "menu_button={\"type\":\"web_app\",\"text\":\"Play\",\"web_app\":{\"url\":\"https://<your-frontend>.up.railway.app/numora\"}}"
```

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