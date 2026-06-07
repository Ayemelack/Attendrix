"""
PHASE 3A — WEBAUTHN/FIDO2 ROUTES

REST endpoints for passkey registration, authentication, and management.
All routes fall back gracefully when WebAuthn is unavailable.
"""

import logging

from flask import Blueprint, request, jsonify, session

from src.infrastructure.security.webauthn_service import webauthn_service
from src.application.auth_service import auth_service
from src.application.rbac import require_auth, require_role
from src.infrastructure.security_legacy import rate_limit_endpoint

logger = logging.getLogger(__name__)

webauthn_bp = Blueprint('webauthn', __name__, url_prefix='/auth/webauthn')


@webauthn_bp.route('/status', methods=['GET'])
def status():
    return jsonify({
        'available': webauthn_service.is_available(),
        'rp_id': webauthn_service.rp_id,
    })


@webauthn_bp.route('/register/begin', methods=['POST'])
@require_auth
@rate_limit_endpoint(limit=10, window=60, scope='user', block_duration=300)
def register_begin():
    """Generate registration options for creating a new passkey."""
    if not webauthn_service.is_available():
        return jsonify({'error': 'WebAuthn not available'}), 501

    user_id = request.current_user['user_id']
    user = auth_service.get_user_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    existing = webauthn_service.get_user_credentials(user_id)
    exclude_ids = [c['credential_id'] for c in existing if c.get('is_active')]

    options = webauthn_service.generate_registration_options(
        user_id=user_id,
        user_email=user.get('email', ''),
        user_display_name=user.get('display_name', user.get('email', '')),
        existing_credential_ids=exclude_ids,
    )

    if not options:
        return jsonify({'error': 'Failed to generate registration options'}), 500

    return jsonify({
        'publicKey': {
            'rp': {'id': options.rp_id, 'name': options.rp_name},
            'user': {
                'id': options.user_id,
                'name': options.user_name,
                'displayName': options.user_display_name,
            },
            'challenge': options.challenge,
            'pubKeyCredParams': options.pub_key_cred_params,
            'timeout': options.timeout,
            'attestation': options.attestation,
            'authenticatorSelection': options.authenticator_selection,
            'excludeCredentials': options.exclude_credentials,
        }
    })


@webauthn_bp.route('/register/complete', methods=['POST'])
@require_auth
@rate_limit_endpoint(limit=10, window=60, scope='user', block_duration=300)
def register_complete():
    """Verify and store a new WebAuthn credential."""
    if not webauthn_service.is_available():
        return jsonify({'error': 'WebAuthn not available'}), 501

    data = request.get_json(silent=True) or {}
    user_id = request.current_user['user_id']
    challenge = data.get('challenge')
    credential_id = data.get('credential_id')
    attestation_object = data.get('attestation_object')
    client_data_json = data.get('client_data_json')
    transports = data.get('transports', ['internal'])
    device_name = data.get('device_name', '')

    if not all([challenge, credential_id, attestation_object, client_data_json]):
        return jsonify({'error': 'Missing required fields'}), 400

    success, error, credential = webauthn_service.verify_registration(
        challenge_b64=challenge,
        credential_id=credential_id,
        attestation_object_b64=attestation_object,
        client_data_json_b64=client_data_json,
        transports=transports,
        device_name=device_name,
    )

    if not success:
        return jsonify({'error': error or 'Registration verification failed'}), 400

    logger.info(f"WebAuthn credential registered for user {user_id}: {credential_id[:16]}...")
    return jsonify({
        'status': 'ok',
        'credential_id': credential.get('credential_id'),
        'device_name': credential.get('device_name'),
        'credential_count': webauthn_service.get_credential_count(user_id),
    })


@webauthn_bp.route('/authenticate/begin', methods=['POST'])
def authenticate_begin():
    """Generate authentication options for a passkey login."""
    if not webauthn_service.is_available():
        return jsonify({'error': 'WebAuthn not available'}), 501

    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    options = webauthn_service.generate_authentication_options(user_id)
    if not options:
        return jsonify({
            'error': 'No active passkeys found for this user',
            'password_fallback': True,
        }), 404

    return jsonify({
        'publicKey': {
            'challenge': options.challenge,
            'rpId': options.rp_id,
            'timeout': options.timeout,
            'allowCredentials': options.allow_credentials,
            'userVerification': options.user_verification,
        }
    })


@webauthn_bp.route('/authenticate/complete', methods=['POST'])
def authenticate_complete():
    """Verify a passkey assertion and log the user in."""
    if not webauthn_service.is_available():
        return jsonify({'error': 'WebAuthn not available'}), 501

    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    credential_id = data.get('credential_id')
    authenticator_data = data.get('authenticator_data')
    client_data_json = data.get('client_data_json')
    signature = data.get('signature')
    user_handle = data.get('user_handle')

    if not all([user_id, credential_id, authenticator_data, client_data_json, signature]):
        return jsonify({'error': 'Missing required fields'}), 400

    success, error, result = webauthn_service.verify_authentication(
        user_id=user_id,
        credential_id=credential_id,
        authenticator_data_b64=authenticator_data,
        client_data_json_b64=client_data_json,
        signature_b64=signature,
        user_handle_b64=user_handle,
    )

    if not success:
        return jsonify({'error': error or 'Authentication failed'}), 401

    user = auth_service.get_user_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    token = auth_service.generate_token(user_id, user.get('role', 'attendee'))

    credential = webauthn_service.get_credential_by_id(credential_id, user_id)
    device_name = credential.get('device_name', 'Passkey') if credential else 'Passkey'

    logger.info(f"WebAuthn login: user {user_id} via {device_name}")
    return jsonify({
        'status': 'ok',
        'token': token,
        'user': {
            'id': user_id,
            'email': user.get('email'),
            'role': user.get('role'),
            'display_name': user.get('display_name'),
        },
        'credential_id': credential_id,
        'device_name': device_name,
    })


@webauthn_bp.route('/credentials', methods=['GET'])
@require_auth
def list_credentials():
    """List all active WebAuthn credentials for the current user."""
    user_id = request.current_user['user_id']
    credentials = webauthn_service.get_user_credentials(user_id)
    return jsonify({
        'credentials': credentials,
        'count': len(credentials),
    })


@webauthn_bp.route('/credentials/<credential_id>', methods=['DELETE'])
@require_auth
def delete_credential(credential_id):
    """Revoke a specific WebAuthn credential."""
    user_id = request.current_user['user_id']

    if not webauthn_service.verify_credential_id_ownership(credential_id, user_id):
        return jsonify({'error': 'Credential not found'}), 404

    if webauthn_service.revoke_credential(user_id, credential_id):
        logger.info(f"User {user_id} revoked WebAuthn credential {credential_id[:16]}...")
        return jsonify({'status': 'ok', 'message': 'Credential revoked'})
    return jsonify({'error': 'Failed to revoke credential'}), 500


@webauthn_bp.route('/credentials/revoke-all', methods=['POST'])
@require_auth
def revoke_all_credentials():
    """Revoke all WebAuthn credentials for the current user."""
    user_id = request.current_user['user_id']
    count = webauthn_service.revoke_all_credentials(user_id)
    logger.info(f"User {user_id} revoked all {count} WebAuthn credentials")
    return jsonify({
        'status': 'ok',
        'revoked_count': count,
        'message': f'{count} credential(s) revoked',
    })


@webauthn_bp.route('/admin/list', methods=['GET'])
@require_auth
@require_role('super_admin', 'institutional_admin')
def admin_list():
    """Admin: list credentials for any user."""
    current_user = request.current_user

    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id parameter required'}), 400

    credentials = webauthn_service.get_user_credentials(user_id)
    return jsonify({
        'user_id': user_id,
        'credentials': credentials,
        'count': len(credentials),
    })


@webauthn_bp.route('/admin/revoke', methods=['POST'])
@require_auth
@require_role('super_admin', 'institutional_admin')
def admin_revoke():
    """Admin: revoke a credential for any user."""
    current_user = request.current_user

    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    credential_id = data.get('credential_id')

    if not user_id or not credential_id:
        return jsonify({'error': 'user_id and credential_id required'}), 400

    if webauthn_service.revoke_credential(user_id, credential_id):
        logger.info(f"Admin {current_user['user_id']} revoked credential {credential_id[:16]}... for user {user_id}")
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Credential not found'}), 404


def register_webauthn_routes(app):
    app.register_blueprint(webauthn_bp)
    logger.info("WebAuthn routes registered")
