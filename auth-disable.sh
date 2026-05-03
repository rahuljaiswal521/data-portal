#!/usr/bin/env bash
# Disable Microsoft login on the portal frontend (portal becomes open to anyone with the URL).
# Run from Demo/ root:  bash portal/auth-disable.sh

set -euo pipefail

RESOURCE_GROUP="data-portal-rg"
SUBSCRIPTION_ID="28e153c2-0b56-43a1-96a5-7e3c35ed050d"

echo "▶  Disabling auth on data-portal-frontend..."

az rest \
  --method PUT \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.App/containerApps/data-portal-frontend/authConfigs/current?api-version=2024-03-01" \
  --body "{\"properties\": {\"platform\": {\"enabled\": false}}}" \
  --output none

az containerapp update \
  --name data-portal-frontend \
  --resource-group "$RESOURCE_GROUP" \
  --remove-env-vars AUTH_ENABLED \
  --output none

echo ""
echo "✔  Auth disabled. Portal is now open (URL-only access)."
echo "   To re-enable:  bash portal/auth-enable.sh"
