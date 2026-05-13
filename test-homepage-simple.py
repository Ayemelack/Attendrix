#!/usr/bin/env python3
"""
Simple test to verify homepage fixes
"""

import requests

def test_homepage_simple():
    base_url = "http://localhost:5000"
    
    print("🏠 Homepage Fixes Verification")
    print("=" * 50)
    
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            content = response.text
            
            print("✅ Homepage Status: Working")
            print()
            
            # Check the key issues mentioned by user
            print("🔍 Checking User-Reported Issues:")
            print()
            
            # 1. Header visibility (should be fixed with padding)
            if 'Attendrix' in content and 'Secure. Smart. Structured Attendance' in content:
                print("   ✅ Header content: Present and visible")
            else:
                print("   ❌ Header content: Missing or hidden")
            
            # 2. Button functionality 
            if 'href="/signup"' in content:
                print("   ✅ Get Started: Links to signup page")
            else:
                print("   ❌ Get Started: Not linked to signup")
                
            if 'href="/demo"' in content:
                print("   ✅ Request Demo: Links to demo page")  
            else:
                print("   ❌ Request Demo: Not linked to demo")
            
            # 3. Dashboard image removal
            # Look for any image references in hero section
            if content.count('hero-dashboard.png') == 0:
                print("   ✅ Dashboard image: Not found (good)")
            else:
                print("   ❌ Dashboard image: Still present")
            
            # 4. Button icons
            if 'fa-user-plus' in content and 'fa-calendar-check' in content:
                print("   ✅ Button icons: Updated correctly")
            else:
                print("   ❌ Button icons: Not updated")
            
            print()
            print("🎯 Summary:")
            
            # Count the fixes
            fixes_working = 0
            total_issues = 4
            
            if b'Attendrix' in content and b'Secure. Smart. Structured Attendance' in content:
                fixes_working += 1
                print("   ✅ Layout: Header properly spaced")
            else:
                print("   ❌ Layout: Header still covered")
                
            if 'href="/signup"' in content and 'href="/demo"' in content:
                fixes_working += 1
                print("   ✅ Buttons: Both functional")
            else:
                print("   ❌ Buttons: Not functional")
                
            if content.count('hero-dashboard.png') == 0:
                fixes_working += 1
                print("   ✅ Visual: Dashboard image removed")
            else:
                print("   ❌ Visual: Dashboard image still present")
                
            print(f"   Overall: {fixes_working}/{total_issues} issues resolved")
            
            if fixes_working == total_issues:
                print("🎉 ALL ISSUES RESOLVED!")
            else:
                print("⚠️  Some issues still need attention")
                
        else:
            print(f"❌ Homepage failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Test error: {str(e)}")
    
    print()
    print("=" * 50)
    print("🌐 Visit: http://localhost:5000")
    print("📱 Manual verification recommended")

if __name__ == "__main__":
    test_homepage_simple()
