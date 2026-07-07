import sys
import logging
from app import app
from src.infrastructure.sqlalchemy_db import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_models_vs_alembic():
    from sqlalchemy import inspect
    engine = SessionLocal().get_bind()
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    required = ['users', 'courses', 'departments', 'attendance_sessions', 'attendance_records']
    missing = [t for t in required if t not in tables]
    if missing:
        logger.error(f"Missing tables: {missing}")
        return False
    logger.info("Database integrity check passed.")
    return True

def audit_authentication():
    with app.app_context():
        import sys
        if 'src.infrastructure.firebase_service' in sys.modules:
            logger.error("Firebase module is still imported!")
            return False
        logger.info("Authentication audit passed.")
        return True

def run_audits():
    success = True
    success &= check_models_vs_alembic()
    success &= audit_authentication()
    
    if success:
        logger.info("Phase 7B audits completed successfully.")
        sys.exit(0)
    else:
        logger.error("Phase 7B audits failed.")
        sys.exit(1)

if __name__ == '__main__':
    run_audits()
