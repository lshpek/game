import type { ReactNode } from 'react';
import { useI18n } from '@/i18n';

export function LoadingSpinner({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-white/60">
      <svg className="h-7 w-7 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden>
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
        <path
          d="M21 12a9 9 0 0 0-9-9"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
      <span className="text-sm">{label ?? t('common.loading')}</span>
    </div>
  );
}

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  const { t } = useI18n();
  return (
    <div className="glass flex flex-col items-center gap-3 p-6 text-center" role="alert">
      <span className="text-3xl" aria-hidden>
        ⚠️
      </span>
      <p className="text-sm text-white/80">{message}</p>
      {onRetry ? (
        <button type="button" className="btn-ghost" onClick={onRetry}>
          {t('common.tryAgain')}
        </button>
      ) : null}
    </div>
  );
}

interface EmptyStateProps {
  icon?: string;
  title: string;
  hint?: string;
  action?: ReactNode;
}

export function EmptyState({ icon = '🎲', title, hint, action }: EmptyStateProps) {
  return (
    <div className="glass flex flex-col items-center gap-3 p-8 text-center">
      <span className="text-4xl" aria-hidden>
        {icon}
      </span>
      <p className="font-semibold text-white/90">{title}</p>
      {hint ? <p className="max-w-xs text-sm text-white/55">{hint}</p> : null}
      {action}
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="glass flex items-center gap-3 p-4">
      <div className="h-12 w-16 animate-pulse rounded-xl bg-white/10" />
      <div className="flex-1 space-y-2">
        <div className="h-3 w-1/3 animate-pulse rounded bg-white/10" />
        <div className="h-2 w-2/3 animate-pulse rounded bg-white/10" />
      </div>
    </div>
  );
}
