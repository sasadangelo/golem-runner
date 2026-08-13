# Golem Demo — Aria, the SRE Agent

**Audience:** technical or semi-technical stakeholders.
**Duration:** ~7 minutes.
**What it shows:** deploy a specialised agent from the CLI in seconds, then have a natural
conversation that uses real tools — including live Kubernetes cluster inspection via MCP.

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

## Step 1 — Deploy the kubernetes-mcp-server (once per cluster)

```bash
helm upgrade -i -n kubernetes-mcp-server --create-namespace kubernetes-mcp-server \
  oci://ghcr.io/containers/charts/kubernetes-mcp-server \
  -f examples/demo-sre/mcp/values.yaml
```

Wait for the MCP server to be ready:
```bash
kubectl rollout status -n kubernetes-mcp-server deployment/kubernetes-mcp-server
```

The server will be reachable at:
```
http://kubernetes-mcp-server.kubernetes-mcp-server.svc.cluster.local:8080
```

---

## Step 2 — Deploy the agent (10 seconds)

```bash
golem agent create \
  --config   examples/demo-sre/config.yaml \
  --agents-md examples/demo-sre/AGENTS.md \
  --skill    examples/demo-sre/check-health.md \
  --skill    examples/demo-sre/inspect-env.md \
  --skill    examples/demo-sre/inspect-k8s.md
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

## Step 3 — Open a chat session

```bash
golem chat --id aria-sre-001
```

---

## Demo conversation

### Intro — the agent knows who it is and what tools it has
```
Who are you and what can you do?
```
> Aria introduces herself, lists her tools including Kubernetes inspection via MCP.

---

### Live HTTP health check
```
Check if https://google.com is reachable and give me a structured report.
```
> Aria calls `http_check`, interprets the status code, returns a formatted report.

---

### Container introspection
```
Give me a full environment report of this container: resources, mounted files, running processes.
```
> Aria runs bash commands and returns a structured Markdown report.

---

### Kubernetes inspection — the new "wow moment"
```
List all pods across all namespaces and tell me if anything is failing.
```
> Aria calls MCP kubernetes tools (`list_pods`), scans all namespaces, identifies any
> pods in `Pending`, `CrashLoopBackOff`, or `Error` state, and returns a structured report.

---

### Cross-tool multi-step diagnostic
```
The golem-control-plane namespace might have issues. Check the pod statuses there,
look for any warning events, and also verify the control plane HTTP endpoint is reachable.
```
> Aria:
> 1. Calls MCP `list_pods` for the `golem-control-plane` namespace
> 2. Calls MCP `list_events` for the same namespace
> 3. Calls `http_check` on the control plane endpoint
> 4. Synthesises all results into a single incident report

---

### Cluster overview
```
Give me a full cluster health report: namespaces, deployments, any failing workloads.
```
> Aria calls `list_namespaces`, `list_deployments` across namespaces, correlates with
> events, and produces a complete cluster health summary.

---

## Teardown

```bash
golem agent delete --id aria-sre-001

# Optional: remove the MCP server
helm uninstall -n kubernetes-mcp-server kubernetes-mcp-server
```

---

## Why this is impressive

| What the audience sees | What it demonstrates |
|---|---|
| One CLI command deploys a specialised agent | AGENTS.md + SKILL.md = zero rebuild |
| Agent greets with its exact persona | AGENTS.md injected at boot |
| Structured Markdown reports every time | SKILL.md makes behaviour repeatable |
| Live Kubernetes queries — pods, events, deployments | MCP tools connected at boot via `mcp_servers` in config.yaml |
| Multi-tool cross-correlation | HTTP check + K8s events in one response |
| `golem agent delete` tears it all down | Full sandbox lifecycle in seconds |
