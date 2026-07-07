import os
import re

# Delete firebase_security.py entirely
if os.path.exists('src/infrastructure/firebase_security.py'):
    os.remove('src/infrastructure/firebase_security.py')

# Clean comprehensive_security.py
if os.path.exists('src/infrastructure/comprehensive_security.py'):
    with open('src/infrastructure/comprehensive_security.py', 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'@classmethod\s*def sanitize_firebase_data.*?return data\s*', '', content, flags=re.DOTALL)
    with open('src/infrastructure/comprehensive_security.py', 'w', encoding='utf-8') as f:
        f.write(content)

# Clean persistent_auth_service.py
if os.path.exists('src/application/persistent_auth_service.py'):
    with open('src/application/persistent_auth_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'self\.firebase.*?=.*?\n', '', content)
    content = re.sub(r'users = self\.firebase_service\.query_documents\(.*?\)', 'users = []', content, flags=re.DOTALL)
    content = re.sub(r'self\.firebase_service\.update_document\(.*?\)', 'pass', content)
    content = re.sub(r'sessions = self\.firebase_service\.query_documents\(.*?\)', 'sessions = []', content, flags=re.DOTALL)
    content = re.sub(r'user_data = self\.firebase_service\.get_document\(.*?\)', 'user_data = None', content)
    content = re.sub(r'user_sessions = self\.firebase_service\.query_documents\(.*?\)', 'user_sessions = []', content, flags=re.DOTALL)
    content = re.sub(r'self\.firebase_service\.create_document\(.*?\)', 'pass', content)
    with open('src/application/persistent_auth_service.py', 'w', encoding='utf-8') as f:
        f.write(content)

# Clean offline_queue_service.py
if os.path.exists('src/application/offline_queue_service.py'):
    with open('src/application/offline_queue_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'self\.firebase_service = None\n', '', content)
    with open('src/application/offline_queue_service.py', 'w', encoding='utf-8') as f:
        f.write(content)

# Clean sms_service.py
if os.path.exists('src/application/sms_service.py'):
    with open('src/application/sms_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'self\.firebase.*?=.*?\n', '', content)
    with open('src/application/sms_service.py', 'w', encoding='utf-8') as f:
        f.write(content)

# Clean security_monitor.py
if os.path.exists('src/infrastructure/security/security_monitor.py'):
    with open('src/infrastructure/security/security_monitor.py', 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'blocked = firebase_service\.query_documents\(self\.BLOCKED_IPS_COLLECTION\)', 'blocked = []', content)
    content = re.sub(r'alerts = firebase_service\.query_documents\(self\.ALERTS_COLLECTION,.*?\)', 'alerts = []', content, flags=re.DOTALL)
    content = re.sub(r'firebase_service\.create_document\(.*?\)', 'pass', content, flags=re.DOTALL)
    with open('src/infrastructure/security/security_monitor.py', 'w', encoding='utf-8') as f:
        f.write(content)

# Clean auth.py
if os.path.exists('src/presentation/routes/auth.py'):
    with open('src/presentation/routes/auth.py', 'r', encoding='utf-8') as f:
        content = f.read()
    content = content.replace("if 'firebase' in error_msg", "if 'pg' in error_msg")
    with open('src/presentation/routes/auth.py', 'w', encoding='utf-8') as f:
        f.write(content)

# Clean repositories.py
if os.path.exists('src/infrastructure/repositories.py'):
    with open('src/infrastructure/repositories.py', 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'return self\.firebase_service\.query_documents\(.*?\)', 'return []', content, flags=re.DOTALL)
    content = re.sub(r'return self\.firebase_service\.get_document\(.*?\)', 'return None', content, flags=re.DOTALL)
    content = re.sub(r'return self\.firebase_service\.update_document\(.*?\)', 'return False', content, flags=re.DOTALL)
    content = re.sub(r'return self\.firebase_service\.delete_document\(.*?\)', 'return False', content, flags=re.DOTALL)
    content = re.sub(r'self\.firebase_service = None', '', content)
    content = re.sub(r'self\.firebase = None', '', content)
    content = re.sub(r'# Note: Firestore.*?\n', '', content)
    content = content.replace('"""Base repository class for Firestore operations"""', '"""Base repository class"""')
    with open('src/infrastructure/repositories.py', 'w', encoding='utf-8') as f:
        f.write(content)
