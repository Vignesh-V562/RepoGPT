import asyncio
import json
from app.ingestion import repo_ingestion_service

def test_chunking():
    print("Testing Smart Chunking...")
    # Sample Python code
    code = """
import os

class MyClass:
    def __init__(self):
        self.x = 1

    def method_one(self):
        print("one")
        return 1

def my_func():
    return "function"
"""
    # Force small max_chars to trigger split
    chunks = repo_ingestion_service._smart_chunk_code(code, ".py", max_chars=50, overlap=10)
    
    print(f"Original Length: {len(code)}")
    print(f"Number of Chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"--- Chunk {i} ---")
        print(f"Lines: {chunk['start_line']} - {chunk['end_line']}")
        print(chunk['text'])
        print("----------------")
    
    if len(chunks) > 1:
        print("SUCCESS: Code was split.")
    else:
        print("WARNING: Code was not split (might be too small or chunking logic failed).")

async def mock_simulated_stream():
    print("\nTesting SSE Format Simulation...")
    session_id = "test-session"
    
    async def mock_generator():
        yield f"data: {json.dumps({'type': 'session', 'sessionId': session_id})}\n\n"
        yield f"data: {json.dumps({'type': 'token', 'content': 'Hello'})}\n\n"
        yield f"data: {json.dumps({'type': 'token', 'content': ' World'})}\n\n"
        yield "data: [DONE]\n\n"

    print("Stream Output:")
    async for chunk in mock_generator():
        print(repr(chunk))
        if not chunk.startswith("data: "):
            print("FAIL: Bad SSE prefix")
            return
        if not chunk.endswith("\n\n"):
            print("FAIL: Bad SSE suffix")
            return
    print("SUCCESS: SSE Format mimics correctness.")

if __name__ == "__main__":
    test_chunking()
    asyncio.run(mock_simulated_stream())
