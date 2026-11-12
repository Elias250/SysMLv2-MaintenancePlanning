from sysmlv2_client import SysMLV2Client, SysMLV2Error
from pprint import pprint
from datetime import datetime
import uuid # For element IDs

BASE_URL = "http://localhost:8083"
# Replace with the actual token from flexo-setup/docker-compose/env/flexo-sysmlv2.env
BEARER_TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJmbGV4by1tbXMtYXVkaWVuY2UiLCJpc3MiOiJodHRwOi8vZmxleG8tbW1zLXNlcnZpY2VzIiwidXNlcm5hbWUiOiJ1c2VyMDEiLCJncm91cHMiOlsic3VwZXJfYWRtaW5zIl0sImV4cCI6MTg2OTY3MzYwMH0.UER7sZXVa1a8i_dnk6TgIBb9SNmOfMHEUEFIQCzMgeA"
# Replace with the Project ID you want to query. This should be a valid project in your SysML v2 service.
PROJECT_ID = "c2429fdb-58a0-4351-8fd1-6f33bef2e321"

def getLatestCommitId(client: SysMLV2Client, project_id: str) -> str:
    """
    Get the latest commit ID for a given project.

    :param client: An instance of SysMLV2Client.
    :param project_id: The ID of the project to query.
    :return: The latest commit ID as a string.
    """
    
    commit_list = client.list_commits(project_id)

    if commit_list:
        latest_commit = commit_list[0]
        latest_commit_id = latest_commit.get('@id')
        latest_commit_date = datetime.fromisoformat(latest_commit['created'].replace('Z', '+00:00'))

        # Find the latest commit by comparing dates
        for commit in commit_list:
            commit_date = datetime.fromisoformat(commit['created'].replace('Z', '+00:00'))

            if commit_date > latest_commit_date:
                latest_commit = commit
                latest_commit_id = commit.get('@id')
                latest_commit_date = commit_date
        
        print(f"Latest commit ID for project {project_id}: {latest_commit_id}")
        return latest_commit_id
    return 0

def searchElements(elements, search_criteria, search_term):
    """
    Search for elements in a list based on specified criteria.

    :param elements: List of elements to search.
    :param search_criteria: The key to search by (e.g., 'declaredName', '@type').
    :param search_term: The value to match against the specified criteria.
    :return: List of matching elements.
    """
    matching_elements = []
    for element in elements:
        if element.get(search_criteria) == search_term:
            matching_elements.append(element)
    return matching_elements

def findSubclassifiedDefinition_ids(elements, base_definition_id, subclassifcations=None)-> list:
    """
    Find all definitions that are specialized of a given base definition.

    :param elements: List of elements to search.
    :param base_definition_id: The ID of the base definition to match against.
    :return: List of subclassed definition IDs.
    """
    subclassed_definitions_id = []
    if subclassifcations is None:
        subclassifcations = searchElements(elements, '@type', 'Subclassification')
        subclassed_definitions_id = [base_definition_id]
    for subclass in subclassifcations:
        if subclass.get('superclassifier').get('@id') == base_definition_id:
            subclassifier = subclass.get('subclassifier').get('@id')
            x = findSubclassifiedDefinition_ids(elements, subclassifier, subclassifcations)
            if x:
                subclassed_definitions_id.extend(x)
            subclassed_definitions_id.append(subclassifier)
            
    return subclassed_definitions_id

def findUsagesElement(elements, definition_ids: list)->list:
    """
    Find all elements that are typed by a given list of definition IDs.

    :param elements: List of elements to search.
    :param definition_ids: List of definition IDs to match against.
    :return: List of usage elements.
    """
    usages = []
    #find all featureTypings (defined by defintions)
    featureTypings = searchElements(elements, '@type', 'FeatureTyping')
    for definition_id in definition_ids:
        for ft in featureTypings:
            if ft.get('type').get('@id') == definition_id:
                usages.append(ft.get('typedFeature').get('@id'))
    return usages

def findAllUsagesOfOneDefinition(elements:list, declaredName:str)->list:
    """
    Find all Ids from usages of a given definition by its declaredName. All specializations of the definition are also included in the search.

    :param elements: List of elements to search.
    :param declaredName: The declared name of the definition to search for.
    :return: List of IDs.
    """
   # Find definition
    definition_id = searchElements(elements, 'declaredName', declaredName)[0].get("@id")

    #find all types (subclassifications of the given definition)
    all_types =findSubclassifiedDefinition_ids(elements, definition_id)

    #find all usages of machine types
    usage_ids = findUsagesElement(elements, all_types)
    return usage_ids

def findPreventativeMaintenanceActivities(client: SysMLV2Client, project_id: str, latest_commit_id: str, elements: list)->list:
    """
    Find all PreventativeMaintenanceActivity elements in the latest commit of a given project.

    :param client: An instance of SysMLV2Client.
    :param project_id: The ID of the project to query.
    :return: List of PreventativeMaintenanceActivity element IDs.
    """
    try:

        if latest_commit_id:

            machine_ids = findAllUsagesOfOneDefinition(elements, 'Machine')

            # find PreventativeMaintenanceActivity definition
            preventativeDefinition_id = searchElements(elements, 'declaredName', 'PreventativeMaintenanceActivity')[0].get("@id")

            #get all specializisations of PreventativeMaintenanceActivity
            prevantative_maintenance_activity_defintions = findSubclassifiedDefinition_ids(elements, preventativeDefinition_id)

            # Create a list of all the maintenance activities
            preventative_maintenance_activity_ids = []
            for machine_id in machine_ids:
                machine = client.get_element(project_id, machine_id, latest_commit_id)
                if machine:
                    ownedRelationships = machine.get('ownedRelationship')
                    #get ownedRelatedElements from ownedRelationships
                    owned_elements = []
                    for featureMembership in ownedRelationships:
                        featureMembership_id = featureMembership.get('@id')
                        featureMembership_element = client.get_element(project_id, featureMembership_id, latest_commit_id)
                        if featureMembership_element.get('@type') == 'FeatureMembership':
                            ownedRelatedElements = featureMembership_element.get('ownedRelatedElement')
                            for ownedRelatedElement in ownedRelatedElements:
                                owned_elements.append(ownedRelatedElement)
                    #filter owned elements for activities
                    if owned_elements:
                        activities = searchElements(owned_elements, '@type', 'ActionUsage')
                        
                        #get all usages of PreventativeMaintenanceActivity and its specializations
                        preventative_maintenance_activity_ids.extend(findUsagesElement(elements, prevantative_maintenance_activity_defintions))
                    else:
                        print(f"No owned elements found for machine {machine_id}.")
                        return 0
                else:
                    print(f"Machine with ID {machine_id} not found in the latest commit.")
                    return 0             

            return preventative_maintenance_activity_ids
        
        return 0  
        
    except SysMLV2Error as e:
        print(f"An API error occurred: {e}")
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")




if __name__ == "__main__":
    try:
        # Initialize the SysML v2 client
        client = SysMLV2Client(base_url=BASE_URL, bearer_token=BEARER_TOKEN)
        print("Client initialized.")
    except ValueError as e:
        print(f"Initialization error: {e}")

    latest_commit_id = getLatestCommitId(client, PROJECT_ID)

    #all elements in the latest commit
    elements = client.list_elements(PROJECT_ID, latest_commit_id)


    preventative_maintenance_activity_ids = findPreventativeMaintenanceActivities(client, PROJECT_ID, latest_commit_id, elements)

    if preventative_maintenance_activity_ids:
        print(f"Preventative Maintenance Activity IDs: {preventative_maintenance_activity_ids}")

        #going through every maintenance activity and getting there service intervals
        for activity_id in preventative_maintenance_activity_ids:
            activity = client.get_element(PROJECT_ID, activity_id, getLatestCommitId(client, PROJECT_ID))
            if activity:
                ownedRelationships = activity.get('ownedRelationship')
            else:
                print(f"Activity with ID {activity_id} not found.")

    else:
        print("No Preventative Maintenance Activities found.")