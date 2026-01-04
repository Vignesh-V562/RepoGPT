-- Table to store cross-file dependencies
CREATE TABLE IF NOT EXISTS file_dependencies (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    source_file_path TEXT NOT NULL,
    target_module TEXT NOT NULL, -- The imported module name or file path
    dependency_type TEXT, -- e.g., 'import', 'require', 'from'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Index for faster lookup of dependencies for a given file
CREATE INDEX IF NOT EXISTS idx_file_dependencies_source ON file_dependencies(repository_id, source_file_path);
