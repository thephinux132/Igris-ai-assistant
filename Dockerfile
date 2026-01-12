# Igris AI Assistant - Docker Image
# Multi-stage build for smaller final image

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY config/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install additional dependencies for container mode
RUN pip install --no-cache-dir gunicorn

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.11-slim as runtime

# Labels
LABEL maintainer="Igris Team"
LABEL version="2.0.0"
LABEL description="Igris AI Assistant - Local System Control"

# Create non-root user
RUN groupadd -r igris && useradd -r -g igris igris

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=igris:igris core/ ./core/
COPY --chown=igris:igris cli/ ./cli/
COPY --chown=igris:igris plugins/ ./plugins/
COPY --chown=igris:igris config/*.yaml ./config/
COPY --chown=igris:igris config/*.example.yaml ./config/
COPY --chown=igris:igris scripts/docker-entrypoint.sh ./

# Create directories for runtime data
RUN mkdir -p /app/logs /app/data /app/config && \
    chown -R igris:igris /app

# Make entrypoint executable
RUN chmod +x /app/docker-entrypoint.sh

# Environment variables
ENV IGRIS_ENV=production
ENV IGRIS_LOG_LEVEL=INFO
ENV IGRIS_CONFIG_DIR=/app/config
ENV IGRIS_DATA_DIR=/app/data
ENV IGRIS_LOG_DIR=/app/logs
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose API port
EXPOSE 8420

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8420/api/v1/health')" || exit 1

# Switch to non-root user
USER igris

# Volumes for persistent data
VOLUME ["/app/logs", "/app/data", "/app/config"]

# Entry point
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command: run API server
CMD ["api"]
