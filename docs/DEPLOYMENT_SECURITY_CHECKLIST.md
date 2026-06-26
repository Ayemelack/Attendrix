# DEPLOYMENT SECURITY CHECKLIST

Use this checklist before every production deployment.

---

## Pre-Deployment

### Environment Variables
- [ ] `SECRET_KEY` set to 32+ char random hex (run `python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] `JWT_SECRET_KEY` set to 64+ char random hex
- [ ] `ENVIRONMENT=production`
- [ ] `FLASK_DEBUG=False`
- [ ] `USE_MOCK_FIREBASE=false`
- [ ] `BOOTSTRAP_ADMIN_PASSWORD` set to strong unique password

### Firebase
- [ ] Real Firebase service account JSON deployed (not `firebase-dev.json`)
- [ ] Firestore security rules deployed (see `docs/FIRESTORE_RULES_AUDIT.md`)
- [ ] Firebase project ID matches credentials
- [ ] `FIREBASE_CREDENTIALS_PATH` points to correct credentials file

### Database
- [ ] PostgreSQL or production database configured (not SQLite)
- [ ] `DATABASE_URL` set correctly
- [ ] Migrations run and verified

### Redis
- [ ] Redis instance configured and reachable
- [ ] `REDIS_URL` set correctly
- [ ] `RATELIMIT_STORAGE_URL` set correctly
- [ ] `REDIS_SESSION_ENABLED=true`

### Email
- [ ] SMTP or Resend API configured
- [ ] `MAIL_FROM` set to verified sender domain
- [ ] SPF record published for sending domain
- [ ] DKIM signing enabled

### HTTPS
- [ ] TLS certificate installed (Let's Encrypt or commercial CA)
- [ ] `FORCE_HTTPS=true`
- [ ] `SESSION_COOKIE_SECURE=true`
- [ ] HSTS enabled with `max-age=31536000`

### Security
- [ ] `CSP_ENABLED=true`
- [ ] Turnstile or reCAPTCHA keys configured
- [ ] MFA required for admin roles (`MFA_REQUIRED_FOR`)
- [ ] Rate limiting configured
- [ ] Security monitoring enabled (`SECURITY_MONITORING_ENABLED=true`)
- [ ] Logging configured with appropriate retention

---

## During Deployment

- [ ] `.env` file NOT copied to deployment
- [ ] `mock_database.json` NOT present
- [ ] `__pycache__/` directories excluded
- [ ] `tools/cert.pem` and `tools/key.pem` NOT deployed (use real TLS)
- [ ] `firebase-dev.json` NOT deployed

---

## Post-Deployment

### Verification
- [ ] Application starts without errors
- [ ] `/api/v1/security/health` returns all modules operational
- [ ] Firebase connection verified (not mock)
- [ ] HTTPS redirect works (HTTP → HTTPS)
- [ ] HSTS header present in responses
- [ ] CSP header present and not blocking legitimate resources
- [ ] Session cookies marked `Secure`, `HttpOnly`, `SameSite=Lax`
- [ ] Login flow works end-to-end
- [ ] Admin bootstrap endpoint requires valid `BOOTSTRAP_ADMIN_PASSWORD`

### Monitoring
- [ ] Logs configured with `LOG_LEVEL=WARNING`
- [ ] Security alerts webhook configured
- [ ] Sentry DSN configured for error tracking
- [ ] Failed login rate limiting verified

---

## Incident Response

- [ ] Security team contact info documented
- [ ] Admin lockdown procedure tested
- [ ] Break-glass access codes generated
- [ ] Backup and restore process verified
- [ ] Forensic log chain integrity confirmed
