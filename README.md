<p align="center">
  <img src="docs/img/golem-logo.png" alt="Golem Runner" width="300" />
</p>

# Golem Runner

**Golem Runner** is the agent execution unit of the [Golem](https://github.com/sasadangelo/golem-control-plane) platform.

It is a single Docker image that becomes any specialised agent at runtime — no rebuild required.
The Control Plane provisions one Runner container per agent, injecting identity (`AGENTS.md`),
skills (`SKILL.md`), and configuration (`config.yaml`) via ConfigMap mounts.

> 📖 For the full platform overview, features, roadmap, and demos see the
> **[Golem Control Plane](https://github.com/sasadangelo/golem-control-plane)** repository.

---

## Getting Started

### Local deployment (no Kubernetes, no Docker)

The fastest way to run the runner on your machine:

```bash
# 1. clone and enter the repo
git clone https://github.com/sasadangelo/golem-runner.git
cd golem-runner

# 2. configure credentials
cp src/golem-runner/.env.example src/golem-runner/.env
# edit .env: set WATSONX_API_KEY

# 3. start the runner
./app.sh
# → agent listening on http://localhost:8000
```

Use the [Golem CLI](https://github.com/sasadangelo/golem-cli) to interact:

```bash
golem chat --id <agent_id>
```

Or interact directly via the runner's REST/WebSocket API (see [docs/APIReference.md](docs/APIReference.md)).

### Minikube deployment (full Kubernetes setup)

Follow the **[Minikube Deployment Guide](https://github.com/sasadangelo/golem-control-plane/blob/main/docs/MinikubeDeployment.md)** in the Control Plane repository — it covers image builds, RBAC, Secrets, and the full deploy flow for both components together.

---

## Image Management Scripts

| Script | Description |
|---|---|
| `build_images.sh` | Build the `golem-runner` image locally with Podman or Docker |
| `delete_images.sh` | Remove the local `golem-runner` image |
| `minikube/load_images.sh` | Load the local image into Minikube's internal registry |
| `minikube/delete_images.sh` | Remove the image from Minikube |

---

## Configuration

The runner uses a two-layer configuration model:

| Layer | Source | What goes here |
|---|---|---|
| Non-secret parameters | `config.yaml` (mounted as ConfigMap in K8s, or local file) | Agent identity, system prompt, skills, LLM settings, triggers, MCP servers |
| Secret credentials | `WATSONX_API_KEY` environment variable | IBM Cloud API key |

### `config.yaml` reference

```yaml
agent:
  id: "my-agent-001"                    # Unique identifier (used as K8s namespace name)
  name: "My Agent"                      # Human-readable name shown in the Agent Card
  description: "What this agent does."
  endpoint: "http://localhost:8000"     # Public URL of this container
  system_prompt: "You are a helpful agent."
  enabled_skills: "bash,http_check"     # Comma-separated embedded tool IDs

  # Optional — only needed for agents that delegate tasks to other agents
  cp_url: "http://golem-cp.golem-system.svc.cluster.local:9000"
  delegation_timeout_seconds: 300

  # Optional — MCP servers to connect at boot (static URIs; MCP Registry in MVP 3)
  mcp_servers:
    - "http://kubernetes-mcp-server.kubernetes-mcp-server.svc.cluster.local:8080"

  # Optional — K8s Secrets to mount as envFrom (secret must exist in the agent namespace)
  env_secrets:
    - "my-credentials"

  # Optional — background triggers (fire autonomously without a user message)
  triggers:
    - type: timer
      interval_seconds: 30
      message: "Check if http://my-service/health is healthy."
    - type: cron
      cron: "0 9 * * 1-5"
      message: "Send the daily standup summary."
    - type: webhook
      path: "/trigger/my-event"
      message: "Handle incoming event."

llm:
  provider: "watsonx"                   # watsonx | ollama (MVP 2)
  protocol: "watsonx"                   # watsonx | openai | ollama (MVP 2)
  model: "openai/gpt-oss-120b"
  project_id: "<your-watsonx-project-id>"
  url: "https://us-south.ml.cloud.ibm.com"
```

### Secret

| Variable | Required | Description |
|---|:---:|---|
| `WATSONX_API_KEY` | ✅ | IBM Cloud API key — the only secret the container needs |

---

## Embedded Tools

Tools declared in `agent.enabled_skills` are registered into the LangGraph tool node at boot.

| Tool ID | Description |
|---|---|
| `bash` | Executes a shell command inside the container; returns stdout/stderr |
| `http_check` | HTTP GET to a URL; returns status code and first 200 chars of body |
| `delegate` | Delegates a task to another agent via the Control Plane A2A broker |

---

## API Reference

👉 **[docs/APIReference.md](docs/APIReference.md)** — full endpoint reference with request/response schemas.

**Endpoint summary:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/.well-known/agent.json` | A2A Agent Card |
| `POST` | `/a2a/tasks/send` | Receive an inbound A2A task from a peer agent |
| `WS` | `/ws/chat` | Streaming chat (token-by-token, terminates with `[DONE]`) |
| `GET` | `/health` | Liveness probe |

---

## Project Layout

```
golem-runner/
├── Dockerfile                         # uv-based image, python:3.12-slim, port 8000
├── app.sh                             # Local dev launcher — loads .env, starts uvicorn with reload
├── build_images.sh                    # Build golem-runner image locally (Podman/Docker)
├── delete_images.sh                   # Remove local golem-runner image
├── pyproject.toml                     # Dependencies, ruff, pytest config
├── uv.lock                            # Reproducible lockfile
├── minikube/
│   ├── load_images.sh                 # Load image into Minikube internal registry
│   └── delete_images.sh               # Remove image from Minikube
├── src/
│   ├── golem-runner/
│   │   ├── main.py                    # FastAPI app — /ws/chat, /a2a/tasks/send, /health
│   │   ├── agent.py                   # LangGraph agentic loop, tool binding, AGENTS.md + SKILL.md injection
│   │   ├── config.yaml                # Default runner configuration
│   │   ├── .env.example               # Secrets template — copy to .env and fill in
│   │   ├── core/
│   │   │   └── config.py              # Pydantic Settings — merges config.yaml + env vars
│   │   └── tools/
│   │       ├── system_tools.py        # Tool: execute_bash_command (bash)
│   │       ├── http_tools.py          # Tool: http_health_check (http_check)
│   │       └── a2a_tools.py           # Tool: delegate_to_agent (delegate)
│   ├── golem_agent_sdk/               # A2A lifecycle, Agent Card, trigger scheduler, task store
│   │   ├── models.py
│   │   ├── router.py
│   │   ├── store.py
│   │   └── trigger_scheduler.py
│   └── golem_framework/               # LLM Gateway abstraction (WatsonX; Ollama + OpenAI in MVP 2)
├── examples/                          # Runnable demo agents (see docs/Demos.md in Control Plane)
│   ├── demo-chatbot/
│   ├── demo-sre/
│   ├── demo-doc/
│   ├── demo-monitor/
│   ├── demo-a2a/
│   └── demo-architecture/
├── docs/
│   ├── APIReference.md                # Runner REST & WebSocket API reference
│   └── img/
└── tests/
```

---

## License

This project is licensed under the MIT License. See [`LICENSE.md`](LICENSE.md) for details.
