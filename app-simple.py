from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_simple_app():
    """Simple Flask app for initial testing"""
    app = Flask(__name__, 
                template_folder='src/presentation/templates',
                static_folder='src/presentation/static')
    
    # Basic configuration
    app.config['SECRET_KEY'] = 'dev-secret-key-for-testing'
    app.config['DEBUG'] = True
    
    # Disable static file caching for development
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.config['CACHE_TYPE'] = 'null'
    
    # Enable CORS
    CORS(app)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    # Routes
    @app.route('/')
    def landing():
        """Landing page"""
        try:
            return render_template('landing.html')
        except Exception as e:
            logger.error(f"Template error: {str(e)}")
            logger.error(f"Template folder: {app.template_folder}")
            logger.error(f"Current working directory: {os.getcwd()}")
            return jsonify({
                'error': 'Template not found',
                'message': str(e),
                'template_folder': app.template_folder,
                'status': 'error'
            }), 500
    
    @app.route('/login')
    def login():
        """Login page"""
        try:
            return render_template('login.html')
        except Exception as e:
            logger.error(f"Login template error: {str(e)}")
            return jsonify({
                'error': 'Login page not found',
                'message': str(e),
                'template_folder': app.template_folder,
                'status': 'error'
            }), 500
    
    @app.route('/api/auth/login', methods=['POST'])
    def api_login():
        """API login endpoint"""
        try:
            data = request.get_json()
            
            email = data.get('email')
            password = data.get('password')
            institution_id = data.get('institutionId')  # Match form field name
            
            # Basic validation
            if not email or not password or not institution_id:
                return jsonify({
                    'error': 'Email, password, and institution ID are required'
                }), 400
            
            # Authenticate real user accounts created via Sign-Up
            # In production, this would query database or Firebase
            # For demo, use in-memory user storage
            
            # Check if user exists in our "database" (in-memory for demo)
            user = None
            if hasattr(app, 'users_db') and email in app.users_db:
                user = app.users_db[email]
            
            if not user:
                return jsonify({
                    'error': 'Invalid email, password, or institution ID'
                }), 401
            
            # Verify password
            if user['password'] != password:
                return jsonify({
                    'error': 'Invalid email, password, or institution ID'
                }), 401
            
            # Verify institution ID - normalize both values for comparison
            # Extract the actual institution ID value from user data
            stored_institution_id = user.get('institution_id', 'user-inst')
            login_institution_id = institution_id.strip() if institution_id else ''
            
            # Normalize stored institution ID to match login format
            # Handle different field names and values
            if stored_institution_id == 'user-inst' and login_institution_id == 'user-inst':
                normalized_match = True
            elif stored_institution_id == 'user-inst' and login_institution_id == 'user-inst':
                normalized_match = True
            elif stored_institution_id and login_institution_id:
                # Both have some value but not 'user-inst', check if they match
                normalized_match = stored_institution_id == login_institution_id
            elif stored_institution_id and login_institution_id:
                # Both have some value but not 'user-inst', check if they match
                normalized_match = stored_institution_id == login_institution_id
            else:
                normalized_match = False
            
            if not normalized_match:
                return jsonify({
                    'error': 'Invalid email, password, or institution ID'
                }), 401
            
            # Successful authentication
            return jsonify({
                'message': 'Login successful',
                'user': {
                    'id': user['id'],
                    'email': user['email'],
                    'role': user['role'],
                    'institution_id': user['institution_id'],
                    'name': f"{user['firstName']} {user['lastName']}"
                },
                'access_token': f"access-token-{user['id']}",
                'refresh_token': f"refresh-token-{user['id']}",
                'token_type': 'Bearer',
                'expires_in': 3600
            }), 200
                
        except Exception as e:
            logger.error(f"Login API error: {str(e)}")
            return jsonify({'error': 'Login failed'}), 500
    
    @app.route('/api/auth/signup', methods=['POST'])
    def api_signup():
        """API signup endpoint"""
        try:
            data = request.get_json()
            
            # Basic validation
            required_fields = ['firstName', 'lastName', 'email', 'password', 'confirmPassword', 'role']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'error': f'{field} is required'}), 400
            
            # Email validation
            email = data.get('email')
            if '@' not in email or '.' not in email:
                return jsonify({'error': 'Invalid email format'}), 400
            
            # Password validation
            password = data.get('password')
            confirm_password = data.get('confirmPassword')
            if password != confirm_password:
                return jsonify({'error': 'Passwords do not match'}), 400
            
            if len(password) < 8:
                return jsonify({'error': 'Password must be at least 8 characters long'}), 400
            
            # Role validation
            valid_roles = ['super_administrator', 'institutional_admin', 'lecturer', 'student', 'employee']
            role = data.get('role')
            if role not in valid_roles:
                return jsonify({'error': 'Invalid role selected'}), 400
            
            # For demo, simulate successful account creation
            user_id = f"user_{len(email)}_{hash(email[:10])}"
            
            # Store user in in-memory database (for demo purposes)
            if not hasattr(app, 'users_db'):
                app.users_db = {}
            
            app.users_db[email] = {
                'id': user_id,
                'firstName': data.get('firstName'),
                'lastName': data.get('lastName'),
                'email': email,
                'password': data.get('password'),  # In production, this would be hashed
                'role': data.get('role'),
                'institutionName': data.get('institutionName', ''),
                'institution_id': data.get('institutionId', 'user-inst'),  # Use form field value
                'created_at': datetime.utcnow().isoformat()
            }
            
            return jsonify({
                'message': 'Your account has been successfully created.',
                'user': {
                    'id': user_id,
                    'firstName': data.get('firstName'),
                    'lastName': data.get('lastName'),
                    'email': email,
                    'role': data.get('role'),
                    'institutionName': data.get('institutionName', ''),
                    'created_at': datetime.utcnow().isoformat()
                }
            }), 201
            
        except Exception as e:
            logger.error(f"Signup API error: {str(e)}")
            return jsonify({'error': 'Account creation failed'}), 500
    
    @app.route('/dashboard')
    def dashboard():
        """Role-based dashboard after login"""
        try:
            # Check for JWT token or session to determine user role
            # For development, check if user is logged in and redirect based on role
            # In a real implementation, this would check JWT token and query user from database
            
            # Get user role from request (in production, this would come from JWT token)
            user_role = request.args.get('role', None)
            
            # If no role specified, check for session/cookie or default to lecturer
            if not user_role:
                # For development, we'll default to lecturer to ensure proper routing
                # In production, this would validate JWT token and extract role
                user_role = 'lecturer'
            
            # Role-based template mapping
            role_templates = {
                'super_administrator': 'dashboard.html',  # Use main dashboard as fallback
                'institutional_admin': 'institutional-dashboard.html',  
                'lecturer': 'lecturer-dashboard.html',  # Fixed template name
                'student': 'student-dashboard.html',
                'employee': 'employee-dashboard.html'  # New employee dashboard
            }
            
            # Role-based URL mapping for direct navigation
            role_urls = {
                'super_administrator': '/dashboard?role=super_administrator',
                'institutional_admin': '/institutional-dashboard',
                'lecturer': '/lecturer-dashboard',
                'student': '/dashboard?role=student',
                'employee': '/employee/dashboard'
            }
            
            # For lecturers, always redirect to their dedicated dashboard
            if user_role == 'lecturer':
                return render_template('lecturer-dashboard.html', user_role=user_role)
            
            # For institutional admin, redirect to their dashboard
            elif user_role == 'institutional_admin':
                return render_template('institutional-dashboard.html', user_role=user_role)
            
            # For students, redirect to their dedicated dashboard
            elif user_role == 'student':
                return render_template('student-dashboard.html', user_role=user_role)
            
            # For employees, redirect to their dedicated dashboard
            elif user_role == 'employee':
                return render_template('employee-dashboard.html', user_role=user_role)
            
            # For other roles, try to render their specific template
            template_name = role_templates.get(user_role, 'dashboard.html')
            
            # Check if template exists, fallback to main dashboard
            try:
                return render_template(template_name, user_role=user_role)
            except:
                # Template doesn't exist, use main dashboard
                return render_template('dashboard.html', user_role=user_role)
                
        except Exception as e:
            logger.error(f"Dashboard template error: {str(e)}")
            return jsonify({
                'error': 'Dashboard not found',
                'message': str(e),
                'template_folder': app.template_folder,
                'status': 'error'
            }), 500
    
    @app.route('/signup')
    def signup():
        """Signup page"""
        try:
            return render_template('signup.html')
        except Exception as e:
            logger.error(f"Signup template error: {str(e)}")
            return jsonify({'error': 'Signup page not found'}), 500
    
    @app.route('/demo')
    def demo():
        """Demo request page"""
        try:
            return render_template('demo.html')
        except Exception as e:
            logger.error(f"Demo template error: {str(e)}")
            return jsonify({'error': 'Demo page not found'}), 500
    
    @app.route('/attendance')
    def attendance():
        """Attendance management page"""
        try:
            return render_template('attendance.html')
        except Exception as e:
            logger.error(f"Attendance template error: {str(e)}")
            return jsonify({'error': 'Attendance page not found'}), 500
    
    @app.route('/scheduling')
    def scheduling():
        """Scheduling management page"""
        try:
            return render_template('scheduling.html')
        except Exception as e:
            logger.error(f"Scheduling template error: {str(e)}")
            return jsonify({'error': 'Scheduling page not found'}), 500
    
    @app.route('/analytics')
    def analytics():
        """Analytics dashboard page"""
        try:
            return render_template('analytics.html')
        except Exception as e:
            logger.error(f"Analytics template error: {str(e)}")
            return jsonify({'error': 'Analytics page not found'}), 500
    
    @app.route('/api/admin/system-overview', methods=['GET'])
    def api_admin_system_overview():
        """API endpoint for Super Administrator system overview"""
        try:
            # In production, this would query actual database
            # For demo, return real-time system data
            total_institutions = 0  # Default value - no demo data
            total_users = 0  # Default value - no demo data
            active_sessions = 0  # Default value - no demo data
            
            # Get real user count from in-memory database if available
            if hasattr(app, 'users_db'):
                total_users = len(app.users_db)
            
            return jsonify({
                'totalInstitutions': total_institutions,
                'totalUsers': total_users,
                'activeSessions': active_sessions,
                'systemStatus': 'Running',
                'lastUpdated': datetime.utcnow().isoformat()
            }), 200
            
        except Exception as e:
            logger.error(f"System overview API error: {str(e)}")
            return jsonify({
                'error': 'Failed to load system overview',
                'totalInstitutions': 0,
                'totalUsers': 0,
                'activeSessions': 0,
                'systemStatus': 'Error'
            }), 500
    
    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0-dev',
            'environment': 'development'
        })
    
    # Profile and Settings Routes
    @app.route('/profile')
    def profile():
        """Profile management page"""
        try:
            # Check if user is coming from specific dashboard
            referrer = request.referrer
            user_role = request.args.get('role', None)
            
            # If referrer contains lecturer-dashboard or role is lecturer, set context
            if (referrer and 'lecturer-dashboard' in referrer) or user_role == 'lecturer':
                return render_template('profile.html', user_role='lecturer', return_to='lecturer-dashboard')
            
            # If referrer contains institutional-dashboard or role is institutional_admin, set context
            elif (referrer and 'institutional-dashboard' in referrer) or user_role == 'institutional_admin':
                return render_template('profile.html', user_role='institutional_admin', return_to='institutional-dashboard')
            
            return render_template('profile.html')
        except Exception as e:
            logger.error(f"Profile template error: {str(e)}")
            return jsonify({'error': 'Profile page not found'}), 500
    
    @app.route('/settings')
    def settings():
        """Settings management page"""
        try:
            return render_template('settings.html')
        except Exception as e:
            logger.error(f"Settings template error: {str(e)}")
            return jsonify({'error': 'Settings page not found'}), 500
    
    @app.route('/dashboard-preferences')
    def dashboard_preferences():
        """Dashboard preferences management page"""
        try:
            # Check if user is coming from institutional dashboard
            referrer = request.referrer
            user_role = request.args.get('role', None)
            
            # If referrer contains institutional-dashboard or role is institutional_admin, set context
            if (referrer and 'institutional-dashboard' in referrer) or user_role == 'institutional_admin':
                return render_template('dashboard-preferences.html', user_role='institutional_admin', return_to='institutional-dashboard')
            
            # If referrer contains lecturer-dashboard or role is lecturer, set context
            elif (referrer and 'lecturer-dashboard' in referrer) or user_role == 'lecturer':
                return render_template('dashboard-preferences.html', user_role='lecturer', return_to='lecturer-dashboard')
            
            return render_template('dashboard-preferences.html')
        except Exception as e:
            logger.error(f"Dashboard preferences template error: {str(e)}")
            return jsonify({'error': 'Dashboard preferences page not found'}), 500
    
    @app.route('/institutions')
    def institutions():
        """Institutions management page"""
        try:
            return render_template('institutions.html')
        except Exception as e:
            logger.error(f"Institutions template error: {str(e)}")
            return jsonify({'error': 'Institutions page not found'}), 500
    
    @app.route('/employee/dashboard')
    def employee_dashboard():
        """Employee dashboard page"""
        try:
            return render_template('employee-dashboard.html')
        except Exception as e:
            logger.error(f"Employee dashboard template error: {str(e)}")
            return jsonify({'error': 'Employee dashboard page not found'}), 500
    
    @app.route('/employee/attendance')
    def employee_attendance():
        """Employee attendance page"""
        try:
            return render_template('employee-attendance.html')
        except Exception as e:
            logger.error(f"Employee attendance template error: {str(e)}")
            return jsonify({'error': 'Employee attendance page not found'}), 500
    
    @app.route('/employee/leave')
    def employee_leave():
        """Employee leave management page"""
        try:
            return render_template('employee-leave.html')
        except Exception as e:
            logger.error(f"Employee leave template error: {str(e)}")
            return jsonify({'error': 'Employee leave page not found'}), 500
    
    @app.route('/employee/schedule')
    def employee_schedule():
        """Employee schedule page"""
        try:
            return render_template('employee-schedule.html')
        except Exception as e:
            logger.error(f"Employee schedule template error: {str(e)}")
            return jsonify({'error': 'Employee schedule page not found'}), 500
    
    @app.route('/employee/tasks')
    def employee_tasks():
        """Employee tasks page"""
        try:
            return render_template('employee-tasks.html')
        except Exception as e:
            logger.error(f"Employee tasks template error: {str(e)}")
            return jsonify({'error': 'Employee tasks page not found'}), 500
    
    @app.route('/users')
    def users():
        """Users management page"""
        try:
            return render_template('users.html')
        except Exception as e:
            logger.error(f"Users template error: {str(e)}")
            return jsonify({'error': 'Users page not found'}), 500
    
    @app.route('/student-attendance')
    def student_attendance():
        """Student attendance page"""
        try:
            return render_template('student-attendance.html')
        except Exception as e:
            logger.error(f"Student attendance template error: {str(e)}")
            return jsonify({'error': 'Student attendance page not found'}), 500
    
    @app.route('/student-assignments')
    def student_assignments():
        """Student assignments page"""
        try:
            return render_template('student-assignments.html')
        except Exception as e:
            logger.error(f"Student assignments template error: {str(e)}")
            return jsonify({'error': 'Student assignments page not found'}), 500
    
    @app.route('/student-schedule')
    def student_schedule():
        """Student schedule page"""
        try:
            return render_template('student-schedule.html')
        except Exception as e:
            logger.error(f"Student schedule template error: {str(e)}")
            return jsonify({'error': 'Student schedule page not found'}), 500
    
    @app.route('/student-grades')
    def student_grades():
        """Student grades page"""
        try:
            return render_template('student-grades.html')
        except Exception as e:
            logger.error(f"Student grades template error: {str(e)}")
            return jsonify({'error': 'Student grades page not found'}), 500
    
    @app.route('/monitoring')
    def monitoring():
        """System monitoring page"""
        try:
            return render_template('monitoring.html')
        except Exception as e:
            logger.error(f"Monitoring template error: {str(e)}")
            return jsonify({'error': 'Monitoring page not found'}), 500
    
    @app.route('/security')
    def security():
        """Security and audit logs page"""
        try:
            return render_template('security.html')
        except Exception as e:
            logger.error(f"Security template error: {str(e)}")
            return jsonify({'error': 'Security page not found'}), 500
    
    @app.route('/controls')
    def controls():
        """Global controls page"""
        try:
            return render_template('controls.html')
        except Exception as e:
            logger.error(f"Controls template error: {str(e)}")
            return jsonify({'error': 'Controls page not found'}), 500
    
    @app.route('/institutional-dashboard')
    def institutional_dashboard():
        """Institutional Administrator dashboard"""
        try:
            return render_template('institutional-dashboard.html')
        except Exception as e:
            logger.error(f"Institutional dashboard template error: {str(e)}")
            return jsonify({'error': 'Institutional dashboard page not found'}), 500
    
    @app.route('/institutional-settings')
    def institutional_settings():
        """Institutional settings page"""
        try:
            return render_template('institutional-settings.html')
        except Exception as e:
            logger.error(f"Institutional settings template error: {str(e)}")
            return jsonify({'error': 'Institutional settings page not found'}), 500
    
    @app.route('/lecturer-dashboard')
    def lecturer_dashboard():
        """Lecturer dashboard page"""
        try:
            return render_template('lecturer-dashboard.html')
        except Exception as e:
            logger.error(f"Lecturer dashboard template error: {str(e)}")
            return jsonify({'error': 'Lecturer dashboard page not found'}), 500
    
    # Lecturer Navigation Routes
    @app.route('/lecturer/courses')
    def lecturer_courses():
        """Lecturer courses management page"""
        try:
            return render_template('lecturer-courses.html')
        except Exception as e:
            logger.error(f"Lecturer courses template error: {str(e)}")
            return jsonify({'error': 'Lecturer courses page not found'}), 500
    
    @app.route('/lecturer/attendance')
    def lecturer_attendance():
        """Lecturer attendance management page"""
        try:
            return render_template('lecturer-attendance.html')
        except Exception as e:
            logger.error(f"Lecturer attendance template error: {str(e)}")
            return jsonify({'error': 'Lecturer attendance page not found'}), 500
    
    @app.route('/lecturer/schedule')
    def lecturer_schedule():
        """Lecturer schedule page"""
        try:
            return render_template('lecturer-schedule.html')
        except Exception as e:
            logger.error(f"Lecturer schedule template error: {str(e)}")
            return jsonify({'error': 'Lecturer schedule page not found'}), 500
    
    @app.route('/lecturer/analytics')
    def lecturer_analytics():
        """Lecturer analytics page"""
        try:
            return render_template('lecturer-analytics.html')
        except Exception as e:
            logger.error(f"Lecturer analytics template error: {str(e)}")
            return jsonify({'error': 'Lecturer analytics page not found'}), 500
    
    @app.route('/lecturer/communication')
    def lecturer_communication():
        """Lecturer communication page"""
        try:
            return render_template('lecturer-communication.html')
        except Exception as e:
            logger.error(f"Lecturer communication template error: {str(e)}")
            return jsonify({'error': 'Lecturer communication page not found'}), 500
    
    @app.route('/lecturer/get-started')
    def lecturer_get_started():
        """Lecturer get started/onboarding page"""
        try:
            return render_template('lecturer-get-started.html')
        except Exception as e:
            logger.error(f"Lecturer get started template error: {str(e)}")
            return jsonify({'error': 'Lecturer get started page not found'}), 500
    
    # Profile API Endpoints
    @app.route('/api/user/profile', methods=['GET', 'PUT'])
    def api_user_profile():
        """API for user profile management"""
        try:
            # Get user info from request (in production, this would use JWT token)
            email = request.headers.get('X-User-Email') or 'demo@example.com'
            
            if request.method == 'GET':
                # Return user profile data
                if hasattr(app, 'users_db') and email in app.users_db:
                    user = app.users_db[email]
                    return jsonify({
                        'success': True,
                        'profile': {
                            'firstName': user.get('firstName', ''),
                            'lastName': user.get('lastName', ''),
                            'email': user.get('email', ''),
                            'role': user.get('role', ''),
                            'created_at': user.get('created_at', ''),
                            'last_login': datetime.utcnow().isoformat()
                        }
                    }), 200
                else:
                    return jsonify({'error': 'User not found'}), 404
            
            elif request.method == 'PUT':
                # Update user profile
                data = request.get_json()
                
                if hasattr(app, 'users_db') and email in app.users_db:
                    user = app.users_db[email]
                    user['firstName'] = data.get('firstName', user.get('firstName'))
                    user['lastName'] = data.get('lastName', user.get('lastName'))
                    user['email'] = data.get('email', user.get('email'))
                    
                    return jsonify({
                        'success': True,
                        'message': 'Profile updated successfully'
                    }), 200
                else:
                    return jsonify({'error': 'User not found'}), 404
                    
        except Exception as e:
            logger.error(f"Profile API error: {str(e)}")
            return jsonify({'error': 'Failed to process profile request'}), 500
    
    @app.route('/api/user/password', methods=['PUT'])
    def api_user_password():
        """API for password change"""
        try:
            data = request.get_json()
            current_password = data.get('currentPassword')
            new_password = data.get('newPassword')
            
            # Validate input
            if not current_password or not new_password:
                return jsonify({'error': 'Current password and new password are required'}), 400
            
            if len(new_password) < 8:
                return jsonify({'error': 'Password must be at least 8 characters long'}), 400
            
            # Get user info (in production, this would use JWT token)
            email = request.headers.get('X-User-Email') or 'demo@example.com'
            
            if hasattr(app, 'users_db') and email in app.users_db:
                user = app.users_db[email]
                
                # Verify current password (in production, this would use proper password hashing)
                if user.get('password') != current_password:
                    return jsonify({'error': 'Current password is incorrect'}), 400
                
                # Update password (in production, this would hash the new password)
                user['password'] = new_password
                
                return jsonify({
                    'success': True,
                    'message': 'Password changed successfully'
                }), 200
            else:
                return jsonify({'error': 'User not found'}), 404
                
        except Exception as e:
            logger.error(f"Password API error: {str(e)}")
            return jsonify({'error': 'Failed to change password'}), 500
    
    @app.route('/api/user/avatar', methods=['POST'])
    def api_user_avatar():
        """API for profile picture upload"""
        try:
            if 'avatar' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
            
            file = request.files['avatar']
            
            # Validate file type
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                return jsonify({'error': 'Invalid file type. Please upload JPG or PNG'}), 400
            
            # Validate file size (max 5MB)
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Seek back to beginning
            
            if file_size > 5 * 1024 * 1024:
                return jsonify({'error': 'File size must be less than 5MB'}), 400
            
            # In production, this would save the file to cloud storage
            # For demo, we'll just return success
            return jsonify({
                'success': True,
                'message': 'Profile picture updated successfully',
                'avatar_url': f'/static/avatars/{file.filename}'
            }), 200
            
        except Exception as e:
            logger.error(f"Avatar upload error: {str(e)}")
            return jsonify({'error': 'Failed to upload profile picture'}), 500
    
    @app.route('/api/user/settings', methods=['GET', 'PUT'])
    def api_user_settings():
        """API for user settings"""
        try:
            # Get user info (in production, this would use JWT token)
            email = request.headers.get('X-User-Email') or 'demo@example.com'
            
            if request.method == 'GET':
                # Return user settings (default settings for demo)
                settings = {
                    'emailNotifications': True,
                    'securityAlerts': True,
                    'systemUpdates': False,
                    'marketingEmails': False,
                    'activityStatus': True,
                    'dataAnalytics': False,
                    'loginAlerts': True,
                    'reauthRequired': True
                }
                
                return jsonify({
                    'success': True,
                    'settings': settings
                }), 200
            
            elif request.method == 'PUT':
                # Update user settings
                data = request.get_json()
                
                # In production, this would save to database
                # For demo, we'll just return success
                return jsonify({
                    'success': True,
                    'message': 'Settings updated successfully'
                }), 200
                
        except Exception as e:
            logger.error(f"Settings API error: {str(e)}")
            return jsonify({'error': 'Failed to process settings request'}), 500
    
    @app.route('/api/user/2fa', methods=['PUT'])
    def api_user_2fa():
        """API for two-factor authentication"""
        try:
            data = request.get_json()
            enabled = data.get('enabled', False)
            
            # In production, this would set up 2FA with email/SMS
            # For demo, we'll just return success
            return jsonify({
                'success': True,
                'message': f'2FA {"enabled" if enabled else "disabled"} successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"2FA API error: {str(e)}")
            return jsonify({'error': 'Failed to update 2FA settings'}), 500
    
    @app.route('/api/user/logout-all', methods=['POST'])
    def api_user_logout_all():
        """API for logging out from all sessions"""
        try:
            # In production, this would invalidate all user tokens
            # For demo, we'll just return success
            return jsonify({
                'success': True,
                'message': 'Logged out from all other sessions'
            }), 200
            
        except Exception as e:
            logger.error(f"Logout all API error: {str(e)}")
            return jsonify({'error': 'Failed to logout from all sessions'}), 500
    
    @app.route('/api/user/download-data', methods=['GET'])
    def api_user_download_data():
        """API for downloading user data"""
        try:
            # Get user info (in production, this would use JWT token)
            email = request.headers.get('X-User-Email') or 'demo@example.com'
            
            if hasattr(app, 'users_db') and email in app.users_db:
                user = app.users_db[email]
                
                # Create user data JSON
                user_data = {
                    'profile': {
                        'firstName': user.get('firstName', ''),
                        'lastName': user.get('lastName', ''),
                        'email': user.get('email', ''),
                        'role': user.get('role', ''),
                        'created_at': user.get('created_at', ''),
                    },
                    'settings': {
                        'emailNotifications': True,
                        'securityAlerts': True,
                        'systemUpdates': False,
                        'marketingEmails': False,
                    },
                    'export_date': datetime.utcnow().isoformat()
                }
                
                return jsonify(user_data), 200
            else:
                return jsonify({'error': 'User not found'}), 404
                
        except Exception as e:
            logger.error(f"Download data API error: {str(e)}")
            return jsonify({'error': 'Failed to download user data'}), 500
    
    @app.route('/api/user/export-attendance', methods=['GET'])
    def api_user_export_attendance():
        """API for exporting attendance records"""
        try:
            # Create CSV data for attendance records
            csv_data = "Date,Course,Status,Time\n"
            csv_data += "2026-04-06,Mathematics,Present,09:00\n"
            csv_data += "2026-04-05,Physics,Present,10:30\n"
            csv_data += "2026-04-04,Chemistry,Present,14:00\n"
            
            return csv_data, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename=attendance-records.csv'
            }
            
        except Exception as e:
            logger.error(f"Export attendance API error: {str(e)}")
            return jsonify({'error': 'Failed to export attendance records'}), 500
    
    @app.route('/api/user/delete-account', methods=['DELETE'])
    def api_user_delete_account():
        """API for deleting user account"""
        try:
            # Get user info (in production, this would use JWT token)
            email = request.headers.get('X-User-Email') or 'demo@example.com'
            
            if hasattr(app, 'users_db') and email in app.users_db:
                # Delete user account
                del app.users_db[email]
                
                return jsonify({
                    'success': True,
                    'message': 'Account deleted successfully'
                }), 200
            else:
                return jsonify({'error': 'User not found'}), 404
                
        except Exception as e:
            logger.error(f"Delete account API error: {str(e)}")
            return jsonify({'error': 'Failed to delete account'}), 500
    
    # Institution Management API Endpoints
    @app.route('/api/admin/institutions', methods=['GET', 'POST'])
    def api_admin_institutions():
        """API for institution management"""
        try:
            if request.method == 'GET':
                # Return all institutions (empty until real data exists)
                institutions = []
                
                return jsonify({
                    'success': True,
                    'institutions': institutions
                }), 200
                
            elif request.method == 'POST':
                # Create new institution
                data = request.get_json()
                
                # Validate required fields
                required_fields = ['name', 'code', 'email']
                for field in required_fields:
                    if not data.get(field):
                        return jsonify({'error': f'{field} is required'}), 400
                
                # Create institution (in production, would save to database)
                new_institution = {
                    'id': f"inst_{len(institutions) + 3}",
                    'name': data.get('name'),
                    'code': data.get('code'),
                    'email': data.get('email'),
                    'phone': data.get('phone'),
                    'address': data.get('address'),
                    'active': True,
                    'created_at': datetime.utcnow().isoformat()
                }
                
                return jsonify({
                    'success': True,
                    'message': 'Institution created successfully',
                    'institution': new_institution
                }), 201
                
        except Exception as e:
            logger.error(f"Institutions API error: {str(e)}")
            return jsonify({'error': 'Failed to process institution request'}), 500
    
    @app.route('/api/admin/institutions/<institution_id>', methods=['PUT', 'DELETE'])
    def api_admin_institution_detail(institution_id):
        """API for individual institution operations"""
        try:
            if request.method == 'PUT':
                # Update institution status
                data = request.get_json()
                new_status = data.get('active')
                
                return jsonify({
                    'success': True,
                    'message': f'Institution {"activated" if new_status else "deactivated"} successfully'
                }), 200
                
            elif request.method == 'DELETE':
                # Delete institution
                return jsonify({
                    'success': True,
                    'message': 'Institution deleted successfully'
                }), 200
                
        except Exception as e:
            logger.error(f"Institution detail API error: {str(e)}")
            return jsonify({'error': 'Failed to process institution operation'}), 500
    
    # User Management API Endpoints
    @app.route('/api/admin/users', methods=['GET', 'POST'])
    def api_admin_users():
        """API for user management"""
        try:
            if request.method == 'GET':
                # Return all users (empty until real data exists)
                users = []
                
                return jsonify({
                    'success': True,
                    'users': users
                }), 200
                
            elif request.method == 'POST':
                # Create new user
                data = request.get_json()
                
                # Validate required fields
                required_fields = ['firstName', 'lastName', 'email', 'role', 'password']
                for field in required_fields:
                    if not data.get(field):
                        return jsonify({'error': f'{field} is required'}), 400
                
                # Validate role
                valid_roles = ['super_administrator', 'institutional_admin', 'lecturer', 'student', 'employee']
                if data.get('role') not in valid_roles:
                    return jsonify({'error': 'Invalid role selected'}), 400
                
                # Create user (in production, would save to database)
                new_user = {
                    'id': f"user_{len(users) + 3}",
                    'firstName': data.get('firstName'),
                    'lastName': data.get('lastName'),
                    'email': data.get('email'),
                    'role': data.get('role'),
                    'institution': data.get('institution'),
                    'status': 'active',
                    'created_at': datetime.utcnow().isoformat(),
                    'last_login': None
                }
                
                # Add to users_db
                if not hasattr(app, 'users_db'):
                    app.users_db = {}
                app.users_db[data.get('email')] = new_user
                
                return jsonify({
                    'success': True,
                    'message': 'User created successfully',
                    'user': new_user
                }), 201
                
        except Exception as e:
            logger.error(f"Users API error: {str(e)}")
            return jsonify({'error': 'Failed to process user request'}), 500
    
    @app.route('/api/admin/users/<user_id>', methods=['PUT', 'DELETE'])
    def api_admin_user_detail(user_id):
        """API for individual user operations"""
        try:
            if request.method == 'PUT':
                # Update user status or role
                data = request.get_json()
                
                return jsonify({
                    'success': True,
                    'message': f'User {"status" or "role"} updated successfully'
                }), 200
                
            elif request.method == 'DELETE':
                # Delete user
                return jsonify({
                    'success': True,
                    'message': 'User deleted successfully'
                }), 200
                
        except Exception as e:
            logger.error(f"User detail API error: {str(e)}")
            return jsonify({'error': 'Failed to process user operation'}), 500
    
    @app.route('/api/admin/role-assignments', methods=['GET', 'PUT'])
    def api_admin_role_assignments():
        """API for role assignments"""
        try:
            if request.method == 'GET':
                # Return role assignments (empty until real data exists)
                assignments = []
                
                return jsonify({
                    'success': True,
                    'assignments': assignments
                }), 200
                
            elif request.method == 'PUT':
                # Update role assignments
                data = request.get_json()
                
                return jsonify({
                    'success': True,
                    'message': 'Role assignments updated successfully'
                }), 200
                
        except Exception as e:
            logger.error(f"Role assignments API error: {str(e)}")
            return jsonify({'error': 'Failed to process role assignment request'}), 500
    
    # System Monitoring API Endpoints
    @app.route('/api/admin/server-status', methods=['GET'])
    def api_admin_server_status():
        """API for server status"""
        try:
            status = {
                'web_server': {
                    'status': 'offline',
                    'uptime': '0%',
                    'response_time': '0ms'
                },
                'database': {
                    'status': 'disconnected',
                    'connections': '0/100',
                    'query_time': '0ms'
                },
                'cache_server': {
                    'status': 'offline',
                    'memory_usage': '0%',
                    'hit_rate': '0%'
                }
            }
            
            return jsonify({
                'success': True,
                'status': status
            }), 200
            
        except Exception as e:
            logger.error(f"Server status API error: {str(e)}")
            return jsonify({'error': 'Failed to get server status'}), 500
    
    @app.route('/api/admin/active-sessions', methods=['GET'])
    def api_admin_active_sessions():
        """API for active sessions"""
        try:
            sessions = []
            
            return jsonify({
                'success': True,
                'sessions': sessions
            }), 200
            
        except Exception as e:
            logger.error(f"Active sessions API error: {str(e)}")
            return jsonify({'error': 'Failed to get active sessions'}), 500
    
    @app.route('/api/admin/api-health', methods=['GET'])
    def api_admin_api_health():
        """API for API health"""
        try:
            endpoints = []
            
            return jsonify({
                'success': True,
                'endpoints': endpoints
            }), 200
            
        except Exception as e:
            logger.error(f"API health API error: {str(e)}")
            return jsonify({'error': 'Failed to get API health'}), 500
    
    @app.route('/api/admin/sessions/<session_id>', methods=['DELETE'])
    def api_admin_session_detail(session_id):
        """API for session operations"""
        try:
            return jsonify({
                'success': True,
                'message': 'Session terminated successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Session detail API error: {str(e)}")
            return jsonify({'error': 'Failed to terminate session'}), 500
    
    @app.route('/api/admin/export-monitoring-data', methods=['GET'])
    def api_admin_export_monitoring_data():
        """API for exporting monitoring data"""
        try:
            data = {
                'server_status': {
                    'timestamp': datetime.utcnow().isoformat(),
                    'web_server': 'Offline',
                    'database': 'Disconnected',
                    'cache_server': 'Offline'
                },
                'active_sessions': [],
                'api_health': []
            }
            
            return jsonify(data), 200
            
        except Exception as e:
            logger.error(f"Export monitoring data API error: {str(e)}")
            return jsonify({'error': 'Failed to export monitoring data'}), 500
    
    # Security & Audit Logs API Endpoints
    @app.route('/api/admin/login-activity', methods=['GET'])
    def api_admin_login_activity():
        """API for login activity logs"""
        try:
            logs = []
            
            return jsonify({
                'success': True,
                'logs': logs
            }), 200
            
        except Exception as e:
            logger.error(f"Login activity API error: {str(e)}")
            return jsonify({'error': 'Failed to get login activity'}), 500
    
    @app.route('/api/admin/system-actions', methods=['GET'])
    def api_admin_system_actions():
        """API for system action logs"""
        try:
            logs = []
            
            return jsonify({
                'success': True,
                'logs': logs
            }), 200
            
        except Exception as e:
            logger.error(f"System actions API error: {str(e)}")
            return jsonify({'error': 'Failed to get system actions'}), 500
    
    @app.route('/api/admin/suspicious-activity', methods=['GET'])
    def api_admin_suspicious_activity():
        """API for suspicious activity logs"""
        try:
            threats = []
            
            return jsonify({
                'success': True,
                'threats': threats
            }), 200
            
        except Exception as e:
            logger.error(f"Suspicious activity API error: {str(e)}")
            return jsonify({'error': 'Failed to get suspicious activity'}), 500
    
    @app.route('/api/admin/security-logs', methods=['GET'])
    def api_admin_security_logs():
        """API for all security logs"""
        try:
            # Get all security logs (empty until real data exists)
            login_logs = []
            system_logs = []
            threats = []
            
            return jsonify({
                'success': True,
                'login_logs': login_logs,
                'system_logs': system_logs,
                'suspicious_logs': threats
            }), 200
            
        except Exception as e:
            logger.error(f"Security logs API error: {str(e)}")
            return jsonify({'error': 'Failed to get security logs'}), 500
    
    @app.route('/api/admin/export-security-data', methods=['GET'])
    def api_admin_export_security_data():
        """API for exporting security data"""
        try:
            data = {
                'export_timestamp': datetime.utcnow().isoformat(),
                'login_activity': [],
                'system_actions': [],
                'suspicious_activity': []
            }
            
            return jsonify(data), 200
            
        except Exception as e:
            logger.error(f"Export security data API error: {str(e)}")
            return jsonify({'error': 'Failed to export security data'}), 500
    
    # Global Controls API Endpoints
    @app.route('/api/admin/announcements', methods=['GET', 'POST'])
    def api_admin_announcements():
        """API for system announcements"""
        try:
            if request.method == 'GET':
                # Return all announcements (empty until real data exists)
                announcements = []
                
                return jsonify({
                    'success': True,
                    'announcements': announcements
                }), 200
                
            elif request.method == 'POST':
                # Create new announcement
                data = request.get_json()
                
                # Validate required fields
                if not data.get('title') or not data.get('message'):
                    return jsonify({'error': 'Title and message are required'}), 400
                
                # Create announcement
                new_announcement = {
                    'id': f"announcement_{len(announcements) + 3}",
                    'title': data.get('title'),
                    'type': data.get('type', 'info'),
                    'message': data.get('message'),
                    'target': data.get('target', 'all'),
                    'created_by': 'admin@example.com',
                    'created_at': datetime.utcnow().isoformat()
                }
                
                return jsonify({
                    'success': True,
                    'message': 'Announcement created successfully',
                    'announcement': new_announcement
                }), 201
                
        except Exception as e:
            logger.error(f"Announcements API error: {str(e)}")
            return jsonify({'error': 'Failed to process announcement request'}), 500
    
    @app.route('/api/admin/system-settings', methods=['GET'])
    def api_admin_system_settings():
        """API for system settings"""
        try:
            settings = {
                'maintenance_mode': False,
                'registration_enabled': False,
                'email_notifications': False,
                'rate_limiting': False,
                'backup_enabled': False
            }
            
            return jsonify({
                'success': True,
                'settings': settings
            }), 200
            
        except Exception as e:
            logger.error(f"System settings API error: {str(e)}")
            return jsonify({'error': 'Failed to get system settings'}), 500
    
    @app.route('/api/admin/system-settings/maintenance', methods=['PUT'])
    def api_admin_system_maintenance():
        """API for maintenance mode setting"""
        try:
            data = request.get_json()
            new_status = data.get('maintenance_mode')
            
            return jsonify({
                'success': True,
                'message': f'Maintenance mode {"enabled" if new_status else "disabled"} successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Maintenance mode API error: {str(e)}")
            return jsonify({'error': 'Failed to update maintenance mode'}), 500
    
    @app.route('/api/admin/system-settings/registration', methods=['PUT'])
    def api_admin_system_registration():
        """API for registration setting"""
        try:
            data = request.get_json()
            new_status = data.get('registration_enabled')
            
            return jsonify({
                'success': True,
                'message': f'Registration {"enabled" if new_status else "disabled"} successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Registration setting API error: {str(e)}")
            return jsonify({'error': 'Failed to update registration status'}), 500
    
    @app.route('/api/admin/system-settings/email-notifications', methods=['PUT'])
    def api_admin_system_email_notifications():
        """API for email notifications setting"""
        try:
            data = request.get_json()
            new_status = data.get('email_notifications')
            
            return jsonify({
                'success': True,
                'message': f'Email notifications {"enabled" if new_status else "disabled"} successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Email notifications API error: {str(e)}")
            return jsonify({'error': 'Failed to update email notifications'}), 500
    
    @app.route('/api/admin/system-backup', methods=['POST'])
    def api_admin_system_backup():
        """API for system backup"""
        try:
            return jsonify({
                'success': True,
                'message': 'System backup started successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"System backup API error: {str(e)}")
            return jsonify({'error': 'Failed to start system backup'}), 500
    
    @app.route('/api/admin/export-system-data', methods=['GET'])
    def api_admin_export_system_data():
        """API for exporting system data"""
        try:
            data = {
                'export_timestamp': datetime.utcnow().isoformat(),
                'system_settings': {
                    'maintenance_mode': False,
                    'registration_enabled': False,
                    'email_notifications': False,
                    'rate_limiting': False,
                    'backup_enabled': False
                },
                'announcements': [],
                'user_count': 0,
                'institution_count': 0
            }
            
            return jsonify(data), 200
            
        except Exception as e:
            logger.error(f"Export system data API error: {str(e)}")
            return jsonify({'error': 'Failed to export system data'}), 500
    
    # Institutional Administrator API Endpoints
    @app.route('/api/institutional/dashboard-statistics', methods=['GET'])
    def api_institutional_dashboard_statistics():
        """API for institutional dashboard statistics"""
        try:
            # Return empty statistics until real data exists
            statistics = {
                'totalUsers': 0,
                'activeCourses': 0,
                'todayAttendance': 0,
                'pendingApprovals': 0,
                'pendingUserCount': 0,
                'activeUserCount': 0,
                'totalUserCount': 0,
                'courseCount': 0,
                'lecturerCount': 0,
                'enrolledCount': 0,
                'attendanceRate': 0,
                'reportCount': 0,
                'alertCount': 0,
                'scheduleCount': 0,
                'conflictCount': 0,
                'publishedCount': 0,
                'announcementCount': 0,
                'activeAlerts': 0,
                'notificationCount': 0,
                'studentAnalytics': 0,
                'lecturerAnalytics': 0,
                'reportGeneration': 0,
                'classroomCount': 0,
                'labCount': 0,
                'resourceUtilization': 0,
                'loginActivity': 0,
                'securityEvents': 0,
                'accessControl': 0
            }
            
            return jsonify({
                'success': True,
                **statistics
            }), 200
            
        except Exception as e:
            logger.error(f"Institutional dashboard statistics API error: {str(e)}")
            return jsonify({'error': 'Failed to get dashboard statistics'}), 500
    
    # Institutional Settings API Endpoints
    @app.route('/api/institutional/settings', methods=['GET'])
    def api_institutional_settings():
        """API for institutional settings"""
        try:
            # Return empty settings until real data exists
            settings = {
                'institutionName': '',
                'institutionCode': '',
                'institutionEmail': '',
                'institutionPhone': '',
                'institutionAddress': '',
                'academicYear': '',
                'semesterSystem': 'semester',
                'classDuration': '60',
                'breakDuration': '15',
                'minAttendance': '75',
                'lateGracePeriod': '10',
                'autoAbsentAfter': '30',
                'alertThreshold': '80',
                'attendanceAlerts': False,
                'scheduleChanges': False,
                'systemUpdates': False,
                'securityAlerts': False,
                'emailNotifications': False,
                'sessionTimeout': '30',
                'passwordExpiry': '90',
                'twoFactorAuth': False,
                'ipRestriction': False
            }
            
            return jsonify({
                'success': True,
                'settings': settings
            }), 200
            
        except Exception as e:
            logger.error(f"Institutional settings API error: {str(e)}")
            return jsonify({'error': 'Failed to get institutional settings'}), 500
    
    @app.route('/api/institutional/settings/basic-info', methods=['PUT'])
    def api_institutional_basic_info():
        """API for basic information settings"""
        try:
            data = request.get_json()
            
            return jsonify({
                'success': True,
                'message': 'Basic information saved successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Basic info settings API error: {str(e)}")
            return jsonify({'error': 'Failed to save basic information'}), 500
    
    @app.route('/api/institutional/settings/academic', methods=['PUT'])
    def api_institutional_academic_settings():
        """API for academic settings"""
        try:
            data = request.get_json()
            
            return jsonify({
                'success': True,
                'message': 'Academic settings saved successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Academic settings API error: {str(e)}")
            return jsonify({'error': 'Failed to save academic settings'}), 500
    
    @app.route('/api/institutional/settings/attendance', methods=['PUT'])
    def api_institutional_attendance_settings():
        """API for attendance settings"""
        try:
            data = request.get_json()
            
            return jsonify({
                'success': True,
                'message': 'Attendance settings saved successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Attendance settings API error: {str(e)}")
            return jsonify({'error': 'Failed to save attendance settings'}), 500
    
    @app.route('/api/institutional/settings/notifications', methods=['PUT'])
    def api_institutional_notification_settings():
        """API for notification settings"""
        try:
            data = request.get_json()
            
            return jsonify({
                'success': True,
                'message': 'Notification settings saved successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Notification settings API error: {str(e)}")
            return jsonify({'error': 'Failed to save notification settings'}), 500
    
    @app.route('/api/institutional/settings/security', methods=['PUT'])
    def api_institutional_security_settings():
        """API for security settings"""
        try:
            data = request.get_json()
            
            return jsonify({
                'success': True,
                'message': 'Security settings saved successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Security settings API error: {str(e)}")
            return jsonify({'error': 'Failed to save security settings'}), 500
    
    @app.route('/api/institutional/settings/email-notifications', methods=['PUT'])
    def api_institutional_email_notifications():
        """API for email notifications setting"""
        try:
            data = request.get_json()
            new_status = data.get('emailNotifications')
            
            return jsonify({
                'success': True,
                'message': f'Email notifications {"enabled" if new_status else "disabled"} successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Email notifications API error: {str(e)}")
            return jsonify({'error': 'Failed to update email notifications'}), 500
    
    # Lecturer Dashboard API Endpoints
    @app.route('/api/lecturer/dashboard-statistics', methods=['GET'])
    def api_lecturer_dashboard_statistics():
        """API for lecturer dashboard statistics"""
        try:
            # Return empty statistics until real data exists
            statistics = {
                # Overview Stats
                'totalCourses': 0,
                'totalStudents': 0,
                'todaySessions': 0,
                'attendanceRate': 0,
                
                # Course Management Stats
                'activeCourses': 0,
                'completedCourses': 0,
                'enrolledStudents': 0,
                'pendingEnrollments': 0,
                'materialsCount': 0,
                'sharedResources': 0,
                
                # Attendance Management Stats
                'pendingAttendance': 0,
                'todayAttendance': 0,
                'editedAttendance': 0,
                'corrections': 0,
                'reportsGenerated': 0,
                'downloadedReports': 0,
                
                # Scheduling Stats
                'weeklyClasses': 0,
                'monthlyClasses': 0,
                'scheduledClasses': 0,
                'conflicts': 0,
                'tomorrowSessions': 0,
                
                # Analytics Stats
                'avgAttendanceRate': 0,
                'trendIndicator': 0,
                'engagedStudents': 0,
                'atRiskStudents': 0,
                'performanceReports': 0,
                'insightsGenerated': 0,
                
                # Communication Stats
                'announcementsSent': 0,
                'readRate': 0,
                'unreadMessages': 0,
                'totalMessages': 0,
                'activeNotifications': 0,
                'pendingNotifications': 0
            }
            
            return jsonify({
                'success': True,
                **statistics
            }), 200
            
        except Exception as e:
            logger.error(f"Lecturer dashboard statistics API error: {str(e)}")
            return jsonify({'error': 'Failed to get dashboard statistics'}), 500
    
    @app.route('/api/lecturer/recent-activity', methods=['GET'])
    def api_lecturer_recent_activity():
        """API for lecturer recent activity"""
        try:
            # Return empty activities until real data exists
            activities = []
            
            return jsonify({
                'success': True,
                'activities': activities
            }), 200
            
        except Exception as e:
            logger.error(f"Lecturer recent activity API error: {str(e)}")
            return jsonify({'error': 'Failed to get recent activity'}), 500
    
    # Lecturer Navigation API Endpoints
    @app.route('/api/lecturer/courses', methods=['GET'])
    def api_lecturer_courses():
        """API for lecturer courses"""
        try:
            # Return empty courses until real data exists
            courses = []
            
            return jsonify({
                'success': True,
                'courses': courses
            }), 200
            
        except Exception as e:
            logger.error(f"Lecturer courses API error: {str(e)}")
            return jsonify({'error': 'Failed to get courses'}), 500
    
    @app.route('/api/lecturer/recent-sessions', methods=['GET'])
    def api_lecturer_recent_sessions():
        """API for lecturer recent sessions"""
        try:
            # Return empty sessions until real data exists
            sessions = []
            
            return jsonify({
                'success': True,
                'sessions': sessions
            }), 200
            
        except Exception as e:
            logger.error(f"Lecturer recent sessions API error: {str(e)}")
            return jsonify({'error': 'Failed to get recent sessions'}), 500
    
    @app.route('/api/lecturer/start-session', methods=['POST'])
    def api_lecturer_start_session():
        """API for starting attendance session"""
        try:
            data = request.get_json()
            
            # Return mock session data
            session = {
                'id': 'session_' + str(hash(data.get('courseId', ''))),
                'courseId': data.get('courseId'),
                'sessionCode': data.get('sessionCode'),
                'isActive': True,
                'startTime': datetime.utcnow().isoformat()
            }
            
            return jsonify({
                'success': True,
                'session': session
            }), 200
            
        except Exception as e:
            logger.error(f"Start session API error: {str(e)}")
            return jsonify({'error': 'Failed to start session'}), 500
    
    @app.route('/api/lecturer/stop-session', methods=['POST'])
    def api_lecturer_stop_session():
        """API for stopping attendance session"""
        try:
            data = request.get_json()
            
            return jsonify({
                'success': True,
                'message': 'Session stopped successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Stop session API error: {str(e)}")
            return jsonify({'error': 'Failed to stop session'}), 500
    
    @app.route('/api/lecturer/today-schedule', methods=['GET'])
    def api_lecturer_today_schedule():
        """API for lecturer today's schedule"""
        try:
            # Return empty schedule until real data exists
            schedule = []
            
            return jsonify({
                'success': True,
                'schedule': schedule
            }), 200
            
        except Exception as e:
            logger.error(f"Today's schedule API error: {str(e)}")
            return jsonify({'error': 'Failed to get today\'s schedule'}), 500
    
    @app.route('/api/lecturer/schedule-stats', methods=['GET'])
    def api_lecturer_schedule_stats():
        """API for lecturer schedule statistics"""
        try:
            return jsonify({
                'success': True,
                'todayClasses': 0,
                'weeklyClasses': 0
            }), 200
            
        except Exception as e:
            logger.error(f"Schedule stats API error: {str(e)}")
            return jsonify({'error': 'Failed to get schedule stats'}), 500
    
    @app.route('/api/lecturer/analytics', methods=['GET'])
    def api_lecturer_analytics():
        """API for lecturer analytics"""
        try:
            return jsonify({
                'success': True,
                'stats': {
                    'avgAttendanceRate': 0,
                    'totalStudents': 0,
                    'activeCourses': 0,
                    'performanceScore': 0
                },
                'charts': {
                    'attendanceTrends': [0, 0, 0, 0, 0, 0],
                    'coursePerformance': [0, 0, 0, 0],
                    'studentEngagement': [0, 0, 0]
                },
                'courses': []
            }), 200
            
        except Exception as e:
            logger.error(f"Analytics API error: {str(e)}")
            return jsonify({'error': 'Failed to get analytics'}), 500
    
    @app.route('/api/lecturer/messages', methods=['GET'])
    def api_lecturer_messages():
        """API for lecturer messages"""
        try:
            # Return empty messages until real data exists
            messages = []
            
            return jsonify({
                'success': True,
                'messages': messages
            }), 200
            
        except Exception as e:
            logger.error(f"Messages API error: {str(e)}")
            return jsonify({'error': 'Failed to get messages'}), 500
    
    @app.route('/api/lecturer/notifications', methods=['GET'])
    def api_lecturer_notifications():
        """API for lecturer notifications"""
        try:
            # Return empty notifications until real data exists
            notifications = []
            
            return jsonify({
                'success': True,
                'notifications': notifications
            }), 200
            
        except Exception as e:
            logger.error(f"Notifications API error: {str(e)}")
            return jsonify({'error': 'Failed to get notifications'}), 500
    
    @app.route('/api/lecturer/communication-stats', methods=['GET'])
    def api_lecturer_communication_stats():
        """API for lecturer communication statistics"""
        try:
            return jsonify({
                'success': True,
                'announcementsSent': 0,
                'readRate': '0%',
                'activeAnnouncements': 0
            }), 200
            
        except Exception as e:
            logger.error(f"Communication stats API error: {str(e)}")
            return jsonify({'error': 'Failed to get communication stats'}), 500
    
    @app.route('/api/lecturer/send-announcement', methods=['POST'])
    def api_lecturer_send_announcement():
        """API for sending announcements"""
        try:
            data = request.get_json()
            
            # Validate required fields
            if not data.get('title') or not data.get('message'):
                return jsonify({'error': 'Title and message are required'}), 400
            
            return jsonify({
                'success': True,
                'message': 'Announcement sent successfully'
            }), 200
            
        except Exception as e:
            logger.error(f"Send announcement API error: {str(e)}")
            return jsonify({'error': 'Failed to send announcement'}), 500
    
    @app.route('/api/test')
    def api_test():
        """Test API endpoint"""
        return jsonify({
            'message': 'Attendrix API is working',
            'endpoints': [
                'GET /health - Health check',
                'GET / - Landing page',
                'GET /api/test - Test endpoint'
            ],
            'firebase_status': 'Disabled for development',
            'database_status': 'Using SQLite for development'
        })
    
    @app.route('/api/info')
    def system_info():
        """System information"""
        return jsonify({
            'system': 'Attendrix',
            'version': '1.0.0-dev',
            'environment': 'development',
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            'flask_version': Flask.__version__,
            'features': {
                'firebase_integration': 'Configured but not initialized',
                'multi_tenant': 'Ready',
                'role_based_access': 'Implemented',
                'anti_proxy_system': 'Implemented',
                'scheduling_engine': 'Implemented',
                'attendance_engine': 'Implemented'
            },
            'next_steps': [
                'Set up Firebase project',
                'Replace firebase-dev.json with real credentials',
                'Install Redis for caching',
                'Configure PostgreSQL for production'
            ]
        })
    
    logger.info("Attendrix development server initialized")
    return app

# Create app instance
app = create_simple_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                    ATTENDRIX DEVELOPMENT SERVER                 ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  Version: 1.0.0-dev                                            ║
    ║  Environment: Development                                        ║
    ║  Server: http://localhost:{port}                                ║
    ║  Health: http://localhost:{port}/health                        ║
    ║  API Test: http://localhost:{port}/api/test                    ║
    ║  System Info: http://localhost:{port}/api/info                 ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  Firebase: Development mode (using mock credentials)              ║
    ║  Database: SQLite (for development only)                        ║
    ║  Debug Mode: {debug}                                             ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
