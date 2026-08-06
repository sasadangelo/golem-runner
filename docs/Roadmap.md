# Golem Runner — Roadmap

> This roadmap covers the **golem-runner** component only.  
> For the full Golem platform roadmap see the [golem](https://github.com/sasadangelo/golem) repository.

---

## MVP — Week 1  `June W1`

**Goal:** Build and validate the generic agent container in isolation.

- [x] Docker image in Python + LangGraph (WatsonX / `langchain-ibm`)
- [x] Read `SYSTEM_PROMPT`, `ENABLED_SKILLS`, `WATSONX_*` from environment variables
- [x] Local Docker test: chat response + tool execution (`bash`, `http_check`) verified end-to-end
- [x] Expose `/.well-known/agent.json` — A2A Agent Card endpoint
- [x] Inbound A2A task endpoint `POST /a2a/tasks/send` (no external SDK — pure Pydantic, A2A v1.0 wire format)

**Deliverable:** a `docker run` command that starts a working, A2A-capable agent. ✅

---

## Post-MVP

| Phase | Item |
|---|---|
| Phase 2 | Background tasks: Cron, Timer, Webhook triggers |
| Phase 2 | Extract `golem-agent-sdk` (A2A lifecycle + identity) as standalone internal library |
| Phase 2 | Extract `golem-framework` (LLM abstraction) as standalone internal library |
| Phase 2 | Stateful Sandbox: PVC-backed agent pod for persistent state across sessions |
| Phase 2 | gVisor / Kata Containers for dynamic code execution |
| Phase 3 | `golem-framework` AutoGen backend |
| Phase 3 | `golem-framework` CrewAI backend |
| Phase 3 | A2A `SendMessage` delegation between agents |
| Phase 3 | Signed Agent Card validation |
