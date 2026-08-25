# Skill: inspect-k8s

## When to use this skill

Apply this skill whenever the user asks to:
- "list pods / deployments / services in namespace X"
- "what's running in the cluster?"
- "check the status of deployment Y"
- "show me the events for pod Z"
- "is there anything failing in namespace X?"
- any Kubernetes resource inspection or cluster health question

## Important

This skill uses **MCP tools provided by the kubernetes-mcp-server**.
Do NOT use `bash` + `kubectl` — use the MCP tools directly.
The MCP tools are available as functions you can call (e.g. `list_pods`, `get_deployment`, `list_events`).

## Protocol — follow these steps exactly

### Step 1 — Identify the scope

Determine from the user message:
- **Namespace**: explicit (e.g. "in namespace foo") or all namespaces if not specified
- **Resource type**: pods, deployments, services, events, configmaps, etc.
- **Filter**: name pattern, label selector, status (e.g. "failing", "not ready")

### Step 2 — Call the appropriate MCP tool

| User intent | MCP tool to call |
|-------------|-----------------|
| List pods | `list_pods` (namespace param) |
| Get pod details | `get_pod` (name + namespace) |
| List deployments | `list_deployments` (namespace) |
| Get deployment | `get_deployment` (name + namespace) |
| List services | `list_services` (namespace) |
| List events | `list_events` (namespace, optionally filtered by object) |
| List namespaces | `list_namespaces` |
| Get cluster info | `cluster_info` |

### Step 3 — Identify anomalies

Look for:
- Pods in `Pending`, `CrashLoopBackOff`, `Error`, `OOMKilled` state
- Deployments where `ready` < `desired`
- Warning events (reason: `BackOff`, `Failed`, `OOMKilling`, `Evicted`)
- Services with no endpoints

### Step 4 — Report using this template

```
## Kubernetes Inspection — <scope>

**Namespace**: <value or "all">
**Resource**: <type>

### Status Summary
<table: name | status | age | notes>

### Anomalies Detected
<bullet list of problems found, or "None detected.">

### Recommendations
<numbered, actionable steps — or "No action required.">
```

## Example invocations

- "List all pods in the default namespace"
- "Is anything failing in the cluster?"
- "Show me the events for the golem-control-plane namespace"
- "Check the status of all deployments"
- "What namespaces exist in this cluster?"
