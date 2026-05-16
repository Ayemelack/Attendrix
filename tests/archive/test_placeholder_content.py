import requests
import re

def test_functional_content():
    print("TESTING FOR PLACEHOLDER CONTENT")
    print("=" * 60)
    
    base_url = "http://localhost:5000"
    
    # Define placeholder patterns to check for
    placeholder_patterns = [
        "This feature will be implemented here",
        "Full [feature] will be implemented here", 
        "coming soon",
        "placeholder",
        "This is a placeholder page",
        "will contain comprehensive",
        "This page will contain"
    ]
    
    # Define functional content indicators
    functional_indicators = [
        "No Security Events Yet",
        "No Backups Available Yet", 
        "No Notifications Yet",
        "No Audit Logs Yet",
        "No Role Assignments Yet",
        "No Monitoring Data Yet",
        "Security Dashboard",
        "Backup Dashboard",
        "Notifications Dashboard",
        "Audit Logs Dashboard",
        "Role Assignments Dashboard",
        "System Monitoring"
    ]
    
    pages_to_test = [
        ('Security', '/admin/security'),
        ('Backup', '/admin/backup'),
        ('Notifications', '/admin/notifications'),
        ('Audit Logs', '/admin/audit'),
        ('Role Assignments', '/admin/roles'),
        ('Monitoring', '/admin/monitoring'),
        ('Users', '/admin/users'),
        ('Profile', '/admin/profile'),
        ('Settings', '/admin/settings'),
        ('Reports', '/admin/reports'),
    ]
    
    results = []
    
    for page_name, page_url in pages_to_test:
        try:
            response = requests.get(f"{base_url}{page_url}", timeout=5)
            if response.status_code == 200:
                content = response.text.lower()
                
                # Check for placeholder content
                found_placeholders = []
                for pattern in placeholder_patterns:
                    if pattern.lower() in content:
                        found_placeholders.append(pattern)
                
                # Check for functional indicators
                found_functional = []
                for indicator in functional_indicators:
                    if indicator.lower() in content:
                        found_functional.append(indicator)
                
                # Determine status
                if found_placeholders:
                    status = "❌ CONTAINS PLACEHOLDERS"
                    details = f"Found: {', '.join(found_placeholders)}"
                elif found_functional:
                    status = "✅ FUNCTIONAL CONTENT"
                    details = f"Found: {found_functional[0]}"
                else:
                    status = "⚠️ UNCLEAR"
                    details = "No clear indicators found"
                
                results.append((page_name, status, details, page_url))
                print(f"{page_name:<20} {status}")
                
            else:
                results.append((page_name, f"❌ ERROR ({response.status_code})", "", page_url))
                print(f"{page_name:<20} ❌ ERROR ({response.status_code})")
                
        except Exception as e:
            results.append((page_name, "❌ FAILED", str(e), page_url))
            print(f"{page_name:<20} ❌ FAILED")
    
    # Summary
    print("\n" + "=" * 60)
    print("DETAILED ANALYSIS:")
    
    functional_count = sum(1 for _, status, _, _ in results if "✅" in status)
    placeholder_count = sum(1 for _, status, _, _ in results if "❌ CONTAINS PLACEHOLDERS" in status)
    total = len(results)
    
    print(f"Functional Pages: {functional_count}/{total}")
    print(f"Placeholder Pages: {placeholder_count}/{total}")
    
    if placeholder_count > 0:
        print("\n⚠️ PAGES WITH PLACEHOLDER CONTENT:")
        for page_name, status, details, url in results:
            if "❌ CONTAINS PLACEHOLDERS" in status:
                print(f"  • {page_name}: {details}")
    
    if functional_count == total:
        print("\n🎉 ALL PAGES ARE FUNCTIONAL!")
        print("✅ No placeholder content found")
        print("✅ All pages show proper functional content")
    else:
        print(f"\n⚠️ {placeholder_count} pages still contain placeholder content")
    
    print("=" * 60)

if __name__ == "__main__":
    test_functional_content()
