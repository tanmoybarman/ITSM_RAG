"""
Vector Store Module for Document Retrieval

This module handles the creation and management of vector embeddings using Pinecone,
allowing for efficient similarity search over document collections.
"""
import os
from typing import List
# Import HuggingFace for generating document embeddings
from langchain.embeddings import HuggingFaceEmbeddings
# Pinecone for vector storage and similarity search
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
# Document schema for type hints
from langchain.schema import Document

def get_embeddings():
    """
    Initialize and configure HuggingFace embeddings model.
    
    Returns:
        HuggingFaceEmbeddings: Configured embeddings model
        
    Note:
        Uses 'all-MiniLM-L6-v2' which provides a good balance between
        performance and resource usage for general text embeddings.
    """
    model_name = "sentence-transformers/all-mpnet-base-v2"
    # Initialize the embeddings model with default parameters
    return HuggingFaceEmbeddings(model_name=model_name)

def initialize_pinecone_index(pinecone_api_key: str, index_name: str = "incident-chatbot") -> None:
    """
    Initialize a Pinecone vector index if it doesn't already exist.
    
    Args:
        pinecone_api_key: API key for Pinecone service
        index_name: Name of the index to create/check (default: "incident-chatbot")
    """
    # Initialize Pinecone client with provided API key
    pc = Pinecone(api_key=pinecone_api_key)
    
    # Check if index already exists, create if it doesn't
    if index_name not in pc.list_indexes().names():
        # Create a new index with configuration matching our embeddings
        pc.create_index(
            name=index_name,
            dimension=768,  # Fixed dimension for all-MiniLM-L6-v2 embeddings
            metric="cosine",  # Cosine similarity for text embeddings
            spec=ServerlessSpec(cloud="aws", region="us-east-1")  # Serverless configuration
        )

def create_vector_store(
    documents: List[Document],
    pinecone_api_key: str,
    index_name: str = "incident-chatbot"
) -> PineconeVectorStore:
    """
    Create a Pinecone vector store from a list of documents.
    
    Args:
        documents: List of Document objects to be vectorized and stored
        pinecone_api_key: API key for Pinecone service
        index_name: Name of the Pinecone index to use (default: "incident-chatbot")
        
    Returns:
        PineconeVectorStore: Configured vector store ready for similarity search
    """
    # Get the embeddings model for converting text to vectors
    embeddings = get_embeddings()
    
    # Ensure the Pinecone index exists and is properly configured
    initialize_pinecone_index(pinecone_api_key, index_name)
    
    # Create and return the vector store with documents
    # This will automatically chunk, embed, and upload the documents to Pinecone
    return PineconeVectorStore.from_documents(
        documents=documents,  # List of documents to store
        embedding=embeddings,  # Embeddings model to use
        index_name=index_name  # Target Pinecone index
    )

def get_retriever(vector_store: PineconeVectorStore, min_confidence: float = 0.5, search_mode: str = 'general'):
    """
    Create a retriever from a vector store with confidence-based filtering.
    
    Args:
        vector_store: Initialized PineconeVectorStore instance
        min_confidence: Minimum similarity score (0-1) for results to be included
        search_mode: The search mode to use. Options are:
                   - 'incident_number': Search by exact incident number match
                   - 'general': General semantic search with confidence filtering and MMR
                   - 'mmr_only': Use only MMR for diverse results
        
    Returns:
        A retriever function that returns documents based on the specified search mode
        and confidence threshold.
        
    Note:
        Uses a combination of similarity search, metadata filtering, and MMR
        to ensure accurate and diverse retrieval of incident information.
    """
    def custom_retriever(query: str, search_mode_override: str = None) -> List[Document]:
        # Use override if provided, otherwise use instance search_mode
        current_search_mode = search_mode_override if search_mode_override else search_mode
        print(f"\n[DEBUG] Custom retriever called with search_mode_override: {search_mode_override}")
        print(f"[DEBUG] Using search mode: {current_search_mode}")
        print(f"[DEBUG] Query: {query}")
        
        # Common function for MMR search
        def run_mmr_search(query, k=3, fetch_k=15, lambda_mult=0.6):
            return vector_store.max_marginal_relevance_search(
                query=query,
                k=k,
                fetch_k=fetch_k,
                lambda_mult=lambda_mult
            )
        def run_mmr_search_mmr_only(query, k=20, fetch_k=40, lambda_mult=0.6):
            return vector_store.max_marginal_relevance_search(
                query=query,
                k=k,
                fetch_k=fetch_k,
                lambda_mult=lambda_mult
            )
            
        # Common function for similarity search with optional metadata filtering
        def run_similarity_search(query, k=10, filter_dict=None):
            params = {
                "query": query,
                "k": k
            }
            if filter_dict:
                params["filter"] = filter_dict
            return vector_store.similarity_search_with_score(**params)
            
        def log_results(results, label):
            """Helper to log search results"""
            print(f"\n{label} ({len(results)}):")
            for i, doc in enumerate(results):
                if isinstance(doc, tuple):  # Handle (doc, score) tuples
                    doc, score = doc
                    print(f"  Result {i+1} - Score: {score:.4f}")
                else:
                    print(f"  Result {i+1}:")
                source = doc.metadata.get('type', 'unknown')
                print(f"    Source: {source}")
                print(f"    Content: {doc.page_content}")
        
        import re
            
        try:
            # Handle different search modes
            if current_search_mode == 'incident_number':
                # Extract incident numbers from query
                incident_numbers = re.findall(r'INC\d+', query.upper())
                if not incident_numbers:
                    print("No incident numbers found in query")
                    return []
                    
                print(f"Found {len(incident_numbers)} incident numbers in query")
                results = []
                
                # For exact incident number matches, bypass vector similarity
                for inc_num in incident_numbers:
                    try:
                        # Directly query by incident number using metadata filter
                        matches = vector_store.similarity_search(
                            query=inc_num,
                            k=5,  # Increased to get more potential matches
                            filter={"incident_number": inc_num}
                        )
                        
                        print(f"Found {len(matches)} exact matches for incident {inc_num}")
                        if matches:
                            # Print the matches for debugging
                            print("Match metadata:")
                            for i, doc in enumerate(matches):
                                print(f"  Match {i+1} - Metadata: {doc.metadata}")
                            # Assign high confidence score (1.0) for exact matches
                            results.extend([(doc, 1.0) for doc in matches])
                            print(f"Added {len(matches)} exact matches for {inc_num}")
                    except Exception as e:
                        print(f"Error searching for incident {inc_num}: {str(e)}")
                
                if results:
                    print(f"Found {len(results)} confident matches for incident numbers")
                    # Sort by score (descending) and return just the documents
                    results.sort(key=lambda x: x[1], reverse=True)
                    return [doc for doc, _ in results]
                    
                print("No confident matches found for incident numbers")
                return []
                
            elif current_search_mode == 'mmr_only':
                print("Using MMR-only search mode")
                mmr_results = run_mmr_search_mmr_only(
                    query=query,
                    k=10,
                    fetch_k=20,
                    lambda_mult=0.6
                )
                
                log_results(mmr_results, "MMR-only results")
                print(f"\nReturning {len(mmr_results)} MMR results")
                return mmr_results
                
            else:  # Default to general search
                print("Using general search with confidence filtering")
                
                # Define metadata filter for relevant document types
                metadata_filter = {
                    "type": {"$in": ["incident_details", "incident_resolution"]}
                }
                
                # First get similarity scores with metadata filter
                results_with_scores = run_similarity_search(
                    query=query, 
                    k=10,  # Increased k to account for the metadata filtering
                    filter_dict=metadata_filter
                )
                
                # Print all scores and sources for debugging
                log_results(results_with_scores, f"Raw similarity scores (filtered by type: {metadata_filter})")
                
                # Filter by confidence
                filtered_results = [(doc, score) for doc, score in results_with_scores 
                                 if score >= min_confidence]
                                         
                print(f"\nKept {len(filtered_results)}/{len(results_with_scores)} results after confidence filtering (threshold: {min_confidence})")
                
                if not filtered_results:
                    print("No results met the confidence threshold, falling back to top 2 results")
                    if results_with_scores:
                        # Sort by score in descending order and take top 2
                        results_with_scores.sort(key=lambda x: x[1], reverse=True)
                        filtered_results = results_with_scores[:2]
                        print(f"Using top {len(filtered_results)} results with highest scores")
                    else:
                        print("No results available to fall back to")
                        return []
                
                # Get just the documents for MMR
                docs = [doc for doc, _ in filtered_results]
                
                # For general search, use filtered results with MMR
                mmr_results = run_mmr_search( 
                    query=query,
                    k=min(3, len(docs)),
                    fetch_k=len(docs),
                    lambda_mult=0.6
                )
                
                log_results(mmr_results, "Final MMR results")
                return mmr_results
                
        except Exception as e:
            print(f"Error in search: {str(e)}")
            return []
    
    return custom_retriever
