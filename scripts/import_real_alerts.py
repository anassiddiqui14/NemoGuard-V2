#!/usr/bin/env python3
"""
Import Real Datadog Alerts — masks sensitive org data from a folder of
Outlook .msg alert exports (Wyndham/WHG production Datadog alerts), then
replays each one through NemoGuard's real webhook ingestion endpoint
(/api/v2/ingest/webhook) so we can see how the Watcher/Correlator/RCA/
Impact/Runbook/Grounding-Critic pipeline performs on genuine production
alert language instead of synthetic simulator data.

PRIVACY
-------
The org's real identity (company name, internal team emails, tracking
URLs/monitor tokens) must never reach the NVIDIA Nemotron API. This script
masks all of that BEFORE writing anything to disk or sending it to the
webhook endpoint:
  - Company/brand name (Wyndham, WHG, etc.) -> generic placeholder
  - Email addresses -> [EMAIL]
  - Datadog/AWS Console tracking URLs (monitor IDs, snapshot tokens,
    urldefense-wrapped links) -> [URL]
  - IPs, AWS account IDs, UUIDs, long opaque tokens -> [IP]/[AWS_ACCOUNT]/[UUID]/[TOKEN]

Internal *service names* (e.g. api gateway names, job names) are
intentionally preserved (not masked) because they're exactly the kind of
topology/service-identifier information the RCA/Impact agents need to
reason about — masking those would defeat the point of testing against
real alert language. Only the org identity + literal PII/tracking tokens
are scrubbed.

USAGE
-----
    cd pipeline-copilot
    # 1) Dry run: parse + mask + write masked JSON files, but don't send anything
    python3 scripts/import_real_alerts.py --source "/tmp/datadog_alerts_raw/Datadog alerts" --dry-run

    # 2) Review the masked output for anything the regexes missed:
    cat data/imported_alerts/*.json

    # 3) Actually replay them through the live webhook endpoint
    python3 scripts/import_real_alerts.py --source "/tmp/datadog_alerts_raw/Datadog alerts" --send

    # 4) Throttle to avoid hammering the Watcher Agent's LLM calls
    python3 scripts/import_real_alerts.py --source "..." --send --delay 3 --limit 10
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

try:
    import extract_msg
except ImportError:
    print("Missing dependency: pip install extract-msg", file=sys.stderr)
    sys.exit(1)

import httpx

# ---------------------------------------------------------------------------
# MASKING
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
URL_RE = re.compile(r"https?://[^\s\"'<>)]+")
UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
AWS_ARN_RE = re.compile(r"arn:aws:[a-zA-Z0-9\-:/._]+")
AWS_ACCOUNT_RE = re.compile(r"\b\d{12}\b")
LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{24,}\b")  # long API keys / monitor snapshot tokens
PHONE_RE = re.compile(r"\b\+?\d[\d\-\s()]{8,}\d\b")

# Real org/brand identifiers found in these exports -> generic placeholder.
# Matched case-insensitively as whole words so we don't accidentally eat
# substrings inside unrelated service names.
ORG_NAME_REPLACEMENTS: dict[str, str] = {
    r"\bwyndham\b": "AcmeCorp",
    r"\bWHGDigitalTeam\b": "digital-oncall-team",
    # "whg" also shows up embedded (lowercase, no word boundary) inside real
    # API path segments like /whgservices/loyalty/... — match it wherever it
    # appears (not just as a standalone word) so those don't leak either.
    r"whg": "acme",
}


def mask_text(text: str) -> str:
    if not text:
        return text
    masked = text
    # URLs first (they're the biggest source of tracking tokens/monitor IDs)
    masked = URL_RE.sub("[URL]", masked)
    masked = EMAIL_RE.sub("[EMAIL]", masked)
    masked = AWS_ARN_RE.sub("[AWS_ARN]", masked)
    masked = UUID_RE.sub("[UUID]", masked)
    masked = IPV4_RE.sub("[IP]", masked)
    masked = AWS_ACCOUNT_RE.sub("[AWS_ACCOUNT]", masked)
    masked = PHONE_RE.sub("[PHONE]", masked)
    for pattern, placeholder in ORG_NAME_REPLACEMENTS.items():
        masked = re.sub(pattern, placeholder, masked, flags=re.IGNORECASE)
    return masked


# ---------------------------------------------------------------------------
# .msg PARSING
# ---------------------------------------------------------------------------

def parse_msg_file(path: Path) -> dict:
    """Extract subject/body/date from an Outlook .msg file, already masked."""
    msg = extract_msg.Message(str(path))
    try:
        subject = mask_text(msg.subject or "")
        body = mask_text(msg.body or "")
        sender = mask_text(str(msg.sender or ""))
        date = str(msg.date) if msg.date else None
    finally:
        msg.close()

    return {
        "source_file": mask_text(path.name),
        "subject": subject,
        "sender": sender,
        "date": date,
        "body": body,
    }


def classify_alert_state(filename_masked: str) -> str:
    lower = filename_masked.lower()
    if lower.startswith("triggered") or lower.startswith("re-triggered"):
        return "TRIGGERED"
    if lower.startswith("recovered"):
        return "RECOVERED"
    if lower.startswith("warn"):
        return "WARN"
    return "UNKNOWN"


def to_webhook_payload(parsed: dict, run_id: str) -> dict:
    state = classify_alert_state(parsed["source_file"])
    return {
        "source": "Datadog",
        "type": "Monitor Alert",
        "monitor_name": parsed["subject"],
        "message": parsed["body"][:4000],
        "alert_state": state,
        "tags": ["source:real_export", f"alert_state:{state.lower()}"],
        "run_id": run_id,
        "original_date": parsed["date"],
    }


def main():
    parser = argparse.ArgumentParser(description="Mask and (optionally) replay real Datadog .msg alert exports through NemoGuard.")
    parser.add_argument("--source", required=True, help="Path to the folder containing extracted .msg files.")
    parser.add_argument("--out-dir", default="data/imported_alerts", help="Where to write masked JSON payloads (gitignored).")
    parser.add_argument("--send", action="store_true", help="Actually POST each masked payload to the webhook endpoint.")
    parser.add_argument("--dry-run", action="store_true", help="Parse + mask + write JSON only, don't send anything.")
    parser.add_argument("--api-base", default="http://localhost:8000", help="NemoGuard API base URL.")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds to sleep between webhook sends (default 2s).")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N files.")
    parser.add_argument("--filter", default=None, help="Only process files whose masked filename contains this substring (case-insensitive).")
    args = parser.parse_args()

    source_dir = Path(args.source)
    if not source_dir.is_dir():
        print(f"FATAL: source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    msg_files = sorted(source_dir.glob("*.msg"))
    if args.limit:
        msg_files = msg_files[: args.limit]

    print(f"Found {len(msg_files)} .msg files in {source_dir}")

    run_id_base = f"REAL-IMPORT-{int(time.time())}"
    written = []

    for idx, path in enumerate(msg_files):
        parsed = parse_msg_file(path)
        if args.filter and args.filter.lower() not in parsed["source_file"].lower():
            continue

        run_id = f"{run_id_base}-{idx:03d}"
        payload = to_webhook_payload(parsed, run_id)

        out_path = out_dir / f"{run_id}.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        written.append(out_path)
        print(f"  [{idx:03d}] {payload['alert_state']:10s} {payload['monitor_name'][:90]}")

    print(f"\nWrote {len(written)} masked JSON payloads to {out_dir}/")

    if not args.send:
        print("Dry run complete (pass --send to actually POST these to the webhook endpoint).")
        return

    print(f"\nSending {len(written)} payloads to {args.api_base}/api/v2/ingest/webhook (delay={args.delay}s)...")
    sent = 0
    failed = 0
    with httpx.Client() as client:
        for out_path in written:
            with open(out_path) as f:
                payload = json.load(f)
            try:
                r = client.post(f"{args.api_base}/api/v2/ingest/webhook", json=payload, timeout=60)
                status = "OK" if r.status_code < 400 else f"HTTP {r.status_code}"
                print(f"  -> {out_path.name}: {status}")
                if r.status_code < 400:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"  -> {out_path.name}: FAILED ({e})")
                failed += 1
            time.sleep(args.delay)

    print(f"\nDone. Sent={sent} Failed={failed}")


if __name__ == "__main__":
    main()
