import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactElement } from 'react';
import { HomePage } from '@/pages/HomePage';
import { ApiError } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import type { PlateCard, PlateRollResult, Rarity, UserProfile } from '@/types';
import { I18nProvider } from '@/i18n';

const profile: UserProfile = {
  id: 1, telegram_id: 42, username: 'tester', first_name: 'Test', last_name: '',
  display_name: 'Test', photo_url: null, language_code: 'en', role: 'USER',
  is_admin: false, is_banned: false, coins: 500, total_earned: 500, total_spent: 0,
  total_rolls: 3, containers_opened: 0, unique_numbers: 3, plates_count: 3,
  countries_count: 2, regions_count: 2, first_discoveries_count: 1, duplicates_sold_count: 0,
  collection_progress: 0.0003, collection_target: 10_000,
  collector_level: { level: 2, title_en: 'Spotter', title_ru: 'Разведчик', xp: 120, xp_into_level: 20, xp_for_level: 100, progress: 0.2 },
  best_value: 1200, best_rarity: 'RARE' as Rarity, best_collector_value: 45_000,
  best_plate_id: 7, best_plate_text: 'A123BC 777',
  referrals_count: 0, shares_count: 0, challenges_completed: 0, current_streak: 2,
  longest_streak: 2, rolls_remaining: 7, daily_allowance: 10, daily_resets_at: null,
  can_claim_daily: false,
  premium: { active: false, tier: null, expires_at: null, perks: [] },
  supporter: false, season_pass_active: false, equipped_title: null, equipped_cosmetics: [],
  created_at: '2026-01-01T00:00:00Z', last_seen_at: null,
};

const daily = {
  rolls_remaining: 7, daily_allowance: 10, resets_at: '2026-01-02T00:00:00Z',
  streak: 2, can_claim: false, claim_reward_coins: 50,
};

const visual = {
  theme: 'european', aspect: 4.6, background: '#f4f6fb', border: '#1f2937',
  text: '#111827', muted: '#6b7280', accent: '#7c5cff', band_color: null, band_width: 0,
  header: '', header_align: 'center' as const, show_flag: true, show_region_flag: true,
  region_badge: true, font_stack: 'display', letter_spacing: '0.06em', gloss: true,
  texture: 'metal',
};

const plate: PlateCard = {
  id: 42, plate_text: 'A123BC 777', normalized_text: 'a123bc777',
  display_segments: ['A123BC', '777'], letters: ['ABC'], numbers: ['123', '777'],
  plate_type: 'STANDARD', rarity: 'SECRET' as Rarity, rarity_score: 999, rarity_color: '#22d3ee',
  reasons: ['meme_pattern'], reason_labels: ['Meme Pattern'], traits: ['meme_pattern'],
  tags: ['special'], story: 'A classic leetspeak reference.', is_secret: true,
  season_code: null, discovery_count: 1, first_discovered_at: null, first_discoverer: null,
  collector_value: 90_000, currency_code: 'EUR', currency_symbol: '€', dealer_value: 30_000,
  country: { code: 'DEU', name_en: 'Germany', name_ru: 'Германия', flag: '🇩🇪' },
  region: null, template: { code: 'DE_STD', pattern: 'LDDDLLLDD' }, visual,
  owned: true, duplicate_count: 0, is_favorite: false, is_new: true, acquired_at: null,
  number: 'A123BC 777',
};

const rollResult: PlateRollResult = {
  success: true, roll_id: 99, plate,
  rarity: 'SECRET' as Rarity, natural_rarity: 'SECRET' as Rarity, luck_rarity: 'COMMON' as Rarity,
  rarity_score: 999, is_duplicate: false, is_first_discovery: true,
  is_new_country: false, is_new_region: false, numora_awarded: 0,
  balance: 500, rolls_remaining: 6, sale_value: 30_000, collector_level: 2,
  missions_completed: [], albums_completed: [], unlocked_achievements: [],
  event: null, replayed: false, share_start_param: 'plate_42',
  value: 30_000, coins_awarded: 0, conversion_value: 30_000, number: plate,
};

const garage = {
  best: plate, recent: plate, plates_count: 3, countries_count: 2, regions_count: 2,
  first_discoveries: 1, best_collector_value: 90_000, world_progress: 0.01,
  level: profile.collector_level, event: null, albums_completed: [], equipped_cosmetics: [],
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
    if (url.includes('/api/garage')) return json(garage);
    if (url.includes('/api/referrals')) return json({ activated: 0, reward_coins: 250 });
    if (url.includes('/api/leaderboard')) return json({ entries: [] });
    if (url.includes('/api/challenges')) return json([]);
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

  it('shows the server plate result after rolling', async () => {
    const user = userEvent.setup();
    renderWithQuery(<HomePage />);

    await waitFor(() => expect(screen.getByTestId('roll-button')).toBeEnabled());
    await user.click(screen.getByTestId('roll-button'));

    await waitFor(() => expect(screen.getByTestId('result-overlay')).toBeInTheDocument());
    const overlay = within(screen.getByTestId('result-overlay'));
    expect(overlay.getByTestId('plate-visual')).toHaveAttribute('data-plate', 'A123BC 777');
    expect(overlay.getByText('Secret')).toBeInTheDocument();
    expect(overlay.getByText(/Secret Discovered/)).toBeInTheDocument();
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
