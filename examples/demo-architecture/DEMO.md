# Golem Demo — Angelo, the TRI Generator

**Audience:** security reviewers, platform architects, IBM management.
**Duration:** ~8 minutes.
**What it shows:** deploy a security analyst agent from the CLI, conduct a natural-language
interview about a new service, and receive a complete IBM-standard TRI document — in one
conversation, without touching a template manually.

---

## Prerequisites

```bash
# Control Plane running on minikube
minikube start

# CLI configured
golem cp add --name minikube --url http://$(minikube ip):9000
golem cp use --name minikube

# Fill in your WatsonX project ID in config.yaml
```

---

## Step 1 — Deploy the MCP filesystem server (once per cluster)

The MCP filesystem server gives Angelo read access to TRI templates and write access
to the output directory.

```bash
examples/demo-architecture/mcp/filesystem/deploy.sh
```

The server will be reachable at:
```
http://filesystem-mcp.default.svc.cluster.local:8080/mcp
```

## Step 2 — Deploy the MCP github server (once per cluster)

The MCP github server gives Angelo read access to github PR creation.

```bash
examples/demo-architecture/mcp/github/deploy.sh
```

The server will be reachable at:
```
http://github-mcp.default.svc.cluster.local:8080/mcp
```

---

## Step 3 — Deploy the agent (10 seconds)

```bash
examples/demo-architecture/deploy.sh
```

Expected output:
```
Agent created: id=demo-architecture-001  namespace=demo-architecture-001  name=Angelo — TRI Generator  status=pending
```

Wait for the pod to start:
```bash
golem agent status --id demo-architecture-001
# → running
```

---

## Step 3 — Open a chat session

```bash
golem chat --id demo-architecture-001
```

---

## Demo conversation

### Opening — Angelo introduces itself

```
Hi Angelo, I need to onboard a new service.
```

> Angelo introduces herself and starts the interview with Question 1.

---

### The interview (12 questions — ~5 minutes)

Feed Angelo the following answers one by one.
Each answer triggers the next question automatically.

| Q# | Your answer |
|----|-------------|
| 1 | "PaymentGateway — handles PCI-DSS card transactions for IBM TLS clients" |
| 2 | "PM Owner: Anna Rossi, anna.rossi@ibm.com — Dev Owner: Luca Bianchi, l.bianchi@ibm.com" |
| 3 | "Approver: Security team, sec-review@ibm.com — Reviewer: Platform team, platform@ibm.com" |
| 4 | "Access to PostgreSQL on IBM Cloud, access to Stripe API, IBM AppID available" |
| 5 | "95% of transactions processed in < 2s, zero card data stored in plain text, SOC2 compliant" |
| 6 | "Two Python microservices: payment-api (FastAPI, port 443) and transaction-logger (async). Uses IBM Granite 3.8B for fraud-pattern detection via WatsonX." |
| 7 | "Kubernetes Cluster (IKS), IBM Cloud Services (Stripe API, AppID), Internet (API Connect gateway)" |
| 8 | "POST /payments — public, behind IBM API Connect, authenticated via OAuth2 AppID tokens" |
| 9 | "Client → API Connect: HTTPS TLS 1.3, card token (no raw PAN), classification: client-SPI. API Connect → payment-api: mTLS, same classification." |
| 10 | "PostgreSQL on IBM Cloud: transaction logs, AES-256, Key Protect, 7-year retention. No card PANs stored." |
| 11 | "IBM AppID (auth), IBM API Connect (gateway), Stripe API (tokenization), IBM Secrets Manager (credentials), IBM Key Protect (encryption keys)" |
| 12 | "HA: 2 replicas across 2 AZs. CI/CD: OnePipeline. Alerting: PagerDuty on p95 latency > 3s. Security concern: Stripe API egress must be whitelisted via Calico." |

---

### Generation

```
Yes, generate the TRI.
```

> Angelo reads the template via MCP filesystem, fills all sections, outputs the complete TRI.

Expected output includes:
```
✅ Phase 2 complete — TRI generated for PaymentGateway.
Ready to save and open a PR. Shall I proceed?
```

---

### Save

```
Yes, save it.
```

> Angelo writes the file to `/data/tri-output/TRI-PaymentGateway-<YYYY-MM>.md` via MCP.

```
✅ Phase 3 complete — TRI saved to /data/tri-output/TRI-PaymentGateway-2026-08.md
```

---

## Teardown

```bash
golem agent delete --id demo-architecture-001

# Optional: remove the MCP filesystem server
kubectl delete namespace golem-mcp-shared
```

---

## Why this is impressive

| What the audience sees | What it demonstrates |
|---|---|
| One CLI command deploys a specialised security analyst | AGENTS.md + SKILL.md = zero rebuild |
| Agent asks questions one by one, stays in context | Multi-turn conversation via WebSocket |
| 12 questions → complete IBM-standard TRI | SKILL.md encodes the IBM protocol |
| Template read from filesystem via MCP | MCP tools connected at boot |
| File written to disk via MCP | Agentic I/O, not just text generation |
| What took 2 days of back-and-forth takes 8 minutes | The wow moment for management |
