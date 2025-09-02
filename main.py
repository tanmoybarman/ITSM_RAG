"""
RAG-based Incident Management System - Main Module

This module serves as the entry point for the RAG (Retrieval-Augmented Generation)
system designed for querying and retrieving information about service incidents.
It handles system initialization, command-line argument parsing, and the main
interactive query loop.
"""
# Standard library imports
import os  # For file system operations and environment variables
import sys  # For system-specific parameters and functions
import argparse  # For parsing command-line arguments
# Third-party imports
from dotenv import load_dotenv  # For loading environment variables from .env file

# Add the project root to the Python path to enable absolute imports
# This allows importing modules from the project root directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Local application imports
from data_loader import load_json_file, process_incident_data  # For loading and processing incident data
from vector_store import create_vector_store, get_retriever, get_embeddings  # For vector storage and retrieval
from rag_chain import create_rag_chain, query_rag_chain  # For RAG chain creation and querying
from pinecone import Pinecone  # For Pinecone client operations
from langchain_pinecone import PineconeVectorStore  # For Pinecone vector store operations

def initialize_system(reload_data: bool = False):
    """
    Initialize and configure all components of the RAG system.
    
    This function:
    1. Loads environment variables
    2. Validates API keys
    3. Optionally loads and processes incident data if reload_data is True or index doesn't exist
    4. Sets up the vector store and retriever
    5. Initializes the RAG chain
    
    Args:
        reload_data: If True, forces reloading of data into the vector store
        
    Returns:
        A configured RAG chain ready for querying
        
    Raises:
        ValueError: If required API keys are not found in environment variables
    """
    try:
        # Load environment variables from .env file if it exists
        load_dotenv()
        
        # Get API keys from environment variables
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        mistral_api_key = os.getenv("MISTRAL_API_KEY")
        
        if not pinecone_api_key or not mistral_api_key:
            raise ValueError("Missing required API keys. Please set PINECONE_API_KEY and MISTRAL_API_KEY in .env file")
        
        # Initialize Pinecone client
        pc = Pinecone(api_key=pinecone_api_key)
        index_name = "incident-chatbot"
        
        # Check if we need to load and process data
        if reload_data or index_name not in pc.list_indexes().names():
            print("Loading and processing incident data...")
            # Load and process documents
            documents = load_json_file("data/incidentListCleaned.json")
            if not documents:
                raise ValueError("No documents were loaded from the data file")
                
            processed_docs = process_incident_data(documents)
            if not processed_docs:
                raise ValueError("No documents were processed")
                
            print(f"Processed {len(processed_docs)} documents")
            
            # Create vector store with processed documents
            print("Creating vector store...")
            vector_store = create_vector_store(processed_docs, pinecone_api_key)
            if not vector_store:
                raise RuntimeError("Failed to create vector store")
        else:
            print("Using existing vector store...")
            # Just connect to the existing vector store
            embeddings = get_embeddings()
            vector_store = PineconeVectorStore(
                index_name=index_name,
                embedding=embeddings
            )
        
        # Set up retriever and RAG chain
        print("Initializing retriever with confidence threshold...")
        # Set a higher confidence threshold to reduce hallucinations
        retriever = get_retriever(vector_store, min_confidence=0.5)
        
        print("Initializing RAG chain...")
        rag_chain = create_rag_chain(retriever, mistral_api_key)
        
        if not rag_chain:
            raise RuntimeError("Failed to initialize RAG chain")
            
        print("System initialization complete!")
        return rag_chain
        
    except Exception as e:
        print(f"Error initializing system: {str(e)}")
        raise

def main():
    """
    Main function that orchestrates the RAG system's operation.
    
    Handles:
    - Command-line argument parsing
    - System initialization
    - Interactive query loop or single query processing
    - Response formatting and display
    """
    # Set up command-line argument parser
    parser = argparse.ArgumentParser(description='Query the RAG system for incident information.')
    # Make query argument optional to support both CLI and interactive modes
    parser.add_argument('query', nargs='?', help='Your query about the incidents')
    parser.add_argument('--reload', action='store_true', help='Force reload of data into vector store')
    args = parser.parse_args()
    
    # Initialize the RAG system components
    print("Initializing RAG system...")
    try:
        rag_chain = initialize_system(reload_data=args.reload)
    except ValueError as e:
        print(f"Error initializing system: {e}")
        sys.exit(1)
    
    # Check if query was provided as command-line argument
    if not args.query:
        # Interactive mode: Enter a loop to process multiple queries
        print("\nEnter your query (or 'exit' to quit):")
        while True:
            # Get user input
            query = input("> ")
            
            # Exit condition for the interactive loop
            if query.lower() in ['exit', 'quit']:
                break
                
            # Skip empty queries
            if not query.strip():
                continue
                
            try:
                # Process the query through the RAG chain with default search mode
                response = query_rag_chain(rag_chain, query, search_mode='general')
                
                # Display the response
                print("\nResponse:")
                print("=" * 80)  # Visual separator
                print(response["answer"])  # The generated answer
                print("=" * 80)
                
                # If context documents are available, display their metadata
                if 'context' in response and response['context']:
                    print("\nSources used:")
                    for i, doc in enumerate(response['context']):
                        # Get document type from metadata, default to 'unknown'
                        doc_type = doc.metadata.get('type', 'unknown')
                        # Display first 200 characters of each source document
                        print(f"{i+1}. [Type: {doc_type}] {doc.page_content[:]}...")
            
            except Exception as e:
                # Handle any errors during query processing
                print(f"Error processing query: {str(e)}")
            
            # Prompt for next query
            print("\nEnter another query (or 'exit' to quit):")
    else:
        # Non-interactive mode: Process a single query from command line
        try:
            # Process the provided query with default search mode
            response = query_rag_chain(rag_chain, args.query, search_mode='general')
            
            # Display the response
            print("\nResponse:")
            print("=" * 80)
            print(response["answer"])
            print("=" * 80)
            
            # Display context sources if available
            if 'context' in response and response['context']:
                print("\nSources used:")
                for i, doc in enumerate(response['context']):
                    doc_type = doc.metadata.get('type', 'unknown')
                    print(f"{i+1}. [Type: {doc_type}] {doc.page_content[:200]}...")
                    
        except Exception as e:
            # Handle any errors during query processing
            print(f"Error processing query: {str(e)}")

# Standard Python idiom to ensure main() only runs when script is executed directly
# (not when imported as a module)
if __name__ == "__main__":
    main()  # Execute the main function
