import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HashRouter } from 'react-router-dom';
import { HuntPage } from '@/pages/HuntPage';
import { WorldPage } from '@/pages/WorldPage';
import { CollectibleVisual, resolveKind } from '@/components/CollectibleVisual';
import { SimCardVisual } from '@/components/SimCardVisual';
import { VehiclePlateVisual } from '@/components/VehiclePlateVisual';
import { CollectibleDetails } from '@/components/CollectibleDetails';
import { CountrySelector } from '@/components/CountrySelector';
import { KindSelector } from '@/components/Selectors';
import { Reveal } from '@/components/Reveal';
import { I18nProvider } from '@/i18n';
import { ApiError } from '@/lib/api';
import { COLLECTIBLE_KINDS } from '@/types';
import type { CountrySummary, PlateCard, PlateRollResult, SimCardDetails } from '@/types';

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
  shareToChat: vi.fn(),
  showBackButton: () => () => {},
  hideBackButton: vi.fn(),
}));

const VISUAL = {
  aspect: 2.4,
  background: '#fff',
  border: '#ccc',
  text: '#111',
  muted: '#777',
  accent: '#111',
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
  theme: 'european',
} as unknown as PlateCard['visual'];

const SIM_DETAILS: SimCardDetails = {
  operator_code: 'numa',
  operator: 'NUMA',
  operator_local: 'НУМА',
  series: 'N-07',
  edition: 'CROWN',
  synthetic_number: '+7 900 123 45 67',
  calling_code: '+7',
  synthetic: true,
};

function card(overrides: Partial<PlateCard> = {}): PlateCard {
  return {
    id: 1,
    plate_text: 'A777AA 77',
    normalized_text: 'A777AA 77',
    display_segments: ['A777AA', '77'],
    letters: [],
    numbers: [],
    plate_type: 'STANDARD',
    kind: 'VEHICLE_PLATE',
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
    country: {
      code: 'RUS',
      iso_alpha2: 'RU',
      flag: '🇷🇺',
      name_en: 'Russia',
      name_ru: 'Россия',
    },
    region: null,
    template: { code: 'ru_standard', pattern: 'LDDD LL DD' },
    visual: VISUAL,
    details: null,
    owned: true,
    duplicate_count: 1,
    is_favorite: false,
    is_new: false,
    acquired_at: null,
    ...overrides,
  } as PlateCard;
}

function simCard(overrides: Partial<PlateCard> = {}): PlateCard {
  return card({
    plate_text: SIM_DETAILS.synthetic_number,
    display_segments: ['+7', '900', '123', '45', '67'],
    plate_type: 'SIM',
    kind: 'SIM_CARD',
    details: SIM_DETAILS,
    template: { code: 'rus_sim_numa_crown_1', pattern: '+7 900 DDD DD DD' },
    ...overrides,
  });
}

function country(overrides: Partial<CountrySummary> = {}): CountrySummary {
  return {
    code: 'RUS',
    iso_alpha2: 'RU',
    name_en: 'Russia',
    name_ru: 'Россия',
    flag: '🇷🇺',
    region_group: 'CIS',
    currency_code: 'RUB',
    currency_symbol: '₽',
    calling_code: '+7',
    collected: 0,
    total: 120,
    progress: 0,
    percent: 0,
    best_rarity: null,
    regions_collected: 0,
    regions_total: 0,
    completed: false,
    sort_order: 1,
    is_active: true,
    is_playable: true,
    ...overrides,
  };
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
const setActiveMock = vi.fn();
const worldMock = vi.fn();
const countryListMock = vi.fn();
const activeCountryMock = vi.fn();

vi.mock('@/services/api', () => ({
  game: {
    roll: (...args: unknown[]) => rollMock(...args),
    rollHistory: () => Promise.resolve([]),
    world: (...args: unknown[]) => worldMock(...args),
    sell: () => Promise.resolve({ balance: 0, numora_gained: 0 }),
    share: () =>
      Promise.resolve({
        mini_app_link: 'https://t/x',
        share_text_ru: '',
        share_text_en: '',
        plate_text: 'x',
      }),
    collection: () => Promise.resolve({ items: [], page: 1, page_size: 30, total: 0, has_more: false }),
  },
  countries: {
    list: (...args: unknown[]) => countryListMock(...args),
    active: () => activeCountryMock(),
    setActive: (...args: unknown[]) => setActiveMock(...args),
    detail: () => Promise.resolve({}),
  },
  leaderboard: { board: () => Promise.resolve({ entries: [] }) },
  social: { referrals: () => Promise.resolve({ activated: 0, reward_coins: 0 }), challenges: () => Promise.resolve([]) },
}));

vi.mock('@/store/auth', () => ({
  useAuthStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      profile: { coins: 5000, rolls_remaining: 10, username: 'player' },
      applyProfile: () => {},
    }),
}));

describe('collectible kinds', () => {
  it('exposes exactly two kinds', () => {
    expect([...COLLECTIBLE_KINDS]).toEqual(['VEHICLE_PLATE', 'SIM_CARD']);
  });

  it('resolves the kind the server sent', () => {
    expect(resolveKind(card({ kind: 'SIM_CARD' }))).toBe('SIM_CARD');
    expect(resolveKind(card({ kind: 'VEHICLE_PLATE' }))).toBe('VEHICLE_PLATE');
  });

  it('falls back to plate_type for payloads cached before the SIM line', () => {
    expect(resolveKind(card({ kind: undefined, plate_type: 'SIM' }))).toBe('SIM_CARD');
    expect(resolveKind(card({ kind: undefined, plate_type: 'STANDARD' }))).toBe('VEHICLE_PLATE');
  });

  it('has no phone-number kind to fall back to', () => {
    // A legacy PHONE row is a SIM card: a number printed on a card, never its own
    // collectible.
    expect(resolveKind(card({ kind: undefined, plate_type: 'PHONE' }))).toBe('VEHICLE_PLATE');
  });
});

describe('collectible visuals', () => {
  it('renders a plate as a physical object', () => {
    renderWith(<VehiclePlateVisual collectible={card()} />);
    const node = screen.getByTestId('vehicle-plate-visual');
    expect(node.dataset.kind).toBe('VEHICLE_PLATE');
    expect(node).toHaveTextContent('A777AA');
  });

  it('renders a SIM as a physical card, never a phone mockup', () => {
    renderWith(<SimCardVisual collectible={simCard()} />);
    const node = screen.getByTestId('sim-card-visual');
    expect(node.dataset.kind).toBe('SIM_CARD');
    expect(node.dataset.plate).toBe('+7 900 123 45 67');
    // The printed number, the operator and the series are all on the card.
    expect(node).toHaveTextContent('+7 900 123 45 67');
    expect(node).toHaveTextContent('NUMA');
    expect(node).toHaveTextContent('N-07');
    // And it must never be mistaken for a real subscriber line.
    expect(node.textContent?.toLowerCase()).toContain('synthetic');
    // 2FF card proportions, not a phone.
    expect(node.style.aspectRatio).toBe(String(25 / 15));
  });

  it('dispatches on the kind the server sent', () => {
    const { unmount } = renderWith(<CollectibleVisual collectible={card()} />);
    expect(screen.getByTestId('vehicle-plate-visual')).toBeTruthy();
    unmount();
    renderWith(<CollectibleVisual collectible={simCard()} />);
    expect(screen.getByTestId('sim-card-visual')).toBeTruthy();
  });
});

describe('collectible details', () => {
  it('shows SIM facts and never a phone-number section', () => {
    renderWith(<CollectibleDetails collectible={simCard()} />);
    const node = screen.getByTestId('collectible-details');
    expect(node.dataset.kind).toBe('SIM_CARD');
    expect(node).toHaveTextContent('NUMA');
    expect(node).toHaveTextContent('N-07');
    expect(node).toHaveTextContent('+7 900 123 45 67');
    expect(node.textContent?.toLowerCase()).not.toContain('phone');
  });

  it('shows plate facts and no operator', () => {
    renderWith(<CollectibleDetails collectible={card({ region: { code: '77', name_en: 'Moscow', name_ru: 'Москва' } })} />);
    const node = screen.getByTestId('collectible-details');
    expect(node.dataset.kind).toBe('VEHICLE_PLATE');
    expect(node).toHaveTextContent('Moscow');
    expect(node.textContent?.toLowerCase()).not.toContain('operator');
  });
});

describe('kind selector', () => {
  it('offers exactly three states: all, plates and SIM', () => {
    renderWith(<KindSelector value={null} onChange={vi.fn()} />);
    expect(screen.getByTestId('kind-ALL')).toBeTruthy();
    expect(screen.getByTestId('kind-VEHICLE_PLATE')).toBeTruthy();
    expect(screen.getByTestId('kind-SIM_CARD')).toBeTruthy();
    expect(screen.queryByTestId('kind-PHONE_NUMBER')).toBeNull();
  });

  it('switches kind in a single tap', () => {
    const onChange = vi.fn();
    renderWith(<KindSelector value={null} onChange={onChange} />);
    fireEvent.click(screen.getByTestId('kind-SIM_CARD'));
    expect(onChange).toHaveBeenCalledWith('SIM_CARD');
  });

  it('reports ALL as no filter rather than a kind', () => {
    const onChange = vi.fn();
    renderWith(<KindSelector value="SIM_CARD" onChange={onChange} />);
    fireEvent.click(screen.getByTestId('kind-ALL'));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('marks the selected kind for assistive tech', () => {
    renderWith(<KindSelector value="SIM_CARD" onChange={vi.fn()} />);
    expect(screen.getByTestId('kind-SIM_CARD').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('kind-ALL').getAttribute('aria-selected')).toBe('false');
  });
});

describe('country selector', () => {
  const countries = [
    country(),
    country({ code: 'USA', iso_alpha2: 'US', flag: '🇺🇸', name_en: 'United States', name_ru: 'США', region_group: 'AMERICAS', calling_code: '+1' }),
    country({ code: 'ATA', flag: '🇦🇹', name_en: 'Antarctica', name_ru: 'Антарктида', region_group: 'ANTARCTIC', is_playable: false, total: 0 }),
  ];

  it('always shows the current country before the sheet opens', () => {
    renderWith(<CountrySelector value="USA" onChange={vi.fn()} countries={countries} />);
    const button = screen.getByTestId('active-country');
    expect(button.textContent).toContain('🇺🇸');
    expect(button.textContent).toContain('United States');
  });

  it('opens a searchable sheet rather than an HTML select', () => {
    renderWith(<CountrySelector value={null} onChange={vi.fn()} countries={countries} />);
    fireEvent.click(screen.getByTestId('active-country'));
    expect(screen.getByTestId('country-sheet')).toBeTruthy();
    expect(screen.getByTestId('country-search')).toBeTruthy();
    expect(document.querySelector('select')).toBeNull();
  });

  it('searches by code, alpha-2, name and calling code', () => {
    renderWith(<CountrySelector value={null} onChange={vi.fn()} countries={countries} />);
    fireEvent.click(screen.getByTestId('active-country'));
    const search = screen.getByTestId('country-search');
    fireEvent.change(search, { target: { value: 'antarc' } });
    expect(screen.getByTestId('country-option-ATA')).toBeTruthy();
    expect(screen.queryByTestId('country-option-RUS')).toBeNull();
    fireEvent.change(search, { target: { value: '+7' } });
    expect(screen.getByTestId('country-option-RUS')).toBeTruthy();
  });

  it('marks a locked country instead of hiding it', () => {
    renderWith(<CountrySelector value={null} onChange={vi.fn()} countries={countries} />);
    fireEvent.click(screen.getByTestId('active-country'));
    const locked = screen.getByTestId('country-option-ATA') as HTMLButtonElement;
    expect(locked.dataset.locked).toBe('true');
    expect(locked.disabled).toBe(true);
  });

  it('marks the selected country', () => {
    renderWith(<CountrySelector value="RUS" onChange={vi.fn()} countries={countries} />);
    fireEvent.click(screen.getByTestId('active-country'));
    expect(screen.getByTestId('country-option-RUS').getAttribute('aria-current')).toBe('true');
  });

  it('passes the chosen code to the caller', () => {
    const onChange = vi.fn();
    renderWith(<CountrySelector value={null} onChange={onChange} countries={countries} />);
    fireEvent.click(screen.getByTestId('active-country'));
    fireEvent.click(screen.getByTestId('country-option-USA'));
    expect(onChange).toHaveBeenCalledWith('USA');
  });

  it('clears the selection back to the whole world', () => {
    const onChange = vi.fn();
    renderWith(<CountrySelector value="RUS" onChange={onChange} countries={countries} />);
    fireEvent.click(screen.getByTestId('active-country'));
    fireEvent.click(screen.getByTestId('country-option-WORLD'));
    expect(onChange).toHaveBeenCalledWith(null);
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
    expect(screen.getByTestId('vehicle-plate-visual')).toHaveTextContent('A777AA');
    expect(screen.getByText('KEEP')).toBeTruthy();
    expect(screen.getByText('SHARE')).toBeTruthy();
    expect(screen.getByText('SELL')).toBeTruthy();
    expect(screen.getByText('COLLECTION')).toBeTruthy();
  }, 15_000);

  it('reveals a SIM card through the same controller', async () => {
    const sim = simCard();
    renderWith(<Reveal result={result({ plate: sim })} pending={false} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('reveal')).toHaveAttribute('data-stage', 'actions'), {
      timeout: 12_000,
    });
    const node = screen.getByTestId('sim-card-visual');
    expect(node).toHaveTextContent('+7 900 123 45 67');
    expect(screen.getByText('KEEP')).toBeTruthy();
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
      await waitFor(() =>
        expect(screen.getByTestId('reveal')).toHaveAttribute('data-stage', 'actions'),
      );
      expect(screen.getByTestId('vehicle-plate-visual')).toBeTruthy();
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
    setActiveMock.mockReset();
    setActiveMock.mockResolvedValue({ country: null, code: null });
    activeCountryMock.mockReset();
    activeCountryMock.mockResolvedValue({
      country: { ...country(), is_active_country: true, sim: { calling_code: '+7', groups: [3, 2, 2], operators: [], editions: [], synthetic: true } },
      code: 'RUS',
      playable_total: 49,
      locked_total: 201,
    });
    countryListMock.mockReset();
    countryListMock.mockResolvedValue({
      items: [country()],
      total: 250,
      playable_total: 49,
      locked_total: 201,
      region_groups: ['CIS'],
      query: null,
      offset: 0,
      limit: 250,
      active_code: null,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('puts the roll button above everything else', async () => {
    renderWith(<HuntPage />);
    await waitFor(() => expect(screen.getByTestId('roll-button')).toBeTruthy());
    expect(screen.getByTestId('kind-selector')).toBeTruthy();
  });

  it('shows the active country without waiting for the sheet', async () => {
    renderWith(<HuntPage />);
    await waitFor(() => expect(screen.getByTestId('active-country')).toBeTruthy());
    expect(screen.getByTestId('active-country').textContent).toContain('🇷🇺');
  });

  it('sends only the kind filter, never a country or an outcome', async () => {
    renderWith(<HuntPage />);
    await waitFor(() => expect(screen.getByTestId('roll-button')).toBeTruthy());
    fireEvent.click(screen.getByTestId('kind-SIM_CARD'));
    await act(async () => {
      fireEvent.click(screen.getByTestId('roll-button'));
    });
    await waitFor(() => expect(rollMock).toHaveBeenCalled());
    // The active country lives on the server; the client must not restate it.
    expect(rollMock.mock.calls[0]?.[1]).toEqual({ kind: 'SIM_CARD' });
    const serialised = JSON.stringify(rollMock.mock.calls[0]);
    expect(serialised).not.toContain('rarity');
    expect(serialised).not.toContain('collector_value');
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

  it('persists a country change through the server, not local state', async () => {
    renderWith(<HuntPage />);
    await waitFor(() => expect(screen.getByTestId('active-country')).toBeTruthy());
    fireEvent.click(screen.getByTestId('active-country'));
    await waitFor(() => expect(screen.getByTestId('country-option-RUS')).toBeTruthy());
    await act(async () => {
      fireEvent.click(screen.getByTestId('country-option-RUS'));
    });
    await waitFor(() => expect(setActiveMock).toHaveBeenCalledWith('RUS'));
  });

  it('says so when a roll fails, and stays usable', async () => {
    rollMock.mockRejectedValueOnce(
      new ApiError('UNAVAILABLE', 'Service unavailable', 503),
    );
    renderWith(<HuntPage />);
    await waitFor(() => expect(screen.getByTestId('roll-button')).toBeTruthy());
    await act(async () => {
      fireEvent.click(screen.getByTestId('roll-button'));
    });
    // No dead end: the message is actionable and the button comes back.
    await waitFor(() => expect(screen.getByText(/unavailable/i)).toBeTruthy());
    const button = screen.getByTestId('roll-button');
    expect(button.hasAttribute('disabled')).toBe(false);
  });

  it('says so when a country switch is refused', async () => {
    setActiveMock.mockRejectedValueOnce(
      new ApiError('COUNTRY_LOCKED', 'Antarctica is not available yet.', 422),
    );
    renderWith(<HuntPage />);
    await waitFor(() => expect(screen.getByTestId('active-country')).toBeTruthy());
    fireEvent.click(screen.getByTestId('active-country'));
    await waitFor(() => expect(screen.getByTestId('country-option-RUS')).toBeTruthy());
    await act(async () => {
      fireEvent.click(screen.getByTestId('country-option-RUS'));
    });
    await waitFor(() => expect(screen.getByText(/not available yet/i)).toBeTruthy());
  });
});

describe('world screen', () => {
  beforeEach(() => {
    worldMock.mockReset();
    countryListMock.mockReset();
    countryListMock.mockResolvedValue({
      items: [country()],
      total: 250,
      playable_total: 49,
      locked_total: 201,
      region_groups: ['CIS'],
      query: null,
      offset: 0,
      limit: 250,
      active_code: null,
    });
  });

  it('shows country progress and marks a locked country', async () => {
    worldMock.mockResolvedValue({
      countries: [
        country({ collected: 118, total: 120 }),
        country({ code: 'ATA', flag: '🇦🇹', name_en: 'Antarctica', name_ru: 'Антарктида', region_group: 'ANTARCTIC', is_playable: false, collected: 0, total: 0 }),
      ],
      total_collected: 118,
      total_plates: 120,
      progress: 0.98,
      offset: 0,
      limit: 60,
      countries_total: 250,
      playable_total: 49,
      locked_total: 201,
    });

    renderWith(<WorldPage />);
    await waitFor(() => expect(screen.getByTestId('world-country-RUS')).toBeTruthy());
    expect(screen.getByTestId('world-country-RUS').textContent).toContain('118');
    expect(screen.getByTestId('world-country-ATA').dataset.locked).toBe('true');
  });
});