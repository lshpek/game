# Number Collector — Telegram Mini App

A production-ready Telegram Mini App: players roll random four-digit numbers
(`0000`–`9999`), each with a rarity, traits, a story and an in-game **Coins**
value, then collect, share, challenge friends and open loot boxes.

Two loops:

```
ROLL → RESULT → COLLECT → SHARE → FRIEND → ROLL
COINS → CONTAINER → ITEM → COLLECTION
```

> The value of a number is an in-game balance. It is **not** money and has no
> cash value.

---

## 1. Architecture

```
Telegram ──▶ Bot (aiogram)  ──▶ Mini App (React)
                                   │ initData (signed by Telegram)
                                   ▼
                          Backend (FastAPI)
                                   │ verify HMAC → JWT session
                                   ▼
                    PostgreSQL / SQLite (SQLAlchemy 2.x, Alembic)
```

| Layer | Choice |
|---|---|
| Frontend | React 18, TypeScript (strict), Vite, Tailwind, framer-motion, TanStack Query, zustand |
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic |
| Database | SQLite for development, PostgreSQL for production (same models) |
| Bot | aiogram 3 |
| Payments | Telegram Stars + a mock provider for local development |

### Repository layout

```
mini app/
├── backend/
│   ├── app/
│   │   ├── api/            # routers + deps (auth, rate limit, idempotency)
│   │   │   └── v1/
│   │   ├── core/           # config, security, logging, errors, locks, rate limit
│   │   ├── db/             # engine, session, declarative base
│   │   ├── game/           # RNG, traits, rules, rarity, valuation, stories, catalogues
│   │   ├── models/         # ORM entities
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # business logic (one module per domain)
│   │   ├── seed.py         # idempotent seeding
│   │   ├── bootstrap.py    # startup: migrate + seed
│   │   └── main.py         # app factory, middleware, error handlers, /health
│   ├── alembic/versions/   # migrations
│   ├── scripts/smoke.py
│   ├── tests/              # pytest suite
│   └── Dockerfile
├── frontend/
│   └── src/{components,pages,services,store,lib,types}
├── bot/bot.py
├── docker-compose.yml
└── .env / .env.example
```

### Server authority (anti-cheat)

The client never decides a result. It posts a request; the backend locks the
player, consumes a roll, generates the number with its own RNG, persists it and
writes the ledger entry — all in one transaction:

```
check user → lock state → consume roll → server RNG
→ insert item → ledger row → update stats → commit
```

* `ROLL`, container opening, daily claim, duplicate conversion and payments all
  accept an `Idempotency-Key` header; a retry returns the original result.
* Per-user in-process locks plus `SELECT … FOR UPDATE` on PostgreSQL remove the
  "one roll, two rewards" race.

---

## 2. Requirements

* Python 3.12+
* Node.js 20+
* Docker (optional, for the compose stack)
* A Telegram bot token from [@BotFather](https://t.me/BotFather)

---

## 3. Installation

```bash
cd "mini app"
cp .env.example .env      # then edit .env
```

### Backend

```bash
cd backend
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env      # VITE_API_BASE_URL
```

### Bot (optional, only needed to talk to Telegram)

```bash
cd bot && pip install -r requirements.txt
```

---

## 4. Environment variables

All backend configuration lives in the project-root `.env` (see `.env.example`).

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development` \| `test` \| `production` |
| `DEBUG` | FastAPI debug flag |
| `SECRET_KEY` | Signs session JWTs — **generate a random value** |
| `DATABASE_URL` | `sqlite:///./app.db` or `postgresql+psycopg://…` |
| `AUTO_MIGRATE` / `AUTO_SEED` | Run Alembic + seeding on startup |
| `BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_BOT_USERNAME` | Username without `@`, used to build deep links |
| `MINI_APP_SHORT_NAME` | Short name of the Mini App (default `game`) |
| `TELEGRAM_WEBHOOK_SECRET` | Secret token for the payment webhook |
| `SERVICE_TOKEN` | Internal token the bot uses to forward payment updates |
| `FRONTEND_URL` / `BACKEND_URL` | Public URLs |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `ADMIN_TELEGRAM_IDS` | Comma-separated Telegram ids that receive the ADMIN role |
| `ALLOW_DEV_LOGIN` | Enables `POST /api/auth/dev` (ignored in production) |
| `DEFAULT_DAILY_ROLLS` | Free rolls per UTC day |
| `PREMIUM_DAILY_ROLLS` | Extra rolls for Pro members |
| `REFERRAL_REWARD_COINS` / `REFERRAL_REWARD_ROLLS` | Referral payout |
| `RATE_LIMIT_*` | Per-scope request limits and window |
| `PAYMENT_PROVIDER` | `mock` locally, `telegram_stars` in production |
| `RARITY_WEIGHTS_OVERRIDE` | Optional JSON overriding rarity odds |

---

## 5. Database setup & migrations

```bash
cd backend
alembic upgrade head                            # apply migrations
alembic revision --autogenerate -m "message"   # create a new one
alembic downgrade -1                            # roll back
python -m app.seed                              # seed catalogue (idempotent)
```

Startup also runs `alembic upgrade head` and seeds an empty catalogue when
`AUTO_MIGRATE` / `AUTO_SEED` are enabled, so `uvicorn` alone is enough locally.

Seeded data: 4 containers, 17 achievements, 2 seasons (Season 1 active), 5 Star
products and 22 notable numbers with pre-computed rarity and stories.

---

## 6. Running

```bash
# Backend  → http://localhost:8000  (docs at /docs)
cd backend && uvicorn app.main:app --reload

# Frontend → http://localhost:5173
cd frontend && npm run dev

# Bot (optional - needs a real BOT_TOKEN)
cd bot
pip install -r requirements.txt
python bot.py --check     # validate config without contacting Telegram
python bot.py             # start long polling (or a webhook if configured)
```

Outside Telegram the frontend signs in through the development endpoint
(`POST /api/auth/dev`) and creates a stable local identity in `localStorage`.
Inside Telegram it exchanges `initData` for a session.

---

## 7. Docker

```bash
docker compose up --build                 # postgres + backend + frontend
docker compose --profile bot up --build    # additionally run the bot
```

The frontend image is nginx serving the SPA build on port 80; the backend runs
as a non-root user with a health check.

---

## 8. Telegram setup

The bot requires a **real** bot token. `python bot.py --check` validates the
configuration without contacting Telegram; `python bot.py` refuses to start with
a placeholder token and explains exactly what is missing.

1. **Create the bot** — [@BotFather](https://t.me/BotFather) → `/newbot`, copy
   the token into `BOT_TOKEN` (and `TELEGRAM_BOT_USERNAME`).
2. **Create the Mini App** — BotFather → `/newapps`. Set the Web App URL to your
   **HTTPS** frontend URL, e.g. `https://your-domain.com/` (nginx serves the SPA
   from `/`).
3. **Set the short name** — put it in `MINI_APP_SHORT_NAME` so deep links match.
4. **Backend URL** — set `VITE_API_BASE_URL=https://your-api.example.com`.
5. **Deep links** — `https://t.me/<bot>/<short_name>?startapp=ref_12345`,
   `?startapp=number_7777`, `?startapp=challenge_abc123`. The bot also accepts
   `/start ref_12345`.
6. **Run it** — `cd bot && python bot.py`. Successful startup logs
   `Bot connected as @yourbot (id=…)`.

---

## 9. Payments (Telegram Stars)

1. Obtain `TELEGRAM_PAYMENT_PROVIDER_TOKEN` from @BotFather.
2. Set `PAYMENT_PROVIDER=telegram_stars` and `PAYMENT_CURRENCY=XTR`.
3. The backend creates the invoice via `createInvoiceLink` and stores a
   `PENDING` payment row.
4. Telegram sends `successful_payment` to the bot, which forwards it to
   `POST /api/payments/telegram/webhook` with `X-Service-Token`.
5. The backend validates amount/currency, marks the payment paid and grants the
   product **once** (`payments.granted` + ledger idempotency key).

A payment is never considered successful because the client said so.
Refunds are supported: `POST /api/payments/refund` (admin) calls
`refundStarPayment` and revokes the premium entitlement.

For local work use `PAYMENT_PROVIDER=mock` and
`POST /api/payments/mock/confirm` (refused when `APP_ENV=production`).

---

## 10. Testing

```bash
cd backend  && pytest                    # 163 tests
cd backend  && ruff check .              # lint (config in backend/ruff.toml)
cd frontend && npm run typecheck         # tsc --noEmit, strict
cd frontend && npm test                  # vitest
cd frontend && npm run build             # production build
```

Start the API and run the end-to-end suite against it:

```bash
cd backend
uvicorn app.main:app --port 8010
python scripts/smoke.py http://127.0.0.1:8010
```

The smoke script uses fresh identities and idempotency keys on every run, so it
is safe to execute repeatedly against the same database. It exits `2` if the
auth rate limit is exhausted — wait one window and retry.

`pytest` works from the repository root or from `backend/`: the root
`pytest.ini` pins `testpaths = backend/tests`, and the file is deliberately
named `smoke.py` (not `*_test.py`) so pytest never collects it.

Coverage includes auth and `initData` tampering, RNG distribution, analyzer and
rarity rules, valuation, stories, roll flow, roll limits, idempotency,
duplicates, containers, daily rewards, referrals, challenges, leaderboards,
achievements, payments, admin authorization, rate limiting and error envelopes.

---

## 11. Security summary

| Concern | Mitigation |
|---|---|
| Forged users | `initData` HMAC verified with the bot token + TTL |
| Token forgery | HS256 JWT signed with `SECRET_KEY`, constant-time comparison |
| Replay of rewards | `Idempotency-Key`, unique constraints, daily unique index |
| Race conditions | per-user locks, `SELECT … FOR UPDATE`, single transaction |
| Payment spoofing | only Telegram-signed updates grant; amounts validated |
| Referral abuse | unique inviter per invitee, no self-referral, paid only after a real roll, daily cap |
| Privilege escalation | admin role derived from `ADMIN_TELEGRAM_IDS` on the server |
| API abuse | configurable per-scope rate limiting |
| SQL injection | SQLAlchemy bound parameters everywhere |
| XSS | React escapes by default; no `dangerouslySetInnerHTML` |
| Error leakage | uniform envelope; stack traces logged, never returned |
| CORS | explicit origin allow-list |

Rate limiting is process-local; for multi-replica deployments swap
`SlidingWindowRateLimiter` for a Redis-backed implementation (same interface).

---

## 12. Production deployment

1. Provision PostgreSQL and set `DATABASE_URL=postgresql+psycopg://…`.
2. Set `APP_ENV=production`, `DEBUG=false`, `ALLOW_DEV_LOGIN=false`.
3. Generate strong secrets:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
4. Put the frontend behind HTTPS (nginx/Cloudflare) and set `CORS_ORIGINS` to
   the exact frontend origin.
5. `docker compose up --build -d`, then verify `GET /health` returns
   `"status":"ok","database":"ok"`.
6. Register the Mini App URL in BotFather and run
   `docker compose --profile bot up -d`.
7. Fill `ADMIN_TELEGRAM_IDS` so moderators can access `/api/admin/*`.
8. Tune `RATE_LIMIT_*` and `RARITY_WEIGHTS_OVERRIDE` for your traffic.
9. Back up PostgreSQL (`pg_dump`) and monitor `/health` plus the
   `analytics_events` table.

### API surface

```
GET    /health
POST   /api/auth/telegram | /api/auth/dev      GET /api/auth/me
GET    /api/user                              POST /api/roll
GET    /api/roll/history                      GET  /api/daily
POST   /api/daily/claim
GET    /api/collection                        POST /api/collection/convert-all
GET    /api/numbers/{value}                   POST /api/numbers/{value}/convert
POST   /api/numbers/{value}/share
GET    /api/containers                        POST /api/containers/open
GET    /api/referrals
GET    /api/challenges                        POST /api/challenges
GET    /api/challenges/{code}                 POST /api/challenges/{code}/accept
GET    /api/leaderboard | /api/leaderboard/all
GET    /api/achievements | /api/seasons
GET    /api/payments/products                 POST /api/payments/invoice
POST   /api/payments/telegram/webhook         GET  /api/premium
POST   /api/analytics/event
GET    /api/admin/stats | /api/admin/users    POST /api/admin/users/coins
GET    /api/admin/economy/transactions        GET  /api/admin/errors
GET    /api/admin/seasons                     POST /api/admin/seasons/toggle
GET    /api/admin/rarity-config
```

Errors always look like this:

```json
{
  "success": false,
  "error": { "code": "NO_ROLLS_AVAILABLE", "message": "No rolls available.", "details": {} }
}
```
