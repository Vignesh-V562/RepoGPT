-- Phase 2.1: Store File Tree for Mapping
ALTER TABLE repositories ADD COLUMN IF NOT EXISTS file_tree JSONB;

-- Table to store a flat list of all files for easier lookups if needed
-- (Optional, but useful for the Repo Map heat zones)
CREATE TABLE IF NOT EXISTS repo_files (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    UNIQUE(repository_id, file_path)
);
