# ---- 1. Mini App build
FROM node:22-alpine AS miniapp
WORKDIR /m
COPY miniapp/package.json miniapp/package-lock.json ./
RUN npm ci
COPY miniapp/ ./
RUN npm run build

# ---- 2. Backend (API + bot + admin + background jobs in one process)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MINIAPP_DIST=/srv/miniapp/dist FILES_DIR=/srv/backend/data/files
WORKDIR /srv/backend
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY --from=miniapp /m/dist /srv/miniapp/dist
RUN useradd -r -u 1000 app && mkdir -p data/files && chown -R app:app data
USER app
EXPOSE 8000
# One worker on purpose: the background jobs loop and the Telegram notifier live in this process.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
