
//Name of the resource group
variable "resource_group_name" {
    default = "auxo-provider-azure"
}

//Location of the resource group 
variable "location" {
    default = "westeurope"
}

//May only lowercase letters and numbers are allowed
variable "storage_account_name" {
    default = "saauxoprovazure"
}

//App service plan name
variable "app_service_plan_name" {
    default = "asp_auxo_provider_azure"
}

//May only contain alphanumeric characters and dashes
variable "function_name" {
    default = "auxo-provider-azure"
}

//Azure subscription ID to inventorize
variable "subscription_id" {}

//API token to authenticate against AUXO
variable "auxo_api_token" {}

//API Address without https://
variable "auxo_api_url" {
    default = "api.on2it.net"
}

//The tag (key) that is used to get the protect surface (by the AUXO-Provider-Azure)
variable "portectsurface_tag" {
    default = "protectsurface"
}

//Name of the protect surface
variable "protect_surface_name" {
    default = "AUXO Provider Azure"
}

variable "deployment_identifier" {}

variable "auxo_provider_azure_id" {
    default = "auxo-provider-azure"
}