metadata description = 'Creates an Azure Storage account.'
param name string
param location string = resourceGroup().location
param tags object = {}

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
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2022-09-01' = {
  parent: storageAccount
  name: 'default'
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  parent: blobService
  name: 'pdf-uploads'
}

output storageAccountName string = storageAccount.name
output storageAccountUrl string = 'https://${storageAccount.name}.blob.core.windows.net'
output containerName string = container.name
output storageAccountId string = storageAccount.id
