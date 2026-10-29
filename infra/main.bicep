// Azure-omgeving voor de check-in-automatisatie, één per omgeving (TST of PRD).
// Gedeeld door alle hotels: wat per hotel verschilt staat in config/hotels/<hotel_id>.toml
// en in Key Vault (<hotel_id>-<naam>).
//
// Zo goedkoop mogelijk:
// - Static Web Apps Free (alleen de pagina's van het formulier, geen gegevens)
// - Functions Flex Consumption: processen en de API van het formulier (geen vaste kost)
// - Table Storage (centen per maand)
// - Log Analytics met dagelijkse limiet, 30 dagen bewaring
// - Budgetmelding per resource group
//
// De Lighthouse-robot (Container Apps Job) komt erbij zodra het Lighthouse-bouwblok klaar is.

targetScope = 'resourceGroup'

@allowed(['tst', 'prd'])
param env string

@description('Regio voor alle gegevens en verwerking (opslag, Function App, Key Vault, logging).')
param location string

@description('Regio van de Static Web App (alleen pagina\'s, geen gegevens; beperkt aantal regio\'s).')
param swaLocation string

@description('Extra adressen die de API mogen aanroepen, met komma\'s, bv. https://checkin.hotellucca.be')
param formOrigins string = ''

@description('Eigen adres van het formulier, bv. checkin.hotellucca.be (leeg = standaardadres van Azure). De CNAME moet eerst bestaan.')
param customDomain string = ''

@description('Client-id van de app registration voor de login op de opvolgpagina (leeg = opvolgpagina dicht).')
param adminClientId string = ''

@description('Waar budgetmeldingen naartoe gaan.')
param alertEmail string

@description('Maandbudget in de munt van het abonnement. 0 = geen budgetmelding.')
param budgetAmount int = 0

@description('Eerste dag van een maand, niet in het verleden bij de eerste deployment.')
param budgetStartDate string = '2026-10-01'


@description('Maximaal aantal GB logging per dag (als tekst, bv. 0.1).')
param logDailyCapGb string = '0.1'

@description('Buiten PRD: alle mails gaan naar dit adres.')
param testEmail string = ''

@description('Buiten PRD: alle SMS en WhatsApp gaan naar dit nummer.')
param testPhone string = ''

@description('Object-id van de beheerder die secrets in Key Vault mag zetten (leeg = geen).')
param kvAdminObjectId string = ''

@description('Image van de robot (bv. acr.azurecr.io/hotel-checkin-robot:<sha>). Leeg = geen robot.')
param robotImage string = ''

@description('Naam en resource group van het gedeelde containerregister (infra/registry.bicep).')
param acrName string = ''
param acrResourceGroup string = ''

@description('Schema van de robot (cron, UTC).')
param robotSchedule string = env == 'prd' ? '*/15 * * * *' : '0 * * * *'

@description('Regio van de robot (Container Apps). Standaard dezelfde als de gegevens.')
param robotLocation string = location

param mailSender string = 'checkin@hotellucca.be'

var suffix = take(uniqueString(resourceGroup().id), 6)
var tags = { app: 'hotel-checkin', env: env }
var tables = ['Reservations', 'Messages', 'MarketingOptOut', 'RobotRuns']

var roles = {
  blobOwner: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  tableContributor: '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
  queueContributor: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  kvSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  kvSecretsOfficer: 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
}

// Opslag: tabellen met gastgegevens en de deploymentpakketten van de Function App
resource st 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'stcheckin${env}${suffix}'
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    // Alleen toegang met managed identity, geen opslagsleutels
    allowSharedKeyAccess: false
    accessTier: 'Hot'
  }
}

resource blobSvc 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: st
  name: 'default'
}

resource deployContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobSvc
  name: 'deployments'
}

resource tableSvc 'Microsoft.Storage/storageAccounts/tableServices@2023-05-01' = {
  parent: st
  name: 'default'
}

resource tbl 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = [
  for t in tables: {
    parent: tableSvc
    name: t
  }
]

// Logging met dagelijkse limiet
resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-checkin-${env}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: json(logDailyCapGb) }
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-checkin-${env}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: law.id
  }
}

// Secrets (Lighthouse, Salto, Twilio, ...), per hotel als <hotel_id>-<naam>
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-checkin-${env}-${suffix}'
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

// Pagina's van het formulier checkin.<hotel> (de API zit in de Function App)
resource swa 'Microsoft.Web/staticSites@2023-12-01' = {
  name: 'swa-checkin-${env}'
  location: swaLocation
  tags: tags
  sku: { name: 'Free', tier: 'Free' }
  properties: {}
}

resource swaDomain 'Microsoft.Web/staticSites/customDomains@2023-12-01' = if (!empty(customDomain)) {
  parent: swa
  name: empty(customDomain) ? 'none' : customDomain
  properties: {}
}

var formHost = empty(customDomain) ? swa.properties.defaultHostname : customDomain

var allowedOrigins = concat(
  ['https://${swa.properties.defaultHostname}'],
  empty(customDomain) ? [] : ['https://${customDomain}'],
  filter(map(split(formOrigins, ','), o => trim(o)), o => !empty(o))
)

// Function App: processen (timer, later Salto en berichten) en de API van het formulier
resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'asp-checkin-${env}'
  location: location
  tags: tags
  kind: 'functionapp'
  sku: { tier: 'FlexConsumption', name: 'FC1' }
  properties: { reserved: true }
}

var funcSettings = filter(
  items({
    AzureWebJobsStorage__accountName: st.name
    APPLICATIONINSIGHTS_CONNECTION_STRING: appi.properties.ConnectionString
    APP_ENV: env
    KEY_VAULT_URL: kv.properties.vaultUri
    STORAGE_TABLE_ENDPOINT: st.properties.primaryEndpoints.table
    MAIL_SENDER: mailSender
    ADMIN_AUTH: empty(adminClientId) ? '' : 'easyauth'
    ROBOT_JOB_ID: empty(robotImage) ? '' : robotJob.id
    ROBOT_IMAGE: robotImage
    TEST_EMAIL: env == 'prd' ? '' : testEmail
    TEST_PHONE: env == 'prd' ? '' : testPhone
    // In TST wijzen de links in de mails naar het testformulier
    CHECKIN_FORM_URL: env == 'prd' ? '' : 'https://${formHost}/?r={token}'
  }),
  s => !empty(s.value)
)

resource func 'Microsoft.Web/sites@2024-04-01' = {
  name: 'func-checkin-${env}-${suffix}'
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      minTlsVersion: '1.2'
      cors: { allowedOrigins: allowedOrigins }
      appSettings: map(funcSettings, s => { name: s.key, value: s.value })
    }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${st.properties.primaryEndpoints.blob}${deployContainer.name}'
          authentication: { type: 'SystemAssignedIdentity' }
        }
      }
      scaleAndConcurrency: { maximumInstanceCount: 40, instanceMemoryMB: 2048 }
      runtime: { name: 'python', version: '3.12' }
    }
  }
}

// Rechten van de Function App (managed identity, geen sleutels)
var storageRoles = [roles.blobOwner, roles.tableContributor, roles.queueContributor]

// Ingebouwde Microsoft-login voor de opvolgpagina. Anoniem blijft toegelaten (check-in-API voor
// gasten); de code van de opvolgpagina eist zelf een aangemelde gebruiker.
// Wie mag aanmelden, wordt beperkt in de app registration (toewijzing verplicht, zie setup-admin.sh).
resource funcAuth 'Microsoft.Web/sites/config@2024-04-01' = if (!empty(adminClientId)) {
  parent: func
  name: 'authsettingsV2'
  properties: {
    platform: { enabled: true }
    globalValidation: {
      requireAuthentication: false
      unauthenticatedClientAction: 'AllowAnonymous'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: adminClientId
          openIdIssuer: '${environment().authentication.loginEndpoint}${tenant().tenantId}/v2.0'
        }
        validation: { allowedAudiences: [adminClientId, 'api://${adminClientId}'] }
        // Altijd vragen welk account (in de browser zijn vaak meerdere accounts aangemeld)
        login: { loginParameters: ['prompt=select_account'] }
      }
    }
    login: { tokenStore: { enabled: false } }
  }
}

resource raStorage 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for r in storageRoles: {
    scope: st
    name: guid(st.id, func.id, r)
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', r)
      principalId: func.identity.principalId
      principalType: 'ServicePrincipal'
    }
  }
]

resource raKvFunc 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kv.id, func.id, roles.kvSecretsUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.kvSecretsUser)
    principalId: func.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource raKvAdmin 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(kvAdminObjectId)) {
  scope: kv
  name: guid(kv.id, kvAdminObjectId, roles.kvSecretsOfficer)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.kvSecretsOfficer)
    principalId: kvAdminObjectId
    principalType: 'User'
  }
}

// Budgetmelding: 80 procent effectief verbruikt of 100 procent verwacht
resource budget 'Microsoft.Consumption/budgets@2023-11-01' = if (budgetAmount > 0) {
  name: 'budget-checkin-${env}'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: { startDate: budgetStartDate }
    notifications: {
      actual80: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: [alertEmail]
      }
      forecast100: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: [alertEmail]
      }
    }
  }
}

// ---------------------------------------------------------------- robot (Lighthouse)
// Container Apps Job met Chromium, op schema en op vraag (knop op de opvolgpagina).
// Leest Lighthouse alleen. Rechten via een eigen managed identity, geen sleutels.

var withRobot = !empty(robotImage)

resource robotId 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (withRobot) {
  name: 'id-checkin-robot-${env}'
  location: location
  tags: tags
}

module robotAcrPull 'acr-pull.bicep' = if (withRobot) {
  name: 'robot-acrpull-${env}'
  scope: resourceGroup(acrResourceGroup)
  params: {
    acrName: acrName
    principalId: robotId!.properties.principalId
  }
}

resource raRobotTables 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (withRobot) {
  scope: st
  name: guid(st.id, 'robot', roles.tableContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.tableContributor)
    principalId: robotId!.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource raRobotKv 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (withRobot) {
  scope: kv
  name: guid(kv.id, 'robot', roles.kvSecretsUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.kvSecretsUser)
    principalId: robotId!.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' = if (withRobot) {
  name: 'cae-checkin-${env}'
  location: robotLocation
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: law.properties.customerId
        sharedKey: law.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
  }
}

resource robotJob 'Microsoft.App/jobs@2024-03-01' = if (withRobot) {
  name: 'job-checkin-robot-${env}'
  location: robotLocation
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${robotId.id}': {} }
  }
  dependsOn: [robotAcrPull, raRobotTables, raRobotKv]
  properties: {
    environmentId: cae.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 900
      replicaRetryLimit: 0
      scheduleTriggerConfig: { cronExpression: robotSchedule, parallelism: 1, replicaCompletionCount: 1 }
      registries: [{ server: '${acrName}.azurecr.io', identity: robotId.id }]
    }
    template: {
      containers: [
        {
          name: 'robot'
          image: robotImage
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: [
            { name: 'APP_ENV', value: env }
            { name: 'KEY_VAULT_URL', value: kv.properties.vaultUri }
            { name: 'STORAGE_TABLE_ENDPOINT', value: st.properties.primaryEndpoints.table }
            { name: 'AZURE_CLIENT_ID', value: robotId!.properties.clientId }
            { name: 'ROBOT_HOURS', value: '2' }
          ]
        }
      ]
    }
  }
}

// De Function App mag de robot starten (knop op de opvolgpagina)
resource raFuncRobot 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (withRobot) {
  scope: robotJob
  name: guid(robotJob.id, func.id, 'contributor')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ad88-20f7382dd24c')
    principalId: func.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output functionAppName string = func.name
output staticWebAppName string = swa.name
output staticWebAppHost string = swa.properties.defaultHostname
output formUrl string = 'https://${formHost}'
output functionAppHost string = func.properties.defaultHostName
output adminUrl string = 'https://${func.properties.defaultHostName}/opvolging/'
output keyVaultName string = kv.name
output storageAccountName string = st.name
