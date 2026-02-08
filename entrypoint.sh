#!/bin/bash
set -e

echo "🚀 Starting Alpaca Trading SaaS Backend..."
echo "Environment: ${DJANGO_SETTINGS_MODULE:-backend.settings.base}"

# Wait for database to be ready (Cloud SQL may take a moment)
echo "⏳ Waiting for database connection..."
sleep 3

# Run migrations
echo "📦 Running database migrations..."
python manage.py migrate --noinput || {
    echo "⚠️ Migration failed, attempting individual migrations..."
    python manage.py migrate contenttypes --noinput || echo "contenttypes skipped"
    python manage.py migrate auth --noinput || echo "auth skipped"
    python manage.py migrate sites --noinput || echo "sites skipped"
    python manage.py migrate sessions --noinput || echo "sessions skipped"
    python manage.py migrate admin --noinput || echo "admin skipped"
    python manage.py migrate trading_api --noinput || echo "trading_api skipped"
    python manage.py migrate account --noinput || echo "account skipped"
    python manage.py migrate socialaccount --noinput || echo "socialaccount skipped"
    python manage.py migrate token_blacklist --noinput || echo "token_blacklist skipped"
    echo "✅ Individual migrations completed"
}

# Setup Google OAuth provider in database (if GOOGLE_CLIENT_ID is set)
if [ -n "$GOOGLE_CLIENT_ID" ]; then
    echo "🔐 Configuring Google OAuth..."
    python scripts/setup_google_oauth.py || echo "⚠️ OAuth setup skipped (may already exist)"
fi

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear 2>/dev/null || python manage.py collectstatic --noinput

# Create cache table if using database cache
python manage.py createcachetable 2>/dev/null || echo "Cache table already exists or not using DB cache"

echo "✅ Initialization complete!"
echo ""
echo "🌐 Starting Gunicorn server on port ${PORT:-8080}..."

# Start server
exec gunicorn backend.wsgi:application \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers ${GUNICORN_WORKERS:-2} \
    --threads ${GUNICORN_THREADS:-4} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --enable-stdio-inheritance
