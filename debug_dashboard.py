import requests
import sys

def test_admin_dashboard_debug():
    try:
        response = requests.get('http://localhost:5000/admin/dashboard', timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 500:
            print("Error details:")
            print(response.text[:500])  # First 500 characters of error
        else:
            print("Success!")
            print("Content preview:", response.text[:200])
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_admin_dashboard_debug()
