# Error Sanitization & Information Leakage Report — Phase 7

## Summary
Fixed 6 categories of information leakage that exposed internal server details to clients.

## Changes Made

### 1. Error Response Sanitization (4 direct leaks + 8 service-layer leaks)
**Files:** `src/presentation/routes/auth.py`, `app.py`, `src/application/feedback_service.py`, `src/application/event_service.py`, `src/application/voucher_seeder.py`
- Replaced all `jsonify({'error': str(e)})` with generic messages: `'Invalid registration data'`, `'Session creation failed'`, etc.
- Exception details are still logged server-side via `logger.error(...)`
- Fixed 12 locations total where raw exceptions leaked to HTTP responses

### 2. CORS Wildcard Removal
**File:** `src/infrastructure/security/api_security.py`
- Replaced `headers['Access-Control-Allow-Origin'] = '*'` with configured origin from `CORS_ALLOWED_ORIGINS` env var (default: `https://attendrix.app`)
- Added `import os` at module level

### 3. SSE Token Security
**File:** `app.py` (lines 1786-1870)
- Added secondary token sources: `Authorization: Bearer` header and `auth_token` cookie
- Query param `?token=` is still supported as fallback but logs a warning
- This reduces token exposure in server logs, browser history, and referrer headers

### 4. Session Token DOM Exposure
**File:** `src/presentation/templates/schedule-demo.html`
- Removed hidden `<input id="sessionToken">` from DOM
- Session token now stored in `sessionStorage` and cookie only, never in page source
- Updated JS references from DOM element to in-memory variable

## Remaining Low-Risk Items
- Dev-mode 500 handler (`str(error)`) — gated behind `ENVIRONMENT == 'development'`
- `comprehensive_security.py` dev/staging error detail — same env gating

## Risk Reduction
- **Information leaks fixed:** 12
- **DOM token exposure:** Eliminated
- **CORS misconfiguration:** Eliminated
- **SSE token leakage:** Reduced (query param deprecated)
