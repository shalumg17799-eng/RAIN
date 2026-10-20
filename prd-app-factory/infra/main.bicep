// Build plane: the PRD-to-App Factory on Azure Container Apps.
//   - portal (Container App, Entra sign-in optional) where people start runs and approve gates
//   - five agents, each an event-driven Container Apps Job with its own managed identity and its own
//     Storage queue; a job execution processes one stage and dispatches the next
//   - Azure Files share mounted at /app/apppacks in the portal and every job (the App Packs)
//   - PostgreSQL Flexible Server: the staging database the agents build apps in
// Written by hand for this project; not yet validated against a live subscription.
targetScope = 'resourceGroup'

param location string = resourceGroup().location
param name string = 'prdfactory'
param acrName string
@description('Factory image (portal + agents 1-4), e.g. myacr.azurecr.io/prd-factory:v1')
param image string
@description('Release agent image (factory + Azure CLI), e.g. myacr.azurecr.io/prd-factory-release:v1')
param releaseImage string
param pgAdminUser string = 'factoryadmin'
@secure()
param pgAdminPassword string
@secure()
param anthropicApiKey string
param agentModel string = 'claude-opus-5-5'
param appModel string = 'claude-sonnet-5-5'
@description('Entra ID app registration for portal sign-in. Empty = no sign-in (not for production).')
param entraClientId string = ''
@secure()
param entraClientSecret string = ''

var agents = [ 'requirements', 'data', 'knowledge', 'app', 'release' ]
var signIn = !empty(entraClientId)

resource logs 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${name}-logs'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: take(toLower(replace('${name}${uniqueString(resourceGroup().id)}', '-', '')), 24)
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { minimumTlsVersion: 'TLS1_2', allowBlobPublicAccess: false }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource share 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: fileService
  name: 'apppacks'
  properties: { shareQuota: 100 }
}

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource queues 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = [for a in agents: {
  parent: queueService
  name: 'factory-${a}'
}]

var queueConnection = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: '${name}-pg'
  location: location
  sku: { name: 'Standard_B2s', tier: 'Burstable' }
  properties: {
    version: '16'
    administratorLogin: pgAdminUser
    administratorLoginPassword: pgAdminPassword
    storage: { storageSizeGB: 64 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
  }
}

resource pgDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: pg
  name: 'factory'
}

resource pgFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: pg
  name: 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${name}-env'
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

resource envStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: env
  name: 'apppacks'
  properties: {
    azureFile: {
      accountName: storage.name
      accountKey: storage.listKeys().keys[0].value
      shareName: share.name
      accessMode: 'ReadWrite'
    }
  }
}

// One identity per component, so each agent's permissions are separate.
resource identities 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = [for a in concat(agents, [ 'portal' ]): {
  name: '${name}-${a}-id'
  location: location
}]

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (a, i) in concat(agents, [ 'portal' ]): {
  name: guid(acr.id, identities[i].id, 'acrpull')
  scope: acr
  properties: {
    principalId: identities[i].properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}]

// Only the release agent may deploy: Contributor on this resource group (generated apps are deployed
// here; grant it on another resource group instead to separate the factory from its apps).
resource releaseContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, identities[4].id, 'contributor')
  properties: {
    principalId: identities[4].properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382be4c3')
  }
}

// AcrPush for the release agent, so `az acr build` can push generated app images.
resource releaseAcrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identities[4].id, 'acrpush')
  scope: acr
  properties: {
    principalId: identities[4].properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')
  }
}

var secrets = concat([
  { name: 'pg-password', value: pgAdminPassword }
  { name: 'anthropic-key', value: anthropicApiKey }
  { name: 'queue-connection', value: queueConnection }
], signIn ? [ { name: 'microsoft-provider-authentication-secret', value: entraClientSecret } ] : [])

var commonEnv = [
  { name: 'PG_HOST', value: pg.properties.fullyQualifiedDomainName }
  { name: 'PG_PORT', value: '5432' }
  { name: 'PG_USER', value: pgAdminUser }
  { name: 'PG_PASSWORD', secretRef: 'pg-password' }
  { name: 'FACTORY_PG_DB', value: 'factory' }
  { name: 'INSIGHTS_PG_HOST', value: pg.properties.fullyQualifiedDomainName }
  { name: 'INSIGHTS_PG_PORT', value: '5432' }
  { name: 'ANTHROPIC_API_KEY', secretRef: 'anthropic-key' }
  { name: 'FACTORY_MODEL', value: agentModel }
  { name: 'INSIGHTS_LLM_PROVIDER', value: 'anthropic' }
  { name: 'INSIGHTS_LLM_MODEL', value: appModel }
  { name: 'FACTORY_QUEUE_CONNECTION', secretRef: 'queue-connection' }
]

var volumes = [ { name: 'apppacks', storageType: 'AzureFile', storageName: envStorage.name } ]
var mounts = [ { volumeName: 'apppacks', mountPath: '/app/apppacks' } ]

resource portal 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${name}-portal'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identities[5].id}': {} } }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: { external: true, targetPort: 8090 }
      registries: [ { server: acr.properties.loginServer, identity: identities[5].id } ]
      secrets: secrets
    }
    template: {
      containers: [ {
        name: 'portal'
        image: image
        env: commonEnv
        volumeMounts: mounts
        resources: { cpu: json('0.5'), memory: '1Gi' }
      } ]
      volumes: volumes
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
  dependsOn: [ acrPull ]
}

resource portalAuth 'Microsoft.App/containerApps/authConfigs@2024-03-01' = if (signIn) {
  parent: portal
  name: 'current'
  properties: {
    platform: { enabled: true }
    globalValidation: { unauthenticatedClientAction: 'RedirectToLoginPage', redirectToProvider: 'azureactivedirectory' }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: entraClientId
          clientSecretSettingName: 'microsoft-provider-authentication-secret'
          openIdIssuer: '${environment().authentication.loginEndpoint}${subscription().tenantId}/v2.0'
        }
        validation: { allowedAudiences: [ 'api://${entraClientId}', entraClientId ] }
      }
    }
  }
}

// Agents: one event-driven job each, started by a message on its own queue.
resource agentJobs 'Microsoft.App/jobs@2024-03-01' = [for (a, i) in agents: {
  name: '${name}-agent-${a}'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identities[i].id}': {} } }
  properties: {
    environmentId: env.id
    configuration: {
      triggerType: 'Event'
      replicaTimeout: 10800
      replicaRetryLimit: 0
      eventTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
        scale: {
          minExecutions: 0
          maxExecutions: 3
          pollingInterval: 20
          rules: [ {
            name: 'queue'
            type: 'azure-queue'
            metadata: { queueName: 'factory-${a}', queueLength: '1', accountName: storage.name }
            auth: [ { secretRef: 'queue-connection', triggerParameter: 'connection' } ]
          } ]
        }
      }
      registries: [ { server: acr.properties.loginServer, identity: identities[i].id } ]
      secrets: secrets
    }
    template: {
      containers: [ {
        name: 'agent'
        image: a == 'release' ? releaseImage : image
        command: a == 'release' ? [ 'python3', '-m', 'factory', 'worker', '--agent', a ] : [ 'python', '-m', 'factory', 'worker', '--agent', a ]
        env: concat(commonEnv, a == 'release' ? [
          { name: 'AZURE_CLIENT_ID', value: identities[i].properties.clientId }
          { name: 'AZURE_SUBSCRIPTION_ID', value: subscription().subscriptionId }
          { name: 'AZURE_RESOURCE_GROUP', value: resourceGroup().name }
          { name: 'AZURE_LOCATION', value: location }
          { name: 'AZURE_ACR_NAME', value: acrName }
          { name: 'PG_ADMIN_PASSWORD', secretRef: 'pg-password' }
        ] : [])
        volumeMounts: mounts
        resources: { cpu: json('1.0'), memory: '2Gi' }
      } ]
      volumes: volumes
    }
  }
  dependsOn: [ acrPull, queues, pgDb, pgFirewall ]
}]

output portalUrl string = 'https://${portal.properties.configuration.ingress.fqdn}'
output storageAccount string = storage.name
