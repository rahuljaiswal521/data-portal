# Build and deploy the Data Platform Portal user guide to Azure Static Web Apps.
#
# Usage (from anywhere):
#   .\portal\docs\deploy.ps1
#
# What it does:
#   1. Runs `mkdocs build --clean` -> portal/docs/site/
#   2. Fetches the SWA deployment token from Azure
#   3. Deploys site/ to https://kind-mushroom-0e9610c00.6.azurestaticapps.net
#
# Prereqs (one-time):
#   - Python 3.x on PATH with `mkdocs-material` installed (`pip install mkdocs-material`)
#   - Node.js on PATH (provides `npx`)
#   - Azure CLI on PATH and logged in (`az login`)

$ErrorActionPreference = "Stop"

$SwaName    = "ecran-data-portal-docs"
$ResourceGp = "ecran-rg"
$LiveUrl    = "https://kind-mushroom-0e9610c00.6.azurestaticapps.net"

# Anchor paths to this script's location so it works no matter where it's invoked from
$DocsDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$PortalDir  = Split-Path -Parent $DocsDir
$SiteDir    = Join-Path $DocsDir "site"
$ConfigFile = Join-Path $DocsDir "mkdocs.yml"

Write-Host "==> Building docs (mkdocs build --clean)" -ForegroundColor Cyan
Push-Location $PortalDir
try {
    python -m mkdocs build --config-file $ConfigFile --clean
    if ($LASTEXITCODE -ne 0) { throw "mkdocs build failed" }
} finally {
    Pop-Location
}

Write-Host "==> Fetching SWA deployment token" -ForegroundColor Cyan
$Token = az staticwebapp secrets list `
    --name $SwaName `
    --resource-group $ResourceGp `
    --query "properties.apiKey" -o tsv
if ([string]::IsNullOrWhiteSpace($Token)) {
    throw "Could not fetch SWA token. Are you logged into az and is RG '$ResourceGp' correct?"
}

Write-Host "==> Deploying $SiteDir to Azure SWA" -ForegroundColor Cyan
Push-Location $DocsDir
try {
    npx --yes "@azure/static-web-apps-cli" deploy ./site `
        --deployment-token $Token `
        --env production `
        --no-use-keychain
    if ($LASTEXITCODE -ne 0) { throw "swa deploy failed" }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Done. Live at: $LiveUrl" -ForegroundColor Green
