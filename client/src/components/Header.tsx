'use client';

import React from 'react';
import { Layout, Brain, Code2, Terminal, Monitor, RefreshCw, CheckCircle2 } from 'lucide-react';
import { motion } from 'framer-motion';

interface HeaderProps {
    mode: 'architect' | 'repo';
    setMode: (mode: 'architect' | 'repo') => void;
    repoStatus?: 'pending' | 'ready' | 'error' | null;
}

const Header: React.FC<HeaderProps> = ({ mode, setMode, repoStatus }) => {
    return (
        <header className="h-16 border-b border-gray-800 bg-black/50 backdrop-blur-md flex items-center justify-between px-6 z-50">
            <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded bg-gradient-to-br from-purple-500 to-emerald-500 flex items-center justify-center">
                    <Terminal className="w-5 h-5 text-black" />
                </div>
                <h1 className="text-xl font-bold gradient-text tracking-tighter">
                    RepoGPT
                </h1>
            </div>

            <div className="flex items-center gap-1 bg-gray-900/50 p-1 rounded-full border border-gray-800">
                <button
                    onClick={() => setMode('architect')}
                    className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all flex items-center gap-2 ${mode === 'architect'
                            ? 'bg-purple-500 text-white shadow-[0_0_15px_rgba(139,92,246,0.5)]'
                            : 'text-gray-500 hover:text-gray-300'
                        }`}
                >
                    <Brain className="w-3.5 h-3.5" />
                    ARCHITECT
                </button>
                <button
                    onClick={() => setMode('repo')}
                    className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all flex items-center gap-2 ${mode === 'repo'
                            ? 'bg-emerald-500 text-black shadow-[0_0_15px_rgba(16,185,129,0.5)]'
                            : 'text-gray-500 hover:text-gray-300'
                        }`}
                >
                    <Code2 className="w-3.5 h-3.5" />
                    ANALYST
                </button>
            </div>

            <div className="flex items-center gap-4">
                {repoStatus === 'ready' && (
                    <div className="flex items-center gap-2 text-[10px] font-bold text-emerald-500 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                        <CheckCircle2 className="w-3 h-3" />
                        INDEXED
                    </div>
                )}
                {repoStatus === 'pending' && (
                    <div className="flex items-center gap-2 text-[10px] font-bold text-purple-400 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20">
                        <RefreshCw className="w-3 h-3 animate-spin" />
                        INDEXING
                    </div>
                )}
                <div className="w-8 h-8 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center">
                    <Monitor className="w-4 h-4 text-gray-400" />
                </div>
            </div>
        </header>
    );
};

export default Header;
