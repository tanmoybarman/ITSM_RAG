"""
Confluence Table Operations for TriageBot

This module provides functionality to read and update tables in Confluence.
"""
import re
from typing import List, Dict, Any, Optional
from atlassian import Confluence
import logging

# Configure logging
logger = logging.getLogger(__name__)

class ConfluenceTable:
    """Handles operations on Confluence tables."""
    
    def __init__(self, confluence: Confluence, page_id: str):
        """Initialize with Confluence client and page ID."""
        self.confluence = confluence
        self.page_id = page_id
        self.page_content = ""
        self.table_data = []
        self.column_mapping = {}
        
    def load_table(self) -> List[Dict[str, Any]]:
        """
        Load and parse the table from Confluence page.
        
        Returns:
            List of dictionaries representing table rows
        """
        try:
            # Get the page content
            page = self.confluence.get_page_by_id(
                page_id=self.page_id,
                expand='body.storage'
            )
            self.page_content = page['body']['storage']['value']
            
            # Find the first table in the page
            table_match = re.search(r'<table.*?>(.*?)</table>', self.page_content, re.DOTALL)
            if not table_match:
                logger.error("No table found in the Confluence page")
                return []
                
            table_html = table_match.group(0)
            
            # Parse table headers
            header_match = re.search(r'<tr.*?>(.*?)</tr>', table_html, re.DOTALL)
            if not header_match:
                logger.error("Could not find table headers")
                return []
                
            headers = re.findall(r'<th.*?>(.*?)</th>', header_match.group(1), re.DOTALL)
            # Clean up header names by removing HTML tags and normalizing
            headers = [re.sub(r'<[^>]+>', '', h).strip().lower() for h in headers]
            
            # Log the found headers for debugging
            logger.info(f"Found table headers: {', '.join(headers)}")
            
            
            # Clean up the headers in column_mapping to remove HTML tags
            self.column_mapping = {i: re.sub(r'<[^>]+>', '', h).strip().lower() for i, h in enumerate(headers)}
            
            # Check if required columns exist (using cleaned column names)
            required_columns = ['url', 'type', 'status']
            available_columns = list(self.column_mapping.values())
            missing_columns = [col for col in required_columns if col not in available_columns]
            if missing_columns:
                logger.warning(f"Missing required columns in table: {', '.join(missing_columns)}")
                logger.warning(f"Available columns: {', '.join(available_columns)}")
            
            # Parse table rows
            row_matches = re.finditer(r'<tr.*?>(.*?)</tr>', table_html, re.DOTALL)
            self.table_data = []
            
            for i, row_match in enumerate(row_matches):
                if i == 0:  # Skip header row
                    continue
                    
                cells = re.findall(r'<td.*?>(.*?)</td>', row_match.group(1), re.DOTALL)
                if not cells:
                    continue
                    
                row_data = {
                    'row_index': i,
                    'original_cells': cells,
                    'data': {}
                }
                
                for col_index, cell_content in enumerate(cells):
                    if col_index in self.column_mapping:
                        # Clean up cell content (remove HTML tags, strip whitespace)
                        clean_content = re.sub(r'<[^>]+>', '', cell_content).strip()
                        row_data['data'][self.column_mapping[col_index]] = clean_content
                        
                        # Store the original cell content for updating
                        row_data[f'cell_{col_index}'] = cell_content
                
                self.table_data.append(row_data)
                
            return [row['data'] for row in self.table_data]
            
        except Exception as e:
            logger.error(f"Error loading table from Confluence: {str(e)}")
            raise
    
    def update_cell(self, row_index: int, column_name: str, new_value: str) -> bool:
        """
        Update a cell in the Confluence table.
        
        Args:
            row_index: Index of the row to update (0-based)
            column_name: Name of the column to update
            new_value: New value to set in the cell
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            logger.debug(f"Updating cell: row={row_index}, column='{column_name}', value='{new_value}'")
            
            if row_index < 0 or row_index >= len(self.table_data):
                logger.error(f"Invalid row index: {row_index}. Table has {len(self.table_data)} rows.")
                return False
                
            # Find the column index for the given column name (case-insensitive)
            column_name_lower = column_name.lower()
            col_index = None
            for idx, name in self.column_mapping.items():
                if name.lower() == column_name_lower:
                    col_index = idx
                    break
                    
            if col_index is None:
                available_columns = ", ".join(f"'{v}'" for v in self.column_mapping.values())
                logger.error(f"Column '{column_name}' not found in table. Available columns: {available_columns}")
                return False
                
            # Update the cell content in our local copy
            cell_key = f'cell_{col_index}'
            if cell_key not in self.table_data[row_index]:
                logger.error(f"Cell not found at row {row_index}, column {col_index}")
                return False
                
            # Preserve any HTML structure while updating the cell content
            old_content = self.table_data[row_index][cell_key]
            if '<p>' in old_content:
                new_content = re.sub(r'<p>.*?</p>', f'<p>{new_value}</p>', old_content, 1)
            else:
                new_content = f'<p>{new_value}</p>'
                
            # Update the table data
            self.table_data[row_index][cell_key] = new_content
            self.table_data[row_index]['data'][column_name.lower()] = new_value
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating cell: {str(e)}")
            return False
    
    def save_changes(self) -> bool:
        """
        Save all changes back to the Confluence page.
        
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Reconstruct the table HTML with updated content
            table_html = '<table><tbody>\n'
            
            # Add header row with proper HTML formatting
            table_html += '<tr>'
            for col_index in sorted(self.column_mapping.keys()):
                header = self.column_mapping[col_index]
                table_html += f'<th><p><strong>{header.title()}</strong></p></th>'
            table_html += '</tr>\n'
            # Add data rows
            for row in self.table_data:
                table_html += '<tr>'
                for col_index in sorted(self.column_mapping.keys()):
                    cell_key = f'cell_{col_index}'
                    if cell_key in row:
                        # Preserve the HTML structure of the cell content
                        cell_content = row[cell_key]
                        # If the cell content doesn't have <p> tags, add them
                        if not cell_content.strip().startswith('<p>'):
                            cell_content = f'<p>{cell_content}</p>'
                        table_html += f'<td>{cell_content}</td>'
                    else:
                        table_html += '<td><p></p></td>'
                table_html += '</tr>\n'
            table_html += '</tbody></table>'
            
            # Get the current page to preserve the title
            page = self.confluence.get_page_by_id(page_id=self.page_id)
            
            # Update the page content with the modified table
            updated_content = re.sub(
                r'<table.*?>.*?</table>',
                table_html,
                self.page_content,
                count=1,
                flags=re.DOTALL
            )
            
            # Save the updated content back to Confluence with proper parameters
            # Get the current page to preserve the version info
            current_page = self.confluence.get_page_by_id(page_id=self.page_id, expand='version')
            
            # Prepare the new version number
            new_version = current_page['version']['number'] + 1
            
            # Update the page with proper parameters
            result = self.confluence.update_page(
                page_id=self.page_id,
                title=page.get('title'),  # Use the existing title
                body=updated_content,
                version_comment='Updated by TriageBot',
                minor_edit=True
            )
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Error saving changes to Confluence: {str(e)}")
            return False
