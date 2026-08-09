<p align="center">
  <img src="docs/img/golem-logo.png" alt="Golem Runner Logo" width="300" />
</p>

# Golem Runner

**Golem Runner** is a generic, configurable AI agent container.
It is a single Docker image that can be turned into any specialised agent at runtime — no rebuild required.

> Part of the [Golem](https://github.com/sasadangelo/golem-control-plane) platform, but fully usable as a standalone component.

---

## Features

| Feature | Status |
|---|:---:|
| Configurable AI agent — identity, system prompt, and skills set via `config.yaml`, no rebuild needed | ✅ |
| LangGraph-based agentic loop with dynamic tool binding | ✅ |
| In-memory conversation history — multi-turn context maintained across messages | ✅ |
| WebSocket streaming endpoint (`/ws/chat`) — streams LLM tokens, terminates with `[DONE]` | ✅ |
| Synchronous HTTP chat endpoint (`POST /chat`) | ✅ |
| A2A Agent Card served at `/.well-known/agent.json` | ✅ |
| A2A inbound task endpoint (`POST /a2a/tasks/send`) | ✅ |
| Built-in tools: `bash` (shell commands) and `http_check` (HTTP health check) | ✅ |
| Extensible tool catalogue — add a `@tool` function, register it, enable via config | ✅ |
| Secrets via `.env` / environment variables, config via `config.yaml` (mount as ConfigMap) | ✅ |
| Liveness probe (`GET /health`) | ✅ |
| `AGENTS.md` injection — custom agent behavioural context at boot | 🔜 |
| `SKILL.md` injection — lazy per-turn skill protocol injection | 🔜 |

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/sasadangelo/golem-runner.git
cd golem-runner
```

### 2. Configuration

Golem Runner is configured via two main files in the `src/golem-runner/` directory:
- **`config.yaml`**: Manages all non-secret parameters (e.g., agent identity, model settings, enabled skills).
- **`.env`**: Manages sensitive credentials and API keys.

First, copy the example environment file to create your local `.env`:

```bash
cp src/golem-runner/.env.example src/golem-runner/.env
```

Open `src/golem-runner/.env` and enter your IBM WatsonX API key:

```ini
WATSONX_API_KEY=your-actual-ibm-cloud-api-key
```

### 3. Start the application

Run the development script to boot up the agent server:

```bash
./app.sh
```

This loads the configuration from `src/golem-runner/config.yaml` and secrets from `src/golem-runner/.env`, starting the FastAPI application with reload enabled on `http://localhost:8000`.

### 4. Chat with the agent

You can send chat requests to the agent via HTTP POST or WebSocket streaming.

**Example A: Ask the agent what it can do over HTTP**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What can you do?"}'
```

**Example B: Ask the agent to inspect a website over HTTP (triggers the `http_check` tool)**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Check if https://google.com is reachable"}'
```

**Example C: Stream a response over WebSocket**
```bash
wscat -c ws://localhost:8000/ws/chat
```

Then send a plain UTF-8 text message such as `What can you do?`. The server streams LLM chunks as text frames and ends the response with `[DONE]`.

---

## Docker Integration

Once you are ready to containerise the application, you can build and run Golem Runner as a Docker container.

### 1. Build the image

Run the build command from the root folder:

```bash
docker build -t golem-runner:v1 .
```

### 2. Run the container

The image ships with a default `config.yaml` baked in. You can run the container with just the secrets file:

```bash
docker run -d --name my-agent \
  -p 8000:8000 \
  --env-file src/golem-runner/.env \
  golem-runner:v1
```

**Injecting a custom `config.yaml`**

If you want to override the default configuration (agent identity, model settings, enabled skills, etc.) without rebuilding the image, mount your own `config.yaml` over the one inside the container:

```bash
docker run -d --name my-agent \
  -p 8000:8000 \
  --env-file src/golem-runner/.env \
  -v "$(pwd)/my-config.yaml:/app/src/golem-runner/config.yaml:ro" \
  golem-runner:v1
```

The path inside the container is `/app/src/golem-runner/config.yaml` — this is where the application looks for its configuration at startup. The `:ro` flag mounts it read-only as a safety measure.

### 3. Test and Cleanup

To test the containerised agent, use the same `curl` commands shown in the **Quick Start** section above (there is no need to repeat them).

Once finished, clean up the running container:

```bash
docker stop my-agent && docker rm my-agent
```

---

## Minikube (Podman driver)

If you are running Minikube with the Podman driver, the cluster cannot pull images from your local Podman daemon directly. You need to load the image into Minikube's internal registry after building it.

### 1. Build the image with Podman

```bash
podman build -t golem-runner:v1 .
```

### 2. Load the image into Minikube

`minikube image load` does not work with the Podman driver. Instead, save the image to a tar archive and load it directly into the Minikube node:

```bash
podman save golem-runner:v1 -o /tmp/golem-runner-v1.tar
minikube image load /tmp/golem-runner-v1.tar
```

### 3. Verify the image is available inside Minikube

```bash
minikube image ls | grep golem-runner
```

### 4. Deploy

Set `imagePullPolicy: Never` in your Pod/Deployment spec to prevent Kubernetes from trying to pull the image from a remote registry:

```yaml
containers:
  - name: golem-runner
    image: golem-runner:v1
    imagePullPolicy: Never
```

### 5. Forward the port

Once the Pod is running, forward port `8000` to your local machine.

First, get the namespace and pod name:

```bash
# List namespaces
kubectl get namespaces

# List pods in the target namespace
kubectl get pods -n <namespace>
```

Then start the port-forward:

```bash
kubectl port-forward pod/<pod name> 8000:8000 -n <namespace>
```

### 6. Chat with the agent

With the port forward active, use the same `curl` commands as in the Quick Start section:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What can you do?"}'
```

---

## Configuration Details

The agent resolves settings in this priority order (highest wins):

```
environment variables / .env  >  config.yaml  >  built-in defaults
```

### Secret (required)

| Variable | Description |
|---|---|
| `WATSONX_API_KEY` | IBM Cloud API key used to authenticate against WatsonX |

### `config.yaml` keys and their env-var overrides

Every `config.yaml` key can be overridden at runtime by the corresponding environment variable without touching the file or rebuilding the image:

| `config.yaml` key | Env-var override | Description |
|---|---|---|
| `agent.id` | `AGENT_ID` | Unique identifier for this agent instance |
| `agent.name` | `AGENT_NAME` | Human-readable agent name |
| `agent.description` | `AGENT_DESCRIPTION` | Short description shown in the A2A Agent Card |
| `agent.endpoint` | `AGENT_ENDPOINT` | Public URL of this container |
| `agent.system_prompt` | `AGENT_SYSTEM_PROMPT` | System prompt that defines the agent persona |
| `agent.enabled_skill` | `AGENT_ENABLED_SKILL` | Comma-separated list of skill IDs to activate (e.g. `bash,http_check`) |
| `llm.url` | `URL` | WatsonX service URL |
| `llm.project_id` | `PROJECT_ID` | WatsonX project ID |
| `llm.model` | `MODEL` | Model identifier (e.g. `openai/gpt-oss-120b`) |

### Available Tools

| Tool ID | Function | Description |
|---|---|---|
| `bash` | `execute_bash_command` | Runs a shell command; returns stdout/stderr |
| `http_check` | `http_health_check` | HTTP GET to a URL; returns status code and body excerpt |

---

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/.well-known/agent.json` | A2A Agent Card |
| `POST` | `/a2a/tasks/send` | Receive an A2A task from a peer agent |
| `POST` | `/chat` | Human-facing synchronous chat endpoint |
| `WS` | `/ws/chat` | Human-facing streaming chat endpoint |
| `GET` | `/health` | Liveness probe |

Full API reference: [docs/GolemRunner.md](docs/GolemRunner.md)

---

## Project Layout

```
golem-runner/
├── Dockerfile                    # uv-based image, python:3.12-slim
├── app.sh                        # Dev launcher — loads .env, checks WATSONX_API_KEY, starts uvicorn
├── pyproject.toml                # Project metadata, dependencies, ruff & pytest config
├── uv.lock                       # Reproducible dependency lockfile (managed by uv)
├── .python-version               # Pins Python 3.12 for all tools and runtimes
├── .pre-commit-config.yaml       # Pre-commit hooks: linting, formatting, secret detection
├── .dockerignore                 # Files excluded from the Docker build context
├── .gitignore                    # Files excluded from version control
├── .secrets.baseline             # detect-secrets baseline (tolerated false positives)
└── src/golem-runner/
    ├── main.py                   # FastAPI server — /chat, /ws/chat, /a2a/tasks/send, and /health endpoints
    ├── agent.py                  # LangGraph dynamic graph built from settings at startup
    ├── config.yaml               # Non-secret configuration (agent identity, model, skills)
    ├── .env.example              # Template for local secrets — copy to .env and fill in
    ├── tools/
    │   ├── system_tools.py       # Tool: execute_bash_command
    │   └── http_tools.py         # Tool: http_health_check
    └── core/
        └── config.py             # Pydantic Settings — merges config.yaml + env vars
```

---

## Extending the Tool Catalogue

1. Add a new `@tool`-decorated function in `src/golem-runner/tools/` (e.g. `tools/db_tools.py`).
2. Register it in the `TOOL_REGISTRY` dict in `agent.py`.
3. Add its key to `config.yaml` under `agent.enabled_skill`.

No changes to `main.py` or the Dockerfile are needed.

---

## Roadmap

See [docs/Roadmap.md](docs/Roadmap.md).

---

## License

MIT
