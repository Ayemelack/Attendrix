# Multi-stage Dockerfile for Attendrix

# Stage 1: Build stage
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Stage 2: Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /tmp/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create app user with no login shell and no home directory
RUN groupadd -r attendrix && \
    useradd -r -g attendrix -d /app -s /usr/sbin/nologin attendrix && \
    mkdir -p /app/config /app/uploads /app/logs /app/static && \
    mkdir -p src/presentation/static/css src/presentation/static/js src/presentation/static/images && \
    mkdir -p logs uploads && \
    chown -R attendrix:attendrix /app

# Copy application code
COPY --chown=attendrix:attendrix . /app

# Set working directory
WORKDIR /app

# Securely set permissions on sensitive files
RUN chmod 640 /app/.env 2>/dev/null || true && \
    chmod 640 /app/firebase-credentials.json 2>/dev/null || true && \
    find /app -name "*.py" -exec chmod 440 {} \; && \
    find /app -name "*.pyc" -delete 2>/dev/null || true

# Install gunicorn
RUN pip install --no-cache-dir --no-compile gunicorn

# Switch to non-root user (drop all privileges)
USER attendrix:attendrix

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "--keepalive", "5", "--max-requests", "1000", "--max-requests-jitter", "100", "app:app"]
