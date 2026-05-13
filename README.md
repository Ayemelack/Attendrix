# Attendrix - Institutional Paperless Attendance System
# Secure. Smart. Structured Attendance.

## Project Overview
Attendrix is an enterprise-grade, multi-tenant institutional paperless attendance system built with Python and Firebase. It eliminates proxy attendance, manual errors, and provides comprehensive analytics for educational institutions.

## Architecture
- **Clean Architecture**: Layered design with Presentation/Application/Domain/Infrastructure layers
- **Multi-Tenant**: Complete data isolation for multiple institutions
- **Python + Firebase**: Python handles frontend/logic, Firebase manages backend services
- **Environment-Isolated**: Development/Staging/Production environments

## Key Features
- Secure authentication with role-based access control
- Advanced scheduling with conflict detection
- Session-based attendance with anti-proxy mechanisms
- Real-time analytics and predictive intelligence
- Smart alerts and communication system
- Leave management workflow
- Survey and feedback engine
- Gamification and recognition system
- API integration capabilities

## Technology Stack
- **Backend**: Python 3.11+, Flask, SQLAlchemy
- **Database**: Firebase Firestore + PostgreSQL (for complex queries)
- **Authentication**: Firebase Auth + JWT
- **Frontend**: HTML5, CSS3, JavaScript (Bootstrap 5)
- **Caching**: Redis
- **Background Tasks**: Celery
- **Deployment**: Docker, Gunicorn

## Installation

### Prerequisites
- Python 3.11+
- Firebase project with Authentication and Firestore enabled
- Redis server
- PostgreSQL (optional, for complex analytics)

### Setup
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure Firebase credentials
4. Set up environment variables
5. Run migrations: `python manage.py migrate`
6. Start the application: `python app.py`

## Environment Configuration
Copy `.env.example` to `.env` and configure:
- `ENVIRONMENT`: development/staging/production
- `FIREBASE_CREDENTIALS_PATH`: Path to Firebase service account file
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SECRET_KEY`: Flask secret key

## Project Structure
```
attendrix/
├── src/
│   ├── presentation/          # UI layer - templates, static files
│   ├── application/           # Business logic layer
│   ├── domain/               # Core models and entities
│   └── infrastructure/       # External services, database
├── config/                   # Configuration files
├── tests/                    # Test suite
├── docs/                     # Documentation
└── scripts/                  # Utility scripts
```

## Roles and Permissions
- **Super Admin**: Multi-institution management
- **Institutional Admin**: Single institution management
- **Lecturer**: Course and attendance management
- **Student**: Attendance marking and viewing
- **Employee**: Work attendance and leave management

## API Documentation
API documentation is available at `/api/docs` when running the application.

## Security Features
- Multi-factor authentication
- Device fingerprinting
- Geolocation verification
- IP-based restrictions
- Comprehensive audit logging
- Encrypted data storage

## Contact
- **Email**: alexiscrazy605@gmail.com
- **Phone**: +237-653-031002

## License
© 2024 Attendrix. All rights reserved.
