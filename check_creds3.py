import sys, json
sys.path.insert(0, '.')
from src.infrastructure.repositories import user_repo
from src.infrastructure.firebase_service import FirebaseService

fb = FirebaseService()

# Get all users
users = user_repo.list_all()
print(f"\n=== USERS ({len(users)} found) ===")
for u in users:
    print(json.dumps(u, indent=2))
    print("---")

# Try to get vouchers via query
try:
    vouchers = fb.query_documents('vouchers', [])
    print(f"\n=== VOUCHERS ({len(vouchers)} found) ===")
    for v in vouchers:
        print(json.dumps(v, indent=2))
        print("---")
except Exception as e:
    print(f"\nVouchers query failed: {e}")
    try:
        # Try collection directly
        docs = fb.firestore_client.collection('vouchers').stream()
        vouchers = [d.to_dict() for d in docs]
        print(f"\n=== VOUCHERS via firestore ({len(vouchers)} found) ===")
        for v in vouchers:
            print(json.dumps(v, indent=2))
            print("---")
    except Exception as e2:
        print(f"Firestore direct also failed: {e2}")
