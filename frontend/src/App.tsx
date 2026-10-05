import { useEffect } from 'react';
import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';

import { BottomNav } from '@/components/BottomNav';
import { LoadingSpinner } from '@/components/States';
import { MobileHeader } from '@/components/MobileHeader';
import { TelegramViewport } from '@/components/TelegramViewport';
import { BoxesPage } from '@/pages/BoxesPage';
import { CollectionPage } from '@/pages/CollectionPage';
import { HuntPage } from '@/pages/HuntPage';
import { WorldPage } from '@/pages/WorldPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { RankingPage } from '@/pages/RankingPage';
import { useAuthStore } from '@/store/auth';
import { I18nProvider, useI18n } from '@/i18n';

/**
 * The app shell: the one place that owns vertical space.
 *
 * Mobile is the primary design and desktop is this scaled up, not the other way round.
 * That means a single column of content at a comfortable reading width, centred in the
 * viewport, with the header and the bottom navigation as fixed furniture either side of
 * it. There is no separate desktop layout to drift out of sync, and no screen can
 * overflow horizontally because no screen is ever wider than `--app-width`.
 *
 * The scroll container is `#root`, sized from `--app-height` (the measured Telegram
 * viewport). Screens never set their own bottom padding for the navigation: the shell
 * reserves it once, from the same variable the navigation is built from, so the two
 * cannot disagree.
 */
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
        // Announced, not just shown: a session failure is the one error the player must
        // not have to notice for themselves.
        role="alert"
        className="flex flex-col items-center justify-center gap-4 px-[var(--gutter)] text-center"
        style={{ minHeight: 'var(--app-height)', paddingTop: 'var(--tg-safe-top)' }}
      >
        <p className="t-h2 text-white">{t('app.signInFailed')}</p>
        <p className="max-w-xs t-caption text-white/50">{error}</p>
        <button type="button" className="btn-primary" onClick={() => void login()}>
          {t('app.retry')}
        </button>
      </div>
    );
  }

  return (
    <div
      className="mx-auto flex w-full max-w-[560px] flex-col"
      style={{ minHeight: 'var(--app-height)' }}
    >
      <MobileHeader />

      {/*
        The single scroll container. The padding below is the navigation height plus the
        system gesture inset plus one comfortable gap - all measured, none of it a magic
        number, so the last card can never end up behind the navigation.
      */}
      <main
        className="flex-1 overflow-y-auto overflow-x-clip overscroll-y-contain px-[var(--gutter)]"
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
          {/* ROLL is the product now. Boxes is the legacy four-digit line and is
              reachable from the profile, not from the primary navigation. */}
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

/**
 * Returning to the top on navigation.
 *
 * A route change must not leave the player halfway down a previous screen's list, which
 * is the "sudden position reset" artefact the old layout produced: the new screen
 * inherited the old scroll offset and then jumped. Resetting to the top explicitly, at
 * the container rather than the window, is deterministic on every platform.
 */
function ScrollReset() {
  const location = useLocation();
  useEffect(() => {
    const container = document.querySelector<HTMLElement>('main');
    if (container) container.scrollTop = 0;
  }, [location.pathname]);
  return null;
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

/**
 * The query cache.
 *
 * A module-level singleton rather than a component-local instance: it has to outlive
 * re-renders and remounts, or every route change would throw away the cache and the player
 * would see a spinner for data they already had.
 *
 * `refetchOnWindowFocus: false` matters inside a Mini App specifically - Telegram fires
 * focus/blur on every chat switch, and a default that refetches on focus turns opening a
 * message into a burst of requests against the roll and collection endpoints.
 */
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
