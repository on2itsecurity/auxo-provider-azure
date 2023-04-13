auxo_api_token          = "YOUR API TOKEN"
auxo_api_url            = "api.on2it.net"
subscription_id         = "YOUR SUBSCRIPTION ID"

resource_group_name     = "auxo-provider-azure"
location                = "westeurope"
deployment_identifier   = "customername01"

auxo_provider_azure_id  = "auxo_provider_azure_1" #Unique ID per deployment, so it is known, what states are maintained by the provider

# Deployment identifier will be used to create the following unique names;
# storage_account_name   = "saauxoproviderazure" + deployment_identifier
# function_name          = "auxo-provider-azure" + deployment_identifier
# When specifying the storage_account_name and function_name manually, leave the deployment_identifier empty.

# Optional
#storage_account_name   = "saauxoproviderazure" #Must be unique
#app_service_plan_name  = "asp_auxo_provider_azure"
#function_name          = "auxo-provider-azure" #Must be unique
#protectsurface_tag     = "protectsurface"
#protectsurface_name    = "Auxo Provider Azure"
