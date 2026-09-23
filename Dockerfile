FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create dedicated non-root user and home directory.
RUN groupadd --gid 1000 golem \
 && useradd --uid 1000 --gid 1000 --home /home/golem --create-home --shell /sbin/nologin golem

# Install system utilities used by bash tool
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Layout inside the image mirrors the ProcessProvisioner convention on the host:
#
#   /home/golem/.golem/runners/<version>/   ← repo root (pyproject.toml, uv.lock, src/)
#     pyproject.toml
#     uv.lock
#     src/
#       golem-runner/                        ← APP_DIR  (uvicorn --app-dir)
#     .venv/                                 ← created by uv sync here
#
# GOLEM_CONFIG_DIR is NOT baked into the image — injected at runtime by the
# provisioner as /home/golem/.golem/agents/<agent_id>/ so the runner workspace
# (config.yaml, AGENTS.md, skills/) is never inside the source tree.
ENV RUNNER_VERSION=0.2.0
ENV RUNNER_ROOT=/home/golem/.golem/runners/${RUNNER_VERSION}
ENV APP_DIR=${RUNNER_ROOT}/src/golem-runner

# Copy the full repo root into RUNNER_ROOT (.dockerignore excludes what is not needed).
# Result: pyproject.toml, uv.lock and src/ land directly under RUNNER_ROOT.
RUN mkdir -p ${RUNNER_ROOT} && chown golem:golem ${RUNNER_ROOT}
COPY --chown=golem:golem . ${RUNNER_ROOT}/

WORKDIR ${RUNNER_ROOT}

# Install from lockfile — .venv is created under RUNNER_ROOT (project root).
RUN uv sync --no-managed-python --no-dev --frozen

# Pre-create the agents base directory so the provisioner can bind-mount
# the agent workspace without a permission error.
RUN mkdir -p /home/golem/.golem/agents && chown -R golem:golem /home/golem/.golem

USER golem

EXPOSE 8000

CMD ["sh", "-c", "${RUNNER_ROOT}/.venv/bin/uvicorn main:app --app-dir ${APP_DIR} --host 0.0.0.0 --port 8000"]
