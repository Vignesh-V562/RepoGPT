-- Phase 2 Schema Updates for Hybrid Search
-- Run this in your Supabase SQL Editor

-- Enable pg_trgm for fuzzy text/keyword search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Add GIN index for keyword search on code_chunks
CREATE INDEX IF NOT EXISTS code_chunks_content_trgm_idx 
ON code_chunks USING GIN (content gin_trgm_ops);

-- Add GIN index for keyword search on file_summaries
CREATE INDEX IF NOT EXISTS file_summaries_summary_trgm_idx 
ON file_summaries USING GIN (summary gin_trgm_ops);

-- Add metadata columns to code_chunks for AST info
ALTER TABLE code_chunks 
ADD COLUMN IF NOT EXISTS chunk_type TEXT DEFAULT 'code',  -- 'function', 'class', 'import', 'code'
ADD COLUMN IF NOT EXISTS chunk_name TEXT;                  -- e.g., 'NeuralNetwork', 'forward'

-- Hybrid Search RPC: Combines vector similarity with keyword matching
CREATE OR REPLACE FUNCTION hybrid_search_chunks (
  query_embedding vector(384),
  query_text text,
  keyword_weight float DEFAULT 0.3,
  vector_weight float DEFAULT 0.7,
  match_count int DEFAULT 20,
  repo_id uuid DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  content text,
  file_path text,
  start_line int,
  end_line int,
  chunk_type text,
  chunk_name text,
  vector_score float,
  keyword_score float,
  combined_score float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    c.id,
    c.content,
    c.file_path,
    c.start_line,
    c.end_line,
    c.chunk_type,
    c.chunk_name,
    (1 - (c.embedding <=> query_embedding))::float AS vector_score,
    COALESCE(similarity(c.content, query_text), 0)::float AS keyword_score,
    (
      vector_weight * (1 - (c.embedding <=> query_embedding)) +
      keyword_weight * COALESCE(similarity(c.content, query_text), 0)
    )::float AS combined_score
  FROM code_chunks c
  WHERE (repo_id IS NULL OR c.repository_id = repo_id)
  ORDER BY combined_score DESC
  LIMIT match_count;
END;
$$;

-- Hybrid Search for File Summaries
CREATE OR REPLACE FUNCTION hybrid_search_file_summaries (
  query_embedding vector(384),
  query_text text,
  keyword_weight float DEFAULT 0.3,
  vector_weight float DEFAULT 0.7,
  match_count int DEFAULT 10,
  repo_id uuid DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  file_path text,
  summary text,
  key_components text[],
  vector_score float,
  keyword_score float,
  combined_score float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    f.id,
    f.file_path,
    f.summary,
    f.key_components,
    (1 - (f.embedding <=> query_embedding))::float AS vector_score,
    COALESCE(similarity(f.summary, query_text), 0)::float AS keyword_score,
    (
      vector_weight * (1 - (f.embedding <=> query_embedding)) +
      keyword_weight * COALESCE(similarity(f.summary, query_text), 0)
    )::float AS combined_score
  FROM file_summaries f
  WHERE (repo_id IS NULL OR f.repository_id = repo_id)
  ORDER BY combined_score DESC
  LIMIT match_count;
END;
$$;
