# permissions required: 

To deploy the AUXO app the following permissions are required: 


- Contributor role in Azure Subscription: 
    - You need the contributor role in your Azure subscription to create, manage, and deploy resources. 
- User Access Administrator role in Azure Subscription: 
    - you need to grant other App access to your Azure resources, you need the User Access Administrator role in your Azure subscription.


# How to assign the permissions to the Azure Subscription

To assign the required roles to an Azure subscription, you can follow these steps:

1. Log in to the Azure portal.
2. Go to the Azure Subscription that you want to assign the role to.
3. Go to the Access control (IAM) section.
4. Click the "Add role assignment" button.
5. From the list select the `Contributor` role
7. Click on `Next`button 
8. Click on `+ Select members` 
9. Add the user account you want to assign the role to. 
10. Click on `Next`button 
11. Click on `Review + assign`

Same procedure needs to be followed from **step 4** for the `User Access Administrator` role as well. 



