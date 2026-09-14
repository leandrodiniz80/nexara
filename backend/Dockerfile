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

# Incident rollback: running `alembic upgrade head` on every boot (added
# for Fase 1, to apply the platform_auth migration automatically) is
# suspected of causing repeat/overlapping migration runs when this
# monorepo's frontend-only commits also redeploy this service -- the
# platform_auth migration is already applied, so re-running it on boot
# isn't needed right now. Plain uvicorn start until root-caused properly.
#
# Shell form (not exec-form array) so ${PORT:-8000} actually expands: Railway
# auto-detects this image's EXPOSE 8000 and doesn't require binding to its
# own $PORT, but Render (and most other Docker PaaS) always inject $PORT and
# expect the process to bind to it -- falling back to 8000 keeps this exact
# image portable to both without maintaining two Dockerfiles.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
