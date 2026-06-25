#!/usr/bin/env python3
import requests
import time
import sys

def verify():
    base_url = "http://localhost:5000"
    test_email = f"browser_user_{int(time.time())}@example.com"
    institution_id = "TEST-BROWSER-INST"

    print("🔄 Starting Verification of Login Patch")
    print("=" * 60)

    # 1. Sign up user
    signup_payload = {
        'firstName': 'Browser',
        'lastName': 'Tester',
        'email': test_email,
        'password': 'Password123!',
        'confirmPassword': 'Password123!',
        'role': 'student',
        'institutionName': 'Browser Test University',
        'institutionId': institution_id,
        'terms': 'on'
    }
    
    print(f"1. Registering user {test_email} with institution {institution_id}...")
    r = requests.post(f"{base_url}/api/auth/signup", json=signup_payload)
    if r.status_code != 201:
        print(f"❌ Signup failed with status {r.status_code}: {r.text}")
        sys.exit(1)
    print("✅ Signup successful")

    # 2. Browser Login (No institutionId, Browser User-Agent)
    # Simulate Chrome user agent
    browser_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    login_payload_no_inst = {
        'email': test_email,
        'password': 'Password123!'
    }
    print("\n2. Simulating Browser Login (No Institution ID, Browser User-Agent)...")
    r = requests.post(f"{base_url}/api/auth/login", json=login_payload_no_inst, headers=browser_headers)
    if r.status_code == 200:
        print("✅ Browser login without institution ID: SUCCESS")
        result = r.json()
        print(f"   Received access token: {result.get('access_token') is not None}")
    else:
        print(f"❌ Browser login failed with status {r.status_code}: {r.text}")
        sys.exit(1)

    # 3. Programmatic Login (No institutionId, default requests User-Agent)
    print("\n3. Simulating Programmatic Login (No Institution ID, python-requests User-Agent)...")
    # By default, requests sends User-Agent: python-requests/...
    r = requests.post(f"{base_url}/api/auth/login", json=login_payload_no_inst)
    if r.status_code == 400:
        print("✅ Programmatic login without institution ID correctly rejected with 400 Bad Request")
        error_data = r.json()
        print(f"   Error message: {error_data.get('error')}")
    else:
        print(f"❌ Programmatic login failed. Expected 400 Bad Request, got {r.status_code}: {r.text}")
        sys.exit(1)

    # 4. Programmatic Login (With institutionId, default requests User-Agent)
    login_payload_with_inst = {
        'email': test_email,
        'password': 'Password123!',
        'institutionId': institution_id
    }
    print("\n4. Simulating Programmatic Login (With Institution ID, python-requests User-Agent)...")
    r = requests.post(f"{base_url}/api/auth/login", json=login_payload_with_inst)
    if r.status_code == 200:
        print("✅ Programmatic login with institution ID: SUCCESS")
    else:
        print(f"❌ Programmatic login with institution ID failed with status {r.status_code}: {r.text}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🎉 ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    verify()
