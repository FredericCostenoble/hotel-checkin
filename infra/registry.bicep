// Containerregister voor de robot, gedeeld door TST en PRD (staat in rg-checkin-prd).
// Basic: ongeveer 5 euro per maand. Geen wachtwoorden: ophalen met managed identity (AcrPull).

param location string = resourceGroup().location

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acrcheckin${take(uniqueString(resourceGroup().id), 8)}'
  location: location
  tags: { app: 'hotel-checkin' }
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

output loginServer string = acr.properties.loginServer
output name string = acr.name
output resourceGroup string = resourceGroup().name
