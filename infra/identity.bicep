
param identityName string
param location string = resourceGroup().location

resource sharedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

output identityprincipalid string = sharedIdentity.properties.principalId
output identityclientid string = sharedIdentity.properties.clientId
output identityname string = sharedIdentity.name
output resourceid string = sharedIdentity.id
