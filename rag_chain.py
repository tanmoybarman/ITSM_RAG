"""
RAG (Retrieval-Augmented Generation) Chain Module

This module implements a question-answering system that combines document retrieval
with language model generation to provide accurate responses about ServiceNow incidents.
"""
from typing import Dict, Any
# Import required LangChain components
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
# Import Mistral AI chat model for response generation
from langchain_mistralai import ChatMistralAI

def create_rag_chain(retriever, mistral_api_key: str):
    """
    Create a Retrieval-Augmented Generation (RAG) chain optimized for incident management.
    
    Args:
        retriever: Document retriever that fetches relevant context
        mistral_api_key: API key for Mistral AI service
        
    Returns:
        Configured RAG chain ready for question-answering
    """
    # Initialize the chat model with specific parameters
    chat_model = ChatMistralAI(
        model="mistral-tiny",
        temperature=0.1,
        max_tokens=2000,  # Increased to handle detailed incident information
        api_key=mistral_api_key
    )
    
    # Enhanced system prompt with greeting handling and incident management
    system_prompt = """You are a ServiceNow incident management assistant. 
    
    GREETING HANDLING:
    - If the user greets you (e.g., "hi", "hello", "good morning"), respond with a friendly greeting and offer assistance with incident-related queries.
    - For general conversation that's not related to incidents, respond politely but guide the conversation back to incident management.
    
    INCIDENT QUERIES:
    - Your responses about incidents MUST be based ONLY on the provided context.
    - If the answer is not explicitly in the context, say "I don't have enough information to answer that question."
    - Never make up or guess information that's not in the context.
    - If asked about specific incidents, only provide details that are in the context.

    When responding about incidents:
    - Always include the incident number if available
    - Only state facts that are present in the context
    - If the context doesn't contain enough information, say so
    - Never invent incident details, resolutions, or statuses

    Context:
    {context}

    Question: {input}
    """
    
    # Add few-shot examples with greeting handling and generic placeholders
    few_shot_examples = [
        # Greeting examples
        ("human", "Hi there!"),
        ("ai", "Hello! I'm your ServiceNow incident assistant. How can I help you with incident management today?"),
        ("human", "Good morning"),
        ("ai", "Good morning! I'm here to help with any ServiceNow incident queries you have. What can I assist you with today?"),
        # Incident query examples
        ("human", "What is this incident about?"),
        ("ai", "Let me look up the details for this incident."),
        ("human", "How was this incident resolved?"),
        ("ai", "I'll check the resolution details for this incident."),
        # Non-incident query handling
        ("human", "How's the weather?"),
        ("ai", "I'm focused on helping with ServiceNow incidents. Would you like to ask about a specific incident or need help with incident management?")
    ]
    
    # Create a custom document prompt
    from langchain_core.prompts import PromptTemplate
    from langchain_core.documents import Document
    
    document_prompt = PromptTemplate(
        input_variables=["page_content"],
        template="{page_content}"
    )
    
    # Create the prompt template
    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt)] + few_shot_examples + [("human", "{input}")]
    )
    
    # Create the document chain with the prompt and custom document prompt
    document_chain = create_stuff_documents_chain(
        chat_model, 
        prompt,
        document_prompt=document_prompt
    )
    
    # Return a custom chain that can process the retrieved documents
    def ensure_document(obj):
        """Ensure the object is a Document with page_content and metadata."""
        from langchain_core.documents import Document
        
        if obj is None:
            return Document(page_content="[No content]")
            
        if isinstance(obj, Document):
            # Ensure metadata exists and is a dict
            if not hasattr(obj, 'metadata') or not isinstance(obj.metadata, dict):
                obj.metadata = {}
            return obj
            
        if isinstance(obj, dict):
            # Handle different dict formats
            if 'page_content' in obj:
                return Document(
                    page_content=str(obj.get('page_content', '')),
                    metadata=obj.get('metadata', {})
                )
            # If it's a simple dict, use it as content
            return Document(
                page_content=str(obj),
                metadata={"source": "converted_dict"}
            )
            
        # For any other type, convert to string
        return Document(
            page_content=str(obj),
            metadata={"source": "converted_unknown"}
        )

    def safe_convert_to_document(doc):
        """Safely convert any document-like object to a Document."""
        from langchain.schema import Document
        
        if doc is None:
            return None
            
        try:
            if isinstance(doc, Document):
                return doc
                
            # Handle dictionary inputs
            if isinstance(doc, dict):
                # Check if this is a document with metadata
                if 'page_content' in doc or 'metadata' in doc:
                    return Document(
                        page_content=doc.get('page_content', ''),
                        metadata=doc.get('metadata', {})
                    )
                # If it's a simple dict, convert to string content
                return Document(
                    page_content=str(doc),
                    metadata={"source": "converted_dict"}
                )
                
            # Handle string inputs
            if isinstance(doc, str):
                return Document(
                    page_content=doc,
                    metadata={"source": "converted_string"}
                )
                
            # For any other type, convert to string
            return Document(
                page_content=str(doc),
                metadata={"source": "converted_unknown"}
            )
            
        except Exception as e:
            print(f"Error converting document: {e}")
            return Document(
                page_content="[Error: Could not process document content]",
                metadata={"error": str(e)}
            )
    
    async def process_retrieved_docs(inputs):
        from langchain_core.documents import Document
        
        query = inputs.get("input", "").strip()
        search_mode = inputs.get("search_mode", "general")
        
        if not query:
            return {
                "input": "",
                "context": [],
                "answer": "Please provide a valid query."
            }
        
        # Handle both sync and async retrievers
        import asyncio
        import inspect
        import re
        
        try:
            # Get documents from retriever with error handling and pass search_mode
            try:
                # Check if retriever is a callable that accepts search_mode
                retriever_kwargs = {"search_mode_override": search_mode}
                
                # Debug: Print retriever function details
                print(f"[DEBUG] Process_retrieved_docs - Search mode: {search_mode}")
                print(f"[DEBUG] Retriever function: {retriever.__name__ if hasattr(retriever, '__name__') else type(retriever)}")
                
                if inspect.iscoroutinefunction(retriever):
                    print("[DEBUG] Retriever is a coroutine function")
                    if hasattr(retriever, '__code__') and 'search_mode_override' in retriever.__code__.co_varnames:
                        print("[DEBUG] Retriever accepts search_mode_override parameter")
                        docs = await retriever(query, **retriever_kwargs)
                    else:
                        print("[DEBUG] Retriever does not accept search_mode_override parameter")
                        docs = await retriever(query)
                else:
                    print("[DEBUG] Retriever is a regular function")
                    if hasattr(retriever, '__code__') and 'search_mode_override' in retriever.__code__.co_varnames:
                        print("[DEBUG] Retriever accepts search_mode_override parameter")
                        docs = retriever(query, **retriever_kwargs)
                    else:
                        print("[DEBUG] Retriever does not accept search_mode_override parameter")
                        docs = retriever(query)
                
                print(f"[DEBUG] Retrieved {len(docs) if docs else 0} documents")
            except Exception as e:
                print(f"Error in retriever: {str(e)}")
                docs = []
            
            # Convert all documents to Document objects safely
            processed_docs = []
            if docs:
                for doc in docs:
                    try:
                        processed = safe_convert_to_document(doc)
                        if processed and processed.page_content:
                            processed_docs.append(processed)
                    except Exception as e:
                        print(f"Error processing document: {str(e)}")
                        continue
            
            docs = processed_docs
            
            # If no documents were found, return a helpful message
            if not docs:
                return {
                    "input": query,
                    "context": [],
                    "answer": "I couldn't find any information about that incident. Please check the incident number and try again."
                }
            
            # Check if we have exact matches for incident numbers in the query
            incident_numbers = re.findall(r'INC\d+', query.upper())
            if incident_numbers:
                # Filter docs to only include exact matches for the requested incidents
                filtered_docs = []
                for doc in docs:
                    doc_incident = doc.metadata.get("incident_number", "")
                    if doc_incident in incident_numbers or doc.metadata.get("type") in ["incident_mapping", "incident_reference"]:
                        filtered_docs.append(doc)
                
                # If we found exact matches, use those; otherwise, use all docs
                if filtered_docs:
                    docs = filtered_docs
            
            # Prepare the context for the LLM
            context = []
            for doc in docs:
                try:
                    # Handle both Document objects and dictionaries
                    if isinstance(doc, dict):
                        # If it's already a dictionary with page_content, use as is
                        if 'page_content' in doc:
                            context.append(doc)
                            continue
                        # Otherwise convert to proper format
                        content = str(doc.get('content', doc.get('text', '')))
                        metadata = dict(doc.get('metadata', {}))
                        context.append({
                            "page_content": content,
                            "metadata": metadata
                        })
                    # Handle Document objects
                    elif hasattr(doc, 'page_content'):
                        content = doc.page_content or ''
                        metadata = {}
                        if hasattr(doc, 'metadata') and doc.metadata is not None:
                            if isinstance(doc.metadata, dict):
                                metadata = dict(doc.metadata)
                        
                        # Ensure source is set
                        if 'source' not in metadata:
                            metadata['source'] = 'processed_document'
                        
                        context.append({
                            "page_content": content,
                            "metadata": metadata
                        })
                except Exception as e:
                    print(f"Error processing document: {str(e)}")
                    continue
            
            if not context:
                return {
                    "input": query,
                    "context": [],
                    "answer": "No relevant information found for your query."
                }
            
            # Get the response from the document chain
            try:
                # Ensure we have valid context
                if not context:
                    return {
                        "input": query,
                        "context": [],
                        "answer": "No relevant information was found for your query. Please try rephrasing or providing more specific details."
                    }
                
                # Ensure all context items are properly formatted Document objects
                documents = []
                for item in context:
                    try:
                        if isinstance(item, dict):
                            # Ensure required fields exist
                            page_content = item.get('page_content', '')
                            if not isinstance(page_content, str):
                                page_content = str(page_content) if page_content is not None else ''
                                
                            metadata = item.get('metadata', {})
                            if not isinstance(metadata, dict):
                                metadata = {}
                            
                            # Create a new Document
                            doc = Document(
                                page_content=page_content,
                                metadata=metadata
                            )
                            documents.append(doc)
                        elif hasattr(item, 'page_content'):
                            # Already a Document-like object
                            documents.append(item)
                    except Exception as e:
                        print(f"Error creating Document: {str(e)}")
                        continue
                
                # Prepare the input for the chain
                chain_input = {
                    "input": query,
                    "context": documents
                }
                
                # Debug: Print chain input structure
                print(f"Chain input structure: {type(chain_input)}")
                print(f"Context type: {type(chain_input['context'])}")
                if chain_input['context']:
                    print(f"First context item type: {type(chain_input['context'][0])}")
                
                # Invoke the appropriate method based on chain type
                if inspect.iscoroutinefunction(document_chain.ainvoke):
                    response = await document_chain.ainvoke(chain_input)
                else:
                    response = document_chain.invoke(chain_input)
                
                # Ensure response is a dictionary
                if not isinstance(response, dict):
                    response = {"answer": str(response) if response else "No response was generated."}
                
                # Ensure we have an answer field
                if "answer" not in response:
                    response["answer"] = "I couldn't generate a proper response. Please try rephrasing your question."
                    
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                print(f"Error in document chain: {str(e)}\n{error_trace}")
                
                # Try to provide a more helpful error message
                if "page_content" in str(e):
                    response = {
                        "answer": "There was an issue processing the documents. This might be due to malformed data. Please try a different query."
                    }
                else:
                    response = {
                        "answer": "An unexpected error occurred while processing your request. Please try again later."
                    }
                
            return {
                "input": query,
                "context": docs,
                "answer": response
            }
            
        except Exception as e:
            return {
                "input": query,
                "context": [],
                "answer": f"An error occurred: {str(e)}. Please try again with a different query."
            }
    
    return process_retrieved_docs



from typing import Union, Awaitable, Callable, Dict, Any
import asyncio
import inspect

def ensure_document(doc):
    """Ensure the input is a valid Document object."""
    from langchain.schema import Document
    
    if isinstance(doc, Document):
        return doc
    elif isinstance(doc, dict):
        return Document(
            page_content=doc.get('page_content', ''),
            metadata=doc.get('metadata', {})
        )
    return Document(page_content=str(doc))

def query_rag_chain(rag_chain: Union[Callable, Awaitable], query: str, search_mode: str = 'general') -> Dict[str, Any]:
    """
    Query the RAG chain with proper error handling and document validation.
    
    Args:
        rag_chain: The RAG chain to query (can be sync or async)
        query: The user's query string
        search_mode: The search mode to use ('incident_number', 'general', or 'mmr_only')
        
    Returns:
        A dictionary containing the response, context, and any errors
    """
    if not query or not isinstance(query, str) or not query.strip():
        return {
            "input": "",
            "context": [],
            "result": "Please provide a valid query.",
            "answer": "Please provide a valid query.",
            "source_documents": []
        }
        
    try:
        # Prepare the input with search_mode to be used by the retriever
        input_data = {
            "input": query.strip(),
            "search_mode": search_mode,
            "search_kwargs": {"search_mode_override": search_mode}
        }
        
        # Execute the RAG chain
        if asyncio.iscoroutinefunction(rag_chain):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            response = loop.run_until_complete(rag_chain(input_data))
        else:
            response = rag_chain(input_data)
            
        # Ensure consistent response format
        result = {
            "input": query,
            "result": response.get("result", ""),
            "answer": response.get("answer", response.get("result", "")),
            "context": [],
            "source_documents": response.get("source_documents", response.get("context", []))
        }
        
        # Process the context to ensure all items are Document objects
        if result["source_documents"]:
            processed_docs = []
            for item in result["source_documents"]:
                try:
                    doc = ensure_document(item)
                    processed_docs.append(doc)
                except Exception as e:
                    print(f"Error processing document: {e}")
                    continue
            result["source_documents"] = processed_docs
            result["context"] = processed_docs  # For backward compatibility
            
        return result
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in query_rag_chain: {str(e)}\n{error_trace}")
        
        return {
            "input": query,
            "context": [],
            "answer": f"An error occurred while processing your query: {str(e)}. Please try again with a different query."
        }