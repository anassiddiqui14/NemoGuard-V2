"""
Manual verification script for WP-005 (Complete Authentication &
Authorization) -- exercises the role-gated endpoints against the live
running stack to confirm require_role/require_any_role behave as
specified in docs build plan §11.2.

Run with: python3 scripts/test_wp005_roles.py
"""
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"


def get_token(role: str) -> str:
    with urllib.request.urlopen(f"{BASE}/api/v2/auth/mock-login?role={role}") as resp:
        return json.loads(resp.read())["access_token"]


def call(method: str, path: str, token: str = None, body: dict = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def check(desc, expected_code, actual_code):
    status = "PASS" if actual_code == expected_code else "FAIL"
    print(f"[{status}] {desc}: expected {expected_code}, got {actual_code}")


viewer_token = get_token("viewer")
operator_token = get_token("operator")
commander_token = get_token("commander")
approver_token = get_token("approver")
admin_token = get_token("admin")

# viewer should NOT be able to trigger triage (requires operator+)
code, _ = call("POST", "/api/v2/incidents/INC-NOPE/triage", viewer_token)
check("viewer cannot trigger triage", 403, code)

# operator SHOULD be able to attempt triage (may 404 on missing incident, not 403)
code, _ = call("POST", "/api/v2/incidents/INC-NOPE/triage", operator_token)
check("operator can attempt triage (not 403)", 404, code)

# commander SHOULD also be able to (commander includes operator per hierarchy)
code, _ = call("POST", "/api/v2/incidents/INC-NOPE/triage", commander_token)
check("commander can attempt triage (not 403)", 404, code)

# viewer should NOT be able to approve
code, _ = call("POST", "/api/v2/incidents/INC-NOPE/plans/PLN-NOPE/approve", viewer_token, {"decision": "approve", "plan_hash": "x"})
check("viewer cannot approve", 403, code)

# commander should NOT be able to approve (approver is a separate role per spec)
code, _ = call("POST", "/api/v2/incidents/INC-NOPE/plans/PLN-NOPE/approve", commander_token, {"decision": "approve", "plan_hash": "x"})
check("commander cannot approve (approver-only)", 403, code)

# approver SHOULD be able to attempt approve (may 404 on missing plan, not 403)
code, _ = call("POST", "/api/v2/incidents/INC-NOPE/plans/PLN-NOPE/approve", approver_token, {"decision": "approve", "plan_hash": "x"})
check("approver can attempt approve (not 403)", 404, code)

# admin SHOULD be able to do everything (superset)
code, _ = call("POST", "/api/v2/incidents/INC-NOPE/plans/PLN-NOPE/approve", admin_token, {"decision": "approve", "plan_hash": "x"})
check("admin can attempt approve (not 403)", 404, code)

code, _ = call("GET", "/api/v2/admin/capabilities", viewer_token)
check("viewer cannot read admin capabilities", 403, code)

code, _ = call("GET", "/api/v2/admin/capabilities", admin_token)
check("admin can read admin capabilities", 200, code)

# All previously-open context endpoints should now require auth
for path in ["/api/v2/context/cmdb", "/api/v2/context/runbooks"]:
    code, _ = call("GET", path, None)
    check(f"unauthenticated cannot read {path}", 401, code)
    code, _ = call("GET", path, viewer_token)
    check(f"viewer can read {path}", 200, code)

print("\nDone.")
