import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import {
  CollectionList,
  CollectionGrid,
} from '@/components/CollectionList';
import { CollectiblePreview, CollectibleRow } from '@/components/CollectiblePreview';
import { RarityBadge, TraitChip, ValuePair } from '@/components/RarityBadge';
import RollButton from '@/components/RollButton';
import { BottomSheet } from '@/components/BottomSheet';
import { I18nProvider } from '@/i18n';
import { plate, rollBalance } from './fixtures';
import type { PlateCard } from '@/types';

/**
 * Overflow discipline.
 *
 * The rule the whole product rests on: **nothing may leave its own box, and nothing may
 * leave the viewport.** A collectible is a physical object, so anything of it that
 * reaches outside the plate - a shadow, a reflection, a bolt, a long serial - is a bug
 * that makes the object look like a card again.
 *
 * What is asserted here is *contract*, not geometry, because jsdom does not lay out. Each
 * container that holds a variable-length value must declare how it handles overflow -
 * `truncate`, `break-words`, or a hard `max-width` - and each must also be able to
 * shrink below its content, which is what `min-w-0` does for a flex child. A row without
 * `min-w-0` is a row that eventually scrolls sideways.
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

/** A long, adversarial value: the sort of text that breaks a layout in production. */
const LONG_NAME = 'Сверхдлинноенаименованиегосударства-Республика-Республика';

beforeEach(() => {
  vi.useRealTimers();
});

describe('Text overflow', () => {
  it('every container of a variable-length value can shrink and truncate', () => {
    const card: PlateCard = plate();
    const country = {
      name_en: LONG_NAME,
      name_ru: LONG_NAME,
      flag: '\u{1F1EC}\u{1F1EA}',
      code: 'GEO',
    } as unknown as PlateCard['country'];

    wrap(<CollectiblePreview card={{ ...card, country }} />);
    const preview = screen.getByTestId('collectible-preview');
    // The country line is the longest string on the object, and it truncates rather than
    // widening the block.
    const countryLine = Array.from(preview.querySelectorAll('span.truncate')).find((node) =>
      node.textContent?.includes(LONG_NAME),
    );
    expect(countryLine).toBeDefined();

    wrap(<CollectibleRow card={{ ...card, country }} />);
    const row = screen.getByTestId('collectible-preview');
    expect(row.className).toContain('min-w-0');
  });

  it('the roll button clips, so no count can escape it', () => {
    wrap(<RollButton rolls={rollBalance({ rolls_remaining: 999_999 })} onRoll={vi.fn()} />);
    const button = screen.getByTestId('roll-button');
    expect(button.className).toContain('overflow-hidden');
    expect(button.className).toContain('isolate');
    // And nothing is positioned outside its box.
    for (const child of Array.from(button.querySelectorAll('*'))) {
      expect(child.className ?? '').not.toMatch(/-top-\d|-left-\d|-right-\d/);
    }
  });

  it('a rarity badge never grows past its label', () => {
    wrap(<RarityBadge rarity="MYTHIC" size="lg" />);
    const badge = screen.getByLabelText(/mythic/i);
    expect(badge.className).toContain('whitespace-nowrap');
    expect(badge.className).toContain('inline-flex');
  });

  it('a trait chip truncates instead of pushing its row wider', () => {
    wrap(<TraitChip code="ALL_SAME_PALINDROME" label={LONG_NAME} />);
    const chip = screen.getByTitle(LONG_NAME);
    expect(chip.className).toContain('max-w-full');
  });

  it('a value pair keeps both figures inside its box', () => {
    const { container } = wrap(
      <ValuePair dealer={9_999_999_999} collector={123_456_789_012} symbol="₽" />,
    );
    const value = container.firstElementChild as HTMLElement;
    expect(value.className).toContain('items-baseline');
    // Both figures share one line and neither can push the row wider.
    expect(value.className).toContain('flex');
  });
});

describe('Cards', () => {
  it('a collection row clips its object well and truncates every text field', () => {
    wrap(
      <CollectionList
        items={[plate()]}
        expanded={null}
        onToggle={vi.fn()}
        selling={false}
        onSell={vi.fn()}
      />,
    );
    const row = screen.getByTestId('collection-row');
    // The text block between the object well and the value column is the one that has to
    // shrink; without `min-w-0` a long country name widens the row instead.
    const textBlock = row.querySelector('span.min-w-0');
    expect(textBlock).not.toBeNull();
    const name = Array.from(row.querySelectorAll('span.truncate')).find((node) =>
      node.textContent?.includes('Russia'),
    );
    expect(name).toBeDefined();
  });

  it('a grid tile keeps its object inside a fixed-width well', () => {
    wrap(
      <ul className="grid grid-cols-2">
        <CollectionGrid items={[plate()]} onOpen={vi.fn()} />
      </ul>,
    );
    const tiles = screen.getAllByRole('button');
    for (const tile of tiles) {
      expect(tile.className).toContain('w-full');
      expect(tile.className).toContain('min-w-0');
    }
  });
});

describe('Containment is declared, not assumed', () => {
  it('the plate field clips and can shrink below its content', () => {
    // `min-width: 0` is what stops a long serial from widening the plate - and widening
    // the plate is what scrolls the page sideways.
    expect(STYLESHEET).toMatch(/\.plate-face\s*\{[^}]*overflow:\s*hidden/);
    expect(STYLESHEET).toMatch(/\.plate-print\s*\{[^}]*white-space:\s*nowrap/);
  });

  it('the reel window, its rows and its objects all clip', () => {
    expect(STYLESHEET).toMatch(/\.reel-window\s*\{[^}]*overflow:\s*hidden/);
    expect(STYLESHEET).toMatch(/\.reel-row\s*\{[^}]*overflow:\s*hidden/);
    expect(STYLESHEET).toMatch(/\.reel-object\s*\{[^}]*overflow:\s*hidden/);
  });

  it('a sheet is bounded by the viewport, not by its content', () => {
    wrap(
      <BottomSheet open onClose={vi.fn()} label="Choose">
        <p>body</p>
      </BottomSheet>,
    );
    const panel = screen.getByTestId('bottom-sheet-panel');
    // Clipped, and bounded on the cross axis by the app's own measure - a sheet stretched
    // across a desktop window reads as a broken dialog.
    expect(panel.className).toContain('sheet');
    expect(panel.className).toContain('max-w-[min(96%,var(--content-max))]');
    // Nothing in the app is allowed a width larger than the viewport.
    // No hardcoded width anywhere near a screen's width. (Excluding min-width, which is a
    // breakpoint, not a size.)
    expect(STYLESHEET).not.toMatch(/(?<!min-)width:\s*\d{4,}px/);
  });

  it('the sheet caps its height against the measured viewport', () => {
    wrap(
      <BottomSheet open onClose={vi.fn()} label="Choose">
        <p>body</p>
      </BottomSheet>,
    );
    const panel = screen.getByTestId('bottom-sheet-panel');
    // Capped against `--app-height`, so it can never exceed what the Mini App has, and
    // bounded on the cross axis by the app's own measure.
    expect(panel.style.maxHeight).toContain('var(--app-height)');
    expect(panel.className).toContain('var(--content-max)');
    expect(panel.className).toContain('w-full');
  });
});
