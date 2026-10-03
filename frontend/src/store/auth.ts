/** Session store: owns the access token and the authenticated profile. */

import { create } from 'zustand';
import { ApiError, getToken, setToken } from '@/lib/api';
import { getInitData, getStartParam, isTelegram } from '@/lib/telegram';
import { auth, user } from '@/services/api';
import type { StartContext, UserProfile } from '@/types';

interface AuthState {
  token: string | null;
  profile: UserProfile | null;
  status: 'idle' | 'loading' | 'authenticated' | 'error';
  error: string | null;
  startContext: StartContext | null;
  bootstrap: () => Promise<void>;
  login: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  logout: () => void;
  applyProfile: (profile: UserProfile) => void;
}

const emptyContext: StartContext = {
  raw: null,
  referral_telegram_id: null,
  shared_number: null,
  challenge_code: null,
};

/** Deterministic local id so browser-only development is stable per device. */
function devTelegramId(): number {
  const key = 'number-collector.dev-id';
  try {
    const existing = window.localStorage.getItem(key);
    if (existing) return Number(existing);
    const created = 900_000_000 + Math.floor(Math.random() * 99_999_999);
    window.localStorage.setItem(key, String(created));
    return created;
  } catch {
    return 900_000_001;
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: getToken(),
  profile: null,
  status: 'idle',
  error: null,
  startContext: null,

  bootstrap: async () => {
    const { token } = get();
    if (!token) {
      set({ status: 'idle' });
      return;
    }
    set({ status: 'loading', error: null });
    try {
      const response = await auth.refresh();
      setToken(response.access_token);
      set({ token: response.access_token, profile: response.user, status: 'authenticated' });
    } catch (error) {
      const code = error instanceof ApiError ? error.code : 'UNKNOWN';
      if (code === 'UNAUTHORIZED' || code === 'USER_NOT_FOUND') {
        setToken(null);
        set({ token: null, profile: null, status: 'idle' });
      } else {
        set({ status: 'error', error: 'Could not load your profile.' });
      }
    }
  },

  login: async () => {
    set({ status: 'loading', error: null });
    try {
      const initData = getInitData();
      const response = isTelegram()
        ? await auth.loginWithTelegram(initData)
        : await auth.loginWithDev(devTelegramId(), getStartParam() ?? undefined);

      setToken(response.access_token);
      set({
        token: response.access_token,
        profile: response.user,
        startContext: { ...emptyContext, ...response.start_context },
        status: 'authenticated',
      });
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : 'Could not sign in. Please try again.';
      set({ status: 'error', error: message });
    }
  },

  refreshProfile: async () => {
    try {
      const profile = await user.profile();
      set({ profile });
    } catch {
      // A failed refresh must not break the screen; the next action retries.
    }
  },

  applyProfile: (profile) => set({ profile }),

  logout: () => {
    setToken(null);
    set({ token: null, profile: null, status: 'idle', startContext: null });
  },
}));
