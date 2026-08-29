# Golem Runner — API Reference

The Golem Runner exposes a minimal HTTP/WebSocket API used by the Control Plane chat proxy,
the A2A protocol, and automation triggers.

---

## `GET /.well-known/agent.json`

A2A Agent Card — published at runner boot, fetched by the Control Plane for peer discovery.

**Response `200`**
```json
{
  "id": "golem-agent-001",
  "name": "Golem Agent Runner",
  "description": "Generic automation agent powered by Golem.",
  "version": "0.1.0",
  "endpoint": "http://golem-agent-001.golem-agent-001.svc.cluster.local:8000",
  "capabilities": { "streaming": true, "pushNotifications": false },
  "skills": [
    { "id": "bash", "name": "bash" },
    { "id": "http_check", "name": "http_check" }
  ]
}
```

---

## `POST /a2a/tasks/send`

Inbound A2A task — accepts a task delegated by a peer agent or submitted by the Control Plane broker.

**Request**
```json
{
  "id": "task-abc123",
  "message": {
    "role": "user",
    "parts": [{ "type": "text", "text": "Check if https://google.com is reachable" }]
  }
}
```

**Response `200`**
```json
{
  "id": "task-abc123",
  "status": { "state": "completed" },
  "artifacts": [{ "parts": [{ "type": "text", "text": "Status Code: 301 ..." }] }]
}
```

---

## `WS /ws/chat`

Human-facing streaming chat endpoint. Used by the Control Plane WebSocket proxy.

**Protocol**

| Direction | Format | Content |
|---|---|---|
| Client → Runner | UTF-8 text | User message (plain text) |
| Runner → Client | UTF-8 text | One LLM token per frame |
| Runner → Client | `[DONE]` | End-of-response sentinel |
| Runner → Client | `[ERROR] …` | Error message if the loop fails |

**Query parameters (optional)**

| Parameter | Description |
|---|---|
| `conversation_id` | UUID identifying the conversation; absent → new conversation created |

**Manual test**
```bash
# requires: npm i -g wscat
wscat -c "ws://localhost:8000/ws/chat?conversation_id=my-conv-1"
# type your message and press Enter
```

---

## `GET /health`

Liveness probe used by the Kubernetes startup and liveness probes.

**Response `200`**
```json
{ "status": "ok" }
```
