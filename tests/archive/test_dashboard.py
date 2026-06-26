import requests
import sys

def test_admin_dashboard():
    try:
        # Test main admin dashboard route
        response = requests.get('http://localhost:5000/admin/dashboard', timeout=5)
        print(f"Dashboard Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("SUCCESS: Super Admin Dashboard is accessible!")
            print("Content length:", len(response.text))
            
            # Check for key dashboard elements
            if "Super Admin Dashboard" in response.text:
                print("SUCCESS: Dashboard title found!")
            if "sidebar" in response.text.lower():
                print("SUCCESS: Sidebar navigation found!")
            if "attendrix" in response.text.lower():
                print("SUCCESS: Attendrix branding found!")
                
        else:
            print(f"ISSUE: Dashboard returned status code {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to server. Make sure it's running on localhost:5000")
        return False
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    print("Testing Super Admin Dashboard...")
    print("=" * 50)
    success = test_admin_dashboard()
    print("=" * 50)
    if success:
        print("Dashboard test completed successfully!")
    else:
        print("Dashboard test failed!")
        sys.exit(1)
