#!/bin/bash
# Agent entrypoint for Cloud Run Job
# Runs the trading strategy once and exits

echo "🤖 Starting LLM Trading Agent (Cloud Run Job)..."
echo "Environment: ${DJANGO_SETTINGS_MODULE:-backend.settings.production}"
echo "Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

# Wait for database
echo "⏳ Waiting for database..."
sleep 3

# Run migrations (in case agent job starts before backend deploys)
echo "📦 Running migrations..."
python manage.py migrate --noinput 2>&1 || echo "⚠️ Migration skipped"

# Run the trading strategy once for all users
echo "📊 Running trading strategy..."
python manage.py run_strategy --once --symbol SPY 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Agent cycle completed successfully"
else
    echo "❌ Agent cycle failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
