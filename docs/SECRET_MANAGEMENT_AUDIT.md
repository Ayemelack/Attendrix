# SECRET MANAGEMENT AUDIT

## Audit Date: 2026-06-07

---

## Secrets Found in Codebase

### 1. Hardcoded Secrets (All Resolved)

| Secret | Location | Risk | Action |
|--------|----------|------|--------|
| `D3f@ultCh4ng3Me!` | `config/settings.py:227` | Default admin password | Removed — must now be set via env var |
| `password123` | `app.py:3722` | Demo user password hardcoded | Moved to `DEMO_USER_PASSWORD` env var |
| `your-email@gmail.com` | `.env.example:39` | Example email with real domain | Changed to `your-email@example.com` |
| `must-set-secure-random-*` | `.env` | Placeholder secrets in tracked file | `.env` already in `.gitignore` (confirmed) |

### 2. Committed Sensitive Files (Removed from Tracking)

| File | Size | Contents | Action |
|------|------|----------|--------|
| `mock_database.json` | 127 KB | User PII, password hashes, institution data | `git rm --cached` |
| `mock_database.json.bak` | ~130 KB | Backup copy of same data | `git rm --cached` |

### 3. Files Correctly Excluded by `.gitignore`

| File | Status |
|------|--------|
| `.env` | ✅ Already untracked |
| `.env.dev` | ✅ Already untracked (and newly added to `.gitignore`) |
| `firebase-dev.json` | ✅ Already untracked |
| `tools/*.pem` | ✅ Already untracked |
| `*.db` / `*.sqlite3` | ✅ Already untracked |

### 4. Template Files (Safe — Contain Placeholders Only)

| File | Purpose |
|------|---------|
| `.env.example` | Environment variable template |
| `config/firebase-credentials.json.example` | Firebase service account template |

---

## Secret Validation Enforcement

### Startup Checks (in `app.py` and `config/settings.py`)

- **Minimum length:** SECRET_KEY ≥ 32 chars, JWT_SECRET_KEY ≥ 64 chars
- **Placeholder detection:** Rejects `must-set-`, `change-me`, `your-`, `secret`, `default`, `changethis`
- **Entropy validation:** Minimum 128 bits for SECRET_KEY, 256 bits for JWT_SECRET_KEY
- **Character diversity:** Rejects keys using only 1 unique character

### Production-Gated Requirements

Production startup **fails** if any of these are missing or invalid:
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `RATELIMIT_STORAGE_URL`
- `FIREBASE_CREDENTIALS_PATH`
- `FIREBASE_PROJECT_ID`
- `SMTP_HOST` / `SMTP_USER` / `SMTP_PASS`
- `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `SECURITY_ALERT_WEBHOOK`

---

## Recommendations

1. Rotate any credentials previously committed — even briefly — in the repository history
2. Use a secrets manager (Hashicorp Vault, AWS Secrets Manager) for production
3. Add pre-commit hook for secret scanning (`trufflehog`, `git-secrets`)
4. Run `git filter-branch` or `BFG Repo-Cleaner` to purge `mock_database.json` from git history
