"""End-to-end smoke test against a running server.

Usage: python scripts/smoke_test.py [base_url]
Exits non-zero if any check fails, so it doubles as a deployment gate.
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
FAILURES: list[str] = []

# Every run uses fresh identities and idempotency keys so the suite can be
# executed repeatedly against the same database.
RUN = int(time.time()) % 1_000_000
PLAYER_A = 5_000_000_000 + RUN * 10 + 1
PLAYER_B = 5_000_000_000 + RUN * 10 + 2
INVITEE = 5_000_000_000 + RUN * 10 + 3
POOR = 5_000_000_000 + RUN * 10 + 4
PROBE = 5_000_000_000 + RUN * 10 + 9


def call(method: str, path: str, token: str | None = None, body: dict | None = None,
         idempotency: str | None = None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/json")
    if data:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    if idempotency:
        request.add_header("Idempotency-Key", idempotency)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def check(label: str, condition: bool, extra: object = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}" + (f"  {extra}" if extra else ""))
    if not condition:
        FAILURES.append(label)


def balance(token: str) -> int:
    return int(call("GET", "/api/user", token)[1].get("coins", 0))


def settings_window() -> int:
    return int(call("GET", "/health")[1].get("rate_limit_window_seconds", 60) or 60)


def ensure_funds(token: str, target: int = 500) -> int:
    """Top the player up through the documented mock Stars product."""
    current = balance(token)
    while current < target:
        invoice = call("POST", "/api/payments/invoice", token,
                       body={"product_code": "coins_1000"},
                       idempotency=f"fund-{RUN}-{current}")
        if invoice[0] != 200:
            break
        call("POST", "/api/payments/mock/confirm", token,
             body={"payment_id": invoice[1]["payment_id"]})
        updated = balance(token)
        if updated == current:
            break
        current = updated
    return current


print("== health & auth ==")
status, health = call("GET", "/health")
check("health 200", status == 200, health.get("status"))
check("database reachable", health.get("database") == "ok")

status, denied = call("GET", "/api/user")
check("unauthenticated request rejected", status == 401, denied.get("error", {}).get("code"))

status, auth_a = call("POST", "/api/auth/dev", body={"telegram_id": PLAYER_A, "username": "alice"})
if status == 429:
    print("RATE LIMITED: the auth endpoint quota for this IP is exhausted.")
    print(f"Wait {settings_window()}s (RATE_LIMIT_WINDOW_SECONDS) or raise RATE_LIMIT_AUTH, then retry.")
    sys.exit(2)
check("dev login", status == 200 and "access_token" in auth_a)
token_a = auth_a.get("access_token", "")

status, auth_b = call("POST", "/api/auth/dev", body={"telegram_id": PLAYER_B, "username": "bob"})
token_b = auth_b.get("access_token", "")
check("second user", status == 200 and bool(token_b))

status, tampered = call("POST", "/api/auth/telegram", body={"init_data": "auth_date=1&user=%7B%7D&hash=bad"})
check("forged initData rejected", status == 401, tampered.get("error", {}).get("code"))

print("\n== roll ==")
status, roll1 = call("POST", "/api/roll", token_a, idempotency=f"smoke-roll-{RUN}")
check("roll succeeds", status == 200, roll1.get("number", {}).get("number"))
number = roll1.get("number", {}).get("number", "")
check("number is 4 digits", len(number) == 4 and number.isdigit(), number)
check("story present", bool(roll1.get("number", {}).get("story")))
check("server-computed value", roll1.get("number", {}).get("value", 0) > 0)

status, retry = call("POST", "/api/roll", token_a, idempotency=f"smoke-roll-{RUN}")
check("idempotent retry returns same roll", status == 200 and retry.get("roll_id") == roll1.get("roll_id"))
check("retry flagged as replay", retry.get("replayed") is True)

print("\n== daily & collection ==")
status, daily = call("GET", "/api/daily", token_a)
check("daily status", status == 200, f"rolls_left={daily.get('rolls_remaining')}")
status, claim = call("POST", "/api/daily/claim", token_a)
check("daily claim", status == 200, f"coins={claim.get('coins_granted')}")
status, again = call("POST", "/api/daily/claim", token_a)
check("second claim blocked", again.get("error", {}).get("code") == "DAILY_ALREADY_CLAIMED")
status, collection = call("GET", "/api/collection?page=1&page_size=10", token_a)
check("collection loads", status == 200 and collection.get("total", 0) >= 1)
status, detail = call("GET", "/api/numbers/0007", token_a)
check("number detail works", status == 200 and detail.get("number") == "0007")
status, bad = call("GET", "/api/numbers/12345", token_a)
check("invalid number rejected", bad.get("error", {}).get("code") == "VALIDATION_ERROR")

print("\n== economy & containers ==")
coins_before = call("GET", "/api/user", token_a)[1].get("coins", 0)
check("player balance is non-negative and readable", coins_before >= 0, f"coins={coins_before}")

status, containers = call("GET", "/api/containers", token_a)
codes = {row["code"] for row in containers}
check("container catalogue", {"basic", "premium", "mystery"} <= codes, sorted(codes))

# A dedicated account with no Coins proves the server refuses the purchase.
token_poor = call("POST", "/api/auth/dev", body={"telegram_id": POOR})[1].get("access_token", "")
status, no_funds = call("POST", "/api/containers/open", token_poor, body={"code": "basic"})
check("purchase without funds rejected", no_funds.get("error", {}).get("code") == "INSUFFICIENT_FUNDS")

status, locked = call("POST", "/api/containers/open", token_poor, body={"code": "pro"})
check("premium box locked", locked.get("error", {}).get("code") == "CONTAINER_UNAVAILABLE")

# Fund the player through the public Stars flow, then exercise the happy path.
rich_coins = ensure_funds(token_a, 500)
check("player funded via Stars product", rich_coins >= 500, f"coins={rich_coins}")

status, opened = call("POST", "/api/containers/open", token_a,
                      body={"code": "basic"}, idempotency=f"smoke-box-{RUN}")
check("container opens for a funded player", status == 200 and opened.get("success") is True,
      opened.get("error", {}).get("code", ""))
status, reopened = call("POST", "/api/containers/open", token_a,
                        body={"code": "basic"}, idempotency=f"smoke-box-{RUN}")
check("container purchase is idempotent",
      status == 200 and reopened.get("opening_id") == opened.get("opening_id")
      and reopened.get("replayed") is True)
if status == 200:
    earned = sum(item["reward_coins"] for item in opened.get("unlocked_achievements", []))
    check("exactly one box charge", balance(token_a) == rich_coins - 100 + earned,
          f"{rich_coins} -> {balance(token_a)}")

print("\n== admin authorization ==")
status, admin_denied = call("GET", "/api/admin/stats", token_a)
check("admin route forbidden", status == 403, admin_denied.get("error", {}).get("code"))

print("\n== referrals ==")
status, referrals = call("GET", "/api/referrals", token_a)
check("referral link built", status == 200 and f"ref_{PLAYER_A}" in referrals.get("referral_link", ""))
coins_inviter = call("GET", "/api/user", token_a)[1].get("coins", 0)

status, invited = call("POST", "/api/auth/dev",
                       body={"telegram_id": INVITEE, "start_param": f"ref_{PLAYER_A}"})
token_c = invited.get("access_token", "")
check("invitee bound to pending referral",
      invited.get("start_context", {}).get("referral_telegram_id") == PLAYER_A)
check("no reward on open only",
      call("GET", "/api/user", token_a)[1].get("coins") == coins_inviter)

call("POST", "/api/roll", token_c)
after = call("GET", "/api/user", token_a)[1]
check("reward paid after first real roll", after.get("coins", 0) > coins_inviter,
      f"{coins_inviter} -> {after.get('coins')}")

call("POST", "/api/auth/dev", body={"telegram_id": PLAYER_A, "start_param": f"ref_{PLAYER_A}"})
status, self_stats = call("GET", "/api/referrals", token_a)
check("self-referral never pays", self_stats.get("activated") == 1)

print("\n== challenges ==")
status, challenge = call("POST", "/api/challenges", token_a, body={})
check("challenge created", status == 200 and challenge.get("status") == "PENDING", challenge.get("code"))
check("challenge deep link", "startapp=challenge_" in (challenge.get("link") or ""))
call("POST", "/api/roll", token_b)
status, accepted = call("POST", f"/api/challenges/{challenge.get('code')}/accept", token_b)
check("challenge completed", status == 200 and accepted.get("status") == "COMPLETED")
status, closed = call("POST", f"/api/challenges/{challenge.get('code')}/accept", token_a)
check("re-accept blocked", closed.get("error", {}).get("code") == "CHALLENGE_CLOSED")

print("\n== leaderboards, achievements, seasons ==")
for period in ("daily", "weekly", "alltime"):
    status, board = call("GET", f"/api/leaderboard?period={period}&category=VALUE", token_a)
    check(f"leaderboard {period}", status == 200 and isinstance(board.get("entries"), list))
status, boards = call("GET", "/api/leaderboard/all?period=alltime", token_a)
check("all leaderboards", set(boards.get("boards", {})) == {"VALUE", "RARITY", "COLLECTION", "ROLLS"})

status, achievements = call("GET", "/api/achievements", token_a)
check("achievements listed", status == 200 and len(achievements) > 0)
status, seasons = call("GET", "/api/seasons", token_a)
check("exactly one active season", status == 200 and sum(1 for s in seasons if s["is_active"]) == 1)

print("\n== payments (mock provider) ==")
status, products = call("GET", "/api/payments/products", token_a)
check("products listed", status == 200 and len(products) > 0)
status, invoice = call("POST", "/api/payments/invoice", token_a,
                       body={"product_code": "coins_1000"}, idempotency=f"smoke-pay-{RUN}")
check("invoice created", status == 200 and invoice.get("provider") == "MOCK")

coins_pre = call("GET", "/api/user", token_a)[1].get("coins", 0)
status, confirmed = call("POST", "/api/payments/mock/confirm", token_a,
                         body={"payment_id": invoice["payment_id"]})
check("payment confirmed", status == 200 and confirmed.get("status") == "PAID")
coins_post = call("GET", "/api/user", token_a)[1].get("coins", 0)
check("coins granted once", coins_post == coins_pre + 1000, f"{coins_pre} -> {coins_post}")

call("POST", "/api/payments/mock/confirm", token_a, body={"payment_id": invoice["payment_id"]})
check("re-confirm does not double pay", call("GET", "/api/user", token_a)[1].get("coins") == coins_post)

status, webhook = call("POST", "/api/payments/telegram/webhook", body={"message": {}})
check("payment webhook requires a secret", webhook.get("error", {}).get("code") == "WEBHOOK_UNAUTHORIZED")

print("\n== sharing, analytics, rate limiting ==")
status, share = call("POST", f"/api/numbers/{number}/share", token_a)
check("share deep link", status == 200 and "startapp=number_" in share.get("mini_app_link", ""))

status, tracked = call("POST", "/api/analytics/event", token_a, body={"name": "share", "props": {"n": 1}})
check("analytics event accepted", status == 200 and tracked.get("success") is True)

statuses = []
for _ in range(30):
    statuses.append(call("GET", "/api/referrals", token_a)[0])
    if 429 in statuses:
        break
check("rate limit kicks in", 429 in statuses, f"after {len(statuses)} requests")
check("auth endpoint stays available after the probe",
      call("POST", "/api/auth/dev", body={"telegram_id": PROBE})[0] == 200)

print("\n" + "=" * 46)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL SMOKE CHECKS PASSED")
