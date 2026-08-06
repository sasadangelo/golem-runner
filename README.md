# Golem Runner

**Golem Runner** is a generic, configurable AI agent container.  
It is a single Docker image that can be turned into any specialised agent at runtime — no rebuild required.

> Part of the [Golem](https://github.com/sasadangelo/golem) platform, but fully usable as a standalone component.

---

## Quick Start

### 1. Build the image

```bash
docker build -t golem-runner:v1 src/golem-runner/
```

### 2. Run an agent

```bash
docker run -d --name my-agent \
  -p 8000:8000 \
  -e WATSONX_API_KEY="your-ibm-cloud-api-key" \
  -e WATSONX_URL="https://us-south.ml.cloud.ibm.com" \
  -e WATSONX_PROJECT_ID="your-watsonx-project-id" \
  -e WATSONX_MODEL_ID="openai/gpt-oss-120b" \
  -e SYSTEM_PROMPT="You are a network diagnostics agent." \
  -e ENABLED_SKILLS="bash,http_check" \
  golem-runner:v1
```

### 3. Chat with the agent

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Check if https://google.com is reachable"}'
```

### 4. Cleanup

```bash
docker stop my-agent && docker rm my-agent
```

---

## Configuration

The agent is configured entirely via environment variables.

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `WATSONX_API_KEY` | ✅ | — | IBM Cloud API key |
| `WATSONX_URL` | ✅ | `https://us-south.ml.cloud.ibm.com` | WatsonX endpoint URL |
| `WATSONX_PROJECT_ID` | ✅ | — | WatsonX project ID |
| `WATSONX_MODEL_ID` | | `openai/gpt-oss-120b` | Model identifier |
| `AGENT_ID` | | `golem-agent-<random>` | Unique agent identifier |
| `AGENT_NAME` | | `"Golem Agent Runner"` | Human-readable agent name |
| `AGENT_DESCRIPTION` | | `"Generic automation agent…"` | Agent description |
| `AGENT_ENDPOINT` | | `http://localhost:8000` | Public URL of this container |
| `SYSTEM_PROMPT` | | `"You are a helpful generic automation agent."` | Agent persona and instructions |
| `ENABLED_SKILLS` | | `""` (no tools) | Comma-separated skill IDs to activate |

### Available Skills

| Skill ID | Function | Description |
|---|---|---|
| `bash` | `execute_bash_command` | Runs a shell command; returns stdout/stderr |
| `http_check` | `http_health_check` | HTTP GET to a URL; returns status code and body excerpt |

---

## HTTP API

| Method | Path | Description |
|---|---|---|
| `GET` | `/.well-known/agent.json` | A2A Agent Card |
| `POST` | `/a2a/tasks/send` | Receive an A2A task from a peer agent |
| `POST` | `/chat` | Human-facing chat endpoint |
| `GET` | `/health` | Liveness probe |

Full API reference: [docs/GolemRunner.md](docs/GolemRunner.md)

---

## Project Layout

```
src/golem-runner/
├── main.py           # FastAPI server — /chat and /health endpoints
├── agent.py          # LangGraph dynamic graph built from env vars at startup
├── tools/
│   ├── system_tools.py   # Skill: execute_bash_command
│   └── http_tools.py     # Skill: http_health_check
├── core/
│   └── config.py         # Pydantic settings
└── Dockerfile            # uv-based image, python:3.12-slim
```

---

## Extending the Skill Catalogue

1. Add a new `@tool`-decorated function in `src/golem-runner/tools/` (e.g. `tools/db_tools.py`).
2. Register it in the `TOOL_REGISTRY` dict in `agent.py`.
3. Pass its key in `ENABLED_SKILLS` at runtime.

No changes to `main.py` or the Dockerfile are needed.

---

## Roadmap

See [docs/Roadmap.md](docs/Roadmap.md).

---

## License

MIT
