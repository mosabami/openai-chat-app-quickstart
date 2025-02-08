metadata description = 'Creates an Azure Storage account.'
param name string
param location string = resourceGroup().location
param tags object = {}
param sharedIdentityId string

resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${sharedIdentityId}': {}
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2022-09-01' = {
  parent: storageAccount
  name: 'default'
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  parent: blobService
  name: 'pdf-uploads'
}


// resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
//   name: guid(storageAccount.id, 'manual', 'StorageBlobDataContributor')
//   scope: storageAccount
//   properties: {
//     roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
//     principalId: sharedIdentityId
//     principalType: 'ServicePrincipal'
//   }
// }

output storageAccountName string = storageAccount.name
output storageAccountUrl string = 'https://${storageAccount.name}.blob.core.windows.net'
output containerName string = container.name
output storageAccountId string = storageAccount.id
