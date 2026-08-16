#!/usr/bin/env python3
"""
Scenario Matrix Runner — end-to-end test suite for NemoGuard's agentic
incident-response pipeline.

Unlike a unit test, this deliberately DOES exercise the real NVIDIA LLM API
(real Nemotron calls, real latency, real cost) — because the thing we most
need confidence in before a release is "does the whole multi-agent chain
(Watcher -> Correlator -> RCA -> Impact -> Runbook -> Grounding Critic)
actually produce a usable, non-degenerate recovery plan for every kind of
failure the simulator can produce, end to end, against the live model?"

None of this touches a real production system: every "incident" originates
from the Scenario Lab simulator (`simulator_backend/main.py`), which
generates synthetic logs/webhooks that mimic Datadog/PagerDuty/Airflow —
the exact same code path the demo UI uses when you click "Trigger Scenario".

USAGE
-----
    cd pipeline-copilot
    python3 scripts/scenario_matrix.py                        # run full matrix, exit non-zero on any failure
    python3 scripts/scenario_matrix.py --scenario OOM_CRASH    # run a single scenario
    python3 scripts/scenario_matrix.py --repeat 3               # run each scenario N times (checks consistency)
    python3 scripts/scenario_matrix.py --no-reset               # don't wipe incidents before running
    python3 scripts/scenario_matrix.py --json report.json       # also write a machine-readable report

WHAT IT CHECKS
--------------
For every triggered incident we poll until the workflow reaches a terminal
triage state (PLAN_READY / NEEDS_REVIEW) or times out, then assert:

  - The incident actually reached a plan-ready state (didn't hang forever,
    didn't silently stay in DETECTED/INVESTIGATING).
  - At least one hypothesis was recorded, with confidence in [0, 1].
  - At least one action plan exists, with overall_risk in a known set.
  - The plan's rationale is non-empty and not just whitespace (this is
    exactly the bug we found and fixed earlier — a critic failure used to
    silently produce a blank rationale).
  - The plan has at least one step (same bug class — empty `steps: []`).
  - Every step has a non-empty action_type and a risk_level in a known set.
  - No unhandled exception was raised anywhere in the run (network errors,
    timeouts, and DB errors during polling are all caught and reported as
    a scenario failure rather than crashing the whole matrix).

This is intentionally NOT asserting exact plan content (LLM output is
non-deterministic) — it's asserting the *shape and health* of the output,
which is what actually causes silent product-quality regressions like the
empty-plan bug.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

API_BASE = "http://localhost:8000"
SIM_BASE = "http://localhost:8001"

# Every scenario_type the simulator explicitly branches on, plus one
# deliberately-unhandled type to exercise the generic/fallback path
# (see the `else:` branch in simulator_backend/main.py::simulate_failure).
SCENARIOS = [
    "SCHEMA_REGRESSION",
    "OOM_CRASH",
    "CASCADING_FAILURE",
    "UNKNOWN_SCENARIO_TYPE",  # exercises the generic fallback path
]

TERMINAL_STATES = {"PLAN_READY", "NEEDS_REVIEW"}
FAILURE_TERMINAL_STATES = {"RESOLVED"}  # shouldn't happen from a fresh trigger, but don't hang if it does
KNOWN_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH"}

# NOTE: RCA now runs strictly before Impact/Runbook (see langgraph_investigator.py —
# this was a deliberate fix so Impact/Runbook are grounded in the real root cause
# instead of guessing blind), so the full chain is no longer fully parallelized and
# can legitimately take longer than 180s under real NVIDIA API latency + a 5-node
# multi-agent LangGraph pass. 240s gives enough headroom without masking genuine hangs.
POLL_INTERVAL_SEC = 3
POLL_TIMEOUT_SEC = 240


@dataclass
class ScenarioResult:
    scenario: str
    run_index: int
    incident_id: Optional[str] = None
    passed: bool = False
    duration_sec: float = 0.0
    checks: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    final_status: Optional[str] = None
    plan_summary: Optional[dict] = None


def _check(result: ScenarioResult, name: str, ok: bool, detail: str = ""):
    result.checks[name] = ok
    if not ok:
        result.errors.append(f"{name} FAILED" + (f": {detail}" if detail else ""))


def reset_environment(client: httpx.Client):
    print("Resetting simulator state (incidents + alerts)...")
    r = client.post(f"{SIM_BASE}/reset", timeout=30)
    r.raise_for_status()


def trigger_scenario(client: httpx.Client, scenario_type: str) -> None:
    r = client.post(f"{SIM_BASE}/trigger", json={"scenario_type": scenario_type}, timeout=30)
    r.raise_for_status()


def wait_for_new_incident(client: httpx.Client, known_ids: set, timeout: float = 60) -> Optional[str]:
    """Poll the open-incidents list until a new incident_id shows up."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"{API_BASE}/api/v2/incidents", params={"state": "open"}, timeout=10)
        r.raise_for_status()
        data = r.json()
        ids = {i["incident_id"] for i in data}
        new_ids = ids - known_ids
        if new_ids:
            candidates = [i for i in data if i["incident_id"] in new_ids]
            candidates.sort(key=lambda i: i.get("detected_at", ""), reverse=True)
            return candidates[0]["incident_id"] if candidates else None
        time.sleep(1.5)
    return None


def poll_incident_until_terminal(client: httpx.Client, incident_id: str, timeout: float = POLL_TIMEOUT_SEC) -> str:
    deadline = time.time() + timeout
    last_status = "UNKNOWN"
    while time.time() < deadline:
        r = client.get(f"{API_BASE}/api/v2/incidents/{incident_id}", timeout=10)
        r.raise_for_status()
        last_status = r.json().get("status", "UNKNOWN")
        if last_status in TERMINAL_STATES or last_status in FAILURE_TERMINAL_STATES:
            return last_status
        time.sleep(POLL_INTERVAL_SEC)
    return last_status  # timed out — caller will fail the "reached terminal state" check


def run_one(client: httpx.Client, scenario: str, run_index: int) -> ScenarioResult:
    result = ScenarioResult(scenario=scenario, run_index=run_index)
    start = time.time()
    try:
        # Snapshot existing open incident ids so we can identify the new one
        r = client.get(f"{API_BASE}/api/v2/incidents", params={"state": "open"}, timeout=10)
        r.raise_for_status()
        known_ids = {i["incident_id"] for i in r.json()}

        trigger_scenario(client, scenario)

        # The simulator sends 1-5 webhooks sequentially (with a 1s delay between each —
        # see simulator_backend/main.py::simulate_failure), and each webhook triggers a
        # synchronous Watcher Agent LLM call before an incident is created/correlated.
        # 30s was too tight for multi-webhook scenarios like CASCADING_FAILURE/SCHEMA_REGRESSION
        # and caused a real test-harness bug: the timeout would fire, the runner would move on
        # to the *next* scenario, and then wrongly attribute the previous scenario's
        # late-arriving incident to the new one. 60s gives enough headroom.
        incident_id = wait_for_new_incident(client, known_ids, timeout=60)
        _check(result, "incident_created", incident_id is not None, "no new incident appeared within 60s")
        if not incident_id:
            return result
        result.incident_id = incident_id

        final_status = poll_incident_until_terminal(client, incident_id)
        result.final_status = final_status
        _check(
            result,
            "reached_terminal_state",
            final_status in TERMINAL_STATES,
            f"got status={final_status!r}, expected one of {TERMINAL_STATES}",
        )

        # Hypotheses
        r = client.get(f"{API_BASE}/api/v2/incidents/{incident_id}/hypotheses", timeout=10)
        r.raise_for_status()
        hyps = r.json()
        _check(result, "has_hypothesis", len(hyps) > 0, "no hypotheses recorded")
        if hyps:
            conf = hyps[0].get("confidence", None)
            _check(
                result,
                "hypothesis_confidence_in_range",
                isinstance(conf, (int, float)) and 0.0 <= conf <= 1.0,
                f"confidence={conf!r}",
            )

        # Plans
        r = client.get(f"{API_BASE}/api/v2/incidents/{incident_id}/plans", timeout=10)
        r.raise_for_status()
        plans = r.json()
        _check(result, "has_plan", len(plans) > 0, "no action plan recorded")

        if plans:
            plan = plans[0]
            rationale = (plan.get("rationale") or "").strip()
            steps = plan.get("steps") or []
            risk = plan.get("overall_risk")

            _check(result, "plan_rationale_nonempty", len(rationale) > 0, "rationale is blank")
            _check(result, "plan_has_steps", len(steps) > 0, "steps list is empty")
            _check(
                result,
                "plan_risk_known",
                risk in KNOWN_RISK_LEVELS,
                f"overall_risk={risk!r}, expected one of {KNOWN_RISK_LEVELS}",
            )

            steps_ok = True
            for s in steps:
                if not (s.get("action_type") or "").strip():
                    steps_ok = False
                if s.get("risk_level") not in KNOWN_RISK_LEVELS:
                    steps_ok = False
            _check(result, "plan_steps_well_formed", steps_ok, "one or more steps missing action_type or valid risk_level")

            result.plan_summary = {
                "action_plan_id": plan.get("action_plan_id"),
                "status": plan.get("status"),
                "overall_risk": risk,
                "num_steps": len(steps),
                "rationale_preview": rationale[:140],
            }

        result.passed = all(result.checks.values()) and len(result.errors) == 0

    except Exception as e:  # noqa: BLE001 - catch everything, report as scenario failure, keep the matrix running
        result.errors.append(f"unhandled exception: {e}")
        result.errors.append(traceback.format_exc())
        result.passed = False
    finally:
        result.duration_sec = round(time.time() - start, 1)

    return result


def print_result(result: ScenarioResult):
    icon = "PASS" if result.passed else "FAIL"
    print(f"\n[{icon}] {result.scenario} (run {result.run_index}) — {result.duration_sec}s — incident={result.incident_id}")
    print(f"    final_status: {result.final_status}")
    if result.plan_summary:
        p = result.plan_summary
        print(f"    plan: {p['num_steps']} steps, risk={p['overall_risk']}, status={p['status']}")
        print(f"    rationale: {p['rationale_preview']!r}")
    for check_name, ok in result.checks.items():
        mark = "  ok " if ok else " FAIL"
        print(f"    [{mark}] {check_name}")
    if result.errors and not result.passed:
        print("    errors:")
        for err in result.errors:
            if "\n" in err:  # traceback — indent it
                for line in err.splitlines():
                    print(f"        {line}")
            else:
                print(f"      - {err}")


def print_summary(results: list):
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print("\n" + "=" * 70)
    print(f"SCENARIO MATRIX SUMMARY: {passed}/{total} passed, {failed} failed")
    print("=" * 70)

    by_scenario: dict = {}
    for r in results:
        by_scenario.setdefault(r.scenario, []).append(r)

    for scenario, runs in by_scenario.items():
        ok = sum(1 for r in runs if r.passed)
        status = "PASS" if ok == len(runs) else "FAIL"
        print(f"  [{status}] {scenario}: {ok}/{len(runs)} runs passed")

    if failed:
        print("\nFailed runs:")
        for r in results:
            if not r.passed:
                print(f"  - {r.scenario} run {r.run_index} (incident={r.incident_id}): {r.errors[:1]}")


def results_to_json(results: list) -> dict:
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "runs": [
            {
                "scenario": r.scenario,
                "run_index": r.run_index,
                "incident_id": r.incident_id,
                "passed": r.passed,
                "duration_sec": r.duration_sec,
                "final_status": r.final_status,
                "checks": r.checks,
                "errors": r.errors,
                "plan_summary": r.plan_summary,
            }
            for r in results
        ],
    }


def main():
    global API_BASE, SIM_BASE

    default_api_base = API_BASE
    default_sim_base = SIM_BASE

    parser = argparse.ArgumentParser(description="Run the NemoGuard scenario matrix against the live stack.")
    parser.add_argument("--scenario", help="Run only this scenario_type (default: run the full matrix).")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat each scenario N times (default: 1).")
    parser.add_argument("--no-reset", action="store_true", help="Don't wipe incidents/alerts before running.")
    parser.add_argument("--json", dest="json_path", help="Write a machine-readable JSON report to this path.")
    parser.add_argument("--api-base", default=default_api_base, help=f"Override API base URL (default: {default_api_base}).")
    parser.add_argument("--sim-base", default=default_sim_base, help=f"Override simulator base URL (default: {default_sim_base}).")
    args = parser.parse_args()

    API_BASE = args.api_base
    SIM_BASE = args.sim_base

    scenarios = [args.scenario] if args.scenario else SCENARIOS

    print(f"Scenario matrix: {scenarios} x {args.repeat} run(s) each")
    print(f"API: {API_BASE}   Simulator: {SIM_BASE}")

    results = []
    with httpx.Client() as client:
        # Sanity check both services are up before burning any LLM calls.
        try:
            client.get(f"{API_BASE}/api/v2/incidents", params={"state": "open"}, timeout=10).raise_for_status()
            client.get(f"{SIM_BASE}/docs", timeout=10)
        except Exception as e:
            print(f"FATAL: could not reach API/simulator before starting ({e}). Is the stack running?")
            sys.exit(2)

        if not args.no_reset:
            reset_environment(client)
            time.sleep(2)

        for scenario in scenarios:
            for run_index in range(1, args.repeat + 1):
                result = run_one(client, scenario, run_index)
                print_result(result)
                results.append(result)

    print_summary(results)

    if args.json_path:
        with open(args.json_path, "w") as f:
            json.dump(results_to_json(results), f, indent=2)
        print(f"\nWrote JSON report to {args.json_path}")

    any_failed = any(not r.passed for r in results)
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
