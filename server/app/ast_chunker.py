"""
AST-based Semantic Code Chunker using Tree-sitter

This module provides intelligent code chunking that respects code structure:
- Functions are kept as single units (with their docstrings)
- Classes include their method signatures
- Import blocks are grouped together
- Fallback to line-based chunking for unsupported languages
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from tree_sitter_language_pack import get_language
    from tree_sitter import Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    print("Warning: tree-sitter or language packages not available. Falling back to regex-based chunking.")


@dataclass
class CodeChunk:
    """Represents a semantic chunk of code."""
    text: str
    start_line: int
    end_line: int
    chunk_type: str  # 'function', 'class', 'import', 'code'
    chunk_name: Optional[str] = None


class ASTChunker:
    """
    Intelligent code chunker that uses AST parsing to create semantically meaningful chunks.
    """
    
    def __init__(self, max_chunk_size: int = 2000, overlap: int = 200):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.parsers = {}
        
        if TREE_SITTER_AVAILABLE:
            self._init_parsers()
    
    def _init_parsers(self):
        """Initialize tree-sitter parsers for all supported languages."""
        try:
            # A list of languages supported by tree-sitter-language-pack
            supported_languages = [
                "python", "javascript", "java", "go", "cpp", "ruby", "rust", "php", "c_sharp", "swift", 
                "kotlin", "scala", "shell", "html", "css", "typescript", "c", "lua", "perl", "r", 
                "zig", "d", "elixir", "elm", "erlang", "fennel", "gleam", "haskell", "janet", 
                "julia", "nim", "ocaml", "pascal", "rescript", "verilog", "vhdl", "v", "wat"
            ]
            for lang in supported_languages:
                try:
                    self.parsers[lang] = Parser(get_language(lang))
                except Exception:
                    # Silently ignore languages that are not available
                    pass
        except Exception as e:
            print(f"Error initializing tree-sitter parsers: {e}")
    
    def chunk_file(self, content: str, file_path: str) -> List[CodeChunk]:
        """
        Chunk a file based on its language and structure.
        """
        ext = self._get_extension(file_path)
        language = self._ext_to_language(ext)
        
        if TREE_SITTER_AVAILABLE and language in self.parsers:
            return self._ast_chunk(content, language)
        else:
            return self._regex_chunk(content, ext)
    
    def _get_extension(self, file_path: str) -> str:
        return file_path.split('.')[-1].lower() if '.' in file_path else ''
    
    def _ext_to_language(self, ext: str) -> str:
        mapping = {
            'py': 'python', 'pyw': 'python', 'pyi': 'python',
            'js': 'javascript', 'jsx': 'javascript', 'mjs': 'javascript', 'cjs': 'javascript',
            'java': 'java', 'class': 'java',
            'go': 'go',
            'cpp': 'cpp', 'cxx': 'cpp', 'cc': 'cpp', 'h': 'cpp', 'hpp': 'cpp', 'hxx': 'cpp',
            'rb': 'ruby', 'rbw': 'ruby',
            'rs': 'rust',
            'php': 'php', 'phtml': 'php', 'php3': 'php', 'php4': 'php', 'php5': 'php', 'phps': 'php',
            'cs': 'c_sharp',
            'swift': 'swift',
            'kt': 'kotlin', 'kts': 'kotlin',
            'scala': 'scala', 'sc': 'scala',
            'sh': 'shell', 'bash': 'shell', 'zsh': 'shell',
            'html': 'html', 'htm': 'html',
            'css': 'css',
            'ts': 'typescript', 'tsx': 'typescript',
            'c': 'c',
            'lua': 'lua',
            'pl': 'perl', 'pm': 'perl',
            'r': 'r',
            'zig': 'zig',
            'd': 'd',
            'ex': 'elixir', 'exs': 'elixir',
            'elm': 'elm',
            'erl': 'erlang', 'hrl': 'erlang',
            'fnl': 'fennel',
            'gleam': 'gleam',
            'hs': 'haskell',
            'janet': 'janet',
            'jl': 'julia',
            'nim': 'nim',
            'ml': 'ocaml', 'mli': 'ocaml',
            'pas': 'pascal', 'pp': 'pascal',
            'res': 'rescript', 'resi': 'rescript',
            'v': 'verilog',
            'vhd': 'vhdl', 'vhdl': 'vhdl',
            'v': 'v',
            'wat': 'wat',
        }
        return mapping.get(ext, '')
    
    def _ast_chunk(self, content: str, language: str) -> List[CodeChunk]:
        """Use tree-sitter to parse and chunk code."""
        parser = self.parsers[language]
        tree = parser.parse(bytes(content, 'utf8'))
        root = tree.root_node
        
        chunks = []
        lines = content.split('\n')
        
        # Collect all top-level definitions
        definitions = []
        self._collect_definitions(root, definitions, language)
        
        # Convert definitions to chunks
        for defn in definitions:
            start_line = defn['start_line']
            end_line = defn['end_line']
            chunk_text = '\n'.join(lines[start_line:end_line + 1])
            
            # If chunk is too large, split it
            if len(chunk_text) > self.max_chunk_size:
                sub_chunks = self._split_large_chunk(chunk_text, start_line, defn['type'], defn['name'])
                chunks.extend(sub_chunks)
            else:
                chunks.append(CodeChunk(
                    text=chunk_text,
                    start_line=start_line + 1,  # 1-indexed
                    end_line=end_line + 1,
                    chunk_type=defn['type'],
                    chunk_name=defn['name']
                ))
        
        # Handle code not covered by definitions
        covered_lines = set()
        for defn in definitions:
            for i in range(defn['start_line'], defn['end_line'] + 1):
                covered_lines.add(i)
        
        # Collect uncovered lines into chunks
        uncovered_chunks = self._chunk_uncovered_lines(lines, covered_lines)
        chunks.extend(uncovered_chunks)
        
        # Sort by start line
        chunks.sort(key=lambda c: c.start_line)
        
        return chunks
    
    def _collect_definitions(self, node, definitions: List[Dict], language: str):
        """Recursively collect function and class definitions."""
        target_types = []
        if language == 'python':
            target_types = ['function_definition', 'class_definition', 'import_statement', 'import_from_statement']
        elif language == 'java':
            target_types = ['method_declaration', 'class_declaration', 'interface_declaration', 'import_declaration']
        elif language == 'go':
            target_types = ['function_declaration', 'method_declaration', 'type_declaration', 'import_declaration']
        elif language == 'cpp':
            target_types = ['function_definition', 'class_specifier', 'struct_specifier']
        elif language in ['javascript', 'typescript']:
            target_types = ['function_declaration', 'class_declaration', 'arrow_function', 'import_statement', 'export_statement']
        elif language == 'ruby':
            target_types = ['method', 'class', 'module']
        elif language == 'rust':
            target_types = ['function_item', 'struct_item', 'enum_item', 'impl_item', 'trait_item', 'use_declaration']
        elif language == 'php':
            target_types = ['function_definition', 'class_declaration', 'trait_declaration', 'interface_declaration', 'namespace_definition']
        elif language == 'c_sharp':
            target_types = ['method_declaration', 'class_declaration', 'struct_declaration', 'interface_declaration', 'enum_declaration', 'namespace_declaration']
        elif language == 'swift':
            target_types = ['function_declaration', 'class_declaration', 'struct_declaration', 'enum_declaration', 'protocol_declaration', 'import_declaration']
        elif language == 'kotlin':
            target_types = ['function_declaration', 'class_declaration', 'object_declaration', 'import_header']
        elif language == 'scala':
            target_types = ['function_definition', 'class_definition', 'object_definition', 'trait_definition', 'import_declaration']
        elif language == 'shell':
            target_types = ['function_definition']
        elif language == 'html':
            target_types = ['element']
        elif language == 'css':
            target_types = ['rule_set']
        elif language == 'c':
            target_types = ['function_definition', 'struct_specifier', 'enum_specifier', 'union_specifier']
        elif language == 'lua':
            target_types = ['function_declaration', 'function_call']
        elif language == 'perl':
            target_types = ['sub_declaration']
        elif language == 'r':
            target_types = ['function_definition']
        else:
            # Generic fallback for other languages
            target_types = ['function_definition', 'class_definition', 'function_declaration', 'class_declaration']

        if node.type in target_types:
            name = self._extract_name(node, language)
            chunk_type = self._node_type_to_chunk_type(node.type)
            
            definitions.append({
                'start_line': node.start_point[0],
                'end_line': node.end_point[0],
                'type': chunk_type,
                'name': name
            })
            # Do not recurse into children of a captured definition
            return

        for child in node.children:
            self._collect_definitions(child, definitions, language)

    
    def _extract_name(self, node, language: str) -> Optional[str]:
        """Extract the name of a function or class from its AST node."""
        for child in node.children:
            if child.type == 'identifier' or child.type == 'name':
                return child.text.decode('utf8')
        return None
    
    def _node_type_to_chunk_type(self, node_type: str) -> str:
        mapping = {
            'function_definition': 'function',
            'function_declaration': 'function',
            'arrow_function': 'function',
            'class_definition': 'class',
            'class_declaration': 'class',
            'import_statement': 'import',
            'import_from_statement': 'import',
        }
        return mapping.get(node_type, 'code')
    
    def _split_large_chunk(self, text: str, start_line: int, chunk_type: str, chunk_name: str) -> List[CodeChunk]:
        """Split an oversized chunk while preserving some context."""
        chunks = []
        lines = text.split('\n')
        current_chunk = []
        current_length = 0
        current_start = 0
        
        for i, line in enumerate(lines):
            line_len = len(line) + 1
            
            if current_length + line_len > self.max_chunk_size and current_chunk:
                chunk_text = '\n'.join(current_chunk)
                chunks.append(CodeChunk(
                    text=chunk_text,
                    start_line=start_line + current_start + 1,
                    end_line=start_line + i,
                    chunk_type=chunk_type,
                    chunk_name=f"{chunk_name}_part{len(chunks)+1}" if chunk_name else None
                ))
                
                # Overlap
                overlap_lines = []
                overlap_len = 0
                for old_line in reversed(current_chunk):
                    if overlap_len + len(old_line) < self.overlap:
                        overlap_lines.insert(0, old_line)
                        overlap_len += len(old_line) + 1
                    else:
                        break
                
                current_chunk = overlap_lines + [line]
                current_length = overlap_len + line_len
                current_start = i - len(overlap_lines)
            else:
                current_chunk.append(line)
                current_length += line_len
        
        if current_chunk:
            chunks.append(CodeChunk(
                text='\n'.join(current_chunk),
                start_line=start_line + current_start + 1,
                end_line=start_line + len(lines),
                chunk_type=chunk_type,
                chunk_name=f"{chunk_name}_part{len(chunks)+1}" if chunk_name else None
            ))
        
        return chunks
    
    def _chunk_uncovered_lines(self, lines: List[str], covered: set) -> List[CodeChunk]:
        """Chunk lines that weren't part of any definition."""
        chunks = []
        current_chunk = []
        current_start = None
        current_length = 0
        
        for i, line in enumerate(lines):
            if i in covered:
                if current_chunk:
                    chunks.append(CodeChunk(
                        text='\n'.join(current_chunk),
                        start_line=current_start + 1,
                        end_line=i,
                        chunk_type='code',
                        chunk_name=None
                    ))
                    current_chunk = []
                    current_start = None
                    current_length = 0
                continue
            
            if current_start is None:
                current_start = i
            
            line_len = len(line) + 1
            if current_length + line_len > self.max_chunk_size and current_chunk:
                chunks.append(CodeChunk(
                    text='\n'.join(current_chunk),
                    start_line=current_start + 1,
                    end_line=i,
                    chunk_type='code',
                    chunk_name=None
                ))
                current_chunk = [line]
                current_start = i
                current_length = line_len
            else:
                current_chunk.append(line)
                current_length += line_len
        
        if current_chunk:
            chunks.append(CodeChunk(
                text='\n'.join(current_chunk),
                start_line=current_start + 1,
                end_line=len(lines),
                chunk_type='code',
                chunk_name=None
            ))
        
        return [c for c in chunks if len(c.text.strip()) > 50]
    
    def _regex_chunk(self, content: str, ext: str) -> List[CodeChunk]:
        """Fallback regex-based chunking for unsupported languages."""
        chunks = []
        lines = content.split('\n')
        
        # Patterns for common constructs
        patterns = {
            'py': [
                (r'^class\s+(\w+)', 'class'),
                (r'^def\s+(\w+)', 'function'),
                (r'^async\s+def\s+(\w+)', 'function'),
            ],
            'js': [
                (r'^class\s+(\w+)', 'class'),
                (r'^function\s+(\w+)', 'function'),
                (r'^const\s+(\w+)\s*=\s*(?:async\s*)?\(', 'function'),
                (r'^export\s+(?:default\s+)?function\s+(\w+)', 'function'),
            ],
        }
        
        lang_patterns = patterns.get(ext, [])
        
        if not lang_patterns:
            # Simple line-based chunking
            return self._simple_chunk(content)
        
        # Find all definitions
        definitions = []
        for i, line in enumerate(lines):
            for pattern, chunk_type in lang_patterns:
                match = re.match(pattern, line)
                if match:
                    name = match.group(1) if match.groups() else None
                    definitions.append({
                        'line': i,
                        'type': chunk_type,
                        'name': name
                    })
                    break
        
        # Create chunks around definitions
        if not definitions:
            return self._simple_chunk(content)
        
        for idx, defn in enumerate(definitions):
            start = defn['line']
            end = definitions[idx + 1]['line'] - 1 if idx + 1 < len(definitions) else len(lines) - 1
            
            chunk_text = '\n'.join(lines[start:end + 1])
            if len(chunk_text.strip()) > 50:
                chunks.append(CodeChunk(
                    text=chunk_text,
                    start_line=start + 1,
                    end_line=end + 1,
                    chunk_type=defn['type'],
                    chunk_name=defn['name']
                ))
        
        return chunks
    
    def _simple_chunk(self, content: str) -> List[CodeChunk]:
        """Simple line-based chunking as last resort."""
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_length = 0
        current_start = 1
        
        for i, line in enumerate(lines):
            line_len = len(line) + 1
            
            if current_length + line_len > self.max_chunk_size and current_chunk:
                chunks.append(CodeChunk(
                    text='\n'.join(current_chunk),
                    start_line=current_start,
                    end_line=i,
                    chunk_type='code',
                    chunk_name=None
                ))
                current_chunk = [line]
                current_length = line_len
                current_start = i + 1
            else:
                current_chunk.append(line)
                current_length += line_len
        
        if current_chunk:
            chunks.append(CodeChunk(
                text='\n'.join(current_chunk),
                start_line=current_start,
                end_line=len(lines),
                chunk_type='code',
                chunk_name=None
            ))
        
        return [c for c in chunks if len(c.text.strip()) > 50]


# Singleton instance
ast_chunker = ASTChunker()
