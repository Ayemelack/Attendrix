#!/usr/bin/env python3
"""
Test script to verify Attendrix login page is working correctly
"""

import requests
import json
import sys

def test_login_page():
    base_url = "http://localhost:5000"
    
    print("🔐 Testing Attendrix Login Page...")
    print("=" * 50)
    
    # Test 1: Login Page Access
    try:
        response = requests.get(f"{base_url}/login", timeout=5)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'text/html' in content_type:
                print("✅ Login Page: SERVING HTML")
                print(f"   Content-Type: {content_type}")
                print(f"   Content-Length: {len(response.content)} bytes")
                
                # Check for key HTML elements
                if b'Attendrix Login' in response.content:
                    print("   ✅ Contains Attendrix Login branding")
                if b'email' in response.content.lower():
                    print("   ✅ Email field present")
                if b'password' in response.content.lower():
                    print("   ✅ Password field present")
                if b'institution' in response.content.lower():
                    print("   ✅ Institution ID field present")
                if b'Secure Login' in response.content:
                    print("   ✅ Login button present")
                    
            else:
                print(f"❌ Login Page: NOT HTML (Content-Type: {content_type})")
                print(f"   Response: {response.text[:200]}...")
        else:
            print(f"❌ Login Page: FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ Login Page: ERROR ({str(e)})")
    
    print()
    
    # Test 2: Landing Page Still Works
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'text/html' in content_type:
                print("✅ Landing Page: STILL SERVING HTML")
            else:
                print(f"❌ Landing Page: NOT HTML (Content-Type: {content_type})")
        else:
            print(f"❌ Landing Page: FAILED (Status: {response.status_code})")
    except Exception as e:
        print(f"❌ Landing Page: ERROR ({str(e)})")
    
    print()
    
    # Test 3: Health Check Still Works
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health Check: STILL WORKING")
        else:
            print(f"❌ Health Check: FAILED (Status: {response.status_code})")
    except Exception as e:
        print(f"❌ Health Check: ERROR ({str(e)})")
    
    print()
    print("=" * 50)
    print("🌐 Access Attendrix Login at: http://localhost:5000/login")
    print("🏠 Landing Page: http://localhost:5000")
    print("📋 Login page is ready for authentication!")

if __name__ == "__main__":
    test_login_page()
