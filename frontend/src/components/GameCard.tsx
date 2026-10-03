import clsx from 'clsx';
import type { HTMLAttributes, ReactNode } from 'react';

interface GameCardProps extends HTMLAttributes<HTMLDivElement> {
  accent?: string;
  glow?: boolean;
}

export function GameCard({ accent, glow = false, className, children, style, ...rest }: GameCardProps) {
  return (
    <div
      className={clsx('glass p-4 shadow-card', className)}
      style={accent ? { borderColor: `${accent}44`, ...style } : style}
      {...rest}
    >
      {glow && accent ? (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-2xl opacity-40 blur-2xl"
          style={{ background: `radial-gradient(circle at 50% 0%, ${accent}55, transparent 70%)` }}
        />
      ) : null}
      {children}
    </div>
  );
}

interface SectionProps {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Section({ title, action, children, className }: SectionProps) {
  return (
    <section className={clsx('space-y-3', className)}>
      <header className="flex items-center justify-between px-1">
        <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-white/50">{title}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}

interface ProgressBarProps {
  value: number;
  max: number;
  accent?: string;
  label?: string;
  trailing?: string;
}

export function ProgressBar({ value, max, accent = '#7c5cff', label, trailing }: ProgressBarProps) {
  const percentage = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div className="space-y-1.5">
      {label || trailing ? (
        <div className="flex items-baseline justify-between text-xs text-white/60">
          <span>{label}</span>
          <span className="font-semibold text-white/85">{trailing}</span>
        </div>
      ) : null}
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-white/10"
        role="progressbar"
        aria-valuenow={Math.round(percentage)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full transition-[width] duration-500 ease-out"
          style={{ width: `${percentage}%`, background: `linear-gradient(90deg, ${accent}, #f472b6)` }}
        />
      </div>
    </div>
  );
}
