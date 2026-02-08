#!/bin/bash
# Setup script for Alpaca Trading SaaS secrets
# Run this to sync secrets between Cloud Secret Manager and GitHub

set -e

PROJECT_ID="${GCP_PROJECT:-samaanai-stg-1009-124126}"
GITHUB_REPO="kittureddy2000/alpaca-trading-saas"

echo "🔐 Alpaca Trading SaaS - Secrets Setup"
echo "========================================"
echo "GCP Project: $PROJECT_ID"
echo "GitHub Repo: $GITHUB_REPO"
echo ""

# Check gcloud auth
if ! gcloud auth print-identity-token &>/dev/null; then
    echo "❌ Not authenticated with gcloud. Run: gcloud auth login"
    exit 1
fi

# Check gh auth
if ! gh auth status &>/dev/null; then
    echo "❌ Not authenticated with GitHub CLI. Run: gh auth login"
    exit 1
fi

echo "✅ Authenticated with GCP and GitHub"
echo ""

# Function to sync secret from GCP to GitHub
sync_secret() {
    local GCP_SECRET_NAME=$1
    local GITHUB_SECRET_NAME=${2:-$1}

    echo -n "  Syncing $GCP_SECRET_NAME -> $GITHUB_SECRET_NAME... "

    SECRET_VALUE=$(gcloud secrets versions access latest --secret="$GCP_SECRET_NAME" --project="$PROJECT_ID" 2>/dev/null)

    if [ -z "$SECRET_VALUE" ]; then
        echo "❌ Not found in GCP"
        return 1
    fi

    echo "$SECRET_VALUE" | gh secret set "$GITHUB_SECRET_NAME" --repo "$GITHUB_REPO" 2>/dev/null
    echo "✅"
}

# Function to create GCP secret if not exists
create_gcp_secret() {
    local SECRET_NAME=$1
    local SECRET_VALUE=$2

    if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        echo "  $SECRET_NAME already exists in GCP"
        return 0
    fi

    echo -n "  Creating $SECRET_NAME in GCP... "
    echo -n "$SECRET_VALUE" | gcloud secrets create "$SECRET_NAME" --data-file=- --project="$PROJECT_ID" 2>/dev/null
    echo "✅"
}

echo "📦 Step 1: Ensure GCP Secrets Exist"
echo "------------------------------------"

# Generate Django Secret Key if needed
if ! gcloud secrets describe ALPACA_DJANGO_SECRET_KEY --project="$PROJECT_ID" &>/dev/null; then
    DJANGO_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    create_gcp_secret "ALPACA_DJANGO_SECRET_KEY" "$DJANGO_KEY"
else
    echo "  ALPACA_DJANGO_SECRET_KEY already exists"
fi

# Generate Encryption Key if needed
if ! gcloud secrets describe ALPACA_ENCRYPTION_KEY --project="$PROJECT_ID" &>/dev/null; then
    ENCRYPT_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
    create_gcp_secret "ALPACA_ENCRYPTION_KEY" "$ENCRYPT_KEY"
else
    echo "  ALPACA_ENCRYPTION_KEY already exists"
fi

echo ""
echo "📤 Step 2: Sync Secrets to GitHub"
echo "----------------------------------"

# Sync existing secrets
sync_secret "GOOGLE_CLIENT_ID" "GOOGLE_CLIENT_ID"
sync_secret "GOOGLE_CLIENT_SECRET" "GOOGLE_CLIENT_SECRET"
sync_secret "GEMINI_API_KEY" "GEMINI_API_KEY"
sync_secret "ALPACA_DJANGO_SECRET_KEY" "DJANGO_SECRET_KEY"
sync_secret "ALPACA_ENCRYPTION_KEY" "ENCRYPTION_KEY"

echo ""
echo "🔑 Step 3: Check for Missing Secrets"
echo "-------------------------------------"

# Check if DB_PASSWORD exists
if ! gh secret list --repo "$GITHUB_REPO" | grep -q "DB_PASSWORD"; then
    echo "  ⚠️  DB_PASSWORD not set in GitHub"
    echo "     Run: echo 'YOUR_PASSWORD' | gh secret set DB_PASSWORD --repo $GITHUB_REPO"
fi

# Check if GCP_SA_KEY exists
if ! gh secret list --repo "$GITHUB_REPO" | grep -q "GCP_SA_KEY"; then
    echo "  ⚠️  GCP_SA_KEY not set in GitHub"
    echo "     Creating service account key..."

    SA_EMAIL="github-actions@$PROJECT_ID.iam.gserviceaccount.com"

    if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        gcloud iam service-accounts keys create /tmp/gcp-key.json --iam-account="$SA_EMAIL" --project="$PROJECT_ID"
        cat /tmp/gcp-key.json | gh secret set GCP_SA_KEY --repo "$GITHUB_REPO"
        rm /tmp/gcp-key.json
        echo "  ✅ GCP_SA_KEY created and set"
    else
        echo "  ❌ Service account not found: $SA_EMAIL"
    fi
fi

echo ""
echo "📋 Current GitHub Secrets:"
gh secret list --repo "$GITHUB_REPO"

echo ""
echo "✅ Setup complete!"
echo ""
echo "⚠️  Manual Steps Required:"
echo "   1. Set DB_PASSWORD if not already set:"
echo "      echo 'your-db-password' | gh secret set DB_PASSWORD --repo $GITHUB_REPO"
echo ""
echo "   2. Add OAuth Redirect URIs in Google Cloud Console:"
echo "      https://console.cloud.google.com/apis/credentials"
echo ""
echo "      Add these redirect URIs:"
echo "      - https://alpaca-api-staging-362270100637.us-west1.run.app/accounts/google/login/callback/"
echo "      - https://stg.alpaca.samaanai.com/accounts/google/login/callback/ (if using custom domain)"
