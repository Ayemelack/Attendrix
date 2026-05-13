# Database schema for Attendrix system

from datetime import datetime
from typing import Dict, Any, List


class DatabaseSchema:
    """Database schema definitions for Attendrix"""
    
    @staticmethod
    def create_tables() -> Dict[str, Any]:
        """Create all necessary database tables"""
        return {
            'users': {
                'description': 'User accounts and authentication',
                'fields': {
                    'id': 'string PRIMARY KEY',
                    'email': 'string UNIQUE NOT NULL',
                    'password_hash': 'string NOT NULL',
                    'first_name': 'string NOT NULL',
                    'last_name': 'string NOT NULL',
                    'role': 'string NOT NULL',  # institutional_admin, lecturer, student
                    'institution_id': 'string NOT NULL',
                    'phone': 'string OPTIONAL',
                    'profile_image_url': 'string OPTIONAL',
                    'is_active': 'boolean DEFAULT true',
                    'email_verified': 'boolean DEFAULT false',
                    'last_login': 'datetime OPTIONAL',
                    'device_fingerprint': 'string OPTIONAL',
                    'created_at': 'datetime DEFAULT CURRENT_TIMESTAMP',
                    'updated_at': 'datetime DEFAULT CURRENT_TIMESTAMP'
                },
                'indexes': ['email', 'institution_id', 'role']
            },
            
            'institutions': {
                'description': 'University/institution records',
                'fields': {
                    'id': 'string PRIMARY KEY',
                    'name': 'string NOT NULL',
                    'code': 'string UNIQUE NOT NULL',
                    'address': 'text NOT NULL',
                    'phone': 'string OPTIONAL',
                    'email': 'string OPTIONAL',
                    'is_active': 'boolean DEFAULT true',
                    'created_at': 'datetime DEFAULT CURRENT_TIMESTAMP'
                },
                'indexes': ['code']
            },
            
            'departments': {
                'description': 'Academic departments',
                'fields': {
                    'id': 'string PRIMARY KEY',
                    'institution_id': 'string NOT NULL',
                    'name': 'string NOT NULL',
                    'code': 'string NOT NULL',
                    'head_id': 'string OPTIONAL',
                    'is_active': 'boolean DEFAULT true',
                    'created_at': 'datetime DEFAULT CURRENT_TIMESTAMP'
                },
                'indexes': ['institution_id', 'code'],
                'foreign_keys': {
                    'institution_id': 'institutions.id'
                }
            },
            
            'courses': {
                'description': 'Academic courses',
                'fields': {
                    'id': 'string PRIMARY KEY',
                    'institution_id': 'string NOT NULL',
                    'department_id': 'string OPTIONAL',
                    'name': 'string NOT NULL',
                    'code': 'string NOT NULL',
                    'lecturer_id': 'string NOT NULL',
                    'description': 'text OPTIONAL',
                    'credits': 'integer DEFAULT 0',
                    'is_active': 'boolean DEFAULT true',
                    'created_at': 'datetime DEFAULT CURRENT_TIMESTAMP'
                },
                'indexes': ['institution_id', 'department_id', 'lecturer_id', 'code'],
                'foreign_keys': {
                    'institution_id': 'institutions.id',
                    'department_id': 'departments.id',
                    'lecturer_id': 'users.id'
                }
            },
            
            'attendance_sessions': {
                'description': 'Attendance sessions for QR codes',
                'fields': {
                    'id': 'string PRIMARY KEY',
                    'course_id': 'string NOT NULL',
                    'lecturer_id': 'string NOT NULL',
                    'session_code': 'string UNIQUE NOT NULL',
                    'start_time': 'datetime NOT NULL',
                    'end_time': 'datetime OPTIONAL',
                    'location': 'string OPTIONAL',
                    'is_active': 'boolean DEFAULT true',
                    'created_at': 'datetime DEFAULT CURRENT_TIMESTAMP'
                },
                'indexes': ['course_id', 'lecturer_id', 'session_code'],
                'foreign_keys': {
                    'course_id': 'courses.id',
                    'lecturer_id': 'users.id'
                }
            },
            
            'attendance_records': {
                'description': 'Individual attendance records',
                'fields': {
                    'id': 'string PRIMARY KEY',
                    'session_id': 'string NOT NULL',
                    'student_id': 'string NOT NULL',
                    'mark_time': 'datetime NOT NULL',
                    'status': 'string NOT NULL',  # present, absent, late, excused
                    'location': 'string OPTIONAL',
                    'device_id': 'string OPTIONAL',
                    'ip_address': 'string OPTIONAL',
                    'verification_method': 'string OPTIONAL',  # qr_code, manual, biometric
                    'created_at': 'datetime DEFAULT CURRENT_TIMESTAMP'
                },
                'indexes': ['session_id', 'student_id', 'mark_time'],
                'foreign_keys': {
                    'session_id': 'attendance_sessions.id',
                    'student_id': 'users.id'
                }
            },
            
            'vouchers': {
                'description': 'One-time use registration vouchers',
                'fields': {
                    'id': 'string PRIMARY KEY',
                    'code': 'string UNIQUE NOT NULL',
                    'email': 'string NOT NULL',
                    'role': 'string NOT NULL',  # institutional_admin, lecturer, student
                    'institution_id': 'string NOT NULL',
                    'is_used': 'boolean DEFAULT false',
                    'used_at': 'datetime OPTIONAL',
                    'created_at': 'datetime DEFAULT CURRENT_TIMESTAMP',
                    'expires_at': 'datetime NOT NULL'
                },
                'indexes': ['code', 'email', 'is_used'],
                'foreign_keys': {
                    'institution_id': 'institutions.id'
                }
            },
            
            'persistent_sessions': {
                'description': 'Remember me session persistence',
                'fields': {
                    'id': 'string PRIMARY KEY',
                    'user_id': 'string NOT NULL',
                    'device_fingerprint': 'string OPTIONAL',
                    'created_at': 'datetime DEFAULT CURRENT_TIMESTAMP',
                    'expires_at': 'datetime NOT NULL',
                    'last_accessed': 'datetime DEFAULT CURRENT_TIMESTAMP',
                    'logged_out_at': 'datetime OPTIONAL'
                },
                'indexes': ['user_id', 'expires_at', 'logged_out_at'],
                'foreign_keys': {
                    'user_id': 'users.id'
                }
            },
            
            'security_logs': {
                'description': 'Security and audit events',
                'fields': {
                    'id': 'string PRIMARY KEY',
                    'user_id': 'string OPTIONAL',
                    'institution_id': 'string OPTIONAL',
                    'event_type': 'string NOT NULL',  # login_success, login_failed, attendance_marked, etc.
                    'description': 'text NOT NULL',
                    'ip_address': 'string OPTIONAL',
                    'user_agent': 'text OPTIONAL',
                    'device_fingerprint': 'string OPTIONAL',
                    'created_at': 'datetime DEFAULT CURRENT_TIMESTAMP'
                },
                'indexes': ['user_id', 'institution_id', 'event_type', 'created_at'],
                'foreign_keys': {
                    'user_id': 'users.id',
                    'institution_id': 'institutions.id'
                }
            }
        }
    
    @staticmethod
    def get_migration_scripts() -> List[str]:
        """Get database migration scripts"""
        return [
            # Create vouchers table
            """
            CREATE TABLE IF NOT EXISTS vouchers (
                id VARCHAR(255) PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                institution_id VARCHAR(255) NOT NULL,
                is_used BOOLEAN DEFAULT FALSE,
                used_at DATETIME NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                INDEX idx_code (code),
                INDEX idx_email (email),
                INDEX idx_is_used (is_used),
                FOREIGN KEY (institution_id) REFERENCES institutions(id)
            );
            """,
            
            # Create persistent_sessions table
            """
            CREATE TABLE IF NOT EXISTS persistent_sessions (
                id VARCHAR(255) PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                device_fingerprint VARCHAR(255) NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
                logged_out_at DATETIME NULL,
                INDEX idx_user_id (user_id),
                INDEX idx_expires_at (expires_at),
                INDEX idx_logged_out_at (logged_out_at),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """,
            
            # Update users table to remove employee role
            """
            ALTER TABLE users MODIFY COLUMN role ENUM('institutional_admin', 'lecturer', 'student') NOT NULL;
            """,
            
            # Create attendance_sessions table
            """
            CREATE TABLE IF NOT EXISTS attendance_sessions (
                id VARCHAR(255) PRIMARY KEY,
                course_id VARCHAR(255) NOT NULL,
                lecturer_id VARCHAR(255) NOT NULL,
                session_code VARCHAR(50) UNIQUE NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME NULL,
                location VARCHAR(255) NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_course_id (course_id),
                INDEX idx_lecturer_id (lecturer_id),
                INDEX idx_session_code (session_code),
                FOREIGN KEY (course_id) REFERENCES courses(id),
                FOREIGN KEY (lecturer_id) REFERENCES users(id)
            );
            """
        ]
