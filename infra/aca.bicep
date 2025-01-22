param name string
param location string = resourceGroup().location
param tags object = {}

param identityName string
param containerAppsEnvironmentName string
param containerRegistryName string
param serviceName string = 'aca'
param exists bool
param openAiDeploymentName string
param openAiEndpoint string
param openAiApiVersion string

param azureStorageAccountUrl string
param azureStorageContainerName string
param azureStorageAccountId string

resource acaIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

var env = [
  {
    name: 'AZURE_OPENAI_CHAT_DEPLOYMENT'
    value: openAiDeploymentName
  }
  {
    name: 'AZURE_OPENAI_ENDPOINT'
    value: openAiEndpoint
  }
  {
    name: 'AZURE_OPENAI_API_VERSION'
    value: openAiApiVersion
  }
  {
    name: 'RUNNING_IN_PRODUCTION'
    value: 'true'
  }
  {
    // DefaultAzureCredential will look for an environment variable with this name:
    name: 'AZURE_CLIENT_ID'
    value: acaIdentity.properties.clientId
  }
  {
    name: 'AZURE_STORAGE_ACCOUNT_URL'
    value: azureStorageAccountUrl
  }
  {
    name: 'AZURE_STORAGE_CONTAINER_NAME'
    value: azureStorageContainerName
  }
]

module app 'core/host/container-app-upsert.bicep' = {
  name: '${serviceName}-container-app-module'
  params: {
    name: name
    location: location
    tags: union(tags, { 'azd-service-name': serviceName })
    identityName: acaIdentity.name
    exists: exists
    containerAppsEnvironmentName: containerAppsEnvironmentName
    containerRegistryName: containerRegistryName
    env: env
    targetPort: 50505
  }
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(azureStorageAccountId, 'manual', 'StorageBlobDataContributor')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
    principalId: acaIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output SERVICE_ACA_IDENTITY_PRINCIPAL_ID string = acaIdentity.properties.principalId
output SERVICE_ACA_NAME string = app.outputs.name
output SERVICE_ACA_URI string = app.outputs.uri
output SERVICE_ACA_IMAGE_NAME string = app.outputs.imageName
