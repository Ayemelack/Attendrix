#!/usr/bin/env python3
import os
import sys

# Add the parent directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app

def test_template_rendering():
    print("TESTING TEMPLATE RENDERING")
    print("=" * 50)
    
    with app.app_context():
        # Test the admin/users template
        template_path = os.path.join(app.template_folder, 'admin', 'users.html')
        print(f"Template path: {template_path}")
        print(f"Template exists: {os.path.exists(template_path)}")
        
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                content = f.read()
                print(f"Template file size: {len(content)} characters")
                print(f"Contains showAddUserModal: {'YES' if 'showAddUserModal' in content else 'NO'}")
                print(f"Contains modal fade: {'YES' if 'modal fade' in content else 'NO'}")
                
                # Check for key functional indicators
                functional_indicators = [
                    'showAddUserModal',
                    'exportUsers',
                    'modal fade',
                    'Add New User',
                    'CSV content'
                ]
                
                print("\nFunctional indicators found:")
                for indicator in functional_indicators:
                    found = indicator in content
                    print(f"  {indicator}: {'YES' if found else 'NO'}")
        
        # Test actual rendering
        print("\nTesting Flask rendering...")
        try:
            # Simulate a request context
            with app.test_request_context():
                from flask import render_template
                rendered = render_template('admin/users.html')
                print(f"Rendered content size: {len(rendered)} characters")
                print(f"Rendered contains showAddUserModal: {'YES' if 'showAddUserModal' in rendered else 'NO'}")
                print(f"Rendered contains modal fade: {'YES' if 'modal fade' in rendered else 'NO'}")
                
                # Check if the rendered content matches the file content
                if os.path.exists(template_path):
                    with open(template_path, 'r') as f:
                        file_content = f.read()
                        if file_content == rendered:
                            print("SUCCESS: Rendered content matches file content")
                        else:
                            print("ISSUE: Rendered content differs from file content")
                            print(f"File content length: {len(file_content)}")
                            print(f"Rendered content length: {len(rendered)}")
                            
                            # Find first difference
                            for i, (file_char, rendered_char) in enumerate(zip(file_content, rendered)):
                                if file_char != rendered_char:
                                    print(f"First difference at position {i}")
                                    print(f"File: '{file_char}'")
                                    print(f"Rendered: '{rendered_char}'")
                                    break
        except Exception as e:
            print(f"ERROR during rendering: {e}")

if __name__ == '__main__':
    test_template_rendering()
