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

Live right now (temporary quick-tunnel, see §5 for a persistent one):
```
https://format-precious-feeds-content.trycloudflare.com/api/v2/ingest/webhook
```

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

## 5. Making the endpoint persistent (important)

The URL above is a **Cloudflare "quick tunnel"** (`cloudflared tunnel --url
http://localhost:80`) — free, no account needed, but:
- the URL changes every time it's restarted
- no uptime guarantee (per Cloudflare's own terms for anonymous quick tunnels)

For your teammate's actual integration, pick one:

**Option A — Cloudflare named tunnel (recommended, still free)**
```bash
cloudflared tunnel login
cloudflared tunnel create nemoguard
cloudflared tunnel route dns nemoguard nemoguard.yourdomain.com
cloudflared tunnel run --url http://localhost:80 nemoguard
```
Gives a stable URL you control, survives restarts if run as a service.

**Option B — Deploy NemoGuard's `api` container with a public IP/DNS**
(e.g. on the same AWS account the Lambda lives in) and point the Lambda
directly at `http://<host>:8000/api/v2/ingest/webhook` — no tunnel needed
at all, lowest latency, most production-appropriate if you're already on
AWS.

**Option C — Keep using a quick tunnel for now**, just re-share the new
URL with your teammate each time it's restarted (fine for a short-term
demo/POC, not for anything left running unattended).

## 6. Optional: securing the endpoint further

If your teammate's Lambda can sign requests, set an environment variable
`WEBHOOK_SECRET_<SOURCE_SYSTEM_UPPERCASED>` (e.g.
`WEBHOOK_SECRET_AWS_LAMBDA`) on the NemoGuard API, then have the sender
compute `X-NemoGuard-Signature: sha256=<hmac>` over the raw request body
using that shared secret (see `src/api/webhook_security.py`). This is
opt-in — omitting it is fine for a POC/internal network.
