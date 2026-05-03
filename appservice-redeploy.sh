#!/usr/bin/env bash
# portal/appservice-redeploy.sh
# Rebuild and redeploy changed services to Azure App Service (ecran-rg).
# Run from Demo/ root:  bash portal/appservice-redeploy.sh [backend|frontend|both]
#
# Examples:
#   bash portal/appservice-redeploy.sh frontend   # only frontend changed
#   bash portal/appservice-redeploy.sh backend    # only backend changed
#   bash portal/appservice-redeploy.sh both       # redeploy everything (default)

set -euo pipefail

TARGET="${1:-both}"

ACR_NAME="ecrandataportal"
ACR_SERVER="ecrandataportal.azurecr.io"
RESOURCE_GROUP="ecran-rg"
BACKEND_APP="ecran-data-platform"
FRONTEND_APP="ecran-data-platform-ui"
BACKEND_API_URL="https://ecran-data-platform.azurewebsites.net/api/v1"

az acr login --name "$ACR_NAME"

if [[ "$TARGET" == "backend" || "$TARGET" == "both" ]]; then
  echo ""
  echo "▶  Rebuilding backend..."
  docker build \
    -f portal/backend/Dockerfile \
    -t "$ACR_SERVER/portal-backend:latest" \
    .
  docker push "$ACR_SERVER/portal-backend:latest"

  echo "   Updating backend App Service..."
  az webapp config container set \
    --name "$BACKEND_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --docker-custom-image-name "$ACR_SERVER/portal-backend:latest" \
    --output none

  az webapp restart \
    --name "$BACKEND_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --output none

  echo "✔  Backend redeployed."
fi

if [[ "$TARGET" == "frontend" || "$TARGET" == "both" ]]; then
  echo ""
  echo "▶  Rebuilding frontend (baking API URL: $BACKEND_API_URL)..."
  docker build \
    -f portal/frontend/Dockerfile \
    --build-arg "NEXT_PUBLIC_API_URL=${BACKEND_API_URL}" \
    -t "$ACR_SERVER/portal-frontend:latest" \
    .
  docker push "$ACR_SERVER/portal-frontend:latest"

  echo "   Updating frontend App Service..."
  az webapp config container set \
    --name "$FRONTEND_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --docker-custom-image-name "$ACR_SERVER/portal-frontend:latest" \
    --output none

  az webapp restart \
    --name "$FRONTEND_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --output none

  echo "✔  Frontend redeployed."
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Redeploy complete!"
echo ""
echo "  Frontend:  https://${FRONTEND_APP}.azurewebsites.net"
echo "  Backend:   https://${BACKEND_APP}.azurewebsites.net"
echo "  Health:    ${BACKEND_API_URL}/health"
echo ""
echo "  First startup may take 2-3 minutes (cold start)."
echo "  Monitor logs:"
echo "    az webapp log tail --name $BACKEND_APP --resource-group $RESOURCE_GROUP"
echo "    az webapp log tail --name $FRONTEND_APP --resource-group $RESOURCE_GROUP"
echo "════════════════════════════════════════════════════════"
