FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Fase 1: applies pending Alembic migrations before every boot -- Railway's
# deploy process never ran them on its own, so the platform_auth tables
# (and any future migration) would otherwise only ever exist if someone
# happened to run `alembic upgrade head` by hand. `exec` hands off PID 1 to
# uvicorn so it still receives Railway's shutdown signal directly.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
