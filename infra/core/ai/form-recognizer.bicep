metadata description = 'Creates an Azure Form Recognizer resource.'
param name string
param location string = resourceGroup().location
param tags object = {}
param sharedIdentityId string

// resource formRecognizer 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
//   name: name
//   location: location
//   tags: tags
//   kind: 'FormRecognizer'
//   properties: {
//     publicNetworkAccess: 'Enabled'
//   }
//   sku: {
//     name: 'S0'
//   }
//   identity: {
//     type: 'UserAssigned'
//     userAssignedIdentities: {
//       '${sharedIdentityId}': {}
//     }
//   }
// }

resource formRecognizer 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: name
  location: location
  tags: tags
  kind: 'FormRecognizer'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${sharedIdentityId}': {}
    }
  }
  properties: {
    customSubDomainName: toLower(name)
    disableLocalAuth: false
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      ipRules: []
      virtualNetworkRules: []
    }
  }
  sku: {
    name: 'S0'
  }
}

output formRecognizerName string = formRecognizer.name
output formRecognizerEndpoint string = formRecognizer.properties.endpoint
