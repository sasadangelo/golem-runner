FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install system utilities used by bash tool
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Copy the full repo layout (.dockerignore excludes what is not needed)
COPY . .

# Install from lockfile so extras (e.g. pydantic-settings[yaml]) are respected
RUN uv sync --no-managed-python --no-dev --frozen

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "main:app", "--app-dir", "/app/src/golem-runner", "--host", "0.0.0.0", "--port", "8000"]
