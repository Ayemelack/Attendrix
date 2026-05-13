# Attendrix Deployment Guide

## 🚀 Production Deployment

Attendrix is designed for enterprise-grade deployment with Docker containerization and multi-service architecture.

### Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- 4GB+ RAM
- 20GB+ storage
- SSL certificates (for production)
- Firebase project with service account credentials

### Quick Start

1. **Clone and Setup**
```bash
git clone <repository-url>
cd attendrix
cp .env.example .env
```

2. **Configure Environment**
```bash
# Edit .env with your configuration
nano .env
```

3. **Setup SSL Certificates**
```bash
mkdir -p nginx/ssl
# Copy your SSL certificates
cp your-cert.pem nginx/ssl/cert.pem
cp your-key.pem nginx/ssl/key.pem
```

4. **Setup Firebase Credentials**
```bash
# Copy Firebase service account file
cp your-firebase-credentials.json config/firebase-credentials.json
```

5. **Deploy**
```bash
docker-compose up -d
```

### Environment Variables

#### Required Variables
- `SECRET_KEY`: Flask secret key (generate with: `openssl rand -hex 32`)
- `JWT_SECRET_KEY`: JWT signing key
- `POSTGRES_PASSWORD`: PostgreSQL database password
- `REDIS_PASSWORD`: Redis password
- `FIREBASE_PROJECT_ID`: Firebase project ID

#### Optional Variables
- `MAIL_USERNAME`: Email for notifications
- `MAIL_PASSWORD`: Email password
- `GOOGLE_GEOCODING_API_KEY`: Google Maps API key
- `FLOWER_USER`: Flower monitoring username
- `FLOWER_PASSWORD`: Flower monitoring password

### Service Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Nginx      │    │   Attendrix     │    │   PostgreSQL    │
│  (Reverse      │────│   (Flask App)   │────│   (Database)    │
│   Proxy)       │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │                 │
                ┌─────────────┐  ┌─────────────┐
                │    Redis    │  │   Celery    │
                │   (Cache)   │  │  (Worker)   │
                └─────────────┘  └─────────────┘
```

### Access Points

- **Web Application**: https://localhost
- **API Documentation**: https://localhost/api/docs
- **Health Check**: https://localhost/health
- **Flower Monitoring**: https://localhost:5555

### Database Management

#### Access PostgreSQL
```bash
docker exec -it attendrix-postgres psql -U attendrix_user -d attendrix_prod
```

#### Backup Database
```bash
docker exec attendrix-postgres pg_dump -U attendrix_user attendrix_prod > backup.sql
```

#### Restore Database
```bash
docker exec -i attendrix-postgres psql -U attendrix_user attendrix_prod < backup.sql
```

### Monitoring and Logs

#### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f postgres
docker-compose logs -f celery-worker
```

#### Monitor with Flower
Access Flower at https://localhost:5555 with credentials from environment variables.

### Scaling

#### Horizontal Scaling
```bash
# Scale web application
docker-compose up -d --scale web=3

# Scale Celery workers
docker-compose up -d --scale celery-worker=4
```

#### Load Balancing
Nginx automatically load balances between scaled web containers.

### Security Configuration

#### SSL/TLS
- Production requires valid SSL certificates
- Certificates should be placed in `nginx/ssl/`
- HTTP automatically redirects to HTTPS

#### Security Headers
Nginx includes security headers:
- HSTS (HTTP Strict Transport Security)
- X-Frame-Options
- X-Content-Type-Options
- XSS Protection

#### Rate Limiting
- API endpoints: 10 requests/second
- Login endpoints: 1 request/second
- Configurable in `nginx/nginx.conf`

### Backup Strategy

#### Automated Backups
```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
mkdir -p $BACKUP_DIR

# Database backup
docker exec attendrix-postgres pg_dump -U attendrix_user attendrix_prod > $BACKUP_DIR/attendrix_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/attendrix_$DATE.sql

# Remove old backups (keep 7 days)
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
EOF

chmod +x backup.sh

# Add to crontab for daily backups
echo "0 2 * * * /path/to/attendrix/backup.sh" | crontab -
```

### Update and Maintenance

#### Update Application
```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

#### Database Migrations
```bash
# Run migrations (if using Alembic)
docker exec attendrix-web flask db upgrade
```

### Troubleshooting

#### Common Issues

1. **Container won't start**
```bash
# Check logs
docker-compose logs <service-name>

# Check resource usage
docker stats
```

2. **Database connection issues**
```bash
# Test database connection
docker exec attendrix-postgres pg_isready -U attendrix_user

# Check network
docker network ls
docker network inspect attendrix_attendrix-network
```

3. **High memory usage**
```bash
# Check memory usage
docker stats

# Restart services
docker-compose restart
```

#### Performance Optimization

1. **Database Optimization**
- Add indexes for frequently queried fields
- Monitor slow queries
- Consider read replicas for high traffic

2. **Redis Optimization**
- Monitor memory usage
- Configure appropriate eviction policies
- Consider Redis Cluster for large deployments

3. **Application Optimization**
- Enable caching for frequently accessed data
- Optimize database queries
- Use connection pooling

### Development Environment

For local development, use the development configuration:

```bash
# Set development environment
export ENVIRONMENT=development

# Use development database
export DATABASE_URL=sqlite:///attendrix_dev.db

# Run with debug mode
export FLASK_DEBUG=True

# Start development server
python app.py
```

### Production Checklist

- [ ] Environment variables configured
- [ ] SSL certificates installed
- [ ] Firebase credentials configured
- [ ] Database backups scheduled
- [ ] Monitoring setup
- [ ] Log rotation configured
- [ ] Security headers verified
- [ ] Rate limiting tested
- [ ] Load testing performed
- [ ] Disaster recovery plan documented

### Support

For deployment issues:
- Check logs: `docker-compose logs`
- Verify configuration: `.env` file
- Test connectivity: `docker-compose exec web curl localhost:8000/health`
- Monitor resources: `docker stats`

## 📞 Contact

- **Email**: alexiscrazy605@gmail.com
- **Phone**: +237-653-031-002
