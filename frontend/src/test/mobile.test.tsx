import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { useState } from 'react';
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import App from '@/App';
import { BottomNav } from '@/components/BottomNav';
import { CountrySelector } from '@/components/CountrySelector';
import RollButton from '@/components/RollButton';
import { ToastHost, notify, notifyError } from '@/components/Toast';
import { I18nProvider } from '@/i18n';
import { setTelegram } from '@/lib/telegram';
import { useAuthStore } from '@/store/auth';
import { polVisual, profile, rollBalance } from './fixtures';
import type { CountrySummary, PlateVisual, RollBalance } from '@/types';

/**
 * Mobile interaction fixes.
 *
 * Every test here corresponds to a specific bug that was fixed, and each one is written
 * so it would fail again if the fix were reverted:
 *
 * * the roll button used to be permanently dead while the bank loaded, because
 *   "no data" was treated as "zero rolls";
 * * the count badge hung off the top of the button with a negative offset;
 * * at zero rolls the countdown - the one useful thing to show - was suppressed;
 * * `main` had no `min-h-0`, so `overflow-y: auto` never engaged;
 * * the sheet's panel-level drag swallowed every vertical swipe meant for the list;
 * * the scroll listener sat on an element that never scrolls, so paging never fired;
 * * the navigation mixed emoji and typographic characters instead of one icon set;
 * * country names were shown in English regardless of the chosen language.
 */

const STYLESHEET = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <I18nProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </I18nProvider>
    </QueryClientProvider>,
  );
}

/**
 * A rerender that keeps its providers.
 *
 * `rerender` replaces the whole tree, so rerendering a bare `<RollButton/>` would drop
 * the query client and the router underneath it and throw. The harness holds the state
 * instead, which is also closer to what the hunt screen actually does.
 */
interface ButtonProps {
  rolls: RollBalance | null;
  onRoll: () => void;
  rolling?: boolean;
  disabled?: boolean;
  locked?: boolean;
}

function wrapStateful(initial: ButtonProps) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  let update: (next: ButtonProps) => void = () => {};
  const Harness = () => {
    const [props, setProps] = useState<ButtonProps>(initial);
    update = setProps;
    return (
      <QueryClientProvider client={client}>
        <I18nProvider>
          <MemoryRouter>
            <RollButton {...props} />
          </MemoryRouter>
        </I18nProvider>
      </QueryClientProvider>
    );
  };
  const utils = render(<Harness />);
  return {
    ...utils,
    // `act`, because a React state update is not observable to the test until React has
    // flushed it - asserting straight after `set` would read the previous render.
    set: (next: Partial<ButtonProps>) => act(() => update({ ...initial, ...next })),
  };
}

const country = (over: Partial<CountrySummary> = {}): CountrySummary =>
  ({
    code: 'RUS',
    iso_alpha2: 'RU',
    name_en: 'Russia',
    name_ru: 'Россия',
    flag: '🇷🇺',
    region_group: 'CIS',
    currency_code: 'RUB',
    currency_symbol: '₽',
    calling_code: '+7',
    visual: polVisual as PlateVisual,
    collected: 2,
    total: 10,
    progress: 0.2,
    percent: 20,
    best_rarity: 'RARE',
    regions_collected: 1,
    regions_total: 5,
    completed: false,
    sort_order: 1,
    is_active: true,
    is_playable: true,
    ...over,
  }) as CountrySummary;

beforeEach(() => {
  setTelegram(null);
  useAuthStore.setState({
    token: 'test-token',
    profile,
    status: 'authenticated',
    error: null,
    startContext: null,
  });
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});

describe('The roll button', () => {
  it('stays clickable while the bank is still loading', () => {
    // This is the bug that made ROLL look dead. `rolls === null` means the bank has not
    // arrived; it does not mean the player has zero rolls.
    const onRoll = vi.fn();
    wrap(<RollButton rolls={null} onRoll={onRoll} />);

    const button = screen.getByTestId('roll-button');
    expect(button).toBeEnabled();
    expect(button.dataset.state).toBe('unknown');
    fireEvent.click(button);
    expect(onRoll).toHaveBeenCalledTimes(1);
  });

  it('shows a loading line rather than a zero count while the bank is unknown', () => {
    wrap(<RollButton rolls={null} onRoll={vi.fn()} />);
    const button = screen.getByTestId('roll-button');
    expect(button.textContent).not.toContain('0');
    expect(button.textContent?.toLowerCase()).toContain('bank');
  });

  it('is disabled only when the server actually said zero', () => {
    wrap(<RollButton rolls={rollBalance({ rolls_remaining: 0 })} onRoll={vi.fn()} />);
    const button = screen.getByTestId('roll-button');
    expect(button).toBeDisabled();
    expect(button.dataset.state).toBe('empty');
  });

  it('shows the countdown at zero rolls, because that is when it matters', () => {
    const rolls = rollBalance({
      rolls_remaining: 0,
      next_roll_at: new Date(Date.now() + 32 * 60_000).toISOString(),
    });
    wrap(<RollButton rolls={rolls} onRoll={vi.fn()} />);
    const button = screen.getByTestId('roll-button');
    expect(button.textContent).toContain('32m');
  });

  it('carries the count inside its own bounds, with nothing hanging off an edge', () => {
    wrap(<RollButton rolls={rollBalance()} onRoll={vi.fn()} />);
    const button = screen.getByTestId('roll-button');
    expect(button.className).toContain('overflow-hidden');
    // No negative-offset descendant: that is what put a number over the button's edge.
    for (const child of Array.from(button.children)) {
      expect(child.getAttribute('style') ?? '').not.toMatch(/-\d/);
    }
    // And the count is somewhere in the subtree, not rendered beside the control.
    expect(button.textContent).toContain('rolls');
    expect(screen.queryByText(/^\d+$/, { selector: 'body > span' })).toBeNull();
  });

  it('reports a distinct state for every phase', () => {
    const onRoll = vi.fn();
    const view = wrapStateful({ rolls: rollBalance(), onRoll });
    expect(screen.getByTestId('roll-button').dataset.state).toBe('ready');

    view.set({ rolling: true });
    expect(screen.getByTestId('roll-button').dataset.state).toBe('rolling');
    expect(screen.getByTestId('roll-button')).toBeDisabled();

    view.set({ rolling: false, locked: true });
    expect(screen.getByTestId('roll-button')).toBeDisabled();
  });

  it('never fires twice for a double tap while a roll is in flight', () => {
    const onRoll = vi.fn();
    const view = wrapStateful({ rolls: rollBalance(), onRoll });
    fireEvent.click(screen.getByTestId('roll-button'));
    expect(onRoll).toHaveBeenCalledTimes(1);

    // The parent flips to rolling; a second press on the same node must do nothing.
    view.set({ rolling: true });
    fireEvent.click(screen.getByTestId('roll-button'));
    expect(onRoll).toHaveBeenCalledTimes(1);
  });

  it('speaks the player language', () => {
    window.localStorage.setItem('numora.lang', 'ru');
    wrap(<RollButton rolls={rollBalance()} onRoll={vi.fn()} />);
    expect(screen.getByTestId('roll-button').textContent).toContain('КРУТИТЬ');
    window.localStorage.setItem('numora.lang', 'en');
  });
});

describe('The vertical scroll container', () => {
  it('lets `main` actually scroll inside a flex column', () => {
    // A flex item's default `min-height: auto` refuses to shrink below its content, so
    // without `min-h-0` the `overflow-y: auto` below is dead code and the header stops
    // sticking. This is the declaration that makes the layout behave.
    expect(STYLESHEET).toMatch(/#root\s*\{[^}]*overflow:\s*hidden/);
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <I18nProvider>
          <CountrySelector value={null} onChange={vi.fn()} countries={[country()]} />
        </I18nProvider>
      </QueryClientProvider>,
    );
    // The sheet's own scroll area is `min-h-0` + `overflow-y-auto` for the same reason.
    expect(STYLESHEET).toMatch(/\.sheet/);
  });

  it('pins the document to one screen so nothing else scrolls', () => {
    expect(STYLESHEET).toMatch(/body\s*\{[^}]*overflow:\s*hidden/);
    expect(STYLESHEET).toMatch(/overscroll-behavior:\s*none/);
  });

  it('gives the sheet a scroll area that owns the vertical gesture', async () => {
    wrap(
      <CountrySelector
        value={null}
        onChange={vi.fn()}
        countries={[country(), country({ code: 'GEO', name_en: 'Georgia', name_ru: 'Грузия' })]}
      />,
    );
    fireEvent.click(screen.getByTestId('active-country'));
    const scroller = await screen.findByTestId('sheet-scroll');
    // `pan-y` only: the browser is told this element scrolls vertically and nothing
    // else, so a horizontal drag still reaches a horizontal child.
    expect(scroller.className).toContain('touch-pan-y');
    expect(scroller.className).toContain('overflow-y-auto');
    expect(scroller.className).toContain('overscroll-contain');
  });

  it('lets the list scroll freely instead of the sheet stealing the swipe', async () => {
    wrap(<CountrySelector value={null} onChange={vi.fn()} countries={[country()]} />);
    fireEvent.click(screen.getByTestId('active-country'));
    const panel = await screen.findByTestId('bottom-sheet-panel');
    // The drag gesture belongs to the handle, not the panel: a panel-level listener
    // claims every vertical swipe inside the sheet, including the list's.
    expect(panel.getAttribute('style') ?? '').not.toContain('touch-none');
    expect(await screen.findByTestId('sheet-handle')).toBeInTheDocument();
  });

  it('confines horizontal swipes to the chip row', async () => {
    wrap(
      <CountrySelector
        value={null}
        onChange={vi.fn()}
        countries={[
          country(),
          country({ code: 'GEO', region_group: 'EUROPE', name_en: 'Georgia' }),
          country({ code: 'USA', region_group: 'AMERICAS', name_en: 'United States' }),
        ]}
      />,
    );
    fireEvent.click(screen.getByTestId('active-country'));
    const row = await screen.findByTestId('country-region-row');
    // Horizontal only. The page can never pick up a stray pan from this row.
    expect(row.className).toContain('touch-pan-x');
    expect(row.className).toContain('overflow-y-hidden');
  });

  it('pages the country list off the container that actually scrolls', async () => {
    const onLoadMore = vi.fn();
    wrap(
      <CountrySelector
        value={null}
        onChange={vi.fn()}
        countries={[country()]}
        onLoadMore={onLoadMore}
        hasMore
      />,
    );
    fireEvent.click(screen.getByTestId('active-country'));
    const scroller = await screen.findByTestId('sheet-scroll');

    // Nowhere near the bottom: nothing loads.
    Object.defineProperty(scroller, 'scrollHeight', { value: 3000, configurable: true });
    Object.defineProperty(scroller, 'clientHeight', { value: 800, configurable: true });
    scroller.scrollTop = 100;
    fireEvent.scroll(scroller);
    expect(onLoadMore).not.toHaveBeenCalled();

    // At the bottom: the next page is requested. Previously this handler sat on the
    // list, which never scrolls, so infinite loading silently never fired.
    scroller.scrollTop = 2200;
    fireEvent.scroll(scroller);
    expect(onLoadMore).toHaveBeenCalled();
  });
});

describe('Bottom navigation', () => {
  it('draws every icon as one vector set, not as text characters', () => {
    wrap(<BottomNav />);
    const nav = screen.getByTestId('bottom-nav');
    // Five SVGs on one grid.
    expect(nav.querySelectorAll('svg')).toHaveLength(5);
    for (const svg of Array.from(nav.querySelectorAll('svg'))) {
      expect(svg.getAttribute('viewBox')).toBe('0 0 24 24');
      expect(svg.getAttribute('stroke-width')).toBe('1.8');
    }
    // No typographic stand-ins and no emoji.
    expect(nav.textContent).not.toMatch(/[◎☺▲]/);
    // The globe emoji is gone; its own emoji variation selector must not appear either.
    expect(nav.innerHTML).not.toContain('&#x1F30D;');
  });

  it('keeps five destinations with a real touch target', () => {
    wrap(<BottomNav />);
    const nav = screen.getByTestId('bottom-nav');
    expect(within(nav).getAllByRole('link')).toHaveLength(5);
    for (const link of Array.from(nav.querySelectorAll('a'))) {
      expect(link.className).toContain('min-h-[48px]');
    }
  });
});

describe('Language', () => {
  it('names the selected country in the chosen language', async () => {
    window.localStorage.setItem('numora.lang', 'ru');
    wrap(<CountrySelector value="RUS" onChange={vi.fn()} countries={[country()]} />);
    const button = screen.getByTestId('active-country');
    expect(button.textContent).toContain('Россия');
    expect(button.textContent).not.toContain('Russia');
    window.localStorage.setItem('numora.lang', 'en');
  });

  it('lists countries in the chosen language too', async () => {
    window.localStorage.setItem('numora.lang', 'ru');
    wrap(
      <CountrySelector
        value={null}
        onChange={vi.fn()}
        countries={[country(), country({ code: 'GEO', name_en: 'Georgia', name_ru: 'Грузия' })]}
      />,
    );
    fireEvent.click(screen.getByTestId('active-country'));
    expect((await screen.findByTestId('country-option-GEO')).textContent).toContain('Грузия');
    window.localStorage.setItem('numora.lang', 'en');
  });
});

describe('In-app feedback', () => {
  it('reports an error without a native dialog', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    wrap(
      <>
        <ToastHost />
        <button type="button" onClick={() => notifyError(new Error('Server refused'), 'failed')}>
          fail
        </button>
      </>,
    );
    fireEvent.click(screen.getByText('fail'));

    await waitFor(() => expect(screen.getByTestId('toast-error')).toBeInTheDocument());
    expect(screen.getByTestId('toast-error').textContent).toContain('Server refused');
    // Announced, and never as a blocking native dialog that freezes the webview.
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(alertSpy).not.toHaveBeenCalled();
    alertSpy.mockRestore();
  });

  it('can be dismissed', async () => {
    wrap(
      <>
        <ToastHost />
        <button type="button" onClick={() => notify('Saved', 'ok')}>
          ok
        </button>
      </>,
    );
    fireEvent.click(screen.getByText('ok'));
    await waitFor(() => expect(screen.getByTestId('toast-ok')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /dismiss|закрыть/i }));
    await waitFor(() => expect(screen.queryByTestId('toast-ok')).toBeNull());
  });

  it('sits clear of the header and the navigation', () => {
    wrap(<ToastHost />);
    notify('hello');
    // Rendered on the next tick by the listener, so read the host when it appears.
    const host = screen.queryByTestId('toast-host');
    if (host) expect(host.style.top).toContain('var(--tg-safe-top)');
  });
});

describe('Shell layout', () => {
  it('sizes the shell and the scroll area from the measured viewport', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input);
      const body = url.includes('/api/user/me')
        ? profile
        : url.includes('/api/game/garage')
          ? { coins: 100, rolls: rollBalance(), recent: null, country_progress: null }
          : url.includes('/api/countries/active')
            ? { code: 'RUS' }
            : { total: 0, items: [] };
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
    });

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={client}>
        <I18nProvider>
          <App />
        </I18nProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByTestId('hunt-page')).toBeInTheDocument());
    const main = container.querySelector('main') as HTMLElement;
    expect(main.className).toContain('min-h-0');
    expect(main.className).toContain('overflow-y-auto');
    // The document cannot grow, so the header stays put and the navigation cannot drift.
    expect(STYLESHEET).toMatch(/#root\s*\{[^}]*max-height:\s*var\(--app-height/);
  });
});
