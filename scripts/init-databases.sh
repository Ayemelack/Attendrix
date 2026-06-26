#!/bin/bash
# Database initialization script for Attendrix

set -e

# Function to create database
create_database() {
    local db_name=$1
    echo "Creating database: $db_name"
    
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        CREATE DATABASE $db_name;
        GRANT ALL PRIVILEGES ON DATABASE $db_name TO $POSTGRES_USER;
EOSQL
    
    echo "Database $db_name created successfully"
}

# Create additional databases if they don't exist
echo "Initializing Attendrix databases..."

# Check if databases already exist
DB_EXISTS=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_database WHERE datname='attendrix_dev'" || echo "")

if [ -z "$DB_EXISTS" ]; then
    create_database "attendrix_dev"
else
    echo "Database attendrix_dev already exists"
fi

DB_EXISTS=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_database WHERE datname='attendrix_staging'" || echo "")

if [ -z "$DB_EXISTS" ]; then
    create_database "attendrix_staging"
else
    echo "Database attendrix_staging already exists"
fi

echo "Database initialization completed!"

# Create initial tables and indexes
echo "Creating initial database schema..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "attendrix_prod" <<-EOSQL
    -- Create extensions if needed
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pg_trgm";
    
    -- Create indexes for common queries
    -- These will be created by the application but we can add some basic ones
    
    -- Example indexes (application will create more specific ones)
    -- CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    -- CREATE INDEX IF NOT EXISTS idx_users_institution_id ON users(institution_id);
    -- CREATE INDEX IF NOT EXISTS idx_attendance_records_student_id ON attendance_records(student_id);
    -- CREATE INDEX IF NOT EXISTS idx_attendance_records_session_id ON attendance_records(attendance_session_id);
    
    -- Create audit log table
    CREATE TABLE IF NOT EXISTS deployment_audit (
        id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
        deployment_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        version VARCHAR(50),
        environment VARCHAR(20),
        status VARCHAR(20)
    );
    
    -- Log this deployment
    INSERT INTO deployment_audit (version, environment, status) 
    VALUES ('1.0.0', 'production', 'completed');
    
EOSQL

echo "Database schema initialization completed!"
