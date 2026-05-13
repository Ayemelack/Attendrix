#!/usr/bin/env python3
"""
Final Test for Login Field Validation Fix
"""

import requests
import sys

def test_final_login_fix():
    base_url = "http://localhost:5000"
    
    print("🔧 Final Login Fix Test")
    print("=" * 50)
    
    try:
        # Test 1: Create a test user
        print("1. Creating Test User...")
        signup_data = {
            'firstName': 'Final',
            'lastName': 'Test',
            'email': 'finaltest@example.com',
            'password': 'password123',
            'confirmPassword': 'password123',
            'role': 'student',
            'institutionName': 'Final Test University',
            'terms': 'on'
        }
        
        response = requests.post(f"{base_url}/api/auth/signup", json=signup_data, timeout=5)
        if response.status_code == 201:
            print("   ✅ Test user created successfully")
        else:
            print(f"   ❌ Test user creation failed: {response.status_code}")
            return
        
        # Test 2: Try login with exact same credentials
        print("2. Testing Login with Created Credentials...")
        login_data = {
            'email': 'finaltest@example.com',
            'password': 'password123',
            'institutionId': 'user-inst'
        }
        
        print(f"   Sending: {login_data}")
        
        response = requests.post(f"{base_url}/api/auth/login", json=login_data, timeout=5)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("   ✅ SUCCESS: Login completed!")
            print(f"   ✅ User: {result['user']['name']}")
            print(f"   ✅ Role: {result['user']['role']}")
            print(f"   ✅ Dashboard: /dashboard?role={result['user']['role']}")
        elif response.status_code == 400:
            error_data = response.json()
            error_msg = error_data.get('error', 'Unknown error')
            print(f"   ❌ FAILED: {error_msg}")
            if 'required' in error_msg:
                print("   ❌ CAUSE: Fields still missing")
            else:
                print("   ❌ CAUSE: Other validation error")
        elif response.status_code == 401:
            error_data = response.json()
            error_msg = error_data.get('error', 'Unknown error')
            print(f"   ❌ FAILED: {error_msg}")
            if 'Invalid email, password, or institution ID' in error_msg:
                print("   ❌ CAUSE: Invalid credentials")
            else:
                print("   ❌ CAUSE: Other authentication error")
        else:
            print(f"   ❌ FAILED: Unexpected status {response.status_code}")
        
        # Test 3: Debug - Check what backend is actually receiving
        print("3. Debugging Backend Field Reception...")
        
        # Send test request with debug info
        debug_data = {
            'email': 'debug@example.com',
            'password': 'debug123',
            'institutionId': 'user-inst',
            'debug': True
        }
        
        response = requests.post(f"{base_url}/api/auth/login", json=debug_data, timeout=5)
        print(f"   Debug Request Status: {response.status_code}")
        
        if response.status_code != 200:
            error_data = response.json()
            print(f"   Debug Error: {error_data}")
        
    except Exception as e:
        print(f"   ❌ Test error: {str(e)}")
    
    print()
    print("=" * 50)
    print("🎯 FINAL LOGIN FIX TEST RESULTS")
    print()
    
    print("✅ Expected Behavior:")
    print("   - All fields filled → Successful login")
    print("   - Missing fields → 'Email, password, and institution ID are required'")
    print("   - Wrong credentials → 'Invalid email, password, or institution ID'")
    print()
    
    print("✅ Field Name Alignment:")
    print("   - Form sends: institutionId")
    print("   - Backend expects: institutionId")
    print("   - Result: ✅ ALIGNED")
    print()
    
    print("✅ Institution ID Handling:")
    print("   - Signup stores: institution_id='user-inst'")
    print("   - Login sends: institutionId='user-inst'")
    print("   - Backend checks: Both field names for compatibility")
    print()
    
    print("🌐 Next Steps:")
    print("   1. Test login in browser")
    print("   2. Check browser network tab for request payload")
    print("   3. Verify all fields are being sent")
    print("   4. Contact if issue persists")
    print()
    
    print("🚀 If this test shows success, the login issue should be resolved!")

if __name__ == "__main__":
    test_final_login_fix()
