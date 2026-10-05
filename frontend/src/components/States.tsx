import type { ReactNode } from 'react';

import { useI18n } from '@/i18n';

/**
 * Loading, error and empty states.
 *
 * Every screen reaches for the same three, so they live together and look the same
 * everywhere. The rules they follow are the accessibility ones:
 *
 * * an error has `role="alert"` and a real retry control - a failure the player cannot act
 *   on is worse than no message at all, because it looks like the button just stopped
 *   working;
 * * a spinner carries a text label, not just motion, so the state is announced;
 * * an empty state says what would fill it, not just "nothing here".
 */

export function LoadingSpinner({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 py-10 text-white/50"
      role="status"
      aria-live="polite"
    >
      <svg className="h-6 w-6 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden>
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="2.5" />
        <path
          d="M21 12a9 9 0 0 0-9-9"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
      </svg>
      <span className="t-caption">{label ?? t('common.loading')}</span>
    </div>
  );
}

/**
 * A failure with a way out.
 *
 * `onRetry` is rendered as a real button whenever it is supplied, and the message is
 * announced rather than only shown.
 */
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  const { t } = useI18n();
  return (
    <div
      className="flex flex-col items-center gap-3 rounded-[18px] border border-rose-400/20 bg-rose-500/[0.07] px-4 py-6 text-center"
      role="alert"
    >
      <span className="text-[20px]" aria-hidden>
        ⚠
      </span>
      <p className="t-caption text-rose-100/90">{message}</p>
      {onRetry ? (
        <button type="button" className="btn-ghost !min-h-[44px] !px-5" onClick={onRetry}>
          {t('common.tryAgain')}
        </button>
      ) : null}
    </div>
  );
}

/** Nothing here yet - plus what would change that. */
export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: string;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2.5 rounded-[18px] border border-dashed border-white/[0.08] px-4 py-9 text-center">
      <span className="text-[26px] leading-none opacity-60" aria-hidden>
        {icon ?? '◎'}
      </span>
      <p className="t-body font-semibold text-white/80">{title}</p>
      {hint ? <p className="max-w-[36ch] t-caption text-white/40">{hint}</p> : null}
      {action}
    </div>
  );
}

/** A placeholder row, shaped like the real thing so the layout does not jump. */
export function SkeletonRow() {
  return (
    <div className="glass flex items-center gap-3 p-2.5" aria-hidden>
      <div className="h-[42px] w-[104px] shrink-0 animate-pulse rounded-xl bg-white/[0.06]" />
      <div className="flex-1 space-y-2">
        <div className="h-2.5 w-1/3 animate-pulse rounded bg-white/[0.07]" />
        <div className="h-2.5 w-2/3 animate-pulse rounded bg-white/[0.05]" />
      </div>
    </div>
  );
}
