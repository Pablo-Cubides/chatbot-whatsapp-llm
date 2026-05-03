# ADR 0001 - Security hardening baseline

## Status
Accepted

## Context
The platform required stronger controls before production promotion:
- unauthenticated critical routes risk
- weak CORS configurations copied from examples
- no unified API throttling at middleware layer
- inconsistent operational playbooks

## Decision
Adopt a hardening baseline composed of:
1. Global API authentication middleware (`/api/*` with explicit public allowlist).
2. Global HTTP rate limiting middleware with Redis backend and in-memory fallback.
3. CORS wildcard guard when credentials are enabled.
4. Fernet key hardening and scheduled rotation-age checks.
5. CI security gates (bandit, pip-audit, safety, trivy) and typed checks for hardened modules.

## Consequences
### Positive
- Reduced abuse surface and brute-force risk.
- Safer default runtime behavior.
- Better operational visibility and repeatability.

### Trade-offs
- Additional environment variables and infra dependency (Redis recommended).
- Slight request overhead for middleware checks.
