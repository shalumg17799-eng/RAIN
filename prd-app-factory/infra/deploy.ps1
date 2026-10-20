# Deploy the PRD-to-App Factory (portal + five agent jobs) to Azure. Run from the prd-app-factory folder.
# Requires the Azure CLI signed in (az login) and:
#   AZURE_SUBSCRIPTION_ID, AZURE_LOCATION, AZURE_RESOURCE_GROUP, AZURE_ACR_NAME (letters/digits, globally unique),
#   PG_ADMIN_PASSWORD, ANTHROPIC_API_KEY.  Optional portal sign-in: ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET.
$ErrorActionPreference = 'Stop'
foreach ($v in 'AZURE_SUBSCRIPTION_ID', 'AZURE_LOCATION', 'AZURE_RESOURCE_GROUP', 'AZURE_ACR_NAME', 'PG_ADMIN_PASSWORD', 'ANTHROPIC_API_KEY') {
    if (-not [Environment]::GetEnvironmentVariable($v)) { throw "Set $v first" }
}
$rg = $env:AZURE_RESOURCE_GROUP; $acr = $env:AZURE_ACR_NAME; $tag = Get-Date -Format 'yyyyMMddHHmm'
az account set --subscription $env:AZURE_SUBSCRIPTION_ID
az group create --name $rg --location $env:AZURE_LOCATION --output none
if (-not (az acr show --name $acr --resource-group $rg --query name --output tsv 2>$null)) {
    az acr create --name $acr --resource-group $rg --sku Basic --output none
}
# Cloud builds: no local Docker needed.
az acr build --registry $acr --image "prd-factory:$tag" --file infra/Dockerfile .
az acr build --registry $acr --image "prd-factory-release:$tag" --file infra/Dockerfile.release .

$out = az deployment group create --resource-group $rg --template-file infra/main.bicep `
    --parameters acrName=$acr image="$acr.azurecr.io/prd-factory:$tag" releaseImage="$acr.azurecr.io/prd-factory-release:$tag" `
                 pgAdminPassword=$env:PG_ADMIN_PASSWORD anthropicApiKey=$env:ANTHROPIC_API_KEY `
                 entraClientId=$env:ENTRA_CLIENT_ID entraClientSecret=$env:ENTRA_CLIENT_SECRET `
    --query properties.outputs --output json | ConvertFrom-Json
Write-Host "Factory portal: $($out.portalUrl.value)"
