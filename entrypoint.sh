#!/bin/bash
# Attendrix Docker Entrypoint Script
# Handles database migrations, static files, and application startup

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if database is ready
check_database() {
    print_status "Checking database connection..."
    
    # Wait for database to be ready
    while ! python manage.py dbshell --command="SELECT 1;" > /dev/null 2>&1; do
        print_status "Waiting for database to be ready..."
        sleep 2
    done
    
    print_success "Database is ready!"
}

# Function to run database migrations
run_migrations() {
    print_status "Running database migrations..."
    
    # Create migrations if needed
    python manage.py makemigrations --noinput
    
    # Apply migrations
    python manage.py migrate --noinput
    
    print_success "Database migrations completed!"
}

# Function to collect static files
collect_static() {
    print_status "Collecting static files..."
    
    python manage.py collectstatic --noinput --clear
    
    print_success "Static files collected!"
}

# Function to create superuser if needed
create_superuser() {
    print_status "Checking for superuser..."
    
    # Check if superuser exists
    if python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    print('Creating superuser...')
    User.objects.create_superuser(
        username='${SUPERUSER_USERNAME:-admin}',
        email='${SUPERUSER_EMAIL:-admin@attendrix.com}',
        password='${SUPERUSER_PASSWORD:-admin123}'
    )
    print('Superuser created successfully!')
else:
    print('Superuser already exists!')
" > /dev/null 2>&1; then
        print_success "Superuser setup completed!"
    else
        print_warning "Superuser creation failed or already exists"
    fi
}

# Function to load initial data
load_initial_data() {
    print_status "Loading initial data..."
    
    # Load fixtures if they exist
    if [ -d "fixtures" ]; then
        for fixture in fixtures/*.json; do
            if [ -f "$fixture" ]; then
                print_status "Loading fixture: $fixture"
                python manage.py loaddata "$fixture" || print_warning "Failed to load $fixture"
            fi
        done
    fi
    
    # Create default institution if needed
    python manage.py shell -c "
from apps.institutions.models import Institution
if not Institution.objects.exists():
    Institution.objects.create(
        name='Default Institution',
        code='DEFAULT',
        address='Default Address',
        phone='+237-000-000-000',
        email='admin@attendrix.com',
        is_active=True
    )
    print('Default institution created!')
else:
    print('Institution already exists!')
" > /dev/null 2>&1 || print_warning "Failed to create default institution"
    
    print_success "Initial data loaded!"
}

# Function to start Celery worker
start_celery_worker() {
    print_status "Starting Celery worker..."
    celery -A attendrix worker --loglevel=info --concurrency=4 &
    CELERY_WORKER_PID=$!
    print_success "Celery worker started with PID: $CELERY_WORKER_PID"
}

# Function to start Celery beat
start_celery_beat() {
    print_status "Starting Celery beat..."
    celery -A attendrix beat --loglevel=info --schedule=/tmp/celerybeat-schedule &
    CELERY_BEAT_PID=$!
    print_success "Celery beat started with PID: $CELERY_BEAT_PID"
}

# Function to start Flower
start_flower() {
    print_status "Starting Flower..."
    celery -A attendrix flower --port=5555 --basic_auth=${FLOWER_USER:-admin}:${FLOWER_PASSWORD:-flower_secure_password_2024} &
    FLOWER_PID=$!
    print_success "Flower started with PID: $FLOWER_PID"
}

# Function to handle graceful shutdown
cleanup() {
    print_status "Received shutdown signal, cleaning up..."
    
    # Stop background processes
    if [ ! -z "$CELERY_WORKER_PID" ]; then
        print_status "Stopping Celery worker..."
        kill -TERM $CELERY_WORKER_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$CELERY_BEAT_PID" ]; then
        print_status "Stopping Celery beat..."
        kill -TERM $CELERY_BEAT_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$FLOWER_PID" ]; then
        print_status "Stopping Flower..."
        kill -TERM $FLOWER_PID 2>/dev/null || true
    fi
    
    print_success "Cleanup completed!"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Main execution
main() {
    print_status "Starting Attendrix application..."
    print_status "Environment: ${DJANGO_SETTINGS_MODULE:-attendrix.settings.production}"
    
    # Change to app directory
    cd /app
    
    # Wait for database
    check_database
    
    # Run migrations
    run_migrations
    
    # Collect static files
    collect_static
    
    # Create superuser
    create_superuser
    
    # Load initial data
    load_initial_data
    
    # Start background services if needed
    if [ "$START_CELERY_WORKER" = "true" ]; then
        start_celery_worker
    fi
    
    if [ "$START_CELERY_BEAT" = "true" ]; then
        start_celery_beat
    fi
    
    if [ "$START_FLOWER" = "true" ]; then
        start_flower
    fi
    
    # Start the main application
    print_status "Starting Attendrix web application..."
    
    # Use the command passed to the script, or default to gunicorn
    if [ $# -gt 0 ]; then
        print_status "Executing: $@"
        exec "$@"
    else
        print_status "Starting Gunicorn server..."
        exec gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 120 --keepalive 5 --max-requests 1000 --max-requests-jitter 50 attendrix.wsgi:application
    fi
}

# Check if we're running in development or production
if [ "${DJANGO_SETTINGS_MODULE}" = "attendrix.settings.development" ]; then
    print_status "Running in development mode"
    # In development, we might want to run the development server
    if [ "$1" = "runserver" ]; then
        exec python manage.py runserver 0.0.0.0:8000
    fi
fi

# Run main function
main "$@"
