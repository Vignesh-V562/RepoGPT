'use client';

import { useState } from 'react';
import { supabase } from '@/lib/supabase';
import { Github, Loader2 } from 'lucide-react';

export default function Login() {
    const [loading, setLoading] = useState(false);
    const [email, setEmail] = useState('');
    const [message, setMessage] = useState('');

    const handleGithubLogin = async () => {
        try {
            setLoading(true);
            const { error } = await supabase.auth.signInWithOAuth({
                provider: 'github',
            });
            if (error) throw error;
        } catch (error: any) {
            alert(error.message);
        } finally {
            setLoading(false);
        }
    };

    const handleMagicLink = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            setLoading(true);
            const { error } = await supabase.auth.signInWithOtp({
                email,
            });
            if (error) throw error;
            setMessage('Check your email for the magic link!');
        } catch (error: any) {
            alert(error.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex min-h-screen items-center justify-center bg-zinc-900 text-zinc-100">
            <div className="w-full max-w-md space-y-8 rounded-xl bg-zinc-800 p-8 shadow-2xl border border-zinc-700">
                <div className="text-center">
                    <h2 className="text-3xl font-bold tracking-tight">Welcome to RepoGPT</h2>
                    <p className="mt-2 text-sm text-zinc-400">Sign in to start chatting with your code</p>
                </div>

                <div className="space-y-4">
                    <button
                        onClick={handleGithubLogin}
                        disabled={loading}
                        suppressHydrationWarning
                        className="flex w-full items-center justify-center rounded-lg bg-zinc-100 px-4 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-200 transition disabled:opacity-50"
                    >
                        {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Github className="mr-2 h-4 w-4" />}
                        Continue with GitHub
                    </button>

                    <button
                        onClick={() => {
                            setLoading(true);
                            supabase.auth.signInWithOAuth({
                                provider: 'google',
                            }).catch((err) => {
                                alert(err.message);
                                setLoading(false);
                            });
                        }}
                        disabled={loading}
                        suppressHydrationWarning
                        className="flex w-full items-center justify-center rounded-lg bg-zinc-100 px-4 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-200 transition disabled:opacity-50"
                    >
                        {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : (
                            <svg className="mr-2 h-4 w-4" aria-hidden="true" focusable="false" data-prefix="fab" data-icon="google" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 488 512">
                                <path fill="currentColor" d="M488 261.8C488 403.3 391.1 504 248 504 110.8 504 0 393.2 0 256S110.8 8 248 8c66.8 0 123 24.5 166.3 64.9l-67.5 64.9C258.5 52.6 94.3 116.6 94.3 256c0 86.5 69.1 156.6 153.7 156.6 98.2 0 135-70.4 140.8-106.9H248v-85.3h236.1c2.3 12.7 3.9 24.9 3.9 41.4z"></path>
                            </svg>
                        )}
                        Continue with Google
                    </button>

                    <div className="relative">
                        <div className="absolute inset-0 flex items-center">
                            <span className="w-full border-t border-zinc-700" />
                        </div>
                        <div className="relative flex justify-center text-xs uppercase">
                            <span className="bg-zinc-800 px-2 text-zinc-500">Or continue with email</span>
                        </div>
                    </div>

                    <form onSubmit={handleMagicLink} className="space-y-4">
                        <input
                            type="email"
                            placeholder="name@example.com"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            suppressHydrationWarning
                            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            required
                        />
                        <button
                            type="submit"
                            disabled={loading}
                            suppressHydrationWarning
                            className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-500 transition disabled:opacity-50"
                        >
                            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin inline" /> : null}
                            Send Magic Link
                        </button>
                    </form>
                    {message && <p className="text-center text-sm text-green-400">{message}</p>}
                </div>
            </div>
        </div>
    );
}
