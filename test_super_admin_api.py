import sys
import os
import requests
import json

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.infrastructure.pg_repositories import pg_repos
from src.application.auth_service import auth_service

# Find a super admin
super_admins = [u for u in pg_repos.user.list_all() if u.role == 'super_admin' or getattr(u.role, 'value', u.role) == 'super_admin']

if not super_admins:
    print("No super admins found.")
    sys.exit(1)

user = super_admins[0]
print(f"Testing with user: {user.email}")

token = auth_service._generate_access_token({
    'id': user.id,
    'email': user.email,
    'role': user.role.value if hasattr(user.role, 'value') else user.role,
    'institution_id': user.institution_id
})

res = requests.get('http://127.0.0.1:5000/api/super-admin/overview', headers={
    'Authorization': f'Bearer {token}'
})
print(f"Status: {res.status_code}")
print(f"Response: {res.text}")
