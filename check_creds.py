import sqlite3, json

conn = sqlite3.connect('attendrix_prod.db')
conn.row_factory = sqlite3.Row

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t['name'] for t in tables])

# Check users table
for table in ['users', 'user', 'vouchers', 'voucher']:
    try:
        rows = conn.execute(f"SELECT * FROM {table} LIMIT 20").fetchall()
        print(f"\n=== {table} ===")
        for row in rows:
            print(dict(row))
    except Exception as e:
        print(f"\n{table}: {e}")

conn.close()
