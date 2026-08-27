"""Teams Incident Communications (WP-ORG-002 §4.19-4.27).

Architecture (per spec):
    Incident / Workflow / Agent -> audit_event -> IncidentUpdateProjector
    (src/domain/commander/status_projector.py) -> NotificationPolicy ->
    NotificationDispatcher -> Teams Adapter.

A Teams delivery failure must never block alert ingestion, investigation,
approval, execution, or verification -- every call into this package from
elsewhere in the codebase is wrapped in try/except at the call site and
this package itself never raises out of dispatch().
"""
