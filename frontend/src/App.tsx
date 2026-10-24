import { useEffect } from 'react';
import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import clsx from 'clsx';

import { BottomNav } from '@/components/BottomNav';
import { LoadingSpinner } from '@/components/States';
import { MobileHeader } from '@/components/MobileHeader';
import { TelegramViewport } from '@/components/TelegramViewport';
import { ToastHost } from '@/components/Toast';
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

  useEffect(() => {
    if (status === 'idle') void login();
  }, [login, status]);

  if (status === 'loading' || status === 'idle') {
    return (
      <div
        className="flex items-center justify-center"
        style={{ minHeight: 'var(--app-height)', paddingTop: 'var(--tg-safe-top)' }}
      >
        <LoadingSpinner label={t('common.loadingGame')} />
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div
        role="alert"
        className="flex flex-col items-center justify-center gap-4 px-[var(--gutter)] text-center"
        style={{ minHeight: 'var(--app-height)', paddingTop: 'var(--tg-safe-top)' }}
      >
        <p className="t-h2 text-white">{t('app.signInFailed')}</p>
        <p className="max-w-xs t-caption text-white/55">{error}</p>
        <button type="button" className="btn-primary" onClick={() => void login()}>
          {t('app.retry')}
        </button>
      </div>
    );
  }

  return (
    <div
      className={clsx(
        'app-shell relative mx-auto flex w-full flex-col overflow-hidden',
        'max-w-[var(--content-max)]',
      )}
      style={{ minHeight: 'var(--app-height)', maxHeight: 'var(--app-height)' }}
      data-testid="app-shell"
    >
      <MobileHeader />
      <ToastHost />

      <main
        className="min-h-0 flex-1 overflow-y-auto overflow-x-clip overscroll-y-contain px-[var(--gutter)]"
        style={{
          paddingTop: 'var(--section-gap)',
          paddingBottom:
            'calc(var(--bottom-nav-height) + var(--tg-safe-bottom) + var(--section-gap))',
          scrollPaddingTop: 'calc(var(--tg-safe-top) + var(--header-height))',
          WebkitOverflowScrolling: 'touch',
        }}
      >
        <ScrollReset />
        <Routes>
          <Route path="/" element={<HuntPage />} />
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

function ScrollReset() {
  const location = useLocation();
  useEffect(() => {
    const container = document.querySelector<HTMLElement>('main');
    if (container) container.scrollTop = 0;
  }, [location.pathname]);
  return null;
}

/** Keeps the profile and roll bank fresh when the tab regains focus without triggering a full-app refetch storm. */
function ProfileSync() {
  const status = useAuthStore((state) => state.status);
  const refreshProfile = useAuthStore((state) => state.refreshProfile);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (status !== 'authenticated') return;
    void refreshProfile();
    const onFocus = () => {
      void refreshProfile();
      void queryClient.invalidateQueries({ queryKey: ['garage'] });
      void queryClient.invalidateQueries({ queryKey: ['daily'] });
    };
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [queryClient, refreshProfile, status]);

  return null;
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 15_000,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <TelegramViewport>
          <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <ProfileSync />
            <AppShell />
          </HashRouter>
        </TelegramViewport>
      </I18nProvider>
    </QueryClientProvider>
  );
}
