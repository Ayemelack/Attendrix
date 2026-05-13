#!/usr/bin/env python3
"""
Simple Navigation Test - Verify All Links Work
"""

import requests
import sys

def simple_navigation_test():
    base_url = "http://localhost:5000"
    
    print("🔧 SIMPLE NAVIGATION TEST")
    print("=" * 50)
    
    try:
        # Test all navigation links
        navigation_links = [
            ("/lecturer-dashboard", "Main Dashboard"),
            ("/lecturer/courses", "My Courses"),
            ("/lecturer/attendance", "Mark Attendance"),
            ("/lecturer/schedule", "My Schedule"),
            ("/lecturer/analytics", "Analytics"),
            ("/lecturer/communication", "Communication")
        ]
        
        all_working = True
        
        for route, description in navigation_links:
            try:
                response = requests.get(f"{base_url}{route}", timeout=5)
                if response.status_code == 200:
                    print(f"   ✅ {description}: Working ({response.status_code})")
                else:
                    print(f"   ❌ {description}: Failed ({response.status_code})")
                    all_working = False
            except Exception as e:
                print(f"   ❌ {description}: Error - {str(e)}")
                all_working = False
        
        print()
        print("=" * 50)
        print("🔧 NAVIGATION TEST RESULTS")
        print()
        
        if all_working:
            print("🎉 SUCCESS: All navigation links are working!")
            print()
            print("✅ Fixed Navigation Links:")
            for route, description in navigation_links[1:]:
                print(f"   ✓ {description} → {route} ✅")
            print()
            print("✅ No 'Resource Not Found' errors")
            print("✅ All pages load correctly")
            print("✅ Backend-Frontend alignment perfect")
            print()
            print("🚀 Lateral dashboard navigation is fully functional!")
        else:
            print("❌ FAILURE: Some navigation links are not working")
            print("Please check the routes and page templates")
        
        return all_working
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = simple_navigation_test()
    sys.exit(0 if success else 1)
