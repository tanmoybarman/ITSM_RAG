"""
Confluence Page Fetcher for TriageBot

This module provides functionality to fetch and display pages from Confluence.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from atlassian import Confluence
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

@dataclass
class ConfluenceConfig:
    """Configuration for Confluence connection."""
    url: str
    username: str
    api_token: str
    space_key: str
    limit: int = 100  # Default limit for number of pages to fetch

class ConfluenceFetcher:
    def __init__(self, config: ConfluenceConfig):
        """Initialize the Confluence fetcher with configuration."""
        self.config = config
        self.confluence = self._get_confluence_client()
        
    def _get_confluence_client(self) -> Confluence:
        """Create and return a Confluence client instance."""
        is_cloud = 'atlassian.net' in self.config.url
        return Confluence(
            url=self.config.url,
            username=self.config.username,
            password=self.config.api_token,
            cloud=is_cloud
        )
    
    def list_pages(self) -> List[Dict[str, Any]]:
        """List all pages in the configured space."""
        try:
            logger.info(f"Fetching up to {self.config.limit} pages from Confluence space: {self.config.space_key}")
            
            # Get all pages from the space
            pages = self.confluence.get_all_pages_from_space(
                space=self.config.space_key,
                limit=self.config.limit,
                expand='version,space'
            )
            
            if not pages:
                logger.warning(f"No pages found in space: {self.config.space_key}")
                return []
                
            logger.info(f"Found {len(pages)} pages in space: {self.config.space_key}")
            return pages
            
        except Exception as e:
            logger.error(f"Failed to fetch pages from Confluence: {str(e)}")
            raise
    
    def get_page_content(self, page_id: str) -> Optional[Dict[str, Any]]:
        """Get the content of a specific page by ID."""
        try:
            logger.info(f"Fetching Confluence page with ID: {page_id}")
            
            # Get the specific page
            page = self.confluence.get_page_by_id(
                page_id=page_id,
                expand='body.storage,version,space,ancestors,children.page'
            )
            
            # Get child pages if they exist
            child_pages = []
            if '_links' in page and 'children' in page['_links']:
                children = self.confluence.get_page_child_by_type(
                    page_id=page_id,
                    type='page',
                    start=0,
                    limit=100,
                    expand='page.version'
                )
                if 'results' in children:
                    child_pages = [{
                        'id': child['id'],
                        'title': child['title'],
                        'url': f"{self.config.url}/wiki{child['_links']['webui']}",
                        'last_updated': child['version']['when']
                    } for child in children['results']]
            
            return {
                'id': page_id,
                'title': page['title'],
                'content': page['body']['storage']['value'],
                'url': f"{self.config.url}/wiki{page['_links']['webui']}",
                'space': page['space']['name'],
                'version': page['version']['number'],
                'last_updated': page['version']['when'],
                'child_pages': child_pages
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch page {page_id}: {str(e)}")
            return None

def setup_confluence_config() -> ConfluenceConfig:
    """Create and return a ConfluenceConfig from environment variables."""
    required_vars = [
        'CONFLUENCE_URL',
        'CONFLUENCE_EMAIL',
        'CONFLUENCE_API_TOKEN',
        'CONFLUENCE_SPACE_KEY'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    return ConfluenceConfig(
        url=os.getenv('CONFLUENCE_URL'),
        username=os.getenv('CONFLUENCE_EMAIL'),
        api_token=os.getenv('CONFLUENCE_API_TOKEN'),
        space_key=os.getenv('CONFLUENCE_SPACE_KEY'),
        limit=int(os.getenv('CONFLUENCE_LIMIT', '100'))
    )
