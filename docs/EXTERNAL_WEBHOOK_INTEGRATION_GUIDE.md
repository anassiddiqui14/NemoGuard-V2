# NemoGuard — External Webhook Integration Guide (Watcher Agent Endpoint)

*For a teammate wiring up a real AWS Lambda (or any monitoring source) to
stream alerts into NemoGuard.*

---

## 1. The endpoint

```
POST /api/v2/ingest/webhook
```

This is the **Watcher Agent** entry point — every alert lands here first.
It is **intentionally unauthenticated** (real monitoring systems can't be
issued NemoGuard JWTs), but is protected by:
- 60 requests/minute per source IP (rate limit)
- 64KB max payload size, max nesting depth 12, max 200 items/level
- optional HMAC-SHA256 signature verification (opt-in per source)
- replay protection (timestamp + event_id dedup)

**Current live URL:**
```
https://llc-evaluate-wearing-file.trycloudflare.com/api/v2/ingest/webhook
```

⚠️ Run `./scripts/get_webhook_url.sh` before sharing this with anyone —
see §5 for why the URL can change and how it's kept running persistently.

## 2. Payload format

**Any reasonable JSON shape works.** The Watcher Agent (an LLM) reads
whatever you send and normalizes it — you do not need to match an exact
schema. That said, sending these fields directly makes classification and
correlation more reliable:

```json
{
  "source_system": "AWS Lambda",
  "alert_type": "LAMBDA_INVOCATION_ERROR",
  "severity": "high",
  "message": "Human-readable description of what failed and why",
  "run_id": "unique-id-for-this-specific-execution/run"
}
```

| Field | Required? | Notes |
|---|---|---|
| `source_system` (or `source`) | recommended | Used for correlation + optional HMAC secret lookup |
| `alert_type` | recommended | Free text, e.g. `LAMBDA_INVOCATION_ERROR`, `OOM_KILLED`, `SCHEMA_VALIDATION_FAILED` |
| `severity` | recommended | `info`/`warning`/`high`/`critical` |
| `message` | recommended | Real error text — the more detail, the better the RCA agent's investigation |
| `run_id` | **important for correlation** | See §3 |

### Minimal working curl example (tested live)

```bash
curl -X POST https://<your-endpoint>/api/v2/ingest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "source_system": "AWS Lambda",
    "alert_type": "LAMBDA_INVOCATION_ERROR",
    "severity": "high",
    "message": "KeyError: '\''customer_id'\'' -- unhandled exception in handler.py line 42",
    "run_id": "arn:aws:lambda:us-east-1:123456789012:function:my-func:$LATEST-req-abc123"
  }'
```

Response: `{"status":"accepted_for_processing"}` — the alert is queued for
real (asynchronous) processing; it does not block your Lambda's response.

### From inside a real Lambda handler

```python
import json, urllib.request

def notify_nemoguard(error, context):
    payload = {
        "source_system": "AWS Lambda",
        "alert_type": type(error).__name__,
        "severity": "high",
        "message": f"{error} (function={context.function_name}, request_id={context.aws_request_id})",
        "run_id": context.aws_request_id,
    }
    req = urllib.request.Request(
        "https://<your-endpoint>/api/v2/ingest/webhook",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=5)
```

Call this from your Lambda's exception handler, or wire it as a
CloudWatch Alarm → SNS → a tiny forwarding Lambda that POSTs here.

## 3. Multiple alerts → ONE incident (correlation)

**This already works out of the box — verified live during this session.**

- Two alerts sharing the **same `run_id`** are always correlated into the
  same incident (deterministic match, highest confidence).
- Alerts without a shared `run_id` but from the same service/topology
  within a short time window are also correlated deterministically
  (`src/domain/correlator.py`).
- If neither deterministic signal applies, the Watcher Agent (LLM) makes a
  best-effort correlation guess, but only ever onto an incident that is
  still genuinely active (never onto a resolved/failed/cancelled one).

**Live proof (this session):**
```
POST .../webhook  {"run_id": "RUN-TEST-EXTERNAL-001", ...}
  -> created INC-67D52379

POST .../webhook  {"run_id": "RUN-TEST-EXTERNAL-001", ...}   (2nd alert, same run_id)
  -> correlated onto the SAME INC-67D52379 (confirmed: 2 alerts, 1 incident)
```

**Practical guidance for your teammate:** if the same underlying failure
fires multiple alerts (e.g. a Lambda retries 3 times, or a CloudWatch
alarm and an SNS notification both fire for the same event), send them
all with the **same `run_id`** and NemoGuard will keep them as one
incident automatically. If you don't have a natural run_id, omit it —
correlation will still work via source/topology/time proximity, just with
slightly less certainty.

## 4. What happens after you POST

1. Watcher Agent classifies it as real signal (not noise) and normalizes it.
2. Correlator Engine decides: new incident, or attach to an existing one.
3. A Temporal workflow kicks off the full multi-agent investigation (RCA →
   Impact → Runbook → Grounding Critic) — this takes roughly 1-10 minutes
   depending on how many tools the RCA agent needs to call.
4. A recovery plan is produced and appears in the NemoGuard dashboard,
   `AWAITING_APPROVAL`. A human must approve before anything executes.

You (the sender) never need to poll or wait for any of this — your POST
returns immediately.

## 5. How the persistent tunnel is set up (and its one real limitation)

The webhook is exposed via a **Cloudflare quick tunnel**
(`cloudflared tunnel --url http://localhost:80`, no account/domain
needed) run as a **macOS LaunchAgent** so it survives terminal closes,
machine sleep, and crashes:

- Config: `~/Library/LaunchAgents/com.nemoguard.cloudflared.plist`
- `KeepAlive=true` → launchd automatically restarts the tunnel process if
  it ever dies for any reason.
- `RunAtLoad=true` → it also starts automatically on every login/reboot.
- Logs (including the current URL): `/tmp/nemoguard_cloudflared.log`

**Get the current URL at any time:**
```bash
./scripts/get_webhook_url.sh
```
This prints the live URL and runs a real health check against it.

### The one real limitation: no owned domain means the URL can change

Because no Cloudflare account/domain is configured, this is Cloudflare's
free "quick tunnel" — the process itself is now durable (it will not
silently die and stay dead), but a **genuine crash or reboot mints a
brand-new random subdomain**, since the quick-tunnel URL is tied to the
process's own session with Cloudflare's edge, not to anything durable.

**Confirmed live during setup:** a deliberate `kill -9` test caused the
URL to change from `https://micro-lace-containers-thumbnails.trycloudflare.com`
to `https://llc-evaluate-wearing-file.trycloudflare.com` within seconds
of launchd auto-restarting it.

**What this means in practice:**
- Under normal operation (no crash, no reboot), the URL you share today
  will keep working indefinitely — you do not need to babysit it.
- If the Mac reboots or the tunnel process genuinely crashes, re-run
  `./scripts/get_webhook_url.sh` and re-share the (possibly new) URL with
  your teammate.
- If you need a URL that **never** changes even across crashes/reboots,
  the only real fix is a Cloudflare **named** tunnel, which requires a
  Cloudflare account and a domain you control:
  ```bash
  cloudflared tunnel login
  cloudflared tunnel create nemoguard
  cloudflared tunnel route dns nemoguard nemoguard.yourdomain.com
  cloudflared tunnel run --url http://localhost:80 nemoguard
  ```
  (You'd then update the LaunchAgent's `ProgramArguments` to use
  `tunnel run nemoguard` instead of `tunnel --url http://localhost:80`.)
- Alternatively, if the Lambda is already in AWS, the most
  production-appropriate option is skipping tunnels entirely: deploy the
  `api` container with a public IP/DNS and point the Lambda directly at
  `http://<host>:8000/api/v2/ingest/webhook`.

### Managing the LaunchAgent

```bash
# Check it's running
launchctl list | grep nemoguard

# Stop it
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.nemoguard.cloudflared.plist

# Start it again (also happens automatically on login/reboot)
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nemoguard.cloudflared.plist
```

## 6. Optional: securing the endpoint further

If your teammate's Lambda can sign requests, set an environment variable
`WEBHOOK_SECRET_<SOURCE_SYSTEM_UPPERCASED>` (e.g.
`WEBHOOK_SECRET_AWS_LAMBDA`) on the NemoGuard API, then have the sender
compute `X-NemoGuard-Signature: sha256=<hmac>` over the raw request body
using that shared secret (see `src/api/webhook_security.py`). This is
opt-in — omitting it is fine for a POC/internal network.
