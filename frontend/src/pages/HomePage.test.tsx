import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactElement } from 'react';
import { HomePage } from '@/pages/HomePage';
import { ApiError } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import type { Rarity, UserProfile } from '@/types';
import { I18nProvider } from '@/i18n';

const profile: UserProfile = {
  id: 1, telegram_id: 42, username: 'tester', first_name: 'Test', last_name: '',
  display_name: 'Test', photo_url: null, language_code: 'en', role: 'USER',
  is_admin: false, is_banned: false, coins: 500, total_earned: 500, total_spent: 0,
  total_rolls: 3, containers_opened: 0, unique_numbers: 3, collection_progress: 0.0003,
  collection_target: 10_000, best_value: 1200, best_rarity: 'RARE' as Rarity,
  referrals_count: 0, shares_count: 0, challenges_completed: 0, current_streak: 2,
  longest_streak: 2, rolls_remaining: 7, daily_allowance: 10, daily_resets_at: null,
  can_claim_daily: false,
  premium: { active: false, tier: null, expires_at: null, perks: [] },
  created_at: '2026-01-01T00:00:00Z', last_seen_at: null,
};

const daily = {
  rolls_remaining: 7, daily_allowance: 10, resets_at: '2026-01-02T00:00:00Z',
  streak: 2, can_claim: false, claim_reward_coins: 50,
};

const rollResult = {
  success: true, roll_id: 99,
  number: {
    number: '1337', rarity: 'SECRET' as Rarity, value: 120_000,
    traits: ['meme_pattern'], tags: ['special'],
    story: '1337 is a classic leetspeak reference from internet culture.',
    is_special: true, discovery_count: 1, duplicate_count: 0, owned: true, acquired_at: null,
  },
  rarity: 'SECRET' as Rarity, natural_rarity: 'SECRET' as Rarity, luck_rarity: 'COMMON' as Rarity,
  value: 120_000, is_duplicate: false, is_first_discovery: true, coins_awarded: 0,
  balance: 500, rolls_remaining: 6, conversion_value: 30_000,
  unlocked_achievements: [], replayed: false, share_start_param: 'number_1337',
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

/** Route table so each test only declares what it changes. */
function installFetch(overrides: Record<string, () => Response> = {}) {
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    for (const [fragment, handler] of Object.entries(overrides)) {
      if (url.includes(fragment)) return handler();
    }
    if (url.includes('/api/roll')) return json(rollResult);
    if (url.includes('/api/daily')) return json(daily);
    if (url.includes('/api/referrals')) return json({ activated: 0, reward_coins: 250 });
    if (url.includes('/api/leaderboard')) return json({ entries: [] });
    if (url.includes('/api/user/top')) return json({ rarest: [], highest_value: [] });
    return json([]);
  }) as typeof fetch;
}

function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <I18nProvider>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <QueryClientProvider client={client}>{ui}</QueryClientProvider>
      </MemoryRouter>
    </I18nProvider>,
  );
}

describe('HomePage roll flow', () => {
  beforeEach(() => {
    useAuthStore.setState({ profile, token: 'test-token', status: 'authenticated' });
    installFetch();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('renders the roll button with the remaining allowance', async () => {
    renderWithQuery(<HomePage />);
    await waitFor(() => expect(screen.getByTestId('roll-button')).toBeEnabled());
    expect(screen.getByText('7 rolls')).toBeInTheDocument();
  });

  it('shows the server result after rolling', async () => {
    const user = userEvent.setup();
    renderWithQuery(<HomePage />);

    await waitFor(() => expect(screen.getByTestId('roll-button')).toBeEnabled());
    await user.click(screen.getByTestId('roll-button'));

    await waitFor(() => expect(screen.getByTestId('result-overlay')).toBeInTheDocument());
    expect(screen.getByTestId('result-number')).toHaveTextContent('1337');
    expect(screen.getByText('Secret')).toBeInTheDocument();
  });

  it('disables the button and explains when no rolls remain', async () => {
    useAuthStore.setState({ profile: { ...profile, rolls_remaining: 0 }, status: 'authenticated' });
    installFetch({ '/api/daily': () => json({ ...daily, rolls_remaining: 0 }) });

    renderWithQuery(<HomePage />);
    await waitFor(() => expect(screen.getByTestId('roll-button')).toBeDisabled());
    expect(screen.getByText(/No rolls left today/i)).toBeInTheDocument();
  });

  it('surfaces the backend error message', async () => {
    const user = userEvent.setup();
    installFetch({
      '/api/roll': () =>
        json({ success: false, error: { code: 'NO_ROLLS_AVAILABLE', message: 'No rolls available.' } }, 409),
    });

    renderWithQuery(<HomePage />);
    await waitFor(() => expect(screen.getByTestId('roll-button')).toBeEnabled());
    await user.click(screen.getByTestId('roll-button'));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('No rolls available.'));
  });
});

describe('ApiError', () => {
  it('carries the machine readable code from the backend envelope', () => {
    const error = new ApiError('NO_ROLLS_AVAILABLE', 'No rolls available.', 409, { required: 1 });
    expect(error.code).toBe('NO_ROLLS_AVAILABLE');
    expect(error.status).toBe(409);
    expect(error.details).toEqual({ required: 1 });
  });
});
