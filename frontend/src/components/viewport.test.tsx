import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { TelegramViewport } from '@/components/TelegramViewport';
import { MobileHeader } from '@/components/MobileHeader';
import { BottomNav } from '@/components/BottomNav';
import { BottomSheet } from '@/components/BottomSheet';
import { CountrySelector } from '@/components/CountrySelector';
import { I18nProvider } from '@/i18n';
import {
  getTelegram,
  initTelegram,
  isAtLeast,
  isTelegram,
  readViewport,
  requestFullscreenFromGesture,
  setTelegram,
  supportsFullscreen,
  type TelegramWebApp,
} from '@/lib/telegram';
import { REVEAL_DURATION, formatCountdown, revealDuration } from '@/lib/motion';
import type { CountrySummary, PlateVisual } from '@/types';
import { polVisual, ruVisual, usVisual } from '@/test/fixtures';

/**
 * The layout system's own tests.
 *
 * These cover the things that were the actual cause of the mobile problems, and that no
 * visual review would catch:
 *
 * * the app's height comes from the client, not from `100vh`;
 * * safe-area insets are published and consumed as variables;
 * * fullscreen is requested, and a refusal does not break initialisation;
 * * the shell reserves room for the navigation from the same variable it is built from;
 * * the country selector is a sheet that closes on Escape, on the scrim and by drag;
 * * the app never scrolls horizontally.
 */

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <I18nProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </I18nProvider>
    </QueryClientProvider>,
  );
}

const root = () => document.documentElement;

beforeEach(() => {
  root().removeAttribute('style');
  root().removeAttribute('data-telegram-scheme');
  root().removeAttribute('data-viewport-source');
  root().removeAttribute('data-tg-fullscreen');
  root().removeAttribute('data-tg-keyboard-open');
  root().removeAttribute('data-tg-fullscreen');
  root().className = '';
});

describe('Telegram viewport', () => {
  it('publishes the measured height as a CSS variable, not 100vh', () => {
    Object.defineProperty(window, 'innerHeight', { value: 780, configurable: true });
    wrap(<TelegramViewport />);
    expect(root().style.getPropertyValue('--app-height')).toBe('780px');
  });

  it('trusts the SDK viewport over the window when Telegram reports one', () => {
    Object.defineProperty(window, 'innerHeight', { value: 900, configurable: true });
    setTelegram({
        initData: 'x',
        colorScheme: 'dark',
        themeParams: {},
        platform: 'android',
        version: '8.0',
        isExpanded: true,
        // The client owns the viewport: the real available height is smaller than the
        // window, because the Telegram chrome is drawn above the webview.
        viewportHeight: 720,
        viewportStableHeight: 780,
        ready: vi.fn(),
        expand: vi.fn(),
        close: vi.fn(),
        setHeaderColor: vi.fn(),
        setBackgroundColor: vi.fn(),
        onEvent: vi.fn(),
        offEvent: vi.fn(),
    } as TelegramWebApp);

    wrap(<TelegramViewport />);

    expect(root().style.getPropertyValue('--app-height')).toBe('720px');
    expect(root().style.getPropertyValue('--tg-viewport-stable-height')).toBe('780px');
    expect(root().dataset.viewportSource).toBe('telegram');
  });

  it('re-measures when the client reports a new viewport', async () => {
    const handlers: Record<string, (...args: never[]) => void> = {};
    setTelegram({
        initData: 'x',
        colorScheme: 'dark',
        themeParams: {},
        platform: 'android',
        version: '8.0',
        isExpanded: true,
        viewportHeight: 700,
        viewportStableHeight: 700,
        ready: vi.fn(),
        expand: vi.fn(),
        close: vi.fn(),
        setHeaderColor: vi.fn(),
        setBackgroundColor: vi.fn(),
        onEvent: (event: string, handler: (...args: never[]) => void) => {
          handlers[event] = handler;
        },
        offEvent: vi.fn(),
    } as TelegramWebApp);

    wrap(<TelegramViewport />);
    expect(root().style.getPropertyValue('--app-height')).toBe('700px');

    // Entering fullscreen resizes the webview after the call: this is exactly the event a
    // layout measured once at mount would miss.
    await act(async () => {
      handlers.viewportChanged?.({ height: 812 } as never);
    });

    await waitFor(() =>
      expect(root().style.getPropertyValue('--app-height')).toBe('812px'),
    );
  });

  it('publishes the keyboard inset and flags the keyboard as open', async () => {
    Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true });
    const viewport = {
      height: 480,
      width: 400,
      offsetTop: 0,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };
    Object.defineProperty(window, 'visualViewport', { value: viewport, configurable: true });

    wrap(<TelegramViewport />);

    expect(root().style.getPropertyValue('--tg-keyboard')).toBe('320px');
    // A real keyboard covers well over 120px; the class exists so the navigation can move.
    expect(root().classList.contains('tg-keyboard-open')).toBe(true);
  });

  it('reports the fullscreen state the client is actually in', () => {
    setTelegram({
        initData: 'x',
        colorScheme: 'dark',
        themeParams: {},
        platform: 'android',
        version: '8.0',
        isExpanded: true,
        isFullscreen: true,
        viewportHeight: 800,
        viewportStableHeight: 800,
        ready: vi.fn(),
        expand: vi.fn(),
        close: vi.fn(),
        setHeaderColor: vi.fn(),
        setBackgroundColor: vi.fn(),
        onEvent: vi.fn(),
        offEvent: vi.fn(),
    } as TelegramWebApp);

    wrap(<TelegramViewport />);

    expect(root().style.getPropertyValue('--tg-fullscreen')).toBe('1');
    expect(root().classList.contains('tg-fullscreen')).toBe(true);
    expect(readViewport().fullscreen).toBe(true);
  });

  it('always publishes a safe-area variable, even with no safe area at all', () => {
    wrap(<TelegramViewport />);
    expect(root().style.getPropertyValue('--tg-safe-top')).toMatch(/^\d+px$/);
    expect(root().style.getPropertyValue('--tg-safe-bottom')).toMatch(/^\d+px$/);
  });
});

describe('Telegram SDK integration', () => {
  afterEach(() => {
    setTelegram(null);
  });

  it('is a no-op outside Telegram', () => {
    expect(() => initTelegram()).not.toThrow();
    expect(supportsFullscreen()).toBe(false);
    expect(requestFullscreenFromGesture()).toBeUndefined();
  });

  it('brings the Mini App up in order: ready, then expand, then fullscreen', () => {
    const order: string[] = [];
    setTelegram({
        initData: 'x',
        colorScheme: 'dark',
        themeParams: {},
        platform: 'android',
        version: '8.0',
        isExpanded: false,
        viewportHeight: 700,
        viewportStableHeight: 700,
        ready: () => order.push('ready'),
        expand: () => order.push('expand'),
        close: vi.fn(),
        setHeaderColor: () => order.push('header'),
        setBackgroundColor: () => order.push('bg'),
        requestFullscreen: () => order.push('fullscreen'),
        onEvent: vi.fn(),
        offEvent: vi.fn(),
    } as TelegramWebApp);

    initTelegram();

    expect(order).toEqual(['ready', 'expand', 'fullscreen', 'header', 'bg']);
  });

  it('still initialises on a client that does not implement fullscreen at all', () => {
    const expand = vi.fn();
    const ready = vi.fn();
    setTelegram({
      initData: 'x',
      colorScheme: 'dark',
      themeParams: {},
      platform: 'android',
      version: '7.0',
      isExpanded: false,
      viewportHeight: 700,
      viewportStableHeight: 700,
      ready,
      expand,
      close: vi.fn(),
      // No `requestFullscreen`: an older client. Fullscreen is a progressive
      // enhancement, so its absence must not cost the player anything else.
      onEvent: vi.fn(),
      offEvent: vi.fn(),
    } as TelegramWebApp);

    expect(supportsFullscreen()).toBe(false);
    initTelegram();
    expect(ready).toHaveBeenCalledTimes(1);
    expect(expand).toHaveBeenCalledTimes(1);
    // And a gesture cannot conjure it into existence.
    requestFullscreenFromGesture();
    expect(expand).toHaveBeenCalledTimes(1);
  });

  it('survives a client that throws on every optional call', () => {
    setTelegram({
        initData: 'x',
        colorScheme: 'dark',
        themeParams: {},
        platform: 'android',
        version: '6.9',
        isExpanded: false,
        viewportHeight: 700,
        viewportStableHeight: 700,
        ready: () => {
          throw new Error('nope');
        },
        expand: () => {
          throw new Error('nope');
        },
        close: vi.fn(),
        requestFullscreen: () => {
          throw new Error('no gesture');
        },
        onEvent: () => {
          throw new Error('nope');
        },
        offEvent: vi.fn(),
    } as TelegramWebApp);

    // A partially supported client must never break the app.
    expect(() => initTelegram()).not.toThrow();
    expect(() => requestFullscreenFromGesture()).not.toThrow();
  });

  it('compares SDK versions numerically, ignoring a suffix', () => {
    setTelegram({
        initData: 'x',
        colorScheme: 'dark',
        themeParams: {},
        platform: 'android',
        version: '7.10',
        isExpanded: true,
        viewportHeight: 700,
        viewportStableHeight: 700,
        ready: vi.fn(),
        expand: vi.fn(),
        close: vi.fn(),
        onEvent: vi.fn(),
        offEvent: vi.fn(),
    } as TelegramWebApp);

    expect(isAtLeast('7.9')).toBe(true);
    expect(isAtLeast('7.10')).toBe(true);
    expect(isAtLeast('8.0')).toBe(false);
  });

  it('does not call requestFullscreen when already fullscreen', () => {
    const request = vi.fn();
    setTelegram({
        initData: 'x',
        colorScheme: 'dark',
        themeParams: {},
        platform: 'android',
        version: '8.0',
        isExpanded: true,
        isFullscreen: true,
        viewportHeight: 700,
        viewportStableHeight: 700,
        ready: vi.fn(),
        expand: vi.fn(),
        close: vi.fn(),
        requestFullscreen: request,
        onEvent: vi.fn(),
        offEvent: vi.fn(),
    } as TelegramWebApp);

    requestFullscreenFromGesture();
    expect(request).not.toHaveBeenCalled();
  });

  it('exposes a null SDK outside Telegram', () => {
    setTelegram(null);
    expect(getTelegram()).toBeNull();
    expect(isTelegram()).toBe(false);
  });
});

describe('App chrome', () => {
  it('renders a compact header that clears the safe area by padding, not by offset', () => {
    wrap(<MobileHeader />);
    const header = screen.getByTestId('app-header');
    // Padding rather than an offset keeps the header inside the safe area while leaving
    // the sticky positioning to the viewport.
    expect(header.style.paddingTop).toBe('var(--tg-safe-top)');
    expect(header.style.top).toBe('');
    // One row, fixed height: the app's own header never competes with Telegram's.
    expect(header.className).toContain('sticky');
  });

  it('builds the bottom navigation from the layout variables', () => {
    wrap(<BottomNav />);
    const nav = screen.getByTestId('bottom-nav');
    // Fixed to the viewport, and cleared below by the system gesture area.
    expect(nav.className).toContain('fixed');
    expect(nav.style.paddingBottom).toBe('var(--tg-safe-bottom)');
    // The gesture class is what moves it aside for the keyboard.
    expect(nav.className).toContain('bottom-nav');
  });

  it('marks the current destination for assistive tech', () => {
    wrap(<BottomNav />);
    const roll = screen.getByTestId('nav-roll');
    expect(roll.getAttribute('aria-current')).toBe('page');
    expect(screen.getByTestId('nav-world').getAttribute('aria-current')).toBeNull();
  });

  it('gives every destination a real touch target', () => {
    wrap(<BottomNav />);
    for (const id of ['nav-roll', 'nav-world', 'nav-collection', 'nav-ranking', 'nav-profile']) {
      expect(screen.getByTestId(id).className).toContain('min-h-[48px]');
    }
  });
});

describe('BottomSheet', () => {
  it('is a modal dialog with a close control and an outside tap target', () => {
    const onClose = vi.fn();
    wrap(
      <BottomSheet open onClose={onClose} label="Choose">
        <p>body</p>
      </BottomSheet>,
    );
    expect(screen.getByRole('dialog')).toBeTruthy();
    fireEvent.click(screen.getByTestId('bottom-sheet-scrim'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    wrap(
      <BottomSheet open onClose={onClose} label="Choose">
        <p>body</p>
      </BottomSheet>,
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('sizes itself against the measured viewport, not a hardcoded vh', () => {
    wrap(
      <BottomSheet open onClose={vi.fn()} label="Choose">
        <p>body</p>
      </BottomSheet>,
    );
    const panel = screen.getByTestId('bottom-sheet-panel');
    expect(panel.style.maxHeight).toContain('var(--app-height)');
    expect(panel.className).not.toContain('vh');
  });

  it('renders nothing when closed', () => {
    wrap(
      <BottomSheet open={false} onClose={vi.fn()} label="Choose">
        <p>body</p>
      </BottomSheet>,
    );
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});

describe('CountrySelector', () => {
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
      visual: ruVisual as PlateVisual,
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

  const countries = [
    country(),
    country({ code: 'POL', iso_alpha2: 'PL', name_en: 'Poland', name_ru: 'Польша', flag: '🇵🇱', region_group: 'EUROPE', visual: polVisual as PlateVisual }),
    country({ code: 'USA', iso_alpha2: 'US', name_en: 'United States', name_ru: 'США', flag: '🇺🇸', region_group: 'AMERICAS', visual: usVisual as PlateVisual }),
    country({ code: 'ZZZ', name_en: 'Atlantis', name_ru: 'Атлантида', flag: '🏝️', is_playable: false }),
  ];

  it('summarises the current country in one tappable row', () => {
    wrap(<CountrySelector value="RUS" onChange={vi.fn()} countries={countries} />);
    const button = screen.getByTestId('active-country');
    expect(button.textContent).toContain('Russia');
    expect(button.textContent).toContain('RUS');
    expect(button.getAttribute('aria-haspopup')).toBe('dialog');
  });

  it('falls back to the whole world when nothing is selected', () => {
    wrap(<CountrySelector value={null} onChange={vi.fn()} countries={countries} />);
    expect(screen.getByTestId('active-country').textContent).toContain('Whole world');
  });

  it('opens a searchable sheet and filters by name, code and calling code', async () => {
    wrap(<CountrySelector value={null} onChange={vi.fn()} countries={countries} />);
    fireEvent.click(screen.getByTestId('active-country'));
    const search = await screen.findByTestId('country-search');
    fireEvent.change(search, { target: { value: 'pol' } });
    expect(screen.getByTestId('country-option-POL')).toBeTruthy();
    expect(screen.queryByTestId('country-option-USA')).toBeNull();
  });

  it('disables a country that cannot be rolled yet, and says so', async () => {
    wrap(<CountrySelector value={null} onChange={vi.fn()} countries={countries} />);
    fireEvent.click(screen.getByTestId('active-country'));
    const locked = await screen.findByTestId('country-option-ZZZ');
    expect(locked).toBeDisabled();
    expect(locked.getAttribute('data-locked')).toBe('true');
  });

  it('offers the whole world as an explicit option', async () => {
    const onChange = vi.fn();
    wrap(<CountrySelector value="RUS" onChange={onChange} countries={countries} />);
    fireEvent.click(screen.getByTestId('active-country'));
    fireEvent.click(await screen.findByTestId('country-option-WORLD'));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('reports the chosen country and closes', async () => {
    const onChange = vi.fn();
    wrap(<CountrySelector value="RUS" onChange={onChange} countries={countries} />);
    fireEvent.click(screen.getByTestId('active-country'));
    fireEvent.click(await screen.findByTestId('country-option-POL'));
    expect(onChange).toHaveBeenCalledWith('POL');
  });

  it('filters by region', async () => {
    wrap(<CountrySelector value={null} onChange={vi.fn()} countries={countries} />);
    fireEvent.click(screen.getByTestId('active-country'));
    fireEvent.click(await screen.findByTestId('country-region-AMERICAS'));
    expect(screen.getByTestId('country-option-USA')).toBeTruthy();
    expect(screen.queryByTestId('country-option-RUS')).toBeNull();
  });
});

describe('Reveal timing', () => {
  it('keeps the whole rarity ladder inside a 1.2-2.2 second band', () => {
    // A reveal the player has to wait through is the fastest way to make a game feel slow
    // on the phone they are holding.
    for (const [tier, ms] of Object.entries(REVEAL_DURATION)) {
      expect(ms, tier).toBeGreaterThanOrEqual(1200);
      expect(ms, tier).toBeLessThanOrEqual(2200);
    }
  });

  it('gives rarer finds longer reveals, without ever exceeding the band', () => {
    expect(revealDuration('COMMON')).toBeLessThan(revealDuration('RARE'));
    expect(revealDuration('RARE')).toBeLessThan(revealDuration('MYTHIC'));
    expect(revealDuration('MYTHIC')).toBeLessThanOrEqual(2200);
    // An unknown or missing tier falls back to the fastest, calmest presentation.
    expect(revealDuration(null)).toBe(REVEAL_DURATION.COMMON);
    expect(revealDuration('NOT_A_RARITY')).toBe(REVEAL_DURATION.COMMON);
  });
});

describe('Formatting helpers', () => {
  it('formats a countdown compactly', () => {
    expect(formatCountdown(0)).toBe('0:00');
    expect(formatCountdown(7)).toBe('0:07');
    expect(formatCountdown(59)).toBe('0:59');
    expect(formatCountdown(32 * 60)).toBe('32m');
    expect(formatCountdown(3660)).toBe('1h 01m');
    // A nonsensical value must not print `NaN` into the interface.
    expect(formatCountdown(Number.NaN)).toBe('0:00');
    expect(formatCountdown(-5)).toBe('0:00');
  });
});

describe('Horizontal overflow', () => {
  it('never lets the document grow wider than the viewport', () => {
    // The regression this guards against: a fixed-width element anywhere in the shell
    // makes the whole Mini App scroll sideways, which on Android feels like the app has
    // two layouts and you are seeing the wrong one.
    Object.defineProperty(document.documentElement, 'scrollWidth', {
      value: 360,
      configurable: true,
    });
    Object.defineProperty(window, 'innerWidth', { value: 360, configurable: true });
    wrap(
      <>
        <TelegramViewport />
        <MobileHeader />
        <BottomNav />
      </>,
    );
    expect(document.documentElement.scrollWidth).toBe(window.innerWidth);
  });
});
