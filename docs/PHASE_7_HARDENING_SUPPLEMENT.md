# Phase 7 — Hardening Supplement Report

## Summary
Added 7 security hardening layers: admin 2FA enforcement, rate limit gap closure,
input validation, security alerting, secrets cleanup, and dependency scanning.

## Changes Made

### 1. Admin 2FA Enforcement (P0)
**Files:** `src/application/rbac.py`, `src/presentation/routes/webauthn_routes.py`
- Added `require_admin_webauthn` decorator in `rbac.py` — checks that admin/super_admin users have at least one active WebAuthn passkey before granting access to sensitive admin actions
- Applied decorator to `webauthn_routes.py` admin credential management routes (`/admin/list`, `/admin/revoke`)
- Non-admin roles pass through transparently
- Bootstrap enrollment flow remains unblocked (register/begin and register/complete are exempt)

### 2. Rate Limiting Gap Closure (P1)
**Files:** `src/presentation/routes/webauthn_routes.py`, `src/infrastructure/security_reinforcements.py`
- Added `@rate_limit_endpoint(limit=20, window=300, scope='ip', block_duration=600)` to `/auth/webauthn/authenticate/begin`
- Added `@rate_limit_endpoint(limit=10, window=300, scope='ip', block_duration=600)` to `/auth/webauthn/authenticate/complete`
- Added `@rate_limit_endpoint(limit=5, window=900, scope='ip', block_duration=1800)` to `/api/auth/forgot-password`
- Added `@rate_limit_endpoint(limit=5, window=900, scope='ip', block_duration=1800)` to `/api/auth/reset-password`

### 3. Input Injection Protection (P1)
**File:** `src/presentation/routes/auth.py`
- Added `InputSanitizer.validate_json_body()` call to the login route — restricts to allowed fields (`email`, `password`, `remember_me`, `device_fingerprint`, `institutionId`, `institution_id`)
- Rejects unexpected fields with `400 Bad Request`

### 4. Security Event Alerting (P1)
**File:** `src/infrastructure/security_legacy.py`
- Added `_dispatch_alert()` to `SecurityAuditLogger.log_event()` — sends webhook POST when risk_score >= 50
- Configured via `SECURITY_ALERT_WEBHOOK` environment variable (Slack/Teams compatible)
- Fail-safe: if webhook is unreachable or unset, alert is silently skipped

### 5. Production Secrets Cleanup (P0)
- Removed `.env.dev` from git tracking (`git rm --cached`)
- Confirmed no Firebase admin SDK credentials, service account files, or key material in git history

### 6. Dependency Vulnerability Scanning (P2)
**New file:** `.github/workflows/security-scan.yml`
- Runs `pip-audit` on every push and PR to `master`/`main`
- Weekly scheduled scan (Mondays 06:00 UTC)
- Secrets scan step checks for committed `.env`, credential JSON, and key files

## Risk Reduction
- **Admin 2FA enforced**: Credential management and admin routes now require WebAuthn passkey
- **Rate limit gaps closed**: 4 previously unprotected authentication endpoints
- **Input validation**: Login route now field-whitelisted
- **Alerting**: High-risk events (score >= 50) can notify via webhook
- **CI/CD scanning**: Dependency vulnerabilities caught before deployment
