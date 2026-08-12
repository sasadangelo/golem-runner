# Golem Demo — Aria, the SRE Agent

**Audience:** technical or semi-technical stakeholders.  
**Duration:** ~5 minutes.  
**What it shows:** deploy a specialised agent from the CLI in seconds, then have a natural conversation that uses real tools inside a live Kubernetes pod.

---

## Prerequisites

```bash
# Control Plane running on minikube
minikube start
# (deploy golem-control-plane — e.g. via app.sh or kubectl apply)

# CLI configured
golem cp add --name minikube --url http://$(minikube ip):9000
golem cp use --name minikube

# Fill in your WatsonX project ID in config.yaml
```

---

## Step 1 — Deploy the agent (10 seconds)

```bash
golem agent create \
  --config  examples/demo-sre/config.yaml \
  --agents-md examples/demo-sre/AGENTS.md \
  --skill   examples/demo-sre/check-health.md \
  --skill   examples/demo-sre/inspect-env.md
```

Expected output:
```
Agent created: id=aria-sre-001  namespace=aria-sre-001  name=Aria — SRE Agent  status=pending
```

Wait for the pod to start:
```bash
golem agent status --id aria-sre-001
# → running
```

---

## Step 2 — Open a chat session

```bash
golem chat --id aria-sre-001
```

---

## Demo conversation (copy-paste these lines one at a time)

### Intro — show the agent knows who it is
```
Who are you and what can you do?
```
> Aria introduces herself, lists her tools, and explains her role.

---

### Live HTTP health check — audience sees a real tool call
```
Check if https://google.com is reachable and give me a structured report.
```
> Aria calls `http_check`, interprets the status code, and returns a formatted report.

---

### Internal cluster check — shows cluster-internal networking
```
Probe the runner's own health endpoint and tell me if this pod is healthy.
```
> Aria calls `http_check` on `http://localhost:8000/health` — proves it's running inside the pod.

---

### Container introspection — the "wow moment"
```
Give me a full environment report of this container: resources, mounted files, running processes.
```
> Aria runs a series of bash commands, redacts secrets automatically, and returns a structured Markdown report showing:
> - hostname, kernel, OS
> - CPU / memory / disk
> - what's mounted at `/app` (config.yaml, AGENTS.md, skill files)
> - running processes

---

### Multi-step diagnostic — shows autonomous reasoning
```
Something might be wrong with IBM WatsonX connectivity. Check if https://us-south.ml.cloud.ibm.com is reachable from this pod, then check disk space and memory, and summarise whether this pod is healthy enough to serve production traffic.
```
> Aria makes multiple tool calls, synthesises the results, and produces a final yes/no verdict with evidence.

---

## Teardown

```bash
golem agent delete --id aria-sre-001
```

---

## Why this is impressive

| What the audience sees | What it demonstrates |
|---|---|
| One CLI command deploys a specialised agent | AGENTS.md + SKILL.md = zero rebuild, zero redeploy of the image |
| Agent greets with its exact persona | AGENTS.md injected into system prompt at boot |
| Structured Markdown reports every time | SKILL.md makes behaviour repeatable, not improvised |
| Live tool calls with real output | Tools run inside an isolated K8s pod — not a simulation |
| Secrets automatically redacted | The agent follows its constraints from AGENTS.md |
| `golem agent delete` tears it all down | Full sandbox lifecycle in seconds |
