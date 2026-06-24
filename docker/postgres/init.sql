-- Attendrix PostgreSQL Initialization Script
-- Sets up the database with extensions and initial configuration

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- Create PostGIS extensions (if available)
-- CREATE EXTENSION IF NOT EXISTS "postgis";
-- CREATE EXTENSION IF NOT EXISTS "postgis_topology";

-- Create indexes for better performance
-- These will be created by Django migrations, but we can add some basic ones

-- Create custom functions
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

-- Create audit logging function
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, operation, old_values, new_values, user_id, timestamp)
        VALUES (TG_TABLE_NAME, 'INSERT', NULL, to_jsonb(NEW), NULL, NOW());
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (table_name, operation, old_values, new_values, user_id, timestamp)
        VALUES (TG_TABLE_NAME, 'UPDATE', to_jsonb(OLD), to_jsonb(NEW), NULL, NOW());
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, operation, old_values, new_values, user_id, timestamp)
        VALUES (TG_TABLE_NAME, 'DELETE', to_jsonb(OLD), NULL, NULL, NOW());
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create full-text search configuration
CREATE TEXT SEARCH CONFIGURATION english_unaccent (COPY = english);
ALTER TEXT SEARCH CONFIGURATION english_unaccent
    DROP MAPPING FOR asciiword;
ALTER TEXT SEARCH CONFIGURATION english_unaccent
    ADD MAPPING FOR asciiword WITH unaccent, english_stem;

-- Create search function
CREATE OR REPLACE FUNCTION search_function(search_term TEXT)
RETURNS TABLE(id UUID, rank REAL) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.id,
        ts_rank_cd(search_vector, plainto_tsquery('english_unaccent', search_term)) AS rank
    FROM 
        searchable_model t
    WHERE 
        search_vector @@ plainto_tsquery('english_unaccent', search_term)
    ORDER BY 
        rank DESC;
END;
$$ LANGUAGE plpgsql;

-- Create database performance monitoring view
CREATE OR REPLACE VIEW performance_stats AS
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation,
    most_common_vals,
    most_common_freqs
FROM 
    pg_stats
WHERE 
    schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY 
    schemaname, tablename, attname;

-- Create user activity monitoring view
CREATE OR REPLACE VIEW user_activity AS
SELECT 
    u.id,
    u.username,
    u.email,
    u.last_login,
    u.is_active,
    COUNT(al.id) as login_attempts,
    MAX(al.created_at) as last_activity
FROM 
    users_user u
LEFT JOIN 
    authentication_securitylog al ON u.id = al.user_id
WHERE 
    u.is_deleted = false
GROUP BY 
    u.id, u.username, u.email, u.last_login, u.is_active
ORDER BY 
    u.last_login DESC NULLS LAST;

-- Create attendance statistics view
CREATE OR REPLACE VIEW attendance_statistics AS
SELECT 
    i.id as institution_id,
    i.name as institution_name,
    COUNT(DISTINCT s.id) as total_sessions,
    COUNT(DISTINCT ar.id) as total_records,
    COUNT(DISTINCT CASE WHEN ar.status = 'present' THEN ar.id END) as present_records,
    COUNT(DISTINCT CASE WHEN ar.status = 'absent' THEN ar.id END) as absent_records,
    COUNT(DISTINCT CASE WHEN ar.status = 'late' THEN ar.id END) as late_records,
    ROUND(
        (COUNT(DISTINCT CASE WHEN ar.status = 'present' THEN ar.id END) * 100.0 / 
         NULLIF(COUNT(DISTINCT ar.id), 0)), 2
    ) as attendance_rate
FROM 
    institutions_institution i
LEFT JOIN 
    scheduling_classsession s ON i.id = s.institution_id
LEFT JOIN 
    attendance_attendancerecord ar ON s.id = ar.session_id
WHERE 
    i.is_deleted = false
GROUP BY 
    i.id, i.name
ORDER BY 
    i.name;

-- Create notification statistics view
CREATE OR REPLACE VIEW notification_statistics AS
SELECT 
    i.id as institution_id,
    i.name as institution_name,
    COUNT(n.id) as total_notifications,
    COUNT(DISTINCT CASE WHEN n.notification_type = 'alert' THEN n.id END) as alert_notifications,
    COUNT(DISTINCT CASE WHEN n.notification_type = 'announcement' THEN n.id END) as announcement_notifications,
    COUNT(DISTINCT CASE WHEN n.in_app_read = true THEN n.id END) as read_notifications,
    COUNT(DISTINCT CASE WHEN n.email_sent = true THEN n.id END) as email_notifications,
    COUNT(DISTINCT CASE WHEN n.sms_sent = true THEN n.id END) as sms_notifications,
    AVG(EXTRACT(EPOCH FROM (n.read_at - n.created_at))/60) as avg_read_time_minutes
FROM 
    institutions_institution i
LEFT JOIN 
    alerts_notification n ON i.id = n.institution_id
WHERE 
    i.is_deleted = false
    AND n.is_deleted = false
GROUP BY 
    i.id, i.name
ORDER BY 
    i.name;

-- Create system health check function
CREATE OR REPLACE FUNCTION system_health_check()
RETURNS TABLE(
    component TEXT,
    status TEXT,
    details JSONB
) AS $$
BEGIN
    -- Database health
    RETURN QUERY
    SELECT 
        'database'::TEXT,
        'healthy'::TEXT,
        jsonb_build_object(
            'connections', COUNT(*),
            'size', pg_size_pretty(pg_database_size(current_database())),
            'uptime', age(pg_postmaster_start_time(), NOW())
        )
    FROM 
        pg_stat_activity
    WHERE 
        state = 'active';
    
    -- Table statistics
    RETURN QUERY
    SELECT 
        'tables'::TEXT,
        'healthy'::TEXT,
        jsonb_build_object(
            'total', COUNT(*),
            'with_data', COUNT(CASE WHEN n_live_tup > 0 THEN 1 END)
        )
    FROM 
        pg_stat_user_tables;
    
    -- Index statistics
    RETURN QUERY
    SELECT 
        'indexes'::TEXT,
        'healthy'::TEXT,
        jsonb_build_object(
            'total', COUNT(*),
            'used', COUNT(CASE WHEN idx_scan > 0 THEN 1 END)
        )
    FROM 
        pg_stat_user_indexes;
END;
$$ LANGUAGE plpgsql;

-- Create cleanup function for old data
CREATE OR REPLACE FUNCTION cleanup_old_data(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
BEGIN
    -- Clean up old audit logs
    DELETE FROM audit_log 
    WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Clean up old security logs
    DELETE FROM authentication_securitylog 
    WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep;
    GET DIAGNOSTICS deleted_count = deleted_count + ROW_COUNT;
    
    -- Clean up old notification queues
    DELETE FROM alerts_notificationqueue 
    WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep;
    GET DIAGNOSTICS deleted_count = deleted_count + ROW_COUNT;
    
    -- Clean up old session data
    DELETE FROM authentication_devicelog 
    WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep;
    GET DIAGNOSTICS deleted_count = deleted_count + ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create backup function
CREATE OR REPLACE FUNCTION create_backup(backup_name TEXT DEFAULT NULL)
RETURNS TEXT AS $$
DECLARE
    backup_file TEXT;
    backup_timestamp TEXT;
BEGIN
    backup_timestamp := to_char(NOW(), 'YYYY-MM-DD_HH24-MI-SS');
    
    IF backup_name IS NULL THEN
        backup_name := 'attendrix_backup_' || backup_timestamp;
    END IF;
    
    backup_file := '/backups/' || backup_name || '.sql';
    
    -- This would typically be called from external backup script
    -- Here we just log the backup request
    INSERT INTO system_log (log_type, message, created_at)
    VALUES ('backup', 'Backup requested: ' || backup_file, NOW());
    
    RETURN backup_file;
END;
$$ LANGUAGE plpgsql;

-- Create system log table for monitoring
CREATE TABLE IF NOT EXISTS system_log (
    id SERIAL PRIMARY KEY,
    log_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on system_log
CREATE INDEX IF NOT EXISTS idx_system_log_created_at ON system_log(created_at);
CREATE INDEX IF NOT EXISTS idx_system_log_type ON system_log(log_type);

-- Grant permissions to the attendrix user
GRANT USAGE ON SCHEMA public TO attendrix;
GRANT CREATE ON SCHEMA public TO attendrix;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO attendrix;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO attendrix;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO attendrix;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO attendrix;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO attendrix;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO attendrix;

-- Create initial system log entry
INSERT INTO system_log (log_type, message, details)
VALUES ('initialization', 'Database initialized successfully', 
        jsonb_build_object('timestamp', NOW(), 'version', '1.0'));

COMMIT;
