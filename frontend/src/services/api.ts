/** Typed endpoint wrappers - one function per backend operation. */

import { apiRequest, makeIdempotencyKey } from '@/lib/api';
import type {
  ActiveCountryResponse,
  CountryCard,
  CountryListResponse,
  HuntFilter,
  AchievementItem,
  AuthResponse,
  ChallengeItem,
  CollectionResponse,
  ContainerCard,
  ContainerOpenResult,
  DailyClaimResult,
  DailyStatus,
  GarageData,
  InvoiceResult,
  LeaderboardBoard,
  PlateCard,
  PlateRollResult,
  PlateShareResult,
  ProductItem,
  ReferralSummary,
  SaleResult,
  SeasonItem,
  SellAllResult,
  UserProfile,
  WorldResponse,
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
};

export const game = {
  /** The server decides the result; the client only animates it. */
  /**
   * Draw one collectible.
   *
   * `hunt` is a *pool filter* only - which kind and which country may be eligible.
   * Everything about the outcome is decided by the server, so this can never be used
   * to forge a result. With no country given, the player's active country decides.
   */
  roll: (key?: string, hunt?: HuntFilter) =>
    apiRequest<PlateRollResult>('/api/roll', {
      method: 'POST',
      idempotencyKey: key ?? makeIdempotencyKey('roll'),
      query: {
        ...(hunt?.kind ? { category: hunt.kind } : {}),
        ...(hunt?.country_code ? { country_code: hunt.country_code } : {}),
      },
    }),

  rollHistory: (limit = 20) =>
    apiRequest<
      Array<{
        roll_id: number;
        plate_text: string;
        rarity: string;
        value: number;
        is_duplicate: boolean;
        country_code?: string;
        kind?: string;
      }>
    >('/api/roll/history', { query: { limit } }),

  garage: () => apiRequest<GarageData>('/api/garage'),

  daily: () => apiRequest<DailyStatus>('/api/daily'),

  claimDaily: () => apiRequest<DailyClaimResult>('/api/daily/claim', { method: 'POST' }),

  collection: (params: {
    page?: number;
    pageSize?: number;
    rarity?: string;
    country?: string;
    kind?: string;
    search?: string;
    sort?: string;
    favoritesOnly?: boolean;
    duplicatesOnly?: boolean;
  }) =>
    apiRequest<CollectionResponse>('/api/collection', {
      query: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 30,
        rarity: params.rarity,
        country: params.country,
        kind: params.kind,
        sort: params.sort,
        search: params.search,
        favorites_only: params.favoritesOnly ?? false,
        duplicates_only: params.duplicatesOnly ?? false,
      },
    }),

  /** Sell copies to the DEALER for NUMORA. */
  sell: (plateId: number, copies = 1) =>
    apiRequest<SaleResult>(`/api/plates/${plateId}/sell`, {
      method: 'POST',
      body: { copies },
    }),

  sellDuplicates: () =>
    apiRequest<SellAllResult>('/api/collection/sell-duplicates', { method: 'POST' }),

  favorite: (plateId: number) =>
    apiRequest<{ plate_id: number; is_favorite: boolean }>(`/api/plates/${plateId}/favorite`, {
      method: 'POST',
    }),

  share: (plateId: number) =>
    apiRequest<PlateShareResult>(`/api/plates/${plateId}/share`, { method: 'POST' }),

  plateDetail: (plateId: number) =>
    apiRequest<{ plate: PlateCard; discoverer: unknown; is_owned: boolean; start_param: string }>(
      `/api/plates/${plateId}`,
    ),

  /** The atlas, one page at a time. */
  world: (params: { limit?: number; offset?: number } = {}) =>
    apiRequest<WorldResponse>('/api/world', {
      query: { limit: params.limit ?? 60, offset: params.offset ?? 0 },
    }),

  achievements: () => apiRequest<AchievementItem[]>('/api/achievements'),

  seasons: () => apiRequest<SeasonItem[]>('/api/seasons'),
  activeSeason: () => apiRequest<SeasonItem | null>('/api/seasons/active'),
};

/**
 * The country system.
 *
 * The active country is authoritative on the server; the client keeps only a mirror
 * for instant rendering. `setActive` is the single write path, so a country can never
 * look selected without the backend having validated it.
 */
export const countries = {
  list: (params: { search?: string; region?: string; playableOnly?: boolean; limit?: number; offset?: number } = {}) =>
    apiRequest<CountryListResponse>('/api/countries', {
      query: {
        search: params.search,
        region: params.region,
        playable_only: params.playableOnly ?? false,
        limit: params.limit ?? 60,
        offset: params.offset ?? 0,
      },
    }),

  active: () => apiRequest<ActiveCountryResponse>('/api/countries/active'),

  /** `null` clears the selection and returns the player to the world-wide hunt. */
  setActive: (code: string | null) =>
    apiRequest<ActiveCountryResponse>('/api/countries/active', {
      method: 'POST',
      body: { code },
    }),

  detail: (code: string) => apiRequest<CountryCard>(`/api/countries/${code}`),
};
export const containers = {
  list: () => apiRequest<ContainerCard[]>('/api/containers'),

  open: (code: string, key?: string) =>
    apiRequest<ContainerOpenResult>('/api/containers/open', {
      method: 'POST',
      body: { code },
      idempotencyKey: key ?? makeIdempotencyKey('container'),
    }),

  history: () =>
    apiRequest<Array<{ opening_id: number; container: string; number: string; value: number }>>(
      '/api/containers/history',
    ),
};

export const social = {
  referrals: () => apiRequest<ReferralSummary>('/api/referrals'),

  challenges: () => apiRequest<ChallengeItem[]>('/api/challenges'),

  createChallenge: (plateId?: number) =>
    apiRequest<ChallengeItem>('/api/challenges', {
      method: 'POST',
      body: plateId === undefined ? {} : { plate_id: plateId },
    }),

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

export interface DuplicateConversion {
  number: string;
  coins_gained: number;
  duplicates_left: number;
  balance: number;
}

export const legacy = {
  /** Boxes still grant legacy 4-digit numbers; duplicates convert to NUMORA. */
  convertDuplicate: (value: string) =>
    apiRequest<DuplicateConversion>(`/api/legacy/numbers/${value}/convert`, { method: 'POST' }),
};

export const analytics = {
  track: (name: string, props: Record<string, unknown> = {}) =>
    apiRequest<{ success: boolean }>('/api/analytics/event', { method: 'POST', body: { name, props } }),
};
