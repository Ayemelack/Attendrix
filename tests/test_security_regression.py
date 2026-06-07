"""
Phase 7 — Security Regression Tests.

Verifies that all critical security controls remain active and enforceable.
Run with the server running on http://127.0.0.1:5000.

Usage:
    py tests/test_security_regression.py
"""

import sys
import os
import json
import time
import requests

BASE_URL = os.environ.get('TEST_BASE_URL', 'http://127.0.0.1:5000')

passed = 0
failed = 0

def test(name, condition, detail=''):
    global passed, failed
    if condition:
        passed += 1
        print(f'  PASS: {name}')
    else:
        failed += 1
        print(f'  FAIL: {name}  -- {detail}')

def login(email, password):
    r = requests.post(f'{BASE_URL}/api/auth/login', json={
        'email': email, 'password': password
    })
    if r.status_code == 200:
        data = r.json()
        return data.get('access_token') or data.get('token')
    return None

def api_get(path, token=None, headers=None):
    hdrs = {'Content-Type': 'application/json'}
    if token:
        hdrs['Authorization'] = f'Bearer {token}'
    if headers:
        hdrs.update(headers)
    return requests.get(f'{BASE_URL}{path}', headers=hdrs)

def api_post(path, data=None, token=None, headers=None):
    hdrs = {'Content-Type': 'application/json'}
    if token:
        hdrs['Authorization'] = f'Bearer {token}'
    if headers:
        hdrs.update(headers)
    return requests.post(f'{BASE_URL}{path}', json=data or {}, headers=hdrs)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
print('=' * 62)
print('ATTENDRIX SECURITY REGRESSION TEST SUITE')
print('=' * 62)

r = api_get('/ping')
test('Server reachable', r.status_code == 200, str(r.status_code))

# Attempt to get tokens for all roles
tokens = {}
test_users = [
    {'email': 'super@attendrix.com', 'password': 'SuperAdmin123!', 'label': 'SuperAdmin'},
    {'email': 'admin@institution-a.com', 'password': 'Admin123!', 'label': 'InstAdmin'},
    {'email': 'lecturer@institution-a.com', 'password': 'Lecturer123!', 'label': 'Lecturer'},
    {'email': 'student@institution-a.com', 'password': 'Student123!', 'label': 'Student'},
]
for u in test_users:
    tok = login(u['email'], u['password'])
    if tok:
        tokens[u['label']] = tok
    print(f'  Login: {u["label"]} -> {"OK" if tok else "FAILED"}')

has_any_token = bool(tokens)
test('At least one user can authenticate', has_any_token)


# ===================================================================
# 1. AUTH ENFORCEMENT — Innovation routes return 401 without token
# ===================================================================
print('\n[1] Innovation Route Auth Enforcement')

INNOVATION_ENDPOINTS = [
    '/api/innovation/risk/predict',
    '/api/innovation/participation/classify',
    '/api/innovation/classroom/intelligence',
    '/api/innovation/digital-twin/snapshot',
    '/api/innovation/security/emergency/activate',
    '/api/innovation/intervention/create',
    '/api/innovation/reputation/student',
    '/api/innovation/trust/attest',
]

for ep in INNOVATION_ENDPOINTS:
    r = api_post(ep)
    test(f'  {ep} -> 401 without auth', r.status_code == 401, str(r.status_code))

# With valid auth they should reach the engine-unavailable 503
if has_any_token:
    tok = list(tokens.values())[0]
    for ep in INNOVATION_ENDPOINTS:
        r = api_post(ep, token=tok)
        test(f'  {ep} -> accepts auth (503 engine or 200)',
             r.status_code in (200, 400, 503), str(r.status_code))


# ===================================================================
# 2. AUTH ENFORCEMENT — WebAuthn routes
# ===================================================================
print('\n[2] WebAuthn Route Auth Enforcement')

R = api_post('/auth/webauthn/register/begin')
test('/auth/webauthn/register/begin -> 401 without auth',
     R.status_code == 401, str(R.status_code))

R = api_post('/auth/webauthn/register/complete')
test('/auth/webauthn/register/complete -> 401 without auth',
     R.status_code == 401, str(R.status_code))

R = api_get('/auth/webauthn/credentials')
test('/auth/webauthn/credentials -> 401 without auth',
     R.status_code == 401, str(R.status_code))

R = api_get('/auth/webauthn/admin/list')
test('/auth/webauthn/admin/list -> 401 without auth',
     R.status_code == 401, str(R.status_code))

R = api_post('/auth/webauthn/admin/revoke')
test('/auth/webauthn/admin/revoke -> 401 without auth',
     R.status_code == 401, str(R.status_code))

# Public WebAuthn endpoints should NOT require auth
R = api_get('/auth/webauthn/status')
test('/auth/webauthn/status -> public',
     R.status_code == 200, str(R.status_code))

R = api_post('/auth/webauthn/authenticate/begin')
test('/auth/webauthn/authenticate/begin -> public (400 for missing user_id)',
     R.status_code == 400, str(R.status_code))


# ===================================================================
# 3. ROLE ENFORCEMENT
# ===================================================================
print('\n[3] Role Enforcement')

if 'Student' in tokens:
    R = api_get('/api/institutional/users', token=tokens['Student'])
    test('Student blocked from listing all users',
         R.status_code in (401, 403), str(R.status_code))

    R = api_get('/api/super-admin/overview', token=tokens['Student'])
    test('Student blocked from super admin overview',
         R.status_code in (401, 403), str(R.status_code))

    R = api_get('/auth/webauthn/admin/list', token=tokens['Student'])
    test('Student blocked from WebAuthn admin list',
         R.status_code in (401, 403), str(R.status_code))

if 'Lecturer' in tokens:
    R = api_get('/api/super-admin/overview', token=tokens['Lecturer'])
    test('Lecturer blocked from super admin overview',
         R.status_code in (401, 403), str(R.status_code))

if 'InstAdmin' in tokens:
    R = api_get('/api/super-admin/overview', token=tokens['InstAdmin'])
    test('InstAdmin blocked from super admin overview (if not super_admin)',
         R.status_code in (401, 403), str(R.status_code))


# ===================================================================
# 4. RATE LIMITING — Login endpoint
# ===================================================================
print('\n[4] Rate Limiting Detection')

# Quickly hit login with bad credentials to trigger rate limit
rate_limited = False
for i in range(15):
    R = requests.post(f'{BASE_URL}/api/auth/login', json={
        'email': 'rate-limit-test@test.com',
        'password': f'WrongPass{i}'
    })
    if R.status_code == 429:
        rate_limited = True
        break

test('Login rate limits after repeated failures', rate_limited,
     f'Last status: {R.status_code}')


# ===================================================================
# 5. JWT BLACKLIST — Token rejected after logout
# ===================================================================
print('\n[5] JWT Blacklist / Token Revocation')

if 'Student' in tokens:
    test_token = tokens['Student']

    R = api_get('/api/student/dashboard', token=test_token)
    test('Token works before logout',
         R.status_code in (200, 404), str(R.status_code))

    R = api_post('/api/auth/logout', token=test_token)
    test('Logout endpoint accessible',
         R.status_code in (200, 401), str(R.status_code))

    if R.status_code == 200:
        R = api_get('/api/student/dashboard', token=test_token)
        test('Token rejected after logout (blacklist active)',
             R.status_code in (401, 403), f'Got {R.status_code} instead of 401')


# ===================================================================
# 6. INPUT VALIDATION — Login field whitelisting
# ===================================================================
print('\n[6] Input Validation')

R = requests.post(f'{BASE_URL}/api/auth/login', json={})
test('Login with empty body -> 400',
     R.status_code == 400, str(R.status_code))

R = requests.post(f'{BASE_URL}/api/auth/login', json={
    'email': 'test@test.com'
})
test('Login missing password -> 400',
     R.status_code == 400, str(R.status_code))

R = requests.post(f'{BASE_URL}/api/auth/login', json={
    'email': 'test@test.com',
    'password': 'SomePass123!',
    'is_admin': True,
    'role': 'super_admin',
})
test('Login with unexpected fields rejected -> 400',
     R.status_code == 400, str(R.status_code))


# ===================================================================
# 7. MASS ASSIGNMENT PREVENTION — Registration field whitelist
# ===================================================================
print('\n[7] Mass Assignment Prevention')

R = requests.post(f'{BASE_URL}/api/auth/register', json={
    'email': 'mass@assign-test.com',
    'password': 'ValidPass123!',
    'first_name': 'Test',
    'last_name': 'User',
    'role': 'student',
    'voucher_code': 'INVALID',
    'institution_id': 'inst-test',
    'is_active': False,
    'email_verified': True,
    'role': 'super_admin',
})
test('Registration rejects dangerous fields',
     R.status_code == 400, str(R.status_code))


# ===================================================================
# 8. CORS HARDENING — No wildcard
# ===================================================================
print('\n[8] CORS Hardening')

R = api_get('/ping')
origin = R.headers.get('Access-Control-Allow-Origin', '')
test('Access-Control-Allow-Origin is not wildcard',
     origin != '*', f'Origin: {origin}')
if origin:
    test('Access-Control-Allow-Origin is specific',
         origin in ('https://attendrix.app', 'http://127.0.0.1:5000'),
         f'Origin: {origin}')


# ===================================================================
# 9. ERROR SANITIZATION — No raw exception leakage
# ===================================================================
print('\n[9] Error Sanitization')

ERROR_PATTERNS = ['Traceback', 'File "', 'line ', 'KeyError', 'ValueError',
                  'IntegrityError', 'DatabaseError', 'OperationalError',
                  'sqlite3.', 'psycopg2.', 'FirebaseError', 'HTTPError']

# Trigger various error conditions and check responses for leakage
R = requests.post(f'{BASE_URL}/api/auth/login', json={
    'email': 'x' * 9999 + '@test.com',
    'password': 'test'
})
body = R.text.lower()
leaked = any(p.lower() in body for p in ERROR_PATTERNS)
test('Login error does not leak internals',
     not leaked, f'Status {R.status_code}')


# ===================================================================
# 10. SSE TOKEN — Supports header/cookie (token not just query param)
# ===================================================================
print('\n[10] SSE Token Source')

# SSE endpoint should return 401 without any token
R = api_get('/api/institutional/events/stream')
test('SSE -> 401 without token',
     R.status_code == 401, str(R.status_code))

# With Authorization header it should pass validation
if has_any_token:
    tok = list(tokens.values())[0]
    R = api_get('/api/institutional/events/stream', token=tok)
    test('SSE accepts Bearer token',
         R.status_code in (200, 503), str(R.status_code))

# With query param (deprecated) it should still work but log a warning
if has_any_token:
    tok = list(tokens.values())[0]
    R = requests.get(f'{BASE_URL}/api/institutional/events/stream?token={tok}',
                     headers={'Content-Type': 'application/json'})
    test('SSE accepts query-param token (deprecated fallback)',
         R.status_code in (200, 503), str(R.status_code))


# ===================================================================
# 11. SESSION TOKEN NOT IN DOM
# ===================================================================
print('\n[11] Session Token DOM Exposure')

R = requests.get(f'{BASE_URL}/schedule-demo')
if R.status_code == 200:
    test('schedule-demo page renders', True)
    has_session_input = 'id="sessionToken"' in R.text
    test('No sessionToken hidden input in DOM',
         not has_session_input,
         'Found sessionToken input in page source')
else:
    test('schedule-demo page accessible',
         R.status_code in (200, 404, 302), str(R.status_code))


# ===================================================================
# RESULTS
# ===================================================================
print('\n' + '=' * 62)
print(f'RESULTS: {passed} passed / {failed} failed / {passed + failed} total')
print('=' * 62)

if failed > 0:
    print('SECURITY REGRESSION TESTS FAILED')
    sys.exit(1)
else:
    print('ALL SECURITY REGRESSION TESTS PASSED')
    sys.exit(0)
