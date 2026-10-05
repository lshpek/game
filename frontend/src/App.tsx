import { useEffect } from 'react';
import { HashRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { BottomNav } from '@/components/BottomNav';
import { LoadingSpinner } from '@/components/States';
import { BoxesPage } from '@/pages/BoxesPage';
import { CollectionPage } from '@/pages/CollectionPage';
import { HuntPage } from '@/pages/HuntPage';
import { WorldPage } from '@/pages/WorldPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { RankingPage } from '@/pages/RankingPage';
import { useAuthStore } from '@/store/auth';
import { I18nProvider, useI18n } from '@/i18n';

function AppShell() {
  const status = useAuthStore((state) => state.status);
  const error = useAuthStore((state) => state.error);
  const login = useAuthStore((state) => state.login);
  const { t } = useI18n();
  const navigate = useNavigate();

  useEffect(() => {
    if (status === 'idle') void login();
  }, [login, status]);

  if (status === 'loading' || status === 'idle') {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <LoadingSpinner label={t('common.loadingGame')} />
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 p-6 text-center">
        <p className="text-lg font-semibold">{t('app.signInFailed')}</p>
        <p className="max-w-xs text-sm text-white/55">{error}</p>
        <button type="button" className="btn-primary" onClick={() => void login()}>
          {t('app.retry')}
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto min-h-dvh w-full max-w-lg px-4 safe-top pb-safe-nav">
      <main className="pt-4">
        <Routes>
          {/* ROLL is the product now. Boxes is the legacy four-digit line and is
              reachable from the profile, not from the primary navigation. */}
          <Route path="/" element={<HuntPage onOpenCollection={() => navigate('/collection')} />} />
          <Route path="/world" element={<WorldPage />} />
          <Route path="/legacy" element={<BoxesPage />} />
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
    <I18nProvider>
      {/*
        Opt in to the React Router v7 behaviours to silence upgrade warnings.
      */}
      <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ProfileSync />
        <AppShell />
      </HashRouter>
    </I18nProvider>
  );
}
