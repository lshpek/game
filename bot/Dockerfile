FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Keep the repository layout so `from bot.admin...` resolves identically here and
# on a developer machine: /app/bot.py plus /app/bot/admin/.
COPY bot.py ./bot.py
COPY __init__.py ./bot/__init__.py
COPY admin ./bot/admin
COPY ruff.toml ./bot/ruff.toml

RUN useradd --create-home --uid 10001 appuser
USER appuser

CMD ["python", "bot.py"]
