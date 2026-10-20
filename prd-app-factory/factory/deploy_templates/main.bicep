// Runtime plane for the generated app "__APP_ID__" on Azure Container Apps.
// Creates: Log Analytics, a managed identity with AcrPull, PostgreSQL Flexible Server (database
// "factory"), a Container Apps environment, the runtime app and a one-off provisioning job that
// loads the App Pack's data and applies its roles and row-level security.
// Written by the factory; not yet validated against a live subscription.
targetScope = 'resourceGroup'

param location string = resourceGroup().location
param appName string = '__APP_DASH__'
@description('Full image reference, e.g. myacr.azurecr.io/factory-__APP_DASH__:v1')
param image string
@description('Existing Azure Container Registry name holding the image')
param acrName string
param pgAdminUser string = 'factoryadmin'
@secure()
param pgAdminPassword string
@secure()
param anthropicApiKey string
param runtimeModel string = 'claude-sonnet-5-5'
@description('Entra ID app registration (client) id. Empty = no sign-in (demo only).')
param entraClientId string = ''
param entraTenantId string = subscription().tenantId
@secure()
param entraClientSecret string = ''

var signIn = !empty(entraClientId)

resource logs 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${appName}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${appName}-id'
  location: location
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, 'acrpull')
  scope: acr
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: '${appName}-pg'
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: pgAdminUser
    administratorLoginPassword: pgAdminPassword
    storage: { storageSizeGB: 32 }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: { mode: 'Disabled' }
  }
}

resource pgDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: pg
  name: 'factory'
}

// Allows Azure services (the Container Apps environment) to reach the server.
// Replace with VNet integration and private endpoints for production.
resource pgFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: pg
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${appName}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var secrets = concat([
  { name: 'pg-password', value: pgAdminPassword }
  { name: 'anthropic-key', value: anthropicApiKey }
], signIn ? [ { name: 'microsoft-provider-authentication-secret', value: entraClientSecret } ] : [])

var envVars = [
  { name: 'FACTORY_APP', value: '__APP_ID__' }
  { name: 'PG_HOST', value: pg.properties.fullyQualifiedDomainName }
  { name: 'PG_PORT', value: '5432' }
  { name: 'PG_USER', value: pgAdminUser }
  { name: 'PG_PASSWORD', secretRef: 'pg-password' }
  { name: 'FACTORY_PG_DB', value: 'factory' }
  { name: 'INSIGHTS_PG_HOST', value: pg.properties.fullyQualifiedDomainName }
  { name: 'INSIGHTS_PG_PORT', value: '5432' }
  { name: 'ANTHROPIC_API_KEY', secretRef: 'anthropic-key' }
  { name: 'INSIGHTS_LLM_PROVIDER', value: 'anthropic' }
  { name: 'INSIGHTS_LLM_MODEL', value: runtimeModel }
  { name: 'FACTORY_AUTH', value: signIn ? 'entra' : 'none' }
]

var registries = [
  {
    server: acr.properties.loginServer
    identity: identity.id
  }
]

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
      }
      registries: registries
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: 'app'
          image: image
          env: envVars
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
    }
  }
  dependsOn: [ acrPull ]
}

// Built-in authentication: every request is signed in with Entra ID; the app reads the user's
// groups from X-MS-CLIENT-PRINCIPAL and maps them to personas with apppacks/__APP_ID__/access.yaml.
// The app registration must emit the "groups" claim (Token configuration > Add groups claim).
resource auth 'Microsoft.App/containerApps/authConfigs@2024-03-01' = if (signIn) {
  parent: app
  name: 'current'
  properties: {
    platform: { enabled: true }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: entraClientId
          clientSecretSettingName: 'microsoft-provider-authentication-secret'
          openIdIssuer: '${environment().authentication.loginEndpoint}${entraTenantId}/v2.0'
        }
        validation: {
          allowedAudiences: [ 'api://${entraClientId}', entraClientId ]
        }
      }
    }
  }
}

resource provisionJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${appName}-provision'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    environmentId: env.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 1800
      replicaRetryLimit: 1
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: registries
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: 'provision'
          image: image
          command: [ 'python', '-m', 'factory', 'provision', '--app', '__APP_ID__' ]
          env: envVars
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
    }
  }
  dependsOn: [ acrPull, pgDb, pgFirewall ]
}

output url string = 'https://${app.properties.configuration.ingress.fqdn}'
output provisionJob string = provisionJob.name
