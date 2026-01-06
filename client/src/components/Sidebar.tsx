'use client';

import React, { useEffect, useState } from 'react';
import { Plus, MessageSquare, Clock, Settings, Trash2, ChevronLeft, ChevronRight, Bookmark, AlertTriangle } from 'lucide-react';
import { motion } from 'framer-motion';
import Modal from './Modal';

interface SidebarProps {
    userId: string;
    onSelectSession: (sessionId: string) => void;
    onNewChat: () => void;
    currentSessionId: string | null;
    activeRepoId: string | null;
    activeFiles?: string[];
}

const Sidebar: React.FC<SidebarProps> = ({
    userId,
    onSelectSession,
    onNewChat,
    currentSessionId,
    activeRepoId,
}) => {
    const [sessions, setSessions] = useState<any[]>([]);
    const [collapsed, setCollapsed] = useState(false);
    const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    useEffect(() => {
        if (userId) fetchSessions();
    }, [userId]);

    const fetchSessions = async () => {
        try {
            const res = await fetch(`/api/chat/history?userId=${userId}`);
            const data = await res.json();
            setSessions(data);
        } catch (error) {
            console.error('Error fetching sessions:', error);
        }
    };

    const confirmDelete = async () => {
        if (!sessionToDelete) return;
        setIsDeleting(true);
        try {
            const res = await fetch(`/api/chat/${sessionToDelete}`, { method: 'DELETE' });
            if (res.ok) {
                setSessions(sessions.filter((s) => s.id !== sessionToDelete));
                if (currentSessionId === sessionToDelete) onNewChat();
            } else {
                const errorData = await res.json().catch(() => ({ detail: 'Unknown error' }));
                console.error('Failed to delete session:', errorData.detail || 'Unknown error');
            }
        } catch (err) {
            console.error(err);
        } finally {
            setIsDeleting(false);
            setSessionToDelete(null);
        }
    };

    const handleDeleteClick = (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setSessionToDelete(id);
    };

    const groupedSessions = {
        today: sessions.filter(s => {
            const d = new Date(s.created_at);
            const today = new Date();
            return d.toDateString() === today.toDateString();
        }),
        previous: sessions.filter(s => {
            const d = new Date(s.created_at);
            const today = new Date();
            return d.toDateString() !== today.toDateString();
        })
    };

    return (
        <motion.div
            initial={false}
            animate={{ width: collapsed ? 64 : 260 }}
            className="h-full border-r border-gray-800 bg-black/50 backdrop-blur-md flex flex-col relative transition-all duration-300"
        >
            <div className="p-4 flex flex-col h-full overflow-hidden">
                {/* New Chat Button */}
                <button
                    onClick={onNewChat}
                    className={`group flex items-center gap-3 w-full bg-white text-black p-3 rounded-lg font-bold text-xs transition-all hover:shadow-[0_0_20px_rgba(255,255,255,0.3)] mb-8 ${collapsed ? 'justify-center' : ''}`}
                >
                    <Plus className="w-5 h-5" />
                    {!collapsed && <span>NEW CHAT</span>}
                </button>

                {/* Sessions List */}
                <div className="flex-1 overflow-y-auto space-y-6 scrollbar-hide">
                    {!collapsed && (
                        <>
                            {groupedSessions.today.length > 0 && (
                                <div>
                                    <h3 className="text-[10px] font-bold text-gray-500 mb-3 ml-2 flex items-center gap-2">
                                        <Clock className="w-3 h-3" />
                                        TODAY
                                    </h3>
                                    <div className="space-y-1">
                                        {groupedSessions.today.map((s) => (
                                            <SessionItem
                                                key={s.id}
                                                s={s}
                                                active={currentSessionId === s.id}
                                                onClick={() => onSelectSession(s.id)}
                                                onDelete={(e: React.MouseEvent) => handleDeleteClick(s.id, e)}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {groupedSessions.previous.length > 0 && (
                                <div>
                                    <h3 className="text-[10px] font-bold text-gray-500 mb-3 ml-2 flex items-center gap-2">
                                        <Bookmark className="w-3 h-3" />
                                        PREVIOUS
                                    </h3>
                                    <div className="space-y-1">
                                        {groupedSessions.previous.map((s) => (
                                            <SessionItem
                                                key={s.id}
                                                s={s}
                                                active={currentSessionId === s.id}
                                                onClick={() => onSelectSession(s.id)}
                                                onDelete={(e: React.MouseEvent) => handleDeleteClick(s.id, e)}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}
                        </>
                    )}

                    {collapsed && (
                        <div className="flex flex-col items-center gap-4">
                            {sessions.slice(0, 10).map(s => (
                                <button
                                    key={s.id}
                                    onClick={() => onSelectSession(s.id)}
                                    className={`p-2 rounded-lg transition-colors ${currentSessionId === s.id ? 'bg-gray-800' : 'hover:bg-gray-900 text-gray-400'}`}
                                >
                                    <MessageSquare className="w-4 h-4" />
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* Delete Confirmation Modal */}
                <Modal
                    isOpen={!!sessionToDelete}
                    onClose={() => setSessionToDelete(null)}
                    title="Delete Chat"
                    confirmLabel="Delete"
                    confirmVariant="danger"
                    onConfirm={confirmDelete}
                    isLoading={isDeleting}
                >
                    <div className="flex flex-col items-center text-center gap-4">
                        <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
                            <Trash2 className="w-6 h-6 text-red-500" />
                        </div>
                        <div className="space-y-2">
                            <p className="text-sm font-bold">Are you sure you want to delete this chat?</p>
                            <p className="text-xs text-gray-500">This action cannot be undone and all messages will be lost.</p>
                        </div>
                    </div>
                </Modal>

                {/* Footer */}
                <div className="pt-4 border-t border-gray-800 flex flex-col gap-2">
                    {!collapsed ? (
                        <>
                            <button className="flex items-center gap-3 p-2 text-xs font-bold text-gray-400 hover:text-white transition-colors">
                                <Settings className="w-4 h-4" />
                                SETTINGS
                            </button>
                            <div className="flex items-center gap-3 p-2 bg-gray-900/50 rounded-lg border border-gray-800">
                                <div className="w-8 h-8 rounded-full bg-purple-500 flex items-center justify-center text-[10px] text-white font-black">
                                    DEV
                                </div>
                                <div className="flex flex-col">
                                    <span className="text-xs font-bold truncate">Developer User</span>
                                    <span className="text-[10px] text-gray-500">Free Tier</span>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="flex flex-col items-center gap-4">
                            <Settings className="w-4 h-4 text-gray-400 hover:text-white cursor-pointer" />
                            <div className="w-8 h-8 rounded-full bg-purple-500 flex items-center justify-center text-[10px] text-white font-black ring-2 ring-white/10">
                                DEV
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Collapse Toggle */}
            <button
                onClick={() => setCollapsed(!collapsed)}
                className="absolute -right-3 top-20 w-6 h-6 bg-gray-800 border border-gray-700 rounded-full flex items-center justify-center hover:bg-gray-700 text-gray-400 z-50 transition-colors"
            >
                {collapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
            </button>
        </motion.div>
    );
};

const SessionItem = ({ s, active, onClick, onDelete }: any) => (
    <button
        onClick={onClick}
        className={`group flex items-center justify-between w-full p-2.5 rounded-lg text-xs font-bold transition-all ${active
            ? 'bg-gray-800 text-white border border-gray-700'
            : 'text-gray-400 hover:bg-gray-900/50 hover:text-gray-200'
            }`}
    >
        <div className="flex items-center gap-3 truncate">
            <MessageSquare className={`w-4 h-4 shrink-0 transition-colors ${active ? 'text-purple-400' : 'text-gray-600'}`} />
            <span className="truncate">{s.title || 'Untitled Session'}</span>
        </div>
        <div className="opacity-0 group-hover:opacity-100 transition-opacity">
            <Trash2
                className="w-3.5 h-3.5 text-gray-600 hover:text-red-400"
                onClick={onDelete}
            />
        </div>
    </button>
);

export default Sidebar;
