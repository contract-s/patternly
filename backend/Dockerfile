# Build from the repo root: docker build -f backend/Dockerfile .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    PATTERNLY_CONTENT=/app/content \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend
# Dependencies first, so code changes don't reinstall them.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/src ./src
RUN uv sync --locked --no-dev
COPY content /app/content

RUN useradd --create-home --uid 1000 app
USER app
EXPOSE 8000
CMD ["patternly", "serve", "--host", "0.0.0.0", "--port", "8000"]
