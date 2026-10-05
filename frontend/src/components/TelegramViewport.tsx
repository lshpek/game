import { useEffect, useState } from 'react';

import {
  readViewport,
  requestFullscreenFromGesture,
  getTelegram,
  type ViewportState,
} from '@/lib/telegram';

/**
 * Keeps one number true at a time: **how much room the Mini App actually has.**
 *
 * This component renders nothing. It subscribes to every signal the client and the
 * browser use to say "the viewport changed", measures on each one, and publishes the
 * result as CSS custom properties. Every other component then reads those variables
 * instead of guessing with `100vh` - which is what makes the header, the sheet, the
 * bottom navigation and the reveal correct in every combination of fullscreen,
 * keyboard, rotation and Telegram version.
 *
 * Published on `:root`:
 *
 * | variable | meaning |
 * | --- | --- |
 * | `--app-height` | usable height in px - the one the whole layout is sized against |
 * | `--tg-viewport-height` | raw reported height |
 * | `--tg-viewport-stable-height` | height that does not move with the keyboard |
 * | `--tg-safe-top` | top inset: status bar, notch, Telegram header |
 * | `--tg-safe-bottom` | bottom inset: gesture / navigation area |
 * | `--tg-keyboard` | how much of the bottom the keyboard covers |
 * | `--tg-fullscreen` | `1` while fullscreen, `0` otherwise |
 *
 * ### Why the top inset is measured rather than trusted
 *
 * `env(safe-area-inset-top)` is the *hardware* inset. Telegram's own header is a
 * separate thing the client draws above the webview, and which of the two applies
 * depends on whether the Mini App is fullscreen. Rather than branch on the client
 * version, the app reserves a measured minimum in non-fullscreen mode: if Telegram is
 * drawing its header inside the viewport, the hardware inset is enlarged by a
 * header-height constant. Both cases end up with a sane value, and the constant is a
 * single number that can be tuned if a client changes its header height.
 */

/** The height Telegram's own header occupies when the Mini App is not fullscreen. */
const TELEGRAM_HEADER_FALLBACK_PX = 44;

/** Telegram's `viewportChanged` payload. */
interface ViewportChangedEvent {
  height?: number;
  stableHeight?: number;
}

type Listener = (state: ViewportState) => void;

const listeners = new Set<Listener>();
let lastState: ViewportState | null = null;
let detach: (() => void) | null = null;

/**
 * How much inset to reserve at the top, in pixels.
 *
 * `env(safe-area-inset-top)` cannot be read from JavaScript, so the CSS variable keeps
 * the hardware value and this only adds what Telegram draws on top of it. A reported
 * viewport shorter than the window is the signal that the client is *not* drawing
 * fullscreen, which is the only reliable hint available without version sniffing.
 */
function topInset(state: ViewportState): number {
  const hardware = readCssPixels('env(safe-area-inset-top, 0px)');
  if (!getTelegram()) return hardware;
  // Fullscreen: the client owns the whole screen, so only the hardware inset applies.
  if (state.fullscreen) return hardware;
  // Non-fullscreen: Telegram's header sits above the webview and must be cleared.
  return Math.max(hardware, hardware > 0 ? TELEGRAM_HEADER_FALLBACK_PX : 0);
}

function bottomInset(_state: ViewportState): number {
  /*
   * Inside Telegram the hardware inset is already correct: the client insets the webview
   * for the gesture area when it is fullscreen, and when it is not, there is no gesture
   * area over the content at all. Outside Telegram `env()` is exactly right too, so the
   * hardware value is the whole truth in every case and nothing is added to it.
   *
   * This is the deliberate counterpart to `topInset`: Telegram draws a *header* it does
   * not inset for, so only the top needs a measured allowance.
   */
  return readCssPixels('env(safe-area-inset-bottom, 0px)');
}

/** Read a CSS length through a probe element. Safe in every browser that has one. */
function readCssPixels(value: string): number {
  if (typeof document === 'undefined' || typeof window === 'undefined') return 0;
  const probe = document.createElement('div');
  probe.style.cssText = `position:absolute;visibility:hidden;pointer-events:none;height:${value};width:${value}`;
  document.documentElement.appendChild(probe);
  const parsed = Number.parseFloat(window.getComputedStyle(probe).height);
  probe.remove();
  return Number.isFinite(parsed) ? parsed : 0;
}

/** Apply one measurement to the document. */
function publish(state: ViewportState): void {
  const root = document.documentElement;
  root.style.setProperty('--app-height', `${state.height}px`);
  root.style.setProperty('--tg-viewport-height', `${state.height}px`);
  root.style.setProperty('--tg-viewport-stable-height', `${state.stableHeight}px`);
  root.style.setProperty('--tg-keyboard', `${state.keyboard}px`);
  root.style.setProperty('--tg-safe-top', `${Math.round(topInset(state))}px`);
  root.style.setProperty('--tg-safe-bottom', `${Math.round(bottomInset(state))}px`);
  root.style.setProperty('--tg-fullscreen', state.fullscreen ? '1' : '0');
  // The client decides whether its own UI is dark; the app follows so a light-themed
  // Telegram never frames a dark app with a white flash.
  root.dataset.telegramScheme = getTelegram()?.colorScheme ?? 'dark';
  root.dataset.viewportSource = state.source;
  root.classList.toggle('tg-keyboard-open', state.keyboard > 120);
  root.classList.toggle('tg-fullscreen', state.fullscreen);
}

/** Measure, publish, and tell any subscriber. Coalesced to one frame. */
let frame = 0;
function measure(): void {
  if (frame) return;
  frame = window.requestAnimationFrame(() => {
    frame = 0;
    const state = readViewport();
    const changed =
      !lastState ||
      lastState.height !== state.height ||
      lastState.stableHeight !== state.stableHeight ||
      lastState.keyboard !== state.keyboard ||
      lastState.fullscreen !== state.fullscreen ||
      lastState.source !== state.source;
    lastState = state;
    if (changed) publish(state);
    for (const listener of listeners) listener(state);
  });
}

/** Subscribe to every signal the viewport can change on, and tear them all down. */
function attach(): () => void {
  const app = getTelegram();
  const handlers: Array<() => void> = [];

  const on = (target: EventTarget, event: string, handler: EventListener) => {
    target.addEventListener(event, handler, { passive: true });
    handlers.push(() => target.removeEventListener(event, handler));
  };

  /*
   * `resize` covers rotation, Android's split screen, and the browser chrome showing
   * or hiding. `orientationchange` is still fired by some Android WebViews before
   * `resize` settles, so it is measured immediately as well.
   */
  on(window, 'resize', measure);
  on(window, 'orientationchange', measure);

  if (app) {
    /*
     * `viewportChanged` fires for every step of expand()/fullscreen/keyboard animation
     * and carries the height inline, so the measurement does not have to race the
     * animation to settle.
     */
    app.onEvent('viewportChanged' as string, ((event: ViewportChangedEvent) => {
      if (typeof event?.height === 'number' && event.height > 0) {
        app.viewportHeight = event.height;
      }
      if (typeof event?.stableHeight === 'number' && event.stableHeight > 0) {
        app.viewportStableHeight = event.stableHeight;
      }
      measure();
    }) as (...args: never[]) => void);

    app.onEvent('fullscreenChanged' as string, (() => {
      measure();
    }) as (...args: never[]) => void);

    // A returning player re-enters through a warm webview; the theme may have changed.
    app.onEvent('themeChanged' as string, (() => {
      publish(readViewport());
    }) as (...args: never[]) => void);

    // The safe-area insets change on rotation, and Telegram reports them separately.
    app.onEvent('safeAreaChanged' as string, (() => {
      publish(readViewport());
    }) as (...args: never[]) => void);
  }

  /*
   * `visualViewport` is the only event that fires when Telegram's keyboard animates,
   * and it fires *during* the animation. Reading it every frame is what stops the
   * bottom navigation from jumping to the wrong place mid-animation.
   */
  const visual = typeof window !== 'undefined' ? window.visualViewport : null;
  if (visual) {
    const onVisual = () => measure();
    visual.addEventListener('resize', onVisual);
    visual.addEventListener('scroll', onVisual);
    handlers.push(() => {
      visual.removeEventListener('resize', onVisual);
      visual.removeEventListener('scroll', onVisual);
    });
  }

  // Fonts land after first paint and change the header height by a pixel or two.
  const fonts = typeof document !== 'undefined' ? (document.fonts as FontFaceSet | undefined) : undefined;
  fonts?.ready.then(measure).catch(() => {});

  return () => {
    handlers.forEach((off) => off());
  };
}

let mounted = 0;

/** Start measuring. Reference-counted so a re-render never detaches the listeners. */
function start(): () => void {
  mounted += 1;
  if (mounted === 1) {
    detach = attach();
    // A synchronous first publish, so the very first paint is already correct and the
    // app never visibly reflows a frame later.
    publish(readViewport());
    measure();
  }
  return () => {
    mounted -= 1;
    if (mounted <= 0) {
      mounted = 0;
      detach?.();
      detach = null;
    }
  };
}

/**
 * The current viewport, as React state.
 *
 * For layout that must *re-render* on a change (a sheet that has to move out of the
 * keyboard's way, for instance). Everything else should read the CSS variables, which
 * cost no re-render at all.
 */
export function useViewport(): ViewportState {
  const [state, setState] = useState<ViewportState>(() => lastState ?? readViewport());
  useEffect(() => {
    const listener: Listener = (next) => setState(next);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);
  return state;
}

/**
 * Mounts the viewport controller.
 *
 * The subscription is reference-counted: only the first mounted instance attaches
 * listeners, and the last one to unmount detaches them. That keeps the measurement
 * running across route changes without tearing down and re-adding on every screen.
 */
export function TelegramViewport({ children }: { children?: React.ReactNode }) {
  useEffect(start, []);

  /*
   * Android grants fullscreen only from a user activation, so the request made during
   * initialisation can be refused. The first real tap in the app is the earliest
   * legitimate moment to retry - and it costs nothing when it is already fullscreen.
   */
  useEffect(() => {
    const onFirstGesture = () => {
      requestFullscreenFromGesture();
      window.removeEventListener('pointerdown', onFirstGesture);
      window.removeEventListener('keydown', onFirstGesture);
    };
    window.addEventListener('pointerdown', onFirstGesture, { once: true, passive: true });
    window.addEventListener('keydown', onFirstGesture, { once: true });
    return () => {
      window.removeEventListener('pointerdown', onFirstGesture);
      window.removeEventListener('keydown', onFirstGesture);
    };
  }, []);

  return <>{children}</>;
}

export default TelegramViewport;
