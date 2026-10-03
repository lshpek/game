import { useEffect } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { BottomNav } from '@/components/BottomNav';
import { LoadingSpinner } from '@/components/States';
import { BoxesPage } from '@/pages/BoxesPage';
import { CollectionPage } from '@/pages/CollectionPage';
import { HomePage } from '@/pages/HomePage';
import { ProfilePage } from '@/pages/ProfilePage';
import { RankingPage } from '@/pages/RankingPage';
import { useAuthStore } from '@/store/auth';

function AppShell() {
  const status = useAuthStore((state) => state.status);
  const error = useAuthStore((state) => state.error);
  const login = useAuthStore((state) => state.login);

  useEffect(() => {
    if (status === 'idle') void login();
  }, [login, status]);

  if (status === 'loading' || status === 'idle') {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <LoadingSpinner label="Opening the game…" />
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 p-6 text-center">
        <p className="text-lg font-semibold">Could not sign in</p>
        <p className="max-w-xs text-sm text-white/55">{error}</p>
        <button type="button" className="btn-primary" onClick={() => void login()}>
          RETRY
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto min-h-dvh w-full max-w-lg px-4 safe-top pb-safe-nav">
      <main className="pt-4">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/containers" element={<BoxesPage />} />
          <Route path="/collection" element={<CollectionPage />} />
          <Route path="/ranking" element={<RankingPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <BottomNav />
    </div>
  );
}

/** Keeps the profile fresh when the tab regains focus inside Telegram. */
function ProfileSync() {
  const status = useAuthStore((state) => state.status);
  const refreshProfile = useAuthStore((state) => state.refreshProfile);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (status !== 'authenticated') return;
    void refreshProfile();
    const onFocus = () => {
      void refreshProfile();
      void queryClient.invalidateQueries();
    };
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [queryClient, refreshProfile, status]);

  return null;
}

export default function App() {
  return (
    // Opt in to the React Router v7 behaviours to silence upgrade warnings.
    <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ProfileSync />
      <AppShell />
    </HashRouter>
  );
}
