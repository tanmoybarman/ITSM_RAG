# ITSM RAG Chatbot Architecture

## System Overview

The ITSM (IT Service Management) RAG (Retrieval-Augmented Generation) Chatbot is a sophisticated AI-powered assistant that combines natural language processing with a knowledge base to provide accurate, context-aware responses about service incidents. This document outlines the system architecture, components, and data flow.

## Architecture Diagram

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#f0f0f0', 'primaryBorderColor': '#666666', 'lineColor': '#666666'}}}%%
flowchart TD
    %% Main Components
    subgraph "Chat UI (chat_ui.py)"
        A[Streamlit UI] -->|User Input| B[render_chat]
        A -->|Navigation| C[render_sidebar]
        A -->|Incident Management| D[render_incident_management]
        A -->|Create Ticket| E[render_create_ticket]
    end

    %% Core Functions
    B -->|Process Message| F[query_rag_chain]
    D -->|Fetch Incidents| G[fetch_incidents]
    D -->|Get Details| H[get_incident_details]
    D -->|Update Incident| I[update_incident]
    D -->|Close Incident| J[close_incident]
    E -->|Create New| K[create_incident]

    %% External Services
    subgraph "External Services"
        L[ServiceNow API] -->|Incident Data| G
        G -->|Formatted Data| L
        H -->|Incident Details| L
        I -->|Update Request| L
        J -->|Close Request| L
        K -->|New Incident| L

        M[Mistral AI] -->|LLM Responses| F
        F -->|Query| M

        N[Pinecone] -->|Vector Search| O[get_retriever]
        O -->|Context| F
    end

    %% Data Flow
    subgraph "Data Processing"
        P[load_json_file] -->|Raw Data| Q[process_incident_data]
        Q -->|Structured Data| R[create_vector_store]
        R -->|Vector DB| N
    end

    %% Styling
    classDef component fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef service fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    classDef data fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px

    class A,B,C,D,E component
    class G,H,I,J,K,L,M,N,O service
    class P,Q,R data
```

## Component Details

### 1. Chat UI (chat_ui.py)
The main user interface built with Streamlit that provides interaction capabilities.

**Key Functions:**
- `render_chat()`: Handles chat interface and message display
- `render_sidebar()`: Manages navigation and UI controls
- `render_incident_management()`: Displays and manages incident data
- `render_create_ticket()`: Provides form for new incident creation

### 2. Core Services
- **query_rag_chain**: Processes natural language queries using RAG
- **Incident Management**: Handles CRUD operations for incidents
  - `fetch_incidents`: Retrieves list of incidents
  - `get_incident_details`: Gets detailed incident information
  - `update_incident`: Updates existing incidents
  - `close_incident`: Closes resolved incidents
  - `create_incident`: Creates new incidents

### 3. External Integrations

#### ServiceNow API
- **Purpose**: Primary incident data source
- **Key Operations**:
  - Fetch incident lists and details
  - Create/update/close incidents
  - Real-time synchronization

#### Mistral AI
- **Role**: Large Language Model for natural language understanding
- **Features**:
  - Generates human-like responses
  - Processes complex queries
  - Understands context from retrieved documents

#### Pinecone
- **Function**: Vector database for semantic search
- **Features**:
  - Stores document embeddings
  - Enables efficient similarity search
  - Supports hybrid search (keyword + semantic)

### 4. Data Processing Pipeline
1. **Data Loading**:
   - `load_json_file`: Loads raw incident data from file/URL
   - `process_incident_data`: Structures and cleans the data

2. **Vector Store**:
   - `create_vector_store`: Converts documents to embeddings
   - `get_retriever`: Manages document retrieval with various search modes

## Data Flow

1. **Initialization**:
   - Load and process incident data
   - Create vector embeddings
   - Initialize RAG chain with Mistral AI

2. **Chat Interaction**:
   - User submits query
   - System retrieves relevant context
   - RAG generates response using context
   - Response displayed to user

3. **Incident Management**:
   - User views/updates incidents
   - Changes synchronized with ServiceNow
   - UI updates to reflect changes

## Dependencies

- **Core**:
  - Python 3.8+
  - Streamlit (Web UI)
  - LangChain (RAG framework)
  - Pinecone Client (Vector database)
  - Mistral AI (LLM)
  - HuggingFace (Embeddings)
  - Requests (HTTP client)

- **APIs**:
  - ServiceNow REST API
  - Mistral AI API
  - Pinecone API

## Configuration

Environment variables (`.env`):
```
PINECONE_API_KEY=your_pinecone_api_key
MISTRAL_API_KEY=your_mistral_api_key
```

## Usage

1. **Setup**:
   ```bash
   pip install -r requirements.txt
   cp .env.example .env  # Update with your API keys
   ```

2. **Run**:
   ```bash
   streamlit run chat_ui.py
   ```

3. **Access**:
   - Open browser to `http://localhost:8501`
   - Use the chat interface or navigate to incident management

## Troubleshooting

- **API Connection Issues**: Verify API keys in `.env`
- **Vector Search Problems**: Check if Pinecone index exists and is populated
- **LLM Response Quality**: Adjust temperature and max tokens in `rag_chain.py`

## License

[Specify your license here]
