import re

file_path = "c:\\Users\\noshi\\OneDrive\\fotsa\\Achieved\\attendrix\\app.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

new_routes = """
    @app.route('/api/super-admin/vouchers', methods=['GET', 'POST'])
    @require_auth
    @require_role('super_admin')
    @log_access
    def super_admin_vouchers():
        from src.application.super_admin_service import super_admin_service
        try:
            if request.method == 'GET':
                data = super_admin_service.get_vouchers()
                return jsonify({'success': True, 'data': data}), 200
            else:
                data = request.get_json()
                result = super_admin_service.create_voucher(data)
                return jsonify(result), 200
        except Exception as e:
            logger.error(f"Super admin vouchers error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/super-admin/vouchers/<voucher_id>/revoke', methods=['POST'])
    @require_auth
    @require_role('super_admin')
    @log_access
    def super_admin_revoke_voucher(voucher_id):
        from src.application.super_admin_service import super_admin_service
        try:
            success = super_admin_service.revoke_voucher(voucher_id)
            if success:
                return jsonify({'success': True}), 200
            return jsonify({'success': False, 'error': 'Voucher not found'}), 404
        except Exception as e:
            logger.error(f"Super admin revoke voucher error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/super-admin/connected-devices', methods=['GET'])
    @require_auth
    @require_role('super_admin')
    @log_access
    def super_admin_connected_devices():
        from src.application.super_admin_service import super_admin_service
        try:
            data = super_admin_service.get_connected_devices()
            return jsonify({'success': True, 'data': data}), 200
        except Exception as e:
            logger.error(f"Super admin connected devices error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/super-admin/events/stream')
    @require_auth
    @require_role('super_admin')
    def super_admin_events_stream():
        from flask import Response
        import queue
        from src.infrastructure.mqtt_service import mqtt_service
        
        def event_stream():
            q = queue.Queue()
            
            def mqtt_callback(topic, payload):
                import json
                try:
                    q.put(json.dumps({'topic': topic, 'data': payload}))
                except:
                    pass
                    
            mqtt_service.initialize()
            mqtt_service.subscribe('attendrix/attendance/#', mqtt_callback)
            mqtt_service.subscribe('attendrix/security/#', mqtt_callback)
            
            try:
                # Send initial connection event
                yield "data: {\\\"status\\\": \\\"connected\\\"}\\n\\n"
                
                while True:
                    try:
                        msg = q.get(timeout=20)
                        yield f"data: {msg}\\n\\n"
                    except queue.Empty:
                        yield ": keepalive\\n\\n"
            finally:
                pass
                
        return Response(event_stream(), mimetype='text/event-stream')

    # ── Existing admin routes ──"""

content = content.replace("    # ── Existing admin routes ──", new_routes)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated app.py")
