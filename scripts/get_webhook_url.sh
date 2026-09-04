#!/bin/bash
# Prints the NemoGuard webhook URL for external teammates.
#
# This is a PERMANENT, STATIC URL via ngrok's free static-domain feature
# (https://dashboard.ngrok.com/domains) -- it does NOT change across
# restarts, crashes, or reboots. This is genuinely different from a
# Cloudflare "quick tunnel" (which mints a brand-new random subdomain on
# every restart -- confirmed live during earlier testing this session).
#
# Run as a macOS LaunchAgent (~/Library/LaunchAgents/com.nemoguard.ngrok.plist,
# checked into scripts/launchd/ for version control) with KeepAlive=true
# (auto-restarts on crash, reconnecting to the SAME static domain --
# verified live with a real kill -9 test) and RunAtLoad=true (auto-starts
# on login/reboot).

STATIC_DOMAIN="patriot-unturned-litigate.ngrok-free.dev"
WEBHOOK_URL="https://${STATIC_DOMAIN}/api/v2/ingest/webhook"

echo "NemoGuard webhook endpoint (permanent -- safe to bookmark/share once):"
echo "  ${WEBHOOK_URL}"
echo
echo "Service status:"
launchctl list | grep nemoguard || echo "  WARNING: com.nemoguard.ngrok is not running. Start it with:"
if ! launchctl list | grep -q nemoguard.ngrok; then
    echo "    launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.nemoguard.ngrok.plist"
fi
echo
echo "Quick health check:"
curl -s -o /dev/null -w "  HTTP status: %{http_code}\n" -X POST "${WEBHOOK_URL}" \
    -H "Content-Type: application/json" -d '{"source_system":"health-check","message":"ping"}'
