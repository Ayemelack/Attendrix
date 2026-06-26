#!/usr/bin/env python3

# Minimal test to isolate authentication service issue
try:
    # Test basic imports
    import sys
    sys.path.append('.')
    
    print("Testing imports...")
    
    # Test domain entities
    from src.domain.entities import User, UserRole
    print("✅ User import successful")
    
    # Test authentication service
    from src.application.authentication_service import AuthenticationService
    print("✅ Authentication service imported successfully")
    
    print("✅ All imports working correctly")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("Test completed")
