#!/bin/bash

# Environment Variables
PROJECT_ID="samaanai-stg-1009-124126"
REGION="us-west1"
SERVICE_NAME="alpaca-api-staging"
JOB_NAME="alpaca-trading-agent"
IMAGE_URL="gcr.io/$PROJECT_ID/$SERVICE_NAME"

# Create Cloud Run Job
gcloud run jobs create $JOB_NAME \
  --image $IMAGE_URL \
  --region $REGION \
  --project $PROJECT_ID \
  --command python \
  --args manage.py,run_strategy \
  --env-vars-file env_vars_job.yaml \
  --set-cloudsql-instances "samaanai-stg-1009-124126:us-west1:samaanai-backend-staging-db" \
  --max-retries 0 \
  --task-timeout 3600s

# Update if exists
if [ $? -eq 1 ]; then
  echo "Job may already exist, attempting update..."
  gcloud run jobs update $JOB_NAME \
    --image $IMAGE_URL \
    --region $REGION \
    --project $PROJECT_ID \
    --command python \
    --args manage.py,run_strategy \
    --env-vars-file env_vars_job.yaml \
    --set-cloudsql-instances "samaanai-stg-1009-124126:us-west1:samaanai-backend-staging-db" \
    --max-retries 0 \
    --task-timeout 3600s
fi
