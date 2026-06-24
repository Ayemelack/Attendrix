# Attendrix Docker Deployment Guide

This guide provides comprehensive instructions for deploying Attendrix using Docker and Docker Compose.

## 🐳 **Docker Architecture Overview**

Attendrix uses a multi-service Docker architecture with the following components:

### **Core Services**
- **Web Application**: Django application with Gunicorn WSGI server
- **Database**: PostgreSQL 15 with optimized configuration
- **Cache/Queue**: Redis 7 for caching and Celery message broker
- **Celery Worker**: Background task processing
- **Celery Beat**: Scheduled task management
- **Flower**: Celery monitoring dashboard
- **Nginx**: Reverse proxy and static file serving

### **Development Services**
- **Database Admin**: pgAdmin for database management
- **Redis Commander**: Redis management interface
- **Mailhog**: Email testing in development

## 🚀 **Quick Start**

### **1. Prerequisites**
- Docker 20.10+
- Docker Compose 2.0+
- Git
- At least 4GB RAM
- 10GB free disk space

### **2. Clone Repository**
```bash
git clone https://github.com/your-org/attendrix.git
cd attendrix
```

### **3. Environment Configuration**
```bash
# Copy environment template
cp .env.docker .env

# Edit environment variables
nano .env
```

### **4. Start Development Environment**
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### **5. Access Applications**
- **Web App**: http://localhost:8000
- **Admin**: http://localhost:8000/admin/
- **Flower**: http://localhost:5555
- **pgAdmin**: http://localhost:5050
- **Redis Commander**: http://localhost:8081
- **Mailhog**: http://localhost:8025

## 🏭 **Production Deployment**

### **1. Production Environment Setup**
```bash
# Copy production environment
cp .env.docker .env.production

# Edit production settings
nano .env.production
```

### **2. SSL Certificate Setup**
```bash
# Create SSL directory
mkdir -p docker/ssl

# Add your SSL certificates
cp your-cert.pem docker/ssl/cert.pem
cp your-key.pem docker/ssl/key.pem
```

### **3. Start Production Services**
```bash
# Use production compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Or use the production-specific file
docker-compose -f docker-compose.prod.yml up -d
```

### **4. Production URLs**
- **HTTPS**: https://your-domain.com
- **HTTP**: http://your-domain.com (redirects to HTTPS)
- **Flower**: https://your-domain.com:5555
- **Health Check**: https://your-domain.com/health/

## 📋 **Configuration Files**

### **Docker Compose Files**
- `docker-compose.yml` - Base configuration
- `docker-compose.override.yml` - Development overrides
- `docker-compose.prod.yml` - Production configuration

### **Dockerfile**
Multi-stage build with:
- **Builder Stage**: Development with all dependencies
- **Production Stage**: Optimized production image

### **Configuration Files**
- `docker/nginx/` - Nginx configuration
- `docker/postgres/` - PostgreSQL configuration
- `docker/redis/` - Redis configuration

## 🔧 **Environment Variables**

### **Required Variables**
```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com

# Database
DB_PASSWORD=secure-db-password

# Redis
REDIS_PASSWORD=secure-redis-password

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### **Optional Variables**
```bash
# Monitoring
SENTRY_DSN=your-sentry-dsn

# Security
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000

# Performance
WEB_WORKERS=4
CELERY_WORKER_CONCURRENCY=4
```

## 🛠️ **Management Commands**

### **Service Management**
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f [service-name]

# Execute commands in container
docker-compose exec web python manage.py shell
docker-compose exec db psql -U attendrix -d attendrix
```

### **Database Management**
```bash
# Create migrations
docker-compose exec web python manage.py makemigrations

# Apply migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Database backup
docker-compose exec web python manage.py dbbackup

# Database restore
docker-compose exec web python manage.py dbrestore backup-file.gz
```

### **Celery Management**
```bash
# View active tasks
docker-compose exec celery celery -A attendrix inspect active

# View scheduled tasks
docker-compose exec celery celery -A attendrix inspect scheduled

# Purge queue
docker-compose exec celery celery -A attendrix purge
```

## 📊 **Monitoring & Logging**

### **Health Checks**
All services include health checks:
```bash
# Check service health
docker-compose ps

# View health check logs
docker-compose logs -f | grep health
```

### **Log Management**
```bash
# View application logs
docker-compose logs -f web

# View database logs
docker-compose logs -f db

# View nginx logs
docker-compose logs -f nginx

# Rotate logs (included in configuration)
```

### **Performance Monitoring**
- **Flower**: http://localhost:5555 (Celery monitoring)
- **pgAdmin**: http://localhost:5050 (Database monitoring)
- **Redis Commander**: http://localhost:8081 (Redis monitoring)

## 🔒 **Security Configuration**

### **Production Security**
```bash
# Enable SSL
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Security headers
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_CONTENT_TYPE_NOSNIFF=True
```

### **Database Security**
```bash
# Strong passwords
DB_PASSWORD=very-strong-password

# Network isolation
# Services communicate within Docker network only
```

### **Redis Security**
```bash
# Require authentication
requirepass very-strong-redis-password

# Disable dangerous commands
rename-command CONFIG ""
rename-command DEBUG ""
```

## 🚨 **Troubleshooting**

### **Common Issues**

#### **Database Connection Failed**
```bash
# Check database status
docker-compose exec db pg_isready -U attendrix

# Check network connectivity
docker-compose exec web ping db
```

#### **Redis Connection Failed**
```bash
# Check Redis status
docker-compose exec redis redis-cli ping

# Test with authentication
docker-compose exec redis redis-cli -a your-password ping
```

#### **Static Files Not Loading**
```bash
# Collect static files
docker-compose exec web python manage.py collectstatic --noinput

# Check Nginx configuration
docker-compose exec nginx nginx -t
```

#### **Celery Tasks Not Running**
```bash
# Check Celery worker status
docker-compose exec celery celery -A attendrix inspect ping

# View worker logs
docker-compose logs -f celery
```

### **Performance Issues**

#### **High Memory Usage**
```bash
# Monitor resource usage
docker stats

# Adjust worker counts
# Edit docker-compose.yml and reduce concurrency
```

#### **Slow Database Queries**
```bash
# Connect to database
docker-compose exec db psql -U attendrix -d attendrix

# Check slow queries
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
```

## 🔄 **Updates & Maintenance**

### **Application Updates**
```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d

# Apply migrations
docker-compose exec web python manage.py migrate
```

### **Database Maintenance**
```bash
# Vacuum database
docker-compose exec db psql -U attendrix -d attendrix -c "VACUUM ANALYZE;"

# Update statistics
docker-compose exec db psql -U attendrix -d attendrix -c "ANALYZE;"
```

### **Backup Strategy**
```bash
# Automated backups (included in production)
# Manual backup
docker-compose exec web python manage.py dbbackup --compress

# Restore backup
docker-compose exec web python manage.py dbrestore backup-file.gz
```

## 📈 **Scaling**

### **Horizontal Scaling**
```bash
# Scale web services
docker-compose up -d --scale web=3

# Scale Celery workers
docker-compose up -d --scale celery=4
```

### **Load Balancing**
Nginx automatically load balances between multiple web containers.

### **Database Scaling**
For high-load scenarios:
- Use PostgreSQL replication
- Implement read replicas
- Consider connection pooling

## 🌐 **Network Configuration**

### **Docker Networks**
- **attendrix_network**: Default network (172.20.0.0/16)
- **attendrix_prod_network**: Production network (172.21.0.0/16)

### **Port Mapping**
Development:
- Web: 8000
- Database: 5432
- Redis: 6379
- Flower: 5555

Production:
- HTTP: 80
- HTTPS: 443
- Flower: 5555

## 📝 **Best Practices**

### **Development**
- Use `.env.docker` for development configuration
- Enable debug mode for detailed error messages
- Use Mailhog for email testing
- Regularly update dependencies

### **Production**
- Use strong, unique passwords
- Enable SSL/TLS encryption
- Regularly update Docker images
- Monitor resource usage
- Implement backup strategy
- Use environment-specific configurations

### **Security**
- Regularly update base images
- Scan for vulnerabilities
- Use non-root users in containers
- Implement rate limiting
- Monitor access logs

## 🆘 **Support**

### **Logs Location**
- Application: `/app/logs/`
- Nginx: `/var/log/nginx/`
- Database: PostgreSQL logs
- System: Docker daemon logs

### **Useful Commands**
```bash
# Container resource usage
docker stats

# Disk usage
docker system df

# Clean up unused resources
docker system prune -a
```

### **Getting Help**
- Check logs: `docker-compose logs -f`
- Verify configuration: `docker-compose config`
- Test connectivity: `docker-compose exec web ping db`

---

**Note**: This Docker setup is designed for both development and production use. Always test in development before deploying to production.
