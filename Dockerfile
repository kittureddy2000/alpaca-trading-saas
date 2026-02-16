# Multi-stage build for Alpaca Trading SaaS
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Production image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY . .

# Make entrypoint scripts executable
RUN chmod +x /app/entrypoint.sh /app/agent-entrypoint.sh

# Collect static files (build-time, may fail without env vars - that's OK)
RUN python manage.py collectstatic --noinput --settings=backend.settings.base 2>/dev/null || echo "Static files will be collected at runtime"

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Use entrypoint script for proper initialization
ENTRYPOINT ["/app/entrypoint.sh"]
