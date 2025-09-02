import streamlit as st
import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv
from main import initialize_system
from rag_chain import query_rag_chain

# Custom CSS for ChatGPT-like styling
st.markdown("""
<style>
    /* Main container */
    .main {
        max-width: 800px;
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
        margin: 0.5rem 0;
        padding: 1rem;
        border-radius: 0.5rem;
        max-width: 80%;
        line-height: 1.5;
    }
    
    .user-message {
        background-color: #f0f7ff;
        margin-left: auto;
        border-bottom-right-radius: 0.2rem;
    }
    
    .assistant-message {
        background-color: #f9f9f9;
        margin-right: auto;
        border-bottom-left-radius: 0.2rem;
    }
    
    /* Input area */
    .stTextInput>div>div>input {
        border-radius: 1.5rem;
        padding: 0.75rem 1rem;
        font-size: 1rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    /* Sidebar */
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
    
    /* Typing indicator */
    .typing {
        display: inline-block;
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
</style>
""", unsafe_allow_html=True)

# Load environment variables
load_dotenv()

# Set page config
st.set_page_config(
    page_title="Incident QA Bot",
    page_icon="❓",
    layout="wide"
)

def initialize_rag_chain():
    """Initialize the RAG chain and store it in session state"""
    if "rag_chain" not in st.session_state:
        with st.spinner("Initializing AI system (this may take a minute)..."):
            try:
                from pinecone import Pinecone
                from dotenv import load_dotenv
                import os
                
                load_dotenv()
                pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
                index_name = "incident-chatbot"
                
                if index_name not in pc.list_indexes().names():
                    raise RuntimeError(f"Vector index '{index_name}' does not exist. Please create it first.")
                
                # Initialize the RAG chain
                from main import initialize_system
                st.session_state.rag_chain = initialize_system(reload_data=False)
                return True
                
            except Exception as e:
                st.error(f"Failed to initialize AI system: {str(e)}")
                import traceback
                traceback.print_exc()
                return False
    return True

def show_initialization_button():
    """Show initialization button and handle its state"""
    if "initialized" not in st.session_state:
        st.session_state.initialized = False
    
    if not st.session_state.initialized:
        st.warning("The AI system is not initialized. Click the button below to start.")
        if st.button("🚀 Initialize AI System", type="primary"):
            with st.spinner("Initializing AI system (this may take a minute)..."):
                if initialize_rag_chain():
                    st.session_state.initialized = True
                    st.rerun()
                else:
                    st.error("Failed to initialize the AI system. Please check the console for errors.")
        return False
    return True

def main():
    st.title("🔍 Incident QA Assistant")
    
    # Check if system is initialized
    if not show_initialization_button():
        return  # Stop further execution if not initialized
    
    # Show welcome message
    st.markdown("""
    <div style='
        background-color: #f8f9fa; 
        padding: 24px; 
        border-radius: 12px; 
        margin: 20px 0;
        border-left: 5px solid #4a90e2;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    '>
        <h3 style='color: #2c3e50; margin-top: 0;'>Welcome to the Incident QA Assistant</h3>
        <p style='color: #34495e; margin-bottom: 8px;'>How can I help you today? Please select a search type:</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Add search type selection in sidebar with custom styling
    st.markdown("""
    <style>
        .sidebar .stButton button {
            font-size: 14px !important;
            padding: 8px 12px !important;
            margin: 4px 0 !important;
        }
        .sidebar .stMarkdown h3 {
            font-size: 1.1rem !important;
            margin-bottom: 12px !important;
        }
        .sidebar .stMarkdown p {
            font-size: 0.9rem !important;
            margin: 12px 0 !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("### 🔍 Search Modes")
        
        # Initialize search type in session state
        if "search_type" not in st.session_state:
            st.session_state.search_type = "incident_number"
        
        # Search mode buttons with consistent styling
        button_style = ""
        
        if st.button("Incident Number", use_container_width=True, 
                    help="Search using incident numbers (e.g., INC0000001)",
                    key="btn_incident"):
            st.session_state.search_type = "incident_number"
            
        if st.button("Resolution Search", use_container_width=True,
                   help="Search for incident resolutions from existing history",
                   key="btn_resolution"):
            st.session_state.search_type = "general"
            
        if st.button("General Search", use_container_width=True,
                   help="General search with diverse results",
                   key="btn_general"):
            st.session_state.search_type = "mmr_only"
        
        st.markdown("---")
        
        # Show selected search type with improved styling
        search_descriptions = {
            "incident_number": "Incident Number",
        
        # Initialize button
        if not st.session_state.get("initialized", False):
            if st.button("🚀 Initialize AI System", use_container_width=True):
                with st.spinner("Initializing AI system..."):
                    if initialize_rag_chain():
                        st.session_state.initialized = True
                        st.rerun()
                    else:
                        st.error("Failed to initialize the AI system.")
    
    # Main chat area
    st.markdown("""
        <div style='text-align: center; margin-bottom: 20px;'>
            <h1>Incident Assistant</h1>
            <p style='color: #666;'>Ask me anything about incidents</p>
        </div>
    """, unsafe_allow_html=True)
                        # Debug logging
                        print("\n--- DEBUG: Raw Response ---")
                        print(f"Type: {type(response)}")
                        print(f"Response: {response}")
                        
                        # Extract the answer from the response
                        if isinstance(response, dict):
                            if 'answer' in response:
                                response_text = str(response['answer'])
                            elif 'result' in response:
                                response_text = str(response['result'])
                            else:
                                response_text = str(response)
                        elif isinstance(response, str):
                            response_text = response
                        else:
                            response_text = str(response)
                        
                        # Extract the answer text from the response
                        if isinstance(response, dict) and 'answer' in response:
                            response_text = response['answer']
                        else:
                            response_text = str(response)
                        
                        # Clean up the response text
                        if isinstance(response_text, dict) and 'answer' in response_text:
                            response_text = response_text['answer']
                        
                        # Convert to string and clean up any remaining escape characters
                        response_text = str(response_text).replace('\\n', '\n').replace('\\"', '"')
                        
                        # Process markdown formatting
                        formatted_lines = []
                        for line in response_text.split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                                
                            # Handle bullet points and numbered lists
                            if any(line.lstrip().startswith(c) for c in ['-', '•', '*', '1.', '2.', '3.', '4.', '5.']):
                                # Ensure proper spacing after bullet points
                                if not line.startswith((' ', '\t')) and not line.startswith(('1.', '2.', '3.', '4.', '5.')):
                                    line = '  ' + line  # Add indentation for nested items
                                formatted_lines.append(line)
                            else:
                                formatted_lines.append(line)
                        
                        # Join lines with proper markdown line breaks
                        formatted_response = '  \n'.join(formatted_lines)
                        
                        # Display the formatted response with typing effect
                        full_response = ""
                        for char in formatted_response:
                            full_response += char
                            message_placeholder.markdown(full_response + "▌")
                            time.sleep(0.003)  # Smooth typing effect
                        
                        # Remove the cursor and display final response
                        message_placeholder.markdown(full_response)
                        
                        # Add assistant response to chat history
                        st.session_state.messages.append({"role": "assistant", "content": full_response.strip()})
                        
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
                        full_response = "Sorry, I encountered an error processing your request."
                        message_placeholder.markdown(full_response)
                        st.session_state.messages.append({"role": "assistant", "content": full_response})
    
    # Other Features Tab
    with tab2:
        st.markdown("## ⚙️ Other Features")
        st.markdown("This section is for additional features. Add your new features here!")
        
        # Example feature - can be replaced with actual features
        with st.expander("📊 Analytics Dashboard"):
            st.write("Incident analytics will be displayed here.")
            # Add your analytics components here
            
        with st.expander("📤 Export Data"):
            st.write("Export functionality will be available here.")
            # Add export functionality here

if __name__ == "__main__":
    main()
