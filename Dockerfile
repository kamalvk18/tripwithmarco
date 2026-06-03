FROM python:3.12-slim
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./backend/
COPY main.py ./

ENV PORT=8080

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
