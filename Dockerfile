# ── Build stage ───────────────────────────────────────────────
FROM python:3.12-alpine AS builder

WORKDIR /build
COPY app/requirements.txt .
RUN mkdir -p /install && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────
FROM python:3.12-alpine

# Non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
RUN apk add --no-cache curl

WORKDIR /app

# Copy installed deps from builder
COPY --from=builder /install /usr/local

# Copy app source
COPY app/ .

# Create logs directory with correct ownership
RUN mkdir -p /app/logs && chown -R appuser:appgroup /app/logs

# Environment defaults — overridden by docker-compose
ENV MODE=stable \
    APP_VERSION=1.0.0 \
    APP_PORT=3000

USER appuser

EXPOSE 3000

# Gunicorn: production WSGI server
CMD ["gunicorn", "main:app", \
     "--bind", "0.0.0.0:3000", \
     "--workers", "2", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]