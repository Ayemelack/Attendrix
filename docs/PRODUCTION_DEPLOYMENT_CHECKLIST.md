# Production Deployment Checklist — Attendrix

## Pre-Deployment Verification

### Environment Configuration
- [ ] `.env` uses `ENVIRONMENT=production` (not `development`)
- [ ] `SECRET_KEY` is 32+ random hex characters: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] `JWT_SECRET_KEY` is 64+ random hex characters: `python -c "import secrets; print(secrets.token_hex(64))"`
- [ ] `FORCE_HTTPS=true`
- [ ] `HSTS_ENABLED=true`
- [ ] `CSP_ENABLED=true`
- [ ] `BOOTSTRAP_ADMIN_PASSWORD` changed from default
- [ ] `CORS_ALLOWED_ORIGINS` lists only production domains
- [ ] `FLASK_DEBUG=False`
- [ ] Database URL is production (not localhost)
- [ ] Redis URL is production (not localhost)

### Secrets & Credentials
- [ ] Firebase service account credentials are valid, not expired
- [ ] Firebase credentials file path is correct
- [ ] Cloudflare Turnstile site/secret keys set (if CAPTCHA enabled)
- [ ] reCAPTCHA site/secret keys set (if Turnstile fallback needed)
- [ ] `RESEND_API_KEY` configured (transactional email)
- [ ] Sentry DSN configured (error monitoring)
- [ ] `SECURITY_ALERT_WEBHOOK` configured (Slack/Teams)
- [ ] `ABUSEIPDB_API_KEY` set (IP reputation)
- [ ] `IPQUALITY_API_KEY` set (IP quality scoring)
- [ ] `GOOGLE_GEOCODING_API_KEY` set (geolocation validation)

### Phase 2 Security Modules Activation
- [ ] `REDIS_SESSION_ENABLED=true` (persistent sessions)
- [ ] `PERSISTENT_RATE_LIMIT=true` (Redis-backed rate limiting)
- [ ] `GEOIP_ENABLED=true` + `GEOIP_DATABASE_PATH` set (MaxMind GeoIP2)
- [ ] `MFA_REQUIRED_FOR=super_admin,institutional_admin`
- [ ] `GEOLOCATION_ENFORCED=true` (if geofencing required)
- [ ] `DEVICE_TRUST_ENABLED=true` (device fingerprint scoring)
- [ ] `CAPTCHA_PROVIDER=turnstile`
- [ ] `USE_MOCK_NETWORK=false` (real IP intelligence)
- [ ] `SECURITY_MONITORING_ENABLED=true`

### Email Production Readiness
- [ ] `SPF_DOMAIN` set (e.g., `attendrix.app`)
- [ ] SPF TXT record published in DNS
- [ ] `DKIM_ENABLED=true` + DKIM key generated and DNS-published
- [ ] `DMARC_POLICY=p=quarantine` or `p=reject` (not `none`)
- [ ] `MAIL_FROM` uses verified sending domain
- [ ] SMTP credentials are correct, not expired
- [ ] Resend API key is configured and verified

## Infrastructure Checks

### Database
- [ ] PostgreSQL is running, reachable, connection pool sized
- [ ] SQLAlchemy connection string uses SSL (`?sslmode=require`)
- [ ] Database migrations applied: `flask db upgrade`
- [ ] Database backups configured and tested

### Redis
- [ ] Redis is running, reachable, authenticated
- [ ] Redis persistence (RDB/AOF) enabled — data survives restart
- [ ] Redis maxmemory-policy configured (e.g., `allkeys-lru`)
- [ ] Redis connection pool sized appropriately

### Celery
- [ ] Celery worker running with `--concurrency` appropriate for hardware
- [ ] Celery beat running (for scheduled tasks)
- [ ] All task queues defined and routed
- [ ] Task result backend configured

### MQTT
- [ ] MQTT broker reachable and authenticated
- [ ] TLS enabled for MQTT connections
- [ ] MQTT topics follow least-privilege ACLs
- [ ] Offline message queuing configured

### File Storage
- [ ] Upload directory exists with correct permissions
- [ ] Max content length set appropriately (`MAX_CONTENT_LENGTH`)
- [ ] Allowed extensions audited

## Security Hardening Verification

### Network
- [ ] TLS/SSL certificate valid, auto-renewal configured (Let's Encrypt / cert-manager)
- [ ] All HTTP traffic redirects to HTTPS
- [ ] HSTS header sent (max-age 31536000, includeSubDomains)
- [ ] Security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection)
- [ ] Content Security Policy is strict (no `'unsafe-inline'` in script-src if possible)
- [ ] No open admin ports exposed (only 443, 80 with redirect)

### Authentication
- [ ] MFA enforced for all admin roles
- [ ] Account lockout after 5 failed attempts
- [ ] Password policy: 8+ chars, upper, lower, digit, special
- [ ] Password max age: 90 days
- [ ] Password history: 5 (no reuse)
- [ ] Session timeout configured (`SESSION_TIMEOUT_MINUTES`)
- [ ] JWT access token expiry ≤ 1 hour
- [ ] JWT refresh token rotation implemented
- [ ] CSRF protection enabled
- [ ] Rate limiting active: IP (100/min), Login (5/min), Register (3/min)

### Monitoring & Incident Response
- [ ] Security event monitoring enabled
- [ ] Threat auto-blocking active
- [ ] Security dashboard accessible to super_admin
- [ ] Audit logging enabled, retention ≥ 365 days
- [ ] Security alerts configured (webhook + email)
- [ ] Forensic audit trail enabled
- [ ] Sentry error tracking enabled with alerts

### Firestore Security
- [ ] Deny-by-default catch-all rule in place
- [ ] All collections have explicit read/write rules
- [ ] No collection allows public write
- [ ] `demo_bookings` create-only public rule intentional
- [ ] Legacy collections (`attendance`, `sessions`, etc.) have restricted access

## Deployment Steps

1. Set all environment variables in production environment
2. Run `flask db upgrade` to apply migrations
3. Start Celery worker: `celery -A app.celery worker --loglevel=INFO`
4. Start Celery beat: `celery -A app.celery beat --loglevel=INFO`
5. Verify Redis connectivity: `redis-cli ping` → `PONG`
6. Verify database connectivity
7. Start Flask app with production WSGI server:
   ```bash
   gunicorn app:app --worker-class gevent --workers 4 --bind 0.0.0.0:5000
   ```
   Or deploy via Docker/container orchestration
8. Verify application starts without errors
9. Run smoke tests on all API endpoints
10. Run security scan (see security_verification_report.md)

## Post-Deployment
- [ ] Monitor logs for errors
- [ ] Verify security headers with `curl -I`
- [ ] Verify CSP with browser dev tools
- [ ] Test CAPTCHA on login/register
- [ ] Test MFA enrollment and verification
- [ ] Test rate limiting by triggering limit
- [ ] Test IP blocking by simulating attack
- [ ] Verify sentry receives errors
- [ ] Verify security dashboard loads
- [ ] Verify security alerts deliver
