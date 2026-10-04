/** Telegram WebApp SDK wrapper with a safe browser fallback (local dev). */

type HapticImpact = 'light' | 'medium' | 'heavy' | 'rigid' | 'soft';

interface TelegramWebApp {
  initData: string;
  initDataUnsafe?: { start_param?: string; user?: { id: number; username?: string } };
  colorScheme: 'light' | 'dark';
  themeParams: Record<string, string>;
  platform: string;
  version: string;
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  ready(): void;
  expand(): void;
  close(): void;
  setHeaderColor(color: string): void;
  setBackgroundColor(color: string): void;
  disableVerticalSwipes?(): void;
  requestFullscreen?(): void;
  onEvent(event: string, handler: () => void): void;
  offEvent(event: string, handler: () => void): void;
  HapticFeedback?: {
    impactOccurred(style: HapticImpact): void;
    notificationOccurred(type: 'error' | 'success' | 'warning'): void;
    selectionChanged(): void;
  };
  showAlert?(message: string): void;
  openTelegramLink?(url: string): void;
  shareToStory?(mediaUrl: string, params?: Record<string, unknown>): void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export const telegram: TelegramWebApp | null =
  typeof window !== 'undefined' ? (window.Telegram?.WebApp ?? null) : null;

export const isTelegram = (): boolean => Boolean(telegram?.initData);

export function initTelegram(): void {
  if (!telegram) return;
  try {
    telegram.ready();
    // Fullscreen Mini App: expand to the full viewport height and, where the
    // client supports it, enter immersive fullscreen as well.
    telegram.expand();
    telegram.requestFullscreen?.();
    telegram.setHeaderColor('#05060c');
    telegram.setBackgroundColor('#05060c');
    telegram.disableVerticalSwipes?.();
  } catch {
    // A partially supported client must never break the app.
  }
}

export function getInitData(): string {
  return telegram?.initData ?? '';
}

/** Deep-link parameter, preferring the verified initData value. */
export function getStartParam(): string | null {
  const fromSdk = telegram?.initDataUnsafe?.start_param;
  if (fromSdk) return fromSdk;

  const params = new URLSearchParams(window.location.search);
  return params.get('startapp');
}

export function haptic(style: HapticImpact = 'light'): void {
  try {
    telegram?.HapticFeedback?.impactOccurred(style);
  } catch {
    /* unsupported client */
  }
}

export function hapticSuccess(): void {
  try {
    telegram?.HapticFeedback?.notificationOccurred('success');
  } catch {
    /* unsupported client */
  }
}

export function hapticError(): void {
  try {
    telegram?.HapticFeedback?.notificationOccurred('error');
  } catch {
    /* unsupported client */
  }
}

/** Invite/share helpers - all deep links are produced by the backend. */
export function openTelegramLink(url: string): void {
  if (telegram?.openTelegramLink) {
    telegram.openTelegramLink(url);
    return;
  }
  window.open(url, '_blank', 'noopener');
}

export function shareToChat(url: string, text: string): void {
  const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
  openTelegramLink(shareUrl);
}

export function alert(message: string): void {
  if (telegram?.showAlert) {
    telegram.showAlert(message);
    return;
  }
  window.alert(message);
}
