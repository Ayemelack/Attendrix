import os
import re

for root, _, files in os.walk('src'):
    for f in files:
        if not f.endswith('.py'): continue
        path = os.path.join(root, f)
        with open(path, 'r', encoding='utf-8') as file:
            content = file.read()
            original = content
        
        # Strip all firebase_service calls
        content = re.sub(r'firebase_service\.[a-z_]+\(.*?\) {0,1}', 'None', content, flags=re.DOTALL)
        content = re.sub(r'self\.firebase_service\.[a-z_]+\(.*?\) {0,1}', 'None', content, flags=re.DOTALL)
        content = re.sub(r'self\.firebase\.[a-z_]+\(.*?\) {0,1}', 'None', content, flags=re.DOTALL)
        content = re.sub(r'firebase\.[a-z_]+\(.*?\) {0,1}', 'None', content, flags=re.DOTALL)
        
        # Strip firebase initialization
        content = re.sub(r'self\.firebase.*?=.*?\n', '', content)
        content = re.sub(r'self\.firebase_service.*?=.*?\n', '', content)
        
        # Replace occurrences in defs
        content = re.sub(r',\s*firebase_service=None', '', content)
        content = re.sub(r'firebase_service=None,\s*', '', content)
        content = re.sub(r'firebase_service=None', '', content)
        content = re.sub(r',\s*firebase_service', '', content)
        content = re.sub(r'firebase_service,\s*', '', content)
        content = re.sub(r'firebase_service', 'None', content)
        
        content = content.replace('if firebase:', 'if False:')
        content = content.replace('if not self.firebase:', 'if False:')
        content = content.replace('if self.firebase:', 'if False:')

        content = content.replace("'source': 'firebase'", "'source': 'pg'")
        content = content.replace("firebase = None", "firebase_none = None")

        if 'sanitize_firebase_data' in content:
            content = re.sub(r'@classmethod\s*def sanitize_firebase_data.*?return data\s*', '', content, flags=re.DOTALL)

        if content != original:
            with open(path, 'w', encoding='utf-8') as file:
                file.write(content)
