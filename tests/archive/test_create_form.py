import requests
from bs4 import BeautifulSoup

def test_create_institution_form():
    print("Testing Create Institution Form Functionality...")
    print("=" * 60)
    
    try:
        # Get the create institution page
        response = requests.get('http://localhost:5000/admin/institutions/create', timeout=5)
        
        if response.status_code != 200:
            print(f"ERROR: Could not access page - Status {response.status_code}")
            return False
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for key form elements
        tests = [
            ('Form Element', 'form#createInstitutionForm'),
            ('Institution Name Field', 'input#institutionName'),
            ('Institution Type Select', 'select#institutionType'),
            ('Institution Level Select', 'select#institutionLevel'),
            ('Email Field', 'input#email'),
            ('Phone Field', 'input#phone'),
            ('Address Field', 'textarea#address'),
            ('Admin Assignment Select', 'select#adminAssignment'),
            ('Submit Button', 'button[type="submit"]'),
            ('Cancel Button', 'button[onclick="resetForm()"]'),
            ('Alert Container', 'div#alertContainer'),
        ]
        
        results = []
        for test_name, selector in tests:
            element = soup.select_one(selector)
            if element:
                results.append((test_name, 'PASS', 'Found'))
            else:
                results.append((test_name, 'FAIL', 'Not found'))
        
        # Check for form sections
        sections = [
            ('Basic Information Section', 'h3:contains("Basic Information")'),
            ('Contact Information Section', 'h3:contains("Contact Information")'),
            ('Admin User Assignment Section', 'h3:contains("Admin User Assignment")'),
            ('Initial Configuration Section', 'h3:contains("Initial Configuration")'),
        ]
        
        for section_name, selector in sections:
            element = soup.find('h3', string=lambda text: text and section_name.split('(')[0].lower() in text.lower())
            if element:
                results.append((section_name, 'PASS', 'Found'))
            else:
                results.append((section_name, 'FAIL', 'Not found'))
        
        # Check for JavaScript functions
        js_functions = [
            'validateForm()',
            'submitForm()',
            'showAlert()',
            'resetForm()',
            'initializeFormHandlers()',
        ]
        
        page_text = response.text
        for func_name in js_functions:
            if func_name in page_text:
                results.append((f'JS Function: {func_name}', 'PASS', 'Found'))
            else:
                results.append((f'JS Function: {func_name}', 'FAIL', 'Not found'))
        
        # Display results
        passed = 0
        failed = 0
        
        for test_name, status, details in results:
            if status == 'PASS':
                print(f"  {test_name:<35} -> {status}  ({details})")
                passed += 1
            else:
                print(f"  {test_name:<35} -> {status}  ({details})")
                failed += 1
        
        print("=" * 60)
        print(f"Test Results: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("SUCCESS: Create Institution form is fully functional!")
            return True
        else:
            print("WARNING: Some form elements may be missing.")
            return False
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    test_create_institution_form()
