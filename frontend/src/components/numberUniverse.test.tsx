import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HashRouter } from 'react-router-dom';
import { HuntPage } from '@/pages/HuntPage';
import { WorldPage } from '@/pages/WorldPage';
import { CollectibleVisual, resolveCategory } from '@/components/CollectibleVisual';
import { CategorySelector, CountrySelector } from '@/components/Selectors';
import { Reveal } from '@/components/Reveal';
import { I18nProvider } from '@/i18n';
import type { PlateCard, PlateRollResult } from '@/types';

const reducedMotion = { current: false };

vi.mock('framer-motion', async () => {
  const actual = await vi.importActual<typeof import('framer-motion')>('framer-motion');
  return {
    ...actual,
    useReducedMotion: () => reducedMotion.current,
  };
});

vi.mock('@/lib/telegram', () => ({
  haptic: vi.fn(),
  hapticSuccess: vi.fn(),
  hapticError: vi.fn(),
}));

const ROLL = {
  plate_text: 'A777AA 77',
  display_segments: ['A777AA', '77'],
  country: { code: 'RUS', flag: '🇷🇺', name_en: 'Russia', name_ru: 'Россия' },
  template: { code: 'ru_std_hero', pattern: 'LDDDAA DD' },
  visual: {
    aspect: 2.4,
    background: '#fff',
    border: '#ccc',
    text: '#111',
    muted: '#777',
    band_color: null,
    band_width: 0.1,
    header: '',
    header_align: 'center',
    show_flag: true,
    show_region_flag: false,
    region_badge: false,
    font_stack: 'system',
    letter_spacing: '0.06em',
    gloss: true,
    texture: 'steel',
  },
} as unknown as PlateCard;

function card(overrides: Partial<PlateCard> = {}): PlateCard {
  return {
    ...ROLL,
    id: 1,
    normalized_text: 'A777AA 77',
    letters: [],
    numbers: [],
    plate_type: 'VEHICLE',
    category: 'VEHICLE_PLATE',
    rarity: 'EPIC',
    rarity_score: 700,
    rarity_color: '#a855f7',
    reasons: ['contains_777'],
    reason_labels: ['777'],
    traits: ['contains_777'],
    tags: ['lucky'],
    story: 'Moscow',
    is_secret: false,
    season_code: null,
    discovery_count: 3,
    first_discovered_at: null,
    first_discoverer: null,
    collector_value: 777000,
    currency_code: 'RUB',
    currency_symbol: '₽',
    dealer_value: 77700,
    region: null,
    owned: true,
    duplicate_count: 1,
    is_favorite: false,
    is_new: false,
    acquired_at: null,
    number: 'A777AA 77',
    ...overrides,
  } as PlateCard;
}

function result(overrides: Partial<PlateRollResult> = {}): PlateRollResult {
  return {
    success: true,
    roll_id: 1,
    plate: card(),
    rarity: 'EPIC',
    natural_rarity: 'RARE',
    luck_rarity: 'COMMON',
    rarity_score: 700,
    is_duplicate: false,
    is_first_discovery: true,
    is_new_country: false,
    is_new_region: false,
    numora_awarded: 26000,
    balance: 26000,
    rolls_remaining: 9,
    sale_value: 700,
    collector_level: 1,
    missions_completed: [],
    albums_completed: [],
    unlocked_achievements: [],
    event: null,
    replayed: false,
    share_start_param: 'plate_1',
    value: 700,
    coins_awarded: 26000,
    conversion_value: 700,
    number: card(),
    ...overrides,
  } as PlateRollResult;
}

function renderWith(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <I18nProvider>
        <HashRouter>{ui}</HashRouter>
      </I18nProvider>
    </QueryClientProvider>,
  );
}

const rollMock = vi.fn();

vi.mock('@/services/api', () => ({
  game: {
    roll: (...args: unknown[]) => rollMock(...args),
    rollHistory: () => Promise.resolve([]),
    world: () => worldMock(),
    sell: () => Promise.resolve({ balance: 0, coins: 0 }),
    share: () => Promise.resolve({ mini_app_link: 'https://t/x', share_text_ru: '', share_text_en: '', plate_text: 'x' }),
  },
  leaderboard: { board: () => Promise.resolve({ entries: [] }) },
  social: { board: () => Promise.resolve({ entries: [] }) },
}));

vi.mock('@/store/auth', () => ({
  useAuthStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      profile: { coins: 5000, rolls_remaining: 10 },
      applyProfile: () => {},
    }),
}));

describe('category model', () => {
  it('resolves the category the server sent', () => {
    expect(resolveCategory(card({ category: 'PHONE_NUMBER' }))).toBe('PHONE_NUMBER');
    expect(resolveCategory(card({ category: 'SIM_CARD' }))).toBe('SIM_CARD');
    expect(resolveCategory(card({ category: 'VEHICLE_PLATE' }))).toBe('VEHICLE_PLATE');
  });

  it('falls back to plate_type for older payloads', () => {
    expect(resolveCategory(card({ category: undefined, plate_type: 'PHONE' }))).toBe('PHONE_NUMBER');
    expect(resolveCategory(card({ category: undefined, plate_type: 'SIM' }))).toBe('SIM_CARD');
    expect(resolveCategory(card({ category: undefined, plate_type: 'STANDARD' }))).toBe('VEHICLE_PLATE');
  });
});

describe('collectible visuals', () => {
  it('renders a plate as a vehicle object', () => {
    renderWith(<CollectibleVisual collectible={card()} />);
    const node = screen.getByTestId('collectible-visual');
    expect(node.dataset.kind).toBe('VEHICLE_PLATE');
    expect(node).toHaveTextContent('A777AA');
  });

  it('renders a phone number as a telecom hero card', () => {
    const phone = card({
      category: 'PHONE_NUMBER',
      plate_type: 'PHONE',
      plate_text: '+7 777 777-77-77',
      display_segments: ['+7', '777', '777-77-77'],
    });
    renderWith(<CollectibleVisual collectible={phone} size="hero" />);
    const node = screen.getByTestId('collectible-visual');
    expect(node.dataset.kind).toBe('PHONE_NUMBER');
    expect(node).toHaveTextContent('+7');
    // A phone number must never read as somebody's line.
    expect(node.textContent?.toLowerCase()).toContain('synthetic');
  });

  it('renders a SIM card as a collectible chip card', () => {
    const sim = card({
      category: 'SIM_CARD',
      plate_type: 'SIM',
      plate_text: 'SC 1234 5678 NU',
      display_segments: ['SC', '1234', '5678', 'NU'],
      template: { code: 'rus_sim_numa_crown', pattern: 'SC DDDD DDDD NU' },
    });
    renderWith(<CollectibleVisual collectible={sim} />);
    const node = screen.getByTestId('collectible-visual');
    expect(node.dataset.kind).toBe('SIM_CARD');
    expect(node).toHaveTextContent('SC');
    expect(node.textContent?.toLowerCase()).toContain('crown');
  });
});

describe('category selector', () => {
  it('offers all four game modes in one row', () => {
    const onChange = vi.fn();
    renderWith(<CategorySelector value={null} onChange={onChange} />);
    expect(screen.getByTestId('category-ALL')).toBeTruthy();
    expect(screen.getByTestId('category-VEHICLE_PLATE')).toBeTruthy();
    expect(screen.getByTestId('category-PHONE_NUMBER')).toBeTruthy();
    expect(screen.getByTestId('category-SIM_CARD')).toBeTruthy();
  });

  it('switches category in a single tap', () => {
    const onChange = vi.fn();
    renderWith(<CategorySelector value={null} onChange={onChange} />);
    fireEvent.click(screen.getByTestId('category-PHONE_NUMBER'));
    expect(onChange).toHaveBeenCalledWith('PHONE_NUMBER');
  });

  it('reports ALL as no filter rather than a category', () => {
    const onChange = vi.fn();
    renderWith(<CategorySelector value="PHONE_NUMBER" onChange={onChange} />);
    fireEvent.click(screen.getByTestId('category-ALL'));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('marks the selected mode for assistive tech', () => {
    renderWith(<CategorySelector value="SIM_CARD" onChange={vi.fn()} />);
    expect(screen.getByTestId('category-SIM_CARD').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('category-ALL').getAttribute('aria-selected')).toBe('false');
  });
});

describe('country selector', () => {
  const countries = [
    { code: 'RUS', flag: '🇷🇺', name_en: 'Russia', name_ru: 'Россия' },
    { code: 'USA', flag: '🇺🇸', name_en: 'USA', name_ru: 'США' },
  ];

  it('puts World first so the full hunt is the default', () => {
    renderWith(<CountrySelector value={null} onChange={vi.fn()} countries={countries} />);
    expect(screen.getByTestId('country-WORLD')).toBeTruthy();
    expect(screen.getByTestId('country-RUS')).toBeTruthy();
  });

  it('passes the chosen country code to the caller', () => {
    const onChange = vi.fn();
    renderWith(<CountrySelector value={null} onChange={onChange} countries={countries} />);
    fireEvent.click(screen.getByTestId('country-USA'));
    expect(onChange).toHaveBeenCalledWith('USA');
  });
});

describe('cinematic reveal', () => {
  beforeEach(() => {
    rollMock.mockReset();
  });

  it('shows the anticipation chamber while the roll is in flight', () => {
    renderWith(<Reveal result={null} pending onClose={vi.fn()} />);
    expect(screen.getByTestId('reveal-chamber')).toBeTruthy();
  });

  it('renders nothing when there is no result and no request', () => {
    const { container } = renderWith(<Reveal result={null} pending={false} onClose={vi.fn()} />);
    expect(container.querySelector('[data-testid="reveal"]')).toBeNull();
  });

  it('reaches the action frame and shows the collectible', async () => {
    renderWith(<Reveal result={result()} pending={false} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('reveal')).toHaveAttribute('data-stage', 'actions'), {
      timeout: 12_000,
    });
    expect(screen.getByTestId('collectible-visual')).toHaveTextContent('A777AA');
    // KEEP / SHARE / SELL / COLLECTION - and nothing more.
    expect(screen.getByText('KEEP')).toBeTruthy();
    expect(screen.getByText('SHARE')).toBeTruthy();
    expect(screen.getByText('SELL')).toBeTruthy();
    expect(screen.getByText('COLLECTION')).toBeTruthy();
  }, 15_000);

  it('can be skipped to the final frame', async () => {
    renderWith(<Reveal result={result()} pending={false} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('reveal-skip')).toBeTruthy());
    fireEvent.click(screen.getByTestId('reveal-skip'));
    await waitFor(() => expect(screen.getByTestId('reveal')).toHaveAttribute('data-stage', 'actions'));
  });

  it('presents the server reward, never a client guess', async () => {
    renderWith(<Reveal result={result({ numora_awarded: 26000 })} pending={false} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('reveal')).toHaveAttribute('data-stage', 'actions'), {
      timeout: 12_000,
    });
    expect(screen.getByTestId('value-counter').textContent).toContain('26');
  }, 15_000);

  it('collapses to the final frame when reduced motion is requested', async () => {
    reducedMotion.current = true;
    try {
      renderWith(<Reveal result={result()} pending={false} onClose={vi.fn()} />);
      // No animation, but the same collectible and the same outcome.
      await waitFor(() =>
        expect(screen.getByTestId('reveal')).toHaveAttribute('data-stage', 'actions'),
      );
      expect(screen.getByTestId('collectible-visual')).toBeTruthy();
      expect(screen.getByText('KEEP')).toBeTruthy();
    } finally {
      reducedMotion.current = false;
    }
  });
});

describe('hunt screen', () => {
  beforeEach(() => {
    rollMock.mockReset();
    rollMock.mockResolvedValue(result());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('puts the roll button above everything else', async () => {
    renderWith(<HuntPage />);
    await waitFor(() => expect(screen.getByTestId('roll-button')).toBeTruthy());
    expect(screen.getByTestId('category-selector')).toBeTruthy();
  });

  it('sends the hunt filter to the server, not an outcome', async () => {
    renderWith(<HuntPage />);
    await waitFor(() => expect(screen.getByTestId('roll-button')).toBeTruthy());
    fireEvent.click(screen.getByTestId('category-PHONE_NUMBER'));
    await act(async () => {
      fireEvent.click(screen.getByTestId('roll-button'));
    });
    await waitFor(() => expect(rollMock).toHaveBeenCalled());
    const hunt = rollMock.mock.calls[0]?.[1] as
      | { category: string | null; country_code: string | null }
      | undefined;
    expect(hunt).toEqual({ category: 'PHONE_NUMBER', country_code: null });
    // The client never sends rarity, value or the number itself.
    const serialised = JSON.stringify(rollMock.mock.calls[0]);
    expect(serialised).not.toContain('rarity');
    expect(serialised).not.toContain('collector_value');
  });

  it('opens the reveal after a roll resolves', async () => {
    renderWith(<HuntPage />);
    await waitFor(() => expect(screen.getByTestId('roll-button')).toBeTruthy());
    await act(async () => {
      fireEvent.click(screen.getByTestId('roll-button'));
    });
    await waitFor(() => expect(screen.getByTestId('reveal')).toBeTruthy());
  });

  it('never sends two rolls for one press', async () => {
    renderWith(<HuntPage />);
    await waitFor(() => expect(screen.getByTestId('roll-button')).toBeTruthy());
    await act(async () => {
      fireEvent.click(screen.getByTestId('roll-button'));
      fireEvent.click(screen.getByTestId('roll-button'));
    });
    await waitFor(() => expect(rollMock).toHaveBeenCalledTimes(1));
  });
});

const worldMock = vi.fn();

describe('world screen', () => {
  beforeEach(() => {
    worldMock.mockReset();
  });

  it('shows country progress and a reason to come back', async () => {
    worldMock.mockResolvedValue({
      countries: [
        {
          code: 'RUS',
          flag: '🇷🇺',
          name_en: 'Russia',
          name_ru: 'Россия',
          config: { discovered: 118, total: 120, by_category: {}, is_secret_found: false },
        },
      ],
      total_collected: 118,
      total_plates: 120,
      progress: 0.98,
    });

    renderWith(<WorldPage />);
    await waitFor(() => expect(screen.getByTestId('world-country-RUS')).toBeTruthy());
    expect(screen.getByTestId('world-country-RUS').textContent).toContain('118');
    expect(screen.getByTestId('world-country-RUS').textContent).toContain('120');
  });
});