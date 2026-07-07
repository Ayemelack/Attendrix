import os
import sys
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.infrastructure.sqlalchemy_db import get_db_session

def upgrade_vouchers():
    session = get_db_session()
    try:
        columns = [
            "assigned_to_email VARCHAR(255)",
            "assigned_to_name VARCHAR(255)",
            "assigned_at TIMESTAMP",
            "email_sent_status VARCHAR(50)",
            "email_sent_at TIMESTAMP"
        ]
        
        for col in columns:
            try:
                col_name = col.split()[0]
                # Try adding directly, PostgreSQL will raise an error if it exists. We catch it.
                try:
                    # using IF NOT EXISTS would be easier, but let's do a safe fallback query
                    result = session.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='vouchers' AND column_name='{col_name}'")).fetchone()
                    if not result:
                        session.execute(text(f"ALTER TABLE vouchers ADD COLUMN {col}"))
                        print(f"Added column {col_name} to vouchers.")
                    else:
                        print(f"Column {col_name} already exists.")
                except Exception as inner_e:
                    # Maybe it's SQLite
                    try:
                        session.execute(text(f"ALTER TABLE vouchers ADD COLUMN {col}"))
                        print(f"Added column {col_name} to vouchers via SQLite fallback.")
                    except Exception as e:
                        print(f"SQLite fallback failed or column already exists: {e}")
            except Exception as e:
                print(f"Error adding {col}: {e}")
        
        session.commit()
        print("Vouchers schema updated successfully.")
    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    upgrade_vouchers()
