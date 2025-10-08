import streamlit as st
import os
import re
import time
import json
import pandas as pd
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from pprint import pprint
from main import initialize_system
from rag_chain import query_rag_chain
import incident_service
import sys
from atlassian import Confluence
from typing import Optional, List, Dict, Any, Tuple
import asyncio

# Initialize RAG system once when the app starts
@st.cache_resource(show_spinner=False)
def get_rag_system():
    """Initialize and cache the RAG system.
    
    This function will only run once when the app starts or when the cache is cleared.
    """
    with st.spinner("Initializing RAG system..."):
        return initialize_system()

# Initialize the RAG system when the module loads
rag_chain = get_rag_system()


def update_confluence_table(confluence_table, row_index, column_name, new_value):
    """
    Update a cell in a Confluence table.
    
    Args:
        confluence_table: The Confluence table object
        row_index: Index of the row to update
        column_name: Name of the column to update
        new_value: New value to set
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Update the cell
        if not confluence_table.update_cell(
            row_index=row_index,
            column_name=column_name,
            new_value=str(new_value)  # Ensure value is a string
        ):
            st.error(f"Failed to update {column_name} for row {row_index}")
            return False
        
        # Save changes to Confluence
        if not confluence_table.save_changes():
            st.error("Failed to save changes to Confluence")
            return False
        
        return True
        
    except Exception as e:
        st.error(f"Error updating Confluence: {str(e)}")
        return False
st.markdown("""
<style>
    /* Main container */
    html, body, .main {
        font-size: 80% !important;
    }
    
    .main {
        max-width: 900px;
        margin: 0 auto;
        padding: 1rem;
    }
    
    /* Chat container */
    .chat-container {
        display: flex;
        flex-direction: column;
        height: 80vh;
        max-height: 80vh;
        overflow-y: auto;
        padding: 1rem;
        scroll-behavior: smooth;
    }
    
    /* Message bubbles */
    .message {
        padding: 0.75rem 1rem;
        border-radius: 1.2rem;
        margin: 0.25rem 0;
        max-width: 80%;
        line-height: 1.4;
        position: relative;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        color: #333333;  /* Dark gray text for better readability */
    }
    
    .user-message {
        background-color: #f0f7ff;
        margin-left: auto;
        border-bottom-right-radius: 0.2rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
    
    .assistant-message {
        background-color: #f5f5f5;
        margin-right: auto;
        border-bottom-left-radius: 0.3rem;
        color: #333333;  /* Ensure text is visible on light gray background */
    }
    
    /* Input area */
    .stTextInput>div>div>input {
        border-radius: 1.5rem !important;
        padding: 0.9rem 1.2rem !important;
        font-size: 1.05rem !important;
        box-shadow: 0 2px 15px rgba(0,0,0,0.1) !important;
        border: 1px solid #e0e0e0 !important;
    }
    
    /* Sidebar */
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
        border-right: 1px solid #eaeaea;
    }
    
    /* Sidebar headers */
    .sidebar .stMarkdown h3 {
        font-size: 1.1rem !important;
    }
    
    /* Typing indicator */
    .typing {
        display: inline-block;
        padding: 0.5rem 1rem;
    }
    
    .typing-dot {
        height: 8px;
        width: 8px;
        background-color: #bbb;
        border-radius: 50%;
        display: inline-block;
        margin: 0 2px;
        animation: typing 1.4s infinite ease-in-out both;
    }
    
    .typing-dot:nth-child(1) { animation-delay: 0s; }
    .typing-dot:nth-child(2) { animation-delay: 0.2s; }
    .typing-dot:nth-child(3) { animation-delay: 0.4s; }
    
    @keyframes typing {
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1); }
    }
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
</style>
""", unsafe_allow_html=True)

# Load environment variables
load_dotenv()

# Set page config
st.set_page_config(
    page_title="ChatGPT-Style Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

def display_typing_indicator():
    """Display a typing indicator"""
    return """
    <div class="typing">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
    </div>
    """

def initialize_session_state():
    """Initialize session state variables"""
    # Initialize messages list if it doesn't exist
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Track if we've initialized the RAG system in this session
    if "rag_initialized" not in st.session_state:
        st.session_state.rag_initialized = False
    
    # Initialize other UI state variables
    default_values = {
        "search_type": "general",
        "show_ticket_details": False,
        "show_view_ticket_button": False,
        "ticket_short_description": "",
        "ticket_description": "",
        "show_update_options": False,
        "active_tab": "Incidents",
        "rag_chain_initializing": False
    }
    
    # Set default values for any missing keys
    for key, default_value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def render_ods_icad():
    """Render the ODS & ICAD section with tagged incidents"""
    st.title("ODS & ICAD Incidents")
    st.write("This section displays incidents tagged with ODS or ICAD.")
    
    # Add a refresh button with a unique key
    if st.button("🔄 Refresh Incidents", key="refresh_incidents_btn"):
        st.rerun()
    
    # Create two columns for ODS and ICAD incidents
    col1, col2 = st.columns(2)
    
    # Fetch all tagged incidents (both ODS and ICAD)
    with st.spinner("Loading incidents..."):
        try:
            tagged_incidents = incident_service.fetch_incidents_by_tag()
            
            # Separate ODS and ICAD incidents
            ods_incidents = []
            icad_incidents = []
            
            if tagged_incidents and 'result' in tagged_incidents:
                for incident in tagged_incidents['result']:
                    # Check if the incident has ODS or ICAD tag
                    if 'sys_tags' in incident and incident['sys_tags']:
                        if 'ODS' in incident['sys_tags']:
                            ods_incidents.append(incident)
                        if 'ICAD' in incident['sys_tags']:
                            icad_incidents.append(incident)
            
        except Exception as e:
            st.error(f"Error loading incidents: {str(e)}")
            return
    
    # Display ODS incidents
    with col1:
        st.subheader("🔵 ODS Incidents")
        if ods_incidents:
            for incident in ods_incidents:
                with st.expander(f"{incident.get('number')}: {incident.get('short_description', 'No description')}"):
                    st.write(f"**Assignment Group:** {incident.get('assignment_group', 'N/A')}")
                    st.write(f"**Created:** {incident.get('sys_created_on', 'N/A')}")
                    st.write(f"**Description:** {incident.get('description', 'No description available')}")
        else:
            st.info("No ODS incidents found.")
    
    # Display ICAD incidents
    with col2:
        st.subheader("🟢 ICAD Incidents")
        if icad_incidents:
            for incident in icad_incidents:
                with st.expander(f"{incident.get('number')}: {incident.get('short_description', 'No description')}"):
                    st.write(f"**Assignment Group:** {incident.get('assignment_group', 'N/A')}")
                    st.write(f"**Created:** {incident.get('sys_created_on', 'N/A')}")
                    st.write(f"**Description:** {incident.get('description', 'No description available')}")
        else:
            st.info("No ICAD incidents found.")

def check_admin_auth():
    """Check if admin is authenticated"""
    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False
    return st.session_state.admin_authenticated

def authenticate_admin():
    """Handle admin authentication"""
    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False
    
    if not st.session_state.admin_authenticated:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🔒 Admin Access")
        password = st.sidebar.text_input("Admin Password:", type="password", key="admin_pass")
        if st.sidebar.button("Authenticate"):
            # In production, use a proper password hashing mechanism
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            # Get password from environment variable or use a default for demonstration
            admin_password_hash = os.getenv("ADMIN_PASSWORD_HASH", "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8")  # default: 'password'
            if hashed_password == admin_password_hash:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.sidebar.error("Incorrect password")
        return False
    return True

def render_sidebar():
    """Render the sidebar with controls"""
    # Initialize reload_data with default value
    reload_data = False
    
    with st.sidebar:
        st.title("⚙️ Settings")
        
        # Initialize search type in session state if not exists
        if 'search_type' not in st.session_state:
            st.session_state.search_type = 'general'
        
        # Get current search mode display text based on current search type
        search_type_to_display = {
            'general': "Looking for quick guide to resolve from past incident history?",
            'incident_number': "Query with Incident Numbers if you have them handy",
            'mmr_only': "For other query"
        }
        
        # Search mode selection
        st.markdown("### 🔍 Search Mode")
        search_mode = st.radio(
            "Select search mode:",
            [
                "Looking for quick guide to resolve from past incident history?",
                "Query with Incident Numbers if you have them handy",
                "For other query"
            ],
            index=["general", "incident_number", "mmr_only"].index(st.session_state.search_type),
            key="search_type_display",
            label_visibility="collapsed"
        )
        
        # Map search mode to internal type
        search_type_map = {
            "Looking for quick guide to resolve from past incident history?": "general",
            "Query with Incident Numbers if you have them handy": "incident_number",
            "For other query": "mmr_only"
        }
        
        # Update search type without clearing messages
        st.session_state.search_type = search_type_map[search_mode]
        
        st.markdown("---")
        
        # App info
        st.markdown("### ℹ️ About")
        st.markdown("This is an AI assistant for querying incident data.")
        
        # Show admin controls section if authenticated
        if check_admin_auth() or authenticate_admin():
            st.markdown("### 🔧 Admin Controls")
            
            # Add reload data option (only visible to authenticated admins)
            reload_data = st.checkbox("Reload data from source", value=False,
                                   help="Check this to force reload data from the source files")
            
            # Show initialization button if not already initializing
            if not st.session_state.rag_initialized and not st.session_state.rag_chain_initializing:
                if st.button("🚀 Initialize AI System", use_container_width=True, key="init_ai_system_btn"):
                    st.session_state.rag_chain_initializing = True
                    st.rerun()
            
            # Handle initialization in a separate block to show spinner
            if st.session_state.rag_chain_initializing and not st.session_state.rag_initialized:
                with st.spinner("Initializing AI system (this may take a minute)..."):
                    try:
                        rag_chain = initialize_system(reload_data=reload_data)
                        if rag_chain:
                            st.session_state.rag_initialized = True
                            st.session_state.rag_chain_initializing = False
                            st.rerun()
                        else:
                            st.error("Failed to initialize the AI chain. Please check the logs.")
                            st.session_state.rag_chain_initializing = False
                    except Exception as e:
                        st.error(f"Error during initialization: {str(e)}")
                        st.error("Please check your API keys and try again.")
                        st.session_state.rag_chain_initializing = False
            
            # Show success message if initialized
            if st.session_state.rag_initialized:
                st.success("✅ AI System Initialized")
                if st.button("🔄 Reinitialize AI System", key="reinit_ai_system_btn"):
                    st.session_state.rag_initialized = False
                    st.rerun()
                    
                # Add logout button for admin
                if st.button("🔒 Logout Admin", key="admin_logout_btn"):
                    st.session_state.admin_authenticated = False
                    st.rerun()
        else:
            # Show a message that admin authentication is required
            st.info("🔒 Admin authentication required for system controls.")
            reload_data = False  # Ensure reload_data is defined in this branch
        return reload_data

def render_chat():
    """Render the chat interface"""
    # Header
    st.markdown("""
        <div style='text-align: center; margin: 1rem 0 2rem 0;'>
            <h1 style='font-size: 2.2rem; margin-bottom: 0.5rem;'>Incident Assistant</h1>
            <p style='color: #666; font-size: 1.1rem;'>How can I help you today?</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Use the globally cached RAG chain
    if not rag_chain:
        st.error("Failed to initialize the AI system. Please restart the application.")
        return
        
    # Store the rag_chain in session state for other functions to use
    st.session_state.rag_chain = rag_chain
    
    # Chat container
    chat_container = st.container()
    
    # Display chat messages using st.chat_message for better state management
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(f"""
                    <div class='message {message["role"]}-message'>
                        {message["content"]}
                    </div>
                """, unsafe_allow_html=True)
    
    # Chat input at the bottom using Streamlit's chat_input
    st.markdown("""
        <style>
            .stChatFloatingInputContainer {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                background: white;
                padding: 1rem;
                box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
                z-index: 1000;
            }
            .message {
                padding: 0.75rem 1rem;
                border-radius: 1.2rem;
                margin: 0.25rem 0;
                max-width: 80%;
                line-height: 1.4;
                white-space: pre-wrap;
                word-wrap: break-word;
            }
            .user-message {
                background-color: #f0f7ff;
                margin-left: auto;
                border-bottom-right-radius: 0.2rem;
                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
                color: #333333;
            }
            .assistant-message {
                background-color: #f5f5f5;
                margin-right: auto;
                border-bottom-left-radius: 0.3rem;
                color: #333333;
            }
        </style>
    """, unsafe_allow_html=True)
    
    if prompt := st.chat_input("Message Incident Assistant..."):
        # Skip empty queries
        if not prompt or not prompt.strip():
            st.warning("Please enter a valid question.")
            st.stop()
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with chat_container:
            st.markdown(f"""
                <div class='message-container user'>
                    <div class='message user-message'>
                        {prompt}
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        # Display assistant response
        with chat_container:
            message_placeholder = st.empty()
            message_placeholder.markdown(display_typing_indicator(), unsafe_allow_html=True)
            
            try:
                # Get response from RAG chain
                response = query_rag_chain(
                    st.session_state.rag_chain,
                    prompt,
                    search_mode=st.session_state.search_type
                )
                
                # Debug: Print the raw response
                print("\n=== RAW RESPONSE FROM RAG CHAIN ===")
                print(f"Type: {type(response)}")
                print("Response content:")
                pprint(response)
                print("=" * 40, "\n")
                
                # Extract the response text, handling the nested dictionary structure
                if isinstance(response, dict):
                    # Handle the case where answer is a nested dictionary
                    if 'answer' in response and isinstance(response['answer'], dict) and 'answer' in response['answer']:
                        response_text = response['answer']['answer']
                    # Handle the case where answer is a direct string
                    elif 'answer' in response and isinstance(response['answer'], str):
                        response_text = response['answer']
                    # Fallback to string representation if structure is unexpected
                    else:
                        response_text = str(response)
                else:
                    response_text = str(response)
                
                # Clean up the response text
                response_text = response_text.strip()
                    
                if isinstance(response_text, str):
                    # First replace escaped newlines with actual newlines
                    response_text = response_text.replace('\\n', '\n')
                    # Ensure consistent bullet point formatting
                    response_text = response_text.replace('- ', '• ')
                    # Replace any remaining escaped quotes
                    response_text = response_text.replace('\\"', '"')
                    # Clean up any double newlines at the start
                    response_text = response_text.lstrip('\n')
                
                # Clear the placeholder first
                message_placeholder.empty()
                
                # Create a container for the assistant's message
                with message_placeholder.container():
                    # Display the full response using Streamlit's markdown
                    st.markdown("""
                    <style>
                    .message-container {
                        display: flex;
                        margin: 0.5rem 0;
                    }
                    
                    .message-container.user {
                        justify-content: flex-end;
                    }
                    
                    .message-container.assistant {
                        justify-content: flex-start;
                    }
                    
                    .assistant-message {
                        background-color: #f5f5f5;
                        padding: 0.75rem 1rem;
                        border-radius: 1.2rem;
                        margin: 0.25rem 0;
                        max-width: 80%;
                        line-height: 1.4;
                        color: #333333;
                        border-bottom-left-radius: 0.3rem;
                        white-space: pre-wrap;
                        word-wrap: break-word;
                    }
                    </style>
                    <div style='display: flex; justify-content: flex-start; margin: 0.5rem 0;'>
                        <div class='assistant-message'>
                    """, unsafe_allow_html=True)
                    
                    # Display the response text with proper formatting
                    st.markdown(response_text)
                    
                    # Close the divs
                    st.markdown("""
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Add the full response to chat history
                st.session_state.messages.append({"role": "assistant", "content": response_text})
                
            except Exception as e:
                error_msg = f"Sorry, I encountered an error: {str(e)}"
                message_placeholder.markdown(f"""
                    <div style='display: flex; justify-content: flex-start;'>
                        <div class='message assistant-message error'>
                            {error_msg}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
    
    st.markdown("</div>", unsafe_allow_html=True)

def render_incident_management():
    """Render the Incident Management section"""
    st.markdown("""
        <div style='text-align: center; margin: 1rem 0 2rem 0;'>
    """, unsafe_allow_html=True)
    
    # Initialize session state variables
    if 'incidents_data' not in st.session_state:
        st.session_state.incidents_data = None
    if 'show_details' not in st.session_state:
        st.session_state.show_details = False
    if 'selected_incident_number' not in st.session_state:
        st.session_state.selected_incident_number = None
    if 'scroll_position' not in st.session_state:
        st.session_state.scroll_position = 0
    if 'last_incident_details' not in st.session_state:
        st.session_state.last_incident_details = None
    if 'page' not in st.session_state:
        st.session_state.page = 1
    if 'rows_per_page' not in st.session_state:
        st.session_state.rows_per_page = 10
    
    # Add a refresh button
    if st.button("🔄 Refresh Incidents", key="refresh_incidents_list_btn"):
        st.session_state.incidents_data = None
        st.session_state.show_details = False
        st.session_state.selected_incident_number = None
        st.rerun()
    
    # Restore scroll position if available
    if 'last_scroll_position' in st.session_state and st.session_state.last_scroll_position:
        st.components.v1.html(st.session_state.last_scroll_position, height=0)
        st.session_state.last_scroll_position = None
    
    # Fetch incidents if not already in session state
    if st.session_state.incidents_data is None:
        with st.spinner("Loading incidents..."):
            st.session_state.incidents_data = incident_service.fetch_incidents()
    
    if st.session_state.incidents_data:
        # Format the data using the service function
        formatted_incidents = incident_service.format_incidents(st.session_state.incidents_data)
        
        if formatted_incidents:
            # Add pagination controls
            col1, col2 = st.columns([1, 3])
            with col1:
                st.session_state.rows_per_page = st.selectbox(
                    'Rows per page:',
                    [5, 10, 20, 50],
                    index=1,
                    key='rows_per_page_select'
                )
            
            # Calculate total pages
            total_pages = (len(formatted_incidents) + st.session_state.rows_per_page - 1) // st.session_state.rows_per_page
            
            # Ensure page is within valid range
            if st.session_state.page < 1:
                st.session_state.page = 1
            elif st.session_state.page > total_pages and total_pages > 0:
                st.session_state.page = total_pages
            
            # Calculate start and end indices for current page
            start_idx = (st.session_state.page - 1) * st.session_state.rows_per_page
            end_idx = min(start_idx + st.session_state.rows_per_page, len(formatted_incidents))
            
            # Get current page data
            display_data = formatted_incidents[start_idx:end_idx]
            
            # Display pagination info
            st.caption(f"Showing {start_idx + 1}-{end_idx} of {len(formatted_incidents)} incidents")
            
            # Pagination controls
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("⏮️ First", disabled=st.session_state.page == 1, key="pagination_first_btn"):
                    st.session_state.page = 1
                    st.rerun()
                if st.button("⬅️ Previous", disabled=st.session_state.page == 1, key="pagination_prev_btn"):
                    st.session_state.page -= 1
                    st.rerun()
            with col3:
                if st.button("Next ➡️", disabled=st.session_state.page == total_pages, key="pagination_next_btn"):
                    st.session_state.page += 1
                    st.rerun()
                if st.button("Last ⏭️", disabled=st.session_state.page == total_pages, key="pagination_last_btn"):
                    st.session_state.page = total_pages
                    st.rerun()
            
            # Display current page number and total pages
            with col2:
                st.markdown(f"<div style='text-align: center; margin: 10px 0;'>Page {st.session_state.page} of {total_pages if total_pages > 0 else 1}</div>", 
                           unsafe_allow_html=True)
            # Create display data without raw_data and get current page data
            display_data = [
                {k: v for k, v in incident.items() if k != 'raw_data'}
                for incident in formatted_incidents[start_idx:end_idx]
            ]
            
            # Display the table with clickable incident numbers
            st.markdown("""
                <style>
                    .sticky-header {
                        position: sticky;
                        top: 0;
                        background: #f0f4f8;  /* Softer blue-gray background */
                        z-index: 100;
                        padding: 12px 0;
                        margin: 0 0 10px 0;
                        border-bottom: 2px solid #d9e2ec;
                        color: #243b53;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                    }
                    .sticky-header .row {
                        font-weight: 600;
                        color: #243b53;
                    }
                    .incident-row {
                        border-bottom: 1px solid #f0f2f6;
                        padding: 10px 0;
                    }
                    .incident-row:hover {
                        background-color: #f8f9fa;
                    }
                </style>
                <div class='sticky-header'>
                    <div class='row' style='display: flex; padding: 5px 15px;'>
                        <div style='flex: 1; color: #2d3748;'>Incident #</div>
                        <div style='flex: 3; color: #2d3748;'>Description</div>
                        <div style='flex: 1; color: #2d3748;'>Status</div>
                        <div style='flex: 2; color: #2d3748;'>Created On</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Show incident details in a modal if an incident is selected (at the top of the table)
            if (st.session_state.get('selected_incident_number') and 
                st.session_state.get('show_details', False)):
                # Find the selected incident in the current page
                selected_incident = next(
                    (inc for inc in display_data 
                     if inc['Number'] == st.session_state.selected_incident_number),
                    None
                )
                
                if selected_incident:
                    # Store the incident number before loading details
                    incident_number = selected_incident["Number"]
                    
                    # Only fetch details if we don't have them in session state or if it's a different incident
                    if (st.session_state.last_incident_details is None or 
                        st.session_state.last_incident_details.get('number') != incident_number):
                        with st.spinner("Loading incident details..."):
                            try:
                                incident_details = incident_service.get_incident_details(incident_number)
                                if isinstance(incident_details, dict) and 'result' in incident_details and incident_details['result']:
                                    incident_data = incident_details['result'][0]
                                    st.session_state.last_incident_details = incident_data
                                else:
                                    st.error("No details found for this incident.")
                                    if st.button("Close Ticket", key=f"incident_management_modal_close_btn_{incident_number}"):
                                        st.session_state.show_details = False
                                        st.session_state.selected_incident_number = None
                                        st.session_state.last_incident_details = None
                                        st.rerun()
                            except Exception as e:
                                st.error(f"Error loading incident details: {str(e)}")
                                if st.button("Close Ticket", key=f"incident_management_modal_close_btn_{incident_number}"):
                                    st.session_state.show_details = False
                                    st.session_state.selected_incident_number = None
                                    st.session_state.last_incident_details = None
                                    st.rerun()
                    
                    # Display the modal with incident details in a centered expander
                    if st.session_state.last_incident_details:
                        incident_data = st.session_state.last_incident_details
                        
                        # Create a centered container for the expander
                        col1, col2, col3 = st.columns([1, 6, 1])
                        with col2:  # Middle column (6 units wide)
                            with st.expander(f"🔍 Incident Details: {incident_number}", expanded=True):
                                # Add some vertical space
                                st.markdown("<div style='margin: 10px 0;'></div>", unsafe_allow_html=True)
                                
                                # Create two columns for the details
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    st.markdown("### ℹ️ Basic Information")
                                    st.markdown(f"**Number:** {incident_data.get('number', 'N/A')}")
                                    st.markdown(f"**Status:** {incident_data.get('state', 'N/A')}")
                                    st.markdown(f"**Priority:** {incident_data.get('priority', 'N/A')}")
                                    st.markdown(f"**Category:** {incident_data.get('category', 'N/A')}")
                                
                                with col_b:
                                    st.markdown("### 👤 Assignment")
                                    st.markdown(f"**Assigned To:** {incident_data.get('assigned_to', 'N/A')}")
                                    st.markdown(f"**Assignment Group:** {incident_data.get('assignment_group', 'N/A')}")
                                    st.markdown(f"**Opened At:** {incident_data.get('opened_at', 'N/A')}")
                                
                                # Work notes section with improved styling and contrast
                                work_notes = incident_data.get('work_notes')
                                if work_notes and str(work_notes).strip():
                                    st.markdown("---")
                                    st.markdown("### 📝 Work Notes")
                                    st.markdown(
                                        f"<div style='background-color: #f0f2f6; padding: 15px; border-radius: 5px; border-left: 4px solid #4a90e2; color: #1a1a1a; line-height: 1.6; white-space: pre-wrap;'>{work_notes}</div>", 
                                        unsafe_allow_html=True
                                    )
                                
                                # Action buttons at the bottom
                                st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
                                
                                # Create columns for buttons
                                btn_col1, btn_col2 = st.columns([1, 1])
                                
                                with btn_col1:
                                    if st.button("✕ Close Details", 
                                           key=f"modal_details_close_{incident_number}",
                                           use_container_width=True,
                                           type="secondary"):
                                        st.session_state.show_details = False
                                        st.session_state.selected_incident_number = None
                                        st.session_state.last_incident_details = None
                                        st.rerun()
                                
                                with btn_col2:
                                    current_state = incident_data.get('state', '').lower()
                                    if current_state not in ['closed', 'resolved']:
                                        if st.button("🔄 Want to update this!",
                                                   key=f"modal_ticket_update_{incident_number}",
                                                   use_container_width=True,
                                                   type="primary"):
                                            st.session_state.show_update_options = True
                                            st.rerun()
                                    
                                    # Show update options if the update button was clicked
                                    if st.session_state.get('show_update_options', False):
                                        st.markdown("### Update Options")
                                        
                                        # Always show Resolve option
                                        with st.expander("✅ Resolve this!", expanded=False):
                                            with st.form(f"resolve_form_{incident_number}"):
                                                close_notes = st.text_area("Resolution Notes", 
                                                                        placeholder="Enter resolution details",
                                                                        key=f"resolve_notes_{incident_number}")
                                                submitted_resolve = st.form_submit_button("Submit Resolution")
                                                if submitted_resolve and close_notes:
                                                    with st.spinner("Updating incident..."):
                                                        payload = {
                                                            "state": "6",  # Resolved state
                                                            "close_notes": close_notes,
                                                            "close_code": "Solution provided"
                                                        }
                                                        success = incident_service.update_incident(incident_number, payload)
                                                        if success:
                                                            st.success(f"Incident {incident_number} has been resolved.")
                                                            st.session_state.show_update_options = False
                                                            st.session_state.last_incident_details = None
                                                            st.session_state.incidents_data = None
                                                            st.rerun()
                                                        else:
                                                            st.error("Failed to update incident. Please try again.")
                                        
                                        # Show different options based on current state
                                        if current_state.lower() == 'on hold':
                                            # For incidents already on hold, show "Update Hold Notes"
                                            with st.expander("📝 Update Hold Notes", expanded=True):
                                                with st.form(f"update_hold_form_{incident_number}"):
                                                    hold_reason = st.text_input("Hold Reason", 
                                                                             placeholder="Enter updated hold reason",
                                                                             key=f"update_hold_reason_{incident_number}")
                                                    work_notes = st.text_area("Work Notes",
                                                                           placeholder="Enter updated work notes",
                                                                           key=f"update_work_notes_{incident_number}")
                                                    submitted_update_hold = st.form_submit_button("Update Hold Notes")
                                                    if submitted_update_hold and hold_reason and work_notes:
                                                        with st.spinner("Updating hold notes..."):
                                                            payload = {
                                                                "state": "3",  # Keep as On Hold
                                                                "hold_reason": hold_reason,
                                                                "work_notes": work_notes
                                                            }
                                                            success = incident_service.update_incident(incident_number, payload)
                                                            if success:
                                                                st.success(f"Hold notes for incident {incident_number} have been updated.")
                                                                st.session_state.show_update_options = False
                                                                st.session_state.last_incident_details = None
                                                                st.session_state.incidents_data = None
                                                                st.rerun()
                                                            else:
                                                                st.error("Failed to update hold notes. Please try again.")
                                        else:
                                            # For other statuses, show "Put on Hold"
                                            with st.expander("⏸️ Put on Hold", expanded=False):
                                                with st.form(f"hold_form_{incident_number}"):
                                                    hold_reason = st.text_input("Hold Reason", 
                                                                             placeholder="Enter reason for hold",
                                                                             key=f"hold_reason_{incident_number}")
                                                    work_notes = st.text_area("Work Notes",
                                                                           placeholder="Enter work notes",
                                                                           key=f"work_notes_{incident_number}")
                                                    submitted_hold = st.form_submit_button("Submit Hold Request")
                                                    if submitted_hold and hold_reason and work_notes:
                                                        with st.spinner("Updating incident..."):
                                                            payload = {
                                                                "state": "3",  # On Hold state
                                                                "hold_reason": hold_reason,
                                                                "work_notes": work_notes
                                                            }
                                                            success = incident_service.update_incident(incident_number, payload)
                                                            if success:
                                                                st.success(f"Incident {incident_number} has been put on hold.")
                                                                st.session_state.show_update_options = False
                                                                st.session_state.last_incident_details = None
                                                                st.session_state.incidents_data = None
                                                                st.rerun()
                                                            else:
                                                                st.error("Failed to update incident. Please try again.")
                                    
                                    # Show status if already closed/resolved
                                    elif current_state in ['closed', 'resolved']:
                                        st.markdown("<div style='text-align: center; padding: 0.5rem; color: #38a169;'>✅ Ticket {current_state.title()}</div>", 
                                                  unsafe_allow_html=True)
                                    elif current_state == 'on hold':
                                        st.markdown("<div style='text-align: center; padding: 0.5rem; color: #d69e2e;'>⏸️ On Hold</div>", 
                                                  unsafe_allow_html=True)

                            # Add some bottom margin
                            st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

            # Create a container for the table
            table_container = st.container()

            with table_container:
                # Display each incident as a row (only for current page)
                for incident in display_data:
                    # Create a clickable row for each incident
                    col1, col2, col3, col4, col5, col6 = st.columns([1, 3, 1, 2, 1, 1])
                    with col1:
                        st.markdown(f"<div style='padding: 8px 0;'>{incident['Number']}</div>", unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"<div style='padding: 8px 0;'>{incident['Description']}</div>", unsafe_allow_html=True)
                    with col3:
                        st.markdown(f"<div style='padding: 8px 0;'>{incident['Status']}</div>", unsafe_allow_html=True)
                    with col4:
                        st.markdown(f"<div style='padding: 8px 0;'>{incident['Created On']}</div>", unsafe_allow_html=True)
                    with col5:
                        if st.button("View", 
                                   key=f"incident_list_view_{incident['Number']}", 
                                   type="secondary",
                                   help=f"View details for incident {incident['Number']}"):
                            st.session_state.scroll_position = """
                                <script>
                                    window.parent.document.getElementById('root').scrollTop = document.body.scrollTop || document.documentElement.scrollTop;
                                </script>
                            """
                            st.session_state.show_details = True
                            st.session_state.selected_incident_number = incident["Number"]
                            st.rerun()
                    # Removed Close Ticket button from main list as per user request
                
                # Add some bottom margin
                st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

            
            # The incident details modal is now shown at the top of the table

def render_create_ticket():
    """Render the Create Ticket form"""
    # Initialize variables
    if 'new_ticket_number' not in st.session_state:
        st.session_state.new_ticket_number = None
    if 'show_ticket_details' not in st.session_state:
        st.session_state.show_ticket_details = False
    if 'form_cleared' not in st.session_state:
        st.session_state.form_cleared = False

    st.markdown("## 📞 Call in a Ticket")
    st.markdown("Please fill out the form below to create a new ticket.")
    
    # Create the form with a unique key
    form_key = "create_ticket_form"
    if st.session_state.form_cleared:
        form_key += "_cleared"
    
    with st.form(form_key):
        # Use a different key when we want to clear the form
        short_desc_key = "short_desc_cleared" if st.session_state.form_cleared else "short_desc"
        desc_key = "detailed_desc_cleared" if st.session_state.form_cleared else "detailed_desc"
        
        short_description = st.text_area(
            "Short Description*", 
            placeholder="Briefly describe the issue", 
            max_chars=160,
            help="A short summary of the issue (required)",
            key=short_desc_key
        )
        
        description = st.text_area(
            "Detailed Description", 
            placeholder="Provide detailed information about the issue",
            help="Include any relevant details, error messages, or steps to reproduce",
            key=desc_key
        )
        
        # Add some spacing
        st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)
        
        # Form submission button
        submitted = st.form_submit_button("Submit Ticket", type="primary")
        
        if submitted:
            if not short_description.strip():
                st.error("Please provide a short description for the ticket.")
            else:
                with st.spinner("Creating your ticket..."):
                    result = incident_service.create_incident(description, short_description)
                    
                    if result and 'result' in result and 'number' in result['result']:
                        ticket_number = result['result']['number']
                        st.session_state.new_ticket_number = ticket_number
                        st.session_state.show_ticket_details = True
                        st.session_state.show_view_ticket_button = True
                        st.session_state.ticket_short_description = short_description
                        st.session_state.ticket_description = description
                        # Set flag to clear form on next render
                        st.session_state.form_cleared = not st.session_state.form_cleared
                        st.rerun()
                    else:
                        error_msg = result.get('error', 'Unknown error occurred')
                        st.error(f"❌ Failed to create ticket. Error: {error_msg}")
                        if 'response_content' in result:
                            st.text_area("Error Details", result['response_content'], height=200)
    
    # Display success message with ticket number in a professional format
    if st.session_state.show_ticket_details:
        with st.container():
            st.markdown(f"""
                <div style='background-color: #e8f5e9; 
                            border-left: 4px solid #4caf50;
                            padding: 12px 20px;
                            margin: 16px 0;
                            border-radius: 4px;'>
                    <p style='margin: 0; color: #1b5e20; font-weight: 500;'>
                        Ticket #{st.session_state.new_ticket_number} has been created successfully
                    </p>
                </div>
            """, unsafe_allow_html=True)
            
            # Show ticket details in a clean, professional format
            st.markdown("### Ticket Details")
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**Ticket Number:**")
                st.markdown("**Status:**")
                st.markdown("**Short Description:**")
                if st.session_state.ticket_description:
                    st.markdown("**Description:**")
            
            with col2:
                st.markdown(f"{st.session_state.new_ticket_number}")
                st.markdown("In Progress")
                st.markdown(f"{st.session_state.ticket_short_description}")
                if st.session_state.ticket_description:
                    st.markdown(f"{st.session_state.ticket_description}")
        
        # Auto-clear the success message after a delay
        st.session_state.show_ticket_details = False

def update_confluence_page(confluence, page_id, title, new_content):
    """Update the Confluence page with new content"""
    try:
        import requests
        from base64 import b64encode
        
        # Get current page to preserve other content
        current_page = confluence.get_page_by_id(page_id, expand='body.storage,version')
        
        # Get parent ID if available
        parent_id = None
        if current_page.get('ancestors'):
            parent_id = current_page['ancestors'][-1].get('id')
        
        # Prepare the update payload
        update_data = {
            'id': page_id,
            'type': 'page',
            'title': title,
            'body': {
                'storage': {
                    'value': new_content,
                    'representation': 'storage'
                }
            },
            'version': {
                'number': current_page.get('version', {}).get('number', 0) + 1,
                'message': f'Updated via ITSM_RAG at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            }
        }
        
        # Add parent if available
        if parent_id:
            update_data['ancestors'] = [{'id': parent_id}]
        
        # Get credentials from environment
        email = os.getenv('CONFLUENCE_EMAIL')
        api_token = os.getenv('CONFLUENCE_API_TOKEN')
        
        if not email or not api_token:
            raise ValueError("Confluence email or API token not found in environment variables")
        
        # Create auth header
        auth_string = f"{email}:{api_token}"
        auth_token = b64encode(auth_string.encode()).decode()
        
        # Update the page using requests
        url = f"{confluence.url}/rest/api/content/{page_id}"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {auth_token}'
        }
        
        response = requests.put(
            url,
            headers=headers,
            json=update_data
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to update page: {response.status_code} - {response.text}")
            
        return response.json()
    except Exception as e:
        st.error(f"Failed to update Confluence page: {str(e)}")
        if 'current_page' in locals():
            st.error(f"Debug - Page data: {current_page}")
        return None

def render_confluence_table():
    """Render the Confluence table from the specified page with editing capabilities"""
    
    # Skip if not in the Confluence tab to prevent unnecessary processing
    if 'active_tab' not in st.session_state or st.session_state.get('active_tab') != 'Confluence':
        return
        
    try:
        from atlassian import Confluence
        from dotenv import load_dotenv
        import os
        import pandas as pd
        from datetime import datetime
        
        load_dotenv()
        
        # Get Confluence configuration from environment variables
        confluence_url = os.getenv('CONFLUENCE_URL')
        email = os.getenv('CONFLUENCE_EMAIL')
        api_token = os.getenv('CONFLUENCE_API_TOKEN')
        space_key = os.getenv('CONFLUENCE_SPACE_KEY')
        page_id = os.getenv('CONFLUENCE_PAGE_ID')
        
        if not all([confluence_url, email, api_token, space_key, page_id]):
            st.error("Missing Confluence configuration in .env file")
            return
            
        # Initialize Confluence client
        confluence = Confluence(
            url=confluence_url,
            username=email,
            password=api_token,
            cloud=True
        )
        
        # Get page content with version information
        try:
            page = confluence.get_page_by_id(page_id, expand='version,body.storage')
            original_content = page['body']['storage']['value']
            
            # Display page title and last updated time if available
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(page.get('title', 'Untitled Page'))
            with col2:
                version_info = page.get('version', {})
                if 'when' in version_info:
                    from datetime import datetime, timezone
                    import pytz
                    
                    # Parse the UTC timestamp
                    utc_time = datetime.fromisoformat(version_info['when'].replace('Z', '+00:00'))
                    
                    # Convert to IST (UTC+5:30)
                    ist = pytz.timezone('Asia/Kolkata')
                    est = pytz.timezone('US/Eastern')
                    
                    # Format the times
                    utc_str = utc_time.strftime('%Y-%m-%d %H:%M:%S UTC')
                    ist_str = utc_time.astimezone(ist).strftime('%Y-%m-%d %H:%M:%S IST')
                    est_str = utc_time.astimezone(est).strftime('%Y-%m-%d %H:%M:%S EST')
                    
                    # Display in a more compact format
                    st.caption(f"Last updated: {ist_str} | {est_str}")
                else:
                    st.caption("Last update time not available")
                    
        except Exception as e:
            st.error(f"Error loading page content: {str(e)}")
            st.info("Please check if the page exists and you have the correct permissions.")
            return
        
        # Add a refresh button
        if st.button("🔄 Refresh Page"):
            st.rerun()
        
        # Display the page content
        st.markdown("---")
        st.markdown("### Page Content")
        
        # Extract and display tables using pandas
        try:
            # Read all tables from the HTML content
            from io import StringIO
            try:
                tables = pd.read_html(StringIO(original_content))
            except DeprecationWarning:
                st.warning("Deprecation warning: pd.read_html() will be deprecated in a future version. Using html5lib as parser.")
                tables = pd.read_html(StringIO(original_content), flavor='html5lib')
            
            if not tables:
                st.info("No tables found on this Confluence page.")
                return
                
            # Store original and edited tables if not already in session state
            if 'original_tables' not in st.session_state:
                st.session_state.original_tables = tables
                st.session_state.edited_tables = [df.copy() for df in tables]
            
            # Ensure edited_tables has the same number of tables as original
            if len(st.session_state.edited_tables) != len(tables):
                st.session_state.edited_tables = [df.copy() for df in tables]
            
            # Display each table with editing capabilities
            for i, df in enumerate(st.session_state.original_tables):
                with st.expander(f"📊 Table {i+1}", expanded=True):
                    # Use a unique key for each table to maintain state
                    table_key = f"table_{i}_{hash(frozenset(df.columns))}"
                
                # Initialize session state for this table if it doesn't exist
                if table_key not in st.session_state:
                    # Convert to dict of lists for better performance
                    st.session_state[table_key] = {
                        'data': df.to_dict('records'),
                        'columns': list(df.columns)
                    }
                    
                # Get current data from session state
                table_data = st.session_state[table_key]
                
                # Check if the first column is a serial column
                first_col = table_data['columns'][0].lower()
                is_serial_col = any(term in first_col for term in ['serial', 'sr', 'sno', 'sl no'])
                
                # Create a DataFrame from the session state data
                display_df = pd.DataFrame(table_data['data'])
                
                # Update serial numbers if needed
                if is_serial_col and not display_df.empty:
                    display_df[display_df.columns[0]] = range(1, len(display_df) + 1)
                
                # Create a container for the table with custom CSS to improve editing experience
                st.markdown("""
                <style>
                    /* Remove dimming effect */
                    .stDataFrame {
                        --shadow: none !important;
                    }
                    
                    /* Style the edit cells */
                    .stDataFrame [data-testid='stDataFrameCell'] {
                        padding: 0.5rem;
                        background-color: white !important;
                    }
                    
                    /* Make the table more compact and readable */
                    .stDataFrame {
                        font-size: 0.9rem;
                        margin: 0 !important;
                    }
                    
                    /* Remove focus outline that causes dimming */
                    .stDataFrame:focus, .stDataFrame:focus-within {
                        outline: none !important;
                        box-shadow: none !important;
                    }
                    
                    /* Style for editable cells */
                    .stDataFrame [data-testid='stDataFrameCell']:focus-within {
                        border: 1px solid #4CAF50 !important;
                        box-shadow: 0 0 0 1px #4CAF50 !important;
                    }
                    
                    /* Remove modal background */
                    .stDataFrame [role='dialog'] {
                        background-color: transparent !important;
                        box-shadow: none !important;
                    }
                </style>
                """, unsafe_allow_html=True)
                
                # Initialize session state for tracking table changes
                if f'table_{i}_needs_update' not in st.session_state:
                    st.session_state[f'table_{i}_needs_update'] = False
                
                # Removed Add Row and Remove Last Row buttons as requested
                
                # Display the data editor with optimized settings
                with st.container():
                    # Use a form to handle cell edits without rerunning the entire script
                    # Use a container to group the table editor and auto-save changes
                    with st.container():
                        edited_df = st.data_editor(
                            display_df,
                            num_rows="fixed",
                            use_container_width=True,
                            key=f"table_editor_{i}",
                            column_config={
                                col: st.column_config.Column(
                                    col,
                                    help=f"Edit {col} values",
                                    width="medium"
                                ) for col in table_data['columns']
                            },
                            hide_index=True,
                            disabled=False
                        )
                        
                        # Auto-save changes when table is edited
                        if not edited_df.equals(display_df):
                            # Update the serial column if it exists
                            if is_serial_col and not edited_df.empty:
                                edited_df[edited_df.columns[0]] = range(1, len(edited_df) + 1)
                            
                            # Update the session state
                            st.session_state.edited_tables[i] = edited_df
                            st.session_state[table_key]['data'] = edited_df.to_dict('records')
                
                # Single column for the validate button
                col1, _ = st.columns([1, 5])
                with col1:
                    if st.button(f"🔍 Validate Incidents", key=f"validate_table_{i}"):
                        try:
                            # Get the current table data
                            current_table = st.session_state.edited_tables[i]
                            
                            # Initialize Confluence client
                            confluence = Confluence(
                                url=os.getenv('CONFLUENCE_URL'),
                                username=os.getenv('CONFLUENCE_EMAIL'),
                                password=os.getenv('CONFLUENCE_API_TOKEN'),
                                cloud=True
                            )
                            
                            # Create a status container for validation progress
                            status_container = st.status("Validating incidents...", expanded=True)
                            
                            # Create a progress bar
                            progress_bar = st.progress(0)
                            
                            # Show available columns in debug mode
                            # st.write("Debug - Available columns in the table:", [str(col) for col in current_table.columns.tolist()])
                            # st.write("Debug - First few rows:", current_table.head(2).to_dict('records'))
                            
                            # Define the exact column names from the table
                            url_col = 'Url'  # Matches the exact case in your table
                            type_col = 'Type'  # Matches the exact case in your table
                            
                            # Check if required columns exist
                            if url_col not in current_table.columns or type_col not in current_table.columns:
                                st.error(f"Required columns not found. Need '{url_col}' and '{type_col}'. Found columns: {current_table.columns.tolist()}")
                                return
                            
                            # Prepare URL data for validation
                            url_data = []
                            ticket_numbers = []
                            
                            for idx, row in current_table.iterrows():
                                # Get the ticket number for updating the correct row
                                ticket_number = row.get('Ticket', row.get('ticket', row.get('Incident', f'Row {idx+1}')))
                                url_value = row.get(url_col, '')
                                type_value = row.get(type_col, '')
                                
                                if url_value and type_value:  # Only add if we have both URL and type
                                    url_data.append((url_value, type_value, ticket_number))
                                ticket_numbers.append(ticket_number)
                            
                            # Initialize Confluence table updater
                            from confluence_table import ConfluenceTable
                            try:
                                page_id = os.getenv('CONFLUENCE_PAGE_ID')
                                if not page_id:
                                    st.error("CONFLUENCE_PAGE_ID is not set in .env file")
                                    return
                                confluence_table = ConfluenceTable(confluence, page_id)
                                if not confluence_table.load_table():
                                    st.error("Failed to load table from Confluence page")
                                    return
                                st.session_state.confluence_table = confluence_table
                            except Exception as e:
                                st.error(f"Failed to initialize Confluence table: {str(e)}")
                                return
                            
                            # Initialize async validator
                            from async_url_validator import AsyncURLValidator
                            validator = AsyncURLValidator(max_concurrent_requests=10, timeout=15)
                            
                            # Run async validation
                            import asyncio
                            
                            # Create a new event loop for the async operation
                            def run_async_validation():
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    return loop.run_until_complete(validator.validate_urls(url_data))
                                finally:
                                    loop.close()
                            
                            # Show progress while validating
                            with st.spinner("Validating URLs (this may take a moment)..."):
                                validation_results = run_async_validation()
                            
                            # Create a mapping of ticket numbers to their results for easier lookup
                            results_by_ticket = {}
                            for result in validation_results:
                                if not result:
                                    continue
                                ticket = result.get('ticket')
                                if ticket:
                                    results_by_ticket[ticket] = result
                            
                            # Process each row in the table and update with validation results
                            formatted_results = []
                            for idx, (_, row) in enumerate(current_table.iterrows()):
                                ticket_number = ticket_numbers[idx] if idx < len(ticket_numbers) else f'Row {idx+1}'
                                result = results_by_ticket.get(ticket_number, {})
                                
                                # Create the result entry
                                formatted_result = {
                                    'ticket': ticket_number,
                                    'status': result.get('status', 'Not Validated'),
                                    'details': result.get('details', 'No validation performed'),
                                    'valid': result.get('valid', False)
                                }
                                formatted_results.append(formatted_result)
                                
                                # Update the status in the table
                                if 'Status' in current_table.columns:
                                    current_table.at[idx, 'Status'] = formatted_result['status']
                                    
                                    # Update the status in Confluence
                                    if 'confluence_table' in st.session_state:
                                        if update_confluence_table(st.session_state.confluence_table, idx, 'Status', formatted_result['status']):
                                            update_confluence_table(st.session_state.confluence_table, idx, 'Updated_Ts_Lastrun', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                                            st.toast(f"Updated ticket {ticket_number} in Confluence", icon="✅")
                                        else:
                                            st.error(f"Failed to update status for ticket {ticket_number}")
                                
                                # Update details if the column exists
                                if 'details' in current_table.columns:
                                    current_table.at[idx, 'details'] = formatted_result['details']
                            
                            # Update the session state with the modified table
                            st.session_state.edited_tables[i] = current_table
                            validation_results = formatted_results

                            # Show validation results
                            with status_container:
                                st.write("## Validation Results")
                                results_df = pd.DataFrame(validation_results)
                                
                                # Add color coding for status
                                def color_status(val):
                                    if val == 'Valid':
                                        return 'color: green; font-weight: bold'
                                    elif val == 'Error':
                                        return 'color: red; font-weight: bold'
                                    elif val == 'Skipped':
                                        return 'color: orange; font-weight: bold'
                                    return ''
                                
                                # Display the results
                                st.dataframe(
                                    results_df.style.applymap(color_status, subset=['status']),
                                    width='stretch'
                                )
                                
                                # Show summary
                                valid_count = sum(1 for r in validation_results if r.get('valid', False))
                                total_count = len(validation_results)
                                
                                st.success(
                                    f"Validation complete! {valid_count} of {total_count} incidents are valid."
                                )
                                
                                # Update the progress bar to 100%
                                progress_bar.progress(100)
                            
                        except Exception as e:
                            with status_container:
                                st.error(f"Error during validation: {str(e)}")
                            
                        # Ensure the spinner is stopped after validation is complete
                        status_container.update(state="complete")
                
                # Removed download button as requested
                    
                st.markdown("---")
            
        except Exception as e:
            st.error(f"Error processing Confluence tables: {str(e)}")
            st.info("The page may not contain any tables or they might be in an unsupported format.")
            # Show raw content for debugging
            if 'original_content' in locals():
                with st.expander("📝 View Raw Page Content"):
                    st.code(original_content, language='html')
            return
            
    except Exception as e:
        st.error(f"Error loading Confluence data: {str(e)}")
        st.info("Please check your Confluence configuration in the .env file")
        if 'original_content' in locals():
            with st.expander("View Raw Page Content"):
                st.code(original_content, language='html')
        return

def main():
    """Main application"""
    initialize_session_state()
    reload_data = render_sidebar()
    
    # Create tabs for navigation
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Incidents", 
        "📞 New Ticket", 
        "💬 Chat", 
        "🔍 ODS & ICAD",
        "🌐 Confluence"
    ])
    
    # Track active tab and render content
    with tab1:
        st.session_state.active_tab = "Incidents"
        st.caption("View and manage all reported incidents and their statuses")
        render_incident_management()
        
    with tab2:
        st.session_state.active_tab = "New Ticket"
        st.caption("Create a new support ticket for any issues or requests")
        # Clear form data when switching to the ticket creation tab
        if 'form_short_description' not in st.session_state:
            st.session_state.form_short_description = ""
            st.session_state.form_description = ""
        render_create_ticket()
        
    with tab3:
        st.session_state.active_tab = "Chat"
        st.caption("Chat with the AI assistant for quick help and information")
        
        # The RAG system is now initialized when the app starts via the cached function
        # Just render the chat interface directly
        render_chat()
            
    with tab4:
        st.session_state.active_tab = "ODS & ICAD"
        st.caption("Access ODS and ICAD data and related incident information")
        render_ods_icad()
        
    with tab5:
        st.session_state.active_tab = "Confluence"
        st.caption("This page is linked to confluence page and allows you to view the recurring Incidents related to InfoAPI backend services on a real-time basis. You can also validate the Incidents using the Validate button provided at the bottom of the table. This will update the status of the Incidents in Confluence table.")
        render_confluence_table()

if __name__ == "__main__":
    main()
