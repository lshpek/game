import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

import { useI18n } from '@/i18n';
import { DURATION, EASE } from '@/lib/motion';

/**
 * In-app feedback.
 *
 * The alternative this replaces is `window.alert()`, and the difference matters on a
 * phone: a native alert freezes the webview, covers Telegram's own chrome, stacks if
 * two fire at once, cannot be styled, and on Android shows its buttons *below* the
 * gesture bar. It is the single most jarring thing a Mini App can do.
 *
 * A toast lives inside the app's own layout, respects the safe area and the navigation,
 * is announced rather than popped, and never blocks a tap.
 */

export interface ToastMessage {
  id: number;
  text: string;
  tone: 'info' | 'ok' | 'error';
}

let nextId = 1;
const listeners = new Set<(message: ToastMessage) => void>();

/**
 * Show a message.
 *
 * A module-level bus rather than context: any component - a mutation three levels deep -
 * can report a failure without the shell having to thread a callback through every
 * screen. Errors are the case that matters, because a silently failed action is worse
 * than a failed one.
 */
export function notify(text: string, tone: ToastMessage['tone'] = 'info'): void {
  const message: ToastMessage = { id: nextId++, text, tone };
  for (const listener of listeners) listener(message);
}

export function notifyError(error: unknown, fallback: string): void {
  notify(
    error instanceof Error && error.message ? error.message : fallback,
    'error',
  );
}

export function ToastHost({ max = 3 }: { max?: number }) {
  const { t } = useI18n();
  const [messages, setMessages] = useState<ToastMessage[]>([]);

  useEffect(() => {
    const listener = (message: ToastMessage) => {
      setMessages((current) => [...current, message].slice(-max));
    };
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, [max]);

  useEffect(() => {
    if (messages.length === 0) return undefined;
    // The last toast lives longer than the rest, because it is the one the player has
    // just triggered.
    const timer = window.setTimeout(
      () => setMessages((current) => current.slice(1)),
      messages.length === 1 ? 4200 : 2600,
    );
    return () => window.clearTimeout(timer);
  }, [messages]);

  if (messages.length === 0) return null;

  return (
    <div
      className="pointer-events-none fixed inset-x-0 z-[80] flex flex-col items-center gap-2 px-4"
      style={{
        // Above the header and clear of the navigation and the gesture area.
        top: 'calc(var(--tg-safe-top) + 12px)',
      }}
      role="region"
      aria-label={t('app.notifications')}
      data-testid="toast-host"
    >
      <AnimatePresence initial={false}>
        {messages.map((message) => (
          <motion.div
            key={message.id}
            className="pointer-events-auto flex w-full max-w-[420px] items-start gap-2.5 rounded-2xl border px-3.5 py-2.5 text-left shadow-lift backdrop-blur-xl"
            style={{
              borderColor:
                message.tone === 'error'
                  ? 'rgba(251,113,133,0.35)'
                  : message.tone === 'ok'
                    ? 'rgba(52,211,153,0.3)'
                    : 'rgba(255,255,255,0.12)',
              background:
                message.tone === 'error'
                  ? 'rgba(60,18,24,0.94)'
                  : message.tone === 'ok'
                    ? 'rgba(10,44,34,0.94)'
                    : 'rgba(15,19,32,0.94)',
            }}
            initial={{ opacity: 0, y: -12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: DURATION.slide, ease: EASE.out }}
            role={message.tone === 'error' ? 'alert' : 'status'}
            data-testid={`toast-${message.tone}`}
          >
            <span aria-hidden className="mt-px shrink-0 text-[13px] leading-none">
              {message.tone === 'error' ? '⚠' : message.tone === 'ok' ? '✓' : 'ℹ'}
            </span>
            <span className="t-caption min-w-0 break-words text-white/90">{message.text}</span>
            <button
              type="button"
              onClick={() =>
                setMessages((current) => current.filter((item) => item.id !== message.id))
              }
              aria-label={t('common.dismiss')}
              className="-mr-1 ml-auto shrink-0 self-start rounded-md px-1 text-[13px] leading-none text-white/40 transition active:scale-90"
            >
              ✕
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

export default ToastHost;
