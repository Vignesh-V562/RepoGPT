'use client';

import React from 'react';
import { Folder, FileText, ChevronRight, ChevronDown } from 'lucide-react';

interface FileNode {
    name: string;
    type: 'file' | 'directory';
    path?: string;
    children?: FileNode[];
}

interface RepoMapProps {
    tree: FileNode;
    activeFiles: string[];
}

const TreeNode: React.FC<{ node: FileNode; level: number; activeFiles: string[] }> = ({ node, level, activeFiles }) => {
    const [isOpen, setIsOpen] = React.useState(level < 1); // Auto-expand root
    const isDirectory = node.type === 'directory';
    const isActive = node.path && activeFiles.includes(node.path);

    return (
        <div className="select-none">
            <div
                className={`flex items-center gap-1.5 py-1 px-2 rounded-md transition-colors cursor-pointer text-xs ${isActive ? 'bg-blue-500/20 text-blue-300 font-semibold' : 'hover:bg-white/5 text-zinc-400'
                    }`}
                style={{ paddingLeft: `${level * 12 + 8}px` }}
                onClick={() => isDirectory && setIsOpen(!isOpen)}
            >
                {isDirectory && (
                    isOpen ? <ChevronDown size={12} className="shrink-0" /> : <ChevronRight size={12} className="shrink-0" />
                )}
                {!isDirectory && <FileText size={12} className={`shrink-0 ${isActive ? 'text-blue-400' : 'text-zinc-600'}`} />}
                {isDirectory && <Folder size={12} className="shrink-0 text-blue-500/60" />}
                <span className="truncate">{node.name}</span>
                {isActive && (
                    <div className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.8)]" />
                )}
            </div>
            {isDirectory && isOpen && node.children && (
                <div>
                    {node.children.map((child, i) => (
                        <TreeNode key={i} node={child} level={level + 1} activeFiles={activeFiles} />
                    ))}
                </div>
            )}
        </div>
    );
};

export default function RepoMap({ tree, activeFiles }: RepoMapProps) {
    if (!tree) return null;

    return (
        <div className="space-y-1">
            <div className="flex items-center justify-between mb-2 px-3">
                <span className="text-[10px] font-bold uppercase text-zinc-600 tracking-[0.2em]">Repository Map</span>
                {activeFiles.length > 0 && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 animate-pulse">
                        {activeFiles.length} files active
                    </span>
                )}
            </div>
            <div className="max-h-[300px] overflow-y-auto custom-scrollbar bg-white/[0.02] rounded-xl border border-white/5 p-2">
                <TreeNode node={tree} level={0} activeFiles={activeFiles} />
            </div>
        </div>
    );
}
