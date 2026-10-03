"""One-off helper: write the Telegram credentials into the root .env file.

Kept in the repo so the values can be re-applied without hand-editing and
without corrupting the file encoding (PowerShell's Set-Content adds a BOM).

Usage:
    python backend/scripts/set_bot_credentials.py <bot_token> <bot_username>
"""

from __future__ import annotations

import pathlib
import secrets
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"

VALUES = {
    "BOT_TOKEN": None,
    "TELEGRAM_BOT_USERNAME": None,
    "SERVICE_TOKEN": None,
    "TELEGRAM_WEBHOOK_SECRET": None,
}


def upsert(text: str, key: str, value: str) -> str:
    line = f"{key}={value}"
    lines = text.split("\n")
    for index, existing in enumerate(lines):
        if existing.startswith(f"{key}="):
            lines[index] = line
            return "\n".join(lines)
    lines.append(line)
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 1

    VALUES["BOT_TOKEN"] = argv[1].strip()
    VALUES["TELEGRAM_BOT_USERNAME"] = argv[2].strip().lstrip("@")
    # Internal secrets are generated once and only filled if still placeholders.
    VALUES["SERVICE_TOKEN"] = secrets.token_urlsafe(32)
    VALUES["TELEGRAM_WEBHOOK_SECRET"] = secrets.token_urlsafe(24)

    text = ENV_FILE.read_text(encoding="utf-8").lstrip("\ufeff")
    for key, value in VALUES.items():
        if value is None:
            continue
        if key in {"SERVICE_TOKEN", "TELEGRAM_WEBHOOK_SECRET"} and f"{key}=CHANGE_ME" not in text:
            print(f"  {key}: already set, left untouched")
            continue
        text = upsert(text, key, value)
        shown = value if key != "BOT_TOKEN" else f"{value[:10]}..."
        print(f"  {key} = {shown}")

    ENV_FILE.write_text(text, encoding="utf-8", newline="\n")
    print(f"updated {ENV_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
