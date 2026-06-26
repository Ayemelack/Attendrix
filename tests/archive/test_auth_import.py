#!/usr/bin/env python3

# Test authentication service import
try:
    from src.application.authentication_service import AuthenticationService
    print("✅ Authentication service imported successfully")
except ImportError as e:
    print(f"❌ ImportError: {e}")
except Exception as e:
    print(f"❌ Other error: {e}")

# Test instantiation
try:
    from src.infrastructure.firebase_service import firebase_service
    auth_service = AuthenticationService(firebase_service)
    print("✅ Authentication service instantiated successfully")
except Exception as e:
    print(f"❌ Instantiation error: {e}")
