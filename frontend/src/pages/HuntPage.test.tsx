import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactElement } from 'react';

import HuntPage from '@/pages/HuntPage';
import { I18nProvider } from '@/i18n';
import { ApiError } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import {
  countryCard,
  garage,
  json,
  plate,
  profile,
  rollBalance,
  rollResult,
  simPlate,
  uniquePlate,
} from '@/test/fixtures';

vi.mock('@/lib/telegram', () => ({
  haptic: vi.fn(),
  hapticSuccess: vi.fn(),
  hapticError: vi.fn(),
  hapticCue: vi.fn(),
  shareToChat: vi.fn(),
  openTelegramLink: vi.fn(),
}));

/** Records every request so a test can assert what was actually sent. */
interface Call {
  url: string;
  init: RequestInit | undefined;
}

const calls: Call[] = [];

function installFetch(overrides: Record<string, () => Response> = {}) {
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    for (const [fragment, handler] of Object.entries(overrides)) {
      if (url.includes(fragment)) return handler();
    }
    if (url.includes('/api/roll?')) return json(rollResult());
    if (url.includes('/api/roll')) return json(rollResult());
    if (url.includes('/api/garage')) return json(garage());
    if (url.includes('/api/countries/active')) return json({ code: 'RUS', country: countryCard() });
    if (url.includes('/api/countries')) return json({ items: [countryCard()], playable_total: 30 });
    if (url.includes('/api/daily')) return json(rollBalance());
    return json({});
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

/** The roll button is the primary action; find it by what it promises. */
const rollButton = () => screen.getByRole('button', { name: /^roll/i });

describe('HuntPage core loop', () => {
  beforeEach(() => {
    calls.length = 0;
    useAuthStore.setState({ profile, token: 'test-token', status: 'authenticated' });
    installFetch();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('leads with the roll, and shows the server balance', async () => {
    renderWithQuery(<HuntPage />);
    await waitFor(() => expect(rollButton()).toBeEnabled());
    // The count is on the control itself, and the same authoritative balance is on the
    // bank line above it - one number, shown once per place it belongs.
    expect(within(rollButton()).getByText(/18/)).toBeInTheDocument();
    expect(screen.getAllByText(/18 rolls/).length).toBeGreaterThan(0);
  });

  it('rolls once per press, and never twice for a double tap', async () => {
    const user = userEvent.setup();
    installFetch({
      '/api/roll': () => json(rollResult({ plate: plate() })),
    });
    renderWithQuery(<HuntPage />);
    await waitFor(() => expect(rollButton()).toBeEnabled());

    await user.dblClick(rollButton());

    await waitFor(() => expect(calls.some((call) => call.url.includes('/api/roll'))).toBe(true));
    // The synchronous guard swallows the second press.
    expect(calls.filter((call) => call.url.includes('/api/roll'))).toHaveLength(1);
  });

  it('sends an idempotency key so a retry can never pay twice', async () => {
    const user = userEvent.setup();
    renderWithQuery(<HuntPage />);
    await waitFor(() => expect(rollButton()).toBeEnabled());
    await user.click(rollButton());

    await waitFor(() => expect(calls.some((call) => call.url.includes('/api/roll'))).toBe(true));
    const headers = calls.find((call) => call.url.includes('/api/roll'))?.init?.headers as
      | Record<string, string>
      | undefined;
    expect(headers?.['Idempotency-Key']).toMatch(/^roll-/);
  });

  it('shows one authoritative reveal, offering ROLL AGAIN', async () => {
    const user = userEvent.setup();
    renderWithQuery(<HuntPage />);
    await waitFor(() => expect(rollButton()).toBeEnabled());
    await user.click(rollButton());

    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument(), { timeout: 5000 });
    const again = await screen.findByRole('button', { name: /roll again/i }, { timeout: 6000 });
    expect(again).toBeEnabled();
  });

  it('never sends a sale request for a collectible with no duplicates', async () => {
    const user = userEvent.setup();
    installFetch({
      '/api/roll': () => json(rollResult({ plate: uniquePlate() })),
    });
    renderWithQuery(<HuntPage />);
    await waitFor(() => expect(rollButton()).toBeEnabled());
    await user.click(rollButton());

    await screen.findByRole('button', { name: /roll again/i }, { timeout: 6000 });
    // The action does not exist, so the invalid request can never be constructed.
    expect(screen.queryByRole('button', { name: /sell duplicates/i })).toBeNull();

    await user.click(screen.getByRole('button', { name: /close|cancel|collection/i, hidden: true }));
    expect(calls.some((call) => call.url.includes('/sell'))).toBe(false);
  });

  it('sells the exact duplicate count when duplicates exist', async () => {
    const user = userEvent.setup();
    const sold = plate({ duplicate_count: 3, sale_value: 250 });
    let sellBody: unknown = null;
    installFetch({
      '/api/roll': () => json(rollResult({ plate: sold })),
      '/sell': () => {
        const call = calls[calls.length - 1];
        sellBody = JSON.parse(String(call?.init?.body ?? '{}'));
        return json({
          plate_id: sold.id,
          plate_text: sold.plate_text,
          copies_sold: 3,
          numora_gained: 750,
          duplicates_left: 0,
          balance: 1250,
        });
      },
    });

    renderWithQuery(<HuntPage />);
    await waitFor(() => expect(rollButton()).toBeEnabled());
    await user.click(rollButton());

    const sellButton = await screen.findByRole(
      'button',
      { name: /sell duplicates/i },
      { timeout: 6000 },
    );
    await user.click(sellButton);

    await waitFor(() => expect(sellBody).not.toBeNull(), { timeout: 8000 });
    expect(sellBody).toEqual({ copies: 3 });
  }, 15000);

  it('surfaces a failed roll instead of failing silently', async () => {
    const user = userEvent.setup();
    installFetch({
      '/api/roll': () =>
        json(
          {
            success: false,
            error: { code: 'NO_ROLLS_AVAILABLE', message: 'No rolls available.' },
          },
          409,
        ),
    });

    renderWithQuery(<HuntPage />);
    await waitFor(() => expect(rollButton()).toBeEnabled());
    await user.click(rollButton());

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('No rolls available.'));
  });

  it('always shows one next objective', async () => {
    renderWithQuery(<HuntPage />);
    await waitFor(() => expect(screen.getByText(/more regions|discover your first region/i)).toBeInTheDocument());
  });

  it('renders the recent find as a physical object', async () => {
    renderWithQuery(<HuntPage />);
    await waitFor(() => expect(rollButton()).toBeEnabled());
    await waitFor(() =>
      expect(screen.getByTestId('hunt-page').querySelector('.plate-frame')).not.toBeNull(),
    );
  });

  it('renders a SIM card recent find as a card', async () => {
    installFetch({ '/api/garage': () => json(garage({ recent: simPlate() })) });
    renderWithQuery(<HuntPage />);
    await waitFor(() => expect(rollButton()).toBeEnabled());
    await waitFor(() => expect(document.querySelector('.sim-body')).not.toBeNull());
  });

  it('disables the roll when the bank is empty and explains why', async () => {
    installFetch({
      '/api/garage': () =>
        json(
          garage({
            rolls: rollBalance({ rolls_remaining: 0, normal_rolls: 0, bank_cap: 20 }),
          }),
        ),
    });
    renderWithQuery(<HuntPage />);
    await waitFor(() => expect(screen.getByRole('button', { name: /no rolls/i })).toBeDisabled());
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