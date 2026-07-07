import sqlite3
import uuid
from datetime import datetime, timedelta

conn = sqlite3.connect('attendrix_prod.db')
cursor = conn.cursor()

# Get or create institution
cursor.execute("SELECT id FROM institutions LIMIT 1")
inst = cursor.fetchone()
if not inst:
    inst_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO institutions (id, name, code, is_active, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
                   (inst_id, 'Demo Institution', 'DEMO', datetime.utcnow(), datetime.utcnow()))
else:
    inst_id = inst[0]

# Delete existing voucher just in case
cursor.execute("DELETE FROM vouchers WHERE code = 'ADMIN123'")

# Create voucher
v_id = str(uuid.uuid4())
now = datetime.utcnow()
expires = now + timedelta(days=90)

try:
    cursor.execute("""
        INSERT INTO vouchers (id, code, role, institution_id, is_used, revoked, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (v_id, 'ADMIN123', 'super_admin', inst_id, 0, 0, now, expires))
    conn.commit()
    print("Voucher ADMIN123 created successfully.")
except Exception as e:
    print(f"Error: {e}")

conn.close()
