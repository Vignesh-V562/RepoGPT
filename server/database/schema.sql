-- Enable Vector Extension
create extension if not exists vector;

-- 1. Users (Managed by Supabase Auth, but we link data here - Optional profile table)
-- create table public.profiles (
--   id uuid references auth.users not null primary key,
--   email text
-- );

-- 2. Repositories (The "Knowledge Base")
create table repositories (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users not null,
  url text not null,
  name text not null,
  status text default 'pending', -- 'pending', 'indexing', 'ready', 'failed'
  created_at timestamp with time zone default timezone('utc'::text, now())
);

-- 3. Code Chunks (The "Brain")
create table code_chunks (
  id uuid default gen_random_uuid() primary key,
  repository_id uuid references repositories on delete cascade,
  file_path text not null,
  content text not null,
  start_line int,
  end_line int,
  embedding vector(384) -- Matching FastEmbed dimension
);

-- 4. Chat Sessions (The "Sidebar History")
create table chat_sessions (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users not null,
  title text, -- Auto-generated from first message
  mode text default 'repo_gpt', -- 'architect' or 'repo_gpt'
  repository_id uuid references repositories on delete cascade, -- Optional, only if in Repo Mode
  created_at timestamp with time zone default timezone('utc'::text, now())
);

-- 5. Messages (The "Conversation")
create table messages (
  id uuid default gen_random_uuid() primary key,
  session_id uuid references chat_sessions on delete cascade,
  role text not null, -- 'user' or 'ai'
  content text not null,
  sources jsonb, -- To store file citations
  created_at timestamp with time zone default timezone('utc'::text, now())
);
