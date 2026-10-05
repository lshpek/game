import { describe, expect, it, vi } from 'vitest';
import { render as rtlRender, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { CollectionList } from '@/components/CollectionList';
import { RarityBadge, TraitChip } from '@/components/RarityBadge';
import RollButton from '@/components/RollButton';
import { RollBalanceLine, formatCountdown } from '@/components/RollEconomy';
import { ValueCounter } from '@/components/ValueCounter';
import { I18nProvider } from '@/i18n';
import { plate, rollBalance, uniquePlate } from '@/test/fixtures';

/** Every component reads strings from context, so tests need the provider. */
const render = (ui: ReactElement) => rtlRender(<I18nProvider>{ui}</I18nProvider>);

describe('RarityBadge', () => {
  it('renders the human label', () => {
    render(<RarityBadge rarity="LEGENDARY" />);
    expect(screen.getByText('Legendary')).toBeInTheDocument();
  });

  it('falls back to COMMON for unknown values', () => {
    render(<RarityBadge rarity="NOT_A_RARITY" />);
    expect(screen.getByText('Common')).toBeInTheDocument();
  });

  it('keeps the visual hierarchy calm for COMMON and rich for the top tiers', () => {
    const { unmount } = rtlRender(
      <I18nProvider>
        <RarityBadge rarity="COMMON" />
      </I18nProvider>,
    );
    // No glow, no halo: an ordinary find must not look like an event.
    expect(screen.getByText('Common').style.boxShadow).toBe('');

    unmount();
    render(<RarityBadge rarity="MYTHIC" />);
    expect(screen.getByText('Mythic').style.boxShadow).toContain('#f43f5e');
  });
});

describe('TraitChip', () => {
  it('keeps the trait code for testing and analytics', () => {
    render(<TraitChip code="palindrome" label="Palindrome" />);
    expect(screen.getByText('Palindrome')).toHaveAttribute('data-trait', 'palindrome');
  });
});

describe('RollButton', () => {
  const rolls = rollBalance();

  it('fires the callback when rolls are available', () => {
    const onRoll = vi.fn();
    render(<RollButton rolls={rolls} onRoll={onRoll} />);
    screen.getByRole('button', { name: /roll/i }).click();
    expect(onRoll).toHaveBeenCalledTimes(1);
  });

  it('is disabled when no rolls remain', () => {
    const onRoll = vi.fn();
    render(<RollButton rolls={rollBalance({ rolls_remaining: 0, normal_rolls: 0 })} onRoll={onRoll} />);
    expect(screen.getByRole('button', { name: /no rolls/i })).toBeDisabled();
  });

  it('is disabled while a roll is in flight, so a double tap cannot pay twice', () => {
    render(<RollButton rolls={rolls} onRoll={vi.fn()} rolling />);
    expect(screen.getByRole('button', { name: /hunting/i })).toBeDisabled();
  });

  it('announces the remaining count to assistive tech', () => {
    render(<RollButton rolls={rollBalance({ rolls_remaining: 7, normal_rolls: 7 })} onRoll={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Roll. 7 available.' })).toBeInTheDocument();
  });

  it('shows the refill countdown when a passive roll is pending', () => {
    render(
      <RollButton
        rolls={rollBalance({
          rolls_remaining: 3,
          normal_rolls: 3,
          next_roll_at: new Date(Date.now() + 32 * 60_000).toISOString(),
          seconds_to_next_roll: 32 * 60,
        })}
        onRoll={vi.fn()}
      />,
    );
    expect(screen.getByText(/32m/)).toBeInTheDocument();
  });
});

describe('RollBalanceLine', () => {
  it('shows the bank, the countdown and the bonus separately', () => {
    const future = new Date(Date.now() + 20 * 60_000).toISOString();
    render(
      <RollBalanceLine
        rolls={rollBalance({
          rolls_remaining: 21,
          normal_rolls: 18,
          bonus_rolls: 3,
          next_roll_at: future,
          seconds_to_next_roll: 20 * 60,
        })}
      />,
    );
    expect(screen.getByText('21 rolls')).toBeInTheDocument();
    expect(screen.getByText('+3 bonus')).toBeInTheDocument();
    expect(screen.getByText(/in 20m/)).toBeInTheDocument();
  });

  it('formats countdowns compactly', () => {
    expect(formatCountdown(0)).toBe('0:00');
    expect(formatCountdown(7)).toBe('0:07');
    expect(formatCountdown(32 * 60)).toBe('32m');
    expect(formatCountdown(3660)).toBe('1h 01m');
  });
});

describe('ValueCounter', () => {
  it('counts up to the final value', async () => {
    render(<ValueCounter value={1234} suffix=" NUMORA" />);
    expect(await screen.findByText('1,234 NUMORA', {}, { timeout: 3000 })).toBeInTheDocument();
  });
});

describe('CollectionList', () => {
  it('renders each item as its physical object, with rarity and duplicates', () => {
    render(
      <CollectionList items={[plate()]} expanded={null} onToggle={vi.fn()} selling={false} onSell={vi.fn()} />,
    );
    const row = screen.getByTestId('collection-row');
    // The object itself is the lead element, not a text placeholder.
    expect(row.querySelector('.plate-frame')).not.toBeNull();
    expect(screen.getByText('Mythic')).toBeInTheDocument();
    expect(screen.getByText('+12,500')).toBeInTheDocument();
    expect(screen.getByText(/×2 duplicates/)).toBeInTheDocument();
  });

  it('offers a dealer sale only when duplicates exist', () => {
    const { unmount } = rtlRender(
      <I18nProvider>
        <CollectionList
          items={[uniquePlate()]}
          expanded={777}
          onToggle={vi.fn()}
          selling={false}
          onSell={vi.fn()}
        />
      </I18nProvider>,
    );
    expect(screen.queryByRole('button', { name: /sell duplicate copies/i })).toBeNull();
    unmount();

    render(
      <CollectionList
        items={[plate()]}
        expanded={777}
        onToggle={vi.fn()}
        selling={false}
        onSell={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /sell duplicate copies/i })).toBeInTheDocument();
  });

  it('shows the provider brand on a SIM card', () => {
    const sim = plate({
      kind: 'SIM_CARD',
      plate_type: 'SIM',
      details: {
        operator_code: 'mts',
        operator: 'MTS',
        operator_local: 'МТС',
        operator_is_real: true,
        operator_visual: 'waveform',
        operator_accent: '#ff0032',
        rarity_modifier: 1.06,
        value_modifier: 1.1,
        series: 'N-42',
        edition: 'APEX',
        synthetic_number: '+7 900 123 45 67',
        calling_code: '+7',
        synthetic: true,
      },
    });
    render(
      <CollectionList items={[sim]} expanded={null} onToggle={vi.fn()} selling={false} onSell={vi.fn()} />,
    );
    expect(screen.getAllByText(/MTS/).length).toBeGreaterThan(0);
  });
});