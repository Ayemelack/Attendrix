from flask import Blueprint, request, jsonify, render_template, Response
from src.application.rbac import require_auth, require_role
from src.application.feedback_service import FeedbackService
from functools import wraps
import json, csv, io, logging

logger = logging.getLogger(__name__)
feedback_api = Blueprint('feedback_api', __name__)
feedback_service = FeedbackService()


def block_institutional_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if hasattr(request, 'current_user') and request.current_user.get('role') == 'institutional_admin':
            logger.warning("Blocked institutional_admin from feedback route: %s", request.path)
            return jsonify({'error': 'Access denied. Institutional administrators cannot access the feedback system.'}), 403
        return f(*args, **kwargs)
    return decorated

# ─── PUBLIC FEED PAGES ───

@feedback_api.route('/feedback')
def feedback_feed_page():
    return render_template('feedback-feed.html')

@feedback_api.route('/feedback/submit')
@require_auth
def feedback_submit_page():
    return render_template('feedback-submit.html')

# ─── PUBLIC FEED API ───

@feedback_api.route('/api/feedback/feed')
def public_feed():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    filters = {
        'category': request.args.get('category'),
        'severity': request.args.get('severity'),
        'search': request.args.get('search'),
        'sort': request.args.get('sort', 'latest'),
        'unresolved_only': request.args.get('unresolved_only') == 'true',
    }
    filters = {k: v for k, v in filters.items() if v}
    result = feedback_service.get_public_feed(page, per_page, filters)
    return jsonify(result), (200 if result.get('success') else 500)

@feedback_api.route('/api/feedback/<feedback_id>')
def feedback_detail(feedback_id):
    result = feedback_service.get_feedback_detail(feedback_id)
    return jsonify(result), (200 if result.get('success') else 404)

@feedback_api.route('/api/feedback', methods=['POST'])
@require_auth
def create_feedback():
    user = request.current_user
    data = request.get_json(silent=True) or {}
    result = feedback_service.create_feedback(
        user_id=user.get('id'),
        user_role=user.get('role', 'student'),
        data=data
    )
    return jsonify(result), (201 if result.get('success') else 400)

@feedback_api.route('/api/feedback/<feedback_id>/upvote', methods=['POST'])
@require_auth
def upvote_feedback(feedback_id):
    user_id = request.current_user.get('id')
    result = feedback_service.upvote_feedback(feedback_id, user_id)
    return jsonify(result), (200 if result.get('success') else 400)

@feedback_api.route('/api/feedback/<feedback_id>/reply', methods=['POST'])
@require_auth
def reply_feedback(feedback_id):
    user = request.current_user
    data = request.get_json(silent=True) or {}
    result = feedback_service.add_reply(
        feedback_id, user.get('id'), user.get('role', 'student'),
        data.get('body', ''), is_admin=False
    )
    return jsonify(result), (201 if result.get('success') else 400)

# ─── SUPER ADMIN API ───

@feedback_api.route('/api/super-admin/feedback/overview')
@require_auth
@require_role('super_admin')
def admin_feedback_overview():
    result = feedback_service.get_admin_overview()
    return jsonify(result), (200 if result.get('success') else 500)

@feedback_api.route('/api/super-admin/feedback/list')
@require_auth
@require_role('super_admin')
def admin_feedback_list():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    filters = {
        'status': request.args.get('status'),
        'category': request.args.get('category'),
        'severity': request.args.get('severity'),
        'institution': request.args.get('institution'),
        'search': request.args.get('search'),
        'sort': request.args.get('sort', 'latest'),
        'unviewed_only': request.args.get('unviewed_only') == 'true',
        'flagged_only': request.args.get('flagged_only') == 'true',
        'hidden_only': request.args.get('hidden_only') == 'true',
        'unresolved_only': request.args.get('unresolved_only') == 'true',
        'escalated_only': request.args.get('escalated_only') == 'true',
    }
    filters = {k: v for k, v in filters.items() if v}
    result = feedback_service.get_all_feedback_admin(page, per_page, filters)
    return jsonify(result), (200 if result.get('success') else 500)

@feedback_api.route('/api/super-admin/feedback/<feedback_id>/view', methods=['POST'])
@require_auth
@require_role('super_admin')
def admin_view_feedback(feedback_id):
    result = feedback_service.admin_view_feedback(feedback_id)
    return jsonify(result), 200

@feedback_api.route('/api/super-admin/feedback/<feedback_id>/detail')
@require_auth
@require_role('super_admin')
def admin_feedback_detail(feedback_id):
    result = feedback_service.get_feedback_detail(feedback_id)
    if result.get('success'):
        feedback_service.admin_view_feedback(feedback_id)
    return jsonify(result), (200 if result.get('success') else 404)

@feedback_api.route('/api/super-admin/feedback/<feedback_id>/note', methods=['POST'])
@require_auth
@require_role('super_admin')
def admin_add_note(feedback_id):
    admin_id = request.current_user.get('id')
    data = request.get_json(silent=True) or {}
    result = feedback_service.admin_add_note(feedback_id, admin_id, data.get('note', ''))
    return jsonify(result), (200 if result.get('success') else 400)

@feedback_api.route('/api/super-admin/feedback/<feedback_id>/moderate', methods=['POST'])
@require_auth
@require_role('super_admin')
def admin_moderate(feedback_id):
    admin_id = request.current_user.get('id')
    data = request.get_json(silent=True) or {}
    result = feedback_service.admin_moderate(
        feedback_id, admin_id,
        data.get('action', ''),
        data.get('reason', '')
    )
    return jsonify(result), (200 if result.get('success') else 400)

@feedback_api.route('/api/super-admin/feedback/<feedback_id>/reply-admin', methods=['POST'])
@require_auth
@require_role('super_admin')
def admin_reply_feedback(feedback_id):
    admin = request.current_user
    data = request.get_json(silent=True) or {}
    result = feedback_service.add_reply(
        feedback_id, admin.get('id'), admin.get('role', 'super_admin'),
        data.get('body', ''), is_admin=True
    )
    feedback_service.admin_view_feedback(feedback_id)
    return jsonify(result), (201 if result.get('success') else 400)

@feedback_api.route('/api/super-admin/feedback/analytics')
@require_auth
@require_role('super_admin')
def admin_feedback_analytics():
    result = feedback_service.get_admin_analytics()
    return jsonify(result), (200 if result.get('success') else 500)

@feedback_api.route('/api/super-admin/feedback/activity')
@require_auth
@require_role('super_admin')
def admin_feedback_activity():
    result = feedback_service.get_user_activity_insights()
    return jsonify(result), (200 if result.get('success') else 500)

@feedback_api.route('/api/super-admin/feedback/response-times')
@require_auth
@require_role('super_admin')
def admin_feedback_response_times():
    result = feedback_service.get_response_time_analytics()
    return jsonify(result), (200 if result.get('success') else 500)

@feedback_api.route('/api/super-admin/feedback/export')
@require_auth
@require_role('super_admin')
def admin_export_feedback():
    fmt = request.args.get('format', 'csv')
    filters = {
        'status': request.args.get('status'),
        'category': request.args.get('category'),
        'severity': request.args.get('severity'),
        'institution': request.args.get('institution'),
    }
    filters = {k: v for k, v in filters.items() if v}
    result = feedback_service.export_csv(filters)
    if not result.get('success'):
        return jsonify(result), 500
    if fmt == 'csv':
        return Response(
            result['csv'],
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=feedback_export.csv'}
        )
    return jsonify(result), 200

# ─── SSE REAL-TIME FEEDBACK EVENTS ───

@feedback_api.route('/api/feedback/events/stream')
@require_auth
@require_role('super_admin')
def feedback_event_stream():
    def generate():
        yield f"data: {json.dumps({'type': 'connected', 'message': 'Feedback events connected'})}\n\n"
        import time
        while True:
            try:
                overview = feedback_service.get_admin_overview()
                if overview.get('success'):
                    yield f"data: {json.dumps({'type': 'overview', 'data': overview['data']})}\n\n"
                time.sleep(5)
            except Exception:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Connection error'})}\n\n"
                break
    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive',
                             'X-Accel-Buffering': 'no'})

# ─── FEEDBACK DIAGNOSTICS PAGE ───

@feedback_api.route('/feedback/diagnostics')
@require_auth
@require_role('super_admin')
def feedback_diagnostics_page():
    from src.infrastructure.feedback_models import FeedbackDiagnostics as FD
    from src.infrastructure.sqlalchemy_db import get_db_session
    db = get_db_session()
    try:
        total = db.query(FD).count()
        vpn_count = db.query(FD).filter(FD.vpn_active == True).count()
        offline_count = db.query(FD).filter(FD.offline_mode == True).count()
        high_latency = db.query(FD).filter(FD.network_latency_ms > 500).count()
        mqtt_failures = db.query(FD).filter(FD.mqtt_sync_status != 'ok', FD.mqtt_sync_status.isnot(None)).count()
        return jsonify({'success': True, 'data': {
            'total_diagnostics': total, 'vpn_issues': vpn_count,
            'offline_events': offline_count, 'high_latency': high_latency,
            'mqtt_failures': mqtt_failures
        }})
    finally:
        db.close()
