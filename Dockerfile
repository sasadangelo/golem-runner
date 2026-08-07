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

# Install Python dependencies
# Build context is the repo root — pyproject.toml and uv.lock are here
COPY pyproject.toml uv.lock ./

# Copy the full repo layout (what is not needed is excluded via .dockerignore)
COPY . .

# Install from lockfile so extras (e.g. pydantic-settings[yaml]) are respected
RUN uv sync --system --no-dev --frozen

EXPOSE 8001

CMD ["uvicorn", "main:app", "--app-dir", "/app/src/golem-runner", "--host", "0.0.0.0", "--port", "8001"]
