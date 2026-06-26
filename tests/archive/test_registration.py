import requests
import json

# Test registration API
url = "http://localhost:5000/api/auth/signup"
data = {
    "first_name": "Test",
    "last_name": "User", 
    "email": "test@example.com",
    "password": "password123",
    "role": "institutional_admin",
    "institution_id": "test123"
}

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
