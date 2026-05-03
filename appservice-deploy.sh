#!/usr/bin/env bash
# portal/appservice-deploy.sh
# Deploys the Data Portal (FastAPI backend + Next.js frontend) to Azure App Service
# (Web App for Containers), reusing the existing ecran-rg / ecran-plan.
#
# Mirrors all security and runtime settings from the existing 'ecran' app:
#   HTTPS-only, HTTP/2, TLS 1.2, FtpsOnly, LeastRequests load balancing.
#
# Prerequisites:
#   - Azure CLI installed and logged into company subscription (az login)
#   - Docker Desktop installed and running
#   - Run from Demo/ root:  bash portal/appservice-deploy.sh
#
# What this script creates:
#   ACR (ecrandataportal) → File Shares on ecranstorage →
#   Backend Web App (ecran-data-platform) → Frontend Web App (ecran-data-platform-ui)
#
# Time estimate: ~15 minutes (first build; PyTorch layer is large).

set -euo pipefail

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

SUBSCRIPTION="49f0cb45-0dfc-4d5d-9580-39ac3d8897bf"
RESOURCE_GROUP="ecran-rg"
LOCATION="australiaeast"
PLAN_NAME="ecran-plan"

BACKEND_APP="ecran-data-platform"
FRONTEND_APP="ecran-data-platform-ui"

# ACR — globally unique, lowercase alphanumeric only
ACR_NAME="ecrandataportal"

# Reuse ecran's storage account — new portal-* shares will be added
STORAGE_ACCOUNT="ecranstorage"

# Secrets — exported from your shell or sourced from a local .env (NEVER commit real values)
# Example: source backend/.env && export DATABRICKS_HOST DATABRICKS_TOKEN DATABRICKS_WAREHOUSE_ID ANTHROPIC_API_KEY SECRET_KEY
DATABRICKS_HOST="${DATABRICKS_HOST:-}"
DATABRICKS_TOKEN="${DATABRICKS_TOKEN:-}"
DATABRICKS_WAREHOUSE_ID="${DATABRICKS_WAREHOUSE_ID:-}"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"

# Session/JWT signing key — must be exported (e.g. from .env). Generate with: openssl rand -hex 32
SECRET_KEY="${SECRET_KEY:-}"

# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

if [[ -z "$DATABRICKS_TOKEN" || -z "$ANTHROPIC_API_KEY" ]]; then
  echo "ERROR: Fill in DATABRICKS_TOKEN and ANTHROPIC_API_KEY above before running."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"
echo "Working directory: $(pwd)"

az account set --subscription "$SUBSCRIPTION"
echo "Subscription: Allianzis ($SUBSCRIPTION)"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Azure Container Registry
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 1/6 — Azure Container Registry"
az acr create \
  --name "$ACR_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Basic \
  --admin-enabled true \
  --output table 2>/dev/null || echo "   ACR already exists, continuing..."

ACR_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USER=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASS=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)
echo "   ACR: $ACR_SERVER"

az acr login --name "$ACR_NAME"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Build & Push Backend Image
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 2/6 — Build & Push Backend Image"
echo "   First build takes ~15 min (PyTorch + sentence-transformers)."
docker build \
  -f portal/backend/Dockerfile \
  -t "$ACR_SERVER/portal-backend:latest" \
  .
docker push "$ACR_SERVER/portal-backend:latest"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Storage File Shares (on existing ecranstorage)
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 3/6 — Storage File Shares"
STORAGE_KEY=$(az storage account keys list \
  --account-name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[0].value" -o tsv)

STORAGE_CONN_STR=$(az storage account show-connection-string \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query connectionString \
  -o tsv)

for SHARE in portal-bronze-conf portal-silver-conf portal-chromadb portal-model-cache portal-app-data; do
  echo "   Creating share: $SHARE"
  az storage share create \
    --name "$SHARE" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --quota 10 \
    --output none 2>/dev/null || echo "   Share $SHARE already exists, continuing..."
done

# Upload existing framework config files into the shares
if [[ -d "bronze_framework/conf" ]]; then
  az storage file upload-batch \
    --source "bronze_framework/conf" \
    --destination "portal-bronze-conf" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --output none
  echo "   Uploaded bronze_framework/conf → portal-bronze-conf"
else
  echo "   WARN: bronze_framework/conf not found — share will be empty"
fi

if [[ -d "silver_framework/conf" ]]; then
  az storage file upload-batch \
    --source "silver_framework/conf" \
    --destination "portal-silver-conf" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --output none
  echo "   Uploaded silver_framework/conf → portal-silver-conf"
else
  echo "   WARN: silver_framework/conf not found — share will be empty"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Backend Web App for Containers
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 4/6 — Backend App Service ($BACKEND_APP)"

az webapp create \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --plan "$PLAN_NAME" \
  --deployment-container-image-name "$ACR_SERVER/portal-backend:latest" \
  --output table

# Set ACR pull credentials
az webapp config container set \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --docker-custom-image-name "$ACR_SERVER/portal-backend:latest" \
  --docker-registry-server-url "https://$ACR_SERVER" \
  --docker-registry-server-user "$ACR_USER" \
  --docker-registry-server-password "$ACR_PASS" \
  --output none

# ── Mirror ecran's security & runtime settings ──────────────────────────────
az webapp config set \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --min-tls-version "1.2" \
  --ftps-state "FtpsOnly" \
  --http20-enabled true \
  --output none

az webapp update \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --https-only true \
  --output none

# ── App Settings (environment variables) ────────────────────────────────────
BACKEND_URL="https://${BACKEND_APP}.azurewebsites.net"

az webapp config appsettings set \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    DATABRICKS_HOST="$DATABRICKS_HOST" \
    DATABRICKS_TOKEN="$DATABRICKS_TOKEN" \
    DATABRICKS_WAREHOUSE_ID="$DATABRICKS_WAREHOUSE_ID" \
    ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    CONF_DIR="/data/bronze_conf" \
    SILVER_CONF_DIR="/data/silver_conf" \
    CHROMADB_PERSIST_DIR="/data/chromadb" \
    TENANT_DB_PATH="/data/app/tenants.db" \
    HF_HOME="/data/model_cache" \
    TRANSFORMERS_CACHE="/data/model_cache" \
    GIT_ENABLED="false" \
    SECRET_KEY="$SECRET_KEY" \
    AZURE_STORAGE_CONNECTION_STRING="$STORAGE_CONN_STR" \
    WEBSITE_HTTPLOGGING_RETENTION_DAYS="3" \
    WEBSITES_PORT="8000" \
  --output none

# ── Mount Azure File Shares as volumes ──────────────────────────────────────
echo "   Mounting file shares..."

az webapp config storage-account add \
  --name "$BACKEND_APP" --resource-group "$RESOURCE_GROUP" \
  --custom-id "portal-bronze-conf" --storage-type AzureFiles \
  --account-name "$STORAGE_ACCOUNT" --share-name "portal-bronze-conf" \
  --access-key "$STORAGE_KEY" --mount-path "/data/bronze_conf" --output none

az webapp config storage-account add \
  --name "$BACKEND_APP" --resource-group "$RESOURCE_GROUP" \
  --custom-id "portal-silver-conf" --storage-type AzureFiles \
  --account-name "$STORAGE_ACCOUNT" --share-name "portal-silver-conf" \
  --access-key "$STORAGE_KEY" --mount-path "/data/silver_conf" --output none

az webapp config storage-account add \
  --name "$BACKEND_APP" --resource-group "$RESOURCE_GROUP" \
  --custom-id "portal-chromadb" --storage-type AzureFiles \
  --account-name "$STORAGE_ACCOUNT" --share-name "portal-chromadb" \
  --access-key "$STORAGE_KEY" --mount-path "/data/chromadb" --output none

az webapp config storage-account add \
  --name "$BACKEND_APP" --resource-group "$RESOURCE_GROUP" \
  --custom-id "portal-model-cache" --storage-type AzureFiles \
  --account-name "$STORAGE_ACCOUNT" --share-name "portal-model-cache" \
  --access-key "$STORAGE_KEY" --mount-path "/data/model_cache" --output none

az webapp config storage-account add \
  --name "$BACKEND_APP" --resource-group "$RESOURCE_GROUP" \
  --custom-id "portal-app-data" --storage-type AzureFiles \
  --account-name "$STORAGE_ACCOUNT" --share-name "portal-app-data" \
  --access-key "$STORAGE_KEY" --mount-path "/data/app" --output none

echo "   Backend URL: $BACKEND_URL"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Build & Push Frontend Image (backend URL baked in at build time)
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 5/6 — Build & Push Frontend Image"
BACKEND_API_URL="${BACKEND_URL}/api/v1"
echo "   Baking backend URL into client bundle: $BACKEND_API_URL"

docker build \
  -f portal/frontend/Dockerfile \
  --build-arg "NEXT_PUBLIC_API_URL=${BACKEND_API_URL}" \
  -t "$ACR_SERVER/portal-frontend:latest" \
  .
docker push "$ACR_SERVER/portal-frontend:latest"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Frontend Web App for Containers
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 6/6 — Frontend App Service ($FRONTEND_APP)"

az webapp create \
  --name "$FRONTEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --plan "$PLAN_NAME" \
  --deployment-container-image-name "$ACR_SERVER/portal-frontend:latest" \
  --output table

az webapp config container set \
  --name "$FRONTEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --docker-custom-image-name "$ACR_SERVER/portal-frontend:latest" \
  --docker-registry-server-url "https://$ACR_SERVER" \
  --docker-registry-server-user "$ACR_USER" \
  --docker-registry-server-password "$ACR_PASS" \
  --output none

# Mirror ecran's security & runtime settings
az webapp config set \
  --name "$FRONTEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --min-tls-version "1.2" \
  --ftps-state "FtpsOnly" \
  --http20-enabled true \
  --output none

az webapp update \
  --name "$FRONTEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --https-only true \
  --output none

FRONTEND_URL="https://${FRONTEND_APP}.azurewebsites.net"

az webapp config appsettings set \
  --name "$FRONTEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    NODE_ENV="production" \
    SECRET_KEY="$SECRET_KEY" \
    AZURE_STORAGE_CONNECTION_STRING="$STORAGE_CONN_STR" \
    WEBSITE_HTTPLOGGING_RETENTION_DAYS="3" \
    WEBSITES_PORT="3000" \
  --output none

# ── Update backend CORS to allow the frontend origin ────────────────────────
# NOTE: If CORS is hardcoded in portal/backend/app/main.py (not env-driven),
# update the allowed origins there and redeploy the backend image.
echo ""
echo "   Updating backend CORS_ORIGINS..."
az webapp config appsettings set \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --settings CORS_ORIGINS="[\"${FRONTEND_URL}\",\"${BACKEND_URL}\"]" \
  --output none

# ══════════════════════════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Deployment complete!"
echo ""
echo "  Frontend:  $FRONTEND_URL"
echo "  Backend:   $BACKEND_URL"
echo "  Health:    ${BACKEND_URL}/api/v1/health"
echo ""
echo "  First startup may take 3-5 minutes (model download + cold start)."
echo "  Monitor logs:"
echo "    az webapp log tail --name $BACKEND_APP --resource-group $RESOURCE_GROUP"
echo "    az webapp log tail --name $FRONTEND_APP --resource-group $RESOURCE_GROUP"
echo "════════════════════════════════════════════════════════"
