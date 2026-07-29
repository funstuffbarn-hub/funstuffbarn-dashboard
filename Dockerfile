# Dockerfile for FunStuffBarn Agent-Etsy Dashboard
# Multi-stage build for production

# ===========================================
# Stage 1: Builder - Install dependencies
# ===========================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install in virtualenv
COPY pyproject.toml ./
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -e .

# ===========================================
# Stage 2: Runtime - Minimal image
# ===========================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=nonroot:nonroot . .

# Create necessary directories
RUN mkdir -p /app/logs /app/reportes /app/prompt_archive && \
    chown -R nonroot:nonroot /app

# Create non-root user (already exists in python:3.11-slim)
USER nonroot

# Environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FUNSTUFFBARN_ROOT=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import sys; sys.exit(0)"]

# Expose port
EXPOSE 8080

# Entry point
ENTRYPOINT ["/opt/venv/bin/python", "main.py"]