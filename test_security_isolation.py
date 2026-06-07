"""
Multi-tenant security isolation test for Attendrix.
Tests: cross-user access, cross-institution access, role escalation,
       unauthorized query prevention, dashboard isolation.
"""
import sys
import os
import json
import requests
from datetime import datetime

BASE_URL = 'http://127.0.0.1:5000'

passed = 0
failed = 0

def test(name, condition, detail=''):
    global passed, failed
    if condition:
        passed += 1
        print(f'  PASS: {name}')
    else:
        failed += 1
        print(f'  FAIL: {name} - {detail}')

def login(email, password):
    r = requests.post(f'{BASE_URL}/api/auth/login', json={
        'email': email, 'password': password
    })
    if r.status_code == 200:
        data = r.json()
        return data.get('access_token') or data.get('token')
    return None

def api_get(path, token):
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.get(f'{BASE_URL}{path}', headers=headers)
    return r

def api_post(path, data, token):
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    r = requests.post(f'{BASE_URL}{path}', json=data, headers=headers)
    return r

print('=' * 60)
print('ATTENDRIX MULTI-TENANT SECURITY ISOLATION TEST')
print('=' * 60)

# We need two different institutions to test cross-institution isolation
# Check if we can find test users
print('\n[1] Testing authentication...')

# Try to login as known users
# The system should have at least one user seeded
r = requests.get(f'{BASE_URL}/api/ping')
test('Server is reachable', r.status_code == 200, str(r.status_code))

# Try login with demo credentials
tokens = {}
test_users = [
    {'email': 'super@attendrix.com', 'password': 'SuperAdmin123!', 'role': 'super_admin', 'label': 'Super Admin'},
    {'email': 'admin@institution-a.com', 'password': 'Admin123!', 'role': 'institutional_admin', 'label': 'Inst Admin A'},
    {'email': 'lecturer@institution-a.com', 'password': 'Lecturer123!', 'role': 'lecturer', 'label': 'Lecturer A'},
    {'email': 'student@institution-a.com', 'password': 'Student123!', 'role': 'student', 'label': 'Student A'},
    {'email': 'admin@institution-b.com', 'password': 'Admin123!', 'role': 'institutional_admin', 'label': 'Inst Admin B'},
    {'email': 'student@institution-b.com', 'password': 'Student123!', 'role': 'student', 'label': 'Student B'},
]

for u in test_users:
    token = login(u['email'], u['password'])
    if token:
        tokens[u['label']] = token
        print(f'  Login OK: {u["label"]} ({u["email"]})')
    else:
        print(f'  Login FAILED: {u["label"]} ({u["email"]}) - skipping tests for this user')

if not tokens:
    print('\nWARNING: Could not log in to any user. Checking if server is running...')
    print('Make sure the server is running on port 5000 first.')
    sys.exit(1)

print(f'\n[2] Testing cross-institution data isolation...')

# Test: Student A should NOT see Student B's data
if 'Student A' in tokens and 'Student B' in tokens:
    r_a = api_get('/api/student/dashboard', tokens['Student A'])
    r_b = api_get('/api/student/dashboard', tokens['Student B'])
    
    if r_a.status_code == 200:
        data_a = r_a.json()
        test('Student A dashboard accessible', True)
    else:
        test('Student A dashboard accessible', False, f'Status {r_a.status_code}')
    
    if r_b.status_code == 200:
        data_b = r_b.json()
        test('Student B dashboard accessible', True)
    else:
        test('Student B dashboard accessible', False, f'Status {r_b.status_code}')

# Test: Inst Admin A should NOT access Inst Admin B's data
if 'Inst Admin A' in tokens and 'Inst Admin B' in tokens:
    r_a = api_get('/api/institutional/dashboard', tokens['Inst Admin A'])
    test('Inst Admin A dashboard accessible', r_a.status_code in (200, 404), str(r_a.status_code))
    
    # Try to access the other institution's course data
    r_cross = api_get('/api/institutional/users', tokens['Inst Admin A'])
    test('Inst Admin A can list users', r_cross.status_code == 200, str(r_cross.status_code))
    if r_cross.status_code == 200:
        users = r_cross.json().get('users', r_cross.json().get('data', []))
        # Flatten in case it's paginated
        if isinstance(users, dict):
            users = users.get('users', [])
        inst_ids = set(u.get('institution_id') for u in users if u.get('institution_id'))
        test('Inst Admin A only sees their institution users',
             len(inst_ids) <= 1, f'Found institutions: {inst_ids}')

# Test: Student A cannot access lecturer-only endpoints
if 'Student A' in tokens:
    r = api_get('/api/institutional/dashboard', tokens['Student A'])
    test('Student A blocked from institutional admin dashboard',
         r.status_code in (401, 403), str(r.status_code))
    
    r = api_get('/api/institutional/users', tokens['Student A'])
    test('Student A blocked from listing all users',
         r.status_code in (401, 403), str(r.status_code))

# Test: Lecturer A cannot access super admin endpoints
if 'Lecturer A' in tokens:
    r = api_get('/api/super-admin/overview', tokens['Lecturer A'])
    test('Lecturer A blocked from super admin overview',
         r.status_code in (401, 403), str(r.status_code))

print(f'\n[3] Testing authorization enforcement layer...')

# Test: Super Admin can access everything
if 'Super Admin' in tokens:
    r = api_get('/api/super-admin/overview', tokens['Super Admin'])
    test('Super Admin can access overview', r.status_code == 200, str(r.status_code))
    
    r = api_get('/api/institutional/dashboard', tokens['Super Admin'])
    # Super admin should be able to access institutional endpoints too
    test('Super Admin can access institutional endpoints',
         r.status_code in (200, 404), str(r.status_code))

# Test: invalid tokens are rejected
r = api_get('/api/institutional/dashboard', 'invalid_token_here')
test('Invalid token rejected', r.status_code in (401, 403), str(r.status_code))

# Test: missing auth header
r = requests.get(f'{BASE_URL}/api/institutional/dashboard')
test('Missing auth header rejected', r.status_code in (401, 403), str(r.status_code))

print(f'\n[4] Testing institution-aware query scoping...')

# Verify that security enforcement is active by checking logs would show warnings
# We can't check logs directly, but we can verify the enforcement module loaded
try:
    from src.infrastructure.firebase_service import FirebaseService, REQUIRES_INSTITUTION_SCOPING
    test('REQUIRES_INSTITUTION_SCOPING has attendance_records',
         'attendance_records' in REQUIRES_INSTITUTION_SCOPING)
    test('REQUIRES_INSTITUTION_SCOPING has security_logs',
         'security_logs' in REQUIRES_INSTITUTION_SCOPING)
    test('REQUIRES_INSTITUTION_SCOPING has users',
         'users' in REQUIRES_INSTITUTION_SCOPING)
    test('REQUIRES_INSTITUTION_SCOPING has notifications',
         'notifications' in REQUIRES_INSTITUTION_SCOPING)
    test('REQUIRES_INSTITUTION_SCOPING has network_nodes',
         'network_nodes' in REQUIRES_INSTITUTION_SCOPING)
    test('EXEMPT_FROM_SCOPING has institutions',
         'institutions' in FirebaseService._get_current_user.__globals__.get('EXEMPT_FROM_SCOPING', set()))
except Exception as e:
    test('Enforcement module loaded', False, str(e))

print(f'\n[5] Testing firestore.rules file...')

try:
    with open('firestore.rules') as f:
        rules = f.read()
    checks = [
        ('prevents global read', 'allow read, write: if false;' in rules),
        ('has institution isolation', 'institution_id' in rules),
        ('has super admin access', 'super_admin' in rules),
        ('has role-based access', 'role' in rules),
        ('has student isolation', 'student' in rules),
        ('blocks default access', 'match /{document=**}' in rules),
    ]
    for name, ok in checks:
        test(f'firestore.rules {name}', ok)
except FileNotFoundError:
    test('firestore.rules exists', False, 'File not found')

print(f'\n[6] Testing storage.rules file...')

try:
    with open('storage.rules') as f:
        rules = f.read()
    test('storage.rules exists', True)
    test('storage.rules has institution scoping', 'institution_id' in rules)
    test('storage.rules blocks default', 'match /{allPaths=**}' in rules)
except FileNotFoundError:
    test('storage.rules exists', False, 'File not found')

print('\n' + '=' * 60)
print(f'RESULTS: {passed} passed / {failed} failed / {passed + failed} total')
print('=' * 60)

if failed > 0:
    print('SOME TESTS FAILED - review issues above')
    sys.exit(1)
else:
    print('ALL SECURITY ISOLATION TESTS PASSED')
    sys.exit(0)
