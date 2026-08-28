# Demo — Matteo: Monitoring Agent

Matteo is an autonomous monitoring agent that checks a service every 30 seconds and sends
Slack alerts when it goes down — and a recovery notification when it comes back up.

No open chat session required. The agent runs entirely in background.

```
[timer: every 30s]
      ↓
  http_check → mock-service /health
      ↓
  status 200?  →  log "✅ healthy"
  status 503?  →  bash curl → Slack "🚨 SERVICE DOWN"
                  (next tick, if 200 again) → Slack "✅ SERVICE RECOVERED"
```

---

## Prerequisites

| Tool | Purpose |
|---|---|
| `minikube` | Local Kubernetes cluster |
| `kubectl` | Cluster management |
| `podman` or `docker` | Image builds |
| `golem` CLI | Agent lifecycle management |
| Slack workspace | Receive alerts |

---

## Step 1 — Create the Slack Incoming Webhook

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name it `Golem Monitor`, select your workspace
3. In the left sidebar → **Incoming Webhooks** → toggle **Activate Incoming Webhooks** ON
4. Click **Add New Webhook to Workspace** → select your channel (e.g. `#alerts`) → **Allow**
5. Copy the webhook URL — it looks like:
   `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX`

---

## Step 2 — Configure secrets

```bash
cd examples/demo-monitor
cp .env.example .env
```

Edit `.env`:
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

## Step 3 — Deploy the mock service

```bash
examples/demo-monitor/mock-service/deploy.sh
```

This builds the mock service image, loads it into minikube, and deploys it in the
`demo-monitor` namespace. The service is reachable inside the cluster at:
```
http://mock-service.demo-monitor.svc.cluster.local:8080/health
```

Verify it is running:
```bash
kubectl port-forward -n demo-monitor svc/mock-service 8080:8080 &
curl http://localhost:8080/health
# → {"status": "ok", "service": "mock-service"}
```

---

## Step 4 — Deploy the Matteo agent

```bash
examples/demo-monitor/deploy.sh
```

This:
1. Creates the `demo-monitor-001` namespace
2. Injects `SLACK_WEBHOOK_URL` as a K8s Secret (`slack-credentials`)
3. Deploys the Matteo agent pod via `golem agent create`

The agent starts immediately and fires its first health check within 30 seconds.

---

## Step 5 — Watch the tasks accumulate

```bash
golem agent tasks --agent demo-monitor-001
```

Every 30 seconds a new `completed` task appears:
```
TASK ID                       STATUS        UPDATED AT                MESSAGE
----------------------------  ------------  ------------------------  --------
task-a3f1b2c4                 completed     2026-08-15 10:00:31       Check if http://mock-service…
task-b7e9f0a1                 completed     2026-08-15 10:01:01       Check if http://mock-service…
```

---

## Step 6 — Bring the service DOWN 🔴

```bash
curl -X POST http://localhost:8080/admin/down
# → {"status": "DOWN", "message": "Service is now down…"}
```

Within 30 seconds:
- A new task appears with status `completed`
- **Your Slack channel receives:**
  > 🚨 *SERVICE DOWN* — `http://mock-service.demo-monitor.svc.cluster.local:8080/health` returned HTTP 503. Immediate attention required.

---

## Step 7 — Bring the service back UP 🟢

```bash
curl -X POST http://localhost:8080/admin/up
# → {"status": "UP", "message": "Service is back up…"}
```

Within 30 seconds:
- **Your Slack channel receives:**
  > ✅ *SERVICE RECOVERED* — `http://mock-service.demo-monitor.svc.cluster.local:8080/health` is back up (HTTP 200).

---

## Cleanup

```bash
kubectl delete namespace demo-monitor-001
kubectl delete namespace demo-monitor
```
