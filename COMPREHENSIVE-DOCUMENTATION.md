# Attendrix - Complete System Documentation

> **Enterprise-Grade Institutional Paperless Attendance System**
> **Tagline:** Secure. Smart. Structured Attendance.

---

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Role System & Permissions](#3-role-system--permissions)
4. [Authentication System](#4-authentication-system)
5. [User Registration (Voucher-Based)](#5-user-registration-voucher-based)
6. [Voucher Management System](#6-voucher-management-system)
7. [Attendance System](#7-attendance-system)
8. [Scheduling System](#8-scheduling-system)
9. [Security & Anti-Proxy System](#9-security--anti-proxy-system)
10. [Device Fingerprinting](#10-device-fingerprinting)
11. [Biometric Enrollment](#11-biometric-enrollment)
12. [Super Admin Dashboard](#12-super-admin-dashboard)
13. [Institutional Admin Dashboard](#13-institutional-admin-dashboard)
14. [Lecturer Dashboard](#14-lecturer-dashboard)
15. [Student Dashboard](#15-student-dashboard)
16. [Landing Page](#16-landing-page)
17. [API Endpoints](#17-api-endpoints)
18. [Database Schema](#18-database-schema)
19. [Entity Models](#19-entity-models)
20. [Infrastructure](#20-infrastructure)
21. [Configuration System](#21-configuration-system)
22. [Development Mode](#22-development-mode)
23. [Deployment](#23-deployment)
24. [Testing](#24-testing)

---

## 1. System Overview

Attendrix is a multi-tenant, role-based attendance management system designed for educational institutions. It eliminates proxy attendance, manual errors, and provides comprehensive analytics.

### Core Capabilities
- **Multi-Tenant**: Complete data isolation for unlimited institutions
- **Role-Based Access**: 4 distinct roles with granular permissions
- **Voucher-Based Registration**: Secure invitation-only signup
- **QR Code Attendance**: Session-based QR attendance marking
- **Anti-Proxy Technology**: Device fingerprinting, geolocation, IP verification
- **Real-Time Analytics**: Live attendance tracking and reporting
- **Conflict Detection**: Smart scheduling with overlap detection
- **Audit Logging**: Complete activity trail for compliance

### Technology Stack
| Component | Technology |
|---|---|
| Backend | Python 3.11+, Flask 2.3 |
| Database | Firebase Firestore (primary), PostgreSQL (analytics) |
| Auth | Firebase Auth, JWT, bcrypt |
| Frontend | HTML5, CSS3, JavaScript, Bootstrap 5 |
| Caching | Redis |
| Background Tasks | Celery |
| Analytics | Pandas, NumPy, Matplotlib, Scikit-learn |
| PDF Generation | ReportLab |
| Deployment | Docker, Gunicorn, Nginx |

---

## 2. Architecture

```
attendrix/
├── app.py                              # Flask application factory & all routes
├── config/
│   ├── settings.py                     # Environment-based config (dev/staging/prod)
│   └── firebase-credentials.json.example
├── src/
│   ├── __init__.py
│   ├── domain/
│   │   └── entities.py                 # All domain models & enums
│   ├── application/
│   │   ├── auth_service.py             # Auth, JWT, password management
│   │   ├── authentication_service.py   # Duplicate/legacy auth service
│   │   ├── persistent_auth_service.py  # "Remember me" session persistence
│   │   ├── rbac.py                     # Role-based access control decorators
│   │   ├── attendance_service.py       # Advanced attendance engine
│   │   ├── attendance_security_service.py # QR-based attendance
│   │   ├── scheduling_service.py       # Scheduling with conflict detection
│   │   ├── voucher_management_service.py # Voucher CRUD & validation
│   │   ├── voucher_seeder.py           # Initial bootstrap voucher generation
│   │   ├── biometric_service.py        # Device biometric enrollment
│   │   └── voucher_service.py          # Legacy voucher service
│   ├── infrastructure/
│   │   ├── firebase_service.py         # Firebase SDK + mock JSON database
│   │   ├── repositories.py            # Repository pattern (CRUD for all entities)
│   │   └── database_schema.py          # PostgreSQL schema definitions
│   └── presentation/
│       ├── static/
│       │   ├── css/landing.css
│       │   └── js/landing.js
│       └── templates/
│           ├── landing.html            # Marketing homepage
│           ├── login.html              # Login page
│           ├── signup.html             # Legacy signup page
│           ├── signup-voucher.html     # Voucher-based signup page
│           ├── logout.html             # Logout confirmation
│           ├── error.html              # Error page
│           ├── admin/
│           │   ├── dashboard.html      # Super Admin dashboard
│           │   ├── institutions.html   # Institution management
│           │   ├── create_institution.html # Create institution form
│           │   ├── users.html          # User management
│           │   ├── monitoring.html     # System monitoring
│           │   ├── security.html       # Security dashboard
│           │   ├── backup.html         # Backup & restore
│           │   ├── notifications.html  # Notifications management
│           │   ├── audit.html          # Audit logs
│           │   ├── roles.html          # Role assignments
│           │   ├── profile.html        # Admin profile
│           │   ├── settings.html       # System settings
│           │   └── reports.html        # Reports
│           ├── institutional-admin/
│           │   └── dashboard.html      # Institutional admin dashboard
│           ├── lecturer/
│           │   └── dashboard.html      # Lecturer dashboard
│           └── student/
│               └── dashboard.html      # Student dashboard
├── app-simple.py                       # Simplified entry point
├── mock_database.json                  # Dev mock database (JSON file)
├── requirements.txt                    # Python dependencies
├── requirements-dev.txt               # Development dependencies
├── Dockerfile                          # Container build
├── docker-compose.yml                  # Multi-container orchestration
├── nginx/                              # Nginx configuration
├── scripts/
│   └── init-databases.sh              # Database initialization script
├── .env.example                        # Environment template
└── *.md                                # Extensive documentation & fix notes
```

### Clean Architecture Layers

**Presentation Layer** (`src/presentation/`): Handles HTTP requests/responses, serves HTML templates, static assets (CSS, JS).

**Application Layer** (`src/application/`): Contains all business logic as services. Orchestrates domain entities and infrastructure.

**Domain Layer** (`src/domain/`): Pure business entities (User, Course, AttendanceSession, etc.) with no external dependencies.

**Infrastructure Layer** (`src/infrastructure/`): Implements database access (Firebase/Firestore), repository pattern, external service integration.

---

## 3. Role System & Permissions

### Roles Defined
| Role | Enum Value | Description |
|---|---|---|
| Super Admin | `super_admin` | Full system access across all institutions |
| Institutional Admin | `institutional_admin` | Manages a single institution |
| Lecturer | `lecturer` | Manages courses and attendance |
| Student | `student` | Marks/view attendance |

### Permissions Matrix (20 permissions total)

| Permission | Super Admin | Institutional Admin | Lecturer | Student |
|---|---|---|---|---|
| `manage_system` | ✓ | | | |
| `manage_institution` | ✓ | | | |
| `view_institution_analytics` | ✓ | | | |
| `manage_departments` | ✓ | ✓ | | |
| `view_department_analytics` | ✓ | ✓ | | |
| `manage_users` | ✓ | ✓ | | |
| `create_users` | ✓ | ✓ | | |
| `view_users` | ✓ | ✓ | | |
| `manage_courses` | ✓ | ✓ | | |
| `view_courses` | ✓ | ✓ | ✓ | ✓ |
| `enroll_students` | ✓ | ✓ | | |
| `manage_schedules` | ✓ | ✓ | | |
| `view_schedules` | ✓ | ✓ | ✓ | ✓ |
| `manage_attendance` | ✓ | ✓ | ✓ | |
| `mark_attendance` | ✓ | ✓ | ✓ | ✓ |
| `view_attendance` | ✓ | ✓ | ✓ | ✓ |
| `view_attendance_reports` | ✓ | ✓ | ✓ | |
| `manage_leave_requests` | ✓ | ✓ | | |
| `submit_leave_request` | ✓ | ✓ | ✓ | ✓ |
| `approve_leave_request` | ✓ | ✓ | | |
| `view_analytics` | ✓ | ✓ | ✓ | ✓ |
| `view_predictive_analytics` | ✓ | | | |
| `view_audit_logs` | ✓ | ✓ | | |
| `manage_notifications` | ✓ | ✓ | | |

### Access Control Decorators (in `src/application/rbac.py`)
- `@require_auth` - Requires valid JWT token
- `@require_role('role1', 'role2')` - Requires one of specified roles
- `@require_permission('perm1', 'perm2')` - Requires any of specified permissions
- `@require_institution_access` - Ensures user can only access their institution's data
- `@require_active_user` - Ensures user account is active
- `@log_access` - Logs API access to audit trail
- `@rate_limit(limit, window)` - Rate limiting by IP/user

### Rate Limiting
- Built-in `RateLimiter` class tracks requests by IP or user ID
- Configurable limits and time windows
- Returns HTTP 429 when exceeded

---

## 4. Authentication System

### Components
- **`AuthenticationService`** in `src/application/auth_service.py`
- **`PersistentAuthService`** in `src/application/persistent_auth_service.py`
- **`DeviceFingerprintService`** in `src/application/auth_service.py`

### Password Security
- **bcrypt** hashing with auto-generated salts
- Passwords hashed before storage
- Verification through `bcrypt.checkpw()`

### JWT Token System
| Token | Expiry | Purpose |
|---|---|---|
| Access Token | 1 hour (configurable) | API authorization |
| Refresh Token | 30 days (configurable) | Obtain new access tokens |
| Device Token | Persistent | "Remember me" device recognition |

### Token Payload
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "role": "lecturer",
  "institution_id": "inst_001",
  "exp": 1700000000,
  "iat": 1700000000,
  "type": "access" | "refresh"
}
```

### Authentication Flow
1. User submits email + password
2. Server queries `users` collection by email
3. Password verified against bcrypt hash
4. Device fingerprint registered (if "remember me")
5. Last login timestamp updated
6. JWT access + refresh tokens generated
7. Security event logged (`login_success` or `login_failed`)
8. Tokens returned to client

### Persistent Sessions ("Remember Me")
- Stores session record in `persistent_sessions` collection
- Configurable max 30-day expiry
- Device fingerprint binding for security
- Session invalidation on explicit logout

### Endpoints
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | No | User login |
| POST | `/api/auth/register` | No | User registration |
| POST | `/api/auth/signup` | No | Alias for register |
| POST | `/api/auth/refresh` | No | Refresh access token |
| POST | `/api/auth/logout` | Yes | User logout |
| GET | `/login` | No | Login page |
| GET | `/signup` | No | Signup page |
| GET | `/signup-voucher` | No | Voucher signup page |
| GET | `/logout` | No | Logout page |

### Token Refresh Flow
1. Client sends refresh token to `/api/auth/refresh`
2. Server decodes and validates refresh token
3. Server fetches user from Firestore (checks active status)
4. New access token generated and returned
5. Old refresh token remains valid until expiry

---

## 5. User Registration (Voucher-Based)

### Registration Flow
1. User obtains a voucher code (from admin/seed)
2. User visits `/signup-voucher` page
3. User enters voucher code on the form
4. Frontend calls `GET /api/voucher/validate/{code}`
5. If valid, form displays role-specific fields
6. User completes registration with email, password, name
7. Frontend calls `POST /api/auth/register`
8. Server creates Firebase Auth user
9. Server creates user document in Firestore `users` collection
10. Server marks voucher as consumed
11. User is redirected to login

### Registration Validation
- Email normalization (strip, lowercase)
- Password strength checked client-side
- Voucher format: 8 chars, uppercase alphanumeric
- Voucher checked for: existence, usage status, expiry, institution match, role match, email binding
- Duplicate email detection

### Registration Payload
```json
{
  "email": "user@example.com",
  "password": "securePassword123",
  "first_name": "John",
  "last_name": "Doe",
  "role": "student",
  "institution_id": "inst_001",
  "voucher_code": "STUD7890",
  "student_id": "optional"
}
```

---

## 6. Voucher Management System

### Overview
Vouchers are 8-character, cryptographically secure, uppercase alphanumeric codes used for invitation-only registration.

### Voucher Properties
- **Code**: 8 chars, alphanumeric, uppercase
- **Role**: Bound to specific role
- **Institution**: Bound to specific institution
- **Email Binding**: Optional - if set, only that email can use it
- **Expiry**: Configurable (default 30 days for batch, 90 days for seed)
- **Status**: Unused, Used, Expired

### Fixed Seed Vouchers (for testing)
| Code | Role | Email Binding |
|---|---|---|
| `ADMIN123` | Institutional Admin | admin@attendrix.demo |
| `LECT4567` | Lecturer | lecturer1@attendrix.demo |
| `LECT4568` | Lecturer | lecturer2@attendrix.demo |
| `LECT4569` | Lecturer | lecturer3@attendrix.demo |
| `STUD7890` | Student | student1@attendrix.demo |
| `STUD7891`-`STUD7899` | Student | student2@-student10@attendrix.demo |

### Voucher Endpoints
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/voucher/validate/{code}` | No | Validate voucher |
| POST | `/api/voucher/generate-batch` | Yes (admin) | Generate voucher batch |
| GET | `/api/voucher/statistics/{institution_id}` | Yes (admin) | Get usage statistics |
| POST | `/system/voucher/seed` | No | Generate initial seed vouchers |
| POST | `/system/voucher/force-reseed` | No | Clear and regenerate all vouchers |
| GET | `/system/voucher/check` | No | Check voucher system status |
| GET | `/system/voucher/debug` | No | List all vouchers in database |

### Voucher Batch Generation
Admins can generate vouchers in bulk with:
- **Role**: The target role
- **Institution ID**: Bound to specific institution
- **Quantity**: Number of vouchers (default 10)
- **Email Binding**: Optional email restriction

### Voucher Consumption
On successful registration:
1. Voucher document found by code
2. `is_used` set to `true`
3. `used_by` set to new user's ID
4. `used_at` timestamp recorded

---

## 7. Attendance System

### Two Attendance Systems

#### 7A. QR-Based Attendance (Simple) - `attendance_security_service.py`
Used by lecturers to create quick QR attendance sessions.

**Create Session**:
- Generates 6-character uppercase alphanumeric session code
- Generates QR code as base64 PNG image
- Session duration: 60 minutes (configurable)
- QR code expires in 5 minutes

**Mark Attendance**:
- Student scans QR code or enters session code
- Validates session exists and is active
- Checks student hasn't already marked
- Verifies session hasn't expired
- Records attendance with device fingerprint, IP, location

**Close Session**:
- Lecturer closes session early
- Verifies lecturer owns the session

#### 7B. Advanced Attendance Engine (Full) - `attendance_service.py`
Comprehensive engine with anti-proxy security.

**Security Checks** (6 layers):
1. **IP Restriction** - Only allow specific IPs
2. **Geolocation Verification** - GPS distance check with configurable radius
3. **Device Fingerprint** - Detect new/unknown devices
4. **Rapid Succession Detection** - Multiple marks in 5 minutes
5. **Multiple Device Detection** - Different IPs/agents in same session
6. **Time Anomaly Detection** - Compare marking time vs historical pattern

**Suspicious Activity Scoring**:
- Each check contributes a risk score
- Scores above 50 trigger suspicious flag
- Activities logged to security logs
- Types: `multiple_devices`, `impossible_location`, `rapid_succession`, `unusual_ip_pattern`, `device_mismatch`, `time_anomaly`

**Session Statistics**:
- Total records, present, late, absent, excused counts
- Suspicious activity count
- Average marking time
- Unique IPs and devices
- Geolocation coverage percentage

### Attendance Endpoints
| Method | Path | Auth | Role | Description |
|---|---|---|---|---|
| POST | `/api/attendance/create-session` | Yes | Lecturer | Create QR session |
| POST | `/api/attendance/mark` | Yes | Student | Mark attendance |
| POST | `/api/attendance/close-session/{session_id}` | Yes | Lecturer | Close session |
| GET | `/api/attendance/sessions/{session_id}/statistics` | Yes | Lecturer/Admin | Get statistics |

---

## 8. Scheduling System

### Scheduling Engine - `scheduling_service.py`
Creates and manages recurring class schedules with conflict detection.

### Conflict Types
| Type | Severity | Description |
|---|---|---|
| `lecturer_double_booking` | High | Lecturer already scheduled at that time |
| `room_double_booking` | High | Room already booked |
| `student_overlap` | Medium | Student has overlapping courses |
| `department_conflict` | Medium | Department exceeds daily class limit (8) |
| `time_slot_unavailable` | High/Medium | Outside hours (8AM-9PM) or too short (<30 min) |

### Schedule Properties
- Institution-bound
- Course, lecturer, room assignment
- Day of week (1=Monday through 7=Sunday)
- Start/end time (HH:MM format)
- Date range (start_date, end_date)
- Recurring or single session

### Class Session Generation
- Generates individual class sessions from recurring schedules
- Creates sessions for each matching weekday within date range
- Session includes: date, time, room, topic, status

### Scheduling Endpoints
| Method | Path | Auth | Role | Description |
|---|---|---|---|---|
| POST | `/api/schedules` | Yes | Admin | Create schedule with conflict check |
| GET | `/api/schedules/{id}/conflicts` | Yes | Admin | Check schedule conflicts |

### Schedule Optimization
- Built-in optimizer analyzes room utilization
- Identifies underutilized rooms (usage < 10 slots)
- Suggests consolidation or rescheduling

---

## 9. Security & Anti-Proxy System

### Multi-Layered Security Architecture

**Layer 1: Authentication Security**
- bcrypt password hashing
- JWT with expiration
- Configurable session timeout (default 30 min)
- Login attempt limiting (configurable: default 5 attempts)
- Account lockout on excessive failures (configurable: default 15 min)
- Optional two-factor authentication

**Layer 2: Device Security**
- Device fingerprinting (see section 10)
- Trusted device tracking
- New device detection with risk scoring
- Multiple device anomaly detection

**Layer 3: Location Security**
- GPS geolocation verification
- Configurable geofence radius (default 100m)
- Distance calculation using geodesic (Haversine formula)
- Boundary proximity alerts (80% of radius)

**Layer 4: Timing Security**
- Session expiry enforcement
- Rapid succession detection (2+ marks in 5 minutes)
- Time anomaly detection (30 min deviation from pattern)
- Session duration limits

**Layer 5: IP Security**
- IP restriction whitelist per session
- Geo-IP tracking
- Unusual IP pattern detection

### Security Event Logging
All security events logged to `security_logs` collection:
- `login_success` / `login_failed`
- `logout`
- Suspicious attendance activities
- Risk scores for each event
- IP address, user agent, geolocation recorded

### Security Configuration (Admin UI)
Configurable via Security dashboard:
- Session timeout period
- Max login attempts before lockout
- Lockout duration
- Two-factor requirement
- Threat score threshold
- Anomaly detection sensitivity
- Geofencing radius
- Strong password policy
- IP whitelist
- Device tracking
- Auto-lockout
- Real-time monitoring

### Audit Logging
Every API access is logged via `@log_access` decorator:
- User ID, institution ID
- HTTP method and path
- IP address and user agent
- Timestamp
- Success/failure status

Audit logs configurable for:
- Retention period (default 90 days)
- Auto-archive (default 30 days)
- Auto-cleanup
- Multiple log categories (security, user activity, system changes, API calls)
- Email/SMS alerts for critical events

---

## 10. Device Fingerprinting

### `DeviceFingerprintService` in `auth_service.py`

### Data Collected
| Attribute | Description |
|---|---|
| User Agent | Browser and OS info |
| IP Address | Network location |
| Screen Resolution | Display dimensions |
| Timezone | User's timezone |
| Language | Browser language |
| Platform | OS platform |
| Hardware Concurrency | CPU cores |
| Canvas Fingerprint | HTML canvas rendering |
| WebGL Renderer | GPU information |
| Plugins | Browser plugins list |
| Fonts | Installed fonts |
| Local/Session Storage | Storage availability |
| IndexedDB | Database availability |

### Fingerprint Generation
1. All device attributes serialized to string
2. SHA-256 hash computed
3. Hash stored in `device_fingerprints` collection
4. Each fingerprint linked to user ID

### Trusted Devices
- Devices can be marked as "trusted"
- Trusted devices bypass certain security checks
- Trust score increases with successful verifications
- Score ranges 0.0 (unknown) to 1.0 (fully trusted)

### Similarity Scoring
When verifying a returning device:
1. Current fingerprint data collected
2. Compared against all enrolled fingerprints
3. Weighted comparison of key fields (user-agent, screen, timezone, etc.)
4. Array comparison for fonts and plugins (Jaccard similarity)
5. Match threshold: 80% similarity
6. Trust score increases by 0.05 per successful verification

---

## 11. Biometric Enrollment

### `BiometricService` in `biometric_service.py`

### Enrollment Process
1. Device data collected from client
2. SHA-256 hash of all fingerprint attributes
3. Stored in `biometric_enrollments` collection
4. Initial trust score: 0.7
5. Each verification increases trust score by 0.05 (max 1.0)

### Verification Process
1. Current device data collected
2. Hash computed and compared against enrolled hashes
3. Detailed similarity scoring across key fields
4. Active enrollments only (deactivated enrollments excluded)

### Management
- Users can view their enrolled devices
- Users can revoke enrollments (soft delete by setting `is_active = false`)
- Revocation reason recorded
- Admin can view all biometric statuses

### Endpoints (backed by BiometricService)
- Enroll device fingerprint
- Verify device fingerprint
- Get user biometric status
- Revoke biometric enrollment

---

## 12. Super Admin Dashboard

### Route: `/admin/dashboard`

### Navigation Sidebar
| Nav Item | Path | Description |
|---|---|---|
| Dashboard | `/admin/dashboard` | System overview |
| Institutions | `/admin/create_institution` | Institution management |
| Users | `/admin/users` | User management |
| Monitoring | `/admin/monitoring` | System monitoring |
| Security | `/admin/security` | Security settings |
| Backup & Restore | `/admin/backup` | Backup management |
| Notifications | `/admin/notifications` | Notification management |
| Audit Logs | `/admin/audit` | Audit trail |
| Role Assignments | `/admin/roles` | Role management |
| Profile | `/admin/profile` | Admin profile |

### Dashboard Features
- **System Status Panel**: Database, API, Storage (78% used), Last Backup status
- **Stats Cards**: Total Institutions (24), Total Users (8,456), Today's Attendance (12,843), System Load (42%)
- **Quick Actions**: Add Institution, Manage Users, View Analytics, System Backup

### Sub-Pages

#### Institutions Management (`/admin/institutions`, `/admin/institutions/create`)
- List all institutions with search/filter
- Create new institution form
- Edit institution details
- Institution status management (active/inactive)
- Institution analytics and reports

#### User Management (`/admin/users`)
**Features**:
- User statistics (total, active, inactive, new this month)
- Search by name/email/ID
- Filter by role (super_admin, institutional_admin, lecturer, student, employee)
- Filter by status (active, inactive, suspended)
- User table with columns: User, Role, Status, Last Active, Actions
- **Add User Modal**: First/Last name, Email, Phone, Role, Institution, Department, Password, Welcome email option
- **Edit User Modal**: Edit name, email, role, status
- **Delete User**: Confirmation dialog, progress animation
- **Suspend User**: Confirmation dialog, progress animation
- **Export Users**: Download user data

#### System Monitoring (`/admin/monitoring`)
**Metrics** (placeholder - planned):
- Server uptime
- CPU usage
- Memory usage
- Database connections
- Performance thresholds (CPU: 80%, Memory: 85%, Disk: 90%)
- Alert configuration
- Data retention settings
- Auto-refresh interval
- Metric tracking selection (CPU, Memory, Disk, Network, Response Time, Error Rate)

#### Security Dashboard (`/admin/security`)
**Features**:
- Security events count
- Active sessions
- Failed logins
- Security alerts
- **Planned**: Threat detection, Access control, MFA, API security, Security alerts, Audit trail

**Configuration**:
- Session timeout (5-480 min)
- Max login attempts (1-10)
- Lockout duration (1-1440 min)
- Two-factor authentication
- Threat score threshold
- Anomaly detection sensitivity
- Geofencing radius
- Strong password policy
- IP whitelist
- Device tracking
- Auto-lockout
- Real-time monitoring

#### Backup & Restore (`/admin/backup`)
- Manual backup creation
- Scheduled backup configuration
- Backup list with timestamps
- Restore from backup
- Backup settings (retention, storage location, encryption)

#### Notifications Management (`/admin/notifications`)
- Notification templates
- Send broadcast notifications
- Notification history
- Notification preferences per institution

#### Audit Logs (`/admin/audit`)
- Complete audit trail
- Advanced search by user, date, event type
- Filter by severity
- **Export**: CSV, JSON, PDF, XML, Excel formats
- Date range filtering (today, yesterday, last 7/30/90 days, custom)
- Log categories: security, user activity, system changes, login events, API calls
- Configurable retention (1-365 days)
- Auto-archive and cleanup
- Real-time monitoring toggle
- Email/SMS alerts for critical events

#### Role Assignments (`/admin/roles`)
- View all roles and their permissions
- Assign roles to users
- Permission matrix display
- Custom role creation (planned)

#### Admin Profile (`/admin/profile`)
- View/edit profile information
- Change password
- Profile picture upload
- Notification preferences
- Account security settings

#### System Settings (`/admin/settings`)
- General system configuration
- Email settings
- Security policies
- Integration settings
- API key management

#### Reports (`/admin/reports`)
- Report generation
- Multiple format export
- Scheduled reports
- Custom report builder

---

## 13. Institutional Admin Dashboard

### Route: `/institutional-admin/dashboard`

### Features
- **Stats Cards**: Total Students, Total Courses, Today's Attendance %, Active Sessions
- **Quick Actions**: Manage Courses, View Reports, Generate Vouchers, System Settings
- Institution-specific data (scoped to their institution)

### Capabilities
- Manage departments within their institution
- Create/manage users (lecturers, students)
- Generate vouchers for their institution
- View institution analytics and reports
- Manage courses and schedules
- View attendance reports
- Approve leave requests
- View audit logs

---

## 14. Lecturer Dashboard

### Route: `/lecturer/dashboard`

### Features
- **Stats Cards**: My Courses, Today's Sessions, Attendance Rate, Pending Tasks
- **Quick Actions**: Start Attendance Session, View My Schedule, Grade Attendance, Course Management
- Session management (create QR sessions, close sessions)
- View attendance statistics per course

### Lecturer Permissions
- View assigned courses
- Create attendance sessions (QR-based)
- Mark attendance manually
- View attendance reports for their courses
- View their schedule
- Submit leave requests
- View analytics

---

## 15. Student Dashboard

### Route: `/student/dashboard`

### Features
- **Stats Cards**: My Attendance %, Enrolled Courses, Upcoming Classes, Pending Leaves
- **Quick Actions**: Mark Attendance, View Schedule, Check Grades, Request Leave
- Attendance history view
- Course enrollment overview

### Student Permissions
- View enrolled courses
- Mark attendance (via QR code/session code)
- View personal attendance records
- View their schedule
- Submit leave requests
- View analytics

---

## 16. Landing Page

### Route: `/`

### Sections
1. **Navigation**: Home, Features, Contact, Sign Up, Login buttons
2. **Hero**:
   - Animated tagline: "Secure. Smart. Structured Attendance."
   - "Get Started" and "Request Live Demo" CTAs
   - Live dashboard preview mockup with animated chart bars
3. **Features** (6 cards):
   - Real-Time Attendance Tracking
   - Anti-Proxy Attendance System
   - Analytics & Reports
   - Smart Notifications
   - Role-Based Access
   - Secure Cloud Storage
4. **Contact**: Email (alexiscrazy605@gmail.com), WhatsApp (+237 65303-1002)
5. **Footer**: Login, Sign Up, Features, Contact links

### Interactive Elements
- Mobile-responsive hamburger menu
- Navbar scroll effect (adds shadow on scroll)
- Smooth scrolling for anchor links
- Intersection Observer animations for feature cards
- Animated chart bars in dashboard mockup

---

## 17. API Endpoints

### Complete Endpoint Reference

#### Authentication
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | No | Login with email/password |
| POST | `/api/auth/register` | No | Register new user with voucher |
| POST | `/api/auth/signup` | No | Alias for register |
| POST | `/api/auth/refresh` | No | Refresh access token |
| POST | `/api/auth/logout` | Yes | Logout user |
| GET | `/login` | No | Login page |
| GET | `/signup` | No | Signup page |
| GET | `/signup-voucher` | No | Voucher signup page |
| GET | `/logout` | No | Logout page |

#### User
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/users/profile` | Yes | Get current user profile |

#### Dashboard
| Method | Path | Auth | Role | Description |
|---|---|---|---|---|
| GET | `/api/dashboard` | Yes | Any | Role-based dashboard data |
| GET | `/admin/dashboard` | Yes | Super Admin | Admin dashboard page |
| GET | `/institutional-admin/dashboard` | Yes | Institutional Admin | Institute admin page |
| GET | `/lecturer/dashboard` | Yes | Lecturer | Lecturer page |
| GET | `/student/dashboard` | Yes | Student | Student page |

#### Admin Pages
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/admin/institutions` | Yes | Institutions management |
| GET | `/admin/institutions/create` | Yes | Create institution form |
| GET | `/admin/users` | Yes | User management |
| GET | `/admin/monitoring` | Yes | System monitoring |
| GET | `/admin/security` | Yes | Security settings |
| GET | `/admin/backup` | Yes | Backup & restore |
| GET | `/admin/notifications` | Yes | Notifications |
| GET | `/admin/audit` | Yes | Audit logs |
| GET | `/admin/roles` | Yes | Role assignments |
| GET | `/admin/profile` | Yes | Admin profile |
| GET | `/admin/settings` | Yes | System settings |
| GET | `/admin/reports` | Yes | Reports |

#### Scheduling
| Method | Path | Auth | Role | Description |
|---|---|---|---|---|
| POST | `/api/schedules` | Yes | Admin | Create schedule |
| GET | `/api/schedules/{id}/conflicts` | Yes | Admin | Check conflicts |

#### Attendance
| Method | Path | Auth | Role | Description |
|---|---|---|---|---|
| POST | `/api/attendance/create-session` | Yes | Lecturer | Create QR session |
| POST | `/api/attendance/mark` | Yes | Student | Mark attendance |
| POST | `/api/attendance/close-session/{id}` | Yes | Lecturer | Close session |
| GET | `/api/attendance/sessions/{id}/statistics` | Yes | Lecturer/Admin | Session stats |

#### Vouchers
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/voucher/validate/{code}` | No | Validate voucher |
| POST | `/api/voucher/generate-batch` | Yes (admin) | Generate batch |
| GET | `/api/voucher/statistics/{institution_id}` | Yes (admin) | Usage stats |
| POST | `/system/voucher/seed` | No | Seed initial vouchers |
| POST | `/system/voucher/force-reseed` | No | Force reseed |
| GET | `/system/voucher/check` | No | Check status |
| GET | `/system/voucher/debug` | No | Debug listing |

#### System
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | No | Landing page |
| GET | `/health` | No | Health check |
| POST | `/api/demo/request` | No | Demo request form |
| GET | `/api/docs` | No | API documentation |

---

## 18. Database Schema

### Firestore Collections

#### `users`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key (Firebase UID) |
| email | string | Unique email (lowercase) |
| password_hash | string | bcrypt hash |
| first_name | string | User's first name |
| last_name | string | User's last name |
| role | string | Enum: institutional_admin, lecturer, student |
| institution_id | string | FK to institutions |
| phone | string? | Optional phone |
| profile_image_url | string? | Profile picture URL |
| is_active | boolean | Account active flag |
| email_verified | boolean | Email verification status |
| last_login | datetime? | Last login timestamp |
| device_fingerprint | string? | Linked device hash |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Update timestamp |

#### `institutions`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| name | string | Institution name |
| code | string | Unique institution code |
| address | text | Physical address |
| phone | string? | Contact phone |
| email | string? | Contact email |
| website | string? | Website URL |
| logo_url | string? | Logo URL |
| is_active | boolean | Active flag |
| settings | map | Institution settings |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Update timestamp |

#### `departments`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| institution_id | string | FK to institutions |
| name | string | Department name |
| code | string | Department code |
| description | string? | Description |
| head_id | string? | FK to users (department head) |
| is_active | boolean | Active flag |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Update timestamp |

#### `courses`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| institution_id | string | FK to institutions |
| department_id | string? | FK to departments |
| name | string | Course name |
| code | string | Course code |
| description | string? | Description |
| credits | integer | Credit hours |
| lecturer_id | string? | FK to users (lecturer) |
| is_active | boolean | Active flag |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Update timestamp |

#### `course_enrollments`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| course_id | string | FK to courses |
| student_id | string | FK to users |
| enrollment_date | datetime | Enrollment date |
| is_active | boolean | Active flag |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Update timestamp |

#### `schedules`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| institution_id | string | FK to institutions |
| course_id | string | FK to courses |
| lecturer_id | string | FK to users |
| room_id | string? | Room identifier |
| day_of_week | integer | 1-7 (Mon-Sun) |
| start_time | string | HH:MM format |
| end_time | string | HH:MM format |
| start_date | datetime? | Schedule start |
| end_date | datetime? | Schedule end |
| is_recurring | boolean | Recurring flag |
| is_active | boolean | Active flag |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Update timestamp |

#### `class_sessions`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| schedule_id | string | FK to schedules |
| course_id | string | FK to courses |
| lecturer_id | string | FK to users |
| session_date | datetime | Class date |
| start_time | datetime | Start time |
| end_time | datetime | End time |
| room_id | string? | Room |
| topic | string? | Class topic |
| notes | string? | Session notes |
| status | string | scheduled/active/completed/cancelled |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Update timestamp |

#### `attendance_sessions`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| class_session_id | string? | FK to class_sessions |
| course_id | string | FK to courses |
| lecturer_id | string | FK to users |
| session_code | string | Unique 6-char code |
| start_time | datetime | Session start |
| end_time | datetime? | Session end |
| location | string? | Location description |
| is_active | boolean | Active flag |
| geolocation_enabled | boolean | GPS required |
| geolocation_lat | float? | Center latitude |
| geolocation_lng | float? | Center longitude |
| geolocation_radius | integer | Radius in meters (default 100) |
| ip_restriction_enabled | boolean | IP whitelist enabled |
| allowed_ips | array | Allowed IPs |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Update timestamp |

#### `attendance_records`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| session_id | string | FK to attendance_sessions |
| attendance_session_id | string | FK (alternate) |
| student_id | string | FK to users |
| mark_time | datetime | When marked |
| marked_at | datetime | When marked (alternate) |
| status | string | present/absent/late/excused |
| location | string? | GPS or description |
| ip_address | string? | Client IP |
| device_id | string? | Device fingerprint |
| user_agent | string? | Browser info |
| geolocation_lat | float? | Marking latitude |
| geolocation_lng | float? | Marking longitude |
| is_late | boolean | Late flag |
| minutes_late | integer | Minutes late |
| notes | string? | Notes |
| is_suspicious | boolean | Suspicious flag |
| suspicion_reason | string? | Reason |
| verification_method | string? | qr_code/manual/biometric |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Update timestamp |

#### `vouchers`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| code | string | Unique 8-char code |
| email_binding | string? | Bound email |
| role | string | Target role |
| institution_id | string | FK to institutions |
| is_used | boolean | Used flag |
| used_by | string? | FK to users who used it |
| used_at | datetime? | When used |
| created_at | datetime | Creation timestamp |
| expires_at | datetime | Expiry timestamp |
| generated_by | string | Creator identifier |
| batch_id | string | Batch identifier |

#### `device_fingerprints`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| user_id | string | FK to users |
| fingerprint_hash | string | SHA-256 hash |
| fingerprint | string? | Legacy fingerprint |
| user_agent | string | Browser info |
| ip_address | string | Client IP |
| screen_resolution | string? | Screen dimensions |
| timezone | string? | Timezone |
| language | string? | Browser language |
| is_trusted | boolean | Trusted flag |
| last_seen | datetime | Last seen timestamp |
| last_used | datetime? | Last used timestamp |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Update timestamp |

#### `trusted_devices`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| user_id | string | FK to users |
| device_fingerprint | string | Device hash |
| browser_info | string? | Browser info |
| first_login_date | datetime | First seen |
| last_active_date | datetime | Last active |
| trust_status | string | trusted/revoked |
| session_token | string? | Device session token |

#### `login_sessions`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| user_id | string | FK to users |
| ip_address | string? | Login IP |
| user_agent | string? | Browser info |
| device_fingerprint | string? | Device hash |
| login_time | datetime | Login timestamp |
| logout_time | datetime? | Logout timestamp |
| is_active | boolean | Active flag |

#### `persistent_sessions`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| user_id | string | FK to users |
| device_fingerprint | string? | Device hash |
| created_at | datetime | Creation timestamp |
| expires_at | datetime | 30-day expiry |
| last_accessed | datetime | Last use |
| logged_out_at | datetime? | Logout timestamp |

#### `security_logs`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| user_id | string? | FK to users |
| institution_id | string? | FK to institutions |
| event_type | string | login_success/login_failed/logout/etc. |
| description | text | Event description |
| ip_address | string? | Client IP |
| user_agent | text? | Browser info |
| device_fingerprint | string? | Device hash |
| geolocation_lat | float? | Latitude |
| geolocation_lng | float? | Longitude |
| risk_score | integer | 0-100 risk rating |
| is_resolved | boolean | Resolved flag |
| resolved_by | string? | Resolver user ID |
| resolved_at | datetime? | Resolution time |
| created_at | datetime | Creation timestamp |

#### `audit_logs`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| user_id | string? | FK to users |
| institution_id | string? | FK to institutions |
| action | string | HTTP method + path |
| resource_type | string | API resource type |
| resource_id | string? | Affected resource |
| old_values | map | Previous state |
| new_values | map | New state |
| ip_address | string? | Client IP |
| user_agent | string? | Browser info |
| timestamp | datetime | Event timestamp |

#### `biometric_enrollments`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| user_id | string | FK to users |
| biometric_type | string | device_fingerprint |
| biometric_data | string | SHA-256 hash |
| device_metadata | map | Full device data |
| is_active | boolean | Active flag |
| enrollment_date | datetime | Enrollment date |
| last_verified | datetime | Last verification |
| verification_count | integer | Total verifications |
| trust_score | float | 0.0-1.0 trust score |
| revoked_date | datetime? | Revocation date |
| revocation_reason | string? | Reason |

#### `notifications`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| user_id | string | FK to users |
| institution_id | string | FK to institutions |
| title | string | Notification title |
| message | string | Notification body |
| type | string | info/warning/error/success |
| is_read | boolean | Read flag |
| action_url | string? | Action link |
| metadata | map | Extra data |
| created_at | datetime | Creation timestamp |
| read_at | datetime? | Read timestamp |

#### `leave_requests`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| user_id | string | FK to users |
| institution_id | string | FK to institutions |
| leave_type | string | Type of leave |
| start_date | datetime | Leave start |
| end_date | datetime | Leave end |
| reason | string | Reason for leave |
| attachment_url | string? | Supporting doc |
| status | string | pending/approved/rejected/cancelled |
| approved_by | string? | Approver user ID |
| approved_at | datetime? | Approval time |
| rejection_reason | string? | Rejection reason |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Update timestamp |

#### `system_configurations`
| Field | Type | Description |
|---|---|---|
| id | string | Primary key |
| institution_id | string? | Null = global config |
| key | string | Config key |
| value | string | Config value |
| description | string? | Description |
| is_active | boolean | Active flag |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Update timestamp |

---

## 19. Entity Models

All entities defined in `src/domain/entities.py`:

| Entity | Type | Key Fields |
|---|---|---|
| `UserRole` | Enum | SUPER_ADMIN, INSTITUTIONAL_ADMIN, LECTURER, STUDENT |
| `AttendanceStatus` | Enum | PRESENT, ABSENT, LATE, EXCUSED |
| `LeaveStatus` | Enum | PENDING, APPROVED, REJECTED, CANCELLED |
| `SessionStatus` | Enum | SCHEDULED, ACTIVE, COMPLETED, CANCELLED |
| `User` | Class | id, institution_id, email, password_hash, first_name, last_name, role, phone, profile_image_url, is_active, email_verified, last_login, created_at, updated_at |
| `UserProfile` | Dataclass | id, user_id, employee_id, student_id, date_of_birth, gender, address, emergency_contact, department_id, join_date, metadata |
| `Institution` | Dataclass | id, name, code, address, phone, email, website, logo_url, is_active, settings |
| `Department` | Dataclass | id, institution_id, name, code, description, head_id, is_active |
| `Course` | Dataclass | id, institution_id, department_id, code, name, description, credits, lecturer_id, is_active |
| `CourseEnrollment` | Dataclass | id, course_id, student_id, enrollment_date, is_active |
| `Schedule` | Dataclass | id, institution_id, course_id, lecturer_id, room_id, day_of_week, start_time, end_time, start_date, end_date, is_recurring, is_active |
| `ClassSession` | Dataclass | id, schedule_id, course_id, lecturer_id, session_date, start_time, end_time, room_id, topic, notes, status |
| `AttendanceSession` | Dataclass | id, class_session_id/course_id, session_code, start_time, end_time, geolocation_enabled, geolocation_lat/lng, geolocation_radius, ip_restriction_enabled, allowed_ips, is_active |
| `AttendanceRecord` | Dataclass | id, attendance_session_id, student_id, marked_at, status, marked_by, ip_address, user_agent, geolocation_lat/lng, is_late, minutes_late, notes, is_suspicious, suspicion_reason |
| `Voucher` | Class | id, code, email, role, institution_id, is_used, created_at, used_at, expires_at |
| `LeaveRequest` | Dataclass | id, user_id, institution_id, leave_type, start_date, end_date, reason, attachment_url, status, approved_by, approved_at, rejection_reason |
| `AuditLog` | Dataclass | id, user_id, institution_id, action, resource_type, resource_id, old_values, new_values, ip_address, user_agent, timestamp |
| `SecurityLog` | Dataclass | id, user_id, institution_id, event_type, description, ip_address, user_agent, geolocation_lat/lng, risk_score, is_resolved, resolved_by, resolved_at |
| `DeviceFingerprint` | Dataclass | id, user_id, fingerprint_hash, user_agent, ip_address, screen_resolution, timezone, language, is_trusted, last_seen |
| `Notification` | Dataclass | id, user_id, institution_id, title, message, type, is_read, action_url, metadata, read_at |
| `SystemConfiguration` | Dataclass | id, institution_id, key, value, description, is_active |

---

## 20. Infrastructure

### Firebase Service (`src/infrastructure/firebase_service.py`)

**Dual-Mode Operation**:
- **Production Mode**: Uses Firebase Admin SDK (real Firestore + Firebase Auth)
- **Mock Mode**: Uses JSON file (`mock_database.json`) for development (no Firebase setup needed)

**Mock Database Collections**:
- `users`, `vouchers`, `device_fingerprints`, `trusted_devices`, `login_sessions`, `authentication_logs`

**Firebase Service Methods**:
| Method | Description |
|---|---|
| `initialize(credentials_path, project_id)` | Initialize SDK or mock mode |
| `create_user(email, password, display_name, ...)` | Create Firebase Auth user |
| `update_user(uid, **kwargs)` | Update user properties |
| `delete_user(uid)` | Delete Firebase user |
| `get_user(uid)` | Get by UID |
| `get_user_by_email(email)` | Get by email |
| `verify_id_token(token)` | Verify Firebase ID token |
| `set_custom_claims(uid, claims)` | Set role claims |
| `disable_user(uid)` | Disable account |
| `enable_user(uid)` | Enable account |
| `reset_password(email)` | Generate reset link |
| `verify_email(email)` | Generate verification link |
| `create_document(collection, data, doc_id)` | Firestore create |
| `get_document(collection, doc_id)` | Firestore read |
| `update_document(collection, doc_id, data)` | Firestore update |
| `delete_document(collection, doc_id)` | Firestore delete |
| `query_documents(collection, filters, limit, order)` | Firestore query |
| `batch_write(operations)` | Batch operations |

### Repository Pattern (`src/infrastructure/repositories.py`)

Base repository provides: `create`, `get_by_id`, `get_by_field`, `get_by_multiple_fields`, `update`, `delete`, `list_all`

**Specialized Repositories**:
| Repository | Collection | Additional Methods |
|---|---|---|
| `InstitutionRepository` | institutions | `get_by_code`, `get_active_institutions` |
| `DepartmentRepository` | departments | `get_by_institution`, `get_by_code` |
| `UserRepository` | users | `get_by_email`, `get_by_institution`, `get_by_role`, `get_by_institution_and_role`, `get_active_users` |
| `UserProfileRepository` | user_profiles | `get_by_user`, `get_by_student_id`, `get_by_employee_id` |
| `CourseRepository` | courses | `get_by_institution`, `get_by_department`, `get_by_lecturer`, `get_by_code` |
| `CourseEnrollmentRepository` | course_enrollments | `get_by_student`, `get_by_course`, `get_active_enrollments` |
| `ScheduleRepository` | schedules | `get_by_institution/course/lecturer/day_of_week`, `get_conflicting_schedules` |
| `ClassSessionRepository` | class_sessions | `get_by_schedule/course/lecturer/date_range` |
| `AttendanceSessionRepository` | attendance_sessions | `get_by_class_session`, `get_active_sessions`, `get_by_session_code` |
| `AttendanceRecordRepository` | attendance_records | `get_by_session/student/student_and_session`, `get_suspicious_records` |
| `LeaveRequestRepository` | leave_requests | `get_by_user/institution/status`, `get_pending_requests` |
| `AuditLogRepository` | audit_logs | `get_by_user/institution/action/date_range` |
| `SecurityLogRepository` | security_logs | `get_by_user/institution/event_type`, `get_high_risk_events` |
| `DeviceFingerprintRepository` | device_fingerprints | `get_by_user/hash`, `get_trusted_devices` |
| `NotificationRepository` | notifications | `get_by_user`, `get_unread`, `get_by_institution` |
| `SystemConfigurationRepository` | system_configurations | `get_by_key`, `get_by_institution`, `get_global_configurations` |

### PostgreSQL Schema (`src/infrastructure/database_schema.py`)
Defines SQL DDL for:
- `users` (with role enum, indexes on email/institution_id/role)
- `institutions` (unique code)
- `departments` (FK to institutions)
- `courses` (FKs to institutions, departments, users)
- `attendance_sessions` (FKs to courses, users)
- `attendance_records` (FKs to sessions, users)
- `vouchers` (unique code, FK to institutions)
- `persistent_sessions` (FK to users)
- `security_logs` (FKs to users, institutions)

---

## 21. Configuration System

### Environment-Based Configuration

| Environment | Class | Debug | Database | Security |
|---|---|---|---|---|
| Development | `DevelopmentConfig` | True | SQLite | Relaxed (no HTTPS cookies) |
| Staging | `StagingConfig` | False | PostgreSQL | Standard |
| Production | `ProductionConfig` | False | PostgreSQL | Strict (HTTPS cookies, Sentry) |

### All Configuration Keys (in `config/settings.py`)

| Key | Default | Description |
|---|---|---|
| `SECRET_KEY` | dev-secret-key | Flask secret |
| `ENVIRONMENT` | development | Runtime environment |
| `FIREBASE_CREDENTIALS_PATH` | firebase-dev.json | Firebase service account |
| `FIREBASE_PROJECT_ID` | attendrix-dev | Firebase project |
| `FIREBASE_DATABASE_URL` | https://attendrix-dev.firebaseio.com | Firestore URL |
| `DATABASE_URL` | sqlite:///attendrix.db | PostgreSQL connection |
| `REDIS_URL` | redis://localhost:6379/0 | Redis connection |
| `MAIL_SERVER` | smtp.gmail.com | SMTP server |
| `MAIL_PORT` | 587 | SMTP port |
| `MAIL_USE_TLS` | True | TLS enabled |
| `RATELIMIT_STORAGE_URL` | redis://localhost:6379/1 | Rate limit storage |
| `RATELIMIT_DEFAULT` | 200/day, 50/hour | Default limits |
| `MAX_CONTENT_LENGTH` | 16MB | Upload size limit |
| `SESSION_TIMEOUT_MINUTES` | 15 | Attendance session timeout |
| `MAX_LATE_MINUTES` | 10 | Late threshold |
| `DEFAULT_ATTENDANCE_THRESHOLD` | 75% | Minimum attendance |
| `GOOGLE_GEOCODING_API_KEY` | "" | Geocoding API |
| `DEFAULT_GEOLOCATION_RADIUS` | 100m | GPS radius |
| `CELERY_BROKER_URL` | redis://localhost:6379/3 | Celery broker |
| `CACHE_TYPE` | redis | Cache backend |
| `SENTRY_DSN` | "" | Error tracking |
| `CORS_ORIGINS` | [localhost:3000, localhost:5000] | Allowed origins |
| `ALLOWED_EXTENSIONS` | png, jpg, jpeg, gif, pdf, doc, docx | Upload types |

---

## 22. Development Mode

### Mock Firebase
```python
os.environ['USE_MOCK_FIREBASE'] = 'true'
```
When enabled, the Firebase service stores all data in `mock_database.json` instead of real Firebase. No actual Firebase credentials are needed.

### Auth Bypass
In development mode (`ENVIRONMENT=development`), the `@require_auth` decorator automatically creates mock user data based on URL path:
- `/admin/*` → super_admin role
- `/institutional-admin/*` → institutional_admin role
- `/lecturer/*` → lecturer role
- `/student/*` → student role

This allows direct URL access to dashboards without real authentication.

### Startup
```bash
python app.py  # Runs on port 5000 with hot-reload enabled
```

### Starting Fresh
Run these API calls to bootstrap the system:
1. `POST /system/voucher/seed` - Generate seed vouchers (ADMIN123, LECT4567-4569, STUD7890-7899)
2. Register users via the signup-voucher page using those codes
3. Login with registered credentials

---

## 23. Deployment

### Docker Deployment
```bash
docker-compose up -d
```
Docker Compose configuration includes:
- Flask app container (Gunicorn)
- Nginx reverse proxy
- Redis cache
- PostgreSQL database (optional)

### Manual Deployment
```bash
pip install -r requirements.txt
gunicorn app:app --workers 4 --bind 0.0.0.0:8000
```

### Environment Variables for Production
- `ENVIRONMENT=production`
- `DATABASE_URL=postgresql://...`
- `REDIS_URL=redis://...`
- `SECRET_KEY=<secure-random-key>`
- `FIREBASE_CREDENTIALS_PATH=/path/to/serviceAccount.json`
- `MAIL_USERNAME` / `MAIL_PASSWORD`
- `SENTRY_DSN` for error tracking

### Nginx Configuration (in `nginx/` directory)
- Static file serving
- Reverse proxy to Gunicorn
- SSL termination support
- Rate limiting at proxy level

---

## 24. Testing

The project includes extensive tests (30+ test files):

| Test File | What it Tests |
|---|---|
| `test_auth_service.py` | Authentication service unit tests |
| `test_routes.py` | Route accessibility |
| `test_all_routes.py` | Complete route coverage |
| `test_registration.py` | User registration flow |
| `test_login.py`, `test-login.py`, `test_login_full.py`, etc. | Login flow variants |
| `test_dashboard.py` | Dashboard page rendering |
| `test_admin_pages.py` | Admin page accessibility |
| `test_complete_dashboard.py` | Full dashboard functionality |
| `test_signup_functionality.py` | Signup process |
| `test_super_admin_dashboard.py` | Super admin specific tests |
| `test_lecturer_dashboard.py` | Lecturer dashboard tests |
| `test_student_dashboard_redesign.py` | Student dashboard tests |
| `test_institutional_dashboard.py` | Institutional admin tests |
| `test_various_navigation_tests.py` | Navigation flow tests |
| Various `test-*.py` files | Feature-specific integration tests |
| `verify_server_status.py` | Server health verification |
| `create_test_users.py` | Test user creation utility |

### Running Tests
```bash
pytest test_*.py -v
```

---

## Complete Feature Checklist

### Authentication & Security
- [x] Email/password login
- [x] JWT access + refresh tokens
- [x] bcrypt password hashing
- [x] "Remember me" persistent sessions (30 days)
- [x] Device fingerprinting
- [x] Trusted device management
- [x] Account lockout after failed attempts
- [x] Optional two-factor authentication
- [x] Password reset flow
- [x] Email verification
- [x] Account enable/disable
- [x] Rate limiting
- [x] Audit logging
- [x] Security event logging
- [x] Suspicious activity detection

### Registration
- [x] Voucher-based invitation system
- [x] Voucher code validation (format, expiry, usage)
- [x] Email binding on vouchers
- [x] Role-specific registration forms
- [x] Duplicate email prevention
- [x] Firebase Auth user creation

### Voucher Management
- [x] 8-character secure code generation
- [x] Batch generation (any quantity)
- [x] Role binding
- [x] Institution binding
- [x] Email binding (optional)
- [x] Expiry date (30/90 days configurable)
- [x] Usage tracking
- [x] Statistics by institution
- [x] Initial seed (1 admin + 3 lecturer + 10 student)
- [x] Force reseed capability
- [x] Debug listing

### Attendance
- [x] QR code session generation (base64 PNG)
- [x] 6-character session codes
- [x] Session duration control (60 min default)
- [x] GPS geolocation verification
- [x] IP restriction/whitelist
- [x] Device fingerprint validation
- [x] Rapid succession detection
- [x] Multiple device detection
- [x] Time anomaly detection
- [x] Proxy attendance prevention
- [x] Late marking detection
- [x] Session statistics (present/late/absent/excused)
- [x] Suspicious activity logging
- [x] Risk scoring (0-100)

### Scheduling
- [x] Recurring weekly schedules
- [x] Date range support
- [x] Lecturer conflict detection
- [x] Room conflict detection
- [x] Student overlap detection
- [x] Department policy enforcement
- [x] Time slot validation (8AM-9PM, min 30 min)
- [x] Automatic class session generation
- [x] Schedule optimization (room utilization)
- [x] Department schedule overview

### Roles & Permissions
- [x] Super Admin (full system access)
- [x] Institutional Admin (single institution)
- [x] Lecturer (course & attendance management)
- [x] Student (attendance marking & viewing)
- [x] 20 granular permissions
- [x] Permission-based access decorators
- [x] Role assignment UI
- [x] Role-based dashboard routing

### Super Admin Features
- [x] System status overview
- [x] Institution CRUD
- [x] User CRUD (search, filter, add, edit, delete, suspend)
- [x] System monitoring dashboard
- [x] Security configuration
- [x] Backup & restore management
- [x] Notification management
- [x] Audit log viewer & exporter (CSV/JSON/PDF/XML/Excel)
- [x] Role assignments
- [x] System settings
- [x] Reports
- [x] Profile management

### Institutional Admin Features
- [x] Institution-scoped dashboard
- [x] Department management
- [x] User management (lecturers & students)
- [x] Course management
- [x] Schedule management
- [x] Voucher generation
- [x] Attendance reports
- [x] Leave request approval

### Lecturer Features
- [x] Course list view
- [x] Attendance session creation (QR)
- [x] Session closure
- [x] Attendance statistics
- [x] Schedule view
- [x] Leave request submission

### Student Features
- [x] Attendance marking (QR/session code)
- [x] Personal attendance records
- [x] Enrolled courses list
- [x] Class schedule view
- [x] Leave request submission
- [x] Attendance percentage tracking

### Frontend/UI
- [x] Professional landing page with animated elements
- [x] Mobile-responsive design
- [x] Role-specific dashboards
- [x] Admin sidebar navigation (10+ pages)
- [x] Real-time clock display
- [x] Modal forms (add/edit user)
- [x] Toast notifications (success/error)
- [x] Progress animations (delete, suspend, export)
- [x] Search & filter functionality
- [x] Dropdown menus
- [x] Smooth scrolling
- [x] Intersection Observer animations

### Device Biometrics
- [x] Multi-attribute device fingerprinting (13+ attributes)
- [x] SHA-256 fingerprint hashing
- [x] Trust score tracking (0.0-1.0)
- [x] Similarity scoring with Jaccard index
- [x] Active/passive enrollment management
- [x] Revocation capability

### Infrastructure
- [x] Firebase Firestore integration
- [x] Firebase Auth integration
- [x] Mock database mode (JSON file)
- [x] PostgreSQL schema (migration scripts)
- [x] Repository pattern (17 repositories)
- [x] Redis caching support
- [x] Celery background tasks
- [x] Docker containerization
- [x] Nginx configuration
- [x] Environment-based configuration (3 environments)
- [x] Sentry error tracking (production)
- [x] CORS support
- [x] Rate limiting at application level
- [x] File upload support (16MB max)
