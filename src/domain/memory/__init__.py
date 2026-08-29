"""Incident Memory (WP-ORG-003).

A governed memory layer -- NOT a model-training mechanism. Draft memory
records are generated deterministically from real, already-persisted
incident data when an incident resolves. A human must explicitly move a
record to APPROVED before it is ever surfaced to a future investigation.
Historical recovery retrieved from memory is presented as evidence only;
it never bypasses current preconditions, policy, approval, or verification.
"""
