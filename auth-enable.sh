#!/usr/bin/env bash
# Enable Microsoft login on the portal frontend.
# Run from Demo/ root:  bash portal/auth-enable.sh
#
# Requires: az login (already done if you've deployed)
# After running: share the portal URL — team members will be prompted to sign in.

set -euo pipefail

RESOURCE_GROUP="data-portal-rg"
SUBSCRIPTION_ID="28e153c2-0b56-43a1-96a5-7e3c35ed050d"
APP_ID="70851a6e-0f2f-4443-904f-bdf9f4875914"        # Azure AD app registration
TENANT_ID="12052350-e210-4041-b7e5-353ed54a6a5e"

# NOTE: If the client secret has expired (it lasts 2 years from March 2026),
# regenerate it with:
#   az ad app credential reset --id $APP_ID --display-name "container-apps-auth" --years 2
# Then export it before running this script:  export AAD_CLIENT_SECRET="<new-secret>"
CLIENT_SECRET="${AAD_CLIENT_SECRET:-}"

if [[ -z "$CLIENT_SECRET" ]]; then
  echo "ERROR: AAD_CLIENT_SECRET not set. Export it before running this script."
  exit 1
fi

echo "▶  Enabling Microsoft login on data-portal-frontend..."

az containerapp auth microsoft update \
  --name data-portal-frontend \
  --resource-group "$RESOURCE_GROUP" \
  --client-id "$APP_ID" \
  --client-secret "$CLIENT_SECRET" \
  --tenant-id "$TENANT_ID" \
  --yes \
  --output none

az rest \
  --method PUT \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.App/containerApps/data-portal-frontend/authConfigs/current?api-version=2024-03-01" \
  --body "{
    \"properties\": {
      \"platform\": {\"enabled\": true},
      \"globalValidation\": {
        \"unauthenticatedClientAction\": \"RedirectToLoginPage\",
        \"redirectToProvider\": \"azureActiveDirectory\"
      },
      \"identityProviders\": {
        \"azureActiveDirectory\": {
          \"registration\": {
            \"clientId\": \"${APP_ID}\",
            \"clientSecretSettingName\": \"microsoft-provider-authentication-secret\",
            \"openIdIssuer\": \"https://login.microsoftonline.com/common/v2.0\"
          },
          \"validation\": {
            \"allowedAudiences\": [\"${APP_ID}\"],
            \"defaultAuthorizationPolicy\": {\"allowedPrincipals\": {}}
          }
        }
      },
      \"login\": {\"preserveUrlFragmentsForLogins\": true}
    }
  }" --output none

az containerapp update \
  --name data-portal-frontend \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars "AUTH_ENABLED=true" \
  --output none

echo ""
echo "✔  Auth enabled. Portal now requires Microsoft login."
echo "   To invite a team member:"
echo "   az ad invitation create \\"
echo "     --invited-user-email teammate@example.com \\"
echo "     --invite-redirect-url https://data-portal-frontend.redgrass-d95a9251.australiaeast.azurecontainerapps.io"
