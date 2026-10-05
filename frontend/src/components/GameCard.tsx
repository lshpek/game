import type { ReactNode } from 'react';

import { useI18n } from '@/i18n';

/**
 * The shared UI primitives.
 *
 * Every screen in the app draws from this one set, and each primitive has a single
 * visual job. That matters more than it sounds: when six different screens each invent
 * their own header treatment, the app reads as six different apps stitched together, and
 * on a phone that shows up immediately as inconsistency.
 *
 * The surfaces here are deliberately distinct from one another:
 *
 * | primitive | reads as |
 * | --- | --- |
 * | `PageHeader` | the screen's name, its one subtitle, one action |
 * | `Stat` | a single number with a label |
 * | `StatGrid` | a row of stats, wrapped at any width |
 * | `LevelBar` | progress toward a level |
 * | `GameCard` | a quiet container for related controls |
 * | `Section` | a titled group of `GameCard`s |
 */

interface PageHeaderProps {
  title: string;
  subtitle?: ReactNode;
  /** Rendered on the right, typically a single icon or count. */
  action?: ReactNode;
}

/**
 * A screen's own heading.
 *
 * Fixed height and `truncate`, because a long localised title - Russian country names run
 * long - must not push the content below it down and make the layout jump between screens.
 */
export function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <header className="flex min-h-[52px] items-center gap-3 px-1">
      <div className="min-w-0 flex-1">
        <h1 className="truncate t-h1 text-white">{title}</h1>
        {subtitle ? (
          <p className="mt-0.5 truncate t-caption text-white/45">{subtitle}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}

interface StatProps {
  label: string;
  value: string | number;
  /** Accent for the value. Defaults to plain white; brass marks money. */
  tone?: string;
  className?: string;
}

/** A single number with a label. Numerals are tabular so they do not jitter as they change. */
export function Stat({ label, value, tone, className = '' }: StatProps) {
  return (
    <div className={`stat ${className}`}>
      <span className={`number-display text-[19px] font-bold ${tone ?? 'text-white'}`}>{value}</span>
      <span className="t-micro max-w-full truncate text-white/35">{label}</span>
    </div>
  );
}

/** A wrapping row of stats. Two or three per row on a phone, more as space allows. */
export function StatGrid({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`grid grid-cols-2 gap-2 sm:grid-cols-3 ${className}`}>{children}</div>;
}

/** A labelled progress bar. Colour is semantic: green when complete, brass while in progress. */
export function LevelBar({ progress, className = '' }: { progress: number; className?: string }) {
  const pct = Math.max(0, Math.min(1, progress));
  return (
    <div
      className={`h-2 overflow-hidden rounded-full bg-white/[0.08] ${className}`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct * 100)}
    >
      <div
        className={`h-full rounded-full transition-[width] duration-500 ${
          pct >= 1 ? 'bg-emerald-400' : 'bg-gradient-to-r from-accent/70 to-brass/70'
        }`}
        style={{ width: `${Math.max(pct * 100, 1)}%` }}
      />
    </div>
  );
}

interface GameCardProps {
  children: ReactNode;
  /** Optional left accent rule. Reserved for genuinely special surfaces. */
  accent?: string;
  className?: string;
}

/**
 * A quiet container.
 *
 * Thin border, very low fill, no shadow: a card's job is to group, not to be noticed. The
 * loudest surface in the app is the roll button, and it should stay that way.
 */
export function GameCard({ children, accent, className = '' }: GameCardProps) {
  return (
    <div
      className={`rounded-[18px] border border-white/[0.07] bg-white/[0.03] p-3.5 ${className}`}
      style={accent ? { borderLeft: `3px solid ${accent}` } : undefined}
    >
      {children}
    </div>
  );
}

/** A titled group of cards, with a hairline instead of a big tracking label. */
export function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="space-y-2.5">
      <div className="flex items-center justify-between gap-3 px-1">
        <h2 className="eyebrow">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

/**
 * A progress bar with a label and a trailing value.
 *
 * `ProgressBar` is a thin rule with text either side rather than a filled capsule: it sits
 * next to real content most of the time, and a capsule would compete with it.
 */
export function ProgressBar({
  value,
  max,
  label,
  trailing,
}: {
  value: number;
  max: number;
  label: string;
  trailing?: string;
}) {
  const progress = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="eyebrow">{label}</span>
        {trailing ? (
          <span className="number-display shrink-0 text-[12px] font-semibold text-white/60">
            {trailing}
          </span>
        ) : null}
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-white/[0.08]"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(progress * 100)}
        aria-label={label}
      >
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${
            progress >= 1 ? 'bg-emerald-400' : 'bg-gradient-to-r from-accent/70 to-brass/70'
          }`}
          style={{ width: `${Math.max(progress * 100, 1)}%` }}
        />
      </div>
    </div>
  );
}

/** Standard input: a real 46px control with a visible focus ring. */
export const INPUT =
  'min-h-[46px] w-full min-w-0 rounded-2xl border border-white/[0.09] bg-white/[0.04] px-3.5 text-body text-white outline-none placeholder:text-white/30 focus:border-accent/60';

/** The empty/loading/error trio, shared so every screen fails the same way. */
export function LoadingBlock({ label }: { label: string }) {
  const { t } = useI18n();
  return <p className="py-6 text-center t-caption text-white/35">{label || t('common.loading')}</p>;
}
