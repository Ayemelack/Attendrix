import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Import our app configuration and metadata
from config.settings import get_config
from src.infrastructure.models import Base

# Import all model files so Alembic sees their tables
import src.infrastructure.mail_models  # noqa: F401
import src.infrastructure.feedback_models  # noqa: F401
import src.infrastructure.demo_sql_repositories  # noqa: F401

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata
target_metadata = Base.metadata

# Override sqlalchemy.url with our explicitly loaded environment variable
import os
from dotenv import load_dotenv

load_dotenv()
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    raise ValueError("DATABASE_URL environment variable must be set for Alembic migrations.")
    
config.set_main_option('sqlalchemy.url', database_url)

# Validation Step: Verify all expected tables are in metadata
expected_tables = {
    'users', 'user_profiles', 'institutions', 'departments',
    'courses', 'course_enrollments', 'vouchers',
    'attendance_sessions', 'attendance_records', 'attendance_verification_logs',
    'offline_queue', 'network_presence', 'activity_logs', 'security_logs', 'device_fingerprints',
    # Mail tables
    'mail_smtp_profiles', 'mail_templates', 'mail_queue', 'mail_audit_logs', 'mail_unsubscribes',
    # Feedback tables
    'feedback', 'feedback_replies', 'feedback_reactions', 'moderation_logs', 'feedback_diagnostics', 'escalation_history',
    # Demo tables
    'demo_leads', 'demo_onboarding_sessions', 'demo_bookings', 'demo_trials', 'demo_analytics_events'
}
registered_tables = set(target_metadata.tables.keys())

missing_tables = expected_tables - registered_tables
if missing_tables:
    raise ValueError(f"CRITICAL ERROR: Missing expected tables in SQLAlchemy metadata: {missing_tables}. Check imports in models.py.")

print("--- Registered SQLAlchemy Metadata Tables ---")
for table in registered_tables:
    print(f"- {table}")
print("---------------------------------------------")

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
