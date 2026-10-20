# Deploy the generated app "__APP_ID__" to Azure Container Apps. Run from the prd-app-factory folder.
# Requires: Azure CLI signed in (az login) and these environment variables:
#   AZURE_SUBSCRIPTION_ID, AZURE_LOCATION, AZURE_RESOURCE_GROUP,
#   AZURE_ACR_NAME (globally unique, letters and digits), PG_ADMIN_PASSWORD, ANTHROPIC_API_KEY
# Optional sign-in: ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET (and fill apppacks/__APP_ID__/access.yaml).
$ErrorActionPreference = 'Stop'
foreach ($v in 'AZURE_SUBSCRIPTION_ID', 'AZURE_LOCATION', 'AZURE_RESOURCE_GROUP', 'AZURE_ACR_NAME', 'PG_ADMIN_PASSWORD', 'ANTHROPIC_API_KEY') {
    if (-not [Environment]::GetEnvironmentVariable($v)) { throw "Set $v first" }
}
$rg = $env:AZURE_RESOURCE_GROUP
$acr = $env:AZURE_ACR_NAME
$tag = Get-Date -Format 'yyyyMMddHHmm'
$image = "$acr.azurecr.io/factory-__APP_DASH__:$tag"

az account set --subscription $env:AZURE_SUBSCRIPTION_ID
az group create --name $rg --location $env:AZURE_LOCATION --output none
if (-not (az acr show --name $acr --resource-group $rg --query name --output tsv 2>$null)) {
    az acr create --name $acr --resource-group $rg --sku Basic --output none
}
# Cloud build: no local Docker needed.
az acr build --registry $acr --image "factory-__APP_DASH__:$tag" --file "apppacks/__APP_ID__/deploy/Dockerfile" .

$out = az deployment group create --resource-group $rg `
    --template-file "apppacks/__APP_ID__/deploy/main.bicep" `
    --parameters image=$image acrName=$acr pgAdminPassword=$env:PG_ADMIN_PASSWORD anthropicApiKey=$env:ANTHROPIC_API_KEY `
                 entraClientId=$env:ENTRA_CLIENT_ID entraClientSecret=$env:ENTRA_CLIENT_SECRET `
    --query properties.outputs --output json | ConvertFrom-Json

az containerapp job start --name $out.provisionJob.value --resource-group $rg --output none
Write-Host "Provisioning job started: $($out.provisionJob.value)"
Write-Host "App URL: $($out.url.value)"
