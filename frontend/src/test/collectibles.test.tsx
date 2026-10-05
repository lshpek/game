import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import CollectibleVisualFrame from '@/components/CollectibleVisualFrame';
import RollReel from '@/components/RollReel';
import SimCardVisual from '@/components/SimCardVisual';
import VehiclePlateVisual from '@/components/VehiclePlateVisual';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { I18nProvider } from '@/i18n';
import { polVisual, ruVisual, usVisual } from './fixtures';
import type { PlateVisual, ReelFrame } from '@/types';

/**
 * The physical collectibles, the reel, and containment.
 *
 * These are the assertions that a visual review cannot make and that a screenshot hides:
 * that a Georgian plate prints Latin letters in its blue block, that a very long serial
 * shrinks instead of overflowing, that a reel frame is byte-for-byte the same recipe the
 * real card carries, and that not one element can escape its own box.
 */

/** The Georgian recipe, as the backend sends it. */
const geVisual: PlateVisual = {
  ...ruVisual,
  theme: 'ge',
  plate_family: 'ge',
  width_mm: 520,
  height_mm: 112,
  aspect: 4.643,
  background: '#ffffff',
  background_alt: '#f3f6fb',
  border: '#0f172a',
  text: '#111111',
  muted: '#5b6572',
  accent: '#ff4b33',
  font_stack_key: 'condensed',
  letter_spacing: '0.05em',
  letter_scale: 0.96,
  group_gap: '0.55em',
  band_position: 'left',
  band_color: '#1c3f94',
  band_width: 0.14,
  band_text: 'GE',
  band_text_source: 'static',
  band_text_color: '#ffffff',
  band_stars: false,
  band_flag: 'ge',
  header_source: 'none',
  region_position: 'none',
  region_style: 'none',
  region_width: 0.0,
  region_flag: false,
  region_text: '',
  mount: 'holes',
  sheen: 0.5,
  relief: 0.32,
  grain: 0.14,
  emblem: '',
};

/** A frame, as the server sends one. */
const frame = (over: Partial<ReelFrame> = {}): ReelFrame => ({
  plate_text: 'AB-123-CD',
  display_segments: ['AB', '123', 'CD'],
  display_segment_gaps: [false, true, true],
  display_segment_kinds: ['letter', 'digit', 'letter'],
  visual: geVisual,
  kind: 'VEHICLE_PLATE',
  country_code: 'GEO',
  country_name_en: 'Georgia',
  country_flag: '🇬🇪',
  ...over,
});

const LONG_TEXT = 'ABCDE 12345 67890 XYZ';

/**
 * The stylesheet, read as text.
 *
 * Containment rules are only observable here: a class name can be renamed and the
 * guarantee silently lost, and jsdom does not compute `overflow` from a stylesheet.
 */
const STYLESHEET = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <I18nProvider>{ui}</I18nProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.useRealTimers();
});

describe('The Russian plate', () => {
  it('is drawn at the proportions GOST R 50577-2018 declares', () => {
    wrap(<VehiclePlateVisual visual={ruVisual} plateText="A777BC 777" regionCode="777" />);
    const frameEl = document.querySelector('.plate-frame') as HTMLElement;
    // 520x112 mm. Long and low - the single clearest tell that it is a plate.
    expect(ruVisual.width_mm).toBe(520);
    expect(ruVisual.height_mm).toBe(112);
    expect(ruVisual.aspect).toBeGreaterThan(4.6);
    expect(frameEl.style.aspectRatio).toBe(String(ruVisual.aspect));
  });

  it('puts the region in its own compartment, once, with the tricolour above it', () => {
    wrap(
      <VehiclePlateVisual
        visual={ruVisual}
        plateText="A777BC 777"
        displaySegments={['A777BC', '777']}
        displaySegmentGaps={[false, true]}
        displaySegmentKinds={['mixed', 'region']}
        regionCode="777"
      />,
    );
    const compartment = document.querySelector('.plate-region-block') as HTMLElement;
    expect(compartment.textContent).toContain('RUS');
    expect(compartment.textContent).toContain('777');
    // The flag is drawn as vectors, and the registration is not suffixed with the code.
    expect(compartment.querySelector('.plate-flag-ru')).not.toBeNull();
    expect(document.querySelector('.plate-print')?.textContent).toBe('A777BC');
  });
});

describe('The Georgian plate', () => {
  it('prints Latin letters in a blue block on the left', () => {
    wrap(<VehiclePlateVisual visual={geVisual} plateText="AB-123-CD" />);
    const band = document.querySelector('.plate-band') as HTMLElement;
    expect(band).not.toBeNull();
    expect(band.textContent).toContain('GE');
    // The flag is drawn, not pasted as an emoji.
    expect(band.querySelector('.plate-flag-ge')).not.toBeNull();
    expect(band.textContent).not.toContain('🇬🇪');
    // And it is on the left, which is where the real format puts it.
    const face = document.querySelector('.plate-face') as HTMLElement;
    expect(face.firstElementChild?.className).toContain('plate-band');
  });

  it('never prints Georgian script', () => {
    wrap(<VehiclePlateVisual visual={geVisual} plateText="AB-123-CD" />);
    const text = document.querySelector('.plate-frame')?.textContent ?? '';
    // Georgian letters live in the U+10A0..U+10FF block.
    expect(/[\u{10A0}-\u{10FF}]/u.test(text)).toBe(false);
    expect(text).toContain('AB-123-CD');
  });

  it('uses pressed screw holes, not studded bolts', () => {
    wrap(<VehiclePlateVisual visual={geVisual} plateText="AB-123-CD" />);
    expect(document.querySelectorAll('.plate-hole')).toHaveLength(2);
    expect(document.querySelectorAll('.plate-bolt')).toHaveLength(0);
  });

  it('has no separate region compartment', () => {
    // The third group of a Georgian number is part of the serial, not a registration.
    wrap(<VehiclePlateVisual visual={geVisual} plateText="AB-123-CD" />);
    expect(document.querySelector('.plate-region-block')).toBeNull();
    expect(geVisual.region_position).toBe('none');
  });
});

describe('Physical containment', () => {
  it('keeps a very long serial inside the plate instead of spilling out of it', () => {
    wrap(<VehiclePlateVisual visual={usVisual} plateText={LONG_TEXT} />);
    const face = document.querySelector('.plate-face') as HTMLElement;
    // The field clips, and the type is sized in container units so it shrinks to fit.
    expect(face.style.overflow).toBe('hidden');
    // `min-width: 0` is what lets a flex child shrink below its content width, which is
    // the difference between a shrinking plate and a page that scrolls sideways.
    expect(face.style.minWidth).toMatch(/^0(px)?$/);
    // The type is a clamp against the container width, never a fixed pixel size, which
    // is what makes it scale with the plate instead of with the screen.
    const print = document.querySelector('.plate-print') as HTMLElement;
    expect(print.style.fontSize).toContain('cqw');
  });

  it('never renders wider than the space it was given', () => {
    wrap(<VehiclePlateVisual visual={polVisual} plateText={LONG_TEXT} scale={1} />);
    const frameEl = document.querySelector('.plate-frame') as HTMLElement;
    // `max-width: 100%` is the only thing between a 520mm plate and a 320px screen.
    expect(frameEl.style.maxWidth).toBe('100%');
    expect(frameEl.style.width).toBe('520px');
  });

  it('keeps a SIM inside its own card', () => {
    wrap(
      <SimCardVisual
        details={{
          operator_code: 'mts',
          operator: 'MTS',
          operator_local: 'МТС',
          operator_is_real: true,
          operator_visual: 'blocks',
          operator_accent: '#ff0000',
          rarity_modifier: 1.1,
          value_modifier: 1,
          series: 'S1',
          edition: 'E1',
          synthetic_number: '+7 999 123 45 67',
          calling_code: '+7',
          synthetic: true,
        }}
        rarity="COMMON"
      />,
    );
    const card = document.querySelector('.sim-body') as HTMLElement;
    // Containment comes from the stylesheet, so assert the rule itself rather than a
    // class name - a class can be renamed and the guarantee silently lost.
    expect(STYLESHEET).toMatch(/\.sim-body\s*\{[^}]*overflow:\s*hidden/);
    expect(STYLESHEET).toMatch(/\.reel-window\s*\{[^}]*overflow:\s*hidden/);
    expect(STYLESHEET).toMatch(/\.reel-row\s*\{[^}]*overflow:\s*hidden/);
    // The physical ID-1 ratio, and every element inside it.
    expect(card.querySelector('.sim-contact')).not.toBeNull();
    expect(card.querySelector('.sim-pad')).not.toBeNull();
    // The clipped corner is a real bevel, not a rounded rectangle.
    expect(card.querySelector('.sim-notch')).not.toBeNull();
    // And the honesty marker is on the card, not only in the UI around it.
    expect(card.textContent).toMatch(/synthetic/i);
  });

  it('shows the reel window as a clipped box whose height scales with the viewport', () => {
    wrap(
      <RollReel
        frames={[frame(), frame({ plate_text: 'EF-456-GH' })]}
        final={<div data-testid="final">final</div>}
        finalLabel="AB-123-CD"
        settled={false}
      />,
    );
    const window = screen.getByTestId('reel-window');
    // Containment is asserted by class, because that is what the stylesheet guarantees;
    // `overflow: hidden` cannot be observed reliably in jsdom.
    expect(window.className).toContain('reel-window');
    // The height is a viewport-relative clamp rather than a fixed pixel count: a fixed
    // 132px row pushed the button and the result off a landscape screen, where the whole
    // app can be 360px tall.
    expect(window.style.height).toBe('var(--reel-row)');
    expect(STYLESHEET).toMatch(/--reel-row:\s*clamp\(/);
  });
});

describe('The roll reel', () => {
  it('renders many frames, each a full collectible object', () => {
    const frames = Array.from({ length: 26 }, (_, index) =>
      frame({ plate_text: `AB-${index}23-CD`, country_code: index % 2 ? 'RUS' : 'GEO' }),
    );
    wrap(
      <RollReel
        frames={frames}
        final={<div data-testid="final">final</div>}
        finalLabel="AB-123-CD"
        settled={false}
      />,
    );
    expect(screen.getAllByTestId('reel-frame')).toHaveLength(26);
    // Each frame is a physical object with its country's recipe, not a line of text.
    const frameEls = screen.getAllByTestId('reel-frame');
    expect(frameEls[0]?.querySelector('.plate-frame')).not.toBeNull();
    expect(frameEls[1]?.dataset.country).toBe('RUS');
  });

  it('renders a SIM frame as a physical card, not a plate', () => {
    wrap(
      <RollReel
        frames={[frame({ kind: 'SIM_CARD', plate_text: '+7 999 123 45 67' })]}
        final={<div data-testid="final">final</div>}
        finalLabel="final"
        settled={false}
      />,
    );
    expect(document.querySelector('.sim-body')).not.toBeNull();
    expect(document.querySelector('.plate-frame')).toBeNull();
  });

  it('shows the real result only after the strip has settled', () => {
    vi.useFakeTimers();
    const frames = Array.from({ length: 26 }, (_, index) => frame({ plate_text: `AB-${index}23-CD` }));
    wrap(
      <RollReel
        frames={frames}
        final={<div data-testid="final">the real result</div>}
        finalLabel="AB-123-CD"
        settled={false}
      />,
    );
    // Mid-scroll: the strip is up, the answer is not.
    expect(screen.queryByTestId('final')).toBeNull();
    expect(screen.getAllByTestId('reel-frame').length).toBeGreaterThan(0);

    act(() => {
      vi.advanceTimersByTime(2600);
    });

    // Settled: the strip is gone and the answer is the only object on screen.
    expect(screen.getByTestId('final')).toBeInTheDocument();
    expect(screen.queryAllByTestId('reel-frame')).toHaveLength(0);
    vi.useRealTimers();
  });

  it('never shows a frame as the answer', () => {
    // The reel settles on the real card, which arrives separately. A frame is a picture.
    const frames = Array.from({ length: 26 }, (_, index) => frame({ plate_text: `XX-${index}23-YY` }));
    wrap(
      <RollReel
        frames={frames}
        final={<div data-testid="final">A777BC 777</div>}
        finalLabel="A777BC 777"
        settled
      />,
    );
    expect(screen.getByTestId('final').textContent).toBe('A777BC 777');
    expect(screen.queryByTestId('reel-frame')).toBeNull();
  });

  it('renders the result directly when there are no frames', () => {
    wrap(
      <RollReel
        frames={[]}
        final={<div data-testid="final">only the result</div>}
        finalLabel="result"
        settled
      />,
    );
    expect(screen.getByTestId('final')).toBeInTheDocument();
    expect(screen.queryByTestId('reel-frame')).toBeNull();
  });

  it('coerces an unknown segment kind instead of throwing inside the animation', () => {
    // The reel payload is off-the-wire input. Twenty-six rows must not crash on one odd
    // value.
    wrap(
      <CollectibleVisualFrame
        visual={geVisual}
        plateText="AB-123-CD"
        displaySegments={['AB', '123', 'CD']}
        displaySegmentGaps={[false, true, true]}
        displaySegmentKinds={['letter', 'NOT_A_KIND', 'letter']}
        kind="VEHICLE_PLATE"
      />,
    );
    expect(document.querySelector('.plate-frame')?.textContent).toContain('AB');
  });

  it('marks a decorative frame as presentational', () => {
    // Twenty-six frames in a scrolling strip must not be announced as twenty-six finds.
    wrap(
      <CollectibleVisualFrame
        visual={geVisual}
        plateText="AB-123-CD"
        displaySegments={['AB', '123', 'CD']}
        displaySegmentGaps={[false, true, true]}
        displaySegmentKinds={['letter', 'digit', 'letter']}
        kind="VEHICLE_PLATE"
      />,
    );
    const frameEl = document.querySelector('.plate-frame') as HTMLElement;
    expect(frameEl.getAttribute('role')).toBe('presentation');
    expect(frameEl.getAttribute('aria-label')).toBeNull();
  });
});

describe('Collectible kinds', () => {
  it('renders a real card as whichever physical object its kind names', () => {
    // The kind is the server's field, and it decides the object. A SIM collectible is a
    // card; there is no third kind and no phone-number object.
    wrap(
      <CollectibleVisualFrame
        visual={geVisual}
        plateText="+7 999 123 45 67"
        displaySegments={['+7', '999', '123', '45', '67']}
        displaySegmentGaps={[false, true, true, true, true]}
        displaySegmentKinds={['mark', 'digit', 'digit', 'digit', 'digit']}
        kind="SIM_CARD"
      />,
    );
    expect(document.querySelector('.sim-body')).not.toBeNull();
    expect(document.querySelector('.plate-frame')).toBeNull();
  });
});
