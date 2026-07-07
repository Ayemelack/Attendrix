with open('src/application/auth_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Remove firebase init
content = re.sub(r'self\.firebase_service =.*?\n', '', content)
content = re.sub(r',\s*firebase_service=None', '', content)

# In create_user, replace firebase_uid creation
content = re.sub(r'firebase_uid = self\.firebase_service\.create_user\(.*?display_name=f\".*?\"\s*\)', 'import uuid\n        firebase_uid = str(uuid.uuid4())', content, flags=re.DOTALL)
content = re.sub(r'self\.firebase_service\.set_custom_claims\(firebase_uid, custom_claims\)', 'pass', content)

# In login, remove set_custom_claims
content = re.sub(r'self\.firebase_service\.set_custom_claims\(.*?\)', 'pass', content)

# Remove any auth errors related to firebase
content = content.replace("if 'firebase_uid' in locals():", "if False:")
content = re.sub(r'self\.firebase_service\.delete_user\(firebase_uid\)', 'pass', content)

with open('src/application/auth_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
