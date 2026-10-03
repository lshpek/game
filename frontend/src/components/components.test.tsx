import { describe, expect, it, vi } from 'vitest';
import { render as rtlRender, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { RarityBadge, TraitChip } from '@/components/RarityBadge';
import { ResultOverlay } from '@/components/ResultOverlay';
import { RollButton } from '@/components/RollButton';
import { CollectionList } from '@/components/CollectionList';
import type { NumberCard } from '@/types';
import { I18nProvider } from '@/i18n';

/** Every component now reads strings from context, so tests need the provider. */
const wrap = (ui: ReactElement) => <I18nProvider>{ui}</I18nProvider>;

const render = (ui: ReactElement) => rtlRender(wrap(ui));

const baseNumber: NumberCard = {
  number: '7777',
  rarity: 'MYTHIC',
  value: 25000,
  traits: ['four_of_kind', 'all_same'],
  tags: ['special'],
  story: 'Four sevens. One of the most recognizable repeated-digit combinations.',
  is_special: true,
  discovery_count: 3,
  duplicate_count: 0,
  owned: true,
  acquired_at: '2026-01-01T00:00:00Z',
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

describe('ResultOverlay', () => {
  it('renders the server result when open', () => {
    render(
      <ResultOverlay
        open
        number={baseNumber}
        rarity="MYTHIC"
        isDuplicate={false}
        isFirstDiscovery
        conversionValue={6250}
        coinsAwarded={0}
        achievements={[]}
        onClose={vi.fn()}
        onShare={vi.fn()}
        onConvert={vi.fn()}
      />,
    );

    expect(screen.getByTestId('result-number')).toHaveTextContent('7777');
    expect(screen.getByText('Mythic')).toBeInTheDocument();
    expect(screen.getByText(/25,000/)).toBeInTheDocument();
    expect(screen.getByText(/Secret Discovered/)).toBeInTheDocument();
  });

  it('offers conversion for duplicates', () => {
    render(
      <ResultOverlay
        open
        number={baseNumber}
        rarity="MYTHIC"
        isDuplicate
        isFirstDiscovery={false}
        conversionValue={6250}
        coinsAwarded={0}
        achievements={[]}
        onClose={vi.fn()}
        onShare={vi.fn()}
        onConvert={vi.fn()}
      />,
    );
    expect(screen.getByText('Duplicate')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Convert to Coins/i })).toBeInTheDocument();
  });

  it('renders nothing when closed', () => {
    render(
      <ResultOverlay
        open={false}
        number={null}
        rarity={null}
        isDuplicate={false}
        isFirstDiscovery={false}
        conversionValue={0}
        coinsAwarded={0}
        achievements={[]}
        onClose={vi.fn()}
        onShare={vi.fn()}
        onConvert={vi.fn()}
      />,
    );
    expect(screen.queryByTestId('result-overlay')).not.toBeInTheDocument();
  });
});

describe('CollectionList', () => {
  it('lists owned numbers with their value', () => {
    render(
      <CollectionList items={[baseNumber]} expanded={null} onToggle={vi.fn()} converting={false} onConvert={vi.fn()} />,
    );
    expect(screen.getByText('7777')).toBeInTheDocument();
    expect(screen.getByText('25,000')).toBeInTheDocument();
  });

  it('expands a row to reveal the conversion action', () => {
    const item = { ...baseNumber, duplicate_count: 2 };
    render(
      <CollectionList items={[item]} expanded={item.number} onToggle={vi.fn()} converting={false} onConvert={vi.fn()} />,
    );
    expect(screen.getByRole('button', { name: /convert duplicate to coins/i })).toBeInTheDocument();
  });
});
