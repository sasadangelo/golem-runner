# Golem Demo — Gianluca, the Document Knowledge Assistant

**Audience:** platform engineers, IBM architects, knowledge-management advocates.
**Duration:** ~10 minutes.
**What it shows:** deploy an LLM-powered document wiki agent from the CLI,
upload documents through a web UI, ask questions about their content with
footnote citations, and compile a structured wiki — all through a single chat.

---

## Architecture

```
Browser
  └── http://localhost:3000 ──► llmwiki-web (Next.js)
                                     │ REST  http://localhost:8000
                                     ▼
┌──────────────────────────────────────────────────────┐
│  Pod: llmwiki  (emptyDir /workspace shared)          │
│                                                      │
│  container: api  :8000  ◄── upload, browse, CRUD     │
│  container: mcp  :8080  ◄── MCP tools for Gianluca   │
│                                                      │
│  /workspace/                                         │
│    wiki/          ← compiled wiki pages (Markdown)   │
│    *.pdf / *.md   ← raw uploaded sources             │
│    .llmwiki/                                         │
│      index.db    ← SQLite FTS index                  │
└──────────────────────────────────────────────────────┘
        ▲  MCP  http://llmwiki-mcp:8080/mcp
        │
  ┌─────┴──────┐
  │  Gianluca  │  golem-runner agent (demo-doc-001)
  └────────────┘
```

**Data lives for the lifetime of the pod** (emptyDir) — sufficient for a demo.

---

## Prerequisites

```bash
# 1. Start minikube
minikube start

# 2. Configure the Golem CLI
golem cp add --name minikube --url http://$(minikube ip):9000
golem cp use --name minikube

# 3. Make sure llmwiki is cloned
ls /Users/sasadangelo/github.com/lucasastorian/llmwiki/mcp   # must exist
```

---

## Step 1 — Deploy the llmwiki stack (once per cluster)

```bash
examples/demo-doc/mcp/llmwiki/deploy.sh
```

The script builds three container images (mcp, api, web), loads them into
minikube, and deploys two Helm releases:
- `llmwiki` — single pod containing the mcp and api containers
- `llmwiki-web` — stateless Next.js UI

Wait for both pods:
```bash
kubectl rollout status deployment/llmwiki
kubectl rollout status deployment/llmwiki-web
```

---

## Step 2 — Deploy the agent

```bash
examples/demo-doc/deploy.sh
```

Wait for the agent:
```bash
golem agent status --id demo-doc-001
# → running
```

---

## Step 3 — Expose services to your laptop

Run each in a separate terminal:

```bash
kubectl port-forward svc/llmwiki-mcp  8080:8080   # MCP  → agent
kubectl port-forward svc/llmwiki-api  8000:8000   # API  → UI
kubectl port-forward svc/llmwiki-web 3000:3000    # UI → browser
```

---

## Step 4 — Upload documents via the UI

Open **http://localhost:3000** in your browser.

The UI opens directly in the wiki workspace (local mode, no login required).

1. Click **Sources** → **Upload**
2. Drag and drop a PDF (e.g. `attention-is-all-you-need.pdf`)
3. The file is indexed in the background — the status changes to **ready**
   within a few seconds for text PDFs.

You can also create a plain text note directly from the UI.

---

## Step 5 — Chat with Gianluca

```bash
golem chat --id demo-doc-001
```

### Opening

```
Hi Gianluca, what can you help me with?
```

> Gianluca calls `guide`, discovers the workspace and uploaded sources.

---

### Build the wiki from the uploaded PDF

```
I've uploaded attention-is-all-you-need.pdf — read it and create wiki pages.
```

> Gianluca calls:
> 1. `search(mode="list")` — confirms the file is there
> 2. `read(path="attention-is-all-you-need.pdf", pages="1-10")`
> 3. `create` — `/wiki/concepts/attention-mechanism.md`
> 4. `create` — `/wiki/entities/transformer.md`
> 5. `edit`   — `/wiki/overview.md` updated with key findings

---

### Ask a question

```
What are the main contributions of the Transformer paper?
```

> Gianluca searches, reads matched chunks, answers with citations:
> "The paper introduces self-attention[^1] and eliminates recurrence[^2]."
> `[^1]: attention-is-all-you-need.pdf, p.2`
> `[^2]: attention-is-all-you-need.pdf, p.3`

---

### Browse the result in the UI

Refresh **http://localhost:3000** — the wiki pages Gianluca created appear
in the sidebar under **Wiki**. Click any page to read it with full Markdown
rendering, Mermaid diagrams, and LaTeX math.

---

### Check wiki health

```
Is the wiki in good shape?
```

> Gianluca calls `lint(knowledge_base="...", path="*")` and reports any
> missing frontmatter, uncited sources, or broken links.

---

## Teardown

```bash
golem agent delete --id demo-doc-001
helm uninstall llmwiki llmwiki-web
```

---

## Why this works for the demo

| What the audience sees | What it demonstrates |
|---|---|
| Upload a PDF in the browser → Gianluca builds a wiki | MCP + REST API share the same filesystem |
| One CLI command deploys the whole stack | emptyDir is enough for a demo |
| Ask questions → cited answers from YOUR documents | RAG without extra infrastructure |
| Browse the compiled wiki at localhost:3000 | Full UI on top of the same data |
| `lint` catches hygiene issues automatically | Structured output via tool contract |
