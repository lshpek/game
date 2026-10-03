/** Typed endpoint wrappers - one function per backend operation. */

import { apiRequest, makeIdempotencyKey } from '@/lib/api';
import type {
  AchievementItem,
  AuthResponse,
  ChallengeItem,
  CollectionPage,
  ContainerCard,
  ContainerOpenResult,
  DailyClaimResult,
  DailyStatus,
  DuplicateConversion,
  InvoiceResult,
  LeaderboardBoard,
  ProductItem,
  ReferralSummary,
  RollResult,
  SeasonItem,
  ShareResult,
  UserProfile,
} from '@/types';

export const auth = {
  loginWithTelegram: (initData: string) =>
    apiRequest<AuthResponse>('/api/auth/telegram', { method: 'POST', body: { init_data: initData } }),

  loginWithDev: (telegramId: number, startParam?: string) =>
    apiRequest<AuthResponse>('/api/auth/dev', {
      method: 'POST',
      authenticated: false,
      body: { telegram_id: telegramId, first_name: 'Local Dev', start_param: startParam ?? undefined },
    }),

  refresh: () => apiRequest<AuthResponse>('/api/auth/me'),
};

export const user = {
  profile: () => apiRequest<UserProfile>('/api/user'),
  top: () => apiRequest<{ rarest: unknown[]; highest_value: unknown[] }>('/api/user/top'),
};

export const game = {
  /** The server decides the result; the client only animates it. */
  roll: (key?: string) =>
    apiRequest<RollResult>('/api/roll', {
      method: 'POST',
      idempotencyKey: key ?? makeIdempotencyKey('roll'),
    }),

  history: (limit = 20) =>
    apiRequest<Array<{ roll_id: number; number: string; rarity: string; value: number; is_duplicate: boolean }>>(
      '/api/roll/history',
      { query: { limit } },
    ),

  daily: () => apiRequest<DailyStatus>('/api/daily'),

  claimDaily: () => apiRequest<DailyClaimResult>('/api/daily/claim', { method: 'POST' }),

  collection: (params: {
    page?: number;
    pageSize?: number;
    rarity?: string;
    search?: string;
    sort?: string;
    duplicatesOnly?: boolean;
  }) =>
    apiRequest<CollectionPage>('/api/collection', {
      query: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 30,
        rarity: params.rarity,
        search: params.search,
        sort: params.sort,
        duplicates_only: params.duplicatesOnly ?? false,
      },
    }),

  numberDetail: (value: string) => apiRequest<CollectionPage['items'][number]>(`/api/numbers/${value}`),

  convertDuplicate: (value: string) =>
    apiRequest<DuplicateConversion>(`/api/numbers/${value}/convert`, { method: 'POST' }),

  convertAllDuplicates: () =>
    apiRequest<{ coins_gained: number; converted: number; balance: number }>('/api/collection/convert-all', {
      method: 'POST',
    }),

  share: (value: string) =>
    apiRequest<ShareResult>(`/api/numbers/${value}/share`, { method: 'POST' }),

  achievements: () => apiRequest<AchievementItem[]>('/api/achievements'),

  seasons: () => apiRequest<SeasonItem[]>('/api/seasons'),
  activeSeason: () => apiRequest<SeasonItem | null>('/api/seasons/active'),
};

export const containers = {
  list: () => apiRequest<ContainerCard[]>('/api/containers'),

  open: (code: string, key?: string) =>
    apiRequest<ContainerOpenResult>('/api/containers/open', {
      method: 'POST',
      body: { code },
      idempotencyKey: key ?? makeIdempotencyKey('container'),
    }),

  history: () => apiRequest<Array<{ opening_id: number; container: string; number: string; value: number }>>(
    '/api/containers/history',
  ),
};

export const social = {
  referrals: () => apiRequest<ReferralSummary>('/api/referrals'),

  challenges: () => apiRequest<ChallengeItem[]>('/api/challenges'),

  createChallenge: (number?: string) =>
    apiRequest<ChallengeItem>('/api/challenges', { method: 'POST', body: { number } }),

  challenge: (code: string) => apiRequest<ChallengeItem>(`/api/challenges/${code}`),

  acceptChallenge: (code: string) =>
    apiRequest<ChallengeItem>(`/api/challenges/${code}/accept`, { method: 'POST' }),
};

export const leaderboard = {
  board: (category: string, period: string, limit = 20) =>
    apiRequest<LeaderboardBoard>('/api/leaderboard', { query: { category, period, limit } }),
};

export const shop = {
  products: () => apiRequest<ProductItem[]>('/api/payments/products'),

  createInvoice: (productCode: string, key?: string) =>
    apiRequest<InvoiceResult>('/api/payments/invoice', {
      method: 'POST',
      body: { product_code: productCode },
      idempotencyKey: key ?? makeIdempotencyKey('invoice'),
    }),

  /** Only available when PAYMENT_PROVIDER=mock (never in production). */
  confirmMock: (paymentId: number) =>
    apiRequest<{ id: number; status: string; granted: boolean }>('/api/payments/mock/confirm', {
      method: 'POST',
      body: { payment_id: paymentId },
    }),

  premium: () => apiRequest<{ active: boolean; tier: string | null; expires_at: string | null; perks: string[] }>('/api/premium'),
};

export const analytics = {
  track: (name: string, props: Record<string, unknown> = {}) =>
    apiRequest<{ success: boolean }>('/api/analytics/event', { method: 'POST', body: { name, props } }),
};
