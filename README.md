# Incident Management RAG System

A Retrieval-Augmented Generation (RAG) system for querying and analyzing IT incident data using Pinecone, HuggingFace embeddings, and Mistral AI.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   Create a `.env` file in the project root with the following variables:
   ```
   PINECONE_API_KEY=your_pinecone_api_key
   MISTRAL_API_KEY=your_mistral_api_key
   ```

3. **Data**:
   Place your `incidentListCleaned.json` file in the `data/` directory.

## Usage

### Interactive Mode
Run the system in interactive mode to enter queries one by one:
```bash
python main.py
```

### data load 
```bash
python main.py --reload    
```

### Single Query Mode
Run a single query directly from the command line:
```bash
python main.py "your query here"
```

### Example Queries
- "What is the status of incident INC0000039?"
- "List all incidents with high priority"
- "How many incidents are in the 'In Progress' state?"
- "What was the resolution for incident INC0007001?"

## Project Structure
- `main.py`: Entry point for the application
- `data_loader.py`: Handles loading and processing incident data
- `vector_store.py`: Manages Pinecone vector store operations
- `rag_chain.py`: Implements the RAG chain with Mistral AI
- `requirements.txt`: Project dependencies

## Notes
- The first run will take longer as it processes documents and creates the vector store.
- Subsequent runs will be faster as the vector store is persisted in Pinecone.
- Ensure you have sufficient Pinecone credits for vector storage and queries.


## Streamlit App

- Run the streamlit app using the following command:
```bash
python -m streamlit run --server.port=8502 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false --server.fileWatcherType=poll app.py

python -m streamlit run chat_ui.py
```