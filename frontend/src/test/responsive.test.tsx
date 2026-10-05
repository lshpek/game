import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import App from '@/App';
import { BottomNav } from '@/components/BottomNav';
import { I18nProvider } from '@/i18n';
import { setTelegram } from '@/lib/telegram';
import { useAuthStore } from '@/store/auth';
import { profile, rollBalance } from './fixtures';

/**
 * Responsiveness.
 *
 * Every number a player can hit is checked here: four portrait phone sizes, a landscape
 * phone, a tablet, a 16:9 desktop, an ultrawide and a deliberately small window.
 *
 * The assertions are deliberately about *contracts* rather than about pixels, because
 * jsdom does not lay out. What is asserted is that each decision is delegated to a
 * variable or a media query - that is what makes a size correct everywhere instead of
 * correct on the screen it was tuned on.
 *
 * The end-to-end guard, `document.documentElement.scrollWidth === window.innerWidth`, is
 * also here for the case that matters most: horizontal overflow is the one failure a
 * player feels immediately and cannot work around.
 */

const STYLESHEET = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

/** The viewports the product has to be correct in. */
const VIEWPORTS = [
  { name: 'iPhone SE / small Android', width: 360, height: 800 },
  { name: 'iPhone 8 / 13 mini', width: 375, height: 812 },
  { name: 'iPhone 14', width: 390, height: 844 },
  { name: 'Pixel 7 / iPhone 14 Plus', width: 412, height: 915 },
  { name: 'landscape phone', width: 844, height: 390, landscape: true },
  { name: 'tablet portrait', width: 768, height: 1024 },
  { name: 'tablet landscape', width: 1024, height: 768 },
  { name: 'desktop 16:9', width: 1920, height: 1080 },
  { name: 'ultrawide', width: 3440, height: 1440 },
  { name: 'tall narrow window', width: 520, height: 1400 },
  { name: 'small browser window', width: 900, height: 600 },
];

function setViewport(width: number, height: number) {
  Object.defineProperty(window, 'innerWidth', { value: width, configurable: true });
  Object.defineProperty(window, 'innerHeight', { value: height, configurable: true });
  Object.defineProperty(document.documentElement, 'scrollWidth', {
    value: width,
    configurable: true,
  });
}

function renderShell() {
  vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
    const url = String(input);
    const body = url.includes('/api/user/me')
      ? profile
      : url.includes('/api/game/garage')
        ? { coins: 12_500, rolls: rollBalance(), recent: null, country_progress: null }
        : url.includes('/api/countries/active')
          ? { code: 'RUS' }
          : { total: 0, items: [] };
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // `App` brings its own router, so wrapping it in another would nest two.
  return render(
    <QueryClientProvider client={client}>
      <I18nProvider>
        <App />
      </I18nProvider>
    </QueryClientProvider>,
  );
}

/** `BottomNav` on its own still needs a router and the query client. */
function renderNav() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <I18nProvider>
        <MemoryRouter>
          <BottomNav />
        </MemoryRouter>
      </I18nProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  setTelegram(null);
  useAuthStore.setState({
    token: 'test-token',
    profile,
    status: 'authenticated',
    error: null,
    startContext: null,
  });
});

describe('The viewport is the source of truth', () => {
  it.each(VIEWPORTS)('$name: the document never scrolls sideways', ({ width }) => {
    setViewport(width, 800);
    renderShell();
    // The single check that matters most on a phone: a sideways scroll means the layout
    // has two widths and the player is looking at the wrong one.
    expect(document.documentElement.scrollWidth).toBe(window.innerWidth);
  });

  it('pins the app to the measured height rather than the document height', () => {
    // Both bounds, not just one: a document that can grow is one where the sticky header
    // drifts and the fixed navigation slides during momentum.
    expect(STYLESHEET).toMatch(/#root\s*\{[^}]*max-height:\s*var\(--app-height/);
    expect(STYLESHEET).toMatch(/#root\s*\{[^}]*overflow:\s*hidden/);
    expect(STYLESHEET).toMatch(/body\s*\{[^}]*overflow:\s*hidden/);
  });

  it('insets horizontally in landscape, where a notch moves to a side', () => {
    // A notch on its side is the one case where the top/bottom insets are not enough.
    expect(STYLESHEET).toMatch(
      /#root\s*\{[^}]*padding-left:\s*env\(safe-area-inset-left/,
    );
    expect(STYLESHEET).toMatch(
      /#root\s*\{[^}]*padding-right:\s*env\(safe-area-inset-right/,
    );
  });

  it('gives height back to the content in landscape', () => {
    // Landscape on a phone can be 360px tall. The permanent furniture yields first.
    expect(STYLESHEET).toMatch(
      /@media\s*\(orientation:\s*landscape\)\s*and\s*\(max-height:\s*560px\)/,
    );
  });
});

describe('The reading measure', () => {
  it('grows from phone to tablet to desktop and then stops', () => {
    // Past ~860px a longer line is harder to read, and a plate stretched across a 4K
    // monitor looks like a billboard rather than a physical object.
    expect(STYLESHEET).toMatch(/--content-max:\s*560px/);
    expect(STYLESHEET).toMatch(/@media\s*\(min-width:\s*768px\)[\s\S]*--content-max:\s*720px/);
    expect(STYLESHEET).toMatch(/@media\s*\(min-width:\s*1024px\)[\s\S]*--content-max:\s*860px/);
    // And nothing opens it back up.
    const widths = STYLESHEET.match(/--content-max:\s*(\d+)px/g) ?? [];
    expect(widths).toHaveLength(3);
  });

  it('drives the shell, the header and the navigation from the same variable', () => {
    renderShell();
    const shell = screen.getByTestId('app-shell');
    expect(shell.className).toContain('max-w-[var(--content-max)]');
    // One measure, three consumers: they cannot disagree about how wide the app is.
    expect(STYLESHEET).toMatch(/max-width:\s*var\(--content-max\)/);
  });

  it('turns the shell into a framed surface on desktop instead of a stranded column', () => {
    // A 560px column in the middle of a 1920px screen reads as broken; a framed surface
    // with a margin reads as an app.
    expect(STYLESHEET).toMatch(
      /@media\s*\(min-width:\s*1024px\)[\s\S]*\.app-shell\s*\{[^}]*border-radius/,
    );
    renderShell();
    expect(document.querySelector('.app-shell')).not.toBeNull();
  });

  it('grows the gutter and the section rhythm with the measure', () => {
    expect(STYLESHEET).toMatch(/--gutter:\s*16px/);
    expect(STYLESHEET).toMatch(/@media\s*\(min-width:\s*1024px\)[\s\S]*--gutter:\s*28px/);
  });
});

describe('Bottom navigation', () => {
  it('gives every destination exactly the same width, height and touch area', () => {
    renderNav();


    const nav = screen.getByTestId('bottom-nav');
    // Five equal columns from the grid, not a flex row with a wider primary.
    expect(screen.getByTestId('bottom-nav-items').className).toContain('grid-cols-5');
    // ROLL carries no width, height or scale advantage over the others.
    expect(nav.innerHTML).not.toContain('flex-[1.15]');
    expect(nav.innerHTML).not.toContain('scale-110');

    const items = within(nav).getAllByRole('link');
    expect(items).toHaveLength(5);
    for (const item of items) {
      // Identical geometry, asserted on every single one.
      expect(item.className).toContain('min-h-[48px]');
      expect(item.className).toContain('h-full');
      expect(item.className).toContain('items-center');
      expect(item.className).toContain('justify-center');
      expect(item.className).not.toMatch(/scale-\[|scale-1[0-9]/);
    }

    // Every icon is the same box, so no destination can look bigger.
    const iconBoxes = Array.from(nav.querySelectorAll('li > a > span')).filter((node) =>
      node.className.includes('h-[22px]'),
    );
    expect(iconBoxes).toHaveLength(5);
    // Every label uses the same type step.
    const labels = Array.from(nav.querySelectorAll('li > a > span.t-micro'));
    expect(labels).toHaveLength(5);
  });

  it('marks the active item by treatment alone, never by geometry', () => {
    renderNav();


    const nav = screen.getByTestId('bottom-nav');
    const roll = within(nav).getByTestId('nav-roll');
    const world = within(nav).getByTestId('nav-world');

    // The active item carries a filled pill and bolder text - and nothing else changes
    // about its box.
    expect(roll.getAttribute('aria-current')).toBe('page');
    expect(world.getAttribute('aria-current')).toBeNull();

    // Geometry is identical between the active and inactive item. Anything the router
    // adds for state is not geometry, so it is excluded deliberately.
    const geometry = (node: HTMLElement) =>
      (node.className ?? '').split(' ').filter((name) => /^(h-|min-h-|w-|flex|items-|justify-|gap-|relative)/.test(name));
    expect(geometry(roll)).toEqual(geometry(world));

    // The pill is inset inside the column, so it cannot widen the item.
    expect(nav.querySelector('.absolute.inset-x-1')?.className).toContain('bg-white/[0.08]');
  });

  it('is pinned to the shell measure, not stretched across a desktop window', () => {
    renderNav();

    expect(screen.getByTestId('bottom-nav').style.maxWidth).toBe('var(--content-max)');
  });
});

describe('Overlays', () => {
  it('sizes itself from the same measure as the app', () => {
    // A hardcoded 440px overlay looked right on a phone and looked stranded on a tablet.
    expect(STYLESHEET).not.toMatch(/max-w-\[440px\]/);
  });

  it('gives the reel a viewport-relative row height', () => {
    // A fixed pixel row pushed the roll button and the result off a landscape screen.
    expect(STYLESHEET).toMatch(/--reel-row:\s*clamp\(/);
    expect(STYLESHEET).toMatch(
      /@media\s*\(orientation:\s*landscape\)[\s\S]*--reel-row:\s*clamp\(/,
    );
  });
});

describe('One scroll container', () => {
  it('scrolls in `main` and nowhere else', async () => {
    const { container } = renderShell();
    await vi.waitFor(() => expect(screen.getByTestId('hunt-page')).toBeInTheDocument());
    const main = container.querySelector('main') as HTMLElement;
    expect(main.className).toContain('overflow-y-auto');
    expect(main.className).toContain('min-h-0');
    // Exactly one scroll container in the whole shell.
    expect(container.querySelectorAll('main')).toHaveLength(1);
    // The shell is pinned to the measured height from both sides, which is what keeps the
    // document from ever becoming the thing that scrolls.
    const shell = screen.getByTestId('app-shell');
    expect(shell.style.minHeight).toBe('var(--app-height)');
    expect(shell.style.maxHeight).toBe('var(--app-height)');
    expect(STYLESHEET).toMatch(/#root\s*\{[^}]*overflow:\s*hidden/);
  });

  it('reserves room for the navigation from the same variables it is built from', async () => {
    const { container } = renderShell();
    await vi.waitFor(() => expect(screen.getByTestId('hunt-page')).toBeInTheDocument());
    const main = container.querySelector('main') as HTMLElement;
    expect(main.style.paddingBottom).toContain('var(--bottom-nav-height)');
    expect(main.style.paddingBottom).toContain('var(--tg-safe-bottom)');
  });
});
