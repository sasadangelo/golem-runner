# Analyse Application Logs

## When to use this skill

Use this skill when asked to fetch and analyse logs from the mock-log-service.

## Step-by-step procedure

1. Fetch the logs:
   ```bash
   curl -s "http://mock-log-service.demo-a2a.svc.cluster.local:8080/logs?limit=100"
   ```

2. Parse the JSON response — it has this shape:
   ```json
   {"count": N, "entries": [{"timestamp": "...", "level": "...", "service": "...",
    "status": 200, "latency_ms": 42, "message": "...", "stack_trace": "..."}, ...]}
   ```

3. Count entries by `status` code. Identify all entries where `status == 500`.

4. For each HTTP 500 entry collect: `service`, `path`, `latency_ms`, `message`, `stack_trace`.

5. Compute:
   - Total entries analysed
   - Number and percentage of HTTP 500 errors
   - List of unique affected services
   - Mean `latency_ms` for 500 entries vs non-500 entries
   - Most common pattern in `stack_trace` (if present)

6. Produce the FINDINGS block and delegate to `report-writer-001`.
