# Golem Demo — A2A Multi-Agent Pipeline

**Audience:** business and technical stakeholders.
**Duration:** ~8 minutes.
**What it shows:** two isolated agents collaborate autonomously — a Log Analyzer
inspects live application logs and delegates report writing to a specialist
Report Writer agent, all triggered by a single CLI command.

```
User (CLI)
    │  golem agent task-send
    ▼
log-analyzer-001
    │  bash curl → mock-log-service /logs
    │  delegate_to_agent("report-writer-001", findings)
    ▼
report-writer-001
    │  bash date
    │  produces Markdown incident report
    ▼
  task result visible on both agents
```

---

## Prerequisites

```bash
# Minikube running
minikube start

# Control Plane deployed (via app.sh or helm)

# CLI configured
golem cp add --name local --url http://$(minikube ip):9000
golem cp use --name local
```

---

## Step 1 — Deploy the mock log service

```bash
examples/demo-a2a/mock-log-service/deploy.sh
```

Verify:
```bash
kubectl port-forward -n demo-a2a svc/mock-log-service 8080:8080 &
curl http://localhost:8080/logs | python3 -m json.tool | head -20
# → 20 healthy INFO entries
```

---

## Step 2 — Deploy the two agents (20 seconds)

```bash
examples/demo-a2a/deploy.sh
```

Expected output:
```
==> Deploying report-writer-001...  ✓
==> Deploying log-analyzer-001...   ✓
```

Wait for pods to reach RUNNING:
```bash
golem agent status --id report-writer-001   # → running
golem agent status --id log-analyzer-001    # → running
```

---

## Step 3 — Inject errors into the mock service 🔴

```bash
curl -X POST http://localhost:8080/admin/inject-errors?count=15
# → {"injected": 15, "error_mode": true}

curl http://localhost:8080/health
# → {"status": "degraded", "error_mode": true}
```

---

## Step 4 — Trigger the pipeline with one CLI command 🚀

```bash
golem agent task-send --agent log-analyzer-001 \
  --message "Analyse the application logs and produce a formal incident report."
```

Expected output:
```
Task submitted: id=task-abc123  status=submitted
Poll result with: golem agent task-get --agent log-analyzer-001 --task task-abc123
```

> **Tip:** add `--wait --timeout 300` to block until the task completes:
> ```bash
> golem agent task-send --agent log-analyzer-001 \
>   --message "Analyse the application logs and produce a formal incident report." \
>   --wait --timeout 300
> ```

---

## Step 5 — Watch the delegation chain

```bash
# Log Analyzer — ran analysis, delegated to Report Writer
golem agent tasks --agent log-analyzer-001

# Report Writer — received the delegated task (source=a2a), wrote the report
golem agent tasks --agent report-writer-001
```

You will see:
- `log-analyzer-001`: one task `source=golem-cli` → `working` → `completed`
- `report-writer-001`: one task `source=a2a` → `working` → `completed` (delegated automatically)

Poll until both reach `completed` (the log-analyzer waits internally for the report-writer via polling).

---

## Step 6 — Read the final report

```bash
# Read the log-analyzer result (includes the full report produced by report-writer):
golem agent task-get --agent log-analyzer-001 --task <task_id>

# Or read the report-writer result directly:
golem agent tasks --agent report-writer-001
golem agent task-get --agent report-writer-001 --task <task_id>
```

The result is a structured Markdown incident report.

---

## Step 7 — Restore the service 🟢

```bash
curl -X POST http://localhost:8080/admin/clear-errors
# → {"error_mode": false, "message": "Errors cleared."}
```

---

## Cleanup

```bash
golem agent delete --id log-analyzer-001
golem agent delete --id report-writer-001
kubectl delete namespace demo-a2a
# Optional: helm uninstall -n kubernetes-mcp-server kubernetes-mcp-server
```

---

## Why this is impressive

| What the audience sees | What it demonstrates |
|---|---|
| One CLI command triggers a 2-agent pipeline | A2A delegation — agents calling agents |
| Log Analyzer never writes the report | Clean separation of responsibilities |
| Report Writer never touches logs | Each agent does exactly one thing |
| Task visible on both agents independently | Full observability of multi-agent execution |
| Each agent is an isolated K8s pod | Real distributed system, not a monolith |
| Zero code — only AGENTS.md + config.yaml | Configuration-driven multi-agent intelligence |
| Kubernetes MCP gives live cluster context | Real infrastructure data in the analysis |
