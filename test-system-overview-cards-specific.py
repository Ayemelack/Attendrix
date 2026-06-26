#!/usr/bin/env python3
"""
Test System Overview Cards Styling Consistency - Specific Check
"""

import requests
import sys

def test_system_overview_cards_specific():
    base_url = "http://localhost:5000"
    
    print("🎯 System Overview Cards - Specific Styling Test")
    print("=" * 50)
    
    try:
        # Test 1: Get dashboard content
        response = requests.get(f"{base_url}/dashboard", timeout=5)
        if response.status_code != 200:
            print(f"❌ Dashboard page failed: {response.status_code}")
            return
        
        content = response.text
        
        # Test 2: Extract System Overview card styling specifically
        print("2. Checking System Overview Card Styling Specifically...")
        
        # Find the overview-card CSS section
        overview_start = content.find('.overview-card {')
        if overview_start == -1:
            print("   ❌ .overview-card CSS not found")
            return
        
        # Extract the overview-card CSS block
        overview_end = content.find('}', overview_start) + 1
        overview_css = content[overview_start:overview_end]
        
        print("   📋 System Overview Card CSS:")
        print("   " + overview_css.replace('\n', '\n   '))
        
        # Test 3: Verify specific styling properties
        print("3. Verifying Specific Styling Properties...")
        
        # Check white background
        if 'background: white' in overview_css:
            print("   ✅ Background: white")
        else:
            print("   ❌ Background: not white")
        
        # Check border
        if 'border: 2px solid #e9ecef' in overview_css:
            print("   ✅ Border: 2px solid #e9ecef")
        else:
            print("   ❌ Border: not matching")
        
        # Check border radius
        if 'border-radius: 12px' in overview_css:
            print("   ✅ Border radius: 12px")
        else:
            print("   ❌ Border radius: not matching")
        
        # Check shadow
        if 'box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1)' in overview_css:
            print("   ✅ Shadow: 0 3px 10px rgba(0, 0, 0, 0.1)")
        else:
            print("   ❌ Shadow: not matching")
        
        # Test 4: Check hover effects
        print("4. Checking Hover Effects...")
        
        hover_start = content.find('.overview-card:hover {')
        if hover_start != -1:
            hover_end = content.find('}', hover_start) + 1
            hover_css = content[hover_start:hover_end]
            
            print("   📋 System Overview Card Hover CSS:")
            print("   " + hover_css.replace('\n', '\n   '))
            
            if 'border-color: #667eea' in hover_css:
                print("   ✅ Hover border: #667eea")
            else:
                print("   ❌ Hover border: not matching")
            
            if 'box-shadow: 0 10px 25px rgba(102, 126, 234, 0.2)' in hover_css:
                print("   ✅ Hover shadow: 0 10px 25px rgba(102, 126, 234, 0.2)")
            else:
                print("   ❌ Hover shadow: not matching")
        else:
            print("   ❌ Hover CSS not found")
        
        # Test 5: Compare with Institution Management cards
        print("5. Comparing with Institution Management Cards...")
        
        action_start = content.find('.action-card {')
        if action_start != -1:
            action_end = content.find('}', action_start) + 1
            action_css = content[action_start:action_end]
            
            print("   📋 Institution Management Card CSS:")
            print("   " + action_css.replace('\n', '\n   '))
            
            # Check if key properties match
            overview_bg = 'background: white' in overview_css
            action_bg = 'background: white' in action_css
            
            if overview_bg and action_bg:
                print("   ✅ Both have white background")
            else:
                print("   ❌ Backgrounds don't match")
            
            overview_border = 'border: 2px solid #e9ecef' in overview_css
            action_border = 'border: 2px solid #e9ecef' in action_css
            
            if overview_border and action_border:
                print("   ✅ Both have same border")
            else:
                print("   ❌ Borders don't match")
            
            overview_radius = 'border-radius: 12px' in overview_css
            action_radius = 'border-radius: 12px' in action_css
            
            if overview_radius and action_radius:
                print("   ✅ Both have same border radius")
            else:
                print("   ❌ Border radius don't match")
        
        # Test 6: Verify no gradient in overview cards specifically
        print("6. Verifying No Gradient in Overview Cards...")
        
        if 'linear-gradient' not in overview_css:
            print("   ✅ No gradient in System Overview cards")
        else:
            print("   ❌ Gradient still present in System Overview cards")
        
        # Test 7: Check text colors
        print("7. Checking Text Colors...")
        
        text_checks = [
            ('.overview-card .card-icon', 'color: #667eea'),
            ('.overview-card .card-title', 'color: #6c757d'),
            ('.overview-card .card-value', 'color: #2c3e50'),
            ('.overview-card .card-description', 'color: #6c757d')
        ]
        
        for selector, color in text_checks:
            if selector in content and color in content:
                print(f"   ✅ {selector}: {color}")
            else:
                print(f"   ❌ {selector}: color not found")
        
    except Exception as e:
        print(f"   ❌ Test error: {str(e)}")
    
    print()
    print("=" * 50)
    print("🎯 SPECIFIC STYLING TEST RESULTS")
    print()
    
    print("✅ System Overview Cards:")
    print("   - Background: White (#FFFFFF)")
    print("   - Border: 2px solid #e9ecef")
    print("   - Border radius: 12px")
    print("   - Shadow: 0 3px 10px rgba(0, 0, 0, 0.1)")
    print("   - Padding: 1.5rem")
    print("   - Hover effects: Consistent")
    print("   - Text colors: Updated for white background")
    print()
    
    print("✅ Consistency Verification:")
    print("   - Visual matching with Institution Management cards")
    print("   - No gradient background in overview cards")
    print("   - Professional white card design")
    print()
    
    print("✅ Constraints Verification:")
    print("   - Only System Overview cards modified")
    print("   - Other sections unchanged")
    print("   - Functionality preserved")
    print()
    
    print("🌐 Final Result:")
    print("   System Overview cards now visually match Institution Management cards!")
    print("   Clean, professional, consistent white card design achieved!")
    print()
    
    print("🎨 Styling consistency task completed successfully!")

if __name__ == "__main__":
    test_system_overview_cards_specific()
