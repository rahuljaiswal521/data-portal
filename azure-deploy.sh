#!/usr/bin/env bash
# portal/azure-deploy.sh
# Deploys the Data Portal (FastAPI backend + Next.js frontend) to Azure Container Apps.
#
# Prerequisites:
#   - Azure CLI installed and logged in  (az login)
#     Install: winget install -e --id Microsoft.AzureCLI
#   - NO Docker Desktop required — images are built in Azure via "az acr build"
#   - Run from the Demo/ root directory:  bash portal/azure-deploy.sh
#
# What this script creates:
#   Resource Group → Container Registry → Storage Account (+ 5 File Shares) →
#   Log Analytics → Container Apps Environment → Backend App → Frontend App
#
# Time estimate: ~15 minutes on first run.

set -euo pipefail

# ══════════════════════════════════════════════════════════════════════════════
# USER CONFIGURATION — edit these before running
# ══════════════════════════════════════════════════════════════════════════════

RESOURCE_GROUP="data-portal-rg"
LOCATION="australiaeast"              # Change to your preferred region

# Must be globally unique, lowercase alphanumeric only (no hyphens for storage/acr)
ACR_NAME="dataportalacr"             # Azure Container Registry
STORAGE_ACCOUNT="dataportalsa"       # Azure Storage Account

# Container Apps
CAE_NAME="data-portal-env"           # Container Apps Environment
BACKEND_APP="data-portal-backend"
FRONTEND_APP="data-portal-frontend"

# Secrets — exported from your shell or sourced from a local .env (NEVER commit real values)
# Example: source backend/.env && export DATABRICKS_HOST DATABRICKS_TOKEN DATABRICKS_WAREHOUSE_ID ANTHROPIC_API_KEY
DATABRICKS_HOST="${DATABRICKS_HOST:-}"
DATABRICKS_TOKEN="${DATABRICKS_TOKEN:-}"
DATABRICKS_WAREHOUSE_ID="${DATABRICKS_WAREHOUSE_ID:-}"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"

# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

if [[ -z "$DATABRICKS_TOKEN" || -z "$ANTHROPIC_API_KEY" ]]; then
  echo "ERROR: Fill in DATABRICKS_TOKEN and ANTHROPIC_API_KEY at the top of this script."
  exit 1
fi

# Must run from Demo/ root so Docker build context is correct
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"
echo "Working directory: $(pwd)"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Resource Group
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 1/9 — Resource Group"
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output table

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Azure Container Registry
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 2/9 — Container Registry"
az acr create \
  --name "$ACR_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --sku Basic \
  --admin-enabled true \
  --output table

ACR_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USER=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASS=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

echo "   ACR: $ACR_SERVER"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Build & Push Backend Image
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 3/9 — Build & Push Backend Image (local Docker build)"
echo "   First build takes ~15 min (PyTorch + sentence-transformers are large)."

# Login to ACR so docker push works
az acr login --name "$ACR_NAME"

# Build from Demo/ root — Dockerfile uses paths relative to this context
docker build \
  -f portal/backend/Dockerfile \
  -t "$ACR_SERVER/portal-backend:latest" \
  .
docker push "$ACR_SERVER/portal-backend:latest"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Storage Account & File Shares
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 4/9 — Storage Account & File Shares"
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --output table

STORAGE_KEY=$(az storage account keys list \
  --account-name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[0].value" -o tsv)

# Create the five file shares the backend needs
for SHARE in bronze-conf silver-conf chromadb model-cache app-data; do
  echo "   Creating share: $SHARE"
  az storage share create \
    --name "$SHARE" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --quota 10 \
    --output none
done

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Upload Existing Config Files to File Shares
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 5/9 — Upload Conf Files to Azure File Shares"

# Upload bronze_framework/conf → bronze-conf share
# This includes sources/*.yaml and environments/*.yaml
if [[ -d "bronze_framework/conf" ]]; then
  az storage file upload-batch \
    --source "bronze_framework/conf" \
    --destination "bronze-conf" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --output none
  echo "   Uploaded bronze_framework/conf"
else
  echo "   WARN: bronze_framework/conf not found — share will be empty"
fi

# Upload silver_framework/conf → silver-conf share
if [[ -d "silver_framework/conf" ]]; then
  az storage file upload-batch \
    --source "silver_framework/conf" \
    --destination "silver-conf" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --output none
  echo "   Uploaded silver_framework/conf"
else
  echo "   WARN: silver_framework/conf not found — share will be empty"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Log Analytics (required by Container Apps)
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 6/9 — Log Analytics Workspace"
az monitor log-analytics workspace create \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "data-portal-logs" \
  --location "$LOCATION" \
  --output table

LOG_WS_ID=$(az monitor log-analytics workspace show \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "data-portal-logs" \
  --query customerId -o tsv)

LOG_WS_KEY=$(az monitor log-analytics workspace get-shared-keys \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "data-portal-logs" \
  --query primarySharedKey -o tsv)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — Container Apps Environment + Storage Mounts
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 7/9 — Container Apps Environment"
az containerapp env create \
  --name "$CAE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --logs-workspace-id "$LOG_WS_ID" \
  --logs-workspace-key "$LOG_WS_KEY" \
  --output table

# Attach each file share to the environment so Container Apps can mount them
echo "   Attaching file shares to environment..."
for SHARE in bronze-conf silver-conf chromadb model-cache app-data; do
  az containerapp env storage set \
    --name "$CAE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --storage-name "$SHARE" \
    --azure-file-account-name "$STORAGE_ACCOUNT" \
    --azure-file-account-key "$STORAGE_KEY" \
    --azure-file-share-name "$SHARE" \
    --access-mode ReadWrite \
    --output none
  echo "   Attached: $SHARE"
done

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — Deploy Backend Container App
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 8/9 — Deploy Backend Container App"

# Generate a container app YAML spec with volume mounts
# Use az rest (ARM PUT) — az containerapp create --yaml has known serialisation bugs
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
CAE_ID=$(az containerapp env show \
  --name "$CAE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query id -o tsv)

az rest \
  --method PUT \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.App/containerApps/${BACKEND_APP}?api-version=2024-03-01" \
  --body "{
    \"location\": \"${LOCATION}\",
    \"properties\": {
      \"managedEnvironmentId\": \"${CAE_ID}\",
      \"configuration\": {
        \"ingress\": {\"external\": true, \"targetPort\": 8000},
        \"registries\": [{\"server\": \"${ACR_SERVER}\", \"username\": \"${ACR_USER}\", \"passwordSecretRef\": \"acr-password\"}],
        \"secrets\": [
          {\"name\": \"acr-password\",     \"value\": \"${ACR_PASS}\"},
          {\"name\": \"databricks-token\", \"value\": \"${DATABRICKS_TOKEN}\"},
          {\"name\": \"anthropic-key\",    \"value\": \"${ANTHROPIC_API_KEY}\"}
        ]
      },
      \"template\": {
        \"volumes\": [
          {\"name\": \"bronze-conf\", \"storageType\": \"AzureFile\", \"storageName\": \"bronze-conf\"},
          {\"name\": \"silver-conf\", \"storageType\": \"AzureFile\", \"storageName\": \"silver-conf\"},
          {\"name\": \"chromadb\",    \"storageType\": \"AzureFile\", \"storageName\": \"chromadb\"},
          {\"name\": \"model-cache\", \"storageType\": \"AzureFile\", \"storageName\": \"model-cache\"},
          {\"name\": \"app-data\",    \"storageType\": \"AzureFile\", \"storageName\": \"app-data\"}
        ],
        \"containers\": [{
          \"name\": \"backend\",
          \"image\": \"${ACR_SERVER}/portal-backend:latest\",
          \"resources\": {\"cpu\": 1.0, \"memory\": \"2Gi\"},
          \"env\": [
            {\"name\": \"DATABRICKS_HOST\",        \"value\": \"${DATABRICKS_HOST}\"},
            {\"name\": \"DATABRICKS_TOKEN\",        \"secretRef\": \"databricks-token\"},
            {\"name\": \"DATABRICKS_WAREHOUSE_ID\", \"value\": \"${DATABRICKS_WAREHOUSE_ID}\"},
            {\"name\": \"ANTHROPIC_API_KEY\",       \"secretRef\": \"anthropic-key\"},
            {\"name\": \"CONF_DIR\",                \"value\": \"/data/bronze_conf\"},
            {\"name\": \"SILVER_CONF_DIR\",         \"value\": \"/data/silver_conf\"},
            {\"name\": \"CHROMADB_PERSIST_DIR\",    \"value\": \"/data/chromadb\"},
            {\"name\": \"TENANT_DB_PATH\",          \"value\": \"/data/app/tenants.db\"},
            {\"name\": \"GIT_ENABLED\",             \"value\": \"false\"},
            {\"name\": \"HF_HOME\",                 \"value\": \"/data/model_cache\"},
            {\"name\": \"TRANSFORMERS_CACHE\",      \"value\": \"/data/model_cache\"}
          ],
          \"volumeMounts\": [
            {\"volumeName\": \"bronze-conf\", \"mountPath\": \"/data/bronze_conf\"},
            {\"volumeName\": \"silver-conf\",  \"mountPath\": \"/data/silver_conf\"},
            {\"volumeName\": \"chromadb\",     \"mountPath\": \"/data/chromadb\"},
            {\"volumeName\": \"model-cache\",  \"mountPath\": \"/data/model_cache\"},
            {\"volumeName\": \"app-data\",     \"mountPath\": \"/data/app\"}
          ]
        }],
        \"scale\": {\"minReplicas\": 1, \"maxReplicas\": 1}
      }
    }
  }" --output none

# Poll until provisioned
echo "   Waiting for backend to provision..."
while true; do
  STATE=$(az containerapp show --name "$BACKEND_APP" --resource-group "$RESOURCE_GROUP" --query "properties.provisioningState" -o tsv 2>/dev/null)
  [[ "$STATE" == "Succeeded" ]] && break
  echo "   ... $STATE"
  sleep 10
done

# Get the backend's public URL
BACKEND_URL=$(az containerapp show \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

BACKEND_API_URL="https://${BACKEND_URL}/api/v1"
echo "   Backend URL: https://${BACKEND_URL}"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 9 — Build & Push Frontend Image (needs BACKEND_API_URL), then Deploy
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "▶  Step 9/9 — Build Frontend Image (cloud build), then Deploy"
echo "   Baking backend URL into client bundle: ${BACKEND_API_URL}"

# Build from Demo/ root — Dockerfile uses paths relative to this context
echo "   Building frontend with backend URL baked in: ${BACKEND_API_URL}"
docker build \
  -f portal/frontend/Dockerfile \
  --build-arg "NEXT_PUBLIC_API_URL=${BACKEND_API_URL}" \
  -t "$ACR_SERVER/portal-frontend:latest" \
  .
docker push "$ACR_SERVER/portal-frontend:latest"

az rest \
  --method PUT \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.App/containerApps/${FRONTEND_APP}?api-version=2024-03-01" \
  --body "{
    \"location\": \"${LOCATION}\",
    \"properties\": {
      \"managedEnvironmentId\": \"${CAE_ID}\",
      \"configuration\": {
        \"ingress\": {\"external\": true, \"targetPort\": 3000},
        \"registries\": [{\"server\": \"${ACR_SERVER}\", \"username\": \"${ACR_USER}\", \"passwordSecretRef\": \"acr-password\"}],
        \"secrets\": [{\"name\": \"acr-password\", \"value\": \"${ACR_PASS}\"}]
      },
      \"template\": {
        \"containers\": [{
          \"name\": \"frontend\",
          \"image\": \"${ACR_SERVER}/portal-frontend:latest\",
          \"resources\": {\"cpu\": 0.5, \"memory\": \"1Gi\"}
        }],
        \"scale\": {\"minReplicas\": 1, \"maxReplicas\": 1}
      }
    }
  }" --output none

echo "   Waiting for frontend to provision..."
while true; do
  STATE=$(az containerapp show --name "$FRONTEND_APP" --resource-group "$RESOURCE_GROUP" --query "properties.provisioningState" -o tsv 2>/dev/null)
  [[ "$STATE" == "Succeeded" ]] && break
  echo "   ... $STATE"
  sleep 10
done

FRONTEND_URL=$(az containerapp show \
  --name "$FRONTEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

# Update backend CORS to include the real frontend URL
echo ""
echo "   Updating backend CORS to allow frontend..."
az containerapp update \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars "CORS_ORIGINS=[\"https://${FRONTEND_URL}\",\"https://${BACKEND_URL}\"]" \
  --output none

# ══════════════════════════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Deployment complete!"
echo ""
echo "  Frontend:  https://${FRONTEND_URL}"
echo "  Backend:   https://${BACKEND_URL}"
echo "  Health:    https://${BACKEND_URL}/api/v1/health"
echo ""
echo "  First startup may take 2-3 minutes (model download)."
echo "  Monitor logs:"
echo "    az containerapp logs show -n $BACKEND_APP -g $RESOURCE_GROUP --follow"
echo "════════════════════════════════════════════════════════"
