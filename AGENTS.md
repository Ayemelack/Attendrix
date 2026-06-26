$ @"
ATTENDRIX — AGENT.MG SPECIFICATION
=====================================
Generated: 2026-06-25 | Source: attendrix/ codebase analysis

================================================================================
1. PROJECT OVERVIEW
================================================================================

Name: Attendrix — Enterprise Institutional Paperless Attendance System
Stack: Python 3.x, Flask, Firebase (Auth + Firestore), SQLAlchemy, Redis,
       Jinja2, bcrypt, PyJWT, Cloudflare Turnstile
Architecture: Layered (Presentation → Application → Domain → Infrastructure)
Auth Strategy: Custom JWT (PyJWT) + Firebase Auth (UID creation) + Firestore
  (user profiles, password hashes). Custom auth — NOT Firebase Auth SDK login.
Primary File: attendrix/app.py — Application factory, all route definitions,
  middleware registration (~3973 lines)

Core Purpose: Multi-tenant attendance tracking for educational institutions.
  Supports 5 roles (super_admin, institutional_admin, lecturer, student,
  employee) with voucher-based registration, geolocation-verified attendance,
  face biometrics, and offline sync queues.

================================================================================
2. ARCHITECTURE
================================================================================

┌─────────────────────────────────────────────────────────────┐
│                   PRESENTATION LAYER                        │
│  routes/auth.py pages.py mail_routes mail_api_routes        │
│  api/feedback_routes.py                                     │
│  templates/ (login.html, signup.html, signup-voucher.html)  │
│  static/ (js/, css/)                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  APPLICATION LAYER                          │
│  auth_service.py     rbac.py     voucher_management_service │
│  DeviceFingerprintService        SecurityLog event logging  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    DOMAIN LAYER                             │
│  entities.py — User, UserRole, Institution, Course,         │
│    Schedule, AttendanceSession, AttendanceRecord, Voucher,  │
│    DeviceFingerprint, SecurityLog, LeaveRequest,            │
│    Notification, SystemConfiguration, DemoBooking           │
│  Enums: AttendanceStatus, SessionStatus, LeaveStatus        │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                 INFRASTRUCTURE LAYER                        │
│  firebase_service.py   sqlalchemy_db.py   redis_session_*   │
│  security_legacy.py    security_reinforcements.py           │
│  comprehensive_security.py   mail_service.py                │
│  repositories/   feedback_models.py   mail_models.py        │
│  demo_sql_repositories.py                                   │
└─────────────────────────────────────────────────────────────┘

MIDDLEWARE EXECUTION ORDER (all before_request handlers):       [Ref]
  1. security_legacy.validate_request_security()                [L1045]
     → CSRF validation (POST/PUT/PATCH, exempt auth paths)
     → User-Agent length check (max 500)
     → GLOBAL RATE LIMIT: key=global:ip:IP, per-endpoint limits [L1073]
  2. security_legacy.verify_content_type()                      [L1104]
  3. security_legacy.check_suspicious_request_patterns()       [L1112]
     → UA min length check (10), Referer origin validation
     → JSON field size limit (100K chars)
  4. comprehensive_security.comprehensive_security_before()    [comp:L1059]
     → Port scan detection, API content-type validation
     → Request size validation, blocked header check
     → JSON data structure validation
     → IP NETWORK RATE LIMIT: max 100/60s per IP              [L1092]
     → Behavioral tracking
  5. security_reinforcements.https_enforcement()               [reinf:L1099]
  6. security_reinforcements.production_server_check()         [L1103]
  7. security_reinforcements.registration_brute_force_check()  [L1107]
     → Per-email (3/hr) + per-IP (10/hr) for registration paths
  8. security_reinforcements.check_request_security()          [L1143]

BLUEPRINT REGISTRATIONS:                                       [app:L3888]
  pages_bp     @ /                   (page templates)
  auth_bp      @ /api/auth           (auth API + init_auth_routes)
  feedback_api @ /api/feedback       (feedback intelligence)
  mail_bp      @ /admin/mail         (Attendrix Mail admin)
  mail_api     @ /api/mail           (internal mail API)
  innovation_bp @ /api/innovation    (Smart Campus Suite, conditional)

================================================================================
3. DIRECTORY STRUCTURE
================================================================================

attendrix/
├── app.py                         # App factory + ALL inline route defs (3973L)
├── config/settings.py             # All config (~20K+ lines)
├── docker-compose.yml
├── .env / .env.example
├── tools/                         # HTTPS cert gen, etc.
├── scripts/                       # Seed/management
└── src/
    ├── domain/
    │   └── entities.py            # 28 entity classes, 5 enums (668L)
    ├── application/
    │   ├── auth_service.py        # AuthService + DeviceFingerprintService (674L)
    │   ├── rbac.py                # Permission + RolePermissions + decorators (492L)
    │   └── voucher_management_service.py
    ├── infrastructure/
    │   ├── firebase_service.py    # Firebase/Firestore abstraction (584L)
    │   ├── sqlalchemy_db.py       # SQLAlchemy engine/session, Base (35L)
    │   ├── security_legacy.py     # EnhancedRateLimiter, CaptchaVerifier,
    │   │                          # InputSanitizer, PasswordPolicy, CSRF,
    │   │                          # SecurityHeaders, AuditLogger (1286L)
    │   ├── security_reinforcements.py # RegistrationBruteForceGuard, HTTPSEnforcer,
    │   │                          # PasswordResetManager, etc. (1159L)
    │   ├── comprehensive_security.py  # IPNetworkSecurityManager, AccountSecurity,
    │   │                          # MultiTenantIsolator, APIHardener,
    │   │                          # BehavioralSecurity (1146L)
    │   ├── mail_service.py        # Email delivery
    │   ├── mail_models.py         # SQLA: MailSmtpProfile, MailTemplate, etc.
    │   ├── feedback_models.py     # SQLA: Feedback, ModerationLog, etc.
    │   ├── demo_sql_repositories.py # SQLA: DemoLead, DemoBooking, etc.
    │   ├── redis_session_store.py # Redis token blacklist + session
    │   └── repositories/          # Data access layer
    └── presentation/
        ├── routes/
        │   ├── auth.py            # Auth blueprint (276L)
        │   ├── pages.py           # Page route blueprint (246L)
        │   ├── mail_routes.py
        │   └── mail_api_routes.py
        ├── api/
        │   └── feedback_routes.py
        ├── templates/
        │   ├── login.html         # CAPTCHA + device fingerprint
        │   ├── signup.html
        │   └── signup-voucher.html # Multi-step flow
        └── static/
            ├── css/
            └── js/

"@ | Out-File -FilePath "C:\Users\noshi\OneDrive\fotsa\Achieved\AGENT.MG" -Encoding utf8
(no output)
$ @"

================================================================================
4. DATA FLOW (KEY PATHS)
================================================================================

4.1. VOUCHER REGISTRATION FLOW (e.g., Institutional Admin signup)

  Browser                          Server (app.py, auth.py, auth_service.py)
    │                                      │
    │  GET /signup-voucher                  │
    │─────────────────────────────────────>│  pages.py: signup_voucher_page()
    │    HTML: signup-voucher.html          │
    │<─────────────────────────────────────│
    │  [Step 1] Enter voucher code          │
    │  GET /api/voucher/validate/<code>     │
    │─────────────────────────────────────>│  app.py: validate_voucher()
    │   → Firestore query vouchers by code │
    │   {valid: true, role, institution_id} │
    │<─────────────────────────────────────│
    │  [Step 2] Fill registration form      │
    │  POST /api/auth/register             │
    │─────────────────────────────────────>│  auth.py: register()
    │                                      │  @require_captcha(action='register')
    │                                      │  @rate_limit_endpoint(5/3600s)
    │                                      │  InputSanitizer sanitize, PasswordPolicy
    │                                      │  auth_service.register_user():
    │                                      │    1. Query Firestore users by email
    │                                      │    2. Validate voucher via VoucherService
    │                                      │    3. bcrypt hash_password()
    │                                      │    4. firebase_service.create_user()
    │                                      │       → Firebase Auth UID created
    │                                      │    5. set_custom_claims(uid, role/inst)
    │                                      │    6. create_document('users', data, uid)
    │                                      │    7. consume_voucher()
    │   201 {user, \"Registration successful\"}
    │<─────────────────────────────────────│
    │  (Admin) → redirect to /login         │
    │  (Student/other) → success page       │

4.2. LOGIN FLOW

  Browser                          Server
    │                                      │
    │  GET /login                           │
    │─────────────────────────────────────>│  pages.py: login_page()
    │   HTML with Turnstile site key        │
    │<─────────────────────────────────────│
    │                                      │
    │  POST /api/auth/login                │
    │  {email, password, captchaToken,     │
    │   device_fingerprint, remember_me,   │
    │   institutionId?}                    │
    │─────────────────────────────────────>│
    │                                      │
    │  BEFORE_REQUEST HANDLERS (in order): │
    │                                      │
    │  1. validate_request_security()      │ [sec_legacy:L1045]
    │     CSRF check (skipped for login)   │
    │     → GLOBAL RATE LIMIT              │ [sec_legacy:L1073]
    │       key = global:ip:{ip}           │
    │       limit = 5 / 60s                │
    │       block_duration = 900s (15min)  │
    │     [429 if exceeded]               │
    │                                      │
    │  2. comprehensive_security_before()  │ [comp:L1059]
    │     → IP NETWORK RATE LIMIT          │ [comp:L1092]
    │       max_requests = 100, window=60  │
    │     [429 if exceeded]               │
    │                                      │
    │  3. registration_brute_force_check() │ [reinf:L1107]
    │     Not triggered (login path)       │
    │                                      │
    │  auth.py login() DECORATORS:         │
    │  @require_captcha(action='login')    │ [auth:L122]
    │    → Turnstile token verify         │
    │  @account_security.require_not_locked│ [auth:L123]
    │    (identifier_param='email')        │
    │  @rate_limit_endpoint(10/300s)       │ [auth:L124]
    │    → key = ip:{ip}                  │
    │                                      │
    │  INLINE: per-email rate limit        │ [auth:L146]
    │    key = login:{email}              │
    │    limit = 5 / 300s                 │
    │    block_duration = 600s            │
    │  [429 if exceeded]                  │
    │                                      │
    │  auth_service.authenticate_user():   │ [auth_svc:L210]
    │    1. query_documents('users',       │
    │       filters=[{email}])            │ ← 401 BUG: eventual consistency
    │    2. Check account locked           │
    │    3. Match institution_id           │
    │    4. verify_password (bcrypt)       │
    │    5. Check is_active               │
    │    6. Check password expiry (90d)    │
    │    7. Generate JWT access+refresh    │
    │    8. Reset failed attempts          │
    │    ← {success, user, tokens}         │
    │                                      │
    │    200 {access_token, refresh_token} │
    │<─────────────────────────────────────│

4.3. ATTENDANCE MARKING FLOW (Student)

  Mobile Browser                     Server
    │                                      │
    │  POST /api/student/verify-scan       │
    │  {session_code, geolocation?}        │
    │─────────────────────────────────────>│  app.py: student_verify_scan()
    │   @require_auth (JWT token check)    │
    │   → Find active AttendanceSession    │
    │     by session_code                  │
    │   → Check session active + active    │
    │   → Geo-fence check (if enabled)     │
    │   → IP restriction check (if enabled)│
    │   → Create AttendanceRecord          │
    │     (student_id from JWT)            │
    │   → 200 {success, status: present,   │
    │          marked_at}                  │
    │<─────────────────────────────────────│

4.4. ATTENDANCE SESSION CREATION FLOW (Lecturer)

  Browser                             Server
    │                                      │
    │  POST /api/attendance/create-session │
    │  {course_id, geolocation, ip_restrict}│
    │─────────────────────────────────────>│  app.py
    │   @require_auth + @require_role      │
    │   → Generate session_code (8-char)   │
    │   → Create AttendanceSession doc     │
    │   → 201 {session_id, session_code}   │
    │<─────────────────────────────────────│

"@ | Out-File -FilePath "C:\Users\noshi\OneDrive\fotsa\Achieved\AGENT.MG" -Encoding utf8 -Append
(no output)
$ @"

================================================================================
5. DATABASE SCHEMA
================================================================================

5.1. FIRESTORE COLLECTIONS (primary datastore — all user/domain data)

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION:  users/{firebase_uid}                                   │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, user_id (same as firebase_uid), email, password_hash (bcrypt)   │
  │ first_name, last_name, role, institution_id                         │
  │ phone?, profile_image_url?, is_active, email_verified, phone_verified│
  │ last_login?, created_at, updated_at                                 │
  │ failed_login_attempts, locked_until?, password_history[],            │
  │ password_updated_at                                                 │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: vouchers/{id} (role-granting registration codes)        │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, code, email, role, institution_id, is_used                      │
  │ created_at, used_at?, expires_at (7-day default expiry)             │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: institutions/{id}                                       │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, name, code, address, phone, email, website?, logo_url?          │
  │ is_active, settings (dict), created_at, updated_at                  │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: departments/{id}                                        │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, institution_id, name, code, description?, head_id?, is_active   │
  │ created_at, updated_at                                              │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: courses/{id}                                            │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, institution_id, department_id, code, name, description?         │
  │ credits, lecturer_id?, is_active, created_at, updated_at            │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: course_enrollments/{id}                                 │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, course_id, student_id, enrollment_date, is_active               │
  │ created_at, updated_at                                              │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: schedules/{id}  (recurring schedule templates)          │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, institution_id, course_id, lecturer_id, room_id?                │
  │ day_of_week (1-7), start_time (HH:MM), end_time (HH:MM)            │
  │ start_date?, end_date?, is_recurring, is_active                     │
  │ created_at, updated_at                                              │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: class_sessions/{id}   (individual session instances)    │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, schedule_id, course_id, lecturer_id                             │
  │ session_date, start_time, end_time, room_id?                        │
  │ topic?, notes?, status (SCHEDULED|ACTIVE|COMPLETED|CANCELLED)       │
  │ created_at, updated_at                                              │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: attendance_sessions/{id}  (marking sessions)            │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, class_session_id, session_code (8-char)                        │
  │ start_time, end_time, geolocation_enabled                           │
  │ geolocation_lat?, geolocation_lng?, geolocation_radius (100m)       │
  │ ip_restriction_enabled, allowed_ips[], is_active                    │
  │ created_at, updated_at                                              │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: attendance_records/{id}                                 │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, attendance_session_id, student_id, marked_at                    │
  │ status (PRESENT|ABSENT|LATE|EXCUSED), marked_by?                    │
  │ ip_address?, user_agent?, geolocation_lat?, geolocation_lng?        │
  │ is_late, minutes_late, notes?, is_suspicious, suspicion_reason?     │
  │ created_at, updated_at                                              │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: leave_requests/{id}                                     │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, user_id, institution_id, leave_type, start_date, end_date       │
  │ reason, attachment_url?, status (PENDING|APPROVED|REJECTED|...),    │
  │ approved_by?, approved_at?, rejection_reason?, created_at, updated_at│
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: security_logs/{id}                                      │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, user_id?, institution_id?, event_type, description              │
  │ ip_address?, user_agent?, geolocation_lat?, geolocation_lng?        │
  │ risk_score (0-100), is_resolved, resolved_by?, resolved_at?         │
  │ created_at                                                          │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: device_fingerprints/{id}                                │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, user_id, fingerprint_hash (SHA-256), user_agent, ip_address     │
  │ screen_resolution?, timezone?, language?, is_trusted                │
  │ last_seen, created_at                                               │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: trusted_devices/{id}    (remember-me)                   │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, user_id, device_fingerprint, browser_info                       │
  │ first_login_date, last_active_date, trust_status, session_token     │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: notifications/{id}                                      │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, user_id, institution_id, title, message, type (info|warn|alert) │
  │ is_read, action_url?, metadata (dict), created_at, read_at?         │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: audit_logs/{id}    (fine-grained action audit)          │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, user_id?, institution_id?, action, resource_type, resource_id?  │
  │ old_values (dict), new_values (dict), ip_address?, user_agent?      │
  │ timestamp                                                           │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: system_configurations/{id}   (per-institution KV store) │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, institution_id?, key, value, description?, is_active            │
  │ created_at, updated_at                                              │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLLECTION: demo_bookings/{id}    (lead capture)                    │
  ├─────────────────────────────────────────────────────────────────────┤
  │ id, email, full_name, phone, institution, institution_type?         │
  │ number_of_students?, preferred_date?, preferred_time?               │
  │ status (PENDING|CONFIRMED|...), booking_token, csrf_token           │
  │ session_token?, meeting_url?, meeting_provider?                     │
  │ onboarding_progress (dict), onboarding_completed, metadata (dict)   │
  │ created_at, updated_at, expires_at (30d), confirmed_at?, scheduled_at?│
  └─────────────────────────────────────────────────────────────────────┘

5.2. SQLALCHEMY TABLES (secondary datastore — demo/mail/feedback)

  demo_sql_repositories.py:         mail_models.py:          feedback_models.py:
  ├── DemoLead                      ├── MailSmtpProfile      ├── Feedback
  ├── OnboardingSession             ├── MailTemplate         ├── FeedbackReply
  ├── DemoBooking                   ├── MailQueue            ├── FeedbackReaction
  ├── DemoAnalyticsEvent            ├── MailAuditLog         ├── ModerationLog
  └── DemoTrial                     └── MailUnsubscribe      ├── FeedbackDiagnostics
                                                             └── EscalationHistory

  CRM only: Register an interest / demo booking with SQLAlchemy.
  Mail: SMTP profiles, templates, queue, audit, unsubscribe.
  Feedback: User feedback, replies, reactions, moderation, diagnostics.

"@ | Out-File -FilePath "C:\Users\noshi\OneDrive\fotsa\Achieved\AGENT.MG" -Encoding utf8 -Append
(no output)
$ @"

================================================================================
6. API ENDPOINT INVENTORY
================================================================================

All routes registered in app.py and blueprints. Rate limit config from
  security_legacy.py ENDPOINT_RATE_LIMITS dict shown where applicable.

AUTH BLUEPRINT (auth_bp @ /api/auth)                         [auth.py]
  POST  /api/auth/register     Register (CAPTCHA, rate: 5/3600s)    [L31]
  POST  /api/auth/signup       Alias for register (5/3600s)         [L112]
  POST  /api/auth/login        Login (CAPTCHA, rate: 10/300s,       [L120]
                                + decorator + per-email + global)
  POST  /api/auth/refresh      Refresh token (10/900s)              [L186]
  POST  /api/auth/logout       Logout (require_auth)                [L212]
  POST  /api/auth/change-password  Change pw (require_auth, 3/3600s)[L242]

PAGE ROUTES (pages_bp @ /)                                     [pages.py]
  GET   /signup-voucher         Voucher registration page           [L194]
  GET   /logout                 Logout page                         [L199]
  GET   /login                  Login page (CAPTCHA key injected)   [L204]
  GET   /signup                 Signup page                         [L218]
  GET   /email-diagnostics      Email diagnostics                   [L225]
  GET   /offline                Offline page                        [L230]
  GET   /sw.js                  Service worker                      [L235]

INLINE APP ROUTES (app.py — direct @app.route)                 [app.py]
  # System & Health
  GET   /health                     Health check                    [L772]
  GET   /api/ping                   Ping                            [L802]
  GET   /api/mqtt/status            MQTT status                     [L812]
  GET   /api/email/diagnostics      Email diagnostics               [L780]

  # Demo / Trial
  POST  /api/request-demo           Request demo (rate: 5/60s)      [L646]
  POST  /api/demo/request           Demo request                    [L921]
  POST  /api/demo/book              Book demo (rate: 5/60s)         [L952]
  POST  /api/demo/lookup            Lookup demo booking             [L1002]
  GET   /api/demo/booking/<token>   Get booking by token            [L1023]
  POST  /api/trial/check-eligibility Check trial eligibility        [L1046]

  # Security Admin
  GET   /api/security/events        Security events                 [L818]
  GET   /api/security/dashboard     Security dashboard              [L835]
  GET   /api/security/blocked-ips   Blocked IPs list                [L864]
  POST  /api/security/unblock-ip    Unblock IP                      [L876]
  GET   /api/security/audit-log     Audit log                       [L892]
  GET   /api/security/threats       Threat list                     [L909]

  # Schedules
  POST  /api/schedules              Create schedule                 [L1082]
  GET   /api/schedules/<id>/conflicts Check conflicts               [L1121]

  # Attendance
  POST  /api/attendance/create-session  Create session (rate: 20/60)[L1140]
  POST  /api/attendance/mark            Mark attendance (rate:10/60)[L1181]
  POST  /api/attendance/close-session/<id>  Close session           [L1313]
  GET   /api/attendance/sessions/<id>/statistics  Session stats     [L1426]

  # Biometric / Face
  GET   /api/biometric/face/status      Face status                 [L1340]
  POST  /api/biometric/face/enroll      Enroll face (rate: 5/300s)  [L1354]
  GET   /api/biometric/face/descriptors Get descriptors             [L1375]
  POST  /api/biometric/face/verify      Verify face                 [L1391]
  DELETE /api/biometric/face/revoke     Revoke face                 [L1412]

  # User Profile
  GET   /api/users/profile              Get profile                 [L1443]
  PUT   /api/users/profile              Update profile              [L1462]

  # Dashboard
  GET   /api/dashboard                  Dashboard                   [L1484]

  # Institutional Admin
  GET   /institutional-admin/dashboard  Dashboard page              [L1527]
  GET   /api/institutional/activity-feed                              [L1534]
  GET   /api/institutional/security-alerts                            [L1543]
  GET   /api/institutional/network-status                             [L1552]
  GET   /api/institutional/session-health                             [L1561]
  GET   /api/institutional/attendance-trends                          [L1572]
  GET   /api/institutional/students                                   [L1581]
  GET   /api/institutional/students/<id>                              [L1593]
  GET   /api/institutional/offline-log                                [L1604]
  GET   /api/institutional/infrastructure                             [L1613]
  GET   /api/institutional/compliance                                 [L1655]
  GET   /api/institutional/payments                                   [L1664]
  GET   /api/institutional/p2p-sync                                   [L1675]
  GET   /api/institutional/quick-actions                              [L1773]
  GET   /api/institutional/translations                               [L1781]
  GET   /api/institutional/events/stream    SSE stream                [L1790]
  POST  /api/institutional/activity-log                               [L1998]
  POST  /api/institutional/security-alert                             [L2014]
  POST  /api/institutional/network/node                               [L2030]
  POST  /api/institutional/session                                    [L2048]
  POST  /api/institutional/offline-sync                               [L2064]
  GET   /api/institutional/offline-queue/stats                        [L2080]
  POST  /api/institutional/offline-queue/process                      [L2091]
  GET   /api/institutional/offline-queue/pending                      [L2189]
  GET   /api/institutional/offline-queue/failed                       [L2200]
  POST  /api/institutional/offline-queue/retry                        [L2211]
  POST  /api/institutional/offline-queue/clear                        [L2224]
  GET   /api/institutional/offline-queue/estimate                     [L2237]
  GET   /api/institutional/offline-queue/nodes                        [L2248]
  POST  /api/institutional/offline-queue/enqueue                      [L2259]
  POST  /api/institutional/infrastructure/ups                         [L2279]
  POST  /api/institutional/infrastructure/isp                         [L2297]
  POST  /api/institutional/compliance/exam-mode                       [L2314]
  POST  /api/institutional/payments/transaction                       [L2330]
  POST  /api/institutional/p2p/peer                                   [L2346]
  POST  /api/institutional/seed-demo                                  [L2363]
  GET   /api/institutional/users                                      [L2380]
  POST  /api/institutional/users                                      [L2392]
  PUT   /api/institutional/users/<id>                                 [L2407]
  POST  /api/institutional/users/<id>/toggle-status                   [L2422]
  DELETE /api/institutional/users/<id>                                [L2432]
  GET   /api/institutional/courses                                    [L2451]
  POST  /api/institutional/courses                                    [L2463]
  PUT   /api/institutional/courses/<id>                               [L2477]
  DELETE /api/institutional/courses/<id>                               [L2491]
  GET   /api/institutional/departments                                [L2504]
  POST  /api/institutional/departments                                [L2516]
  PUT   /api/institutional/departments/<id>                           [L2530]
  DELETE /api/institutional/departments/<id>                          [L2544]
  GET   /api/institutional/enrollments                                [L2557]
  POST  /api/institutional/enrollments                                [L2569]
  DELETE /api/institutional/enrollments/<id>                          [L2583]
  GET   /api/institutional/lookup/lecturers                           [L2596]
  GET   /api/institutional/lookup/departments                         [L2605]
  GET   /api/institutional/lookup/courses                             [L2614]
  GET   /api/institutional/lookup/students                            [L2623]
  POST  /api/institutional/sms/send                                   [L2637]

  # Innovation Engine (Smart Campus)
  GET   /api/innovation/infrastructure/status                        [L1622]
  (and more via innovation_bp blueprint)

  # Super Admin
  GET   /api/super-admin/overview                                     [L2927]
  GET   /api/super-admin/institutions                                 [L2942]
  GET   /api/super-admin/users                                        [L2957]
  GET   /api/super-admin/activity-feed                                [L2979]
  GET   /api/super-admin/security-events                              [L2994]
  GET   /api/super-admin/attendance/overview                          [L3010]
  GET   /api/super-admin/suspicious-activity                          [L3025]
  GET   /api/super-admin/audit-logs                                   [L3040]
  POST  /api/super-admin/user/<id>/toggle-status                      [L3056]
  POST  /api/super-admin/institution/<id>/toggle-status               [L3073]
  GET   /api/super-admin/system-health                                [L3090]
  GET   /api/super-admin/security-analytics                           [L3104]
  GET   /api/super-admin/attendance-analytics                         [L3118]
  GET   /api/super-admin/demo-bookings                                [L3132]
  GET   /api/super-admin/notifications-summary                        [L3146]
  POST  /api/super-admin/security-events/<id>/resolve                 [L3160]
  GET   /api/super-admin/anti-proxy-intelligence                      [L3176]
  GET   /api/super-admin/network-infrastructure                       [L3190]
  GET   /api/super-admin/role-governance                              [L3204]
  GET   /api/super-admin/ai-risk-intelligence                         [L3218]

  # Student
  GET   /api/student/events/stream    SSE stream (lecturer too)       [L1843]
  GET   /api/student/dashboard                                        [L2777]
  GET   /api/student/attendance-history                               [L2794]
  GET   /api/student/schedule                                         [L2813]
  GET   /api/student/analytics                                        [L2829]
  GET   /api/student/security                                         [L2846]
  POST  /api/student/verify-scan       Mark attendance (rate: 20/60)  [L2863]

  # Reports
  GET   /api/reports/attendance                                       [L1684]
  GET   /api/reports/network                                          [L1729]
  GET   /api/reports/security                                         [L1751]
  GET   /api/reports/minesec-xml                                      [L2637]

  # Vouchers
  GET   /api/voucher/validate/<code>   Validate voucher               [L3358]
  POST  /api/voucher/generate-batch    Generate vouchers (rate:10/60) [L3431]
  GET   /api/voucher/list              List vouchers                  [L3477]
  POST  /api/voucher/revoke/<id>       Revoke voucher                 [L3514]
  GET   /api/voucher/export/csv        Export as CSV                  [L3533]
  POST  /api/voucher/email-delivery    Email vouchers                 [L3588]
  GET   /api/voucher/statistics/<inst>  Voucher statistics            [L3645]

  # Institutions
  GET   /api/institutions              List institutions              [L1907]
  GET   /api/institutions/<id>         Get institution                [L1916]
  GET   /api/institution/extended      Extended info                  [L1927]

  # Notifications
  GET   /api/notifications            List notifications              [L1950]
  POST  /api/notifications/<id>/read   Mark read                     [L1962]

  # Leave Requests
  GET   /api/leave-requests            List leave requests            [L1969]
  POST  /api/leave-requests            Submit leave request           [L1982]

  # System
  GET   /system/voucher/status         Voucher system status          [~L3800]
  GET   /system/voucher/debug          Voucher debug (super_admin)    [L3835]
  GET   /api/docs                      API documentation              [L3855]
  GET   /api/mail/unsubscribe          Mail unsubscribe               [L3905]

  # Feedback (feedback_api blueprint @ /api/feedback)
  # Mail (mail_bp @ /admin/mail, mail_api @ /api/mail)
  # Innovation (innovation_bp @ /api/innovation, conditional)

"@ | Out-File -FilePath "C:\Users\noshi\OneDrive\fotsa\Achieved\AGENT.MG" -Encoding utf8 -Append
(no output)
$ @"

================================================================================
7. AUTHENTICATION & AUTHORIZATION
================================================================================

7.1. AUTHENTICATION FLOW

  ┌───────────────────────────────────────────────────────────────────────────┐
  │ CUSTOM JWT AUTH — NOT Firebase Auth SDK login                            │
  │                                                                          │
  │ Login:                                                                   │
  │   1. Client sends email + password to POST /api/auth/login               │
  │   2. Server queries Firestore 'users' collection by email                │
  │   3. Server verifies password_hash with bcrypt.checkpw()                 │
  │   4. Server generates JWT access token (HS256) + refresh token           │
  │   5. Returns {access_token, refresh_token, user}                         │
  │                                                                          │
  │ Firebase Auth is used ONLY for:                                          │
  │   - Creating user accounts (firebase_admin.auth.create_user())           │
  │   - Setting custom claims (role + institution_id) for Firebase SDK users │
  │   - Password reset emails (via Firebase Auth API)                        │
  │   - NOT for login verification                                           │
  └───────────────────────────────────────────────────────────────────────────┘

7.2. JWT TOKEN SPECIFICATION

  Access Token (short-lived):
    Header:  {alg: HS256, typ: JWT}
    Payload: {user_id, jti, email, role, institution_id,
              exp (default 15min), iat, type: 'access'}
    Secret:  JWT_SECRET_KEY from config

  Refresh Token (long-lived):
    Payload: {user_id, exp (default 7d), iat, type: 'refresh'}

  Verification (rbac.py:require_auth @ L163):
    → Extract Bearer token from Authorization header
    → auth_service.verify_token() decodes JWT, checks:
      - Signature (JWT_SECRET_KEY)
      - Expiration
      - Blacklist check (redis_token_blacklist by jti)
      - User exist + is_active in Firestore
    → Sets request.current_user = payload

  Blacklisting: On logout, jti added to Redis blacklist with TTL = exp

7.3. ROLE-BASED ACCESS CONTROL

  5 roles defined in entities.py UserRole enum:
    SUPER_ADMIN          = \"super_admin\"          # Cross-institution admin
    INSTITUTIONAL_ADMIN  = \"institutional_admin\"  # Single-institution admin
    LECTURER             = \"lecturer\"             # Course instructor
    STUDENT              = \"student\"              # Student attendee
    EMPLOYEE             = \"employee\"             # Staff (limited access)

  Role↔Permission matrix (rbac.py RolePermissions @ L63):
    PERMISSION                         SA  IA  LEC  EMP  STU
    manage_system                       ✓   –   –    –    –
    manage_institution                  ✓   –   –    –    –
    view_institution_analytics          ✓   –   –    –    –
    manage_departments                  ✓   ✓   –    –    –
    view_department_analytics           ✓   ✓   –    –    –
    manage_users                        ✓   ✓   –    –    –
    create_users                        ✓   ✓   –    –    –
    view_users                          ✓   ✓   –    –    –
    manage_courses                      ✓   ✓   –    –    –
    view_courses                        ✓   ✓   ✓    ✓    ✓
    enroll_students                     ✓   ✓   –    –    –
    manage_schedules                    ✓   ✓   –    –    –
    view_schedules                      ✓   ✓   ✓    ✓    ✓
    manage_attendance                   ✓   ✓   ✓    –    –
    mark_attendance                     ✓   ✓   ✓    –    ✓
    view_attendance                     ✓   ✓   ✓    ✓    ✓
    view_attendance_reports             ✓   ✓   ✓    –    –
    manage_leave_requests               ✓   ✓   –    –    –
    submit_leave_request                ✓   ✓   ✓    ✓    ✓
    approve_leave_request               ✓   ✓   –    –    –
    view_analytics                      ✓   ✓   ✓    –    ✓
    view_predictive_analytics           ✓   –   –    –    –
    view_audit_logs                     ✓   ✓   –    –    –
    manage_notifications                ✓   ✓   –    –    –

  Decorators:
    @require_auth                       — Validates JWT, sets request.current_user
    @require_role(*roles)               — Checks request.current_user.role
    @require_admin_webauthn             — Requires admin + WebAuthn passkey
    @log_access                         — Audit-log endpoint access

================================================================================
8. SECURITY
================================================================================

8.1. RATE LIMITING (4 independent layers — see §9 for deep dive)

  Layer 1: Global before_request (security_legacy.validate_request_security)
           key = global:ip:{IP}  — SHARED across ALL endpoints
           Per-endpoint limits via ENDPOINT_RATE_LIMITS dict
  Layer 2: IP Network Security (comprehensive_security.comprehensive_security_before)
           key = ip:{IP} (internal dict)
           limit = 100/60s
  Layer 3: @rate_limit_endpoint decorator
           key = ip:{IP} or user:{UID}
           Per-route config (e.g., login: 10/300s)
  Layer 4: Registration Brute Force (security_reinforcements)
           key = email:{EMAIL} or ip:{IP}
           limit = 3/hr per email, 10/hr per IP (registration only)

8.2. CAPTCHA (Cloudflare Turnstile / reCAPTCHA)
  @require_captcha decorator: verifies token via Turnstile API
  Skips validation if TURNSTILE_SECRET_KEY not configured (dev mode)
  Applied to: register, signup, login endpoints

8.3. CSRF PROTECTION
  Custom CSRF manager in security_legacy.py
  Token generated per session, validated on POST/PUT/PATCH/DELETE
  CSRF_EXEMPT_PATHS: auth endpoints (/login, /register, etc.), demo, bootstrap

8.4. INPUT SANITIZATION (InputSanitizer — security_legacy.py)
  SQL injection patterns: 5 regex patterns (OR/AND/UNION/SELECT/etc.)
  XSS patterns: 10+ regex patterns (<script>, javascript:, on*=, eval(), etc.)
  Email normalization: strip, lowercase, reject malformed
  String sanitization: strip, limit to max_length, remove control chars

8.5. PASSWORD POLICY (PasswordPolicy — security_legacy.py)
  Minimum 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char
  History check (last 5 passwords) on change
  Expiry check (90 days) on login
  Progressive lockout after 5 failed attempts (15-minute lock)

8.6. JWT SESSION MANAGEMENT
  Access token: 15-min expiry, refresh via /api/auth/refresh
  Token blacklisting on logout (Redis, TTL-based)
  require_auth decorator validates: signature, expiry, blacklist, user active

8.7. AUDIT LOGGING
  SecurityAuditLogger.log_event() — structured security events
  log_security_event() — from comprehensive_security.py
  @log_access decorator — endpoint access audit
  Event types: rate_limited, registration_*, login_*, security_alert, etc.

8.8. ADDITIONAL SECURITY MEASURES
  HTTPS enforcement (security_reinforcements.HTTPSEnforcer)
  Security headers: HSTS, CSP, XFO, XSS-Protection, Content-Type-Options
  Multi-tenant isolation: query filters auto-injected with institution_id
  Account lockout: per-user failed attempt counter in Firestore
  Device fingerprinting: SHA-256 hash of UA+IP+screen+timezone+lang
  Behavioral monitoring: velocity checks, endpoint crawl detection
  Content validation: JSON structure, request size, field size limits

"@ | Out-File -FilePath "C:\Users\noshi\OneDrive\fotsa\Achieved\AGENT.MG" -Encoding utf8 -Append
(no output)
