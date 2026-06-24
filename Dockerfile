# Attendrix Dockerfile
# Multi-stage build for production deployment

# Stage 1: Build stage
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libgdal-dev \
    gdal-bin \
    libproj-dev \
    libgeos-dev \
    libspatialite-dev \
    spatialite-bin \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    libzip-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV DJANGO_SETTINGS_MODULE=attendrix.settings.production

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    libgdal28 \
    libproj25 \
    libgeos3.11.0 \
    libspatialite7 \
    libffi8 \
    libssl3 \
    libjpeg62-turbo \
    libpng16-16 \
    libwebp7 \
    libzip4 \
    zlib1g \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r attendrix && useradd -r -g attendrix attendrix

# Set work directory
WORKDIR /app

# Copy Python dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/media /app/static /app/uploads && \
    chown -R attendrix:attendrix /app

# Set permissions
RUN chmod +x /app/entrypoint.sh

# Switch to non-root user
USER attendrix

# Collect static files
RUN python manage.py collectstatic --noinput --clear

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Start the application
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "--keepalive", "5", "--max-requests", "1000", "--max-requests-jitter", "50", "attendrix.wsgi:application"]
