import logging

import azure.functions as func

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
import json
import requests
import os

# Acquire a credential object using managed identity for authentication.
credential = DefaultAzureCredential()

# Retrieve environment variable.
SUBSCRIPTION_ID = os.environ['SUBSCRIPTION_ID']
API_TOKEN = os.environ['API_TOKEN']
PROTECT_SURFACE_TAG = os.environ['PROTECT_SURFACE_TAG']
API_URL = os.environ['API_URL']
AUXO_PROVIDER_AZURE_ID = os.environ['AUXO_PROVIDER_AZURE_ID']

# Obtain the management object for resources.
compute_client = ComputeManagementClient(credential, SUBSCRIPTION_ID)
network_client = NetworkManagementClient(credential,SUBSCRIPTION_ID)
resource_client = ResourceManagementClient(credential, SUBSCRIPTION_ID)

# Create dictionary {protectsurface_name : {location_name : {content_type : [list of resources]}}}
# The function add_resources_to_state goes through all resources in the subscription and adds them to this dictionary
def update_local_protectsurface_intended_state(intended_state: str, protectsurface_name: str, location_name: str, content_type: str, identifier: str) -> dict:
    if protectsurface_name in intended_state:
        if location_name in intended_state[protectsurface_name]:
            if content_type in intended_state[protectsurface_name][location_name]:
                intended_state[protectsurface_name][location_name][content_type].append(identifier)
            else:
                intended_state[protectsurface_name][location_name][content_type] = []
                intended_state[protectsurface_name][location_name][content_type].append(identifier)
        else:
            intended_state[protectsurface_name][location_name] = {}
            intended_state[protectsurface_name][location_name][content_type] = []
            intended_state[protectsurface_name][location_name][content_type].append(identifier)
    else:
        intended_state[protectsurface_name] = {}
        intended_state[protectsurface_name][location_name] = {}
        intended_state[protectsurface_name][location_name][content_type] = []
        intended_state[protectsurface_name][location_name][content_type].append(identifier)

    return intended_state


# Code to find all resources and add them to the correct protectsurface
def add_resources_to_state():
    
    # Retrieve the list of virtual-machines
    protectsurface_intended_state = {}

    # Add VMs and VM Public and Private IPs
    for vm in compute_client.virtual_machines.list_all():
        try:
            protectsurface_name = vm.tags[PROTECT_SURFACE_TAG]
        except (KeyError, TypeError) as error:
            protectsurface_name = 'Unidentified Resources'
        vm_id = vm.id
        location_name = vm.location

        protectsurface_intended_state = update_local_protectsurface_intended_state(protectsurface_intended_state, protectsurface_name, location_name, 'azure_cloud', vm_id)

        # Finds public and private IP addresses by looking at the NICs attached to each VM and adds them to the state
        for interface in vm.network_profile.network_interfaces:
            network_interface_name = ' '.join(interface.id.split('/')[-1:])
            resource_group = ''.join(interface.id.split('/')[4])

            network_object = network_client.network_interfaces.get(resource_group, network_interface_name).ip_configurations

            # Add private ip addresses
            for interface_object in network_object:
                private_address = interface_object.private_ip_address

                protectsurface_intended_state = update_local_protectsurface_intended_state(protectsurface_intended_state, protectsurface_name, location_name, 'ipv4', private_address)

            # Add public ip addresses
            if interface_object.public_ip_address:
                vm_public_ip_id = interface_object.public_ip_address.id
                vm_public_ip_name = ' '.join(vm_public_ip_id.split('/')[-1:])
                resource_group = ''.join(vm_public_ip_id.split('/')[4])
                
                public_address = network_client.public_ip_addresses.get(resource_group, vm_public_ip_name).ip_address
                
                protectsurface_intended_state = update_local_protectsurface_intended_state(protectsurface_intended_state, protectsurface_name, location_name, 'ipv4', public_address)
          

    # Add Virtual Network Subnets
    for virtual_network in network_client.virtual_networks.list_all():
        try:
            protectsurface_name = virtual_network.tags[PROTECT_SURFACE_TAG]
        except (KeyError, TypeError) as error:
            protectsurface_name = 'Unidentified Resources'
        virtual_network_id = virtual_network.id
        location_name = virtual_network.location

        protectsurface_intended_state = update_local_protectsurface_intended_state(protectsurface_intended_state, protectsurface_name, location_name, 'azure_cloud', virtual_network_id)

        for subnet in virtual_network.subnets:
            virtual_network_subnet = subnet.address_prefix

            # Virtual networks can have identical subnets. This code prevents duplicate subnets being added to a protect surface
            if 'ipv4' in protectsurface_intended_state[protectsurface_name][location_name].keys():
                if virtual_network_subnet in protectsurface_intended_state[protectsurface_name][location_name]['ipv4']:
                    continue
                    
            protectsurface_intended_state = update_local_protectsurface_intended_state(protectsurface_intended_state, protectsurface_name, location_name, 'ipv4', virtual_network_subnet)

    # Add all resource ids to the state if they are not VMs or VNETs which were added already
    for resource_group in resource_client.resource_groups.list():
        for resource in resource_client.resources.list_by_resource_group(resource_group.name):
            if resource.type != 'Microsoft.Compute/virtualMachines' and resource.type != 'Microsoft.Network/virtualNetworks':
                try:
                    protectsurface_name = resource.tags[PROTECT_SURFACE_TAG]
                except (KeyError, TypeError) as error:
                    protectsurface_name = 'Unidentified Resources'
                resource_id = resource.id

            protectsurface_intended_state = update_local_protectsurface_intended_state(protectsurface_intended_state, protectsurface_name, location_name, 'azure_cloud', resource_id)
        
    return protectsurface_intended_state


# Goes through the dictionary protectsurface_intended_state and makes an API call for each protect surface and location to update AUXO
def prepare_api_body_and_execute_api_call(protectsurface_intended_state: dict):

    for protectsurface in protectsurface_intended_state:
        protect_surface_name = protectsurface
        for location in protectsurface_intended_state[protectsurface].keys():
            state_contents = []
            lat,long = get_location_coords(location)
            for content_type, contents in protectsurface_intended_state[protectsurface][location].items():
                state_contents.append({content_type : contents})
            upsert_protectsurface_to_auxo(protect_surface_name, location, lat, long, state_contents)


# Formats the body of the api call in the format required for the POST to AUXO api
def construct_state_body(protect_surface_name: str, state_contents: dict) -> dict:

    state_api_input = []

    for item in state_contents:
        for k in item:
            content_type = k
            content = item[k]

            state_api_input.append({'maintainer' : f'{AUXO_PROVIDER_AZURE_ID}', 'description' : f'{protect_surface_name} {content_type}', 'content_type' : content_type, 'content' : content})
    return state_api_input


#POST request using Upsert api call https://api.on2it.net/v3/doc/#tag/Protect-Surfaces/paths/~1zerotrust~1upsert-protectsurface-location-state/post
def upsert_protectsurface_to_auxo(protect_surface_name: str, location: str, lat: float, long: float, state_contents: dict):

    body = {
        'items': [
            {
                'protectsurface_uniqueness_key': f"{protect_surface_name.replace(' ', '_')}",
                'location_uniqueness_key': f'{location}_{lat}_{long}',
                'protectsurface_name': protect_surface_name,
                'protectsurface_relevance': 60,
                'location_name': location,
                'location_coords': {
                    'lat': lat,
                    'long': long
                },
                'states': construct_state_body(protect_surface_name, state_contents)
            }
        ]
    }

    upsert_url = f'https://{API_URL}/v3/zerotrust/upsert-protectsurface-location-state'

    headers={'Content-Type': 'application/json',                                      
                'Authorization': f'Bearer {API_TOKEN}'}

    jsonbody = json.dumps(body)
    
    upsert_response = requests.post(upsert_url,
                                headers=headers, data=jsonbody)
    if upsert_response.status_code != 200:
        logging.info(f'Error http: [{upsert_response.status_code}] Unable to Upsert {protect_surface_name}: {upsert_response.content}')
    else:
        logging.info(f'Upsert to {protect_surface_name} Successful Response = {upsert_response.json()}')


# check if the coords have been set, if not, needs to update the location with the coords from https://gist.github.com/lpellegr/8ed204b10c2589a1fb925a160191b974
def get_location_coords(location_name: str):

    if location_name == 'westeurope':
        return 38.13, -78.45
    elif location_name == 'eastasia':
        return 22.267, 114.188
    elif location_name == 'southeastasia':
        return 1.283, 103.833
    elif location_name == 'centralus':
        return 41.5908, -93.6208
    elif location_name == 'eastus':
        return 37.3719, -79.8164
    elif location_name == 'eastus2':
        return 36.6681, -78.3889
    elif location_name == 'westus':
        return 37.783, -122.417
    elif location_name == 'northcentralus':
        return 41.8819, -87.6278
    elif location_name == 'southcentralus':
        return 29.4167, -98.5
    elif location_name == 'northeurope':
        return 52.3667, 4.9
    elif location_name == 'japanwest':
        return 34.6939, 135.5022
    elif location_name == 'Japan East':
        return 35.68, 139.77
    elif location_name == 'brazilsouth':
        return -23.55, -46.633
    elif location_name == 'australiaeast':
        return -33.86, 151.2094
    elif location_name == 'australiasoutheast':
        return -37.8136, 144.9631
    elif location_name == 'southindia':
        return 12.9822, 80.1636
    elif location_name == 'centralindia':
        return 18.5822, 73.9197
    elif location_name == 'westindia':
        return 19.088, 72.868
    elif location_name == 'jioindiawest':
        return 22.470701, 70.05773
    elif location_name == 'jioindiacentral':
        return 21.146633, 79.08886
    elif location_name == 'canadacentral':
        return 43.653, -79.383
    elif location_name == 'canadaeast':
        return 46.817, -71.217
    elif location_name == 'uksouth':
        return 50.941, -0.799
    elif location_name == 'ukwest':
        return 53.427, -3.084
    elif location_name == 'westcentralus':
        return 40.890, -110.234
    elif location_name == 'westus2':
        return 47.233, -119.852
    elif location_name == 'koreacentral':
        return 37.5665, 126.9780
    elif location_name == 'koreasouth':
        return 35.1796, 129.0756
    elif location_name == 'francecentral':
        return 46.3772, 2.3730
    elif location_name == 'francesouth':
        return 43.8345, 2.1972
    elif location_name == 'australiacentral':
        return -35.3075, 149.1244
    elif location_name == 'australiacentral2':
        return -35.3075, 149.1244
    elif location_name == 'uaecentral':
        return 24.466667, 54.366669
    elif location_name == 'uaenorth':
        return 25.266666, 55.316666
    elif location_name == 'southafricanorth':
        return -25.731340, 28.218370
    elif location_name == 'southafricawest':
        return -34.075691, 18.843266
    elif location_name == 'switzerlandnorth':
        return 47.451542, 8.564572
    elif location_name == 'switzerlandwest':
        return 46.204391, 6.143158
    elif location_name == 'germanynorth':
        return 53.073635, 8.806422
    elif location_name == 'germanywestcentral':
        return 50.110924, 8.682127
    elif location_name == 'norwaywest':
        return 58.969975, 5.733107
    elif location_name == 'norwayeast':
        return 59.913868, 10.752245
    elif location_name == 'brazilsoutheast':
        return -22.90278, -43.2075
    elif location_name == 'westus3':
        return 33.448376, -112.074036
    elif location_name == 'swedencentral':
        return 60.67488, 17.14127
    else: 
        return 35.0,-40.0

# api call to retrieve all states

def get_states_api_call():
    get_states_url = f'https://{API_URL}/v3/zerotrust/get-states'

    headers={'Content-Type': 'application/json',                                      
            'Authorization': f'Bearer {API_TOKEN}'}

    get_states_response = requests.get(get_states_url,
                                    headers=headers)

    if get_states_response.status_code != 200:
        logging.info(f'Error http: [{get_states_response.status_code}] States get request failed {get_states_response.content}')
    else:
        logging.info(f'State get request successful')

    decoded_response = json.loads(get_states_response.content.decode('utf-8'))
    return decoded_response

# api call to retrieve the protect surface name from the protect surface id. The protect surface name which is equal to the state name is used by delete_unused_api_maintained_states to compare the list of api maintained states in Auxo with the ones in protectsurface_intended_state

def get_protect_surface_name_by_id_api_call(protect_surface_id):
    get_states_url = f'https://{API_URL}/v3/zerotrust/get-protectsurface?id={protect_surface_id}'

    headers={'Content-Type': 'application/json',                                      
            'Authorization': f'Bearer {API_TOKEN}'}


    get__protect_surface_response = requests.get(get_states_url,
                                    headers=headers)

    if get__protect_surface_response.status_code != 200:
        logging.info(f'Error http: [{get__protect_surface_response.status_code}] Protect surface get request failed {get__protect_surface_response.content}')
    else:
        logging.info(f'Protect surface get request successful')

    decoded_response = json.loads(get__protect_surface_response.content.decode('utf-8'))
    
    return decoded_response['items'][0]['name']

# api call to delete states

def delete_state_by_id_api_call(state_name, state_id):
    get_states_url = f'https://{API_URL}/v3/zerotrust/remove-state?id={state_id}'

    headers={'Content-Type': 'application/json',                                      
            'Authorization': f'Bearer {API_TOKEN}'}


    delete_state_response = requests.post(get_states_url,
                                    headers=headers)
    if delete_state_response.status_code != 200:
        logging.info(f'Error http: [{delete_state_response.status_code}] Failed to delete state {state_name}:{state_id} {delete_state_response.content}')
    else:
        logging.info(f'Successfully deleted state {state_name}:{state_id}')

# Creates a dictionary of all the api maintained states in Auxo containing {state_name: state_id}

def create_dictionary_of_api_maintained_states_in_auxo(list_of_states):
    api_maintained_state_list = {}
    for state in list_of_states['items']:
        if state['maintainer'] == f'{AUXO_PROVIDER_AZURE_ID}':
            state_name = get_protect_surface_name_by_id_api_call(state['protectsurface_id'])
            api_maintained_state_list.setdefault(state_name, [])
            api_maintained_state_list[state_name].append(state['id'])
    return api_maintained_state_list

# Compares the api maintained states in Auxo with the states that contain resources in Azure. If an api maintained state no longer has any resources then it will be deleted.

def delete_unused_api_maintained_states(protectsurface_intended_state, api_maintained_state_list):
    for state_name in api_maintained_state_list:
        logging.info(f'API maintained states: {api_maintained_state_list}')
        if state_name not in protectsurface_intended_state:
            for state_id in api_maintained_state_list[state_name]:
                delete_state_by_id_api_call(state_name, state_id)

def main(mytimer: func.TimerRequest) -> None:
    # Functions to create protect surface and states and execute api call to add them to Auxo
    protectsurface_intended_state = add_resources_to_state()
    prepare_api_body_and_execute_api_call(protectsurface_intended_state)
    # Functions to find any api maintained states that are now empty due to changes to tags recorded in protectsurface_intended_state. The delete_unused_api_maintained_states function will delete these empty states if they are api maintained.
    list_of_states = get_states_api_call()
    api_maintained_state_list = create_dictionary_of_api_maintained_states_in_auxo(list_of_states)
    delete_unused_api_maintained_states(protectsurface_intended_state, api_maintained_state_list)
