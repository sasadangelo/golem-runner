# Golem Runner — Agent Runner

The Golem Runner is the **atomic execution unit** of the Golem platform.
It is a single, generic Docker image that can be configured entirely at runtime — no rebuild required.

See also: [Roadmap](Roadmap.md)

---

## Purpose

Each agent sandbox in Golem runs exactly one Agent Runner container.
The same image becomes a diagnostics agent, a code-writing assistant, or any other specialised agent simply by mounting a different `config.yaml` at container startup.

---

## Directory Layout

```
src/golem-runner/
├── __init__.py
├── main.py           # FastAPI server — /chat, /a2a/tasks/send, and /health endpoints
├── agent.py          # LangGraph dynamic graph, built from settings at startup
├── config.yaml       # Non-secret runtime configuration (mounted at deploy time)
├── core/
│   └── config.py     # Pydantic Settings — merges config.yaml + WATSONX_API_KEY env var
├── tools/
│   ├── __init__.py
│   ├── system_tools.py   # Skill: execute_bash_command
│   └── http_tools.py     # Skill: http_health_check
├── Dockerfile            # uv-based image, python:3.12-slim
├── pyproject.toml        # uv project dependencies
└── .env.example          # Template for local secrets
```

---

## Configuration

Configuration uses a **two-layer model** managed by `core/config.py` (Pydantic Settings):

| Layer | Source | What goes here |
|---|---|---|
| Non-secret parameters | `config.yaml` (mounted into the container) | Agent identity, system prompt, enabled skills, LLM model/URL/project |
| Secret credentials | `WATSONX_API_KEY` environment variable (single var) | IBM Cloud API key |

### `config.yaml` reference

```yaml
agent:
  id: "golem-agent-001"          # Unique identifier — used in the A2A Agent Card
  name: "Golem Agent Runner"     # Human-readable agent name
  description: "Generic automation agent powered by Golem."
  endpoint: "http://localhost:8001"  # Public URL of this container
  system_prompt: "You are a helpful generic automation agent."
  enabled_skill: "bash,http_check"  # Comma-separated skill IDs to activate

llm:
  provider: "watsonx"
  protocol: "watsonx"
  model: "openai/gpt-oss-120b"
  url: "https://us-south.ml.cloud.ibm.com"
  project_id: "<your-watsonx-project-id>"
```

### Secret environment variable

| Variable | Required | Description |
|---|:---:|---|
| `WATSONX_API_KEY` | ✅ | IBM Cloud API key — the only secret the container needs |

### Accessing settings in code

```python
from core.config import settings

settings.agent.id
settings.agent.system_prompt
settings.agent.enabled_skill   # "bash,http_check"
settings.llm.model
settings.llm.api_key           # SecretStr, injected from WATSONX_API_KEY
```

### Available Skills

| Skill ID | Function | Description |
|---|---|---|
| `bash` | `execute_bash_command` | Runs a shell command inside the container; returns stdout/stderr |
| `http_check` | `http_health_check` | HTTP GET to a URL; returns status code and first 200 chars of body |

---

## HTTP API

### `GET /.well-known/agent.json`

A2A Agent Card — used by the Control Plane to register the agent and by peer agents for discovery.

```json
{
  "id": "golem-agent-001",
  "name": "Golem Agent Runner",
  "description": "Generic automation agent powered by Golem.",
  "version": "0.1.0",
  "endpoint": "http://agent-001.sandbox.svc:8000",
  "capabilities": { "streaming": false, "pushNotifications": false },
  "skills": [{ "id": "bash", "name": "bash" }, { "id": "http_check", "name": "http_check" }]
}
```

### `POST /a2a/tasks/send`

A2A inbound task reception — accepts a task delegated by a peer agent.

**Request**
```json
{
  "id": "task-abc123",
  "message": {
    "role": "user",
    "parts": [{ "type": "text", "text": "Check if https://google.com is reachable" }]
  }
}
```

**Response**
```json
{
  "id": "task-abc123",
  "status": { "state": "completed" },
  "artifacts": [{ "parts": [{ "type": "text", "text": "Status Code: 301 ..." }] }]
}
```

### `POST /chat`

Human-facing chat endpoint.

**Request**
```json
{ "message": "Check if https://google.com is reachable" }
```

**Response**
```json
{ "reply": "The site is reachable. Status Code: 200 ..." }
```

### `GET /health`

Liveness probe.

```json
{ "status": "ok" }
```

---

## Local Development with Docker

### 1. Build the image

```bash
docker build -t golem-runner:v1 .
```

### 2. Create your local config and secrets

Copy the example files and fill in your values:

```bash
cp src/golem-runner/config.yaml /tmp/agent-config.yaml   # edit as needed
cp src/golem-runner/.env.example .env                     # add WATSONX_API_KEY
```

Edit `/tmp/agent-config.yaml` — set at least `llm.project_id` and customise
`agent.system_prompt` / `agent.enabled_skill` for the scenario you want.

### 3. Run a diagnostics agent

```bash
docker run -d --name agent-test-1 \
  -p 8000:8000 \
  -v /tmp/agent-config.yaml:/app/src/golem-runner/config.yaml:ro \
  -e WATSONX_API_KEY="your-ibm-cloud-api-key" \
  golem-runner:v1
```

The container inherits all non-secret parameters from the mounted `config.yaml`.
The only environment variable required is `WATSONX_API_KEY`.

### 4. Test the agent

**Generic response:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Who are you and what can you do?"}'
```

**HTTP health check tool:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Check if https://google.com is reachable"}'
```

**Bash tool:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How many files are in the current directory and what is the container IP?"}'
```

### 5. Cleanup

```bash
docker stop agent-test-1 && docker rm agent-test-1
```

---

## Extending the Skill Catalogue

1. Add a new `@tool`-decorated function in `tools/` (e.g. `tools/db_tools.py`).
2. Register it in the `TOOL_REGISTRY` dict in [`agent.py`](../src/golem-runner/agent.py).
3. Add its key to `agent.enabled_skill` in `config.yaml` at runtime.

No code changes are needed in `main.py` or the Dockerfile.

---

## Architecture Context

In the full Golem platform the Agent Runner pod is spawned and configured by the **K8s Provisioner** (Week 2).
The Control Plane mounts a per-agent `config.yaml` (via a Kubernetes ConfigMap) and injects `WATSONX_API_KEY` as a Kubernetes Secret into the pod. Egress-only NetworkPolicy rules are enforced around the pod.
