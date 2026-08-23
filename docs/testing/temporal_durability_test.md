# Temporal Approval Durability Test

**Test date:** 2026-08-21  
**Work package:** WP-008  
**Result:** PASS — isolated-worker and deployed-Compose-worker restart evidence validated

## Scope and remaining restart exercise

This harness proves that the production workflow and API approval path work
correctly through a genuine worker interruption while the workflow is blocked
at its approval gate: the first isolated Temporal worker stops, a replacement
worker starts on the same task queue, the API signal is delivered, one governed
action executes, one independent verification passes, and the terminal
database state is coherent.

The initial harness uses an isolated, in-process Temporal worker/task queue.
It proves workflow recovery across a real worker restart. The guarded Compose
harness (`scripts/run_compose_temporal_durability_test.py`) subsequently
completed the equivalent operational topology exercise against the deployed
`nemoguard-temporal-worker` container: it stopped the container only after the
fixture reached persisted `AWAITING_APPROVAL`, recreated it in the same
opt-in staging configuration, submitted one production-API approval, and
verified one action execution, one verification record, and a coherent
terminal audit trail.

The existing unit workflow suite deterministically covers approval,
cancellation, rejection, approval timeout, and cancellation-priority behavior.

## Objective

Verify that a post-restart Temporal worker correctly handles an approval signal
from the production API when the client sends the UI-style uppercase decision
`APPROVED`, then executes exactly one controlled **read-only** plan step and
persists terminal lifecycle and verification evidence.

This test specifically validates the fix in
`src/domain/workflows/incident_workflow.py`: `workflow.wait_condition(...)`
returns `None` after its predicate becomes true and raises
`asyncio.TimeoutError` on timeout. Treating its return value as a boolean
caused every received approval/cancel signal to be misclassified as a timeout.

## Environment

All Docker Compose services were healthy before the test:

- `nemoguard-api`
- `nemoguard-postgres`
- `nemoguard-temporal`
- `nemoguard-temporal-worker` (rebuilt/restarted with the corrected workflow)
- `nemoguard-frontend`
- `nemoguard-simulator`

The harness itself now performs the isolated-worker interruption while the
workflow is persistently `AWAITING_APPROVAL`, then starts a replacement worker
on the same queue before the API approval signal is submitted. The deployed
Compose worker was healthy but was not the worker intentionally interrupted by
this controlled test.

Temporal namespace: `default`

## Controlled Fixture

| Field | Value |
|---|---|
| Incident | `INC-DURABILITY-FIX-20260821121741` |
| Plan | `PLN-DURABILITY-FIX-20260821121741` |
| Step | `STP-DURABILITY-FIX-20260821121741` |
| Tool | `check_table_staleness` |
| Capability | `data.check_table_staleness` |
| Risk | `LOW` |
| Requires approval | `false` |
| Input | `{"table_name":"order_events","run_id":"RUN-DURABILITY-FIX-20260821121741"}` |

Before the test, the fixture contained exactly this one `PENDING` action step
and had zero execution records. No mutating capability was included.

## Test Method

The normal lifecycle workflow begins with LLM-backed triage, which generates a
new plan. Running it unmodified would invalidate a controlled one-step
execution assertion. The purpose-built harness
`scripts/run_temporal_durability_test.py` therefore:

1. Creates a uniquely named, FK-consistent fixture with exactly one
   `PENDING`, `LOW`-risk, read-only `check_table_staleness` action and zero
   execution records.
2. Uses the real `IncidentStateService` to transition the fixture from
   `INVESTIGATING` to `PLAN_READY` as controlled setup.
3. Starts the production `IncidentLifecycleWorkflow` against the real Temporal
   server on a fresh isolated task queue.
4. Replaces only `triage_incident_activity` with a deterministic activity that
   preserves the pre-created controlled plan.
5. Uses the real lifecycle transition activity and real execution activity.
6. Waits for the persisted `AWAITING_APPROVAL` state, then stops the only
   worker polling that task queue.
7. Starts a replacement worker on the same task queue and only then obtains
   an approver token from the running API and fetches the API-computed plan
   hash.
8. Calls the production endpoint:

   ```text
   POST /api/v2/incidents/<newly-created-incident-id>/plans/<newly-created-plan-id>/approve
   Authorization: Bearer <approver token>

   {"decision":"APPROVED","plan_hash":"<API-computed hash>"}
   ```

9. Requires the endpoint result to be `{"status":"signaled_temporal"}`.
10. Requires the workflow result to be
    `{"status":"completed","action":"executed"}`.
11. Validates terminal state using the governed capability path's authoritative
    persistence records.

Only triage is stubbed; the workflow, Temporal server, API approval boundary,
state-machine transitions, governed capability execution, verification, and
Postgres persistence are real.

## Results

### Lifecycle audit trail

The persisted event sequence was:

1. `INVESTIGATING -> PLAN_READY`
2. `PLAN_READY -> AWAITING_APPROVAL`
3. `APPROVAL_RECORDED`
4. `AWAITING_APPROVAL -> EXECUTING`
5. `ACTION_EXECUTED`:
   `Capability data.check_table_staleness executed with result=SUCCESS, verification=PASSED.`
6. `EXECUTING -> VERIFYING`
7. `VERIFYING -> RESOLVED`
8. `VERIFICATION_PASSED`
9. `INCIDENT_RESOLVED`

### Terminal database evidence

| Assertion | Observed value |
|---|---|
| Workflow result | `{"status":"completed","action":"executed"}` |
| API approval delivery | `signaled_temporal` |
| Incident status | `RESOLVED` |
| Plan status | `EXECUTED` |
| Controlled step status | `SUCCEEDED` |
| Controlled step tool | `check_table_staleness` |
| Controlled step risk | `LOW` |
| `ACTION_EXECUTED` audit events | exactly `1` |
| Passed `verification_result` records | exactly `1` |
| Mutating/unexpected steps | none |

The passed verification result was
`data.check_table_staleness verification` and reported no stale or partial
write condition for the controlled run.

## Persistence Note

The first harness iteration incorrectly asserted that the legacy `execution`
table would receive one row. The governed capability execution path instead
persists its authoritative outcome through:

- the action step (`SUCCEEDED`);
- an `ACTION_EXECUTED` audit event; and
- a passed `verification_result`.

The live workflow had already succeeded—incident `RESOLVED`, plan `EXECUTED`,
step `SUCCEEDED`—when that incorrect assertion failed. The harness was
corrected to assert the actual governed-execution persistence model. Its
non-mutating verification mode then passed with:

```json
{
  "action_execution_count": 1,
  "incident_status": "RESOLVED",
  "plan_status": "EXECUTED",
  "step": {
    "requires_approval": 0,
    "risk_level": "LOW",
    "status": "SUCCEEDED",
    "tool_name": "check_table_staleness"
  },
  "verification_count": 1
}
```

## Reproduction

From `pipeline-copilot`, while Docker Compose services are running:

```bash
POSTGRES_URL='postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db' \
.venv/bin/python scripts/run_temporal_durability_test.py
```

Every full run automatically creates a unique fixture and prints its incident
and plan IDs. A completed fixture is intentionally immutable for the purpose
of this test. To validate its persistence evidence without changing state,
provide those printed IDs:

```bash
DURABILITY_INCIDENT_ID='INC-DURABILITY-RESTART-20260821135402-E28F14AB' \
DURABILITY_PLAN_ID='PLN-DURABILITY-RESTART-20260821135402-E28F14AB' \
POSTGRES_URL='postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db' \
.venv/bin/python scripts/run_temporal_durability_test.py --verify-only
```

A new full run needs no fixture provisioning or source edits; the harness
creates another uniquely named one-step, read-only fixture automatically.

## Worker-interruption result

On 2026-08-21, the restart-capable harness created and exercised this fresh
fixture:

| Field | Value |
|---|---|
| Incident | `INC-DURABILITY-RESTART-20260821135402-E28F14AB` |
| Plan | `PLN-DURABILITY-RESTART-20260821135402-E28F14AB` |
| Step | `STP-DURABILITY-RESTART-20260821135402-E28F14AB` |

Worker A reached the persisted `AWAITING_APPROVAL` state and was shut down.
Worker B was then started on the same isolated task queue. The API returned
`{"status":"signaled_temporal"}` for the uppercase `APPROVED` request, and
the resumed workflow returned:

```json
{"status":"completed","action":"executed"}
```

A follow-up `--verify-only` read against Postgres confirmed:

```json
{
  "action_execution_count": 1,
  "incident_status": "RESOLVED",
  "persisted_execution_count": 1,
  "plan_status": "EXECUTED",
  "verification_count": 1
}
```

The focused workflow regression suite also passed:

```text
8 passed in 1.84s
```

## Deployed Compose worker-interruption result

On 2026-08-21, the guarded Compose harness completed the previously pending
container-level recovery exercise using an explicitly enabled, default-off
staging triage mode. The production Compose worker container was stopped only
after this controlled fixture reached `AWAITING_APPROVAL`:

| Field | Value |
|---|---|
| Incident | `INC-DURABILITY-RESTART-20260821152011-7A006D70` |
| Plan | `PLN-DURABILITY-RESTART-20260821152011-7A006D70` |
| Step | `STP-DURABILITY-RESTART-20260821152011-7A006D70` |
| Interrupted container | `nemoguard-temporal-worker` |

The replacement container became running on the same Temporal task queue.
After one uppercase `APPROVED` decision through the production API, the
workflow returned `{"status":"completed","action":"executed"}` and the API
returned `{"status":"signaled_temporal"}`.

| Assertion | Observed value |
|---|---|
| Worker stop point | `AWAITING_APPROVAL` |
| Replacement worker | running |
| Incident status | `RESOLVED` |
| Plan status | `EXECUTED` |
| Controlled step status | `SUCCEEDED` |
| Action execution count | exactly `1` |
| Persisted execution count | exactly `1` |
| Passed verification count | exactly `1` |

The harness restores the deployed worker to its normal Compose configuration
afterward. The final worker environment was verified as
`NEMOGUARD_PRECREATED_PLAN_TRIAGE=0`; the staging behavior remains disabled by
default.
