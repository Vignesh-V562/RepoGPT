'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, AlertCircle } from 'lucide-react';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: React.ReactNode;
    confirmLabel?: string;
    onConfirm?: () => void;
    confirmVariant?: 'danger' | 'primary' | 'success';
    isLoading?: boolean;
    showClose?: boolean;
}

const Modal: React.FC<ModalProps> = ({
    isOpen,
    onClose,
    title,
    children,
    confirmLabel,
    onConfirm,
    confirmVariant = 'primary',
    isLoading = false,
    showClose = true
}) => {
    const variantClasses = {
        primary: 'bg-white text-black hover:bg-gray-200',
        danger: 'bg-red-500 text-white hover:bg-red-600 shadow-[0_0_20px_rgba(239,68,68,0.3)]',
        success: 'bg-emerald-500 text-white hover:bg-emerald-600 shadow-[0_0_20px_rgba(16,185,129,0.3)]',
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
                    />

                    {/* Modal Content */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        className="relative w-full max-w-md glass border border-white/10 rounded-2xl overflow-hidden shadow-2xl"
                    >
                        {/* Header */}
                        <div className="p-4 border-b border-white/5 flex items-center justify-between">
                            <h3 className="text-xs font-black uppercase tracking-widest text-gray-400">
                                {title}
                            </h3>
                            {showClose && (
                                <button
                                    onClick={onClose}
                                    className="p-1 rounded-lg hover:bg-white/5 text-gray-500 hover:text-white transition-colors"
                                >
                                    <X className="w-4 h-4" />
                                </button>
                            )}
                        </div>

                        {/* Body */}
                        <div className="p-6">
                            {children}
                        </div>

                        {/* Footer */}
                        {confirmLabel && (
                            <div className="p-4 border-t border-white/5 bg-black/20 flex justify-end gap-3">
                                <button
                                    onClick={onClose}
                                    className="px-4 py-2 rounded-lg text-[10px] font-black uppercase tracking-tighter text-gray-400 hover:text-white transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={onConfirm}
                                    disabled={isLoading}
                                    className={`px-6 py-2 rounded-lg text-[10px] font-black uppercase tracking-tighter transition-all flex items-center gap-2 ${variantClasses[confirmVariant]} ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                                >
                                    {isLoading ? 'Processing...' : confirmLabel}
                                </button>
                            </div>
                        )}
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    );
};

export default Modal;
