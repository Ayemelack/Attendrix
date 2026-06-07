# DEBUG ARTIFACT REMOVAL REPORT

## Audit Date: 2026-06-07

---

## Files Removed from Git Tracking

| File | Reason | Action |
|------|--------|--------|
| `mock_database.json` | 127KB of PII (password hashes, emails, names) committed to repo | `git rm --cached` |
| `mock_database.json.bak` | Duplicate backup of same sensitive data | `git rm --cached` |

## Files Already Ignored (Confirmed)

| File | .gitignore Rule | Status |
|------|----------------|--------|
| `.env` | Line 88: `.env` | ✅ Untracked |
| `.env.dev` | Now line 89: `.env.dev` | ✅ Untracked |
| `.env.*` | Now line 90: `.env.*` | ✅ Untracked |
| `firebase-dev.json` | Line 123: `firebase-dev.json` | ✅ Untracked |
| `tools/cert.pem` | Line 124: `*.pem` | ✅ Untracked |
| `tools/key.pem` | Line 124: `*.pem` | ✅ Untracked |

## .gitignore Enhancements

Added the following patterns to `.gitignore`:
- `.env.dev` (explicit)
- `.env.*` (catch-all for environment variants)
- `mock_database.json`
- `mock_database.json.bak`
- `mock_database*.json` (catch-all)
- `config/firebase-credentials.json`
- `firebase*.json` (broad Firebase credentials pattern)

---

## Debug Overrides Removed

| Location | Issue | Fix |
|----------|-------|-----|
| `firebase_service.py:84` | `if True or ...` forced mock mode | Evaluates `USE_MOCK_FIREBASE` properly |
| `config/settings.py:184` | `unsafe-eval` in CSP default | Removed |
| `config/settings.py:227` | `D3f@ultCh4ng3Me!` default admin password | Removed — must be configured explicitly |
| `app.py:3722` | `password123` hardcoded in demo response | Moved to env var |

---

## Secure Coding Practices Enforced

| Practice | Implementation |
|----------|---------------|
| Mock mode blocked in production | `firebase_service.py` raises `RuntimeError` if mock requested in production |
| Secrets must be explicitly configured | Production bootstrap fails if `BOOTSTRAP_ADMIN_PASSWORD` is missing |
| Entropy validation | SECRET_KEY min 128 bits, JWT_SECRET_KEY min 256 bits |
| Placeholder detection | Common patterns (`must-set-`, `change-me`, `your-`) rejected |
| CSP hardening | `unsafe-eval` removed; nonce support for scripts and styles |
| Sensitive files ignored | `.gitignore` covers all credential and environment files |

---

## Still Present (Low Risk)

| Artifact | Reason Kept |
|----------|-------------|
| `test_*.py` | Test files needed for CI/CD |
| `setup_friends.bat` | Development setup script (excluded from production deploy) |
| `check_passwords.py` | Security utility script |
| `create_test_users.py` | Development utility |
| `*.bak` files (non-mock) | Documentation backups |
