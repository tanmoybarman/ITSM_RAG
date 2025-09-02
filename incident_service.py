import json
import requests
from typing import Dict, List, Optional

def fetch_incidents() -> Optional[Dict]:
    """
    Fetch incidents from the ServiceNow API
    
    Returns:
        Optional[Dict]: JSON response containing incidents or None if there's an error
    """
    url = "https://cts-vibeappuk6402-5.azurewebsites.net/api/servicenow/distinctIncidents"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching incidents: {str(e)}")
        return None

def get_incident_details(incident_number: str) -> Optional[Dict]:
    """
    Fetch details for a specific incident
    
    Args:
        incident_number: The incident number to fetch details for
        
    Returns:
        Optional[Dict]: Incident details or None if there's an error
    """
    print("\n=== get_incident_details function called! ===")
    print(f"Incident number received: {incident_number}")
    url = f"https://cts-vibeappuk6402-5.azurewebsites.net/api/servicenow/incidentsByNumbers/{incident_number}"
    print(f"\n=== Fetching details for incident: {incident_number} ===")
    print(f"API URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Response status code: {response.status_code}")
        response.raise_for_status()
        
        # First, get the raw response text for debugging
        response_text = response.text
        print(f"Raw response text: {response_text[:500]}...")  # Print first 500 chars
        
        # Try to parse JSON
        try:
            response_data = json.loads(response_text)
            print("Successfully parsed JSON response")
            print(f"Response data type: {type(response_data)}")
            if isinstance(response_data, dict):
                print(f"Response keys: {list(response_data.keys())}")
            return response_data
            
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response: {str(e)}")
            print(f"Response content type: {type(response_text)}")
            print(f"Response length: {len(response_text)} characters")
            return {"error": "Invalid JSON response", "raw_response": response_text}
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Error fetching incident details: {str(e)}"
        print(error_msg)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_content = e.response.text
                print(f"Error response content: {error_content}")
                return {"error": error_msg, "response_content": error_content}
            except Exception as inner_e:
                print(f"Error reading error response: {str(inner_e)}")
        return {"error": error_msg}

def update_incident(incident_number: str, payload: dict) -> bool:
    """
    Update an incident in ServiceNow
    
    Args:
        incident_number: The incident number to update
        payload: Dictionary containing the fields to update
        
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"\n=== update_incident function called for incident: {incident_number} ===")
    print(f"Payload: {payload}")
    
    try:
        # First, get the sys_id for the incident
        url = f"https://dev276871.service-now.com/api/now/table/incident?sysparm_query=number={incident_number}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Basic YWRtaW46WlhTd2FRbnAvNjQk"  # Base64 encoded admin:ZXBpY29kZXI=
        }
        
        # Make the request with basic auth
        response = requests.get(url, headers=headers)
        
        response.raise_for_status()
        result = response.json()
        
        if not result.get('result') or len(result['result']) == 0:
            print(f"No incident found with number: {incident_number}")
            return False
            
        sys_id = result['result'][0]['sys_id']
        
        # Now update the incident
        update_url = f"https://dev276871.service-now.com/api/now/table/incident/{sys_id}"
        
        # Make the update request with basic auth
        update_response = requests.patch(update_url, 
                                      json=payload, 
                                      headers=headers)
        
        update_response.raise_for_status()
        print(f"Successfully updated incident {incident_number}")
        return True
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Error updating incident: {str(e)}"
        print(error_msg)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_content = e.response.text
                print(f"Error response content: {error_content}")
            except Exception as inner_e:
                print(f"Error reading error response: {str(inner_e)}")
        return False

def close_incident(incident_number: str) -> bool:
    """
    Close an incident in ServiceNow
    
    Args:
        incident_number: The incident number to close
        
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"\n=== close_incident function called for incident: {incident_number} ===")
    
    try:
        # First, get the sys_id for the incident
        url = f"https://dev276871.service-now.com/api/now/table/incident?sysparm_query=number={incident_number}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Basic YWRtaW46WlhTd2FRbnAvNjQk"  # Base64 encoded admin:ZXBpY29kZXI=
        }
        
        # Make the request with basic auth
        response = requests.get(url, headers=headers)
        
        response.raise_for_status()
        result = response.json()
        
        if not result.get('result') or len(result['result']) == 0:
            print(f"No incident found with number: {incident_number}")
            return False
            
        sys_id = result['result'][0]['sys_id']
        
        # Now close the incident
        close_url = f"https://dev276871.service-now.com/api/now/table/incident/{sys_id}"
        close_payload = {
            "state": "7",  # 7 is typically the state for 'Closed' in ServiceNow
            "incident_state": "7"
        }
        
        # Make the update request with basic auth
        update_response = requests.patch(close_url, 
                                      json=close_payload, 
                                      headers=headers)
        
        update_response.raise_for_status()
        print(f"Successfully closed incident {incident_number}")
        return True
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Error closing incident: {str(e)}"
        print(error_msg)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_content = e.response.text
                print(f"Error response content: {error_content}")
            except Exception as inner_e:
                print(f"Error reading error response: {str(inner_e)}")
        return False
    
    url = "https://cts-vibeappuk6402-5.azurewebsites.net/api/servicenow/updateIncidentState"
    headers = {"Content-Type": "application/json"}
    payload = {"sys_id": sys_id, "state": "6"}  # 6 typically means 'Resolved' in ServiceNow
    
    try:
        print(f"Closing incident {incident_number} (sys_id: {sys_id})")
        response = requests.put(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"Successfully closed incident {incident_number}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error closing incident {incident_number}: {str(e)}")
        return False

def create_incident(description: str, short_description: str) -> Dict:
    """
    Create a new incident in ServiceNow
    
    Args:
        description: Detailed description of the incident
        short_description: Short description of the incident
        
    Returns:
        Dict: Response from the API or error details
    """
    print(f"\n=== create_incident function called ===")
    url = "https://dev276871.service-now.com/api/now/table/incident"
    
    # Set up query parameters
    params = {
        'sysparm_display_value': 'true',
        'sysparm_exclude_reference_link': 'true',
        'sysparm_fields': 'number,description,short_description',
        'sysparm_input_display_value': 'true'
    }
    
    # Set up request headers
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': 'Basic YWRtaW46WlhTd2FRbnAvNjQk'
    }
    
    # Set up the request payload
    payload = {
        "description": description,
        "short_description": short_description,
        "caller_id": "",
        "assigned_to": "5137153cc611227c000bbd1bd8cd2007",
        "state": "2",  # 2 typically means 'In Progress' in ServiceNow
        "assignment_group": "d625dccec0a8016700a222a0f7900d06"
    }
    
    try:
        print(f"Creating new incident with description: {short_description}")
        response = requests.post(
            url,
            params=params,
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        
        # Parse and return the response
        response_data = response.json()
        print(f"Successfully created incident: {response_data.get('result', {}).get('number')}")
        return response_data
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Error creating incident: {str(e)}"
        print(error_msg)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_content = e.response.text
                print(f"Error response content: {error_content}")
                return {"error": error_msg, "response_content": error_content}
            except Exception as inner_e:
                print(f"Error reading error response: {str(inner_e)}")
        return {"error": error_msg}


def format_incidents(incidents_data: Dict) -> List[Dict]:
    """
    Format the incidents data for display and sort by 'Created On' in descending order
    
    Args:
        incidents_data: Raw incidents data from the API
        
    Returns:
        List[Dict]: Formatted and sorted list of incidents with selected fields
    """
    if not incidents_data or 'result' not in incidents_data:
        return []
        
    formatted_incidents = []
    for incident in incidents_data.get('result', []):
        formatted_incidents.append({
            "Number": incident.get('number', 'N/A'),
            "Description": incident.get('description', 'No description'),
            "Status": incident.get('state', 'N/A'),
            "Created On": incident.get('sys_created_on', 'N/A'),
            "raw_data": incident  # Store raw data for details
        })
    
    # Sort incidents by 'Created On' in descending order (newest first)
    formatted_incidents.sort(key=lambda x: x["Created On"], reverse=True)
    
    return formatted_incidents
