import os
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SupabaseCheck")

def check_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        logger.error("❌ SUPABASE_URL or SUPABASE_SERVICE_KEY not found in environment!")
        return False
    
    try:
        supabase: Client = create_client(url, key)
        # Try to select from a common table or just check connectivity
        response = supabase.table("repositories").select("count", count="exact").limit(1).execute()
        logger.info(f"✅ Supabase connection successful. Found {response.count} repositories.")
        return True
    except Exception as e:
        logger.error(f"❌ Supabase Connection Error: {e}")
        return False

if __name__ == "__main__":
    check_supabase()
