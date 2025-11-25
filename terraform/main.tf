# This Terraform configuration will create a Azure Function for the auxo-provider-auxo.
# Created by Rob Maas (rob.maas@on2it.net)

terraform {
    required_providers {
        azurerm = {
            source  = "hashicorp/azurerm"
            version = "4.39.0"
        }
    }
}

provider "azurerm" {
    subscription_id = var.subscription_id
    features {
        resource_group {
            prevent_deletion_if_contains_resources = false
        }        
    }
}

# Create the resourcegroup holding the resources
resource "azurerm_resource_group" "rg_auxo_provider_azure" {
    name     = var.resource_group_name
    location = var.location
    
    tags     = {
        (var.portectsurface_tag) = var.protect_surface_name
    }
}

# Create a storage account to store the "function" 
resource "azurerm_storage_account" "sa_auxo_provider_azure" {
    name                     = format("%s%s", var.storage_account_name, var.deployment_identifier)
    resource_group_name      = azurerm_resource_group.rg_auxo_provider_azure.name
    location                 = azurerm_resource_group.rg_auxo_provider_azure.location
    
    account_tier             = "Standard"
    account_replication_type = "LRS"
    
    tags                     = {
        (var.portectsurface_tag) = var.protect_surface_name
    }
}

# Create an app service plan
resource "azurerm_service_plan" "asp_auxo_provider_azure" {
    name                = var.app_service_plan_name
    resource_group_name = azurerm_resource_group.rg_auxo_provider_azure.name
    location            = azurerm_resource_group.rg_auxo_provider_azure.location
    
    os_type             = "Linux"
    sku_name            = "Y1"
    
    tags                = {
        (var.portectsurface_tag) = var.protect_surface_name
    }
}

# Create an application insights instance for logging/monitoring
resource "azurerm_application_insights" "ai_auxo_provider_azure" {
    name                = format("%s-appinsights", var.function_name)
    resource_group_name = azurerm_resource_group.rg_auxo_provider_azure.name
    location            = azurerm_resource_group.rg_auxo_provider_azure.location
    application_type    = "web"

    tags                = {
        (var.portectsurface_tag) = var.protect_surface_name
    }

}

# Create the function app
resource "azurerm_linux_function_app" "fa_auxo_provider_azure" {
    name                      = format("%s%s", var.function_name, var.deployment_identifier)
    resource_group_name       = azurerm_resource_group.rg_auxo_provider_azure.name
    location                  = azurerm_resource_group.rg_auxo_provider_azure.location

    storage_account_name      = azurerm_storage_account.sa_auxo_provider_azure.name
    storage_account_access_key= azurerm_storage_account.sa_auxo_provider_azure.primary_access_key
    service_plan_id           = azurerm_service_plan.asp_auxo_provider_azure.id

    site_config {  
        application_insights_key               = azurerm_application_insights.ai_auxo_provider_azure.instrumentation_key
        application_insights_connection_string = azurerm_application_insights.ai_auxo_provider_azure.connection_string
        application_stack {
            python_version = "3.12"
        }
    }

    app_settings = {
        SCM_DO_BUILD_DURING_DEPLOYMENT = true
        FUNCTIONS_WORKER_RUNTIME = "python"       
        
        //Specific for AUXO-Provider-Azure
        "SUBSCRIPTION_ID"        = var.subscription_id
        "API_TOKEN"              = var.auxo_api_token
        "API_URL"                = var.auxo_api_url
        "PROTECT_SURFACE_TAG"    = var.portectsurface_tag
        "AUXO_PROVIDER_AZURE_ID" = var.auxo_provider_azure_id
    }

    identity {
        type = "SystemAssigned"
    }

    tags                      = {
        (var.portectsurface_tag) = var.protect_surface_name
    }
}

# Assign role (permissions) to function app
resource "azurerm_role_assignment" "ra_auxo_provider_azure" {
    role_definition_name = "Reader"
    scope                = format("/subscriptions/%s", var.subscription_id)
    principal_id         = azurerm_linux_function_app.fa_auxo_provider_azure.identity.0.principal_id
}

# Create zip/deployment file 
resource "null_resource" "deployment_zip" {
    provisioner "local-exec" {
        command = "cd .. && zip -r deploy/functionapp.zip protectsurface_update/ host.json requirements.txt"
    }
    triggers = {
        code_changed = filemd5("../protectsurface_update/__init__.py")
    }
}

# Deploy zip file to function app
resource "null_resource" "deploy" {
    provisioner "local-exec" {
        command = format("az account set --subscription %s && az functionapp deployment source config-zip --resource-group %s --name %s --src ../deploy/functionapp.zip --build-remote true --verbose", var.subscription_id, azurerm_resource_group.rg_auxo_provider_azure.name, azurerm_linux_function_app.fa_auxo_provider_azure.name)
    }
    triggers = {      
      new_zip = filemd5("../protectsurface_update/__init__.py")
    }
}