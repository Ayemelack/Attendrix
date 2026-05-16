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
    && apt-get clean

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create app user
RUN groupadd -r attendrix && \
    useradd -r -g attendrix -d /app -s /bin/bash attendrix

# Create app directories
RUN mkdir -p /app/config /app/uploads /app/logs /app/static && \
    chown -R attendrix:attendrix /app

# Copy application code
COPY --chown=attendrix:attendrix . /app

# Set working directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p src/presentation/static/css src/presentation/static/js src/presentation/static/images && \
    mkdir -p logs uploads

# Install gunicorn
RUN pip install gunicorn

# Switch to non-root user
USER attendrix

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "--keepalive", "5", "--max-requests", "1000", "--max-requests-jitter", "100", "app:app"]
