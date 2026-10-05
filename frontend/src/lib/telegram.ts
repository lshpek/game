/**
 * The Telegram WebApp surface NUMORA actually runs on.
 *
 * Everything here exists because a Telegram Mini App is *not* a browser page: the
 * client owns the viewport, changes it without a navigation, and reports its real
 * size through the SDK. A page that assumes the browser owns layout gets it wrong
 * on Android in four different ways at once:
 *
 * 1. **Header / status bar.** When the Mini App is not fullscreen, Telegram draws a
 *    header above the webview. The webview's own `0px` is *below* it, so content at
 *    `padding-top: 0` sits under the Telegram header, not under the notch.
 * 2. **Gesture / navigation area.** `env(safe-area-inset-bottom)` is frequently `0`
 *    inside a Mini App even with a physical gesture bar present, because the webview
 *    is already inset by the client. Trusting the CSS variable alone leaves the last
 *    row of content under the system bar.
 * 3. **Fullscreen transition.** `expand()` and `requestFullscreen()` both resize the
 *    webview *after* they are called. A layout that measured once at mount is wrong
 *    from that moment on, and `100vh` never corrects itself.
 * 4. **Keyboard.** Telegram's keyboard is a separate window: it shrinks the
 *    `visualViewport`, not `innerHeight`. Any element pinned to the bottom must move,
 *    or the sheet the player is typing in is covered.
 *
 * So this module publishes the truth as CSS custom properties on `:root`, and the
 * whole UI is laid out against those variables (see index.css). One measurement,
 * one place, every screen correct.
 */

/** The subset of the SDK this app depends on, plus the newer APIs it probes for. */
export interface TelegramWebApp {
  initData: string;
  initDataUnsafe?: {
    start_param?: string;
    user?: { id: number; username?: string };
    language_code?: string;
  };
  colorScheme: 'light' | 'dark';
  themeParams: Record<string, string>;
  platform: string;
  version: string;
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  /** BotFather's "fullscreen" setting, honoured by clients that support it. */
  isFullscreen?: boolean;
  /** Present only on clients that implement Bot API 9.x fullscreen. */
  isVersionChanged?: boolean;
  fullscreenChanged?: { id: number; active: boolean };
  ready(): void;
  expand(): void;
  close(): void;
  /** Optional: absent on older clients. */
  setHeaderColor?(color: string): void;
  /** Optional: absent on older clients. */
  setBackgroundColor?(color: string): void;
  setViewportHeight?(height: number, velocity?: number): void;
  disableVerticalSwipes?(): void;
  enableVerticalSwipes?(): void;
  requestFullscreen?(): void;
  exitFullscreen?(): void;
  onEvent(event: string, handler: (...args: never[]) => void): void;
  offEvent(event: string, handler: (...args: never[]) => void): void;
  HapticFeedback?: {
    impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void;
    notificationOccurred(type: 'error' | 'success' | 'warning'): void;
    selectionChanged(): void;
  };
  BackButton?: {
    isVisible?: boolean;
    show(): void;
    hide(): void;
    onClick(handler: () => void): void;
    offClick(handler: () => void): void;
  };
  MainButton?: {
    text: string;
    isVisible?: boolean;
    show(): void;
    hide(): void;
    setText?(text: string): void;
    onClick(handler: () => void): void;
    offClick(handler: () => void): void;
  };
  showAlert?(message: string): void;
  openTelegramLink?(url: string): void;
  shareToStory?(mediaUrl: string, params?: Record<string, unknown>): void;
  openLink?(url: string, options?: Record<string, unknown>): void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

/**
 * The SDK, or `null` in a plain browser (local dev, tests, desktop web).
 *
 * Read lazily rather than captured at module load. The SDK script tag is synchronous and
 * runs first in production, but a deferred or failed load is exactly the case where the app
 * must degrade gracefully instead of holding a stale reference - and reading it through a
 * getter is what lets that be tested at all.
 */
let cached: TelegramWebApp | null | undefined;
export function getTelegram(): TelegramWebApp | null {
  if (cached === undefined) {
    cached = (typeof window !== 'undefined' ? window.Telegram?.WebApp : undefined) ?? null;
  }
  return cached;
}

export function setTelegram(app: TelegramWebApp | null): void {
  // Also mirrors onto `window`, so a test that installs a fake client exercises the same
  // code path a real client does rather than a private channel.
  if (typeof window !== 'undefined') {
    window.Telegram = app ? { WebApp: app } : undefined;
  }
  cached = app;
}

export const telegram: TelegramWebApp | null = getTelegram();

export const isTelegram = (): boolean => Boolean(getTelegram()?.initData);

/** Whether this client can enter BotFather fullscreen at all. */
export const supportsFullscreen = (): boolean =>
  typeof getTelegram()?.requestFullscreen === 'function';

export const isFullscreen = (): boolean => Boolean(getTelegram()?.isFullscreen);

/* ---------------------------------------------------------------------------
 * Capability detection
 * --------------------------------------------------------------------------- */

/**
 * `isAtLeast` against the SDK version string.
 *
 * Telegram versions are dotted and sometimes carry a suffix (`"7.10"`, `"8.0-beta"`).
 * Only the numeric prefix is compared, so an unparseable string means "assume new
 * enough" rather than "never call the API" - probing a missing method is harmless,
 * but skipping one that exists leaves the layout wrong.
 */
export function isAtLeast(version: string): boolean {
  const app = getTelegram();
  if (!app) return true;
  const parse = (value: string) =>
    value
      .split('.')
      .slice(0, 2)
      .map((part) => Number.parseInt(part, 10))
      .map((n) => (Number.isFinite(n) ? n : 0));
  const [currentMajor = 0, currentMinor = 0] = parse(app.version);
  const [wantMajor = 0, wantMinor = 0] = parse(version);
  if (currentMajor !== wantMajor) return currentMajor > wantMajor;
  return currentMinor >= wantMinor;
}

/* ---------------------------------------------------------------------------
 * Initialisation
 * --------------------------------------------------------------------------- */

/**
 * The client instance `initTelegram` last prepared.
 *
 * Keyed by identity rather than a boolean, so initialisation happens once *per client*: a
 * client that is torn down and replaced - which is what a reopened Mini App looks like -
 * gets prepared again, while a second call against the same client is a no-op.
 */
let preparedFor: TelegramWebApp | null | undefined;

/**
 * Bring the Mini App up.
 *
 * The order matters and is not interchangeable:
 *
 * * `ready()` first - Telegram shows its own loading frame until this is called, so
 *   anything after it can paint.
 * * `expand()` next - grows the webview to the full sheet.
 * * `requestFullscreen()` last, and only if it exists. Older clients simply do not have
 *   it, and calling it unconditionally would throw inside the try/catch and skip the
 *   colour setup, leaving the app framed by a white header.
 *
 * `disableVerticalSwipes()` is deliberately *not* called: it blocks the swipe that closes
 * the Mini App, and this app has its own bottom sheet that needs the gesture.
 */
export function initTelegram(): void {
  const app = getTelegram();
  if (preparedFor === app) return;
  preparedFor = app;
  if (!app) return;
  try {
    app.ready();
    app.expand();
  } catch {
    // A partially supported client must never break the app.
  }
  try {
    app.requestFullscreen?.();
  } catch {
    // Fullscreen is a progressive enhancement: the fallback is the normal sheet.
  }
  try {
    app.setHeaderColor?.('#05070c');
    app.setBackgroundColor?.('#05070c');
  } catch {
    // Older clients lack these.
  }
  app.MainButton?.hide?.();
}

/**
 * Re-assert fullscreen after a user gesture.
 *
 * Android only grants fullscreen from a real user activation, so the call made during
 * initialisation can be rejected on some clients. The shell retries once, from the
 * first tap, which is the earliest moment a gesture exists.
 */
export function requestFullscreenFromGesture(): void {
  const app = getTelegram();
  const request = app?.requestFullscreen;
  if (!app || !request || isFullscreen()) return;
  try {
    request.call(app);
  } catch {
    /* not permitted on this client */
  }
}

/* ---------------------------------------------------------------------------
 * Runtime state
 * --------------------------------------------------------------------------- */

export interface ViewportState {
  /** Height the client says the Mini App occupies, in CSS pixels. */
  height: number;
  /** Height that does not move while the keyboard animates. */
  stableHeight: number;
  /** How much of the bottom is currently covered by the keyboard. */
  keyboard: number;
  /** Whether the client is in fullscreen. */
  fullscreen: boolean;
  /** Whether the values above came from the SDK or from a CSS/visual fallback. */
  source: 'telegram' | 'visual-viewport' | 'css';
}

/**
 * Read the viewport once, preferring the most trustworthy source available.
 *
 * `viewportHeight` from the SDK is authoritative inside Telegram. The visual viewport
 * is the fallback for clients that report a stale value, and CSS units are the last
 * resort outside Telegram entirely.
 */
export function readViewport(): ViewportState {
  const visual = typeof window !== 'undefined' ? window.visualViewport : null;

  const keyboard =
    visual && typeof window.innerHeight === 'number'
      ? Math.max(0, Math.round(window.innerHeight - visual.height - visual.offsetTop))
      : 0;

  const app = getTelegram();
  if (app && Number.isFinite(app.viewportHeight) && app.viewportHeight > 0) {
    const stable =
      Number.isFinite(app.viewportStableHeight) && app.viewportStableHeight > 0
        ? app.viewportStableHeight
        : app.viewportHeight;
    return {
      height: Math.round(app.viewportHeight),
      stableHeight: Math.round(stable),
      keyboard: Math.max(keyboard, 0),
      fullscreen: Boolean(app.isFullscreen),
      source: 'telegram',
    };
  }

  if (visual && visual.height > 0) {
    return {
      height: Math.round(visual.height),
      stableHeight: Math.round(visual.height),
      keyboard: Math.max(keyboard, 0),
      fullscreen: false,
      source: 'visual-viewport',
    };
  }

  const css = typeof window !== 'undefined' ? window.innerHeight : 0;
  return {
    height: Math.round(css),
    stableHeight: Math.round(css),
    keyboard: 0,
    fullscreen: false,
    source: 'css',
  };
}

/* ---------------------------------------------------------------------------
 * Haptics
 * --------------------------------------------------------------------------- */
type HapticImpact = 'light' | 'medium' | 'heavy' | 'rigid' | 'soft';

export function haptic(style: HapticImpact = 'light'): void {
  try {
    getTelegram()?.HapticFeedback?.impactOccurred?.(style);
  } catch {
    /* unsupported client */
  }
}

export function hapticSuccess(): void {
  try {
    getTelegram()?.HapticFeedback?.notificationOccurred?.('success');
  } catch {
    /* unsupported client */
  }
}

export function hapticError(): void {
  try {
    getTelegram()?.HapticFeedback?.notificationOccurred?.('error');
  } catch {
    /* unsupported client */
  }
}

/**
 * Haptics tuned to the moment they belong to.
 *
 * The product rule is that *touch confirms the action, and rarity confirms the reward*,
 * so a common find stays calm and a legendary one escalates. Each pattern is a short,
 * bounded sequence - never a long buzz and never anything that fires on a loop.
 */
export type HapticCue =
  /** Any button press. */
  | 'tap'
  /** A roll starts. */
  | 'roll'
  /** The collectible settles into place. */
  | 'lock'
  /** RARE and above. */
  | 'rare'
  /** LEGENDARY and above. */
  | 'legendary'
  /** Something the player must notice went wrong. */
  | 'error'
  /** A reward landed. */
  | 'success';

const CUES: Record<HapticCue, () => void> = {
  tap: () => haptic('light'),
  roll: () => haptic('medium'),
  lock: () => haptic('heavy'),
  rare: () => {
    haptic('medium');
    haptic('heavy');
  },
  legendary: () => {
    haptic('heavy');
    haptic('heavy');
    hapticSuccess();
  },
  error: () => hapticError(),
  success: () => hapticSuccess(),
};

/** Fire a named haptic cue. Never throws, whatever the client supports. */
export function hapticCue(cue: HapticCue): void {
  CUES[cue]();
}

/* ---------------------------------------------------------------------------
 * Links and sharing
 * --------------------------------------------------------------------------- */

/** Invite/share helpers - all deep links are produced by the backend. */
export function openTelegramLink(url: string): void {
  const app = getTelegram();
  if (app?.openTelegramLink) {
    app.openTelegramLink(url);
    return;
  }
  window.open(url, '_blank', 'noopener');
}

export function shareToChat(url: string, text: string): void {
  const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
  openTelegramLink(shareUrl);
}

export function openLink(url: string): void {
  const app = getTelegram();
  if (app?.openLink) {
    app.openLink(url, { try_instant_view: false });
    return;
  }
  window.open(url, '_blank', 'noopener');
}

export function alert(message: string): void {
  const alert = getTelegram()?.showAlert;
  if (alert) {
    alert.call(getTelegram(), message);
    return;
  }
  window.alert(message);
}

/* ---------------------------------------------------------------------------
 * Telegram's header back arrow
 * --------------------------------------------------------------------------- */

/**
 * Exactly one owner at a time.
 *
 * The Mini App has no browser chrome, so without this a sub-screen is a dead end: the
 * player can only ever tap the bottom nav. The button is registered on mount and hidden
 * again on unmount, which keeps a single owner - two handlers would both fire and the
 * player would bounce between screens.
 */
export function showBackButton(onClick: () => void): () => void {
  const button = getTelegram()?.BackButton;
  if (!button) return () => {};
  try {
    button.onClick(onClick);
    button.show();
  } catch {
    return () => {};
  }
  return () => {
    try {
      button.offClick(onClick);
      button.hide();
    } catch {
      // A partially supported client must never break navigation.
    }
  };
}

export function hideBackButton(): void {
  try {
    getTelegram()?.BackButton?.hide();
  } catch {
    // Unsupported client.
  }
}

export function getInitData(): string {
  return getTelegram()?.initData ?? '';
}

/** Deep-link parameter, preferring the verified initData value. */
export function getStartParam(): string | null {
  const fromSdk = getTelegram()?.initDataUnsafe?.start_param;
  if (fromSdk) return fromSdk;

  const params = new URLSearchParams(window.location.search);
  return params.get('startapp');
}
