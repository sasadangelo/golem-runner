# Skill: inspect-env

## When to use this skill

Apply this skill whenever the user asks to:
- "what container / pod / environment am I running in?"
- "show me the system info / memory / disk / CPU"
- "what environment variables are set?" (redact secrets)
- "what processes are running?"
- "show me the mounted files" / "what's in /app?"
- "show me the logs" (read from a known path)
- general container or system introspection

## Protocol — follow these steps exactly

Run the bash commands below in sequence. Skip any command that requires a binary
not present in a minimal Python Docker image.

### Step 1 — Identity

```bash
echo "=== Hostname ===" && hostname
echo "=== Kernel ===" && uname -a
echo "=== OS ===" && cat /etc/os-release 2>/dev/null | head -5
```

### Step 2 — Resource snapshot

```bash
echo "=== CPU cores ===" && nproc
echo "=== Memory ===" && free -h 2>/dev/null || cat /proc/meminfo | head -6
echo "=== Disk ===" && df -h / 2>/dev/null
```

### Step 3 — Mounted files (agent configuration)

```bash
echo "=== /app contents ===" && ls -lh /app/ 2>/dev/null
echo "=== /app/skills ===" && ls -lh /app/skills/ 2>/dev/null || echo "(no skills directory)"
echo "=== config.yaml ===" && cat /app/config.yaml 2>/dev/null | grep -v api_key
```

### Step 4 — Environment variables (redact secrets)

```bash
env | grep -viE '(key|token|secret|password|passwd|credential)' | sort
```

### Step 5 — Running processes

```bash
ps aux 2>/dev/null || ps -ef 2>/dev/null
```

## Report template

```
## Container Environment Report

### Identity
- **Hostname**: <value>
- **OS**: <value>
- **Kernel**: <value>

### Resources
- **CPU cores**: <value>
- **Memory**: <value>
- **Disk (/)**: <value>

### Agent Configuration
<summary of what's mounted at /app — config.yaml present? AGENTS.md? skills?>

### Environment Variables
<table or list — sensitive values redacted as [REDACTED]>

### Processes
<list of running processes>

### Assessment
<one paragraph — is the environment healthy? anything unusual?>
```

## Important

- Any value that looks like an API key, token, or password must be printed as `[REDACTED]`.
- Do not print the content of `.env` files.
