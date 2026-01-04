-- File Summaries Table for Hierarchical RAG
-- Run this in your Supabase SQL Editor

CREATE TABLE IF NOT EXISTS file_summaries (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  repository_id UUID REFERENCES repositories ON DELETE CASCADE,
  file_path TEXT NOT NULL,
  summary TEXT NOT NULL,
  key_components TEXT[], -- e.g., ['NeuralNetwork class', 'forward() method', 'Layer class']
  embedding VECTOR(384),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
  UNIQUE(repository_id, file_path)
);

-- Index for faster similarity search
CREATE INDEX IF NOT EXISTS file_summaries_embedding_idx ON file_summaries 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- RPC: Match file summaries (Stage 1 of hierarchical retrieval)
CREATE OR REPLACE FUNCTION match_file_summaries (
  query_embedding vector(384),
  match_threshold float,
  match_count int,
  repo_id uuid
)
RETURNS TABLE (
  id uuid,
  file_path text,
  summary text,
  key_components text[],
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    file_summaries.id,
    file_summaries.file_path,
    file_summaries.summary,
    file_summaries.key_components,
    1 - (file_summaries.embedding <=> query_embedding) AS similarity
  FROM file_summaries
  WHERE file_summaries.repository_id = repo_id
  AND 1 - (file_summaries.embedding <=> query_embedding) > match_threshold
  ORDER BY file_summaries.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- RPC: Match code chunks filtered by specific files (Stage 2)
CREATE OR REPLACE FUNCTION match_code_chunks_in_files (
  query_embedding vector(384),
  match_threshold float,
  match_count int,
  repo_id uuid,
  file_paths text[]
)
RETURNS TABLE (
  id uuid,
  content text,
  file_path text,
  start_line int,
  end_line int,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    code_chunks.id,
    code_chunks.content,
    code_chunks.file_path,
    code_chunks.start_line,
    code_chunks.end_line,
    1 - (code_chunks.embedding <=> query_embedding) AS similarity
  FROM code_chunks
  WHERE code_chunks.repository_id = repo_id
  AND code_chunks.file_path = ANY(file_paths)
  AND 1 - (code_chunks.embedding <=> query_embedding) > match_threshold
  ORDER BY code_chunks.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Update original match_code_chunks to also return line numbers
CREATE OR REPLACE FUNCTION match_code_chunks (
  query_embedding vector(384),
  match_threshold float,
  match_count int,
  repo_id uuid
)
RETURNS TABLE (
  id uuid,
  content text,
  file_path text,
  start_line int,
  end_line int,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    code_chunks.id,
    code_chunks.content,
    code_chunks.file_path,
    code_chunks.start_line,
    code_chunks.end_line,
    1 - (code_chunks.embedding <=> query_embedding) AS similarity
  FROM code_chunks
  WHERE code_chunks.repository_id = repo_id
  AND 1 - (code_chunks.embedding <=> query_embedding) > match_threshold
  ORDER BY code_chunks.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
