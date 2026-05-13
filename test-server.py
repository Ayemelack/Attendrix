#!/usr/bin/env python3
"""
Test script to verify Attendrix landing page is working correctly
"""

import requests
import json
import sys

def test_server():
    base_url = "http://localhost:5000"
    
    print("🧪 Testing Attendrix Server...")
    print("=" * 50)
    
    # Test 1: Health Check
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Health Check: PASSED")
            print(f"   Status: {data.get('status')}")
            print(f"   Version: {data.get('version')}")
        else:
            print(f"❌ Health Check: FAILED (Status: {response.status_code})")
    except Exception as e:
        print(f"❌ Health Check: ERROR ({str(e)})")
    
    print()
    
    # Test 2: Landing Page
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'text/html' in content_type:
                print("✅ Landing Page: SERVING HTML")
                print(f"   Content-Type: {content_type}")
                print(f"   Content-Length: {len(response.content)} bytes")
                
                # Check for key HTML elements
                if b'attendrix' in response.content.lower():
                    print("   ✅ Contains Attendrix branding")
                if b'bootstrap' in response.content.lower():
                    print("   ✅ Bootstrap CSS loaded")
                if b'landing.css' in response.content:
                    print("   ✅ Custom CSS loaded")
                    
            else:
                print(f"❌ Landing Page: NOT HTML (Content-Type: {content_type})")
                print(f"   Response: {response.text[:200]}...")
        else:
            print(f"❌ Landing Page: FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ Landing Page: ERROR ({str(e)})")
    
    print()
    
    # Test 3: Static Files
    static_files = [
        '/static/css/landing.css',
        '/static/js/landing.js'
    ]
    
    for static_file in static_files:
        try:
            response = requests.get(f"{base_url}{static_file}", timeout=5)
            if response.status_code == 200:
                print(f"✅ Static File: {static_file} - SERVED")
            else:
                print(f"❌ Static File: {static_file} - FAILED ({response.status_code})")
        except Exception as e:
            print(f"❌ Static File: {static_file} - ERROR ({str(e)})")
    
    print()
    print("=" * 50)
    print("🌐 Access Attendrix at: http://localhost:5000")
    print("📋 Server is ready for development!")

if __name__ == "__main__":
    test_server()
