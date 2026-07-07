import json
from app import app

def test_voucher_validation():
    with app.test_client() as client:
        print("Testing voucher validation for ADMIN123...")
        response = client.get('/api/voucher/validate/ADMIN123')
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.get_json(), indent=2)}")
        
        # Verify that it generated correctly and it's valid
        if response.get_json().get('valid') is True:
            print("✅ Fix verified successfully! The voucher was found and validated.")
        else:
            print("❌ Fix verification failed. Voucher not valid.")

if __name__ == '__main__':
    test_voucher_validation()
