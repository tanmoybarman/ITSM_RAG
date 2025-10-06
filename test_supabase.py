import os
from dotenv import load_dotenv
from supabase import create_client, Client

def test_supabase_connection():
    # Load environment variables from .env file
    load_dotenv()
    
    # Get Supabase URL and key from environment variables
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        print("Error: Please set SUPABASE_URL and SUPABASE_KEY in your .env file")
        return
    
    try:
        # Initialize the Supabase client
        print("🔌 Initializing Supabase client...")
        supabase: Client = create_client(supabase_url, supabase_key)
        
        # Test the connection by querying the customer_membership_new table
        # Note: PostgreSQL converts unquoted identifiers to lowercase
        table_name = 'customer_membership_new'
        print(f"🔍 Testing connection by querying {table_name} table...")
        
        # Try to get the count of records in the table
        response = supabase.table(table_name) \
            .select('*', count='exact') \
            .limit(1) \
            .execute()
        
        # If we get here, the connection was successful
        print("✅ Successfully connected to Supabase!")
        print(f"🔢 Found {response.count} records in CUSTOMER_MEMBERSHIP_NEW table")
        
        # Try to get the first few rows to show as a sample
        try:
            sample_data = supabase.table(table_name) \
                .select('*') \
                .limit(3) \
                .execute()
                
            if sample_data.data:
                print("\n📋 Sample data from CUSTOMER_MEMBERSHIP_NEW:")
                for i, row in enumerate(sample_data.data[:3], 1):
                    print(f"\nRow {i}:")
                    for key, value in row.items():
                        print(f"  {key}: {value}")
        except Exception as e:
            print(f"\nℹ️ Could not fetch sample data: {str(e)}")
            print("This might be due to table permissions or empty table.")
            
    except Exception as e:
        print(f"❌ Error connecting to Supabase: {str(e)}")

if __name__ == "__main__":
    test_supabase_connection()
