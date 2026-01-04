import pytest
import os
import sys

# Add server to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ast_chunker import ast_chunker, CodeChunk

def test_python_chunking():
    code = """
import os

def hello_world():
    print("Hello")
    return True

class Calculator:
    def add(self, a, b):
        return a + b
"""
    chunks = ast_chunker.chunk_file(code, "test.py")
    
    # Verify we found the expected chunks
    types = [c.chunk_type for c in chunks]
    assert "import" in types
    assert "function" in types
    assert "class" in types
    
    # Find the function chunk
    func_chunk = next(c for c in chunks if c.chunk_type == "function")
    assert func_chunk.chunk_name == "hello_world"
    assert "return True" in func_chunk.text

def test_javascript_chunking():
    code = """
import React from 'react';

function Header() {
    return <h1>Header</h1>;
}

const Footer = () => {
    return <footer>Footer</footer>;
};
"""
    chunks = ast_chunker.chunk_file(code, "component.jsx")
    
    types = [c.chunk_type for c in chunks]
    assert "import" in types
    # Note: Depending on tree-sitter installation, arrow functions might be identified as 'function' or 'code'
    # but the standard function declaration should definitely be caught.
    assert any(c.chunk_type == "function" for c in chunks)

def test_large_file_splitting():
    # Create a large function that exceeds max_chunk_size
    large_func = "def huge_function():\n" + "\n".join([f"    x = {i}" for i in range(500)])
    
    # Temporarily reduce max size for testing
    original_max = ast_chunker.max_chunk_size
    ast_chunker.max_chunk_size = 500
    
    try:
        chunks = ast_chunker.chunk_file(large_func, "large.py")
        # Should be split into multiple parts
        assert len(chunks) > 1
        assert all(c.chunk_name.startswith("huge_function_part") for c in chunks)
    finally:
        ast_chunker.max_chunk_size = original_max

def test_unsupported_language_fallback():
    code = "this is just some text\nin a non-existent language\nthat should be chunked by line."
    chunks = ast_chunker.chunk_file(code, "unknown.xyz")
    
    assert len(chunks) >= 1
    assert chunks[0].chunk_type == "code"
