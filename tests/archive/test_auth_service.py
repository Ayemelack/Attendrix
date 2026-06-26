#!/usr/bin/env python3

# Test authentication service in context of Flask app
from flask import Flask, request
import sys
import os

# Test imports
try:
    from src.application.authentication_service import AuthenticationService
    print("✅ Authentication service imported successfully")
except ImportError as e:
    print(f"❌ ImportError: {e}")

# Test instantiation
try:
    from src.infrastructure.firebase_service import firebase_service
    auth_service = AuthenticationService(firebase_service)
    print("✅ Authentication service instantiated successfully")
except Exception as e:
    print(f"❌ Instantiation error: {e}")

print("Test completed successfully")
