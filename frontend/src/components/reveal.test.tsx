import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { act } from 'react';
import { render as rtlRender, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import userEvent from '@testing-library/user-event';
import Reveal from '@/components/Reveal';
import SimCardVisual from '@/components/SimCardVisual';
import VehiclePlateVisual from '@/components/VehiclePlateVisual';
import { I18nProvider } from '@/i18n';
import { REVEAL_DURATION, revealDuration } from '@/lib/motion';
import {
  plate,
  polVisual,
  rollBalance,
  rollResult,
  ruVisual,
  simPlate,
  uniquePlate,
  usVisual,
} from '@/test/fixtures';

vi.mock('framer-motion', async () => {
  const actual = await vi.importActual<typeof import('framer-motion')>('framer-motion');
  return { ...actual, useReducedMotion: () => false };
});

vi.mock('@/lib/telegram', () => ({
  haptic: vi.fn(),
  hapticSuccess: vi.fn(),
  hapticError: vi.fn(),
  hapticCue: vi.fn(),
  shareToChat: vi.fn(),
}));

const render = (ui: React.ReactElement) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return rtlRender(
    <QueryClientProvider client={client}>
      <I18nProvider>{ui}</I18nProvider>
    </QueryClientProvider>,
  );
};

/**
 * Run a reveal forward past its final stage.
 *
 * The staging is time-based on purpose, so the test waits for the read-out rather than
 * reaching into internal state.
 */
async function settle(ms = REVEAL_DURATION.MYTHIC + 200) {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, ms));
  });
}

describe('Reveal staging', () => {
  beforeEach(() => vi.useRealTimers());
  afterEach(() => vi.restoreAllMocks());

  it('shows nothing without a collectible', () => {
    render(<Reveal card={null} loading={false} onClose={vi.fn()} />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('presents the exact collectible the backend decided, unchanged', async () => {
    const card = plate({ plate_text: 'A777BC 777' });
    render(<Reveal card={card} loading={false} onClose={vi.fn()} />);
    await settle();

    // The printed plate text is the stored text: no client-side remixing.
    expect(screen.getByRole('img', { name: 'A777BC 777' })).toBeInTheDocument();
    expect(screen.getByText(/Mythic/i)).toBeInTheDocument();
  });

  it('moves through its stages and settles on the read-out', async () => {
    render(<Reveal card={plate()} loading={false} onClose={vi.fn()} />);

    // Not settled yet: the read-out is absent while the object is entering.
    expect(screen.queryByText(/Mythic/i)).toBeNull();

    await settle(revealDuration(plate().rarity) + 250);
    expect(screen.getByText(/Mythic/i)).toBeInTheDocument();
  });

  it('can be skipped without changing the result', async () => {
    const user = userEvent.setup();
    render(<Reveal card={plate()} loading={false} onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByRole('button', { name: /skip/i })).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: /skip/i }));

    // The same collectible, just immediately.
    expect(screen.getByRole('img', { name: 'A777BC 777' })).toBeInTheDocument();
    expect(screen.getByText(/Mythic/i)).toBeInTheDocument();
  });

  it('scales its length by rarity without ever skipping the read-out', async () => {
    expect(revealDuration('COMMON')).toBeLessThan(revealDuration('RARE'));
    expect(revealDuration('RARE')).toBeLessThan(revealDuration('LEGENDARY'));
    expect(revealDuration('LEGENDARY')).toBeLessThan(revealDuration('SECRET'));
    // An unknown tier degrades to the common timing rather than to nothing.
    expect(revealDuration('NOPE')).toBe(REVEAL_DURATION.COMMON);
  });

  it('renders a SIM card as a card, with its operator and a synthetic marker', async () => {
    render(<Reveal card={simPlate()} loading={false} onClose={vi.fn()} />);
    await settle();
    // The brand appears on the card itself and again in the read-out line.
    expect(screen.getAllByText('MTS').length).toBeGreaterThan(0);
    expect(screen.getByText(/synthetic/i)).toBeInTheDocument();
  });
});

describe('Reveal actions', () => {
  afterEach(() => vi.restoreAllMocks());

  it('offers ROLL AGAIN as the primary action', async () => {
    const onRollAgain = vi.fn();
    render(
      <Reveal
        card={plate()}
        loading={false}
        onClose={vi.fn()}
        onRollAgain={onRollAgain}
        canRollAgain
      />,
    );
    await settle();
    const again = screen.getByRole('button', { name: /roll again/i });
    again.click();
    expect(onRollAgain).toHaveBeenCalledTimes(1);
  });

  it('disables ROLL AGAIN when no rolls remain', async () => {
    render(
      <Reveal
        card={plate()}
        loading={false}
        onClose={vi.fn()}
        onRollAgain={vi.fn()}
        canRollAgain={false}
      />,
    );
    await settle();
    expect(screen.getByRole('button', { name: /roll again/i })).toBeDisabled();
  });

  it('offers SELL DUPLICATES with the amount when duplicates exist', async () => {
    render(
      <Reveal card={plate()} loading={false} onClose={vi.fn()} onSellDuplicates={vi.fn()} />,
    );
    await settle();
    expect(screen.getByRole('button', { name: /sell duplicates/i })).toBeInTheDocument();
  });

  it('does not offer a sale, and says why, when there are no duplicates', async () => {
    render(
      <Reveal card={uniquePlate()} loading={false} onClose={vi.fn()} onSellDuplicates={vi.fn()} />,
    );
    await settle();
    // The action must not exist at all: it would be a request the backend refuses.
    expect(screen.queryByRole('button', { name: /sell duplicates/i })).toBeNull();
    expect(screen.getByText(/own the only copy/i)).toBeInTheDocument();
  });

  it('never shows a sale action when no handler was supplied', async () => {
    render(<Reveal card={plate()} loading={false} onClose={vi.fn()} />);
    await settle();
    expect(screen.queryByRole('button', { name: /sell duplicates/i })).toBeNull();
  });

  it('marks a first discovery as a status on the card', async () => {
    render(<Reveal card={plate()} loading={false} onClose={vi.fn()} isFirstDiscovery />);
    await settle();
    expect(screen.getByText(/first discovery/i)).toBeInTheDocument();
  });

  it('keeps the reward read-out to one main value', async () => {
    render(<Reveal card={plate()} loading={false} onClose={vi.fn()} />);
    await settle();
    // One number dominates; the collector value stays out of the reveal.
    expect(screen.getByText('+12,500')).toBeInTheDocument();
    expect(screen.getByText('NUMORA')).toBeInTheDocument();
  });
});

describe('VehiclePlateVisual', () => {
  it('draws the country identifier band from the recipe, not a giant flag', () => {
    render(
      <VehiclePlateVisual
        visual={polVisual}
        plateText="AB 12345"
        displaySegments={['AB', '12345']}
        displaySegmentGaps={[false, true]}
        displaySegmentKinds={['letter', 'digit']}
      />,
    );
    const frame = document.querySelector('.plate-frame') as HTMLElement;
    // The EU band with Poland's own code: PL, not a generic EU placeholder.
    const band = frame.querySelector('.plate-band') as HTMLElement;
    expect(band).not.toBeNull();
    expect(band.textContent).toContain('PL');
    expect(band.textContent).not.toContain('🇵🇱');
  });

  it('moves the region into its own compartment on a Russian plate', () => {
    render(
      <VehiclePlateVisual
        visual={ruVisual}
        plateText="A777BC 777"
        displaySegments={['A777BC', '777']}
        displaySegmentGaps={[false, true]}
        displaySegmentKinds={['mixed', 'region']}
        regionCode="777"
      />,
    );
    // The compartment carries the printed RUS legend and the region code, in the order the
    // real format prints them.
    const compartment = document.querySelector('.plate-region-block') as HTMLElement;
    expect(compartment).not.toBeNull();
    expect(compartment.textContent).toContain('RUS');
    expect(compartment.textContent).toContain('777');
    // And the registration itself is not suffixed with the code: on a two-compartment
    // plate the code appears once, in its own compartment.
    expect(document.querySelector('.plate-print')?.textContent).toBe('A777BC');
    expect(compartment.style.boxSizing).toBe('border-box');
    expect(compartment.querySelector('.plate-flag-ru')?.getAttribute('style')).toContain('2.1em');
    // The flag is drawn as vectors, not printed as an emoji.
    expect(compartment.querySelector('.plate-flag-ru')).not.toBeNull();
    expect(compartment.textContent).not.toContain('🇷🇺');
  });

  it('prints the state name as the header on a US plate', () => {
    render(
      <VehiclePlateVisual visual={usVisual} plateText="D431K406" regionName="California" />,
    );
    const header = document.querySelector('.plate-header') as HTMLElement;
    expect(header.textContent).toBe('California');
  });

  it('reserves the recipe-declared region badge area beside the number', () => {
    render(
      <VehiclePlateVisual visual={polVisual} plateText="AB 12345" regionCode="MZ" />,
    );
    const badge = document.querySelector('.plate-region-badge') as HTMLElement;
    const face = document.querySelector('.plate-face') as HTMLElement;
    expect(badge.textContent).toBe('MZ');
    expect(badge.style.right).toBe('0px');
    expect(face.style.paddingRight).toContain('calc(');
  });

  it('keeps all plate families free of decorative mounting circles', () => {
    const { unmount } = rtlRender(<VehiclePlateVisual visual={usVisual} plateText="D431K406" />);
    expect(document.querySelectorAll('.plate-hole')).toHaveLength(0);
    expect(document.querySelectorAll('.plate-bolt')).toHaveLength(0);
    unmount();

    rtlRender(<VehiclePlateVisual visual={ruVisual} plateText="A777BC 777" regionCode="777" />);
    expect(document.querySelectorAll('.plate-bolt')).toHaveLength(0);
    expect(document.querySelectorAll('.plate-hole')).toHaveLength(0);
  });

  it('draws a plate at the proportions its recipe declares', () => {
    render(<VehiclePlateVisual visual={ruVisual} plateText="A777BC 777" />);
    const frame = document.querySelector('.plate-frame') as HTMLElement;
    // 520x112 mm: the object is long and low, which is the whole point.
    expect(frame.style.aspectRatio).toBe(String(ruVisual.aspect));
    expect(frame.style.width).toBe(`${ruVisual.width_mm}px`);
    expect(ruVisual.aspect).toBeGreaterThan(4);
  });

  it('prints the exact stored text, groups and gaps included', () => {
    render(
      <VehiclePlateVisual
        visual={polVisual}
        plateText="AB 12345"
        displaySegments={['AB', '12345']}
        displaySegmentGaps={[false, true]}
        displaySegmentKinds={['letter', 'digit']}
      />,
    );
    // The printed object reads back as exactly `plate_text`, spaces included, so the
    // value a player sees, copies and searches are the same string.
    const print = document.querySelector('.plate-print') as HTMLElement;
    expect(print.textContent).toBe('AB 12345');
    // The whole plate, including any compartment, still carries the full value.
    expect(document.querySelector('.plate-frame')?.getAttribute('aria-label')).toBe('AB 12345');
  });

  it('falls back to character runs when grouped segments are absent', () => {
    render(<VehiclePlateVisual visual={ruVisual} plateText="AB 123" />);
    const print = document.querySelector('.plate-print') as HTMLElement;
    // Never an empty plate: the stored value is always what gets printed.
    expect(print.textContent?.replace(/\s+/g, '')).toBe('AB123');
  });
});

describe('SimCardVisual', () => {
  it('shows the real operator brand, series and edition', () => {
    const sim = simPlate();
    render(<SimCardVisual details={sim.details} />);
    expect(screen.getByText('MTS')).toBeInTheDocument();
    expect(screen.getByText('N-42')).toBeInTheDocument();
    expect(screen.getByText('APEX')).toBeInTheDocument();
  });

  it('always states that the number is synthetic', () => {
    const sim = simPlate();
    render(<SimCardVisual details={sim.details} />);
    expect(screen.getByText(/synthetic · game collectible/i)).toBeInTheDocument();
  });

  it('labels a documented game brand as such', () => {
    const sim = simPlate({
      details: {
        ...simPlate().details!,
        operator: 'PER NOVA',
        operator_is_real: false,
      },
    });
    render(<SimCardVisual details={sim.details} />);
    expect(screen.getByText(/game brand/i)).toBeInTheDocument();
  });
});

describe('roll payload contract', () => {
  it('carries the economy and the next objective so the client owns neither', () => {
    const result = rollResult({ rolls: rollBalance({ rolls_remaining: 12, normal_rolls: 12 }) });
    expect(result.rolls?.normal_rolls).toBe(12);
    expect(result.rolls?.regen_minutes).toBe(45);
    expect(result.next_target?.code).toBeTruthy();
  });
});
