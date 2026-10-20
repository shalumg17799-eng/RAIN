#!/usr/bin/env bash
# Deploy the generated app "__APP_ID__" to Azure Container Apps (bash; used by the release agent's
# job on Azure, where it signs in with its managed identity). Run from the prd-app-factory folder.
# Requires: AZURE_SUBSCRIPTION_ID, AZURE_LOCATION, AZURE_RESOURCE_GROUP, AZURE_ACR_NAME,
#           PG_ADMIN_PASSWORD, ANTHROPIC_API_KEY. Optional: ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET.
set -euo pipefail
for v in AZURE_SUBSCRIPTION_ID AZURE_LOCATION AZURE_RESOURCE_GROUP AZURE_ACR_NAME PG_ADMIN_PASSWORD ANTHROPIC_API_KEY; do
  [ -n "${!v:-}" ] || { echo "Set $v first" >&2; exit 2; }
done
if ! az account show >/dev/null 2>&1; then
  az login --identity ${AZURE_CLIENT_ID:+--username "$AZURE_CLIENT_ID"} --output none
fi
rg="$AZURE_RESOURCE_GROUP"; acr="$AZURE_ACR_NAME"; tag="$(date +%Y%m%d%H%M)"
image="$acr.azurecr.io/factory-__APP_DASH__:$tag"
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az group create --name "$rg" --location "$AZURE_LOCATION" --output none
az acr show --name "$acr" --resource-group "$rg" --output none 2>/dev/null || az acr create --name "$acr" --resource-group "$rg" --sku Basic --output none
az acr build --registry "$acr" --image "factory-__APP_DASH__:$tag" --file "apppacks/__APP_ID__/deploy/Dockerfile" .
out=$(az deployment group create --resource-group "$rg" \
  --template-file "apppacks/__APP_ID__/deploy/main.bicep" \
  --parameters image="$image" acrName="$acr" pgAdminPassword="$PG_ADMIN_PASSWORD" anthropicApiKey="$ANTHROPIC_API_KEY" \
               entraClientId="${ENTRA_CLIENT_ID:-}" entraClientSecret="${ENTRA_CLIENT_SECRET:-}" \
  --query properties.outputs --output json)
job=$(echo "$out" | python3 -c "import json,sys; print(json.load(sys.stdin)['provisionJob']['value'])")
url=$(echo "$out" | python3 -c "import json,sys; print(json.load(sys.stdin)['url']['value'])")
az containerapp job start --name "$job" --resource-group "$rg" --output none
echo "Provisioning job started: $job"
echo "App URL: $url"
