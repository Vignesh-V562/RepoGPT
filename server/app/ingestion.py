import os
import re
import shutil
import uuid
import git
import asyncio
import stat
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from app.supabase_client import supabase
from src.llm_provider import llm

# Local storage for repos (temporary)
# Local storage for repos (temporary)
REPO_STORAGE_PATH = "./cloned_repos"


def on_rm_error(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.
    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)

class RepoIngestionService:
    def __init__(self):
        self.thread_pool = ThreadPoolExecutor(max_workers=2)

    
    async def ingest_repo(self, repo_url: str, user_id: str, repo_entry_id: str):
        """
        Entry point for background ingestion.
        We run the blocking synchronous parts in a thread pool.
        """
        loop = asyncio.get_event_loop()
        try:
            print(f"Starting ingestion (background) for {repo_url}...")
            await loop.run_in_executor(
                None, 
                lambda: supabase.table("repositories").update({"status": "indexing"}).eq("id", repo_entry_id).execute()
            )
            await loop.run_in_executor(self.thread_pool, self._process_repo_sync, repo_url, repo_entry_id)

        except Exception as e:
            print(f"Ingestion Task Failed: {e}")
            await loop.run_in_executor(
                None, 
                lambda: supabase.table("repositories").update({"status": "failed"}).eq("id", repo_entry_id).execute()
            )

    def _process_repo_sync(self, repo_url: str, repo_entry_id: str):
        """Synchronous worker function that handles cloning, parsing, summarizing, and embedding."""
        try:
            repo_name = repo_url.split("/")[-1].replace(".git", "")
            local_path = os.path.join(REPO_STORAGE_PATH, f"{repo_entry_id}_{repo_name}")
            
            if os.path.exists(local_path):
                shutil.rmtree(local_path, onerror=on_rm_error)
            
            # 1. Clone
            print(f"[1/5] Cloning {repo_url}...")
            git.Repo.clone_from(repo_url, local_path, depth=1)
            
            # 2. Build File Tree
            print(f"[2/5] Building file tree...")
            file_tree = self._build_file_tree(local_path)
            
            # 3. Parse, Chunk, and Summarize Files
            print(f"[3/5] Parsing and summarizing files...")
            documents, file_summaries = self._parse_chunk_and_summarize(local_path, repo_entry_id)
            
            # 4. Embed & Store Chunks
            print(f"[4/5] Embedding {len(documents)} chunks...")
            self._embed_and_store_chunks(documents)
            
            # 5. Extract & Store Dependencies
            print(f"[5/5] Extracting dependencies...")
            dependencies = self._extract_all_dependencies(local_path, repo_entry_id)
            self._store_dependencies(dependencies)

            # 6. Embed & Store File Summaries
            print(f"[6/5] Embedding {len(file_summaries)} file summaries...")
            self._embed_and_store_summaries(file_summaries)
            
            # 6. Store File Tree & Metadata
            print(f"[6/5] Storing file tree...")
            supabase.table("repositories").update({
                "status": "ready",
                "file_tree": file_tree
            }).eq("id", repo_entry_id).execute()
            
            # Store flat list of files
            self._store_repo_files(file_tree, repo_entry_id)

            # 7. Cleanup & Done
            shutil.rmtree(local_path, onerror=on_rm_error)
            print(f"Ingestion complete for {repo_url}")

        except Exception as e:
            print(f"Sync processing error: {e}")
            raise e

    def _build_file_tree(self, local_path: str) -> dict:
        """Build a structured JSON representation of the file structure."""
        tree = {"name": os.path.basename(local_path), "type": "directory", "children": []}
        allowed_extensions = {'.py', '.ipynb', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.cpp', '.c', '.h', '.md', '.html', '.css', '.sql'}
        
        path_map = {local_path: tree}

        for root, dirs, files in os.walk(local_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.git']]
            
            for d in dirs:
                full_path = os.path.join(root, d)
                node = {"name": d, "type": "directory", "children": []}
                path_map[root]["children"].append(node)
                path_map[full_path] = node
            
            for f in files:
                ext = os.path.splitext(f)[1]
                if ext in allowed_extensions:
                    rel_path = os.path.relpath(os.path.join(root, f), local_path)
                    node = {"name": f, "type": "file", "path": rel_path}
                    path_map[root]["children"].append(node)
        
        return tree

    def _store_repo_files(self, tree: dict, repo_id: str):
        """Extract all file paths and store them in repo_files table."""
        files_to_store = []
        
        def traverse(node):
            if node["type"] == "file":
                files_to_store.append({"repository_id": repo_id, "file_path": node["path"]})
            elif "children" in node:
                for child in node["children"]:
                    traverse(child)
        
        traverse(tree)
        
        if files_to_store:
            try:
                # Batch insert (ignore duplicates if any)
                supabase.table("repo_files").upsert(files_to_store, on_conflict="repository_id, file_path").execute()
            except Exception as e:
                print(f"Error storing repo files: {e}")

    def _parse_chunk_and_summarize(self, local_path: str, repo_entry_id: str):
        """Parse files, create chunks, and generate summaries."""
        documents = []
        file_summaries = []
        allowed_extensions = {'.py', '.ipynb', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.cpp', '.c', '.h', '.md', '.html', '.css', '.sql'}
        
        for root, _, files in os.walk(local_path):
            if ".git" in root or "node_modules" in root or "__pycache__" in root:
                continue
            
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext not in allowed_extensions:
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    content = ""
                    # SPECIAL HANDLING FOR NOTEBOOKS
                    if ext == '.ipynb':
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                notebook = json.load(f)
                                for cell in notebook.get('cells', []):
                                    cell_type = cell.get('cell_type')
                                    source = cell.get('source', [])
                                    if cell_type == 'code':
                                        # Strip Jupyter magics/shell commands which break parsers
                                        filtered = [line for line in source if not line.strip().startswith(('%', '!', '?'))]
                                        content += "".join(filtered) + "\n\n"
                                    elif cell_type == 'markdown':
                                        content += "".join(source) + "\n\n"
                        except Exception as e:
                            print(f"Error parsing notebook {file}: {e}")
                            continue
                    else:
                        # Standard handling for other files
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                    if not content.strip() or len(content) < 50:
                        continue

                    relative_path = os.path.relpath(file_path, local_path)
                    
                    # Generate file summary using LLM
                    summary_data = self._generate_file_summary(relative_path, content, ext)
                    if summary_data:
                        summary_data["repository_id"] = repo_entry_id
                        file_summaries.append(summary_data)
                    
                    # Create code chunks using AST chunker (Phase 2)
                    try:
                        from app.ast_chunker import ast_chunker
                        ast_chunks = ast_chunker.chunk_file(content, relative_path)
                        for chunk in ast_chunks:
                            if len(chunk.text) < 50:
                                continue
                            documents.append({
                                "repository_id": repo_entry_id,
                                "file_path": relative_path,
                                "content": chunk.text,
                                "start_line": chunk.start_line,
                                "end_line": chunk.end_line,
                                "chunk_type": chunk.chunk_type,
                                "chunk_name": chunk.chunk_name,
                            })
                    except ImportError:
                        # Fallback to simple chunking if AST chunker not available
                        chunks = self._smart_chunk_code(content, ext)
                        for chunk in chunks:
                            if len(chunk['text']) < 50:
                                continue
                            documents.append({
                                "repository_id": repo_entry_id,
                                "file_path": relative_path,
                                "content": chunk['text'],
                                "start_line": chunk['start_line'],
                                "end_line": chunk['end_line'],
                                "chunk_type": "code",
                                "chunk_name": None,
                            })
                except Exception as e:
                    print(f"Error processing {file}: {e}")
        
        return documents, file_summaries

    def _generate_file_summary(self, file_path: str, content: str, ext: str) -> dict:
        """Use LLM to create a concise summary of the file's purpose."""
        try:
            # Smart Truncation for LLM context (12k limit)
            limit = 12000
            if len(content) > limit:
                # Capture Head (4k) and Tail (8k) to catch imports and final implementations/results
                head = content[:4000]
                tail = content[-8000:]
                truncated_content = f"{head}\n\n... [TRUNCATED] ...\n\n{tail}"
            else:
                truncated_content = content
            
            prompt = f"""Analyze this code file and provide:
1. A 2-3 sentence summary of what this file does
2. A list of key components (classes, functions, constants) defined in it

File: {file_path}
```
{truncated_content}
```

Respond in this exact format:
SUMMARY: [your 2-3 sentence summary]
COMPONENTS: [component1], [component2], [component3]

Be specific. For example: "Handles user authentication and session management."
"""
            response_text, _ = llm.generate_content(
                mode="analyst",
                prompt=prompt
            )
            
            # Parse response
            summary = ""
            components = []
            
            if "SUMMARY:" in response_text:
                summary_match = re.search(r'SUMMARY:\s*(.+?)(?=COMPONENTS:|$)', response_text, re.DOTALL)
                if summary_match:
                    summary = summary_match.group(1).strip()
            
            if "COMPONENTS:" in response_text:
                components_match = re.search(r'COMPONENTS:\s*(.+?)$', response_text, re.DOTALL)
                if components_match:
                    components_str = components_match.group(1).strip()
                    # Parse comma-separated or bracket-enclosed list
                    components = [c.strip().strip('[]') for c in components_str.split(',') if c.strip()]
            
            if not summary:
                summary = f"Code file: {file_path}"
            
            return {
                "file_path": file_path,
                "summary": summary,
                "key_components": components[:10]  # Limit to 10 components
            }
            
        except Exception as e:
            print(f"Error generating summary for {file_path}: {e}")
            return {
                "file_path": file_path,
                "summary": f"Code file at {file_path}",
                "key_components": []
            }

    def _smart_chunk_code(self, text: str, ext: str, max_chars=1500, overlap=200):
        """
        Splits code into chunks trying to respect functional boundaries.
        Increased chunk size for better context.
        """
        lines = text.split('\n')
        chunks = []
        current_chunk = []
        current_length = 0
        current_start_line = 1
        
        for i, line in enumerate(lines):
            line_len = len(line) + 1
            
            if current_length + line_len > max_chars and current_chunk:
                joined_text = "\n".join(current_chunk)
                chunks.append({
                    "text": joined_text,
                    "start_line": current_start_line,
                    "end_line": current_start_line + len(current_chunk) - 1
                })
                
                # Overlap logic
                overlap_chunk = []
                overlap_len = 0
                for old_line in reversed(current_chunk):
                    if overlap_len + len(old_line) < overlap:
                        overlap_chunk.insert(0, old_line)
                        overlap_len += len(old_line) + 1
                    else:
                        break
                
                current_chunk = overlap_chunk + [line]
                current_length = overlap_len + line_len
                current_start_line = (i + 1) - len(overlap_chunk)
            else:
                current_chunk.append(line)
                current_length += line_len
                
        if current_chunk:
            chunks.append({
                "text": "\n".join(current_chunk),
                "start_line": current_start_line,
                "end_line": current_start_line + len(current_chunk) - 1
            })
            
        return chunks

    def _embed_and_store_chunks(self, documents):
        """Embed and store code chunks."""
        batch_size = 50
        total_docs = len(documents)
        
        for i in range(0, total_docs, batch_size):
            batch = documents[i:i+batch_size]
            texts = [doc["content"] for doc in batch]
            
            response = llm.google_client.models.embed_content(
                model="text-embedding-004",
                contents=texts,
                config={'output_dimensionality': 384}
            )
            embeddings = [e.values for e in response.embeddings]
            
            rows_to_insert = []
            for j, doc in enumerate(batch):
                doc["embedding"] = embeddings[j]
                rows_to_insert.append(doc)
            
            supabase.table("code_chunks").insert(rows_to_insert).execute()

    def _embed_and_store_summaries(self, file_summaries):
        """Embed and store file summaries."""
        if not file_summaries:
            return
            
        batch_size = 20
        total_summaries = len(file_summaries)
        
        for i in range(0, total_summaries, batch_size):
            batch = file_summaries[i:i+batch_size]
            # Embed the summary + key components together for better retrieval
            texts = [f"{s['summary']} Components: {', '.join(s.get('key_components', []))}" for s in batch]
            
            response = llm.google_client.models.embed_content(
                model="text-embedding-004",
                contents=texts,
                config={'output_dimensionality': 384}
            )
            embeddings = [e.values for e in response.embeddings]
            
            rows_to_insert = []
            for j, summary in enumerate(batch):
                summary["embedding"] = embeddings[j]
                rows_to_insert.append(summary)
            
            try:
                supabase.table("file_summaries").insert(rows_to_insert).execute()
            except Exception as e:
                print(f"Error inserting file summaries: {e}")

    def _extract_all_dependencies(self, local_path: str, repo_id: str):
        """Extract dependencies from all files in the repository."""
        all_deps = []
        allowed_extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.cpp', '.c', '.h'}
        
        for root, _, files in os.walk(local_path):
            if ".git" in root or "node_modules" in root or "__pycache__" in root:
                continue
            
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext not in allowed_extensions:
                    continue
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, local_path)
                
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        deps = self._extract_dependencies(content, ext)
                        for target, dep_type in deps:
                            all_deps.append({
                                "repository_id": repo_id,
                                "source_file_path": rel_path,
                                "target_module": target,
                                "dependency_type": dep_type
                            })
                except Exception as e:
                    print(f"Error extracting dependencies from {file}: {e}")
        
        return all_deps

    def _extract_dependencies(self, content: str, ext: str):
        """Extract dependency targets based on file extension."""
        deps = []
        if ext == '.py':
            # import math, from os import path
            import_matches = re.finditer(r'^import\s+([\w\.]+)', content, re.MULTILINE)
            from_matches = re.finditer(r'^from\s+([\w\.]+)\s+import', content, re.MULTILINE)
            for m in import_matches: deps.append((m.group(1), 'import'))
            for m in from_matches: deps.append((m.group(1), 'from'))
        elif ext in ['.js', '.ts', '.tsx', '.jsx']:
            # import React from 'react', const x = require('y')
            import_matches = re.finditer(r'import\s+.*\s+from\s+[\'"](.+)[\'"]', content)
            require_matches = re.finditer(r'require\(\s*[\'"](.+)[\'"]\s*\)', content)
            for m in import_matches: deps.append((m.group(1), 'import'))
            for m in require_matches: deps.append((m.group(1), 'require'))
        elif ext == '.java':
            # import com.example.MyClass;
            matches = re.finditer(r'^import\s+([\w\.]+);', content, re.MULTILINE)
            for m in matches: deps.append((m.group(1), 'import'))
        elif ext == '.go':
            # import "fmt", import ("os")
            matches = re.finditer(r'import\s+[\'"](.+)[\'"]', content)
            for m in matches: deps.append((m.group(1), 'import'))
        elif ext in ['.cpp', '.c', '.h']:
            # #include "my_header.h", #include <vector>
            matches = re.finditer(r'^#include\s+[\'"<](.+)[\'">]', content, re.MULTILINE)
            for m in matches: deps.append((m.group(1), 'include'))
            
        return list(set(deps))

    def _store_dependencies(self, dependencies):
        """Store extracted dependencies in Supabase."""
        if not dependencies:
            return
            
        batch_size = 100
        for i in range(0, len(dependencies), batch_size):
            batch = dependencies[i:i+batch_size]
            try:
                supabase.table("file_dependencies").insert(batch).execute()
            except Exception as e:
                print(f"Error inserting dependencies: {e}")

repo_ingestion_service = RepoIngestionService()
