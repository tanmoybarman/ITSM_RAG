"""
TriageBot - Confluence Page Fetcher

A simple CLI tool to fetch and view Confluence pages.
"""
import os
import argparse
from typing import List, Dict, Any
from dotenv import load_dotenv

from confluence_loader import ConfluenceFetcher, setup_confluence_config

# Load environment variables
load_dotenv()

def list_pages(fetcher: ConfluenceFetcher):
    """List all pages in the Confluence space."""
    try:
        print("\nFetching pages from Confluence...")
        pages = fetcher.list_pages()
        
        if not pages:
            print("No pages found in the space.")
            return
            
        print(f"\nFound {len(pages)} pages in space '{fetcher.config.space_key}':\n")
        for i, page in enumerate(pages, 1):
            print(f"{i}. {page['title']} (ID: {page['id']})")
            print(f"   URL: {fetcher.config.url}/wiki{page['_links']['webui']}")
            print(f"   Last updated: {page['version']['when']}\n")
            
    except Exception as e:
        print(f"Error listing pages: {str(e)}")

def show_page(fetcher: ConfluenceFetcher, page_id: str, show_children: bool = True):
    """Show the content of a specific page with optional child pages."""
    try:
        print(f"\nFetching page ID: {page_id}")
        page = fetcher.get_page_content(page_id)
        
        if not page:
            print("Page not found or could not be loaded.")
            return
            
        print("\n" + "=" * 80)
        print(f"TITLE: {page['title']}")
        print("=" * 80)
        print(f"URL: {page['url']}")
        print(f"Space: {page['space']}")
        print(f"Last updated: {page['last_updated']}")
        print("\n" + "-" * 80 + "\n")
        
        # Print the content with basic HTML tag stripping for better readability
        import re
        content = re.sub(r'<[^>]+>', '', page['content'])  # Remove HTML tags
        content = re.sub(r'\s+', ' ', content).strip()  # Normalize whitespace
        print(content[:1000] + ('...' if len(content) > 1000 else ''))
        
        # Show child pages if available
        if show_children and page.get('child_pages'):
            print("\n" + "-" * 80)
            print("CHILD PAGES:")
            for i, child in enumerate(page['child_pages'], 1):
                print(f"{i}. {child['title']} (ID: {child['id']})")
                print(f"   URL: {child['url']}")
                print(f"   Last updated: {child['last_updated']}\n")
        
        print("\n" + "=" * 80 + "\n")
        return page
        
    except Exception as e:
        print(f"Error fetching page: {str(e)}")

def interactive_mode(fetcher: ConfluenceFetcher, initial_page_id: str = None):
    """Start an interactive session to browse Confluence pages."""
    current_page_id = initial_page_id
    
    while True:
        if current_page_id:
            # Show the current page and its children
            print("\n" + "=" * 60)
            print("  TriageBot - Confluence Page Browser")
            print("=" * 60)
            current_page = show_page(fetcher, current_page_id, show_children=True)
            
            if not current_page:
                current_page_id = None
                continue
                
            # Show navigation options
            print("\nNAVIGATION:")
            print("  [ID]     - Enter a page ID to view")
            print("  [number] - Select a child page by number")
            print("  back     - Go back to parent page")
            print("  home     - Go to space homepage")
            print("  exit     - Quit the program")
            
            # Get user input
            user_input = input("\nEnter command: ").strip().lower()
            
            if user_input == 'exit':
                print("Goodbye!")
                break
                
            elif user_input == 'back':
                # Go back to parent or space home if no parent
                if current_page.get('ancestors') and len(current_page['ancestors']) > 0:
                    current_page_id = current_page['ancestors'][-1]['id']
                else:
                    current_page_id = None
                    
            elif user_input == 'home':
                current_page_id = None
                
            elif user_input.isdigit():
                # Check if it's a child page number
                child_num = int(user_input)
                if current_page.get('child_pages') and 1 <= child_num <= len(current_page['child_pages']):
                    current_page_id = current_page['child_pages'][child_num - 1]['id']
                else:
                    print("Invalid child page number.")
                    
            else:
                # Assume it's a page ID
                current_page_id = user_input
                
        else:
            # Show space home with list of top-level pages
            print("\n" + "=" * 60)
            print(f"  TriageBot - Space: {fetcher.config.space_key}")
            print("=" * 60)
            print("  Type a page ID or select from the list below:")
            print("  Type 'exit' to quit\n")
            
            pages = fetcher.list_pages()
            if pages:
                for i, page in enumerate(pages, 1):
                    print(f"{i}. {page['title']} (ID: {page['id']})")
                    print(f"   URL: {fetcher.config.url}/wiki{page['_links']['webui']}")
                    print(f"   Last updated: {page['version']['when']}\n")
            
            user_input = input("Enter page ID or number: ").strip().lower()
            
            if user_input == 'exit':
                print("Goodbye!")
                break
                
            if user_input.isdigit():
                page_num = int(user_input)
                if 1 <= page_num <= len(pages):
                    current_page_id = pages[page_num - 1]['id']
                else:
                    print("Invalid page number.")
            else:
                current_page_id = user_input
    
    while True:
        try:
            command = input("\n> ").strip().split()
            
            if not command:
                continue
                
            if command[0].lower() == 'exit':
                print("Goodbye!")
                break
                
            elif command[0].lower() == 'list':
                list_pages(fetcher)
                
            elif command[0].lower() == 'show' and len(command) > 1:
                show_page(fetcher, command[1])
                
            else:
                print("\nAvailable commands:")
                print("  list              - List all pages in the space")
                print("  show <page-id>    - Show content of a specific page")
                print("  exit              - Exit the program")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {str(e)}")

def main():
    """Main entry point for the CLI."""
    try:
        # Setup Confluence configuration
        config = setup_confluence_config()
        fetcher = ConfluenceFetcher(config)
        
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='TriageBot - Confluence Page Fetcher')
        parser.add_argument('page_id', nargs='?', help='Optional page ID to start with')
        parser.add_argument('--list', action='store_true', help='List all pages in the space')
        
        args = parser.parse_args()
        
        if args.list:
            list_pages(fetcher)
        else:
            # Start interactive mode with optional initial page
            interactive_mode(fetcher, initial_page_id=args.page_id)
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
        
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
