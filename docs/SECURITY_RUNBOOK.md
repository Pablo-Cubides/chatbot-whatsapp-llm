# Security Runbook

## 1) HTTP Rate Limit

Variables:
- `RATE_LIMIT_ENABLED=true`
- `RATE_LIMIT_REDIS_ENABLED=true`
- `RATE_LIMIT_REDIS_URL=redis://redis:6379/0`
- `RATE_LIMIT_API_REQUESTS=120`
- `RATE_LIMIT_AUTH_REQUESTS=10`
- `RATE_LIMIT_SYSTEM_REQUESTS=30`

Validation:
1. Call any `/api/*` endpoint repeatedly.
2. Confirm response `429` when threshold is exceeded.
3. Confirm headers exist: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

## 2) CORS Hardening

- Never use `*` in `CORS_ORIGINS` if credentials are enabled.
- Server now auto-forces localhost safe defaults when `*` is detected.

## 3) Fernet Key Hardening

- Key file: `data/fernet.key`
- POSIX: owner read/write only.
- Windows: ACL is reduced to current user with `icacls`.

Rotation policy:
- `FERNET_KEY_ROTATION_DAYS=90` (recommended)
- Scheduler checks key age and logs warning when rotation is due.

## 4) Incident quick actions

1. Rotate `JWT_SECRET` and revoke active tokens.
2. Rotate `FERNET_KEY` and re-encrypt critical secrets if needed.
3. Reduce rate-limit thresholds temporarily.
4. Review auth and webhook signature logs for anomalies.
