#!/usr/bin/env python3
import os
import sys

# Add the parent directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_template_issue():
    print("DEBUGGING TEMPLATE ISSUE")
    print("=" * 50)
    
    # Check the actual file content
    template_path = "src/presentation/templates/admin/users.html"
    
    print(f"Template path: {template_path}")
    print(f"Template exists: {os.path.exists(template_path)}")
    
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        print(f"File size: {len(file_content)} characters")
        
        # Look for showAddUserModal function
        start_idx = file_content.find("function showAddUserModal()")
        if start_idx != -1:
            end_idx = file_content.find("function", start_idx + 1)
            if end_idx == -1:
                end_idx = len(file_content)
            
            function_content = file_content[start_idx:start_idx + 500]
            print("First 500 chars of showAddUserModal in file:")
            print(function_content)
            
            if "alert(" in function_content:
                print("ISSUE: File contains alert() placeholder!")
            elif "modal fade" in function_content:
                print("SUCCESS: File contains modal HTML!")
            else:
                print("UNCLEAR: Neither alert nor modal found")
        else:
            print("Function not found in file")
    
    # Now check what Flask is actually serving
    print("\n" + "=" * 50)
    print("CHECKING WHAT FLASK SERVES")
    
    try:
        from app import app
        
        with app.test_request_context():
            from flask import render_template
            rendered = render_template('admin/users.html')
            
            print(f"Rendered content size: {len(rendered)} characters")
            
            # Look for showAddUserModal function in rendered content
            start_idx = rendered.find("function showAddUserModal()")
            if start_idx != -1:
                end_idx = rendered.find("function", start_idx + 1)
                if end_idx == -1:
                    end_idx = len(rendered)
                
                function_content = rendered[start_idx:start_idx + 500]
                print("First 500 chars of showAddUserModal in rendered:")
                print(function_content)
                
                if "alert(" in function_content:
                    print("ISSUE: Rendered content contains alert() placeholder!")
                elif "modal fade" in function_content:
                    print("SUCCESS: Rendered content contains modal HTML!")
                else:
                    print("UNCLEAR: Neither alert nor modal found")
            else:
                print("Function not found in rendered content")
                
            # Check if file content matches rendered content
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                
                if file_content == rendered:
                    print("SUCCESS: Rendered content matches file content")
                else:
                    print("ISSUE: Rendered content differs from file content")
                    
                    # Find first difference
                    min_len = min(len(file_content), len(rendered))
                    for i in range(min_len):
                        if file_content[i] != rendered[i]:
                            print(f"First difference at position {i}")
                            print(f"File: '{file_content[i]}'")
                            print(f"Rendered: '{rendered[i]}'")
                            break
                    
                    if len(file_content) != len(rendered):
                        print(f"Length difference: File={len(file_content)}, Rendered={len(rendered)}")
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    debug_template_issue()
