import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';

import App from '@/App';
import { useAuthStore } from '@/store/auth';
import { garage, json, profile, rollBalance } from './fixtures';

/**
 * The whole app, rendered.
 *
 * The shell is where a runtime error would hide: it owns the single scroll container, the
 * sticky header, the fixed navigation, the route table and the viewport controller, and
 * none of that is exercised by testing screens individually. If the shell throws, every
 * screen is broken and no per-screen test would say so.
 *
 * These assertions are about *structure*, not about any one screen's content.
 */

/** Minimal backend: enough for the shell and the hunt screen to mount. */
function stubApi() {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
    const url = String(input);
    if (url.includes('/api/user/me')) return Promise.resolve(json(profile));
    if (url.includes('/api/countries/active')) {
      return Promise.resolve(json({ code: 'RUS', name_en: 'Russia' }));
    }
    if (url.includes('/api/countries')) {
      return Promise.resolve(json({ total: 0, items: [] }));
    }
    if (url.includes('/api/game/garage')) {
      return Promise.resolve(json(garage({ rolls: rollBalance(), recent: null })));
    }
    return Promise.resolve(json({}));
  });
}

beforeEach(() => {
  window.Telegram = undefined;
  useAuthStore.setState({
    token: 'test-token',
    profile,
    status: 'authenticated',
    error: null,
    startContext: null,
  });
});

describe('App shell', () => {
  it('mounts without throwing and reaches the hunt screen', async () => {
    const fetchMock = stubApi();
    const { container } = render(<App />);

    await waitFor(() => expect(screen.getByTestId('hunt-page')).toBeInTheDocument());

    // The three pieces of permanent chrome.
    expect(screen.getByTestId('app-header')).toBeInTheDocument();
    expect(screen.getByTestId('bottom-nav')).toBeInTheDocument();
    // One scroll container, so a screen can never inherit another's scroll offset.
    expect(container.querySelectorAll('main')).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalled();
  });

  it('lays the shell out against layout variables, not magic numbers', async () => {
    stubApi();
    const { container } = render(<App />);
    await waitFor(() => expect(screen.getByTestId('hunt-page')).toBeInTheDocument());

    const main = container.querySelector('main') as HTMLElement;
    // Reserved room for the navigation plus the system gesture area, all measured.
    expect(main.style.paddingBottom).toContain('var(--bottom-nav-height)');
    expect(main.style.paddingBottom).toContain('var(--tg-safe-bottom)');
    expect(main.style.paddingTop).toContain('var(--section-gap)');
    // Clip, not hidden: `hidden` on the scroll container breaks sticky positioning inside it.
    expect(main.className).toContain('overflow-x-clip');
    expect(main.className).not.toContain('overflow-x-auto');
  });

  it('keeps exactly five primary destinations', async () => {
    stubApi();
    render(<App />);
    await waitFor(() => expect(screen.getByTestId('hunt-page')).toBeInTheDocument());

    const nav = screen.getByTestId('bottom-nav');
    for (const id of ['nav-roll', 'nav-world', 'nav-collection', 'nav-ranking', 'nav-profile']) {
      expect(within(nav).getByTestId(id)).toBeInTheDocument();
    }
    // The legacy four-digit line is deliberately not one of them: it stays reachable from
    // the profile, so a "roll four digits" tab cannot read as the product's main loop.
    expect(within(nav).queryByTestId('nav-boxes')).toBeNull();
    // Five destinations across a 360px screen is 72px each: real touch targets.
    expect(within(nav).getAllByRole('link')).toHaveLength(5);
  });

  it('navigates between destinations and resets the scroll position', async () => {
    stubApi();
    render(<App />);
    await waitFor(() => expect(screen.getByTestId('hunt-page')).toBeInTheDocument());

    const main = document.querySelector('main') as HTMLElement;
    main.scrollTop = 240;

    within(screen.getByTestId('bottom-nav')).getByTestId('nav-world').click();

    await waitFor(() => expect(screen.getByTestId('world-page')).toBeInTheDocument());
    // A new screen starts at the top rather than inheriting the previous one's offset -
    // the "sudden position reset" artefact the old per-screen scroll setup produced.
    await waitFor(() => expect(main.scrollTop).toBe(0));
  });

  it('shows an actionable error when the session cannot be established', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      Promise.resolve(new Response('', { status: 500 })),
    );
    useAuthStore.setState({ status: 'error', error: 'Could not load your profile.', profile: null });

    render(<App />);

    expect(screen.getByRole('alert')).toBeInTheDocument();
    // A failure the player cannot act on looks exactly like a dead button.
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });
});
