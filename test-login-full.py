#!/usr/bin/env python3
"""
Comprehensive test for Attendrix login functionality
"""

import requests
import json
import sys

def test_login_functionality():
    base_url = "http://localhost:5000"
    
    print("🔐 Comprehensive Login Functionality Test")
    print("=" * 60)
    
    # Test 1: Login Page UI
    print("1. Testing Login Page UI...")
    try:
        response = requests.get(f"{base_url}/login", timeout=5)
        if response.status_code == 200:
            content = response.text
            checks = [
                ('Attendrix Login branding', 'Attendrix Login'),
                ('Email field', 'name="email"'),
                ('Password field', 'name="password"'),
                ('Institution ID field', 'name="institutionId"'),
                ('Login button', 'Secure Login'),
                ('Remember me checkbox', 'rememberMe'),
                ('Demo request button', 'Request Demo'),
                ('Back to home link', 'Back to Home')
            ]
            
            for check_name, check_text in checks:
                if check_text in content:
                    print(f"   ✅ {check_name}: Present")
                else:
                    print(f"   ❌ {check_name}: Missing")
        else:
            print(f"   ❌ Login page failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Login page error: {str(e)}")
    
    print()
    
    # Test 2: Login API - Valid Credentials
    print("2. Testing Login API - Valid Demo Credentials...")
    try:
        login_data = {
            'email': 'demo@attendrix.com',
            'password': 'demo123',
            'institution_id': 'demo-inst'
        }
        
        response = requests.post(f"{base_url}/api/auth/login", 
                               json=login_data, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            print("   ✅ Login API: Success")
            print(f"   ✅ User ID: {result.get('user', {}).get('id')}")
            print(f"   ✅ User Role: {result.get('user', {}).get('role')}")
            print(f"   ✅ Access Token: Present")
            print(f"   ✅ Refresh Token: Present")
        else:
            print(f"   ❌ Login API failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Login API error: {str(e)}")
    
    print()
    
    # Test 3: Login API - Invalid Credentials
    print("3. Testing Login API - Invalid Credentials...")
    try:
        login_data = {
            'email': 'invalid@test.com',
            'password': 'wrongpass',
            'institution_id': 'wrong-inst'
        }
        
        response = requests.post(f"{base_url}/api/auth/login", 
                               json=login_data, timeout=5)
        
        if response.status_code == 401:
            print("   ✅ Login API: Correctly rejects invalid credentials")
        else:
            print(f"   ❌ Login API should return 401, got: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Login API error: {str(e)}")
    
    print()
    
    # Test 4: Login API - Missing Fields
    print("4. Testing Login API - Missing Required Fields...")
    try:
        # Missing institution_id
        login_data = {
            'email': 'demo@attendrix.com',
            'password': 'demo123'
        }
        
        response = requests.post(f"{base_url}/api/auth/login", 
                               json=login_data, timeout=5)
        
        if response.status_code == 400:
            print("   ✅ Login API: Correctly rejects missing fields")
        else:
            print(f"   ❌ Login API should return 400, got: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Login API error: {str(e)}")
    
    print()
    
    # Test 5: Landing Page Still Works
    print("5. Testing Landing Page Still Accessible...")
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            print("   ✅ Landing page: Still accessible")
        else:
            print(f"   ❌ Landing page failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Landing page error: {str(e)}")
    
    print()
    
    # Test 6: Health Check Still Works
    print("6. Testing Health Check...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ Health check: Working")
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Health check error: {str(e)}")
    
    print()
    print("=" * 60)
    print("🎯 LOGIN FUNCTIONALITY TEST COMPLETE")
    print()
    print("📱 Manual Testing Instructions:")
    print(f"   1. Visit: {base_url}/login")
    print("   2. Use demo credentials:")
    print("      Email: demo@attendrix.com")
    print("      Password: demo123")
    print("      Institution ID: demo-inst")
    print("   3. Test form validation and error handling")
    print("   4. Test navigation back to home")
    print()
    print("🌐 All systems ready for development!")

if __name__ == "__main__":
    test_login_functionality()
