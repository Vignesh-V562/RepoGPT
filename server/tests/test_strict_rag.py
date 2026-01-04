import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

# Add server directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock Supabase before importing rag
with patch('app.supabase_client.supabase') as mock_supabase:
    # We need to mock the import in rag.py
    import app.rag as rag

async def test_strict_rag():
    print("🚀 Starting Strict RAG Verification Tests...\n")
    
    # CASE 1: Completely unrelated query (e.g., Recipe) - Expect Hard Refusal
    print("--- Case 1: Unrelated Query ('How to make a cake?') ---")
    # Mocking empty search results
    with patch('app.rag.supabase.rpc') as mock_rpc:
        mock_rpc.return_value.execute.return_value.data = []
        
        async for event in rag.query_repo("test-repo", "How to make a cake?"):
            if isinstance(event, dict) and event.get('type') == 'token':
                print(f"Token: {event['content']}")
            elif isinstance(event, dict) and event.get('type') == 'status':
                print(f"Status: {event['content']}")
    
    print("\n--- Case 2: Out-of-bounds Technical Query ('How to implement OAuth?') ---")
    # This might find some "near" matches but should refuse in the final synthesis
    # We'll just verify the refusal logic triggers when no chunks are found
    with patch('app.rag.supabase.rpc') as mock_rpc:
        mock_rpc.return_value.execute.return_value.data = []
        
        async for event in rag.query_repo("test-repo", "How to implement OAuth?"):
            if isinstance(event, dict) and event.get('type') == 'token':
                print(f"Token: {event['content']}")
            elif isinstance(event, dict) and event.get('type') == 'status':
                print(f"Status: {event['content']}")

if __name__ == "__main__":
    asyncio.run(test_strict_rag())
