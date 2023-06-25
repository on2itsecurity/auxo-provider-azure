# AUXO-Provider-Azure

## Description

Will collect resources from Azure and send them to AUXO.
The `protectsurface` tag (default) or the tag configured will be used to map the resource to the appropriate protect surfaces within AUXO.

## Requirements

- AUXO API Token
- Terraform
- Azure CLI
- zip

## How to use

### Deploy

- Clone the repository
- Copy `example.tfvars` and change the values.
  ```
  cd terraform
  cp example.tfvars mydeployment.tfvars
  open mydeployment.tfvars
  ```
- Run terraform
  ```bash
  cd terraform 
  terraform init
  terraform plan --var-file=mydeployment.tfvars --out=mydeployment.plan
  terfaform apply mydeployment.plan
  ```
- If you want to remove the deployment.
  ```bash
  terraform destroy --var-file=mydeployment.tfvars
  ```
- Azure CLI Instructions:

`az login`
or 
`az login --tenant TENANT_ID` #in case deployment via guest account, otherwise it will default to your own tenant. 

validate default subscription:

`az account list -o table` # validate if subscription is the default subscription selected under 'IsDefault' 

set default subscriptions:

`az account set --subscription SUBSCRIPTION_ID`

### Update

- Update the repository, within the directory where you cloned the repository.
  ```bash
  git pull
  ```
- Update the deployment
  ```bash
  cd terraform
  terraform plan --var-file=mydeployment.tfvars --out=mydeployment.plan
  terfaform apply mydeployment.plan
  ```

## Known limitations

- Every subscription should have its own function deployed.

### Validate

In the Azure portal

* Go to the Azure function
    * Check Monitor > Invocations and check the function is executing every 5 minutes
    * Check under Monitor > Logs to see real-time logs/output of the function

!!! note
	please note that for the first run, it can take 10 min.