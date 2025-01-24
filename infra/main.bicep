targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name which is used to generate a short unique hash for each resource')
param name string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Id of the user or app to assign application roles')
param principalId string = ''

@description('Flag to decide where to create OpenAI role for current user')
param createRoleForUser bool = true

param acaExists bool = false

// Parameters for the Azure OpenAI resource:
param openAiResourceName string = ''
param openAiResourceGroupName string = ''
@minLength(1)
@description('Location for the OpenAI resource')
// Look for the desired model in availability table. Default model is gpt-4o-mini:
// https://learn.microsoft.com/azure/ai-services/openai/concepts/models#standard-deployment-model-availability
@allowed([
  'australiaeast'
  'brazilsouth'
  'canadaeast'
  'eastus'
  'eastus2'
  'francecentral'
  'germanywestcentral'
  'japaneast'
  'koreacentral'
  'northcentralus'
  'norwayeast'
  'polandcentral'
  'southafricanorth'
  'southcentralus'
  'southindia'
  'spaincentral'
  'swedencentral'
  'switzerlandnorth'
  'uksouth'
  'westeurope'
  'westus'
  'westus3'
])
@metadata({
  azd: {
    type: 'location'
  }
})
param openAiResourceLocation string
param openAiSkuName string = ''
param openAiApiVersion string = '' // Used by the SDK in the app code
param disableKeyBasedAuth bool = true

// Parameters for the specific Azure OpenAI deployment:
param openAiDeploymentName string // Set in main.parameters.json
param openAiModelName string // Set in main.parameters.json
param openAiModelVersion string // Set in main.parameters.json
param openAiDeploymentCapacity int // Set in main.parameters.json
param openAiDeploymentSkuName string // Set in main.parameters.json

@description('Flag to decide whether to create Azure OpenAI instance or not')
param createAzureOpenAi bool // Set in main.parameters.json

@description('Azure OpenAI endpoint to use. If provided, no Azure OpenAI instance will be created.')
param openAiEndpoint string = ''

var resourceToken = toLower(uniqueString(subscription().id, name, location ))
var tags = { 'azd-env-name': name }

resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: '${name}-rg'
  location: location
  tags: tags
}

resource openAiResourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' existing = if (!empty(openAiResourceGroupName)) {
  name: !empty(openAiResourceGroupName) ? openAiResourceGroupName : resourceGroup.name
}

var prefix = resourceToken

module sharedidentity 'identity.bicep' = {
  name: 'identity'
  scope: resourceGroup
  params: {
    location: location
    identityName: '${prefix}-id-shareds'
  }
}

module formRecognizer 'core/ai/form-recognizer.bicep' = {
  name: 'form-recognizer'
  scope: resourceGroup
  params: {
    name: '${prefix}-form-recognizer'
    location: location
    tags: tags
    sharedIdentityId: sharedidentity.outputs.resourceid
  }
}

output FORM_RECOGNIZER_NAME string = formRecognizer.outputs.formRecognizerName
output FORM_RECOGNIZER_ENDPOINT string = formRecognizer.outputs.formRecognizerEndpoint

module openAi 'core/ai/cognitiveservices.bicep' = if (createAzureOpenAi) {
  name: 'openai'
  scope: openAiResourceGroup
  params: {
    name: !empty(openAiResourceName) ? openAiResourceName : '${resourceToken}-cog'
    location: !empty(openAiResourceLocation) ? openAiResourceLocation : location
    tags: tags
    sharedIdentityId: sharedidentity.outputs.resourceid
    disableLocalAuth: disableKeyBasedAuth
    sku: {
      name: !empty(openAiSkuName) ? openAiSkuName : 'S0'
    }
    deployments: [
      {
        name: openAiDeploymentName
        model: {
          format: 'OpenAI'
          name: openAiModelName
          version: openAiModelVersion
        }
        sku: {
          name: openAiDeploymentSkuName
          capacity: openAiDeploymentCapacity
        }
      }
    ]
  }
}

module logAnalyticsWorkspace 'core/monitor/loganalytics.bicep' = {
  name: 'loganalytics'
  scope: resourceGroup
  params: {
    name: '${prefix}-loganalytics'
    location: location
    tags: tags
  }
}

// Container apps host (including container registry)
module containerApps 'core/host/container-apps.bicep' = {
  name: 'container-apps'
  scope: resourceGroup
  params: {
    name: 'app'
    location: location
    tags: tags
    containerAppsEnvironmentName: '${prefix}-containerapps-env'
    containerRegistryName: '${replace(prefix, '-', '')}registry'
    logAnalyticsWorkspaceName: logAnalyticsWorkspace.outputs.name
  }
}

// Storage account
module storageAccount 'core/storage/storage-account.bicep' = {
  name: 'storage-account'
  scope: resourceGroup
  params: {
    name: '${prefix}x'
    location: location
    tags: tags
    sharedIdentityId: sharedidentity.outputs.resourceid
  }
}

// Azure Cognitive Search service
module searchService 'core/search/search-service.bicep' = {
  name: 'search-service'
  scope: resourceGroup
  params: {
    name: '${prefix}-search'
    location: location
    tags: tags
  }
}


// Container app frontend
module aca 'aca.bicep' = {
  name: 'aca'
  scope: resourceGroup
  params: {
    name: replace('${take(prefix,19)}-ca', '--', '-')
    location: location
    tags: tags
    identityPrincipalid: sharedidentity.outputs.identityprincipalid
    identityClientId: sharedidentity.outputs.identityclientid
    identityName: sharedidentity.outputs.identityname
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    containerRegistryName: containerApps.outputs.registryName
    openAiDeploymentName: openAiDeploymentName
    openAiEndpoint: createAzureOpenAi ? openAi.outputs.endpoint : openAiEndpoint
    openAiApiVersion: openAiApiVersion
    exists: acaExists
    azureStorageAccountUrl: storageAccount.outputs.storageAccountUrl
    azureStorageContainerName: storageAccount.outputs.containerName
    azureSearchServiceUrl: searchService.outputs.searchServiceUrl
    formRecognizerEndpoint: formRecognizer.outputs.formRecognizerEndpoint


  }
}

// module openAiRoleUser 'core/security/role.bicep' = if (createRoleForUser && createAzureOpenAi) {
//   scope: openAiResourceGroup
//   name: 'openai-role-user'
//   params: {
//     principalId: sharedidentity.outputs.identityprincipalid
//     roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
//     principalType: 'User'
//   }
// }

module storageRoleAssignment 'core/security/role.bicep' = {
  name: 'storage-account-roless'
  scope: resourceGroup
  params: {
    principalId: sharedidentity.outputs.identityprincipalid
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
    principalType: 'ServicePrincipal'
  }
}

module searchRoleAssignment 'core/security/role.bicep' = {
  name: 'search-roless'
  scope: resourceGroup
  params: {
    principalId: sharedidentity.outputs.identityprincipalid
    roleDefinitionId: '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // Search Service Contributor
    principalType: 'ServicePrincipal'
  }
}

module openAiRoleAssignment 'core/security/role.bicep' = {
  name: 'openai-roless'
  scope: resourceGroup
  params: {
    principalId: sharedidentity.outputs.identityprincipalid
    roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User
    principalType: 'ServicePrincipal'
  }
}





module storageRoleAssignmentForSearch 'core/security/role.bicep' = {
  name: 'storage-account-roles-search'
  scope: resourceGroup
  params: {
    principalId: searchService.outputs.searchServicePrincipalId
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
    principalType: 'ServicePrincipal'
  }
}

module searchRoleAssignmentForSearch 'core/security/role.bicep' = {
  name: 'search-roles-search'
  scope: resourceGroup
  params: {
    principalId: searchService.outputs.searchServicePrincipalId
    roleDefinitionId: '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // Search Service Contributor
    principalType: 'ServicePrincipal'
  }
}

module openAiRoleAssignmentForSearch 'core/security/role.bicep' = {
  name: 'openai-roles-search'
  scope: resourceGroup
  params: {
    principalId: searchService.outputs.searchServicePrincipalId
    roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User
    principalType: 'ServicePrincipal'
  }
}




output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId

output AZURE_OPENAI_RESOURCE_GROUP string = openAiResourceGroup.name
output AZURE_OPENAI_RESOURCE_NAME string = openAi.outputs.name
output AZURE_OPENAI_CHAT_DEPLOYMENT string = openAiDeploymentName
output AZURE_OPENAI_API_VERSION string = openAiApiVersion
output AZURE_OPENAI_ENDPOINT string = createAzureOpenAi ? openAi.outputs.endpoint : openAiEndpoint

output SERVICE_ACA_IDENTITY_PRINCIPAL_ID string = sharedidentity.outputs.identityprincipalid
output SERVICE_ACA_NAME string = aca.outputs.SERVICE_ACA_NAME
output SERVICE_ACA_URI string = aca.outputs.SERVICE_ACA_URI
output SERVICE_ACA_IMAGE_NAME string = aca.outputs.SERVICE_ACA_IMAGE_NAME

output AZURE_CONTAINER_ENVIRONMENT_NAME string = containerApps.outputs.environmentName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerApps.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerApps.outputs.registryName

output AZURE_SEARCH_SERVICE_NAME string = searchService.outputs.searchServiceName
output AZURE_SEARCH_SERVICE_URL string = searchService.outputs.searchServiceUrl
// output AZURE_SEARCH_SERVICE_KEY string = searchService.outputs.searchServiceKey
output AZURE_SEARCH_SERVICE_ID string = searchService.outputs.searchServiceId
