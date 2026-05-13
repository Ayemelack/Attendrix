from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
from datetime import datetime, timedelta
import logging

# Import configuration
from config.settings import get_config

# Import infrastructure services
from src.infrastructure.firebase_service import firebase_service

# Import application services
from src.application.rbac import require_auth, require_role, log_access

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
        # Pass mock setting from config to environ so firebase_service can read it
        os.environ['USE_MOCK_FIREBASE'] = app.config.get('USE_MOCK_FIREBASE', 'true')
        
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

    # Auto-seed demo data on first startup (development mode only)
    if app.config.get('ENVIRONMENT', 'development') == 'development' and auth_service:
        try:
            existing = firebase_service.query_documents('users', limit=1)
            if not existing:
                logger.info("No users found — auto-seeding demo data for development...")
                from src.application.voucher_seeder import VoucherSeeder
                from src.domain.entities import UserRole

                seeder = VoucherSeeder(firebase_service)
                seeder.generate_seed_vouchers()

                demo_users = [
                    {'email': 'admin@attendrix.demo', 'password': 'password123', 'first_name': 'Admin', 'last_name': 'User', 'role': UserRole.INSTITUTIONAL_ADMIN, 'voucher': 'ADMIN123'},
                    {'email': 'lecturer1@attendrix.demo', 'password': 'password123', 'first_name': 'John', 'last_name': 'Doe', 'role': UserRole.LECTURER, 'voucher': 'LECT4567'},
                    {'email': 'student1@attendrix.demo', 'password': 'password123', 'first_name': 'Jane', 'last_name': 'Smith', 'role': UserRole.STUDENT, 'voucher': 'STUD7890'},
                ]
                # Register extra student users for richer dashboard data
                student_voucher_codes = ['STUD7900', 'STUD7901', 'STUD7902', 'STUD7903', 'STUD7904',
                                         'STUD7905', 'STUD7906', 'STUD7907', 'STUD7908', 'STUD7909']
                extra_students = [
                    ('alice@attendrix.demo', 'Alice', 'Ndefru'),
                    ('bob@attendrix.demo', 'Bob', 'Tataw'),
                    ('carol@attendrix.demo', 'Carol', 'Ayuk'),
                    ('david@attendrix.demo', 'David', 'Nkwi'),
                    ('eve@attendrix.demo', 'Eve', 'Mbah'),
                    ('frank@attendrix.demo', 'Frank', 'Asaah'),
                    ('grace@attendrix.demo', 'Grace', 'Kum'),
                    ('henry@attendrix.demo', 'Henry', 'Ndifor'),
                    ('iris@attendrix.demo', 'Iris', 'Lum'),
                    ('jack@attendrix.demo', 'Jack', 'Njini'),
                ]
                for idx, (email, fn, ln) in enumerate(extra_students):
                    demo_users.append(
                        {'email': email, 'password': 'password123', 'first_name': fn, 'last_name': ln,
                         'role': UserRole.STUDENT, 'voucher': student_voucher_codes[idx]}
                    )

                created = 0
                for u in demo_users:
                    try:
                        voucher_code = u.get('voucher')
                        # Create a voucher for this user if it doesn't exist yet
                        if voucher_code and not firebase_service.query_documents(
                            'vouchers', filters=[{'field': 'code', 'value': voucher_code}]
                        ):
                            from src.application.voucher_management_service import VoucherManagementService
                            vm = VoucherManagementService(firebase_service)
                            vm.generate_voucher_batch(
                                role=u['role'], institution_id='inst_001',
                                quantity=1, email_binding=u['email'],
                                fixed_code=voucher_code
                            )
                        auth_service.register_user(
                            email=u['email'], password=u['password'],
                            first_name=u['first_name'], last_name=u['last_name'],
                            role=u['role'], institution_id='inst_001',
                            voucher_code=voucher_code
                        )
                        created += 1
                    except ValueError as ve:
                        logger.warning(f"Auto-seed user {u['email']}: {ve}")
                    except Exception as ue:
                        logger.warning(f"Auto-seed user {u['email']} failed: {ue}")
                logger.info(f"Auto-seed complete: {len(demo_users)} vouchers, {created} demo users")

                # Seed comprehensive dashboard demo data
                try:
                    from src.application.dashboard_seeder import seed_comprehensive_demo_data
                    seed_result = seed_comprehensive_demo_data(firebase_service, 'inst_001')
                    logger.info(f"Dashboard demo data seeded: {seed_result.get('total_documents_created', 0)} documents")
                except Exception as dse:
                    logger.warning(f"Dashboard data seeding skipped: {dse}")
        except Exception as seed_err:
            logger.warning(f"Auto-seeding skipped: {seed_err}")

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
            
            from src.infrastructure.repositories import user_repo
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
    @require_auth
    @require_role('super_admin')
    @log_access
    def admin_dashboard():
        """Hidden System Administration - PRIVATE ROUTE"""
        return render_template('admin/dashboard.html')
    
    @app.route('/institutional-admin/dashboard')
    @require_auth
    @require_role('institutional_admin')
    @log_access
    def institutional_admin_dashboard():
        """Institutional Administrator Dashboard"""
        return render_template('institutional-admin/dashboard.html')

    # ── Institutional Admin API Endpoints ──
    @app.route('/api/institutional/activity-feed')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_activity_feed():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        events = dashboard_service.get_activity_feed(institution_id) if dashboard_service else []
        return jsonify({'events': events})

    @app.route('/api/institutional/security-alerts')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_security_alerts():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        alerts = dashboard_service.get_security_alerts(institution_id) if dashboard_service else []
        return jsonify({'alerts': alerts})

    @app.route('/api/institutional/network-status')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_network_status():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = dashboard_service.get_network_status(institution_id) if dashboard_service else {}
        return jsonify(data)

    @app.route('/api/institutional/session-health')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_session_health():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = dashboard_service.get_session_health(institution_id) if dashboard_service else {'active_sessions': 0, 'total_sessions': 0, 'sessions': []}
        return jsonify(data)

    @app.route('/api/institutional/attendance-trends')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_attendance_trends():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = dashboard_service.get_attendance_trends(institution_id) if dashboard_service else {'daily_rates': [], 'dates': [], 'average': 0, 'faculty_comparison': []}
        return jsonify(data)

    @app.route('/api/institutional/students')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_students():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        students = dashboard_service.get_students_with_risk(institution_id) if dashboard_service else []
        return jsonify({'students': students})

    @app.route('/api/institutional/offline-log')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
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
        data = dashboard_service.get_payment_status(institution_id) if dashboard_service else {}
        return jsonify(data)

    @app.route('/api/institutional/p2p-sync')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_p2p_sync():
        institution_id = request.current_user.get('institution_id', 'inst_001')
        data = dashboard_service.get_p2p_sync_status(institution_id) if dashboard_service else {}
        return jsonify(data)

    @app.route('/api/institutional/quick-actions')
    @require_auth
    @require_role('institutional_admin', 'super_admin')
    @log_access
    def institutional_quick_actions():
        actions = dashboard_service.get_quick_actions() if dashboard_service else []
        return jsonify({'actions': actions})

    @app.route('/api/institutional/translations')
    @log_access
    def institutional_translations():
        lang = request.args.get('lang', 'en')
        data = dashboard_service.get_translations(lang) if dashboard_service else {}
        return jsonify(data)

    # ── DATA CREATION / MANAGEMENT ENDPOINTS ──

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
    @require_role('institutional_admin', 'super_admin')
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

    @app.route('/lecturer/dashboard')
    @require_auth
    @require_role('lecturer')
    @log_access
    def lecturer_dashboard():
        """Lecturer Dashboard"""
        return render_template('lecturer/dashboard.html')
    
    @app.route('/student/dashboard')
    @require_auth
    @require_role('student')
    @log_access
    def student_dashboard():
        """Student Dashboard"""
        return render_template('student/dashboard.html')
    
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
        return render_template('admin/security.html')
    
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
    
    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    @app.route('/system/voucher/seed', methods=['POST'])
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
                
        except Exception as e:
            logger.error(f"Voucher seeding error: {str(e)}")
            return jsonify({'error': 'Failed to seed vouchers'}), 500
    
    @app.route('/system/voucher/force-reseed', methods=['POST'])
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
