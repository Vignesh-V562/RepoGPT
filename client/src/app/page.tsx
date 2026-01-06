'use client';

import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import Login from '@/components/Login';
import Header from '@/components/Header';
import Sidebar from '@/components/Sidebar';
import ChatInterface from '@/components/ChatInterface';

export default function Home() {
  const [session, setSession] = useState<any>(null);
  const [mode, setMode] = useState<'architect' | 'repo'>('repo');
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [activeRepoId, setActiveRepoId] = useState<string | null>(null);
  const [activeFiles, setActiveFiles] = useState<string[]>([]);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      console.log('Auth event:', _event, session);
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  if (!session) {
    return <Login />;
  }

  return (
    <div className="flex flex-col h-screen bg-black text-white selection:bg-purple-500/30">
      <Header mode={mode} setMode={setMode} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          userId={session.user.id}
          onSelectSession={setCurrentSessionId}
          onNewChat={() => setCurrentSessionId(null)}
          currentSessionId={currentSessionId}
          activeRepoId={activeRepoId}
        />
        <ChatInterface
          mode={mode}
          sessionId={currentSessionId}
          setSessionId={setCurrentSessionId}
          userId={session.user.id}
          activeRepoId={activeRepoId}
          setActiveRepoId={setActiveRepoId}
          activeFiles={activeFiles}
          setActiveFiles={setActiveFiles}
        />
      </div>
    </div>
  );
}
