#!/usr/bin/env bash
# portal/redeploy.sh
# Rebuild and redeploy changed services to Azure Container Apps.
# Run from Demo/ root:  bash portal/redeploy.sh [backend|frontend|both]
#
# Examples:
#   bash portal/redeploy.sh backend    # only backend changed
#   bash portal/redeploy.sh frontend   # only frontend changed
#   bash portal/redeploy.sh both       # redeploy everything (default)

set -euo pipefail
export MSYS_NO_PATHCONV=1   # prevent Git Bash from converting /paths to C:/Program Files/Git/paths

TARGET="${1:-both}"

ACR="dataportalacr.azurecr.io"
RESOURCE_GROUP="data-portal-rg"
BACKEND_APP="data-portal-backend"
FRONTEND_APP="data-portal-frontend"
BACKEND_URL="https://data-portal-backend.redgrass-d95a9251.australiaeast.azurecontainerapps.io/api/v1"

# Unique tag per build — ensures Azure always pulls the new image
TAG=$(date +%Y%m%d-%H%M%S)

az acr login --name dataportalacr

if [[ "$TARGET" == "backend" || "$TARGET" == "both" ]]; then
  echo "▶  Rebuilding backend (tag: $TAG)..."
  docker build -f portal/backend/Dockerfile -t "$ACR/portal-backend:$TAG" -t "$ACR/portal-backend:latest" .
  docker push "$ACR/portal-backend:$TAG"
  docker push "$ACR/portal-backend:latest"
  az containerapp update \
    --name "$BACKEND_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR/portal-backend:$TAG" \
    --output none
  echo "✔  Backend redeployed ($TAG)."
fi

if [[ "$TARGET" == "frontend" || "$TARGET" == "both" ]]; then
  echo "▶  Rebuilding frontend (tag: $TAG)..."
  docker build \
    -f portal/frontend/Dockerfile \
    --build-arg "NEXT_PUBLIC_API_URL=${BACKEND_URL}" \
    -t "$ACR/portal-frontend:$TAG" \
    -t "$ACR/portal-frontend:latest" \
    .
  docker push "$ACR/portal-frontend:$TAG"
  docker push "$ACR/portal-frontend:latest"
  az containerapp update \
    --name "$FRONTEND_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR/portal-frontend:$TAG" \
    --output none
  echo "✔  Frontend redeployed ($TAG)."
fi

echo ""
echo "Done. Remember to re-enable ingress if the portal is currently offline:"
echo "  bash portal/auth-enable.sh   (if you also want auth)"
echo "  az containerapp ingress enable --name data-portal-frontend --resource-group $RESOURCE_GROUP --type external --target-port 3000 --output none"
echo "  az containerapp ingress enable --name data-portal-backend  --resource-group $RESOURCE_GROUP --type external --target-port 8000 --output none"
