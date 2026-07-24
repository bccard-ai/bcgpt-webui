# syntax=docker/dockerfile:1
# BCGPT WebUI - Multi-stage Docker Build
# Stage 1: Build frontend (Bun)
# Stage 2: Runtime (Python)

# ============================================================
# Stage 1: Frontend Build
# ============================================================
FROM oven/bun:1-alpine AS frontend-builder

WORKDIR /app

# Install dependencies first (layer caching)
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# Copy source and build
COPY . .
RUN bun run build

# ============================================================
# Stage 2: Python Runtime
# ============================================================
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="BCGPT WebUI" \
      org.opencontainers.image.description="Enterprise-Grade Self-Hosted AI Platform with Advanced Agent Orchestration" \
      org.opencontainers.image.source="https://github.com/bccard-ai/bcgpt-webui" \
      org.opencontainers.image.vendor="BC Card" \
      org.opencontainers.image.licenses="Apache-2.0"

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        bash \
        git \
        build-essential \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# Install Python dependencies first (layer caching)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/build /app/build

# Copy license and notice files for compliance (BSD 3-Clause §2, Apache 2.0 §4(d))
COPY LICENSE NOTICE /app/

# Environment defaults
ENV DOCKER=true \
    PORT=8090 \
    HOST=0.0.0.0 \
    DATA_DIR=/app/backend/data \
    FRONTEND_BUILD_DIR=/app/build \
    BCGPT_SESSION_COOKIE_SAME_SITE=lax

# Create data directory and non-root user
RUN mkdir -p /app/backend/data && \
    addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8090/healthz || exit 1

# Persistent data volume
VOLUME ["/app/backend/data"]

# Expose port
EXPOSE 8090

# Run as non-root user
USER appuser

# Entry point
CMD ["bash", "start.sh"]
