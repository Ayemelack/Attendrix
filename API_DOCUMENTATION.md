# Attendrix - API Documentation

## Overview

Attendrix provides a comprehensive RESTful API for institutional paperless attendance management. The API follows REST principles and uses JSON for data exchange.

## Base URL

```
Production: https://your-domain.com/api
Development: http://localhost:8000/api
```

## Authentication

Attendrix uses JWT (JSON Web Tokens) for authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### Authentication Flow

1. **Register User**
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password",
  "first_name": "John",
  "last_name": "Doe",
  "role": "student",
  "institution_id": "institution-uuid"
}
```

2. **Login**
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password"
}
```

Response:
```json
{
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "role": "student",
    "institution_id": "institution-uuid"
  },
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

3. **Refresh Token**
```http
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

## User Roles

- **super_admin**: Multi-institution management
- **institutional_admin**: Single institution management
- **lecturer**: Course and attendance management
- **student**: Attendance marking and viewing
- **employee**: Work attendance and leave management

## API Endpoints

### Authentication

#### Register User
```http
POST /api/auth/register
```

**Required Fields:**
- `email` (string): User email
- `password` (string): User password (min 8 characters)
- `first_name` (string): First name
- `last_name` (string): Last name
- `role` (string): User role
- `institution_id` (string): Institution UUID

**Optional Fields:**
- `phone` (string): Phone number
- `profile_image_url` (string): Profile image URL

#### Login
```http
POST /api/auth/login
```

**Required Fields:**
- `email` (string): User email
- `password` (string): User password

#### Refresh Token
```http
POST /api/auth/refresh
```

**Required Fields:**
- `refresh_token` (string): Refresh token

#### Logout
```http
POST /api/auth/logout
Authorization: Bearer <token>
```

### User Profile

#### Get User Profile
```http
GET /api/users/profile
Authorization: Bearer <token>
```

Response:
```json
{
  "id": "user-uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "student",
  "institution_id": "institution-uuid",
  "phone": "+1234567890",
  "profile_image_url": "https://example.com/image.jpg",
  "is_active": true,
  "email_verified": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Scheduling

#### Create Schedule
```http
POST /api/schedules
Authorization: Bearer <token>
Content-Type: application/json

{
  "institution_id": "institution-uuid",
  "course_id": "course-uuid",
  "lecturer_id": "lecturer-uuid",
  "room_id": "room-uuid",
  "day_of_week": 1,
  "start_time": "09:00",
  "end_time": "10:00",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-12-31T00:00:00Z",
  "is_recurring": true
}
```

**Required Fields:**
- `institution_id` (string): Institution UUID
- `course_id` (string): Course UUID
- `lecturer_id` (string): Lecturer UUID
- `day_of_week` (integer): Day of week (1-7, Monday-Sunday)
- `start_time` (string): Start time (HH:MM format)
- `end_time` (string): End time (HH:MM format)

**Optional Fields:**
- `room_id` (string): Room UUID
- `start_date` (string): Schedule start date
- `end_date` (string): Schedule end date
- `is_recurring` (boolean): Whether schedule is recurring

#### Check Schedule Conflicts
```http
GET /api/schedules/{schedule_id}/conflicts
Authorization: Bearer <token>
```

Response:
```json
{
  "schedule_id": "schedule-uuid",
  "conflicts": [
    {
      "type": "lecturer_double_booking",
      "description": "Lecturer is already scheduled during this time slot",
      "severity": "high",
      "conflicting_schedules": [...]
    }
  ]
}
```

### Attendance

#### Create Attendance Session
```http
POST /api/attendance/sessions
Authorization: Bearer <token>
Content-Type: application/json

{
  "class_session_id": "class-session-uuid",
  "settings": {
    "duration_minutes": 15,
    "geolocation_enabled": true,
    "geolocation_lat": 3.8480,
    "geolocation_lng": 11.5021,
    "geolocation_radius": 100,
    "ip_restriction_enabled": false,
    "allowed_ips": ["192.168.1.100", "10.0.0.50"]
  }
}
```

**Required Fields:**
- `class_session_id` (string): Class session UUID

**Optional Settings:**
- `duration_minutes` (integer): Session duration in minutes (default: 15)
- `geolocation_enabled` (boolean): Enable geolocation verification
- `geolocation_lat` (float): Allowed latitude
- `geolocation_lng` (float): Allowed longitude
- `geolocation_radius` (integer): Radius in meters (default: 100)
- `ip_restriction_enabled` (boolean): Enable IP restriction
- `allowed_ips` (array): List of allowed IP addresses

#### Mark Attendance
```http
POST /api/attendance/mark
Authorization: Bearer <token>
Content-Type: application/json

{
  "session_code": "AB12CD34",
  "geolocation_lat": 3.8480,
  "geolocation_lng": 11.5021
}
```

**Required Fields:**
- `session_code` (string): Attendance session code

**Optional Fields:**
- `geolocation_lat` (float): Current latitude
- `geolocation_lng` (float): Current longitude

#### Get Session Statistics
```http
GET /api/attendance/sessions/{session_id}/statistics
Authorization: Bearer <token>
```

Response:
```json
{
  "session_id": "session-uuid",
  "total_records": 25,
  "present": 20,
  "late": 3,
  "absent": 2,
  "excused": 0,
  "suspicious": 1,
  "average_marking_time": "2024-01-01T09:05:00Z",
  "unique_ips": 20,
  "unique_devices": 18,
  "geolocation_coverage": 85.0
}
```

### Dashboard

#### Get Dashboard Data
```http
GET /api/dashboard
Authorization: Bearer <token>
```

Response varies by user role:

**Student Dashboard:**
```json
{
  "user_role": "student",
  "user_id": "user-uuid",
  "institution_id": "institution-uuid",
  "attendance_summary": {
    "total_sessions": 50,
    "attended_sessions": 45,
    "attendance_percentage": 90.0,
    "late_count": 3
  },
  "courses": [
    {
      "id": "course-uuid",
      "name": "Computer Science 101",
      "code": "CS101",
      "attendance_percentage": 92.0
    }
  ],
  "announcements": [
    {
      "id": "announcement-uuid",
      "title": "Class Schedule Update",
      "message": "Schedule changes for next week",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

**Lecturer Dashboard:**
```json
{
  "user_role": "lecturer",
  "user_id": "user-uuid",
  "institution_id": "institution-uuid",
  "courses": [
    {
      "id": "course-uuid",
      "name": "Computer Science 101",
      "code": "CS101",
      "enrolled_students": 30,
      "average_attendance": 85.0
    }
  ],
  "attendance_sessions": [
    {
      "id": "session-uuid",
      "course_name": "Computer Science 101",
      "session_code": "AB12CD34",
      "is_active": true,
      "created_at": "2024-01-01T09:00:00Z"
    }
  ],
  "analytics": {
    "total_students": 150,
    "average_attendance": 87.5,
    "suspicious_activities": 2
  }
}
```

### System

#### Health Check
```http
GET /health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "environment": "production"
}
```

#### API Documentation
```http
GET /api/docs
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required or invalid
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Error Response Format

```json
{
  "error": "Error message description",
  "details": {
    "field": "Specific error details"
  }
}
```

## Rate Limiting

- **General API**: 100 requests per minute
- **Authentication endpoints**: 10 requests per minute
- **Login endpoint**: 5 requests per minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Data Validation

### Email Format
Must be a valid email address.

### Password Requirements
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number

### UUID Format
All UUID fields should be in standard UUID v4 format.

## Webhooks

Attendrix supports webhooks for real-time notifications:

### Configure Webhook
Contact your administrator to configure webhook endpoints.

### Webhook Events

- `attendance.marked`: Student marked attendance
- `session.created`: New attendance session created
- `user.registered`: New user registered
- `security.alert`: Suspicious activity detected

### Webhook Payload
```json
{
  "event": "attendance.marked",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "session_id": "session-uuid",
    "student_id": "student-uuid",
    "status": "present"
  }
}
```

## SDKs and Libraries

### Python SDK
```python
from attendrix_sdk import AttendrixClient

client = AttendrixClient(
    base_url='https://your-domain.com/api',
    api_key='your-api-key'
)

# Mark attendance
result = client.attendance.mark(
    session_code='AB12CD34',
    geolocation_lat=3.8480,
    geolocation_lng=11.5021
)
```

### JavaScript SDK
```javascript
import { AttendrixClient } from 'attendrix-sdk';

const client = new AttendrixClient({
  baseURL: 'https://your-domain.com/api',
  apiKey: 'your-api-key'
});

// Mark attendance
const result = await client.attendance.mark({
  sessionCode: 'AB12CD34',
  geolocationLat: 3.8480,
  geolocationLng: 11.5021
});
```

## Support

For API support:
- **Documentation**: https://docs.attendrix.com
- **Email**: api-support@attendrix.com
- **Status Page**: https://status.attendrix.com

## Changelog

### v1.0.0 (2024-01-01)
- Initial API release
- Authentication endpoints
- Attendance management
- Scheduling system
- User management
- Dashboard endpoints
