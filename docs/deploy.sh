#!/usr/bin/env bash
# Build and deploy the Data Platform Portal user guide to Azure Static Web Apps.
#
# Usage (from anywhere):
#   ./portal/docs/deploy.sh
#
# Prereqs (one-time):
#   - Python 3.x on PATH with `mkdocs-material` installed (pip install mkdocs-material)
#   - Node.js on PATH (provides `npx`)
#   - Azure CLI on PATH and logged in (`az login`)

set -euo pipefail

SWA_NAME="ecran-data-portal-docs"
RESOURCE_GROUP="ecran-rg"
LIVE_URL="https://kind-mushroom-0e9610c00.6.azurestaticapps.net"

# Anchor paths to this script's directory
DOCS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORTAL_DIR="$(dirname "$DOCS_DIR")"
SITE_DIR="$DOCS_DIR/site"
CONFIG_FILE="$DOCS_DIR/mkdocs.yml"

echo "==> Building docs (mkdocs build --clean)"
( cd "$PORTAL_DIR" && python -m mkdocs build --config-file "$CONFIG_FILE" --clean )

echo "==> Fetching SWA deployment token"
TOKEN=$(az staticwebapp secrets list \
    --name "$SWA_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.apiKey" -o tsv)

if [[ -z "${TOKEN:-}" ]]; then
    echo "ERROR: Could not fetch SWA token. Are you logged into az and is RG '$RESOURCE_GROUP' correct?" >&2
    exit 1
fi

echo "==> Deploying $SITE_DIR to Azure SWA"
( cd "$DOCS_DIR" && npx --yes @azure/static-web-apps-cli deploy ./site \
    --deployment-token "$TOKEN" \
    --env production \
    --no-use-keychain )

echo
echo "Done. Live at: $LIVE_URL"
