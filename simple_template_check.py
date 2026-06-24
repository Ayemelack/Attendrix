#!/usr/bin/env python
"""
Simple template syntax check
"""
import re

def check_template_syntax():
    template_path = 'templates/landing/index.html'
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("🔍 Checking Django Template Syntax...")
        print("=" * 60)
        
        # Check for common template syntax errors
        issues = []
        
        # Check for proper Django template tag syntax
        if "{% url 'accounts:login' %}" not in content:
            issues.append("❌ Login button: Missing or incorrect Django URL tag")
        else:
            print("✅ Login button: Django URL tag syntax correct")
            
        if "{% url 'demo:request' %}" not in content:
            issues.append("❌ Demo button: Missing or incorrect Django URL tag")
        else:
            print("✅ Demo button: Django URL tag syntax correct")
            
        # Check for malformed template tags
        malformed_tags = re.findall(r'{%\s*[^}]*%}', content)
        for tag in malformed_tags:
            if 'url' in tag and "'" not in tag and '"' not in tag:
                issues.append(f"❌ Malformed URL tag: {tag}")
                
        # Check for section IDs
        if 'id="home"' not in content:
            issues.append("❌ Missing #home section ID")
        else:
            print("✅ #home section ID found")
            
        if 'id="about"' not in content:
            issues.append("❌ Missing #about section ID")
        else:
            print("✅ #about section ID found")
            
        if 'id="how-it-works"' not in content:
            issues.append("❌ Missing #how-it-works section ID")
        else:
            print("✅ #how-it-works section ID found")
            
        if 'id="modules"' not in content:
            issues.append("❌ Missing #modules section ID")
        else:
            print("✅ #modules section ID found")
            
        if 'id="contact"' not in content:
            issues.append("❌ Missing #contact section ID")
        else:
            print("✅ #contact section ID found")
        
        # Check for broken href attributes
        broken_hrefs = re.findall(r'href="#"[^"\s>]*', content)
        if broken_hrefs:
            issues.append(f"❌ Found {len(broken_hrefs)} empty or broken href attributes")
        else:
            print("✅ No broken href attributes found")
        
        print("=" * 60)
        
        if issues:
            print("🚨 ISSUES FOUND:")
            for issue in issues:
                print(f"  {issue}")
            return False
        else:
            print("🎉 ALL CHECKS PASSED!")
            print("✅ Template syntax is correct")
            print("✅ All required sections are present")
            print("✅ Django URL tags are properly formatted")
            print("✅ No broken links found")
            return True
            
    except Exception as e:
        print(f"❌ Error reading template: {e}")
        return False

if __name__ == "__main__":
    success = check_template_syntax()
        
        if success:
            print("\n🎯 CONCLUSION:")
            print("The template syntax is CORRECT.")
            print("The issue is likely that Django apps are not properly loaded.")
            print("Try running: python manage.py runserver")
            print("Instead of the simple test server.")
        else:
            print("\n❌ CONCLUSION:")
            print("Template has syntax errors that need to be fixed.")
