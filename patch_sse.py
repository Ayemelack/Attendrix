import re

file_path = "c:\\Users\\noshi\\OneDrive\\fotsa\\Achieved\\attendrix\\app.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the previous SSE endpoint with one that handles token from args
old_stream = """    @app.route('/api/super-admin/events/stream')
    @require_auth
    @require_role('super_admin')
    def super_admin_events_stream():"""

new_stream = """    @app.route('/api/super-admin/events/stream')
    def super_admin_events_stream():
        # EventSource does not support custom headers, so we authenticate via query parameter
        token = request.args.get('token')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
            
        # Verify token
        from src.application.auth_service import auth_service
        try:
            payload = auth_service.verify_token(token)
            if not payload or payload.get('role') != 'super_admin':
                return jsonify({'error': 'Forbidden'}), 403
        except Exception as e:
            return jsonify({'error': 'Invalid token'}), 401"""

content = content.replace(old_stream, new_stream)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed SSE endpoint in app.py")
