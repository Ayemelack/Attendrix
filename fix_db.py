import sqlite3

conn = sqlite3.connect('attendrix_prod.db')
cursor = conn.cursor()

def add_col(name, type_def):
    try:
        cursor.execute(f"ALTER TABLE vouchers ADD COLUMN {name} {type_def}")
        print(f"Added {name}")
    except Exception as e:
        print(f"Error adding {name}: {e}")

add_col("expires_at", "DATETIME")
add_col("revoked", "BOOLEAN DEFAULT 0")
add_col("revoked_at", "DATETIME")

conn.commit()
conn.close()
print("Done.")
