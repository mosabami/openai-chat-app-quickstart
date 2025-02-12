param name string
param location string = resourceGroup().location
param tags object = {}

param identityPrincipalid string
param identityClientId string
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

param azureSearchServiceUrl string


param formRecognizerEndpoint string

var env = [
  {
    name: 'AZURE_OPENAI_CHAT_DEPLOYMENT'
    value: openAiDeploymentName
  }
  {
    name: 'AZURE_STORAGE_ACCOUNT_KEY'
    value: ''
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
    value: identityClientId
  }
  {
    name: 'AZURE_STORAGE_ACCOUNT_URL'
    value: azureStorageAccountUrl
  }
  {
    name: 'AZURE_STORAGE_CONTAINER_NAME'
    value: azureStorageContainerName
  }
  {
    name: 'AZURE_SEARCH_SERVICE_URL'
    value: azureSearchServiceUrl
  }

  {
    name: 'FORM_RECOGNIZER_ENDPOINT'  // Add this block
    value: formRecognizerEndpoint
  }
  {
    name: 'AZURE_SEARCH_CHUNK_SIZE'
    value: '1000'
  }
  {
    name: 'AZURE_SEARCH_CHUNK_SIZE_OVERLAP'  // Add this block
    value: '160'
  }
  {
    name: 'AZURE_SEARCH_INDEX_NAME'  // Add this block
    value: 'pdf-index'
  }
  {
    name: 'FILE_UPLOAD_PASSWORD'  // Add this block
    value: 'P@ssword'
  }
  {
    name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT'  // Add this block
    value: 'text-embedding-ada-002'
  }
]

module app 'core/host/container-app-upsert.bicep' = {
  name: '${serviceName}-container-app-module'
  params: {
    name: name
    location: location
    tags: union(tags, { 'azd-service-name': serviceName })
    identityName: identityName
    exists: exists
    containerAppsEnvironmentName: containerAppsEnvironmentName
    containerRegistryName: containerRegistryName
    env: env
    targetPort: 50505
  }
}



output SERVICE_ACA_IDENTITY_PRINCIPAL_ID string = identityPrincipalid
output SERVICE_ACA_NAME string = app.outputs.name
output SERVICE_ACA_URI string = app.outputs.uri
output SERVICE_ACA_IMAGE_NAME string = app.outputs.imageName
