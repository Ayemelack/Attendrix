#!/usr/bin/env python3
"""
Test current homepage state to verify issues mentioned by user
"""

import requests
import sys

def test_current_homepage():
    base_url = "http://localhost:5000"
    
    print("🔍 Current Homepage State Test")
    print("=" * 60)
    
    # Test 1: Check if homepage loads
    print("1. Testing Homepage Loading...")
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            print("   ✅ Homepage loads successfully")
            content = response.text
        else:
            print(f"   ❌ Homepage failed: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Homepage error: {str(e)}")
        return
    
    # Test 2: Check for navigation overlap issues
    print("2. Testing Navigation Layout...")
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            content = response.text
            # Check if hero section has proper padding
            if 'padding-top: 150px' in content:
                print("   ✅ Hero section has navigation padding")
            else:
                print("   ⚠️  Hero section padding might not be applied")
                
            # Check if header content is present
            if b'Attendrix' in content and b'Secure. Smart. Structured Attendance' in content:
                print("   ✅ Header content present")
            else:
                print("   ❌ Header content missing")
                
            # Check if content is covered by looking at structure
            if 'col-lg-6' in content and content.count('col-lg-6') == 1:
                print("   ✅ Single column layout (no image column)")
            else:
                print("   ⚠️  Multiple columns detected")
        else:
            print(f"   ❌ Homepage failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Layout test error: {str(e)}")
    
    # Test 3: Check button functionality
    print("3. Testing Button Links...")
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            content = response.text
            
            # Check Get Started button
            if 'href="/signup"' in content:
                print("   ✅ Get Started links to /signup")
            else:
                print("   ❌ Get Started not linked to signup")
                
            # Check Request Demo button  
            if 'href="/demo"' in content:
                print("   ✅ Request Demo links to /demo")
            else:
                print("   ❌ Request Demo not linked to demo")
                
            # Check button icons
            if 'fa-user-plus' in content:
                print("   ✅ Get Started has user-plus icon")
            else:
                print("   ❌ Get Started icon not updated")
                
            if 'fa-calendar-check' in content:
                print("   ✅ Request Demo has calendar-check icon")
            else:
                print("   ❌ Request Demo icon not updated")
        else:
            print(f"   ❌ Homepage failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Button test error: {str(e)}")
    
    # Test 4: Check if signup page exists
    print("4. Testing Signup Page...")
    try:
        response = requests.get(f"{base_url}/signup", timeout=5)
        if response.status_code == 200:
            print("   ✅ Signup page accessible")
        else:
            print(f"   ❌ Signup page failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Signup test error: {str(e)}")
    
    # Test 5: Check if demo page exists
    print("5. Testing Demo Page...")
    try:
        response = requests.get(f"{base_url}/demo", timeout=5)
        if response.status_code == 200:
            print("   ✅ Demo page accessible")
        else:
            print(f"   ❌ Demo page failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Demo test error: {str(e)}")
    
    print()
    print("=" * 60)
    print("📊 Current State Analysis:")
    print()
    
    # Overall assessment
    print("Based on the test results:")
    print("1. If padding-top: 120px is present → Layout should be fixed")
    print("2. If buttons link to /signup and /demo → Buttons should be functional")
    print("3. If single col-lg-6 → No dashboard image")
    print("4. If signup and demo pages exist → New pages are working")
    print()
    print("🌐 Test the homepage manually at: http://localhost:5000")

if __name__ == "__main__":
    test_current_homepage()
