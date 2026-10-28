# NemoGuard "Watcher Agent" — Agent Specification & Configuration
_Prepared for product team reference to recreate this agent on the Axet platform._

---

## 1. Agent Identity

| Field | Value |
|---|---|
| Agent Name | `Watcher_Agent` |
| Role / Persona | "First-Line Intelligence" — triage classifier & normalizer |
| Class | `WatcherAgent` (extends `BaseAgent`) |
| Source file | `src/domain/agents/watcher_agent.py` |
| Model (default, admin-configurable) | `nvidia/nemotron-3-super-120b-a12b` ("Super" tier — fast, lower reasoning) |
| Model resolution | Pulled **live** at agent construction time from an admin-editable settings service (`get_setting("model.super_tier")`) — no hardcoded model string, no restart needed to change it |
| Invocation pattern | Single-shot JSON completion (no tool calling, no multi-turn loop) |
| Temperature / top_p | `0.1` / `0.95` (kept low for strict JSON adherence) |
| Max tokens | `16384` |
| Output contract | Strict JSON only (parsed, with a tolerant sanitizer for malformed control characters) |

---

## 2. Purpose

The Watcher Agent is the **first-line intelligence** layer of the incident pipeline. It sits directly in the webhook ingestion path and is the very first thing that looks at a raw, arbitrarily-shaped alert payload (from Datadog, PagerDuty, email forwarders, custom webhooks, etc.).

Its two jobs:
1. **Signal vs. noise classification** — decide whether an incoming payload represents a genuine actionable anomaly or should be discarded as noise.
2. **Normalization** — if valid, convert the arbitrary payload into NemoGuard's canonical alert schema so every downstream system (correlator, RCA agent, dashboards) can rely on a consistent shape regardless of source system quirks.

It also performs a **soft, advisory correlation guess** (which existing active incident this alert might belong to) and detects **recovery/resolution signals** (e.g. a Datadog "Recovered:" notification), both of which downstream deterministic code treats as advisory input rather than ground truth (see §6).

---

## 3. System Prompt (verbatim)

```
You are the Watcher Agent (First-Line Intelligence).
Your job is to analyze incoming webhook payloads (from Datadog, PagerDuty, Emails, etc.) and determine if they represent a real anomaly or are just noise.
If it is a valid alert, normalize it into a standard schema.

Monitoring tools like Datadog also send "recovered"/"resolved"/"cleared" notifications
once a previously-firing alert returns to normal (e.g. subject starting with
"Recovered:", "OK:", "Resolved:", or explicit recovery language in the body).
These ARE valid, meaningful signals — you must still classify them as `is_valid: true`
and still attempt to correlate them to an existing active incident (same service/run_id/
monitor), but set `is_recovery_signal: true` so the system knows this alert reports
that the underlying issue has cleared rather than reporting a new/ongoing problem.

You MUST return ONLY valid JSON in this exact format:
{
  "is_valid": true,
  "confidence": 0.95,
  "is_recovery_signal": false,
  "reasoning": "Why you think this is or isn't a valid pipeline alert, whether it's a recovery/resolution notification, and why it correlates to an existing incident (if any).",
  "correlated_incident_id": "ID of an active incident if this alert belongs to it (based on run_id, service topology, or temporal proximity), else null",
  "normalized_alert": {
    "severity": "info|warning|high|critical",
    "alert_type": "Brief classification (e.g., SCHEMA_COLUMN_MISSING, DB_TIMEOUT)",
    "source_system": "The system that sent the alert (e.g., Datadog, Airflow, SendGrid)",
    "message": "A clean, human-readable summary of the alert",
    "run_id": "Extract run_id or job_id if present, otherwise null"
  }
}
If `is_valid` is false, `normalized_alert` can be null.
```

---

## 4. User/Task Prompt Template (per invocation)

Built dynamically for each call via `analyze(payload, active_incidents)`:

```
Analyze the following incoming webhook payload. If it matches any of the active incidents (by run_id, system proximity, or identical failure), set correlated_incident_id to that incident's ID.

ACTIVE INCIDENTS FOR CORRELATION:
<JSON array of {incident_id, title, summary, primary_run_id, status} for every currently open/active incident>

PAYLOAD:
<raw incoming webhook JSON payload, exactly as received>
```

- `active_incidents` is only included if non-empty.
- No conversation history / memory is passed in — each call is stateless and self-contained (all needed context is the payload + current active-incident list).

---

## 5. Inputs & Outputs

### Inputs
| Input | Description |
|---|---|
| `payload: Dict[str, Any]` | Raw webhook body as received, unmodified, in whatever shape the source system sent it. |
| `active_incidents: list` | List of currently **non-terminal** incidents (status not in RESOLVED/FAILED/CLOSED/CANCELLED), each with `incident_id`, `title`, `summary`, `primary_run_id`, `status`. Used only as correlation context, not training data. |

### Output (strict JSON schema)
```json
{
  "is_valid": true,
  "confidence": 0.95,
  "is_recovery_signal": false,
  "reasoning": "string",
  "correlated_incident_id": "string | null",
  "normalized_alert": {
    "severity": "info | warning | high | critical",
    "alert_type": "string (short classification code)",
    "source_system": "string",
    "message": "string",
    "run_id": "string | null"
  }
}
```
If `is_valid` is `false`, `normalized_alert` may be `null` and the payload is dropped as noise with no further processing.

---

## 6. Where It Sits in the Pipeline / Trigger

- **Trigger**: Invoked synchronously inside `IncidentOrchestrator._process_webhook_unlocked()` (`src/domain/orchestrator.py`), which runs for **every inbound webhook delivery** to the ingestion endpoint.
- **Concurrency control**: Webhook processing is serialized via a process-wide lock (`threading.Lock`) across the full "normalize → correlate → persist" transaction, to prevent duplicate incidents from near-simultaneous alert fan-out (e.g. multiple SNS/SQS deliveries for one failed run).
- **Downstream flow after the Watcher Agent returns**:
  1. If `is_valid == false` → request is dropped (`status: "ignored"`), nothing persisted.
  2. If `is_valid == true` → `normalized_alert` is inserted into the `alert` table.
  3. **Deterministic correlation engine (`CorrelatorEngine.best_match_for_alert`) runs FIRST** against real structured fields (run_id, alert_type, time proximity, CMDB topology adjacency) of alerts already attached to active incidents.
     - If the deterministic engine finds a strong match (score ≥ `min_cluster_score`, default `0.6`), **that wins** — the Watcher Agent's own `correlated_incident_id` guess is discarded.
     - Only if the deterministic engine finds **no** confident match does the system fall back to trusting the Watcher Agent's own `correlated_incident_id`/`confidence`/`reasoning` fields (still validated against the real active-incident list to prevent hallucinated IDs).
  4. If `is_recovery_signal == true` and the alert correlates to an existing incident → that incident is **auto-transitioned to RESOLVED** with an audit trail noting it was closed by an *external* recovery signal (not an executed NemoGuard remediation plan).
  5. If no correlation match and severity is `high`/`critical` → a **brand-new incident** is created and investigation (RCA/Impact/Runbook/Commander) is kicked off.
  6. If a genuinely new `run_id` correlates onto an incident that already has a plan → the system **re-triggers full re-investigation** (RCA → Impact → Runbook → Critic) rather than silently absorbing new evidence into a stale plan.

**Design principle to carry over**: *"Deterministic truth, probabilistic advice"* — the LLM's classification/normalization judgment is trusted, but any decision with real structured ground truth available (correlation matching) is double-checked/overridden by deterministic code. Only use the agent's judgment where an LLM genuinely adds value (classifying arbitrary unstructured payloads, free-text summarization) — not for decisions where hard data already exists.

---

## 7. Model & Infra Configuration

| Setting | Value / Mechanism |
|---|---|
| LLM provider | NVIDIA NIM (`https://integrate.api.nvidia.com/v1`), OpenAI-compatible API via `AsyncOpenAI` client |
| Auth | `NVIDIA_API_KEY` env var (no hardcoded fallback key) |
| Default model (admin-editable) | `nvidia/nemotron-3-super-120b-a12b` |
| Alternate tiers available (same codebase) | `model.ultra_tier` = `nvidia/nemotron-3-ultra-550b-a55b` (highest reasoning, slowest; `chat_template_kwargs.enable_thinking=true`, `reasoning_budget=16384`); `model.fallback_tier` = Super tier |
| Model-tier fallback behavior | Only applies to agents configured on the "ultra" tier: if a call doesn't complete within `model.fallback_timeout_seconds` (default 45s) OR errors outright, automatically retries on the fallback tier model. **Watcher Agent runs on the Super tier by default, so this fallback path is largely N/A for it** unless an admin reassigns it to Ultra. |
| Streaming | Yes — response streamed token-by-token and accumulated; no partial results surfaced to caller, only final parsed JSON. |
| Output parsing | Strips ```` ```json ```` / ```` ``` ```` fences if present, then a custom JSON sanitizer that escapes literal control characters (raw newlines/tabs) found **inside string values only** — because LLMs occasionally emit multi-line string fields with literal newlines instead of `\n` escapes, which breaks `json.loads`. |
| Timeout / retries | None at the Watcher-call-site level beyond the shared base-agent model-tier fallback mechanism described above (Watcher itself doesn't set a tool-call iteration cap since it makes no tool calls). |
| Error handling | On any exception or JSON parse failure, returns `{"error": "..."}` which the orchestrator surfaces as `{"status": "error", "message": ...}` and halts further processing of that webhook. |

---

## 8. Behavioral Notes / Edge Cases to Preserve

1. **Recovery signal detection**: Must recognize "Recovered:"/"OK:"/"Resolved:" style subjects or explicit recovery language in the body as **valid, meaningful signals** (not noise) — and still attempt correlation on them, flagging `is_recovery_signal: true` rather than treating them as a brand-new problem.
2. **Noise filtering**: Must be able to reject genuinely irrelevant payloads (`is_valid: false`) without hallucinating a `normalized_alert`.
3. **Schema discipline**: `alert_type` should be a short, consistent classification code (e.g. `SCHEMA_COLUMN_MISSING`, `DB_TIMEOUT`), not a free-form sentence — downstream RCA/correlation logic keys off this field.
4. **`run_id` extraction**: Should pull `run_id`/`job_id` from wherever it appears in the arbitrary payload shape (nested fields, free text) — set to `null` if genuinely absent, never fabricated.
5. **Correlation guess is advisory, not authoritative**: The agent's `correlated_incident_id` and `confidence` are only used as a fallback when deterministic correlation (same `run_id`, time proximity, matching `alert_type`, CMDB topological adjacency) finds no confident match. Any reimplementation should preserve this hierarchy — don't let the LLM's correlation decision override hard structured evidence.
6. **Idempotent / stateless design**: Each call only needs the current payload + a snapshot of active incidents — no persisted conversation state, no memory of prior calls required for the agent itself (memory/history concerns live in the orchestrator, not the agent).
7. **Strict JSON-only output**: No markdown, no prose outside the JSON object. The reference implementation defensively strips ` ```json ` fences and sanitizes literal control characters inside string values as a safety net — product team should decide whether Axet's output-parsing layer already handles this or whether equivalent sanitization is needed.

---

## 9. Suggested Axet Platform Mapping

| NemoGuard concept | Axet platform equivalent (to be filled in by product team) |
|---|---|
| System prompt (§3) | Agent "instructions" / persona definition |
| Per-call task prompt template (§4) | Agent "input template" with `{{payload}}` / `{{active_incidents}}` variables |
| Strict JSON output schema (§5) | Agent "structured output schema" / function-return schema |
| Trigger: inbound webhook (§6) | Axet "webhook trigger" node feeding this agent as the first step of a pipeline |
| Downstream deterministic correlation override (§6) | A conditional/branching step AFTER the agent node that re-validates the agent's `correlated_incident_id` against a deterministic rules node, only trusting the LLM guess if the deterministic step returns no match |
| Model tier / admin-editable model selection (§7) | Axet model-config binding (ideally editable without redeploying the agent) |
| Error handling or empty results (§7) | Axet's standard agent-failure handling (surface error, do not pass invalid state downstream) |

---

## 10. Summary for Product Team

This is a **lightweight, single-shot classification + normalization agent** — not a multi-step reasoning or tool-using agent. It's intentionally kept simple and fast (hence the "Super" model tier, not "Ultra") because it runs on the hot path of every single webhook delivery and must return quickly. The only two outputs that genuinely matter downstream are `is_valid` (gate) and `normalized_alert` (schema normalization) — everything else (`correlated_incident_id`, `confidence`, `reasoning`) is treated as *advisory* input to deterministic logic, not as ground truth. When rebuilding this on Axet, prioritize:
- Fast model tier / low latency.
- Strict, validated JSON output.
- A clear system prompt boundary: this agent classifies & normalizes; it does NOT make the final correlation decision, resolve incidents, or create incidents — those are owned by deterministic orchestration code that merely *consults* this agent's output.
</content>
