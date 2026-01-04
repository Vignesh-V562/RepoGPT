create or replace function match_code_chunks (
  query_embedding vector(384),
  match_threshold float,
  match_count int,
  repo_id uuid
)
returns table (
  id uuid,
  content text,
  file_path text,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    code_chunks.id,
    code_chunks.content,
    code_chunks.file_path,
    1 - (code_chunks.embedding <=> query_embedding) as similarity
  from code_chunks
  where repository_id = repo_id
  and 1 - (code_chunks.embedding <=> query_embedding) > match_threshold
  order by code_chunks.embedding <=> query_embedding
  limit match_count;
end;
$$;
