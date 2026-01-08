import os
from src.llm_provider import llm
from fastembed import TextEmbedding
from app.supabase_client import supabase

embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

# Try to load cross-encoder for reranking (Phase 2)
try:
    from sentence_transformers import CrossEncoder
    reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)
    RERANKER_AVAILABLE = True
    print("✓ Cross-encoder reranker loaded")
except ImportError:
    RERANKER_AVAILABLE = False
    reranker = None
    print("⚠ Cross-encoder not available. Install sentence-transformers for reranking.")


def rerank_chunks(query: str, chunks: list, top_k: int = 15) -> list:
    """
    Rerank chunks using cross-encoder for better precision.
    Returns chunks sorted by relevance score.
    """
    if not RERANKER_AVAILABLE or not chunks:
        return chunks[:top_k]
    
    try:
        pairs = [(query, c.get('content', '')[:2000]) for c in chunks]  # Truncate for speed
        scores = reranker.predict(pairs)
        
        # Attach scores and sort
        for i, chunk in enumerate(chunks):
            chunk['rerank_score'] = float(scores[i])
        
        chunks.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
        return chunks[:top_k]
    except Exception as e:
        print(f"Reranking error: {e}")
        return chunks[:top_k]


async def _fetch_history(session_id: str, limit: int = 5):
    """Fetch recent chat history for context."""
    if not session_id:
        return []
    try:
        res = supabase.table("messages").select("role, content").eq("session_id", session_id).order("created_at", desc=True).limit(limit).execute()
        # Reverse to get chronological order
        return res.data[::-1]
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []


async def _condense_query(query: str, history: list) -> str:
    """Turn a conversational follow-up into a standalone search query."""
    if not history:
        return query
    
    history_str = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history])
    
    prompt = f"""Given the following conversation history and a follow-up question, rephrase the follow-up question to be a standalone search query that can be used to search a codebase.
    
CHATHISTORY:
{history_str}

FOLLOW-UP QUESTION: {query}

STANDALONE QUERY:"""
    
    try:
        condensed, _ = llm.generate_content(
            mode="chat",
            prompt=prompt
        )
        condensed = condensed.strip()
        print(f"RAG: Condensed '{query}' -> '{condensed}'")
        return condensed
    except Exception as e:
        print(f"Query condensation error: {e}")
        return query


def is_repo_query(query: str) -> bool:
    """Determine if a query likely requires codebase context."""
    # List of keywords that imply looking at code or repository structure
    repo_keywords = [
        "code", "file", "function", "class", "how dose", "where is", "repo", 
        "implement", "logic", "variable", "import", "package", "method",
        "blueprint", "architecture", "structure", "folder", "directory"
    ]
    query_lower = query.lower()
    
    # Check for direct repo keywords
    if any(k in query_lower for k in repo_keywords):
        return True
    
    # If the user is asking "what is this", "where does X happen", 
    # or using technical terms like "auth", "db", "api"
    tech_keywords = ["auth", "database", "db", "api", "endpoint", "route", "server", "client"]
    if any(k in query_lower for k in tech_keywords):
        return True
        
    return False

async def _get_general_chat_response(query: str, history: list):
    """Handle general questions without RAG."""
    history_str = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history])
    prompt = f"You are RepoGPT assistant. Answer the following question based on your general knowledge. If the user is asking about code specifically, inform them that you are ready to analyze the repo if they provide more detail.\n\nHistory:\n{history_str}\n\nUser: {query}\n\nAssistant:"
    
    for chunk in llm.generate_content_stream(mode="chat", prompt=prompt):
        yield {"type": "token", "content": chunk}


async def query_repo(repo_id: str, query: str, session_id: str = None):
    """
    Production-grade RAG with:
    1. Query condensation (Conversational Memory)
    2. Two-stage retrieval (file summaries -> code chunks)
    3. Hybrid search (vector + keyword) when available
    4. Cross-encoder reranking for precision
    5. Enhanced prompting
    """
    
    # 0. Condense Query if history exists
    actual_search_query = query
    history = []
    if session_id:
        history = await _fetch_history(session_id)
        
        # Check if history is relevant to the CURRENT repo
        # If the session was started for Repo A but we are now in Repo B, 
        # the history might be misleading.
        if history and repo_id:
            try:
                session_info = supabase.table("chat_sessions").select("repository_id").eq("id", session_id).single().execute()
                if session_info.data and session_info.data.get("repository_id") != repo_id:
                    print(f"RAG: Detected repo mismatch (Session: {session_info.data.get('repository_id')}, Current: {repo_id}). Ignoring history for condensation.")
                    history = []
            except Exception as e:
                print(f"RAG: Error checking session repo: {e}")

        if history:
            actual_search_query = await _condense_query(query, history)

    # 0.1 Intent Detection: Skip RAG for non-technical or general conversational queries
    if not is_repo_query(actual_search_query):
        print(f"RAG: Skipping retrieval for general query: '{actual_search_query}'")
        yield {"type": "status", "content": "General query detected. Responding via global knowledge..."}
        async for chunk in _get_general_chat_response(query, history):
            yield chunk
        return

    # 1. Embed Query
    yield {"type": "status", "content": "Condensing query for context..."}
    query_vec = list(embedding_model.embed([actual_search_query]))[0].tolist()

    # 2. Stage 1: Find Relevant Files via Summary Search
    yield {"type": "status", "content": "Identifying relevant files..."}
    relevant_files = []
    file_summaries_context = ""
    
    # Try hybrid search first (Phase 2), fallback to vector-only
    try:
        hybrid_params = {
            "query_embedding": query_vec,
            "query_text": actual_search_query,
            "keyword_weight": 0.3,
            "vector_weight": 0.7,
            "match_count": 15,
            "repo_id": repo_id
        }
        file_response = supabase.rpc("hybrid_search_file_summaries", hybrid_params).execute()
        
        if file_response.data:
            print(f"RAG: Found {len(file_response.data)} files via hybrid search.")
            yield {"type": "status", "content": f"Found {len(file_response.data)} potential files..."}
            for f in file_response.data:
                relevant_files.append(f['file_path'])
                components = f.get('key_components', [])
                components_str = ', '.join(components) if components else 'N/A'
                file_summaries_context += f"📄 **{f['file_path']}** (score: {f.get('combined_score', 0):.2f})\n"
                file_summaries_context += f"   {f['summary']}\n"
                file_summaries_context += f"   Components: {components_str}\n\n"
    except Exception as e:
        print(f"Hybrid file search failed, trying vector-only: {e}")
        try:
            vector_params = {
                "query_embedding": query_vec,
                "match_threshold": 0.15,
                "match_count": 8,
                "repo_id": repo_id
            }
            file_response = supabase.rpc("match_file_summaries", vector_params).execute()
            if file_response.data:
                print(f"RAG: Found {len(file_response.data)} files via vector-only search.")
                for f in file_response.data:
                    relevant_files.append(f['file_path'])
                    file_summaries_context += f"📄 **{f['file_path']}**\n   {f['summary']}\n\n"
        except Exception as e2:
            print(f"Vector file search also failed: {e2}")
    
    # 3. Stage 2: Get Code Chunks
    yield {"type": "status", "content": "Extracting code chunks..."}
    chunks = []
    
    # Try hybrid chunk search first
    try:
        hybrid_chunk_params = {
            "query_embedding": query_vec,
            "query_text": actual_search_query,
            "keyword_weight": 0.3,
            "vector_weight": 0.7,
            "match_count": 20,  # Reduced for faster processing
            "repo_id": repo_id
        }
        chunk_response = supabase.rpc("hybrid_search_chunks", hybrid_chunk_params).execute()
        if chunk_response.data:
            print(f"RAG: Found {len(chunk_response.data)} chunks via hybrid search.")
            yield {"type": "status", "content": f"Retrieved {len(chunk_response.data)} code blocks..."}
            chunks = chunk_response.data
    except Exception as e:
        print(f"Hybrid chunk search failed: {e}")
    
    # Fallback to filtered search if hybrid not available
    if not chunks and relevant_files:
        try:
            filtered_params = {
                "query_embedding": query_vec,
                "match_threshold": 0.1,
                "match_count": 20,
                "repo_id": repo_id,
                "file_paths": relevant_files
            }
            chunk_response = supabase.rpc("match_code_chunks_in_files", filtered_params).execute()
            if chunk_response.data:
                print(f"RAG: Found {len(chunk_response.data)} chunks via filtered search.")
                chunks = chunk_response.data
        except Exception as e:
            print(f"Filtered chunk search failed: {e}")
    
    # Final fallback to basic vector search
    if not chunks:
        try:
            basic_params = {
                "query_embedding": query_vec,
                "match_threshold": 0.1,
                "match_count": 25,
                "repo_id": repo_id
            }
            chunk_response = supabase.rpc("match_code_chunks", basic_params).execute()
            if chunk_response.data:
                print(f"RAG: Found {len(chunk_response.data)} chunks via basic search.")
                chunks = chunk_response.data
        except Exception as e:
            print(f"Basic chunk search failed: {e}")
            yield {"type": "error", "content": "Error retrieving context from database."}
            return
    
    yield {"type": "metadata", "files": list(set(relevant_files))}
    
    if not chunks and not file_summaries_context:
        print("RAG: No chunks and no file summaries context found. Strict refusal triggered.")
        yield {"type": "token", "content": "❌ **No relevant code or documentation was found in the repository for this query.**\n\nTo ensure accuracy and avoid hallucinations, I only answer based on the provided codebase context. Please try rephrasing your search or checking if the specific file is indexed."}
        return

    # 4. Rerank chunks for precision (Phase 2)
    if chunks:
        yield {"type": "status", "content": "Reranking candidates for precision..."}
        chunks = rerank_chunks(actual_search_query, chunks, top_k=15)
    
    # 5. Build Code Context with metadata
    code_context = ""
    for chunk in chunks:
        file_path = chunk.get('file_path', 'unknown')
        start_line = chunk.get('start_line', '?')
        end_line = chunk.get('end_line', '?')
        content = chunk.get('content', '')
        chunk_type = chunk.get('chunk_type', 'code')
        chunk_name = chunk.get('chunk_name', '')
        
        # Format header based on chunk type
        if chunk_type == 'function' and chunk_name:
            header = f"### Function `{chunk_name}` in {file_path}"
        elif chunk_type == 'class' and chunk_name:
            header = f"### Class `{chunk_name}` in {file_path}"
        else:
            header = f"### {file_path} (Lines {start_line}-{end_line})"
        
        code_context += f"{header}\n```\n{content}\n```\n\n"

    print(f"RAG: Final file summaries context length: {len(file_summaries_context)} chars")
    print(f"RAG: Final code context length: {len(code_context)} chars")
    # 6. Construct Enhanced Prompt
    prompt = f"""You are **RepoGPT**, an AI assistant specialized in analyzing codebases.
Your mission: Provide accurate and technically deep answers about this codebase.

## User's Question
{query}

## Repository Overview (AI-Analyzed File Summaries)
{file_summaries_context if file_summaries_context else "File summaries not available. Analyzing raw code."}

## Relevant Code (Semantically Retrieved & Reranked)
{code_context if code_context else "No code chunks found."}

---

## Response Guidelines
1. **Context-Only Mode**: ONLY answer using the provided code snippets and file summaries. DO NOT use external knowledge about how things "usually" work in other systems.
2. **Strict Factuality**: If the provided context does not contain the answer, explicitly state: "The repository context does not provide information on [specific topic]."
3. **Mandatory Citations**: Every claim about the code MUST be accompanied by a file path or function name from the context.
4. **Be Specific**: Reference exact class names, function names, and file paths.
5. **Use Code Examples**: Quote relevant snippets from the provided context when explaining.

## Format
- Use headers (##, ###) to organize your response
- Use bullet points for lists
- Use `inline code` for identifiers
- Use code blocks for longer excerpts

Now provide your expert analysis:
"""

    # 7. Stream Response
    yield {"type": "status", "content": "Generating technical analysis..."}
    try:
        # Optimization: Use 'chat' mode (8B) for faster replies to simple questions
        # Use 'analyst' (70B) only for complex analytical queries
        is_complex = len(code_context) > 5000 or "analyze" in query.lower() or "explain" in query.lower()
        active_mode = "analyst" if is_complex else "chat"
        
        for chunk in llm.generate_content_stream(
            mode=active_mode,
            prompt=prompt
        ):
            yield {"type": "token", "content": chunk}
    except Exception as e:
        print(f"LLM Error: {e}")
        yield {"type": "error", "content": f"Error generating response: {str(e)}"}
