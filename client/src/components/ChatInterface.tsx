'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Send, Link as LinkIcon, Terminal, Copy, Check, User, Sparkles, Brain, Code2, Shield, FileText, ChevronRight, AlertTriangle, Github } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { motion, AnimatePresence } from 'framer-motion';
import Modal from './Modal';

interface Message {
    id?: string;
    role: 'user' | 'ai';
    content: string;
    latency?: string;
    type?: 'token' | 'status' | 'error' | 'session' | 'metadata';
}

interface ChatInterfaceProps {
    mode: 'architect' | 'repo';
    sessionId: string | null;
    setSessionId: (id: string) => void;
    userId: string;
    activeRepoId: string | null;
    setActiveRepoId: (id: string | null) => void;
    activeFiles: string[];
    setActiveFiles: (files: string[]) => void;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
    mode,
    sessionId,
    setSessionId,
    userId,
    activeRepoId,
    setActiveRepoId,
    activeFiles,
    setActiveFiles,
}) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [repoUrl, setRepoUrl] = useState('');
    const [repoUrlInput, setRepoUrlInput] = useState('');
    const [urlError, setUrlError] = useState<string | null>(null);
    const [showRepoModal, setShowRepoModal] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [isIngesting, setIsIngesting] = useState(false);
    const [currentStatus, setCurrentStatus] = useState<string | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // Fetch messages whenever sessionId changes and we aren't busy loading
        if (sessionId && !isLoading) {
            fetchMessages();
        } else if (!sessionId && !isLoading) {
            setMessages([]);
        }
    }, [sessionId, isLoading]); // Added isLoading as a dependency to sync after stream finish

    useEffect(() => {
        scrollToBottom();
    }, [messages, currentStatus]);

    const scrollToBottom = (force = false) => {
        if (!messagesEndRef.current) return;

        // Find the scrollable container (the one with overflow-y-auto)
        let container = messagesEndRef.current.parentElement;
        while (container && !container.classList.contains('overflow-y-auto')) {
            container = container.parentElement;
        }

        if (!container) return;

        const isAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 150;

        if (force || isAtBottom) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }
    };

    const fetchMessages = async () => {
        try {
            const res = await fetch(`/api/chat/${sessionId}`);
            const data = await res.json();
            if (Array.isArray(data)) {
                setMessages(data.map((m: any) => ({
                    role: m.role,
                    content: m.content,
                    id: m.id
                })));
            } else {
                console.error("API returned non-array data:", data);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userMsg: Message = { role: 'user', content: input };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setIsLoading(true);
        setCurrentStatus('Thinking...');
        setTimeout(() => scrollToBottom(true), 100);

        try {
            const endpoint = mode === 'architect' ? '/api/chat/analyze' : '/api/chat/stream';
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: input,
                    userId,
                    sessionId,
                    repoId: activeRepoId,
                }),
            });

            if (!response.body) return;

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let aiResponse = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.replace('data: ', '').trim();
                        if (dataStr === '[DONE]') break;

                        try {
                            const data = JSON.parse(dataStr);
                            if (data.type === 'session') {
                                setSessionId(data.sessionId);
                            } else if (data.type === 'status') {
                                setCurrentStatus(data.content);
                            } else if (data.type === 'token') {
                                aiResponse += data.content;
                                setMessages(prev => {
                                    const last = prev[prev.length - 1];
                                    if (last && last.role === 'ai') {
                                        return [...prev.slice(0, -1), { ...last, content: aiResponse }];
                                    } else {
                                        return [...prev, { role: 'ai', content: aiResponse, latency: '1.2s' }];
                                    }
                                });
                            } else if (data.type === 'metadata' && data.files) {
                                setActiveFiles(data.files);
                            }
                        } catch (e) {
                            if (dataStr) {
                                aiResponse += dataStr;
                                setMessages(prev => {
                                    const last = prev[prev.length - 1];
                                    if (last && last.role === 'ai') {
                                        return [...prev.slice(0, -1), { ...last, content: aiResponse }];
                                    } else {
                                        return [...prev, { role: 'ai', content: aiResponse }];
                                    }
                                });
                            }
                        }
                    }
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setIsLoading(false);
            setCurrentStatus(null);
        }
    };

    const validateGithubUrl = (url: string) => {
        const regex = /^(https?:\/\/)?(www\.)?github\.com\/[\w.-]+\/[\w.-]+\/?$/;
        return regex.test(url);
    };

    const handleIngest = async () => {
        if (!repoUrlInput.trim()) {
            setUrlError("Please enter a repository URL");
            return;
        }

        if (!validateGithubUrl(repoUrlInput)) {
            setUrlError("Please enter a valid GitHub repository URL (e.g., https://github.com/owner/repo)");
            return;
        }

        setUrlError(null);
        setIsIngesting(true);
        try {
            const res = await fetch('/api/repo/ingest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repoUrl: repoUrlInput, userId }),
            });
            const data = await res.json();
            if (res.ok) {
                const repoName = repoUrlInput.split('/').pop() || 'repository';
                setActiveRepoId(data.repoId);
                setShowRepoModal(false);
                setRepoUrlInput('');

                // Add success feedback message to chat
                setMessages([{
                    role: 'ai',
                    content: `✅ **Successfully connected to ${repoName}!**\n\nI have started indexing the codebase. You can start asking questions about the logic, architecture, or specific files right away. I'll continue processing the full depth in the background.`,
                    latency: '0.2s'
                }]);

                setCurrentStatus("INGESTION STARTED...");
            } else {
                setUrlError(data.detail || "Failed to start ingestion");
            }
        } catch (err) {
            console.error(err);
            setUrlError("An error occurred. Please try again.");
        } finally {
            setIsIngesting(false);
        }
    };

    return (
        <div className="flex-1 flex flex-col h-full bg-black relative overflow-hidden">
            {/* Background Decor */}
            <div className="absolute top-0 left-0 w-full h-full pointer-events-none opacity-20">
                <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-purple-900/40 rounded-full blur-[120px]" />
                <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-emerald-900/40 rounded-full blur-[120px]" />
            </div>

            <div className="flex-1 overflow-y-auto p-6 pb-32 space-y-8 z-10 scroll-smooth">
                {messages.length === 0 ? (
                    <WelcomeScreen onPrompt={(p) => setInput(p)} />
                ) : (
                    <div className="max-w-4xl mx-auto space-y-8 pb-4">
                        {messages.map((m, i) => (
                            <MessageBubble key={m.id || i} message={m} mode={mode} />
                        ))}
                        {currentStatus && (
                            <div className="flex items-center gap-3 text-xs font-bold text-gray-500 animate-pulse ml-12">
                                <Terminal className="w-4 h-4" />
                                {currentStatus.toUpperCase()}
                            </div>
                        )}
                        <div ref={messagesEndRef} className="h-4" />
                    </div>
                )}
            </div>

            {/* Floating Console Input */}
            <div className="p-6 pb-2 z-20">
                <div className="max-w-3xl mx-auto relative group">
                    <div className="absolute -inset-0.5 bg-gradient-to-r from-purple-500 to-emerald-500 rounded-2xl blur opacity-20 group-focus-within:opacity-40 transition-opacity" />
                    <div className="relative glass p-4 rounded-xl flex flex-col gap-3">
                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder={mode === 'architect' ? "Describe the architecture you want to build..." : "Ask me anything about your codebase..."}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSubmit(e);
                                }
                            }}
                            className="bg-transparent border-none outline-none resize-none text-sm font-bold placeholder-gray-600 min-h-[60px]"
                        />
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => {
                                        setRepoUrlInput('');
                                        setUrlError(null);
                                        setShowRepoModal(true);
                                    }}
                                    className="p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors flex items-center gap-2 text-[10px] font-bold"
                                >
                                    <LinkIcon className="w-3.5 h-3.5" />
                                    ATTACH REPO
                                </button>
                            </div>
                            <button
                                onClick={handleSubmit}
                                disabled={!input.trim() || isLoading}
                                className={`p-2 px-4 rounded-lg font-black text-[10px] transition-all flex items-center gap-2 ${input.trim() ? 'bg-white text-black shadow-[0_0_15px_rgba(255,255,255,0.3)]' : 'bg-gray-800 text-gray-500'}`}
                            >
                                <Send className="w-3.5 h-3.5" />
                                SEND
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Ingestion Modal */}
            <Modal
                isOpen={showRepoModal}
                onClose={() => setShowRepoModal(false)}
                title="Attach Repository"
                confirmLabel="Start Ingestion"
                onConfirm={handleIngest}
                isLoading={isIngesting}
            >
                <div className="space-y-4">
                    <div className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/20 flex gap-4">
                        <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center shrink-0">
                            <Github className="w-5 h-5 text-purple-400" />
                        </div>
                        <div className="space-y-1">
                            <p className="text-xs font-bold">Connect your code</p>
                            <p className="text-[10px] text-gray-500">Provide a public GitHub repository URL to start the analysis.</p>
                        </div>
                    </div>

                    <div className="space-y-2">
                        <label className="text-[10px] font-black text-gray-500 uppercase tracking-widest ml-1">Repository URL</label>
                        <div className="relative group">
                            <div className="absolute -inset-0.5 bg-gradient-to-r from-purple-500 to-emerald-500 rounded-lg blur opacity-20 group-focus-within:opacity-50 transition-opacity" />
                            <input
                                type="text"
                                value={repoUrlInput}
                                onChange={(e) => setRepoUrlInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') handleIngest();
                                }}
                                placeholder="https://github.com/owner/repo"
                                className="relative w-full bg-black border border-white/10 rounded-lg p-3 text-sm font-bold focus:outline-none focus:border-white/20 transition-all"
                            />
                        </div>
                        {urlError && (
                            <motion.div
                                initial={{ opacity: 0, y: -10 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="flex items-center gap-2 text-red-400 text-[10px] font-bold mt-2 ml-1"
                            >
                                <AlertTriangle className="w-3 h-3" />
                                {urlError}
                            </motion.div>
                        )}
                    </div>
                </div>
            </Modal>
        </div>
    );
};

const WelcomeScreen = ({ onPrompt }: { onPrompt: (p: string) => void }) => (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="h-full flex flex-col items-center justify-center max-w-4xl mx-auto"
    >
        <div className="flex items-center gap-4 mb-8">
            <Terminal className="w-12 h-12 text-purple-500" />
            <h1 className="text-4xl font-black gradient-text tracking-tighter uppercase leading-none">
                RepoGPT
            </h1>
        </div>

        <div className="text-lg font-bold text-gray-400 mb-12 text-center h-8">
            CHAT WITH YOUR CODEBASE.
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
            <StarterCard
                icon={<Brain className="text-purple-400" />}
                title="Plan a new project"
                desc="Use Architect mode to ideate features and stack."
                onClick={() => onPrompt("Help me plan a University LMS with React and Spring Boot.")}
            />
            <StarterCard
                icon={<Code2 className="text-emerald-400" />}
                title="Explain Auth logic"
                desc="Deep dive into how authentication is handled."
                onClick={() => onPrompt("Explain how Google Auth is implemented in this codebase.")}
            />
            <StarterCard
                icon={<Shield className="text-red-400" />}
                title="Find security bugs"
                desc="Scan for common vulnerabilities and leaks."
                onClick={() => onPrompt("Check the codebase for any exposed API keys or security flaws.")}
            />
            <StarterCard
                icon={<FileText className="text-blue-400" />}
                title="Generate a README"
                desc="Create professional documentation automatically."
                onClick={() => onPrompt("Generate a professional README.md for this project.")}
            />
        </div>
    </motion.div>
);

const StarterCard = ({ icon, title, desc, onClick }: any) => (
    <button
        onClick={onClick}
        className="glass p-4 rounded-xl text-left transition-all hover:bg-white/5 hover:border-white/20 group"
    >
        <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-lg bg-black/50 flex items-center justify-center border border-white/5">
                {icon}
            </div>
            <span className="font-black text-xs uppercase tracking-wider">{title}</span>
        </div>
        <p className="text-[10px] text-gray-500 font-bold group-hover:text-gray-300 transition-colors">{desc}</p>
    </button>
);

const MessageBubble = ({ message, mode }: { message: Message, mode: string }) => {
    const isUser = message.role === 'user';

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.98, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className={`flex ${isUser ? 'justify-end' : 'justify-start'} w-full relative`}
        >
            <div className={`p-4 rounded-2xl max-w-[85%] ${isUser
                ? 'bg-gray-900/80 border border-gray-700 text-gray-100 font-bold text-sm ml-12'
                : `glass-${mode === 'architect' ? 'purple' : 'emerald'} mr-12`
                }`}>
                {!isUser && (
                    <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/5">
                        <div className="flex items-center gap-2">
                            <div className={`w-2 h-2 rounded-full ${mode === 'architect' ? 'bg-purple-500 shadow-[0_0_8px_rgba(139,92,246,0.6)]' : 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]'}`} />
                            <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">RepoGPT</span>
                            <span className="text-[8px] font-bold text-gray-600 ml-2">{message.latency || '0.8s'}</span>
                        </div>
                        <Sparkles className={`w-3 h-3 ${mode === 'architect' ? 'text-purple-400' : 'text-emerald-400'}`} />
                    </div>
                )}

                <div className={`text-sm leading-relaxed ${!isUser ? 'text-gray-300' : ''}`}>
                    <ReactMarkdown
                        components={{
                            code({ node, inline, className, children, ...props }: any) {
                                const match = /language-(\w+)/.exec(className || '');
                                return !inline && match ? (
                                    <div className="my-6 rounded-lg overflow-hidden border border-gray-800 shadow-2xl">
                                        <div className="bg-gray-900 px-4 py-2 flex items-center justify-between border-b border-gray-800">
                                            <span className="text-[9px] font-black text-gray-500 uppercase tracking-tighter">
                                                {match[1]}
                                            </span>
                                            <button className="text-gray-500 hover:text-white transition-colors">
                                                <Copy className="w-3 h-3" />
                                            </button>
                                        </div>
                                        <SyntaxHighlighter
                                            style={vscDarkPlus}
                                            language={match[1]}
                                            PreTag="div"
                                            customStyle={{ margin: 0, padding: '1rem', background: '#0a0a0c', fontSize: '11px' }}
                                            {...props}
                                        >
                                            {String(children).replace(/\n$/, '')}
                                        </SyntaxHighlighter>
                                    </div>
                                ) : (
                                    <code className="bg-gray-800 px-1.5 py-0.5 rounded text-xs font-bold text-purple-300" {...props}>
                                        {children}
                                    </code>
                                );
                            },
                            h1: ({ children }) => <h1 className="text-lg font-black mt-6 mb-2 text-white border-l-4 border-purple-500 pl-3">{children}</h1>,
                            h2: ({ children }) => <h2 className="text-base font-black mt-5 mb-2 text-white">{children}</h2>,
                            h3: ({ children }) => <h3 className="text-sm font-black mt-4 mb-2 text-gray-100">{children}</h3>,
                            ul: ({ children }) => <ul className="space-y-2 my-4">{children}</ul>,
                            li: ({ children }) => (
                                <li className="flex gap-2">
                                    <span className="text-purple-500 font-black">›</span>
                                    <span>{children}</span>
                                </li>
                            ),
                            p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>
                        }}
                    >
                        {message.content}
                    </ReactMarkdown>
                </div>

                {!isUser && message.content.includes("src/") && (
                    <div className="mt-6 pt-4 border-t border-white/5 flex flex-wrap gap-2">
                        <span className="text-[10px] font-black text-gray-500 mr-2 uppercase self-center">Citations:</span>
                        <CitationChip file="src/utils.py" lines="10-15" />
                    </div>
                )}
            </div>
        </motion.div>
    );
};

const CitationChip = ({ file, lines }: { file: string, lines: string }) => (
    <button className="flex items-center gap-2 px-2 py-1 rounded bg-gray-900 border border-gray-800 hover:border-gray-600 transition-all group">
        <FileText className="w-3 h-3 text-emerald-500" />
        <span className="text-[9px] font-bold text-gray-400 group-hover:text-white">{file}</span>
        <span className="text-[8px] text-gray-600 font-bold">{lines}</span>
    </button>
);

export default ChatInterface;
