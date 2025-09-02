import streamlit as st
import os
import re
import time
import json
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from pprint import pprint
from main import initialize_system
from rag_chain import query_rag_chain
from incident_service import fetch_incidents, format_incidents, get_incident_details, close_incident, create_incident, update_incident

# Custom CSS for ChatGPT-like UI
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
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "initialized" not in st.session_state:
        st.session_state.initialized = False
    if "search_type" not in st.session_state:
        st.session_state.search_type = "general"
    if "show_ticket_details" not in st.session_state:
        st.session_state.show_ticket_details = False
    if "show_view_ticket_button" not in st.session_state:
        st.session_state.show_view_ticket_button = False
    if "ticket_short_description" not in st.session_state:
        st.session_state.ticket_short_description = ""
    if "ticket_description" not in st.session_state:
        st.session_state.ticket_description = ""
    if "show_update_options" not in st.session_state:
        st.session_state.show_update_options = False

def render_sidebar():
    """Render the sidebar with controls"""
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
        
        # Add reload data option
        reload_data = st.checkbox("Reload data from source", value=False,
                               help="Check this to force reload data from the source files")
        
        # Initialize button
        if not st.session_state.get("initialized", False):
            if st.button("🚀 Initialize AI System", use_container_width=True):
                with st.spinner("Initializing AI system (this may take a minute)..."):
                    try:
                        rag_chain = initialize_system(reload_data=reload_data)
                        if rag_chain:
                            st.session_state.rag_chain = rag_chain
                            st.session_state.initialized = True
                            st.rerun()
                        else:
                            st.error("Failed to initialize the AI chain. Please check the logs.")
                    except Exception as e:
                        st.error(f"Error during initialization: {str(e)}")
                        st.error("Please check your API keys and try again.")
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
    if st.button("🔄 Refresh Incidents"):
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
            st.session_state.incidents_data = fetch_incidents()
    
    if st.session_state.incidents_data:
        # Format the data using the service function
        formatted_incidents = format_incidents(st.session_state.incidents_data)
        
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
                if st.button("⏮️ First", disabled=st.session_state.page == 1):
                    st.session_state.page = 1
                    st.rerun()
                if st.button("⬅️ Previous", disabled=st.session_state.page == 1):
                    st.session_state.page -= 1
                    st.rerun()
            with col3:
                if st.button("Next ➡️", disabled=st.session_state.page == total_pages):
                    st.session_state.page += 1
                    st.rerun()
                if st.button("Last ⏭️", disabled=st.session_state.page == total_pages):
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
                                incident_details = get_incident_details(incident_number)
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
                                                        success = update_incident(incident_number, payload)
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
                                                            success = update_incident(incident_number, payload)
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
                                                            success = update_incident(incident_number, payload)
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
                    result = create_incident(description, short_description)
                    
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

def main():
    """Main application"""
    initialize_session_state()
    reload_data = render_sidebar()
    
    # Create tabs for navigation
    tab1, tab2, tab3 = st.tabs(["📋 Incident Management", "📞 Call in a Ticket", "💬 Chat"])
    
    # Clear form data when switching to the ticket creation tab
    if tab2:
        st.session_state.form_short_description = ""
        st.session_state.form_description = ""
    
    with tab1:
        render_incident_management()
        
    with tab2:
        render_create_ticket()
        
    with tab3:
        if st.session_state.get("initialized", False):
            render_chat()
        else:
            st.warning("⚠️ Please initialize the AI system from the sidebar to use the chat feature.")

if __name__ == "__main__":
    main()
