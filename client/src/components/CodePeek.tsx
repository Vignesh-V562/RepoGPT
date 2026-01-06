'use client';

import React, { useEffect, useState } from 'react';
import { X, Copy, ExternalLink, FileCode } from 'lucide-react';
import { supabase } from '@/lib/supabase';

interface CodePeekProps {
    isOpen: boolean;
    onClose: () => void;
    filePath: string;
    repoId: string;
    lineRange?: string; // e.g., "10-20"
}

export default function CodePeek({ isOpen, onClose, filePath, repoId, lineRange }: CodePeekProps) {
    const [content, setContent] = useState<string>('');
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        if (isOpen && filePath && repoId) {
            fetchCode();
        }
    }, [isOpen, filePath, repoId]);

    const fetchCode = async () => {
        setIsLoading(true);
        try {
            // Find chunks for this file
            const { data, error } = await supabase
                .from('code_chunks')
                .select('content, start_line, end_line')
                .eq('repository_id', repoId)
                .eq('file_path', filePath)
                .order('start_line', { ascending: true });

            if (data && data.length > 0) {
                // Combine chunks or find the relevant range
                const fullContent = data.map(c => c.content).join('\n---\n');
                setContent(fullContent);
            } else {
                setContent('Code not found in indexed chunks.');
            }
        } catch (err) {
            console.error("Error fetching code peek:", err);
            setContent('Error loading code.');
        } finally {
            setIsLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-y-0 right-0 w-full max-w-2xl bg-[#0f0f11] border-l border-white/10 shadow-2xl z-50 animate-in slide-in-from-right duration-300 flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-white/5 bg-white/[0.02]">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-500/10 rounded-lg">
                        <FileCode size={18} className="text-blue-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-bold text-white truncate max-w-[300px]">{filePath.split('/').pop()}</h3>
                        <p className="text-[10px] text-zinc-500 font-mono">{filePath} {lineRange ? `(Lines ${lineRange})` : ''}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button onClick={() => navigator.clipboard.writeText(content)} className="p-2 text-zinc-500 hover:text-white transition-colors" title="Copy code">
                        <Copy size={18} />
                    </button>
                    <button onClick={onClose} className="p-2 text-zinc-500 hover:text-white transition-colors">
                        <X size={20} />
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-auto p-6 custom-scrollbar bg-[#0a0a0c]">
                {isLoading ? (
                    <div className="space-y-4 animate-pulse">
                        {[...Array(10)].map((_, i) => (
                            <div key={i} className="h-4 bg-white/5 rounded w-full" style={{ width: `${Math.random() * 40 + 60}%` }} />
                        ))}
                    </div>
                ) : (
                    <pre className="text-xs font-mono text-zinc-300 whitespace-pre-wrap leading-relaxed">
                        {content}
                    </pre>
                )}
            </div>

            <div className="p-4 border-t border-white/5 bg-white/[0.02] flex justify-end">
                <button
                    onClick={onClose}
                    className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-xs font-semibold transition-colors"
                >
                    Close Preview
                </button>
            </div>
        </div>
    );
}
