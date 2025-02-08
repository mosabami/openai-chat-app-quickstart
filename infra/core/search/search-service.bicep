metadata description = 'Creates an Azure Cognitive Search service.'
param name string
param location string = resourceGroup().location
param sku string = 'basic'
param tags object = {}

resource searchService 'Microsoft.Search/searchServices@2020-08-01' = {
  name: name
  location: location
  sku: {
    name: sku
  }
  properties: {
    hostingMode: 'default'
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
}

output searchServiceName string = searchService.name
output searchServiceUrl string = 'https://${searchService.name}.search.windows.net'
output searchServiceId string = searchService.id
output searchServicePrincipalId string = searchService.identity.principalId
