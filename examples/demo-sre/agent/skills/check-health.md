# Skill: check-health

## When to use this skill

Apply this skill whenever the user asks to:
- "check if [service/URL] is up / reachable / healthy"
- "probe the health endpoint of [service]"
- "is [URL] responding?"
- perform any HTTP health check, liveness or readiness verification

## Protocol — follow these steps exactly

1. **Extract the target URL** from the user message.
   - If the URL uses a Kubernetes service DNS name (e.g. `http://my-svc.namespace.svc.cluster.local:8080/health`),
     use it as-is — the runner pod is inside the cluster.
   - If the user gives a bare hostname (e.g. `google.com`), prepend `https://`.

2. **Call `http_check`** with the target URL.

3. **Interpret the result**:
   | Status code | Verdict |
   |-------------|---------|
   | 200–299     | ✅ Healthy |
   | 300–399     | ⚠️ Redirect — note the final location |
   | 400–499     | ❌ Client error — check path / authentication |
   | 500–599     | 🔴 Server error — service is degraded or down |
   | Connection error | 🔴 Unreachable — network or DNS issue |

4. **Report** using this template:

```
## Health Check — <URL>

**Status**: <verdict emoji> <HTTP status code> <reason phrase>
**Response time**: <if available, otherwise omit>
**Body preview**: <first 200 chars of response body>

### Interpretation
<one-sentence explanation of what the status means>

### Recommendations
<numbered list of next steps, or "No action required." if healthy>
```

## Example invocations the user might give

- "Check if https://google.com is up"
- "Is the runner itself healthy? probe /health"
- "Can this pod reach https://us-south.ml.cloud.ibm.com ?"
- "Check all of these endpoints: ..."

## Self-check

If the user asks to check the runner's own health endpoint, use `http://localhost:8000/health`.
