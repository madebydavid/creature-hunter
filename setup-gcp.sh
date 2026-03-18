#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="earth-embeddings-sandbox"
SA_NAME="earth-embeddings-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="key.json"

# ──────────────────────────────────────
# Phase 1: Preflight — gather everything, create nothing
# ──────────────────────────────────────

echo "Running preflight checks..."

# gcloud installed?
if ! command -v gcloud &>/dev/null; then
    echo "Error: gcloud CLI not found. Install from https://cloud.google.com/sdk/docs/install"
    exit 1
fi
echo "  gcloud found."
# Auth valid? (actually make an API call, not just check config)
if ! gcloud auth print-access-token &>/dev/null; then
    echo "Error: gcloud auth is expired or invalid."
    echo "  Run: gcloud auth login"
    exit 1
fi
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null)
echo "  Authenticated as: $ACTIVE_ACCOUNT"
# Now safe to query billing, project, etc.
BILLING_ACCOUNT=$(gcloud billing accounts list \
    --format="csv[no-heading](name,open)" \
    | grep ",True" | head -1 | cut -d',' -f1)
if [[ -z "$BILLING_ACCOUNT" ]]; then
    echo "Error: No active billing account found."
    echo "  Set one up at https://console.cloud.google.com/billing"
    echo "  Nothing has been created."
    exit 1
fi
echo "  Billing account: $BILLING_ACCOUNT"

# Project exists?
PROJECT_EXISTS=false
if gcloud projects describe "$PROJECT_ID" &>/dev/null; then
    PROJECT_EXISTS=true
    echo "  Project '$PROJECT_ID' already exists."
else
    echo "  Project '$PROJECT_ID' will be created."
fi

# Billing already linked?
BILLING_LINKED=false
if [[ "$PROJECT_EXISTS" == true ]]; then
    CURRENT_BILLING=$(gcloud billing projects describe "$PROJECT_ID" \
        --format="value(billingAccountName)" 2>/dev/null || true)
    if [[ -n "$CURRENT_BILLING" ]]; then
        BILLING_LINKED=true
        echo "  Billing already linked."
    else
        echo "  Billing will be linked."
    fi
fi

# Service account exists?
SA_EXISTS=false
if [[ "$PROJECT_EXISTS" == true ]]; then
    if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        SA_EXISTS=true
        echo "  Service account already exists."
    else
        echo "  Service account will be created."
    fi
fi

# Key file exists?
KEY_EXISTS=false
if [[ -f "$KEY_FILE" ]]; then
    KEY_EXISTS=true
    echo "  Key file already exists."
else
    echo "  Key file will be created."
fi

echo ""
echo "Preflight complete. Proceeding..."
echo ""

# ──────────────────────────────────────
# Phase 2: Create/configure
# ──────────────────────────────────────

if [[ "$PROJECT_EXISTS" == false ]]; then
    echo "Creating project..."
    gcloud projects create "$PROJECT_ID" --name="Earth Embeddings"
fi

gcloud config set project "$PROJECT_ID" --quiet

if [[ "$BILLING_LINKED" == false ]]; then
    echo "Linking billing..."
    gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
fi

echo "Enabling APIs..."
gcloud services enable earthengine.googleapis.com

if [[ "$SA_EXISTS" == false ]]; then
    echo "Creating service account..."
    gcloud iam service-accounts create "$SA_NAME" \
        --display-name="Earth Embeddings Pipeline"
fi

echo "Ensuring IAM roles..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/earthengine.viewer" \
    --condition=None --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/serviceusage.serviceUsageConsumer" \
    --condition=None --quiet

if [[ "$KEY_EXISTS" == false ]]; then
    echo "Creating key..."
    gcloud iam service-accounts keys create "$KEY_FILE" \
        --iam-account="$SA_EMAIL"
fi

if [[ -f "$KEY_FILE" ]]; then
    chmod 644 "$KEY_FILE"
fi

# ──────────────────────────────────────
# Done
# ──────────────────────────────────────

echo ""
echo "Setup complete."
echo ""
echo "Add to your .env:"
echo "  export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/$KEY_FILE"
echo "  export GCP_PROJECT_ID=$PROJECT_ID"
echo "  export SERVICE_ACCOUNT_EMAIL=$SA_EMAIL"
echo ""
echo "One-time manual step — register this project for Earth Engine:"
echo "  https://console.cloud.google.com/earth-engine/configuration?project=$PROJECT_ID"
echo ""
echo "Optional (user workflow):"
echo "  https://code.earthengine.google.com"
echo "  earthengine set_project $PROJECT_ID"
