"""
TriageBot - Incident Validation Script

This script validates URLs in a Confluence table and updates their status.
"""
import os
import sys
import argparse
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from atlassian import Confluence

# Import our modules
from confluence_loader import ConfluenceConfig, ConfluenceFetcher
from confluence_table import ConfluenceTable
from url_validator import URLValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IncidentValidator:
    """Main class for validating incidents in Confluence."""
    
    def __init__(self, confluence: Confluence, page_id: str):
        """Initialize with Confluence client and page ID."""
        self.confluence = confluence
        self.page_id = page_id
        self.confluence_table = ConfluenceTable(confluence, page_id)
        self.validator = URLValidator()
    
    def run_validation(self, max_incidents: Optional[int] = None) -> bool:
        """Run validation for all incidents in the table."""
        try:
            # Load the table from Confluence
            logger.info(f"Loading incidents from Confluence page {self.page_id}")
            incidents = self.confluence_table.load_table()
            
            if not incidents:
                logger.error("No incidents found in the table")
                return False
            
            logger.info(f"Found {len(incidents)} incidents to validate")
            
            # Process each incident
            success_count = 0
            total_incidents = min(len(incidents), max_incidents) if max_incidents else len(incidents)
            
            for i, incident in enumerate(incidents, 1):
                if max_incidents and i > max_incidents:
                    break
                    
                logger.info(f"Processing incident {i}/{total_incidents}: {incident.get('ticket', 'Unknown')}")
                
                # Skip if required fields are missing
                if not incident.get('url') or not incident.get('type'):
                    logger.warning(f"Skipping incident {incident.get('ticket', 'Unknown')}: Missing URL or type")
                    self._update_incident_status(
                        i-1,  # row index is 0-based
                        'Skipped',
                        'Missing URL or type'
                    )
                    continue
                
                # Validate the URL
                try:
                    result = self.validator.validate_url(
                        url=incident['url'],
                        url_type=incident['type']
                    )
                    
                    # Update the status in the table
                    self._update_incident_status(
                        i-1,  # row index is 0-based
                        result['status'],
                        result['details']
                    )
                    
                    if result['valid']:
                        success_count += 1
                    
                    logger.info(f"Status for {incident.get('ticket', 'Unknown')}: {result['status']}")
                    
                except Exception as e:
                    logger.error(f"Error validating incident {incident.get('ticket', 'Unknown')}: {str(e)}")
                    self._update_incident_status(
                        i-1,  # row index is 0-based
                        'Error',
                        f'Validation failed: {str(e)}'
                    )
            
            # Update the 'Updated_Ts_LastRun' column with current timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for i in range(len(self.confluence_table.table_data)):
                self.confluence_table.update_cell(
                    row_index=i,
                    column_name='Updated_Ts_LastRun',
                    new_value=timestamp
                )
            
            # Save all changes to Confluence
            logger.info("Saving changes to Confluence...")
            if self.confluence_table.save_changes():
                logger.info(f"Successfully updated {success_count}/{total_incidents} incidents")
                logger.info(f"Updated 'Updated_Ts_LastRun' timestamp to {timestamp}")
                return True
            else:
                logger.error("Failed to save changes to Confluence")
                return False
                
        except Exception as e:
            logger.error(f"Error during validation: {str(e)}")
            return False
    
    def _update_incident_status(self, row_index: int, status: str, details: str = '') -> bool:
        """Update the status of an incident in the table."""
        # Get the current incident data to include URL and type in the status
        incidents = self.confluence_table.table_data
        if 0 <= row_index < len(incidents):
            incident = incidents[row_index].get('data', {})
            url = incident.get('url', 'Unknown URL')
            incident_type = incident.get('type', 'Unknown Type')
            
            # Truncate long URLs for display
            if len(url) > 20:
                url = url[:17] + '...'
                
            # Update status to include type and URL
            status = f"{status} "
        
        # Add timestamp to status
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status_with_details = f"{status} ({timestamp})"
        
        if details:
            status_with_details += f" - {details}"
        
        # Update the status in the table
        return self.confluence_table.update_cell(
            row_index=row_index,
            column_name='status',
            new_value=status_with_details
        )


def main():
    """Main entry point for the script."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Validate URLs in a Confluence table.')
    parser.add_argument('--page-id', type=str, default='229509',
                      help='Confluence page ID containing the table (default: 229509)')
    parser.add_argument('--max', type=int, default=None,
                      help='Maximum number of incidents to process (default: all)')
    parser.add_argument('--dry-run', action='store_true',
                      help='Run validation without saving changes to Confluence')
    
    args = parser.parse_args()
    
    try:
        # Setup Confluence configuration from environment variables
        config = ConfluenceConfig(
            url=os.getenv('CONFLUENCE_URL'),
            username=os.getenv('CONFLUENCE_EMAIL'),
            api_token=os.getenv('CONFLUENCE_API_TOKEN'),
            space_key=os.getenv('CONFLUENCE_SPACE_KEY')
        )
        
        # Initialize Confluence client
        confluence = Confluence(
            url=config.url,
            username=config.username,
            password=config.api_token,
            cloud=True
        )
        
        # Run the validation
        validator = IncidentValidator(confluence, args.page_id)
        
        if args.dry_run:
            logger.info("Running in dry-run mode. No changes will be saved to Confluence.")
        
        success = validator.run_validation(max_incidents=args.max)
        
        if success:
            logger.info("Validation completed successfully!")
            return 0
        else:
            logger.error("Validation completed with errors.")
            return 1
            
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
