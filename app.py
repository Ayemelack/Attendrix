from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
from datetime import datetime, timedelta
import logging

# Import configuration
from config.settings import get_config

# Import infrastructure services
from src.infrastructure.firebase_service import firebase_service
from src.infrastructure.mqtt_service import mqtt_service

# Import application services
from src.application.rbac import require_auth, require_role, log_access

# Celery task queue for asynchronous background processing
from celery import Celery as _Celery

celery = _Celery('attendrix')
celery.conf.update(
    broker_url=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_soft_time_limit=300,
    task_time_limit=600,
)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def send_sms_background(self, phone_number: str, message: str):
    """Send SMS asynchronously via Celery worker."""
    from src.application.sms_service import SMSService
    svc = SMSService(firebase_service)
    try:
        svc.send_sms(phone_number, message)
    except Exception as exc:
        logger.error(f"SMS background send failed: {exc}")
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=30, acks_late=True)
def publish_attendance_event(self, session_id: str, student_id: str, status: str):
    """Publish attendance event via MQTT from background worker."""
    mqtt_service.initialize()
    mqtt_service.publish(
        f'attendrix/attendance/{session_id}',
        {
            'student_id': student_id,
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'celery-worker',
        },
        qos=1,
    )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RateLimiter:
    """In-memory rate limiter for login endpoint"""
    def __init__(self):
        self._attempts = {}
        self._lockouts = {}

    def is_limited(self, key: str, max_attempts: int = 10, window: int = 300) -> bool:
        now = datetime.utcnow()
        if key in self._lockouts:
            if now < self._lockouts[key]:
                return True
            del self._lockouts[key]

        if key not in self._attempts:
            self._attempts[key] = []

        self._attempts[key] = [t for t in self._attempts[key] if now - t < timedelta(seconds=window)]
        self._attempts[key].append(now)

        if len(self._attempts[key]) > max_attempts:
            self._lockouts[key] = now + timedelta(minutes=5)
            del self._attempts[key]
            return True

        return False

    def record_success(self, key: str):
        if key in self._attempts:
            del self._attempts[key]
        if key in self._lockouts:
            del self._lockouts[key]


rate_limiter = RateLimiter()


def create_app():
    """Application factory"""
    import os
    from pathlib import Path
    
    # Get the correct template and static folder paths
    template_folder = Path(__file__).parent / 'src' / 'presentation' / 'templates'
    static_folder = Path(__file__).parent / 'src' / 'presentation' / 'static'
    
    app = Flask(__name__, template_folder=str(template_folder), static_folder=str(static_folder))
    
    # Disable template caching completely
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['EXPLAIN_TEMPLATE_LOADING'] = True
    app.jinja_env.auto_reload = True
    app.jinja_env.cache = None
    
    # Load configuration
    config = get_config()
    app.config.from_object(config)
    config.init_app(app)
    
    # JWT Configuration
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)
    
    # Initialize extensions
    CORS(app)
    
    # Initialize Firebase
    try:
        # Pass config values to environ for downstream services
        os.environ['USE_MOCK_FIREBASE'] = app.config.get('USE_MOCK_FIREBASE', 'true')
        os.environ.setdefault('FIREBASE_CREDENTIALS_PATH', 'firebase-dev.json')
        
        # Trigger reload
        firebase_service.initialize(
            credentials_path='firebase-dev.json',
            project_id=None
        )
        logger.info(f"Firebase initialized (mock={os.environ['USE_MOCK_FIREBASE']})")
    except Exception as e:
        logger.error(f"Firebase initialization failed: {str(e)}")
    
    # Initialize authentication service
    try:
        from src.application.auth_service import AuthenticationService
        global auth_service
        auth_service = AuthenticationService()
        logger.info("Authentication service initialized successfully")
    except Exception as e:
        logger.error(f"Authentication service initialization failed: {str(e)}")
        auth_service = None

    # Initialize dashboard data service (replaces mock_data_provider)
    try:
        from src.application.dashboard_data_service import DashboardDataService
        global dashboard_service
        dashboard_service = DashboardDataService(firebase_service)
        logger.info("Dashboard data service initialized successfully")
    except Exception as e:
        logger.error(f"Dashboard data service initialization failed: {str(e)}")
        dashboard_service = None

    # Initialize student dashboard service
    try:
        from src.application.student_dashboard_service import StudentDashboardService
        global student_dashboard_service
        student_dashboard_service = StudentDashboardService(firebase_service)
        logger.info("Student dashboard service initialized successfully")
    except Exception as e:
        logger.error(f"Student dashboard service initialization failed: {str(e)}")
        student_dashboard_service = None

    # Initialize event service for SSE
    try:
        from src.application.event_service import EventService
        global event_service
        event_service = EventService(firebase_service, dashboard_service)
        logger.info("Event service initialized successfully")
    except Exception as e:
        logger.error(f"Event service initialization failed: {str(e)}")
        event_service = None

    # Initialize SMS service
    try:
        from src.application.sms_service import SMSService
        global sms_service
        sms_service = SMSService(firebase_service)
        sms_service.configure(provider=os.environ.get('SMS_PROVIDER', 'mock'))
        logger.info("SMS service initialized successfully")
    except Exception as e:
        logger.error(f"SMS service initialization failed: {str(e)}")
        sms_service = None

    # Initialize payment service
    try:
        from src.application.payment_service import PaymentService
        global payment_service
        payment_service = PaymentService(firebase_service)
        logger.info("Payment service initialized successfully")
    except Exception as e:
        logger.error(f"Payment service initialization failed: {str(e)}")
        payment_service = None

    # Initialize scheduling engine
    try:
        from src.application.scheduling_service import SchedulingEngine
        global scheduling_engine
        scheduling_engine = SchedulingEngine()
        logger.info("Scheduling engine initialized successfully")
    except Exception as e:
        logger.error(f"Scheduling engine initialization failed: {str(e)}")
        scheduling_engine = None

    # Initialize attendance engine
    try:
        from src.application.attendance_service import AttendanceEngine
        global attendance_engine
        attendance_engine = AttendanceEngine()
        logger.info("Attendance engine initialized successfully")
    except Exception as e:
        logger.error(f"Attendance engine initialization failed: {str(e)}")
        attendance_engine = None

    # Initialize offline queue service
    try:
        from src.application.offline_queue_service import OfflineQueueService
        global offline_queue_service
        offline_queue_service = OfflineQueueService(firebase_service)
        logger.info("Offline queue service initialized successfully")
    except Exception as e:
        logger.error(f"Offline queue service initialization failed: {str(e)}")
        offline_queue_service = None

    # Initialize MQTT service
    try:
        mqtt_service.initialize()
        if os.environ.get('MQTT_AUTO_CONNECT', 'false').lower() == 'true':
            mqtt_service.connect()
        logger.info(f"MQTT service initialized (mock={os.environ.get('USE_MOCK_MQTT', 'true')})")
    except Exception as e:
        logger.error(f"MQTT service initialization failed: {str(e)}")

    # Initialize Biometric service
    try:
        from src.application.biometric_service import BiometricService as _BiometricService
        global biometric_service_
        biometric_service_ = _BiometricService(firebase_service)
        logger.info("Biometric service initialized successfully")
    except Exception as e:
        logger.error(f"Biometric service initialization failed: {str(e)}")
        biometric_service_ = None

    # Update Celery config with app-level settings
    celery.conf.update(
        broker_url=app.config.get('CELERY_BROKER_URL', os.environ.get('REDIS_URL', 'redis://localhost:6379/0')),
        result_backend=app.config.get('CELERY_RESULT_BACKEND', os.environ.get('REDIS_URL', 'redis://localhost:6379/0')),
    )

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': 'Access forbidden'}), 403
    
    # Routes
    @app.route('/')
    def landing():
        """Landing page"""
        # Debug: Log template path and file info
        template_path = app.jinja_env.loader.get_source(app.jinja_env, 'landing.html')[1]
        logger.info(f"Rendering template from: {template_path}")
        
        response = render_template('landing.html')
        # Add cache-busting headers
        from flask import make_response
        resp = make_response(response)
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    
    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'environment': app.config.get('ENVIRONMENT', 'unknown')
        })
    
    @app.route('/api/ping')
    def ping():
        """Lightweight ping endpoint for latency measurement."""
        import time as time_mod
        return jsonify({
            'pong': True,
            'server_time': datetime.utcnow().isoformat(),
            'timestamp': time_mod.time(),
        })

    @app.route('/api/mqtt/status')
    def mqtt_status():
        """MQTT broker connection status (mock or real)."""
        return jsonify(mqtt_service.status)

    @app.route('/api/demo/request', methods=['POST'])
    @log_access
    def demo_request():
        """Handle demo request form submission"""
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['fullName', 'email', 'phone', 'institutionName', 'institutionType', 'numberOfStudents']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'error': f'{field} is required'}), 400
            
            # Log demo request
            logger.info(f"Demo request received: {data.get('email')} - {data.get('institutionName')}")
            
            # Here you would typically:
            # 1. Save to database
            # 2. Send email notification
            # 3. Create follow-up task
            
            return jsonify({
                'success': True,
                'message': 'Demo request received successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Demo request error: {str(e)}")
            return jsonify({'error': 'Failed to process demo request'}), 500
    
    # Authentication routes
    @app.route('/api/auth/register', methods=['POST'])
    @log_access
    def register():
        """User registration with voucher validation"""
        try:
            data = request.get_json()

            required_fields = ['email', 'password', 'first_name', 'last_name', 'role', 'voucher_code']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400

            from src.domain.entities import UserRole
            role_mapping = {
                'institutional_admin': UserRole.INSTITUTIONAL_ADMIN,
                'lecturer': UserRole.LECTURER,
                'student': UserRole.STUDENT
            }

            role_enum = role_mapping.get(data['role'])
            if not role_enum:
                return jsonify({'error': f'Invalid role: {data["role"]}'}), 400

            if not auth_service:
                return jsonify({'error': 'Authentication service not available'}), 500

            user = auth_service.register_user(
                email=data['email'],
                password=data['password'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                role=role_enum,
                institution_id=data['institution_id'],
                voucher_code=data.get('voucher_code'),
                student_id=data.get('student_id')
            )

            return jsonify({
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role.value,
                'institution_id': user.institution_id,
                'message': 'Registration successful'
            }), 201

        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            error_msg = str(e).lower()
            if 'firebase' in error_msg and 'credentials' in error_msg:
                return jsonify({'error': 'Service temporarily unavailable'}), 503
            if 'exists' in error_msg:
                return jsonify({'error': 'Email already registered'}), 409
            return jsonify({'error': f'Registration failed: {str(e)}'}), 500
    
    @app.route('/signup-voucher')
    def signup_voucher_page():
        """Professional voucher-based signup page"""
        return render_template('signup-voucher.html')

    @app.route('/api/auth/signup', methods=['POST'])
    @log_access
    def signup():
        """User registration - alias for register endpoint"""
        return register()
    
    @app.route('/api/auth/login', methods=['POST'])
    @log_access
    def login():
        """User login with rate limiting"""
        try:
            data = request.get_json()
            if data is None:
                return jsonify({'success': False, 'message': 'Invalid request format'}), 400

            if not data.get('email') or not data.get('password'):
                return jsonify({'success': False, 'message': 'Email and password are required'}), 400

            client_ip = request.remote_addr or 'unknown'
            if rate_limiter.is_limited(client_ip):
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return jsonify({'success': False, 'message': 'Too many attempts. Try again in 15 minutes.'}), 429

            if not auth_service:
                return jsonify({'success': False, 'message': 'Service temporarily unavailable'}), 500

            result = auth_service.authenticate_user(
                email=data['email'],
                password=data['password'],
                remember_me=data.get('remember_me', False),
                device_fingerprint=data.get('device_fingerprint'),
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )

            if result and isinstance(result, dict):
                if result.get('success'):
                    rate_limiter.record_success(client_ip)
                    return jsonify(result), 200
                return jsonify(result), 401

            return jsonify({'success': False, 'message': 'Authentication failed'}), 401

        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return jsonify({'success': False, 'message': 'Authentication failed'}), 401
    
    @app.route('/api/auth/refresh', methods=['POST'])
    @log_access
    def refresh_token():
        """Refresh access token"""
        try:
            data = request.get_json()
            refresh_token = data.get('refresh_token')
            
            if not refresh_token:
                return jsonify({'error': 'Refresh token required'}), 400
            
            result = auth_service.refresh_token(refresh_token)
            
            if result:
                return jsonify(result), 200
            else:
                return jsonify({'error': 'Invalid refresh token'}), 401
                
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            return jsonify({'error': 'Token refresh failed'}), 500
    
    @app.route('/api/auth/logout', methods=['POST'])
    @require_auth
    @log_access
    def logout():
        """User logout"""
        try:
            user_id = request.current_user.get('user_id')
            success = auth_service.logout_user(
                user_id=user_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            
            if success:
                return jsonify({'message': 'Logged out successfully'}), 200
            else:
                return jsonify({'error': 'Logout failed'}), 500
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return jsonify({'error': 'Logout failed'}), 500

    @app.route('/api/auth/change-password', methods=['POST'])
    @require_auth
    @log_access
    def change_password():
        """Change password for authenticated user"""
        try:
            data = request.get_json()
            if not data or not data.get('current_password') or not data.get('new_password'):
                return jsonify({'error': 'current_password and new_password required'}), 400

            user_id = request.current_user.get('user_id')
            ok = auth_service.change_password(
                user_id=user_id,
                current_password=data['current_password'],
                new_password=data['new_password']
            )
            if ok:
                return jsonify({'message': 'Password changed successfully'}), 200
            else:
                return jsonify({'error': 'Current password is incorrect'}), 401
        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            return jsonify({'error': 'Password change failed'}), 500


    @app.route('/logout', methods=['GET'])
    def logout_page():
        """Logout page redirect"""
        return render_template('logout.html')
    
    @app.route('/login', methods=['GET'])
    def login_page():
        """Login page"""
        return render_template('login.html')
    
    @app.route('/signup', methods=['GET'])
    def signup_page():
        """Sign up page"""
        return render_template('signup.html')
    
    # Scheduling routes
    @app.route('/api/schedules', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def create_schedule():
        """Create a new schedule"""
        try:
            data = request.get_json()
            
            schedule_id, conflicts = scheduling_engine.create_schedule(data)
            
            if schedule_id:
                return jsonify({
                    'message': 'Schedule created successfully',
                    'schedule_id': schedule_id
                }), 201
            else:
                return jsonify({
                    'error': 'Schedule creation failed',
                    'conflicts': [
                        {
                            'type': conflict.conflict_type,
                            'description': conflict.description,
                            'severity': conflict.severity
                        } for conflict in conflicts
                    ]
                }), 400
                
        except Exception as e:
            logger.error(f"Schedule creation error: {str(e)}")
            return jsonify({'error': 'Schedule creation failed'}), 500
    
    @app.route('/api/schedules/<schedule_id>/conflicts', methods=['GET'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def check_schedule_conflicts(schedule_id):
        """Check conflicts for a schedule"""
        try:
            # This would typically fetch the schedule and check conflicts
            # For now, return a placeholder response
            return jsonify({
                'schedule_id': schedule_id,
                'conflicts': []
            }), 200
            
        except Exception as e:
            logger.error(f"Conflict check error: {str(e)}")
            return jsonify({'error': 'Conflict check failed'}), 500
    
    # Attendance routes
    @app.route('/api/attendance/create-session', methods=['POST'])
    @require_auth
    @require_role('lecturer')
    @log_access
    def create_attendance_session():
        """Create QR attendance session - real implementation"""
        try:
            data = request.get_json()
            
            course_id = data.get('course_id')
            location = data.get('location')
            
            if not course_id:
                return jsonify({'error': 'Course ID required'}), 400
            
            # Use real attendance security service
            from src.application.attendance_security_service import AttendanceSecurityService
            attendance_security = AttendanceSecurityService(firebase_service)
            
            result = attendance_security.create_attendance_session(
                course_id=course_id,
                lecturer_id=request.current_user.get('user_id'),
                location=location
            )
            
            if 'error' in result:
                return jsonify(result), 400
            else:
                return jsonify(result), 200
                
        except Exception as e:
            logger.error(f"Attendance session creation error: {str(e)}")
            return jsonify({'error': 'Session creation failed'}), 500
    
    @app.route('/api/attendance/mark', methods=['POST'])
    @require_auth
    @require_role('student')
    @log_access
    def mark_attendance():
        """Mark attendance with QR code validation - real implementation"""
        try:
            data = request.get_json()
            
            session_code = data.get('session_code')
            if not session_code:
                return jsonify({'error': 'Session code required'}), 400

            # Optional face verification
            face_descriptor = data.get('face_descriptor')
            if face_descriptor:
                from src.application.biometric_service import BiometricService as _BS
                bs = _BS(firebase_service)
                face_result = bs.verify_face(
                    request.current_user.get('user_id'),
                    face_descriptor
                )
                if not face_result.get('verified'):
                    return jsonify({
                        'error': 'Face verification failed',
                        'face_result': face_result
                    }), 403
            
            # Use real attendance security service
            from src.application.attendance_security_service import AttendanceSecurityService
            attendance_security = AttendanceSecurityService(firebase_service)
            
            result = attendance_security.mark_attendance(
                session_code=session_code,
                student_id=request.current_user.get('user_id'),
                device_fingerprint=data.get('device_fingerprint'),
                ip_address=request.remote_addr,
                location=data.get('location')
            )

            if 'error' in result:
                return jsonify(result), 400
            else:
                mqtt_service.publish(
                    f'attendrix/attendance/{result.get("session_id", session_code)}',
                    {
                        'student_id': request.current_user.get('user_id'),
                        'status': 'present',
                        'session_code': session_code,
                        'method': result.get('method', 'qr'),
                        'timestamp': datetime.utcnow().isoformat(),
                    },
                    qos=1,
                )
                return jsonify(result), 200
                
        except Exception as e:
            logger.error(f"Attendance marking error: {str(e)}")
            return jsonify({'error': 'Failed to mark attendance'}), 500
    
    @app.route('/api/attendance/close-session/<session_id>', methods=['POST'])
    @require_auth
    @require_role('lecturer')
    @log_access
    def close_attendance_session(session_id):
        """Close attendance session"""
        try:
            # Use real attendance security service
            from src.application.attendance_security_service import AttendanceSecurityService
            attendance_security = AttendanceSecurityService(firebase_service)
            
            result = attendance_security.close_attendance_session(
                session_id=session_id,
                lecturer_id=request.current_user.get('user_id')
            )
            
            if 'error' in result:
                return jsonify(result), 400
            else:
                return jsonify(result), 200
                
        except Exception as e:
            logger.error(f"Session closure error: {str(e)}")
            return jsonify({'error': 'Failed to close session'}), 500

    # ── FACE RECOGNITION ENDPOINTS ──

    @app.route('/api/biometric/face/status', methods=['GET'])
    @require_auth
    def face_status():
        """Check if user has face enrolled"""
        try:
            from src.application.biometric_service import BiometricService as _BS
            bs = _BS(firebase_service)
            user_id = request.current_user.get('user_id')
            result = bs.get_face_status(user_id)
            return jsonify(result), 200
        except Exception as e:
            logger.error(f"Face status error: {str(e)}")
            return jsonify({'enrolled': False, 'error': 'Failed to check face status'}), 500

    @app.route('/api/biometric/face/enroll', methods=['POST'])
    @require_auth
    @require_role('student')
    def face_enroll():
        """Enroll face descriptor for current user"""
        try:
            data = request.get_json()
            descriptor = data.get('descriptor')
            if not descriptor:
                return jsonify({'success': False, 'error': 'Face descriptor required'}), 400
            from src.application.biometric_service import BiometricService as _BS
            bs = _BS(firebase_service)
            user_id = request.current_user.get('user_id')
            institution_id = request.current_user.get('institution_id')
            result = bs.enroll_face(user_id, descriptor, institution_id)
            status = 200 if result.get('success') else 400
            return jsonify(result), status
        except Exception as e:
            logger.error(f"Face enroll error: {str(e)}")
            return jsonify({'success': False, 'error': 'Failed to enroll face'}), 500

    @app.route('/api/biometric/face/verify', methods=['POST'])
    @require_auth
    @require_role('student')
    def face_verify():
        """Verify face descriptor against enrolled face"""
        try:
            data = request.get_json()
            descriptor = data.get('descriptor')
            threshold = data.get('threshold', 0.6)
            if not descriptor:
                return jsonify({'verified': False, 'error': 'Face descriptor required'}), 400
            from src.application.biometric_service import BiometricService as _BS
            bs = _BS(firebase_service)
            user_id = request.current_user.get('user_id')
            result = bs.verify_face(user_id, descriptor, threshold)
            status = 200 if not result.get('error') else 400
            return jsonify(result), status
        except Exception as e:
            logger.error(f"Face verify error: {str(e)}")
            return jsonify({'verified': False, 'error': 'Failed to verify face'}), 500

    @app.route('/api/biometric/face/revoke', methods=['DELETE'])
    @require_auth
    def face_revoke():
        """Revoke face enrollment"""
        try:
            from src.application.biometric_service import BiometricService as _BS
            bs = _BS(firebase_service)
            user_id = request.current_user.get('user_id')
            result = bs.revoke_face(user_id)
            return jsonify(result), 200
        except Exception as e:
            logger.error(f"Face revoke error: {str(e)}")
            return jsonify({'success': False, 'error': 'Failed to revoke face'}), 500

    @app.route('/api/attendance/sessions/<session_id>/statistics', methods=['GET'])
    @require_auth
    @require_role('lecturer', 'institutional_admin', 'super_admin')
    @log_access
    def get_session_statistics(session_id):
        """Get attendance session statistics"""
        try:
            stats = attendance_engine.get_session_statistics(session_id)
            return jsonify(stats), 200
            
        except Exception as e:
            logger.error(f"Session statistics error: {str(e)}")
            return jsonify({'error': 'Failed to get statistics'}), 500
    
    # User profile routes
    @app.route('/api/users/profile', methods=['GET'])
    @require_auth
    @log_access
    def get_user_profile():
        """Get user profile"""
        try:
            user_id = request.current_user.get('user_id')
            user_data = user_repo.get_by_id(user_id)
            
            if user_data:
                # Remove sensitive information
                user_data.pop('password_hash', None)
                return jsonify(user_data), 200
            else:
                return jsonify({'error': 'User not found'}), 404
                
        except Exception as e:
            logger.error(f"Profile retrieval error: {str(e)}")
            return jsonify({'error': 'Failed to get profile'}), 500
    @app.route('/api/users/profile', methods=['PUT'])
    @require_auth
    @log_access
    def update_user_profile():
        """Update user profile"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400

            user_id = request.current_user.get('user_id')
            ok = auth_service.update_profile(user_id, data)
            if ok:
                return jsonify({'message': 'Profile updated'}), 200
            else:
                return jsonify({'error': 'No valid fields to update'}), 400
        except Exception as e:
            logger.error(f"Profile update error: {str(e)}")
            return jsonify({'error': 'Profile update failed'}), 500

    
    # Dashboard routes
    @app.route('/api/dashboard', methods=['GET'])
    @require_auth
    @log_access
    def get_dashboard():
        """Get role-based dashboard data"""
        try:
            user_role = request.current_user.get('role')
            user_id = request.current_user.get('user_id')
            institution_id = request.current_user.get('institution_id')
            
            # Return different dashboard data based on role
            dashboard_data = {
                'user_role': user_role,
                'user_id': user_id,
                'institution_id': institution_id
            }
            
            if user_role == 'student':
                dashboard_data.update({
                    'attendance_summary': 'Student attendance data',
                    'courses': 'Enrolled courses',
                    'announcements': 'Recent announcements'
                })
            elif user_role == 'lecturer':
                dashboard_data.update({
                    'courses': 'Assigned courses',
                    'attendance_sessions': 'Active sessions',
                    'analytics': 'Class analytics'
                })
            elif user_role in ['institutional_admin', 'super_admin']:
                dashboard_data.update({
                    'institution_stats': 'Institution statistics',
                    'user_management': 'User management data',
                    'system_health': 'System health metrics'
                })
            
            return jsonify(dashboard_data), 200
            
        except Exception as e:
            logger.error(f"Dashboard retrieval error: {str(e)}")
            return jsonify({'error': 'Failed to get dashboard data'}), 500
    
    # Clean dashboard routes - no old logic
    @app.route('/admin/dashboard')
    def admin_dashboard():
        """Hidden System Administration - PRIVATE ROUTE"""
        return render_template('admin/dashboard.html')
    
    @app.route('/institutional-admin/dashboard')
    def institutional_admin_dashboard():
        """Institutional Administrator Dashboard"""
        return render_template('institutional-admin/dashboard.html')

    # ── Institutional Admin API Endpoints ──
    @app.route('/api/institutional/activity-feed')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def institutional_activity_feed():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        events = dashboard_service.get_activity_feed(institution_id) if dashboard_service else []
        return jsonify({'events': events})

    @app.route('/api/institutional/security-alerts')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def institutional_security_alerts():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        alerts = dashboard_service.get_security_alerts(institution_id) if dashboard_service else []
        return jsonify({'alerts': alerts})

    @app.route('/api/institutional/network-status')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def institutional_network_status():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = dashboard_service.get_network_status(institution_id) if dashboard_service else {}
        return jsonify(data)

    @app.route('/api/institutional/session-health')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def institutional_session_health():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        data = dashboard_service.get_session_health(institution_id, page=page, per_page=per_page) if dashboard_service else {'active_sessions': 0, 'total_sessions': 0, 'sessions': [], 'total': 0, 'page': 1, 'per_page': 20, 'total_pages': 1}
        return jsonify(data)

    @app.route('/api/institutional/attendance-trends')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def institutional_attendance_trends():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = dashboard_service.get_attendance_trends(institution_id) if dashboard_service else {'daily_rates': [], 'dates': [], 'average': 0, 'faculty_comparison': []}
        return jsonify(data)

    @app.route('/api/institutional/students')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def institutional_students():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        search = request.args.get('search', '', type=str)
        result = dashboard_service.get_students_with_risk(institution_id, page=page, per_page=per_page, search=search) if dashboard_service else {'students': [], 'total': 0, 'page': 1, 'per_page': 12, 'total_pages': 1}
        return jsonify(result)

    @app.route('/api/institutional/students/<student_id>')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def institutional_student_detail(student_id):
        institution_id = request.current_user.get('institution_id', 'inst_001')
        detail = dashboard_service.get_student_detail(institution_id, student_id) if dashboard_service else None
        if not detail:
            return jsonify({'error': 'Student not found'}), 404
        return jsonify(detail)

    @app.route('/api/institutional/offline-log')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def institutional_offline_log():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = dashboard_service.get_offline_log(institution_id) if dashboard_service else {'total_offline_sessions': 0, 'pending_syncs': 0, 'last_sync': '—', 'sync_success_rate': 100, 'nodes_offline': 0, 'queue': []}
        return jsonify(data)

    @app.route('/api/institutional/infrastructure')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_infrastructure():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = dashboard_service.get_infrastructure_status(institution_id) if dashboard_service else {}
        return jsonify(data)

    @app.route('/api/institutional/compliance')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_compliance():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = dashboard_service.get_compliance_status(institution_id) if dashboard_service else {}
        return jsonify(data)

    @app.route('/api/institutional/payments')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_payments():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        data = dashboard_service.get_payment_status(institution_id, page=page, per_page=per_page) if dashboard_service else {}
        return jsonify(data)

    @app.route('/api/institutional/p2p-sync')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_p2p_sync():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = dashboard_service.get_p2p_sync_status(institution_id) if dashboard_service else {}
        return jsonify(data)

    @app.route('/api/reports/attendance')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def download_attendance_report():
        """Generate and download attendance report as PDF"""
        try:
            institution_id = request.current_user.get('institution_id', 'inst_001')
            report_type = request.args.get('type', 'summary')

            from src.application.report_service import ReportService
            report_svc = ReportService(firebase_service)
            pdf_bytes = report_svc.generate_attendance_report(
                institution_id, report_type=report_type
            )

            if not pdf_bytes:
                return jsonify({'error': 'Report generation failed'}), 500

            from flask import send_file
            import io as io_mod
            return send_file(
                io_mod.BytesIO(pdf_bytes),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'attendance_report_{datetime.utcnow().strftime("%Y%m%d")}.pdf'
            )
        except Exception as e:
            logger.error(f"Report download failed: {str(e)}")
            return jsonify({'error': 'Report generation failed'}), 500

    @app.route('/api/institutional/quick-actions')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_quick_actions():
        actions = dashboard_service.get_quick_actions() if dashboard_service else []
        return jsonify({'actions': actions})

    @app.route('/api/institutional/translations')
    @require_auth
    @log_access
    def institutional_translations():
        lang = request.args.get('lang', 'en')
        data = dashboard_service.get_translations(lang) if dashboard_service else {}
        return jsonify(data)

    # ── SSE REAL-TIME EVENT STREAM ──
    @app.route('/api/institutional/events/stream')
    def institutional_event_stream():
        """Server-Sent Events endpoint for real-time dashboard updates.

        Uses ?token= query param because EventSource does not support headers.
        In dev mode, falls back to ?institution_id if no token provided.
        """
        from flask import Response as FlaskResponse

        token = request.args.get('token')
        user_id = None
        institution_id = None

        if token:
            try:
                payload = auth_service.verify_token(token)
                if payload:
                    user_id = payload.get('user_id')
                    institution_id = payload.get('institution_id', 'inst_001')
            except Exception as e:
                logger.warning(f"SSE token validation failed: {e}")
        elif app.config.get('ENVIRONMENT', 'development') == 'development':
            inst_arg = request.args.get('institution_id', 'inst_001')
            user_id = f"dev_user_{inst_arg}"
            institution_id = inst_arg
            logger.warning(f"SSE dev fallback — no token, auto-created user={user_id}")

        if not user_id or not institution_id:
            return jsonify({'error': 'Authentication required'}), 401

        if not event_service:
            return jsonify({'error': 'Event service unavailable'}), 503

        return FlaskResponse(
            event_service.generate_stream(institution_id, user_id),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
                'Access-Control-Allow-Origin': '*',
            }
        )

    @app.route('/api/student/events/stream')
    def student_event_stream():
        """SSE endpoint for student real-time updates.

        Mirrors the institutional stream but filters events relevant to students:
        attendance confirmations, schedule changes, notifications.
        """
        from flask import Response as FlaskResponse

        token = request.args.get('token')
        user_id = None
        institution_id = None

        if token:
            try:
                payload = auth_service.verify_token(token)
                if payload:
                    user_id = payload.get('user_id')
                    institution_id = payload.get('institution_id', 'inst_001')
            except Exception as e:
                logger.warning(f"Student SSE auth failed: {e}")
        elif app.config.get('ENVIRONMENT', 'development') == 'development':
            user_id = request.args.get('user_id', 'dev_student')
            institution_id = request.args.get('institution_id', 'inst_001')
            logger.warning(f"Student SSE dev fallback — user={user_id}")

        if not user_id or not institution_id:
            return jsonify({'error': 'Authentication required'}), 401

        if not event_service:
            return jsonify({'error': 'Event service unavailable'}), 503

        return FlaskResponse(
            event_service.generate_student_stream(institution_id, user_id),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
                'Access-Control-Allow-Origin': '*',
            }
        )

    # ── DATA CREATION / MANAGEMENT ENDPOINTS ──

    # Wire additional repository-layer endpoints
    from src.infrastructure.repositories import (
        institution_repo, notification_repo, leave_request_repo,
        system_config_repo, department_repo, course_repo,
        attendance_session_repo, attendance_record_repo, security_log_repo,
    )

    @app.route('/api/institutions', methods=['GET'])
    @require_auth
    @require_role('super_admin')
    @log_access
    def list_institutions():
        limit = request.args.get('limit', 50, type=int)
        data = institution_repo.list_all(limit=limit)
        return jsonify({'institutions': data})

    @app.route('/api/institutions/<institution_id>', methods=['GET'])
    @require_auth
    @require_role('super_admin', 'institutional_admin')
    @log_access
    def get_institution(institution_id):
        data = institution_repo.get_by_id(institution_id)
        if not data:
            return jsonify({'error': 'Institution not found'}), 404
        return jsonify(data)

    @app.route('/api/notifications', methods=['GET'])
    @require_auth
    @log_access
    def list_notifications():
        user_id = request.current_user.get('user_id')
        unread = request.args.get('unread', '').lower() == 'true'
        if unread:
            data = notification_repo.get_unread(user_id)
        else:
            data = notification_repo.get_by_user(user_id)
        return jsonify({'notifications': data})

    @app.route('/api/notifications/<notification_id>/read', methods=['POST'])
    @require_auth
    @log_access
    def mark_notification_read(notification_id):
        notification_repo.update(notification_id, {'is_read': True, 'read_at': datetime.utcnow().isoformat()})
        return jsonify({'message': 'Notification marked as read'})

    @app.route('/api/leave-requests', methods=['GET'])
    @require_auth
    @log_access
    def list_leave_requests():
        user_id = request.current_user.get('user_id')
        institution_id = request.current_user.get('institution_id', 'inst_001')
        role = request.current_user.get('role')
        if role in ('super_admin', 'institutional_admin'):
            data = leave_request_repo.get_by_institution(institution_id)
        else:
            data = leave_request_repo.get_by_user(user_id)
        return jsonify({'leave_requests': data})

    @app.route('/api/leave-requests', methods=['POST'])
    @require_auth
    @log_access
    def create_leave_request():
        data = request.get_json()
        doc_id = leave_request_repo.create({
            'user_id': request.current_user.get('user_id'),
            'institution_id': request.current_user.get('institution_id', 'inst_001'),
            'leave_type': data.get('leave_type', ''),
            'start_date': data.get('start_date', ''),
            'end_date': data.get('end_date', ''),
            'reason': data.get('reason', ''),
            'status': 'pending',
        })
        return jsonify({'id': doc_id, 'message': 'Leave request submitted'}), 201

    @app.route('/api/institutional/activity-log', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def create_activity_log():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        doc_id = dashboard_service.create_activity_log(
            institution_id=institution_id,
            type=data.get('type', 'info'),
            message=data.get('message', ''),
            faculty=data.get('faculty', ''),
            user_id=request.current_user.get('user_id', '')
        )
        return jsonify({'id': doc_id, 'message': 'Activity log created'}), 201

    @app.route('/api/institutional/security-alert', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def create_security_alert():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        doc_id = dashboard_service.create_security_alert(
            institution_id=institution_id,
            event_type=data.get('event_type', 'manual_alert'),
            description=data.get('description', ''),
            severity=data.get('severity', 'medium'),
            user_id=request.current_user.get('user_id', '')
        )
        return jsonify({'id': doc_id, 'message': 'Security alert created'}), 201

    @app.route('/api/institutional/network/node', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def upsert_network_node():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        doc_id = dashboard_service.upsert_network_node(
            institution_id=institution_id,
            name=data.get('name', ''),
            type=data.get('type', 'building'),
            status=data.get('status', 'healthy'),
            latency_ms=data.get('latency_ms', 0),
            packet_loss=data.get('packet_loss', 0.0),
            node_id=data.get('node_id')
        )
        return jsonify({'id': doc_id, 'message': 'Network node saved'}), 201

    @app.route('/api/institutional/session', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def create_session():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        doc_id = dashboard_service.create_attendance_session(
            institution_id=institution_id,
            course_id=data.get('course_id', ''),
            course_name=data.get('course_name', ''),
            lecturer_name=data.get('lecturer_name', ''),
            total_students=data.get('total_students', 0)
        )
        return jsonify({'id': doc_id, 'message': 'Attendance session created'}), 201

    @app.route('/api/institutional/offline-sync', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def enqueue_offline_sync():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        doc_id = dashboard_service.enqueue_offline_sync(
            institution_id=institution_id,
            node_name=data.get('node_name', 'Unknown'),
            records=data.get('records', 0)
        )
        return jsonify({'id': doc_id, 'message': 'Offline sync enqueued'}), 201

    # ── OFFLINE QUEUE SERVICE API ──

    @app.route('/api/institutional/offline-queue/stats')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def offline_queue_stats():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        if not offline_queue_service:
            return jsonify({'error': 'Offline queue service unavailable'}), 503
        stats = offline_queue_service.get_queue_stats(institution_id)
        return jsonify(stats)

    @app.route('/api/institutional/offline-queue/process', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def offline_queue_process():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        if not offline_queue_service:
            return jsonify({'error': 'Offline queue service unavailable'}), 503
        result = offline_queue_service.process_queue(institution_id)
        return jsonify(result)

    @app.route('/api/institutional/offline-queue/pending')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def offline_queue_pending():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        if not offline_queue_service:
            return jsonify({'error': 'Offline queue service unavailable'}), 503
        pending = offline_queue_service.get_pending(institution_id)
        return jsonify({'pending': pending[:25], 'total': len(pending)})

    @app.route('/api/institutional/offline-queue/failed')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def offline_queue_failed():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        if not offline_queue_service:
            return jsonify({'error': 'Offline queue service unavailable'}), 503
        failed = offline_queue_service.get_failed(institution_id)
        return jsonify({'failed': failed[:25], 'total': len(failed)})

    @app.route('/api/institutional/offline-queue/retry', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def offline_queue_retry():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json() or {}
        entry_id = data.get('entry_id')
        if not offline_queue_service:
            return jsonify({'error': 'Offline queue service unavailable'}), 503
        count = offline_queue_service.retry_failed(entry_id=entry_id, institution_id=institution_id)
        return jsonify({'retried': count, 'message': f'Reset {count} entries for retry'})

    @app.route('/api/institutional/offline-queue/clear', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def offline_queue_clear():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json() or {}
        older_than = data.get('older_than_hours', 24)
        if not offline_queue_service:
            return jsonify({'error': 'Offline queue service unavailable'}), 503
        removed = offline_queue_service.clear_synced(institution_id, older_than_hours=older_than)
        return jsonify({'removed': removed, 'message': f'Cleared {removed} old synced entries'})

    @app.route('/api/institutional/offline-queue/estimate')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def offline_queue_estimate():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        if not offline_queue_service:
            return jsonify({'error': 'Offline queue service unavailable'}), 503
        estimate = offline_queue_service.estimate_sync_duration(institution_id)
        return jsonify(estimate)

    @app.route('/api/institutional/offline-queue/nodes')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def offline_queue_nodes():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        if not offline_queue_service:
            return jsonify({'error': 'Offline queue service unavailable'}), 503
        nodes = offline_queue_service.get_node_sync_status(institution_id)
        return jsonify({'nodes': nodes})

    @app.route('/api/institutional/offline-queue/enqueue', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def offline_queue_enqueue():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        if not data or not data.get('operation_type') or not data.get('payload'):
            return jsonify({'error': 'operation_type and payload are required'}), 400
        if not offline_queue_service:
            return jsonify({'error': 'Offline queue service unavailable'}), 503
        entry_id = offline_queue_service.enqueue(
            institution_id=institution_id,
            operation_type=data['operation_type'],
            payload=data['payload'],
            node_name=data.get('node_name', 'web'),
            priority=data.get('priority', 0)
        )
        return jsonify({'id': entry_id, 'message': 'Operation queued for sync'}), 201

    @app.route('/api/institutional/infrastructure/ups', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def upsert_ups():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        doc_id = dashboard_service.upsert_ups_status(
            institution_id=institution_id,
            charge_pct=data.get('charge_pct', 100),
            runtime_minutes=data.get('runtime_minutes', 180),
            status=data.get('status', 'online'),
            load_pct=data.get('load_pct', 30),
            power_status=data.get('power_status', 'mains'),
            ups_id=data.get('ups_id')
        )
        return jsonify({'id': doc_id, 'message': 'UPS status updated'}), 201

    @app.route('/api/institutional/infrastructure/isp', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def upsert_isp():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        doc_id = dashboard_service.upsert_isp(
            institution_id=institution_id,
            name=data.get('name', ''),
            status=data.get('status', 'up'),
            latency_ms=data.get('latency_ms', 0),
            bandwidth_mbps=data.get('bandwidth_mbps', 0),
            isp_id=data.get('isp_id')
        )
        return jsonify({'id': doc_id, 'message': 'ISP status updated'}), 201

    @app.route('/api/institutional/compliance/exam-mode', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def set_exam_mode():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        doc_id = dashboard_service.set_exam_mode(
            institution_id=institution_id,
            active=data.get('active', False),
            exam_type=data.get('exam_type'),
            gce_candidates=data.get('gce_candidates', 0),
            exam_id=data.get('exam_id')
        )
        return jsonify({'id': doc_id, 'message': 'Exam mode updated'}), 201

    @app.route('/api/institutional/payments/transaction', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def create_transaction():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        doc_id = dashboard_service.create_transaction(
            institution_id=institution_id,
            phone=data.get('phone', ''),
            amount_xaf=data.get('amount_xaf', 0),
            provider=data.get('provider', ''),
            status=data.get('status', 'pending')
        )
        return jsonify({'id': doc_id, 'message': 'Transaction created'}), 201

    @app.route('/api/institutional/p2p/peer', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def upsert_p2p_peer():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        doc_id = dashboard_service.upsert_p2p_peer(
            institution_id=institution_id,
            address=data.get('address', ''),
            status=data.get('status', 'online'),
            latency_ms=data.get('latency_ms', 0),
            blocks_synced=data.get('blocks_synced', 0),
            peer_id=data.get('peer_id')
        )
        return jsonify({'id': doc_id, 'message': 'P2P peer saved'}), 201

    @app.route('/api/institutional/seed-demo', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def seed_demo_data():
        """Seed comprehensive demo data for the dashboard."""
        try:
            from src.application.dashboard_seeder import seed_comprehensive_demo_data
            institution_id = request.current_user.get('institution_id', 'inst_001')
            result = seed_comprehensive_demo_data(firebase_service, institution_id)
            return jsonify(result), 201
        except Exception as e:
            logger.error(f"Demo seed error: {str(e)}")
            return jsonify({'error': f'Seeding failed: {str(e)}'}), 500

    # ── USER MANAGEMENT API ──

    @app.route('/api/institutional/users')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_users():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str)
        result = dashboard_service.list_users(institution_id, search=search, page=page, per_page=per_page) if dashboard_service else {'users': [], 'total': 0, 'page': 1, 'per_page': 20, 'total_pages': 1}
        return jsonify(result)

    @app.route('/api/institutional/users', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_create_user():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        user_id = dashboard_service.create_user(institution_id, data) if dashboard_service else None
        if not user_id:
            return jsonify({'error': 'Failed to create user'}), 500
        return jsonify({'id': user_id, 'message': 'User created'}), 201

    @app.route('/api/institutional/users/<user_id>', methods=['PUT'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_update_user(user_id):
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        ok = dashboard_service.update_user(user_id, data) if dashboard_service else False
        if not ok:
            return jsonify({'error': 'User not found'}), 404
        return jsonify({'message': 'User updated'})

    @app.route('/api/institutional/users/<user_id>/toggle-status', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_toggle_user(user_id):
        ok = dashboard_service.toggle_user_status(user_id) if dashboard_service else False
        if not ok:
            return jsonify({'error': 'User not found'}), 404
        return jsonify({'message': 'User status toggled'})
    @app.route('/api/institutional/users/<user_id>', methods=['DELETE'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_delete_user(user_id):
        """Delete a user"""
        try:
            ok = dashboard_service.delete_user(user_id) if dashboard_service else False
            if not ok:
                return jsonify({'error': 'User not found'}), 404
            return jsonify({'message': 'User deleted'}), 200
        except Exception as e:
            logger.error(f"User deletion error: {str(e)}")
            return jsonify({'error': 'Failed to delete user'}), 500


    # ── COURSE MANAGEMENT API ──

    @app.route('/api/institutional/courses')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def institutional_courses():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str)
        result = dashboard_service.list_courses(institution_id, search=search, page=page, per_page=per_page) if dashboard_service else {'courses': [], 'total': 0, 'page': 1, 'per_page': 20, 'total_pages': 1}
        return jsonify(result)

    @app.route('/api/institutional/courses', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_create_course():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        course_id = dashboard_service.create_course(institution_id, data) if dashboard_service else None
        if not course_id:
            return jsonify({'error': 'Failed to create course'}), 500
        return jsonify({'id': course_id, 'message': 'Course created'}), 201

    @app.route('/api/institutional/courses/<course_id>', methods=['PUT'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_update_course(course_id):
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        ok = dashboard_service.update_course(course_id, data) if dashboard_service else False
        if not ok:
            return jsonify({'error': 'Course not found'}), 404
        return jsonify({'message': 'Course updated'})

    @app.route('/api/institutional/courses/<course_id>', methods=['DELETE'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_delete_course(course_id):
        ok = dashboard_service.delete_course(course_id) if dashboard_service else False
        if not ok:
            return jsonify({'error': 'Course not found'}), 404
        return jsonify({'message': 'Course deleted'})

    # ── DEPARTMENT MANAGEMENT API ──

    @app.route('/api/institutional/departments')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_departments():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str)
        result = dashboard_service.list_departments(institution_id, search=search, page=page, per_page=per_page) if dashboard_service else {'departments': [], 'total': 0, 'page': 1, 'per_page': 20, 'total_pages': 1}
        return jsonify(result)

    @app.route('/api/institutional/departments', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_create_department():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        dept_id = dashboard_service.create_department(institution_id, data) if dashboard_service else None
        if not dept_id:
            return jsonify({'error': 'Failed to create department'}), 500
        return jsonify({'id': dept_id, 'message': 'Department created'}), 201

    @app.route('/api/institutional/departments/<dept_id>', methods=['PUT'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_update_department(dept_id):
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        ok = dashboard_service.update_department(dept_id, data) if dashboard_service else False
        if not ok:
            return jsonify({'error': 'Department not found'}), 404
        return jsonify({'message': 'Department updated'})

    @app.route('/api/institutional/departments/<dept_id>', methods=['DELETE'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_delete_department(dept_id):
        ok = dashboard_service.delete_department(dept_id) if dashboard_service else False
        if not ok:
            return jsonify({'error': 'Department not found'}), 404
        return jsonify({'message': 'Department deleted'})

    # ── ENROLLMENT MANAGEMENT API ──

    @app.route('/api/institutional/enrollments')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_enrollments():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str)
        result = dashboard_service.list_enrollments(institution_id, search=search, page=page, per_page=per_page) if dashboard_service else {'enrollments': [], 'total': 0, 'page': 1, 'per_page': 20, 'total_pages': 1}
        return jsonify(result)

    @app.route('/api/institutional/enrollments', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_create_enrollment():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        enrollment_id = dashboard_service.create_enrollment(institution_id, data) if dashboard_service else None
        if not enrollment_id:
            return jsonify({'error': 'Failed to create enrollment'}), 500
        return jsonify({'id': enrollment_id, 'message': 'Enrollment created'}), 201

    @app.route('/api/institutional/enrollments/<enrollment_id>', methods=['DELETE'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_delete_enrollment(enrollment_id):
        ok = dashboard_service.delete_enrollment(enrollment_id) if dashboard_service else False
        if not ok:
            return jsonify({'error': 'Enrollment not found'}), 404
        return jsonify({'message': 'Enrollment deleted'})

    # ── LOOKUP HELPERS ──

    @app.route('/api/institutional/lookup/lecturers')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_lookup_lecturers():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        lecturers = dashboard_service.list_lecturers(institution_id) if dashboard_service else []
        return jsonify({'lecturers': lecturers})

    @app.route('/api/institutional/lookup/departments')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_lookup_departments():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        result = dashboard_service.list_departments(institution_id) if dashboard_service else {'departments': []}
        return jsonify(result)

    @app.route('/api/institutional/lookup/courses')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_lookup_courses():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        result = dashboard_service.list_courses(institution_id, per_page=999) if dashboard_service else {'courses': []}
        return jsonify(result)

    @app.route('/api/institutional/lookup/students')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_lookup_students():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        search = request.args.get('search', '', type=str)
        result = dashboard_service.list_users(institution_id, search=search, per_page=50) if dashboard_service else {'users': []}
        # Filter to students only
        students = [u for u in result.get('users', []) if u.get('role') == 'student']
        return jsonify({'students': students})

    # ── PHASE D: MINESEC XML, SMS, MOBILE MONEY ──

    @app.route('/api/reports/minesec-xml')
    @require_auth
    @require_role('institutional_admin', 'super_admin', 'lecturer')
    @log_access
    def minesec_xml_report():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        from src.application.report_service import ReportService
        rs = ReportService(firebase_service)
        xml_bytes = rs.generate_minesec_xml(institution_id)
        if not xml_bytes:
            return jsonify({'error': 'Failed to generate MINESEC XML report'}), 500
        from flask import Response as FlaskResponse
        return FlaskResponse(
            xml_bytes,
            mimetype='application/xml',
            headers={
                'Content-Disposition': f'attachment; filename=minesec_report_{institution_id}.xml',
                'Content-Type': 'application/xml; charset=utf-8',
            }
        )

    @app.route('/api/institutional/sms/send', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_send_sms():
        data = request.get_json()
        if not data or not data.get('to') or not data.get('message'):
            return jsonify({'error': 'Phone number and message are required'}), 400
        to = data['to']
        message = data['message']
        priority = data.get('priority', 'normal')
        if sms_service:
            result = sms_service.send_sms(to, message, priority)
            return jsonify(result)
        return jsonify({'error': 'SMS service unavailable'}), 503

    @app.route('/api/institutional/sms/queue', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_queue_sms():
        data = request.get_json()
        if not data or not data.get('to') or not data.get('message'):
            return jsonify({'error': 'Phone number and message are required'}), 400
        if sms_service:
            result = sms_service.queue_sms(data['to'], data['message'], data.get('priority', 'normal'))
            return jsonify(result), 201
        return jsonify({'error': 'SMS service unavailable'}), 503

    @app.route('/api/institutional/sms/queue/process', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_process_sms_queue():
        if sms_service:
            sent = sms_service.process_queue()
            stats = sms_service.get_queue_stats()
            return jsonify({'sent': sent, 'stats': stats})
        return jsonify({'error': 'SMS service unavailable'}), 503

    @app.route('/api/institutional/sms/stats')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_sms_stats():
        if sms_service:
            return jsonify(sms_service.get_queue_stats())
        return jsonify({'queued': 0, 'sent': 0, 'failed': 0, 'total': 0})

    @app.route('/api/institutional/payments/initiate', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_initiate_payment():
        data = request.get_json()
        if not data or not data.get('provider') or not data.get('phone') or not data.get('amount'):
            return jsonify({'error': 'Provider, phone, and amount are required'}), 400
        if payment_service:
            result = payment_service.initiate_payment(
                provider=data['provider'],
                phone=data['phone'],
                amount=int(data['amount']),
                reference=data.get('reference', ''),
                description=data.get('description', ''),
            )
            return jsonify(result)
        return jsonify({'error': 'Payment service unavailable'}), 503

    @app.route('/api/institutional/payments/confirm', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_confirm_payment():
        data = request.get_json()
        if not data or not data.get('transaction_id'):
            return jsonify({'error': 'Transaction ID is required'}), 400
        if payment_service:
            result = payment_service.confirm_payment(
                transaction_id=data['transaction_id'],
                provider_ref=data.get('provider_reference', ''),
            )
            return jsonify(result)
        return jsonify({'error': 'Payment service unavailable'}), 503

    @app.route('/api/institutional/payments/providers')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_payment_providers():
        if payment_service:
            return jsonify({'providers': payment_service.get_provider_status()})
        return jsonify({'providers': []})

    @app.route('/api/institutional/translations/extended')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_translations_extended():
        lang = request.args.get('lang', 'en')
        from src.application.bilingual import TRANSLATIONS
        result = {}
        for key, val in TRANSLATIONS.items():
            result[key] = val.get(lang, val.get('en', key))
        return jsonify(result)

    @app.route('/lecturer/dashboard')
    def lecturer_dashboard():
        """Lecturer Dashboard"""
        return render_template('lecturer/dashboard.html')
    
    @app.route('/student/dashboard')
    def student_dashboard():
        """Student Dashboard"""
        return render_template('student/dashboard.html')
    
    @app.route('/api/student/dashboard', methods=['GET'])
    @require_auth
    @require_role('student')
    @log_access
    def api_student_dashboard():
        """Student dashboard data API"""
        try:
            user_id = request.current_user.get('user_id')
            inst_id = request.current_user.get('institution_id', '')
            if student_dashboard_service is None:
                return jsonify({'error': 'Service not available'}), 503
            data = student_dashboard_service.get_dashboard_data(user_id, inst_id)
            return jsonify(data), 200
        except Exception as e:
            logger.error(f"Student dashboard API error: {str(e)}")
            return jsonify({'error': 'Failed to load dashboard'}), 500

    @app.route('/api/student/attendance-history', methods=['GET'])
    @require_auth
    @require_role('student')
    @log_access
    def api_student_attendance_history():
        """Student attendance history"""
        try:
            user_id = request.current_user.get('user_id')
            inst_id = request.current_user.get('institution_id', '')
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            if student_dashboard_service is None:
                return jsonify({'error': 'Service not available'}), 503
            data = student_dashboard_service.get_attendance_history(user_id, inst_id, page, per_page)
            return jsonify(data), 200
        except Exception as e:
            logger.error(f"Attendance history API error: {str(e)}")
            return jsonify({'error': 'Failed to load history'}), 500

    @app.route('/api/student/schedule', methods=['GET'])
    @require_auth
    @require_role('student')
    @log_access
    def api_student_schedule():
        """Student class schedule"""
        try:
            inst_id = request.current_user.get('institution_id', '')
            if student_dashboard_service is None:
                return jsonify({'error': 'Service not available'}), 503
            sessions = student_dashboard_service.get_schedule(request.current_user.get('user_id'), inst_id)
            return jsonify({'sessions': sessions}), 200
        except Exception as e:
            logger.error(f"Schedule API error: {str(e)}")
            return jsonify({'error': 'Failed to load schedule'}), 500

    @app.route('/api/student/analytics', methods=['GET'])
    @require_auth
    @require_role('student')
    @log_access
    def api_student_analytics():
        """Student attendance analytics"""
        try:
            user_id = request.current_user.get('user_id')
            inst_id = request.current_user.get('institution_id', '')
            if student_dashboard_service is None:
                return jsonify({'error': 'Service not available'}), 503
            data = student_dashboard_service.get_analytics(user_id, inst_id)
            return jsonify(data), 200
        except Exception as e:
            logger.error(f"Analytics API error: {str(e)}")
            return jsonify({'error': 'Failed to load analytics'}), 500

    @app.route('/api/student/security', methods=['GET'])
    @require_auth
    @require_role('student')
    @log_access
    def api_student_security():
        """Student security data (devices, events)"""
        try:
            user_id = request.current_user.get('user_id')
            inst_id = request.current_user.get('institution_id', '')
            if student_dashboard_service is None:
                return jsonify({'error': 'Service not available'}), 503
            data = student_dashboard_service.get_security_data(user_id, inst_id)
            return jsonify(data), 200
        except Exception as e:
            logger.error(f"Security data API error: {str(e)}")
            return jsonify({'error': 'Failed to load security data'}), 500

    @app.route('/api/student/verify-scan', methods=['POST'])
    @require_auth
    @require_role('student')
    @log_access
    def api_student_verify_scan():
        """Verify a session code before marking attendance"""
        try:
            data = request.get_json()
            session_code = data.get('session_code', '')
            device_fingerprint = data.get('device_fingerprint', '')
            if not session_code:
                return jsonify({'error': 'Session code required'}), 400
            if student_dashboard_service is None:
                return jsonify({'error': 'Service not available'}), 503
            result = student_dashboard_service.verify_scan(
                session_code=session_code,
                user_id=request.current_user.get('user_id'),
                device_fingerprint=device_fingerprint
            )
            if 'error' in result:
                return jsonify(result), 400
            return jsonify(result), 200
        except Exception as e:
            logger.error(f"Verify scan error: {str(e)}")
            return jsonify({'error': 'Verification failed'}), 500

    @app.route('/admin/institutions')
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_institutions():
        """Institutions management page"""
        return render_template('admin/institutions.html')
    
    @app.route('/admin/institutions/create')
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_create_institution():
        """Create institution page"""
        return render_template('admin/create_institution.html')
    
    @app.route('/admin/users')
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_users():
        """User management page"""
        return render_template('admin/users.html')
    
    @app.route('/admin/monitoring')
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_monitoring():
        """System monitoring page"""
        return render_template('admin/monitoring.html')
    
    @app.route('/admin/security')
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_security():
        """Security settings page"""
        import os
        template_path = os.path.join(app.template_folder, 'admin', 'security.html')
        print(f"DEBUG: Template path: {template_path}")
        print(f"DEBUG: Template exists: {os.path.exists(template_path)}")
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                content = f.read()
                if "No Security Events Yet" in content:
                    print("DEBUG: Functional content found in template")
                else:
                    print("DEBUG: Placeholder content found in template")
        return render_template('admin/security.html')
    
    @app.route('/admin/backup')
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_backup():
        """Backup & restore page"""
        return render_template('admin/backup.html')
    
    @app.route('/admin/notifications')
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_notifications():
        """Notifications management page"""
        return render_template('admin/notifications.html')
    
    @app.route('/admin/audit')
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_audit():
        """Audit logs page"""
        return render_template('admin/audit.html')
    
    @app.route('/admin/roles')
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_roles():
        """Role assignments page"""
        return render_template('admin/roles.html')
    
    @app.route('/admin/profile')
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_profile():
        """Admin profile page"""
        return render_template('admin/profile.html')
    
    @app.route('/admin/settings')
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_settings():
        """System settings page"""
        return render_template('admin/settings.html')
    
    @app.route('/admin/reports')
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_reports():
        """Reports page"""
        return render_template('admin/reports.html')
    
    # Fallback route for dashboard access
    @app.route('/<path:path>')
    def fallback_route(path):
        """Fallback route for better error handling"""
        import os as os_mod
        error_template = Path(__file__).parent / 'src' / 'presentation' / 'templates' / 'error.html'
        # Check if this looks like a dashboard route
        if any(path.startswith(prefix) for prefix in ['admin/', 'institutional-admin/', 'lecturer/', 'student/']):
            if error_template.exists():
                return render_template('error.html',
                    error_code=404,
                    error_message="Dashboard not found. Please check your role and permissions.",
                    back_url="/"), 404
            return jsonify({'error': 'Dashboard not found'}), 404
        
        # For other paths, let Flask handle the 404
        return None
    
    # Professional Voucher Management API endpoints
    @app.route('/api/voucher/validate/<code>', methods=['GET'])
    @log_access
    def validate_voucher(code):
        """Professional voucher validation endpoint for new signup"""
        try:
            from src.application.voucher_management_service import VoucherManagementService
            voucher_service = VoucherManagementService(firebase_service)
            
            # For the new signup flow, we need to validate voucher exists and get basic info
            # Email and role will be provided during registration
            
            # Check voucher format first
            logger.info(f"DEBUG: Received code type: {type(code)}, value: '{code}', repr: {repr(code)}")
            logger.info(f"DEBUG: Validating voucher code: '{code}' (length: {len(code) if code else 'None'})")
            logger.info(f"DEBUG: isalnum: {code.isalnum() if code else 'None'}, isupper: {code.isupper() if code else 'None'}")
            
            # Check each condition separately for debugging
            if code:
                char_list = list(code)
                conditions = {
                    'not code': not code,
                    'len != 8': len(code) != 8,
                    'not alnum': not code.isalnum(),
                    'not upper': not code.isupper(),
                    'char_list': char_list,
                    'actual_length': len(code)
                }
                logger.info(f"DEBUG: Validation conditions: {conditions}")
                logger.info(f"DEBUG: Character by character: {[(i, c, ord(c)) for i, c in enumerate(char_list)]}")
            else:
                logger.info(f"DEBUG: Code is None or empty")
            
            if not code or len(code) != 8 or not code.isalnum() or not code.isupper():
                logger.warning(f"DEBUG: Voucher format validation failed for: '{code}'")
                return jsonify({
                    'valid': False,
                    'error': 'Invalid voucher format',
                    'error_code': 'INVALID_FORMAT'
                }), 200
            
            logger.info(f"DEBUG: Voucher format validation passed for: '{code}'")
            
            # Query voucher from database
            vouchers = voucher_service.firebase_service.query_documents(
                'vouchers',
                filters=[{'field': 'code', 'value': code}]
            )
            
            if not vouchers:
                return jsonify({
                    'valid': False,
                    'error': 'Voucher code not found',
                    'error_code': 'NOT_FOUND'
                }), 200
            
            voucher = vouchers[0]
            
            # Check if already used
            if voucher.get('is_used', False):
                return jsonify({
                    'valid': False,
                    'error': 'Voucher has already been used',
                    'error_code': 'ALREADY_USED'
                }), 200
            
            # Check expiry
            from datetime import datetime
            expiry_date = datetime.fromisoformat(voucher['expires_at'])
            if datetime.utcnow() > expiry_date:
                return jsonify({
                    'valid': False,
                    'error': 'Voucher has expired',
                    'error_code': 'EXPIRED'
                }), 200
            
            # Voucher is valid - return basic info for role-specific form
            return jsonify({
                'valid': True,
                'role': voucher['role'],
                'institution_id': voucher['institution_id'],
                'email_binding': voucher.get('email_binding'),
                'message': 'Voucher is valid for registration'
            }), 200
                
        except Exception as e:
            logger.error(f"Voucher validation error: {str(e)}")
            return jsonify({
                'valid': False,
                'error': 'Voucher validation failed',
                'error_code': 'SYSTEM_ERROR'
            }), 500
    
    @app.route('/api/voucher/generate-batch', methods=['POST'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def generate_voucher_batch():
        """Generate voucher batch for institutional distribution"""
        try:
            data = request.get_json()
            role = data.get('role')
            institution_id = data.get('institution_id')
            quantity = data.get('quantity', 10)
            email_binding = data.get('email_binding')  # Optional
            
            if not role or not institution_id:
                return jsonify({'error': 'Role and institution_id required'}), 400
            
            from src.application.voucher_management_service import VoucherManagementService
            voucher_service = VoucherManagementService(firebase_service)
            
            vouchers = voucher_service.generate_voucher_batch(
                role=UserRole(role),
                institution_id=institution_id,
                quantity=quantity,
                email_binding=email_binding
            )
            
            return jsonify({
                'vouchers': vouchers,
                'message': f'Generated {len(vouchers)} vouchers successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Voucher batch generation error: {str(e)}")
            return jsonify({'error': 'Failed to generate vouchers'}), 500
    
    @app.route('/api/voucher/statistics/<institution_id>', methods=['GET'])
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def get_voucher_statistics(institution_id):
        """Get voucher usage statistics"""
        try:
            from src.application.voucher_management_service import VoucherManagementService
            voucher_service = VoucherManagementService(firebase_service)
            
            stats = voucher_service.get_voucher_statistics(institution_id)
            
            return jsonify(stats), 200
            
        except Exception as e:
            logger.error(f"Voucher statistics error: {str(e)}")
            return jsonify({'error': 'Failed to get statistics'}), 500
    
    @app.route('/offline')
    def offline_page():
        return render_template('offline.html')

    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    @app.route('/system/bootstrap', methods=['POST'])
    def bootstrap():
        """First-run bootstrap: create initial admin user if no users exist."""
        try:
            existing = firebase_service.query_documents('users', limit=1)
            if existing:
                return jsonify({'error': 'System already bootstrapped'}), 400

            data = request.get_json() or {}
            email = data.get('email', 'admin@attendrix.demo')
            password = data.get('password', 'password123')
            first_name = data.get('first_name', 'Admin')
            last_name = data.get('last_name', 'User')

            from src.domain.entities import UserRole
            user = auth_service.register_user(
                email=email, password=password,
                first_name=first_name, last_name=last_name,
                role=UserRole.SUPER_ADMIN,
                institution_id='inst_001',
                voucher_code=None
            )

            from src.application.voucher_seeder import VoucherSeeder
            seeder = VoucherSeeder(firebase_service)
            seeder.generate_seed_vouchers()

            return jsonify({
                'success': True,
                'message': 'Admin user created. You can now log in.',
                'email': email
            }), 201

        except Exception as e:
            logger.error(f"Bootstrap error: {str(e)}")
            return jsonify({'error': f'Bootstrap failed: {str(e)}'}), 500

    @app.route('/system/voucher/seed', methods=['POST'])
    @require_auth
    @require_role('super_admin')
    @log_access
    def seed_vouchers():
        """System bootstrap - generate initial seed vouchers and demo users"""
        try:
            from src.application.voucher_seeder import VoucherSeeder
            from src.domain.entities import UserRole
            voucher_seeder = VoucherSeeder(firebase_service)

            existing = voucher_seeder.check_existing_vouchers()
            if existing['exists'] and existing['count'] > 0:
                return jsonify({'success': False, 'message': 'Vouchers already exist', 'existing_count': existing['count']}), 400

            result = voucher_seeder.generate_seed_vouchers()
            if not result['success']:
                return jsonify(result), 500

            # Create demo users with known passwords
            demo_users = [
                {'email': 'admin@attendrix.demo', 'password': 'password123', 'first_name': 'Admin', 'last_name': 'User', 'role': UserRole.INSTITUTIONAL_ADMIN, 'voucher': 'ADMIN123'},
                {'email': 'lecturer1@attendrix.demo', 'password': 'password123', 'first_name': 'John', 'last_name': 'Doe', 'role': UserRole.LECTURER, 'voucher': 'LECT4567'},
                {'email': 'student1@attendrix.demo', 'password': 'password123', 'first_name': 'Jane', 'last_name': 'Smith', 'role': UserRole.STUDENT, 'voucher': 'STUD7890'},
            ]

            created_users = []
            for user in demo_users:
                try:
                    u = auth_service.register_user(
                        email=user['email'],
                        password=user['password'],
                        first_name=user['first_name'],
                        last_name=user['last_name'],
                        role=user['role'],
                        institution_id='inst_001',
                        voucher_code=user['voucher']
                    )
                    created_users.append({'email': user['email'], 'role': user['role'].value})
                except Exception as e:
                    logger.warning(f"Failed to create demo user {user['email']}: {str(e)}")

            test_vouchers = voucher_seeder.get_test_vouchers()

            return jsonify({
                'success': True,
                'message': f'Seeded {result["vouchers_created"]} vouchers and {len(created_users)} demo users',
                'vouchers_created': result['vouchers_created'],
                'demo_users_created': len(created_users),
                'demo_credentials': {'password': 'password123'},
                'test_vouchers': test_vouchers,
                'voucher_details': result['vouchers']
            }), 200

        except Exception as e:
            logger.error(f"Voucher seeding error: {str(e)}")
            return jsonify({'error': 'Failed to seed vouchers'}), 500
    
    @app.route('/system/voucher/force-reseed', methods=['POST'])
    @require_auth
    @require_role('super_admin')
    @log_access
    def force_reseed_vouchers():
        """Force reseed vouchers - override existing"""
        try:
            from src.application.voucher_seeder import VoucherSeeder
            voucher_seeder = VoucherSeeder(firebase_service)
            
            # Clear existing vouchers by deleting all documents
            vouchers = firebase_service.query_documents('vouchers', limit=100)
            for voucher in vouchers:
                firebase_service.delete_document('vouchers', voucher['id'])
            
            # Generate new seed vouchers
            result = voucher_seeder.generate_seed_vouchers()
            
            if result['success']:
                # Get test vouchers for immediate use
                test_vouchers = voucher_seeder.get_test_vouchers()
                
                return jsonify({
                    'success': True,
                    'message': 'Force reseed completed',
                    'vouchers_created': result['vouchers_created'],
                    'test_vouchers': test_vouchers,
                    'voucher_details': result['vouchers']
                }), 200
            else:
                return jsonify(result), 500
                
        except Exception as e:
            logger.error(f"Force reseed error: {str(e)}")
            return jsonify({'error': 'Failed to force reseed vouchers'}), 500
    
    @app.route('/system/voucher/check', methods=['GET'])
    @require_auth
    @require_role('super_admin')
    @log_access
    def check_voucher_status():
        """Check voucher system status"""
        try:
            from src.application.voucher_seeder import VoucherSeeder
            voucher_seeder = VoucherSeeder(firebase_service)
            
            status = voucher_seeder.check_existing_vouchers()
            test_vouchers = voucher_seeder.get_test_vouchers()
            
            return jsonify({
                'system_status': 'operational',
                'voucher_table_exists': True,
                'vouchers_exist': status['exists'],
                'voucher_count': status['count'],
                'test_vouchers_available': len(test_vouchers),
                'test_vouchers': test_vouchers,
                'voucher_details': status.get('sample', []),
                'message': 'Voucher system is ready' if status['exists'] else 'System needs seeding'
            }), 200
            
        except Exception as e:
            logger.error(f"Voucher status check error: {str(e)}")
            return jsonify({'error': 'Failed to check voucher status'}), 500
    
    @app.route('/system/voucher/debug', methods=['GET'])
    @require_auth
    @require_role('super_admin')
    @log_access
    def debug_vouchers():
        """Debug endpoint to see all vouchers in database"""
        try:
            vouchers = firebase_service.query_documents('vouchers', limit=50)
            
            return jsonify({
                'debug_info': 'All vouchers in database',
                'voucher_count': len(vouchers),
                'vouchers': vouchers
            }), 200
            
        except Exception as e:
            logger.error(f"Voucher debug error: {str(e)}")
            return jsonify({'error': 'Failed to debug vouchers'}), 500

    # API documentation route
    @app.route('/api/docs')
    def api_docs():
        """API documentation"""
        return jsonify({
            'title': 'Attendrix API',
            'version': '1.0.0',
            'description': 'Enterprise Institutional Paperless Attendance System API',
            'endpoints': {
                'authentication': {
                    'POST /api/auth/register': 'Register new user',
                    'POST /api/auth/login': 'User login',
                    'POST /api/auth/refresh': 'Refresh access token',
                    'POST /api/auth/logout': 'User logout'
                },
                'scheduling': {
                    'POST /api/schedules': 'Create schedule',
                    'GET /api/schedules/{id}/conflicts': 'Check schedule conflicts'
                },
                'attendance': {
                    'POST /api/attendance/sessions': 'Create attendance session',
                    'POST /api/attendance/mark': 'Mark attendance',
                    'GET /api/attendance/sessions/{id}/statistics': 'Get session statistics'
                },
                'user': {
                    'GET /api/users/profile': 'Get user profile'
                },
                'dashboard': {
                    'GET /api/dashboard': 'Get dashboard data'
                }
            }
        })
    
    return app


# Application factory
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    # Force debug and reloader
    debug = True
    use_reloader = True
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=use_reloader
    )
