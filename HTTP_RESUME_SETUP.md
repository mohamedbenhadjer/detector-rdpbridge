# HTTP Resume Endpoint - Quick Setup Guide

## Overview

The HTTP resume endpoint allows your agent to programmatically resume a held Playwright script by sending an HTTP POST request, eliminating the need to manually touch a file.

## Prerequisites

✅ **PYTHONPATH must be set** (critical!)
```bash
export PYTHONPATH="/home/mohamed/detector-rdpbridge:$PYTHONPATH"
```

Without this, Python will not load the custom `sitecustomize.py` and the HTTP server won't start.

## Complete Configuration

```bash
# 1. Required: PYTHONPATH
export PYTHONPATH="/home/mohamed/detector-rdpbridge:$PYTHONPATH"

# 2. Required: Authentication token
export MINIAGENT_TOKEN="your-flutter-token"

# 3. Required: Hold mode
export MINIAGENT_ON_ERROR=hold

# 4. Enable HTTP resume endpoint
export MINIAGENT_RESUME_HTTP=1
export MINIAGENT_RESUME_HTTP_TOKEN="strong-shared-secret"

# 5. Optional: customize host/port (defaults shown)
export MINIAGENT_RESUME_HTTP_HOST=127.0.0.1
export MINIAGENT_RESUME_HTTP_PORT=8787
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
```

## Verification

Test that the endpoint is running:

```bash
# Start a Python script that imports sitecustomize
python -c "import sitecustomize; import time; time.sleep(30)" &

# Wait a moment for server to start
sleep 2

# Test the endpoint
curl -v -X POST http://127.0.0.1:8787/resume \
  -H "Authorization: Bearer strong-shared-secret"

# Expected response:
# HTTP/1.0 200 OK
# {"ok": true}
```

## Agent Integration

When your agent finishes fixing an issue and wants to resume the script:

### Dart/Flutter Example

```dart
import 'package:http/http.dart' as http;

Future<void> resumePlaywrightRun({
  required String host,
  required int port,
  required String token,
}) async {
  final uri = Uri.parse('http://$host:$port/resume');
  final res = await http.post(
    uri,
    headers: {'Authorization': 'Bearer $token'},
  );
  
  if (res.statusCode != 200) {
    throw Exception('Resume failed (${res.statusCode}): ${res.body}');
  }
  
  print('Resume signal sent successfully');
}

// Usage:
await resumePlaywrightRun(
  host: '127.0.0.1',
  port: 8787,
  token: 'strong-shared-secret',
);
```

### JavaScript/Node Example

```javascript
async function resumePlaywrightRun({ host, port, token }) {
  const res = await fetch(`http://${host}:${port}/resume`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
  
  if (!res.ok) {
    throw new Error(`Resume failed ${res.status}: ${await res.text()}`);
  }
  
  console.log('Resume signal sent successfully');
}

// Usage:
await resumePlaywrightRun({
  host: '127.0.0.1',
  port: 8787,
  token: 'strong-shared-secret',
});
```

### Bash/Shell Example

```bash
curl -sS -X POST http://127.0.0.1:8787/resume \
  -H "Authorization: Bearer $MINIAGENT_RESUME_HTTP_TOKEN"
```

## Targeting Specific Runs (Multiple Concurrent Scripts)

If running multiple Playwright scripts simultaneously, use one of these strategies:

### Option 1: Unique Port Per Run

```bash
# Script 1
export MINIAGENT_RESUME_HTTP_PORT=8787
python script1.py &

# Script 2
export MINIAGENT_RESUME_HTTP_PORT=8788
python script2.py &
```

Agent maps `runId` → port and calls the correct endpoint.

### Option 2: Unique Token Per Run

```bash
# Script 1
export MINIAGENT_RESUME_HTTP_TOKEN="token-for-run-abc123"
python script1.py &

# Script 2
export MINIAGENT_RESUME_HTTP_TOKEN="token-for-run-def456"
python script2.py &
```

Agent maps `runId` → token and uses the appropriate Bearer token.

### Option 3: Unique Resume File Per Run

```bash
# Script 1
export MINIAGENT_RESUME_FILE="/tmp/miniagent_resume_abc123"
python script1.py &

# Script 2
export MINIAGENT_RESUME_FILE="/tmp/miniagent_resume_def456"
python script2.py &
```

HTTP endpoint writes to that specific file.

## Troubleshooting

### Connection Refused

**Problem:** `curl: (7) Failed to connect to 127.0.0.1 port 8787`

**Solutions:**
1. ✅ Verify PYTHONPATH is set: `echo $PYTHONPATH` should include `/home/mohamed/detector-rdpbridge`
2. ✅ Verify HTTP resume is enabled: `echo $MINIAGENT_RESUME_HTTP` should be `1`
3. ✅ Verify token is set: `echo $MINIAGENT_RESUME_HTTP_TOKEN` should not be empty
4. ✅ Check if server started: Look for log "Resume HTTP server listening on http://127.0.0.1:8787"
5. ✅ Check port isn't already in use: `ss -ltnp | grep 8787`

### 401 Unauthorized

**Problem:** HTTP endpoint returns `{"ok": false, "error": "unauthorized"}`

**Solutions:**
1. ✅ Token mismatch: ensure the Bearer token in the request matches `MINIAGENT_RESUME_HTTP_TOKEN`
2. ✅ Check header format: must be `Authorization: Bearer <token>` (note the space after "Bearer")

### Script Still Doesn't Resume

**Problem:** HTTP returns 200 OK but script stays paused

**Solutions:**
1. ✅ Verify hold mode is active: `echo $MINIAGENT_ON_ERROR` should be `hold`
2. ✅ Check resume file was created: `ls -la /tmp/miniagent_resume` (or your custom path)
3. ✅ Check script logs for "Resume signal detected; continuing."
4. ✅ Ensure the HTTP endpoint and script are in the same filesystem namespace (not different containers)

### Cross-Container/Host Access

**Problem:** Agent runs in different container/host than the script

**Solutions:**
1. ✅ Bind to reachable interface: `export MINIAGENT_RESUME_HTTP_HOST=0.0.0.0` (or specific IP)
2. ✅ Expose/publish the port if using Docker: `docker run -p 8787:8787 ...`
3. ✅ Use SSH tunnel: `ssh -L 8787:localhost:8787 script-host`
4. ✅ Agent calls the script host's IP instead of 127.0.0.1

## Logs and Monitoring

Expected log sequence when resume works:

```
# At script start:
[INFO] Resume HTTP server listening on http://127.0.0.1:8787

# When error occurs:
[WARNING] Holding on error (TimeoutError) - waiting for agent. Resume file: /tmp/miniagent_resume

# When agent calls /resume:
resume-http: 127.0.0.1 - - "POST /resume HTTP/1.1" 200 -
[INFO] Resume HTTP: resume signal emitted via file

# Script continues:
[INFO] Resume signal detected; continuing.
```

## Security Notes

- Default bind is `127.0.0.1` (localhost only) for security
- Token is **required** to prevent accidental/malicious resume
- If exposing beyond localhost:
  - Use strong token (32+ random chars)
  - Restrict with firewall rules
  - Consider SSH tunneling instead of public exposure
- Do not log full tokens in production

## Next Steps

1. Test with `test_hold_mode.py` to verify end-to-end flow
2. Integrate resume call into your agent's "session end" workflow
3. Store runId → (port or token) mapping when support requests arrive
4. Call the correct endpoint when agent completes its work

---

For more details, see:
- `HOLD_MODE_IMPLEMENTATION.md` - Technical details
- `HOLD_MODE_TEST.md` - Test scenarios
- `README.md` - Full configuration reference

