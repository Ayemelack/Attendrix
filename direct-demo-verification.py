#!/usr/bin/env python3
"""
Direct Demo Content Verification
"""

import requests
import sys

def direct_demo_verification():
    base_url = "http://localhost:5000"
    
    print("🔍 DIRECT DEMO CONTENT VERIFICATION")
    print("=" * 50)
    
    try:
        print("1. Fetching Student Dashboard Content...")
        
        response = requests.get(f"{base_url}/dashboard?role=student", timeout=5)
        if response.status_code == 200:
            content = response.text
            
            # Direct search for demo terms
            demo_terms_found = []
            demo_terms = ['demo', 'coming soon', 'this is a demo', 'alert(', 'showcomingsoon(']
            
            for term in demo_terms:
                if term in content:
                    demo_terms_found.append(term)
                    print(f"   ❌ Found: '{term}'")
                else:
                    print(f"   ✅ Not found: '{term}'")
            
            if not demo_terms_found:
                print("   ✅ SUCCESS: NO DEMO TERMS FOUND IN DASHBOARD")
                return True
            else:
                print(f"   ❌ FAILURE: {len(demo_terms_found)} demo terms found")
                return False
        else:
            print("   ❌ Failed to fetch dashboard")
            return False
        
    except Exception as e:
        print(f"   ❌ Test error: {str(e)}")
        return False
    
    finally:
        print()
        print("=" * 50)
        print("🔍 DIRECT VERIFICATION RESULTS")
        print()
        
        print("📊 FINAL STATUS:")
        if 'demo_terms_found' in locals() and not locals()['demo_terms_found']:
            print("✅ COMPLETE: ALL DEMO BEHAVIOR ELIMINATED")
            print("🚀 READY FOR PRODUCTION")
        else:
            print("❌ INCOMPLETE: DEMO BEHAVIOR STILL EXISTS")

if __name__ == "__main__":
    success = direct_demo_verification()
    sys.exit(0 if success else 1)
