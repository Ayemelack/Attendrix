#!/usr/bin/env python3
"""
Startup script for new Attendrix backend
"""

import subprocess
import sys
import os

def main():
    print("🚀 STARTING ATTENDRIX NEW BACKEND")
    print("=" * 50)
    
    # Check if Flask is installed
    try:
        import flask
        print("✅ Flask is available")
    except ImportError:
        print("❌ Flask not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
        print("✅ Flask installed")
    
    # Start the new backend
    try:
        print("🌐 Starting new backend on port 5000...")
        print("📊 Demo endpoint: http://localhost:5000/submit-demo")
        print("🔍 Health check: http://localhost:5000/health")
        print("=" * 50)
        
        # Change to backend directory and run
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        subprocess.run([sys.executable, "attendrix_backend_new.py"])
        
    except Exception as e:
        print(f"❌ Error starting backend: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
