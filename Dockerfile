# ── Stage 1: Build React frontend ─────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build
# output → /app/frontend/dist


# ── Stage 2: Python backend ────────────────────────────────────────────────────
FROM python:3.14-slim AS final
WORKDIR /app

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install dependencies (no dev deps, frozen lockfile)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source
COPY backend/ ./backend/
COPY main.py ./

# Copy built React app from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Persistent trip storage lives on a Fly volume at /data
RUN mkdir -p /data/trips

ENV TRIPS_DIR=/data/trips
ENV PORT=8080

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
