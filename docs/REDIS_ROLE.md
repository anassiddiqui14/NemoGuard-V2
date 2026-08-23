# Redis Audit (2026-08-23)

## Finding

A `nemoguard-redis` container (`redis:7-alpine`) was found running in this
environment, but it is **not used anywhere in the NemoGuard application**.

## Evidence

1. `grep -rni "redis"` across `src/`, `frontend/src/`, `docker-compose.yml`,
   `localstack_lab/`, `simulator_backend/`, and `scripts/` returns **zero
   matches**. Redis is not referenced by rate limiting, sessions, caching,
   SSE/event buffering, or any other subsystem.
2. The current `docker-compose.yml` on disk (as of this commit) contains
   **no `redis` service definition at all**.
3. `docker compose ps -a` nonetheless still listed a `redis` service as part
   of this Compose project, and `docker inspect` confirmed the container's
   own Compose labels pointed at this exact `docker-compose.yml` path —
   i.e., it was a genuine **orphaned container** left running from an
   earlier version of the compose file that has since dropped the service,
   not a container from an unrelated project.

## Action taken

The orphaned `nemoguard-redis` container was stopped and removed
(`docker stop && docker rm`). The API and frontend were verified healthy
immediately afterward (`/api/v2/status` returned `"healthy"` for both the
orchestrator and database; the frontend returned HTTP 200), confirming
Redis was not a runtime dependency.

## Recommendation

No code or compose changes are needed — the file already has no `redis`
service. If Redis becomes desired in the future (e.g., as a rate-limiter
backend or session cache), it should be reintroduced deliberately with:
- an explicit `docker-compose.yml` service definition,
- documented purpose and data model,
- TTL/persistence strategy,
- and — since it would sit behind the API — network/security
  configuration appropriate for a production deployment.
