import { describe, expect, it, vi } from 'vitest';
import { render as rtlRender, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { RarityBadge, TraitChip } from '@/components/RarityBadge';
import { ResultOverlay } from '@/components/ResultOverlay';
import { RollButton } from '@/components/RollButton';
import { CollectionList } from '@/components/CollectionList';
import { ValueCounter } from '@/components/ValueCounter';
import type { PlateCard, PlateRollResult } from '@/types';
import { I18nProvider } from '@/i18n';

/** Every component now reads strings from context, so tests need the provider. */
const wrap = (ui: ReactElement) => <I18nProvider>{ui}</I18nProvider>;

const render = (ui: ReactElement) => rtlRender(wrap(ui));

const visual = {
  theme: 'european',
  aspect: 4.6,
  background: '#f4f6fb',
  border: '#1f2937',
  text: '#111827',
  muted: '#6b7280',
  accent: '#7c5cff',
  band_color: '#1d3fa8',
  band_width: 0.11,
  header: 'RUS',
  header_align: 'center' as const,
  show_flag: true,
  show_region_flag: true,
  region_badge: true,
  font_stack: 'display',
  letter_spacing: '0.06em',
  gloss: true,
  texture: 'metal',
};

const basePlate: PlateCard = {
  id: 777,
  plate_text: 'A777BC777',
  normalized_text: 'a777bc777',
  display_segments: ['A777BC', '777'],
  letters: ['ABC'],
  numbers: ['777', '777'],
  plate_type: 'STANDARD',
  rarity: 'MYTHIC',
  rarity_score: 480,
  rarity_color: '#f43f5e',
  reasons: ['all_same', 'four_of_kind'],
  reason_labels: ['All Same', 'Four of a Kind'],
  traits: ['all_same', 'four_of_kind'],
  tags: ['special'],
  story: 'Every digit repeats - the purest form of plate repetition.',
  is_secret: false,
  season_code: null,
  discovery_count: 3,
  first_discovered_at: '2026-01-01T00:00:00Z',
  first_discoverer: null,
  collector_value: 25000,
  currency_code: 'RUB',
  currency_symbol: '₽',
  dealer_value: 12500,
  country: { code: 'RUS', name_en: 'Russia', name_ru: 'Россия', flag: '🇷🇺' },
  region: { code: 'MOW', name_en: 'Moscow', name_ru: 'Москва' },
  template: { code: 'RUS_STD', pattern: 'LDDDLLLDD' },
  visual,
  owned: true,
  duplicate_count: 2,
  is_favorite: false,
  is_new: false,
  acquired_at: '2026-01-01T00:00:00Z',
  number: 'A777BC777',
};

const baseRoll: PlateRollResult = {
  success: true,
  roll_id: 99,
  plate: basePlate,
  rarity: 'MYTHIC',
  natural_rarity: 'MYTHIC',
  luck_rarity: 'COMMON',
  rarity_score: 480,
  is_duplicate: false,
  is_first_discovery: true,
  is_new_country: false,
  is_new_region: false,
  numora_awarded: 0,
  balance: 500,
  rolls_remaining: 6,
  sale_value: 12500,
  collector_level: 3,
  missions_completed: [],
  albums_completed: [],
  unlocked_achievements: [],
  event: null,
  replayed: false,
  share_start_param: 'plate_777',
  value: 12500,
  coins_awarded: 0,
  conversion_value: 12500,
  number: basePlate,
};
describe('RarityBadge', () => {
  it('renders the human label', () => {
    render(<RarityBadge rarity="LEGENDARY" />);
    expect(screen.getByText('Legendary')).toBeInTheDocument();
  });

  it('falls back to COMMON for unknown values', () => {
    render(<RarityBadge rarity="NOT_A_RARITY" />);
    expect(screen.getByText('Common')).toBeInTheDocument();
  });
});

describe('TraitChip', () => {
  it('keeps the trait code for testing and analytics', () => {
    render(<TraitChip code="palindrome" label="Palindrome" />);
    const chip = screen.getByText('Palindrome');
    expect(chip).toHaveAttribute('data-trait', 'palindrome');
  });
});

describe('RollButton', () => {
  it('fires the callback when rolls are available', () => {
    const onRoll = vi.fn();
    render(<RollButton rollsLeft={3} onRoll={onRoll} />);
    screen.getByTestId('roll-button').click();
    expect(onRoll).toHaveBeenCalledTimes(1);
  });

  it('is disabled when no rolls remain', () => {
    const onRoll = vi.fn();
    render(<RollButton rollsLeft={0} onRoll={onRoll} />);
    expect(screen.getByTestId('roll-button')).toBeDisabled();
  });

  it('shows the remaining roll count', () => {
    render(<RollButton rollsLeft={1} onRoll={vi.fn()} />);
    expect(screen.getByText('1 roll')).toBeInTheDocument();
  });
});

describe('ValueCounter', () => {
  it('counts up to the final value', async () => {
    render(<ValueCounter value={1234} suffix=" NUMORA" />);
    expect(await screen.findByText('1,234 NUMORA', {}, { timeout: 3000 })).toBeInTheDocument();
  });
});

describe('ResultOverlay', () => {
  it('renders the revealed plate when open', async () => {
    render(
      <ResultOverlay open result={baseRoll} onClose={vi.fn()} onShare={vi.fn()} onSell={vi.fn()} />,
    );

    expect(screen.getByTestId('plate-visual')).toHaveAttribute('data-plate', 'A777BC777');
    expect(screen.getByText('Mythic')).toBeInTheDocument();
    expect(screen.getByText(/Secret Discovered/)).toBeInTheDocument();
    // The dealer value animates up to its final number.
    expect(await screen.findByText('12,500 NUMORA', {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText(/₽25,000/)).toBeInTheDocument();
  });

  it('offers a dealer sale for duplicates', () => {
    render(
      <ResultOverlay
        open
        result={{ ...baseRoll, is_duplicate: true, is_first_discovery: false }}
        onClose={vi.fn()}
        onShare={vi.fn()}
        onSell={vi.fn()}
      />,
    );
    expect(screen.getByText('Duplicate')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sell duplicates/i })).toBeInTheDocument();
  });

  it('renders nothing when closed', () => {
    render(
      <ResultOverlay open={false} result={null} onClose={vi.fn()} onShare={vi.fn()} onSell={vi.fn()} />,
    );
    expect(screen.queryByTestId('result-overlay')).not.toBeInTheDocument();
  });
});

describe('CollectionList', () => {
  it('lists owned plates with their dealer value', () => {
    render(
      <CollectionList items={[basePlate]} expanded={null} onToggle={vi.fn()} selling={false} onSell={vi.fn()} />,
    );
    expect(screen.getByTestId('plate-visual')).toHaveAttribute('data-plate', 'A777BC777');
    expect(screen.getByText('+12,500')).toBeInTheDocument();
    expect(screen.getByText('×2 dup')).toBeInTheDocument();
  });

  it('expands a row to reveal the dealer sale action', () => {
    render(
      <CollectionList items={[basePlate]} expanded={777} onToggle={vi.fn()} selling={false} onSell={vi.fn()} />,
    );
    expect(screen.getByRole('button', { name: /Sell duplicate copies/i })).toBeInTheDocument();
  });
});
