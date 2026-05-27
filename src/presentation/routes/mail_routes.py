import logging
from flask import Blueprint, request, jsonify, render_template
from src.infrastructure.mail_service import mail_service
from src.application.rbac import require_auth, require_role, log_access


logger = logging.getLogger(__name__)

mail_bp = Blueprint('mail_admin', __name__, url_prefix='/admin/mail')


@mail_bp.route('')
@require_auth
@require_role('super_admin', 'institutional_admin')
@log_access
def mail_dashboard():
    return render_template('admin/mail.html')


@mail_bp.route('/api/stats')
@require_auth
@require_role('super_admin', 'institutional_admin')
@log_access
def mail_stats():
    return jsonify(mail_service.get_queue_stats())


@mail_bp.route('/api/queue')
@require_auth
@require_role('super_admin', 'institutional_admin')
@log_access
def mail_queue():
    status = request.args.get('status')
    limit = request.args.get('limit', 50, type=int)
    return jsonify(mail_service.get_queue_emails(status_filter=status, limit=limit))


@mail_bp.route('/api/templates')
@require_auth
@require_role('super_admin', 'institutional_admin')
@log_access
def mail_templates():
    return jsonify(mail_service.get_templates())


@mail_bp.route('/api/audit')
@require_auth
@require_role('super_admin', 'institutional_admin')
@log_access
def mail_audit():
    limit = request.args.get('limit', 100, type=int)
    return jsonify(mail_service.get_audit_logs(limit=limit))


@mail_bp.route('/api/process', methods=['POST'])
@require_auth
@require_role('super_admin')
@log_access
def process_queue():
    count = mail_service.process_queue(batch_size=20)
    return jsonify({'processed': count})


@mail_bp.route('/api/retry', methods=['POST'])
@require_auth
@require_role('super_admin')
@log_access
def retry_failed():
    data = request.get_json() or {}
    mail_ids = data.get('mail_ids')
    count = mail_service.retry_failed_emails(mail_ids=mail_ids)
    return jsonify({'retried': count})


@mail_bp.route('/api/cancel/<mail_id>', methods=['POST'])
@require_auth
@require_role('super_admin')
@log_access
def cancel_email(mail_id):
    success = mail_service.cancel_email(mail_id)
    return jsonify({'success': success})


@mail_bp.route('/api/test', methods=['POST'])
@require_auth
@require_role('super_admin')
@log_access
def test_connection():
    results = mail_service.test_connection()
    return jsonify(results)


@mail_bp.route('/api/preview/<template_name>')
@require_auth
@require_role('super_admin', 'institutional_admin')
@log_access
def preview_template(template_name):
    templates = mail_service.get_templates()
    tpl = next((t for t in templates if t['template_name'] == template_name), None)
    if not tpl:
        return jsonify({'error': 'Template not found'}), 404

    sample_vars = {
        'voucher_delivery': {
            'recipient_name': 'John Doe', 'role_name': 'Student',
            'voucher_code': 'ABCD1234', 'expires_at': '2026-06-30',
        },
        'demo_confirmation': {
            'recipient_name': 'Jane Smith', 'institution': 'University of Technology',
            'demo_date': '2026-06-15', 'demo_time': '10:00 AM', 'timezone': 'UTC',
            'portal_url': 'http://localhost:5000/demo-prep?token=sample',
        },
        'password_reset': {
            'recipient_name': 'John Doe',
            'reset_link': 'http://localhost:5000/reset?token=sample',
            'expiry_minutes': '60',
        },
        'account_activation': {
            'recipient_name': 'John Doe', 'recipient_email': 'john@example.com',
            'activation_link': 'http://localhost:5000/activate?token=sample',
            'role_name': 'Student', 'institution_name': 'University of Technology',
        },
        'attendance_notification': {
            'recipient_name': 'John Doe', 'course_name': 'Computer Science 101',
            'session_name': 'Week 3 Lecture', 'session_date': '2026-05-27',
            'attendance_status': 'Present', 'status_color': '#10B981',
        },
        'institution_announcement': {
            'recipient_name': 'John Doe', 'announcement_title': 'Holiday Notice',
            'announcement_body': 'The university will be closed on June 1st.',
            'institution_name': 'University of Technology', 'announcement_date': '2026-05-27',
        },
        'system_alert': {
            'alert_title': 'Database Maintenance', 'alert_message': 'Scheduled maintenance at 2 AM.',
            'alert_severity': 'Info', 'alert_timestamp': '2026-05-27T10:00:00Z',
            'alert_component': 'Database',
        },
    }

    from src.infrastructure.mail_service import _load_template_file, _render_template
    body_template_str = tpl.get('subject_template', '')
    vars_for_template = sample_vars.get(template_name, {})
    subject = _render_template(body_template_str, vars_for_template)

    return jsonify({
        'template_name': template_name,
        'category': tpl.get('category'),
        'subject': subject,
        'variables': vars_for_template,
        'active': tpl.get('is_active'),
    })


@mail_bp.route('/api/send-test', methods=['POST'])
@require_auth
@require_role('super_admin')
@log_access
def send_test_email():
    data = request.get_json() or {}
    recipient = data.get('recipient_email', '')
    template_name = data.get('template_name', 'voucher_delivery')

    if not recipient:
        return jsonify({'error': 'recipient_email is required'}), 400

    sample_vars = {
        'voucher_delivery': {
            'recipient_name': 'Test User', 'role_name': 'Student',
            'voucher_code': 'TEST1234', 'expires_at': '2026-12-31',
        },
        'demo_confirmation': {
            'recipient_name': 'Test User', 'institution': 'Test University',
            'demo_date': '2026-06-15', 'demo_time': '10:00 AM', 'timezone': 'UTC',
            'portal_url': 'http://localhost:5000',
        },
        'password_reset': {
            'recipient_name': 'Test User',
            'reset_link': 'http://localhost:5000/reset?token=test',
            'expiry_minutes': '60',
        },
        'account_activation': {
            'recipient_name': 'Test User', 'recipient_email': 'test@example.com',
            'activation_link': 'http://localhost:5000/activate?token=test',
            'role_name': 'Student', 'institution_name': 'Test University',
        },
        'attendance_notification': {
            'recipient_name': 'Test User', 'course_name': 'CS 101',
            'session_name': 'Week 1', 'session_date': '2026-05-27',
            'attendance_status': 'Present', 'status_color': '#10B981',
        },
        'institution_announcement': {
            'recipient_name': 'Test User', 'announcement_title': 'Test Announcement',
            'announcement_body': 'This is a test announcement.',
            'institution_name': 'Test University', 'announcement_date': '2026-05-27',
        },
        'system_alert': {
            'alert_title': 'Test Alert', 'alert_message': 'This is a test alert.',
            'alert_severity': 'Info', 'alert_timestamp': '2026-05-27T10:00:00Z',
            'alert_component': 'Test',
        },
    }

    variables = data.get('variables', {}) or sample_vars.get(template_name, {})

    mail_id = mail_service.queue_email(
        template_type=template_name,
        recipient_email=recipient,
        recipient_name=variables.get('recipient_name', ''),
        variables=variables,
        priority=10,
    )

    if not mail_id:
        return jsonify({'error': 'Failed to queue test email'}), 500

    mail_service.process_queue(batch_size=1)

    return jsonify({'mail_id': mail_id, 'message': 'Test email queued and processed'})
