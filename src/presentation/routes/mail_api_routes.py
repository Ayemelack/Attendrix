import logging
from flask import Blueprint, request, jsonify
from src.infrastructure.mail_service import mail_service
from src.application.rbac import require_auth, log_access


logger = logging.getLogger(__name__)

mail_api = Blueprint('mail_api', __name__, url_prefix='/api/mail')


@mail_api.route('/queue', methods=['POST'])
@require_auth
@log_access
def api_mail_queue():
    if not mail_service or not mail_service._initialized:
        return jsonify({'error': 'Mail service not initialized'}), 503

    data = request.get_json() or {}
    template_type = data.get('template_type', '')
    recipient_email = data.get('recipient_email', '').strip().lower()
    variables = data.get('variables', {})

    if not template_type:
        return jsonify({'error': 'template_type is required'}), 400
    if not recipient_email:
        return jsonify({'error': 'recipient_email is required'}), 400

    mail_id = mail_service.queue_email(
        template_type=template_type,
        recipient_email=recipient_email,
        recipient_name=data.get('recipient_name', ''),
        variables=variables,
        priority=data.get('priority', 0),
    )

    if mail_id:
        return jsonify({'success': True, 'mail_id': mail_id}), 201
    return jsonify({'error': 'Failed to queue email'}), 500


@mail_api.route('/status/<mail_id>')
@require_auth
@log_access
def api_mail_status(mail_id):
    if not mail_service or not mail_service._initialized:
        return jsonify({'error': 'Mail service not initialized'}), 503

    status = mail_service.get_mail_status(mail_id)
    if status is None:
        return jsonify({'error': 'Mail not found'}), 404
    return jsonify(status)


@mail_api.route('/queue', methods=['GET'])
@require_auth
@log_access
def api_mail_list():
    if not mail_service or not mail_service._initialized:
        return jsonify({'error': 'Mail service not initialized'}), 503

    status = request.args.get('status')
    limit = request.args.get('limit', 50, type=int)
    limit = min(limit, 200)

    emails = mail_service.get_queue_emails(status_filter=status, limit=limit)
    return jsonify(emails)
