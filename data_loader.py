"""Module for loading and processing incident data."""
import json
from typing import List, Dict, Any
from langchain.schema import Document
from langchain.document_loaders import JSONLoader
import pandas as pd

import requests
from typing import Union

def load_json_file(file_path: str) -> List[Document]:
    """
    Load JSON data from a file path or URL and return documents.
    
    Args:
        file_path: Either a local file path or a URL to fetch JSON data from
        
    Returns:
        List[Document]: List of documents loaded from the JSON data
    """
    # Check if the input is a URL
    if file_path.startswith(('http://', 'https://')):
        try:
            response = requests.get(file_path, timeout=30)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()
            
            # Create a temporary file to use with JSONLoader
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                json.dump(data, temp_file)
                temp_path = temp_file.name
            
            try:
                loader = JSONLoader(
                    file_path=temp_path,
                    jq_schema=".result.[],.countOfIncidentsByStatus.count[],.howToResolveBook.incidentResolutionByincidentDescription[],.sizeOfTotalIncident",
                    text_content=False,
                    json_lines=False,
                )
                return loader.load()
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
                    
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to fetch data from URL {file_path}: {str(e)}")
    else:
        # Original file loading logic
        loader = JSONLoader(
            file_path=file_path,
            jq_schema=".result.[],.countOfIncidentsByStatus.count[],.howToResolveBook.incidentResolutionByincidentDescription[],.sizeOfTotalIncident",
            text_content=False,
            json_lines=False,
        )
        return loader.load()

def dict_to_text_on_incident_details(d: Dict[str, Any]) -> str:
    """Convert incident details dictionary to formatted text."""
    return (
        f"the incident number {d.get('incidentNumber', '')}\n"
        f"has description: {d.get('incidentDescription', '').lower()}\n"
        f"with current state: {d.get('stateOfTicket', '').lower()}\n"
        f"and is currently assigned to: {d.get('incidentAssignedTo', 'no one').lower()}\n"
        f"and has priority of: {d.get('severity_priority', '').lower()}\n"
        f"and work notes provided for this incident number is: {d.get('workNotes', '').lower()}\n"
        f"resolution provided for this incident number {d.get('incidentNumber', '')} was: {d.get('howItWasResolved', '').lower()}\n"
        f"This incident number: {d.get('incidentNumber', '')} has the tag {d.get('incidentTag', '').lower()}\n"
    )

def dict_to_text_on_incident_by_state_count(d: Dict[str, Any]) -> str:
    """Convert incident state count dictionary to formatted text."""
    return (
        f"count of incident number with state: {d.get('incidentState', '')}\n"
        f"is: {d.get('incidentByStateCount', '')}\n"
    )

def dict_to_text_incident_description_resolution(d: Dict[str, Any]) -> str:
    """Convert incident resolution dictionary to formatted text."""
    return (
        f"incident with description: {d.get('incidentDescription', '')}\n"
        f"was closed and fixed with these steps provided as: {d.get('incidentResolution', '')}\n"
    )

def ensure_document(obj):
    """Ensure the object is a Document with page_content and metadata."""
    from langchain.schema import Document
    
    if isinstance(obj, Document):
        return obj
    elif isinstance(obj, dict):
        return Document(
            page_content=obj.get('page_content', ''),
            metadata=obj.get('metadata', {})
        )
    return Document(page_content=str(obj))

def process_incident_data(documents: List[Document]) -> List[Document]:
    """Process raw documents into structured document types."""
    # Ensure all inputs are Documents
    documents = [ensure_document(doc) for doc in documents]
    
    # Convert documents to a DataFrame for easier manipulation
    df = pd.DataFrame([{"content": doc.page_content, **doc.metadata} for doc in documents])
    df = df.drop_duplicates()
    cleaned_data = df.to_dict(orient="records")
    
    # Get the total number of incidents
    incident_count = int(list(cleaned_data[-1].values())[0])
    
    # Split data into different types with proper type checking
    def safe_json_loads(item):
        value = list(item.values())[0]
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value
        
    incident_data = [safe_json_loads(item) for item in cleaned_data[:incident_count]]
    state_count_data = [safe_json_loads(item) for item in cleaned_data[incident_count:incident_count+4]]
    resolution_data = [safe_json_loads(item) for item in cleaned_data[incident_count+4:len(cleaned_data)-1]]
    
    # Convert to Document objects with enhanced metadata
    incident_docs = []
    for item in incident_data:
        incident_number = item.get("incidentNumber", "")
        doc_content = dict_to_text_on_incident_details(item)
        doc_metadata = {
            "incident_number": incident_number,
            "incident_description": item.get("incidentDescription", ""),
            "status": item.get("stateOfTicket", "").lower(),
            "assigned_to": item.get("incidentAssignedTo", "").lower(),
            "work_notes": item.get("workNotes", ""),
            "resolution": item.get("howItWasResolved", ""),
            "tags": item.get("incidentTag", "").lower(),
            "type": "incident_details",
            "source": "incident_data"
        }
        incident_docs.append(Document(
            page_content=doc_content,
            metadata=doc_metadata
        ))
        
    
    state_count_docs = []
    for item in state_count_data:
        if not isinstance(item, dict):
            continue
        doc = Document(
            page_content=dict_to_text_on_incident_by_state_count(item),
            metadata={
                "type": "incident_status_count",
                "incidentStatus": str(item.get("incidentState", "")),
                "incidentByStatusCount": str(item.get("incidentByStateCount", ""))
            }
        )
        state_count_docs.append(doc)
    
    resolution_docs = []
    for item in resolution_data:
        if not isinstance(item, dict):
            continue
        doc = Document(
            page_content=dict_to_text_incident_description_resolution(item),
            metadata={
                "type": "incident_resolution",
                "incidentDescription": str(item.get("incidentDescription", "")),
                "incidentResolution": str(item.get("incidentResolution", ""))
            }
        )
        resolution_docs.append(doc)
    
    # Combine all documents and ensure they are Document objects
    all_docs = []
    
    # Add all documents with type checking
    for doc_list in [incident_docs, state_count_docs, resolution_docs]:
        for doc in doc_list:
            if not isinstance(doc, Document):
                doc = ensure_document(doc)
            all_docs.append(doc)
    '''
    # Add a document mapping incident numbers to their details
    incident_mapping = {}
    for doc in all_docs:
        if hasattr(doc, 'metadata') and isinstance(doc.metadata, dict):
            if "incident_number" in doc.metadata:
                incident_num = doc.metadata["incident_number"]
                if incident_num and doc.metadata.get("type") == "incident_details":
                    incident_mapping[incident_num] = doc.page_content
    
    # Add a document with all incident numbers and their summaries
    
    if incident_mapping:
        mapping_content = "\n".join([f"{num}: {desc[:100]}..." for num, desc in incident_mapping.items()])
        mapping_doc = Document(
            page_content=f"Incident number to description mapping:\n{mapping_content}",
            metadata={"type": "incident_mapping"}
        )
        all_docs.append(mapping_doc)
    '''
    
    # Final validation
    for doc in all_docs:
        if not hasattr(doc, 'page_content') or not hasattr(doc, 'metadata'):
            all_docs.remove(doc)
    
    return all_docs
