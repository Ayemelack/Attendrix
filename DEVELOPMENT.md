# Attendrix Development Setup Guide

## ✅ Server Status: RUNNING

The Attendrix development server is currently running on:
- **Main Server**: http://localhost:5000
- **Health Check**: http://localhost:5000/health
- **API Test**: http://localhost:5000/api/test
- **System Info**: http://localhost:5000/api/info

## 🔧 Firebase Development Configuration

### ✅ Completed Setup
1. **Firebase Credentials**: Created `firebase-dev.json` with development credentials
2. **Environment Configuration**: Created `.env.dev` for development settings
3. **Settings Updated**: Modified `config/settings.py` to use development files
4. **Security**: `.gitignore` properly blocks production credentials

### 🔑 Firebase Setup Instructions

To connect to a real Firebase project:

1. **Create Firebase Project**
   - Go to [Firebase Console](https://console.firebase.google.com/)
   - Create new project: `attendrix-dev`

2. **Generate Service Account Key**
   - Go to Project Settings → Service Accounts
   - Click "Generate new private key"
   - Select JSON format
   - Download and replace `firebase-dev.json`

3. **Enable Firebase Services**
   - Authentication: Enable Email/Password
   - Firestore Database: Create database in test mode
   - Storage: Enable if needed

## 🚀 Quick Start Commands

### Windows
```batch
# Run the startup script
start-dev.bat

# Or start manually
py app-simple.py
```

### Linux/Mac
```bash
# Make script executable
chmod +x start-dev.sh

# Run the startup script
./start-dev.sh

# Or start manually
python3 app-simple.py
```

## 📊 Available Endpoints

### Core Endpoints
- `GET /` - Landing page
- `GET /health` - Health check
- `GET /api/test` - API test endpoint
- `GET /api/info` - System information

### Authentication (When Firebase is configured)
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/refresh` - Refresh token
- `POST /api/auth/logout` - User logout

### System Features (Current Status)
- ✅ **Flask Application**: Running
- ✅ **CORS Enabled**: Cross-origin requests allowed
- ✅ **Development Mode**: Debug enabled
- ⚠️ **Firebase Integration**: Configured but needs real credentials
- ⚠️ **Database**: Using SQLite for development
- ⚠️ **Redis**: Not connected (caching disabled)

## 🔍 Testing the System

### 1. Health Check
Open http://localhost:5000/health in your browser
Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-04-06T15:33:42.123Z",
  "version": "1.0.0-dev",
  "environment": "development"
}
```

### 2. API Test
Open http://localhost:5000/api/test in your browser
Expected response:
```json
{
  "message": "Attendrix API is working",
  "endpoints": [...],
  "firebase_status": "Configured but not initialized",
  "database_status": "Using SQLite for development"
}
```

### 3. System Information
Open http://localhost:5000/api/info in your browser
Shows detailed system status and next steps.

## 🔒 Security Configuration

### Development Mode
- **Debug**: Enabled for development
- **Session Security**: Relaxed for development
- **CORS**: Allows localhost origins
- **Logging**: Debug level logging

### Production Considerations
- Firebase credentials are properly isolated
- Production credentials (`firebase-prod.json`) are blocked by `.gitignore`
- Environment-specific configuration files
- Security headers will be enabled in production

## 📝 Development Notes

### Firebase Integration Status
- **Configuration**: ✅ Complete
- **Authentication**: Ready (needs real credentials)
- **Firestore**: Ready (needs real project)
- **Real-time Features**: Ready (needs real project)

### Database Status
- **Development**: SQLite (for local testing)
- **Production**: PostgreSQL (configured but not running)
- **Caching**: Redis (configured but not running)

### Next Steps for Full Functionality
1. Set up real Firebase project
2. Replace `firebase-dev.json` with real credentials
3. Start Redis server for caching
4. Configure PostgreSQL for production testing
5. Test authentication endpoints
6. Test attendance functionality

## 🛠️ Troubleshooting

### Server Won't Start
```bash
# Check Python version
py --version

# Install missing dependencies
py -m pip install flask flask-cors firebase-admin pyjwt bcrypt python-decouple

# Check port availability
netstat -an | findstr :5000
```

### Firebase Connection Issues
- Verify Firebase project exists
- Check service account key permissions
- Ensure Firestore database is created
- Verify network connectivity

### Common Issues
- **Port 5000 in use**: Change port in environment variable `PORT=5001`
- **Module not found**: Run `py -m pip install -r requirements-dev.txt`
- **Firebase errors**: Check credentials file format and permissions

## 📞 Support

For development support:
- **Documentation**: Check inline code comments
- **Issues**: Check server logs for error messages
- **Firebase**: [Firebase Console](https://console.firebase.google.com/)
- **Email**: alexiscrazy605@gmail.com

---

## ✅ Current Status Summary

**Attendrix development server is successfully running** with:
- ✅ Core Flask application
- ✅ Development environment configuration
- ✅ Firebase integration framework
- ✅ Security best practices
- ✅ Error handling and logging
- ✅ API endpoints for testing

**Ready for Firebase project setup and full feature testing!**
