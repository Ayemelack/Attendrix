import sys, json
sys.path.insert(0, '.')
from src.infrastructure.firebase_service import FirebaseService

fb = FirebaseService()
# Try to get all user documents by prefix scan
users = []
try:
    # FirebaseService only has get_document, but the repo might use internal methods
    # Let's check what's available
    methods = [m for m in dir(fb) if not m.startswith('_')]
    print("FirebaseService methods:", methods)
except Exception as e:
    print("Error:", e)

from src.infrastructure import repositories
repo_methods = [m for m in dir(repositories.user_repo) if not m.startswith('_')]
print("\nuser_repo methods:", repo_methods)
