#!/usr/bin/env python3
"""
Simple HTTP Server for Attendrix Phase 1 Landing Page
"""

import http.server
import socketserver
import os
import sys

# Set the port
PORT = 8000

# Change to the correct directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def log_message(self, format, *args):
        # Suppress log messages for cleaner output
        pass

try:
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        print(f"🚀 Attendrix Server Started")
        print(f"📱 Local Access: http://localhost:{PORT}/phase1_landing.html")
        print(f"🌐 Network Access: http://127.0.0.1:{PORT}/phase1_landing.html")
        print(f"⏹️  Press Ctrl+C to stop the server")
        print("-" * 50)
        httpd.serve_forever()

except KeyboardInterrupt:
    print("\n⏹️  Server stopped by user")
    sys.exit(0)
except Exception as e:
    print(f"❌ Error starting server: {e}")
    sys.exit(1)
