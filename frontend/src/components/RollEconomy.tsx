import { useEffect, useMemo, useState } from 'react';

import { useT } from '@/i18n';
import { DURATION, EASE, SPRING, formatCountdown, useReducedMotion } from '@/lib/motion';
import type { NextTarget, RollBalance } from '@/types';

function secondsUntil(rolls: RollBalance | null): number | null {
  if (!rolls?.next_roll_at) return null;
  const target = new Date(rolls.next_roll_at).getTime();
  if (Number.isNaN(target)) return null;
  const delta = Math.round((target - Date.now()) / 1000);
  return delta > 0 ? delta : 0;
}

export function useRefillCountdown(rolls: RollBalance | null): string | null {
  const [display, setDisplay] = useState<string | null>(null);

  useEffect(() => {
    const initial = secondsUntil(rolls);
    if (initial === null) {
      setDisplay(null);
      return undefined;
    }
    setDisplay(formatCountdown(initial));
    const timer = window.setInterval(() => {
      const next = secondsUntil(rolls);
      if (next === null) return;
      setDisplay((current) => {
        const formatted = formatCountdown(next);
        return formatted === current ? current : formatted;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [rolls]);

  return display;
}

export function RollBalanceLine({
  rolls,
  compact = false,
}: {
  rolls: RollBalance | null;
  compact?: boolean;
}) {
  const t = useT();
  const countdown = useRefillCountdown(rolls);

  if (!rolls) {
    return (
      <p className="t-micro text-white/30" data-testid="roll-balance">
        —
      </p>
    );
  }

  return (
    <div
      className={`flex min-w-0 flex-col ${compact ? 'items-end gap-0.5' : 'items-start gap-1.5'}`}
      data-testid="roll-balance"
    >
      <span className="number-display max-w-full truncate text-[15px] font-bold text-white">
        ⚡ {t('hunt.rollsCount', { n: rolls.rolls_remaining })}
      </span>
      {rolls.bonus_rolls > 0 ? (
        <span className="rounded-md border border-brass/30 bg-brass/10 px-1.5 py-0.5 t-micro text-brass-soft">
          +{rolls.bonus_rolls} {t('hunt.bonusRolls')}
        </span>
      ) : null}
      {countdown ? (
        <span className="t-micro tabular-nums text-white/45" data-testid="roll-countdown">
          {t('hunt.nextRollIn')} {countdown}
        </span>
      ) : null}
    </div>
  );
}

export function CountdownPill({
  rolls,
  className = '',
}: {
  rolls: RollBalance | null;
  className?: string;
}) {
  const countdown = useRefillCountdown(rolls);
  if (!countdown) return null;
  return (
    <span className={`t-micro tabular-nums ${className}`} aria-hidden>
      {countdown}
    </span>
  );
}

export function NextTargetLine({ target }: { target: NextTarget | null }) {
  const t = useT();
  const reduced = useReducedMotion();

  const message = useMemo(() => {
    if (!target) return t('hunt.alwaysOneObjective');
    switch (target.code) {
      case 'country_collect':
        return t('hunt.targetMoreRegions', { count: target.remaining });
      case 'country_region':
        return t('hunt.targetMoreRegions', { count: target.remaining });
      case 'first_discovery':
        return t('hunt.targetFirstDiscovery', { country: target.country_name_en });
      case 'album_completion':
        return t('hunt.targetAlbum');
      case 'mission':
        return t('hunt.targetMissions');
      case 'achievement':
        return t('hunt.targetAchievements');
      default:
        return t('hunt.alwaysOneObjective');
    }
  }, [target, t]);

  const progress = Math.max(0, Math.min(1, target?.progress ?? 0));

  return (
    <div
      className="glass flex w-full flex-col gap-1.5 px-3.5 py-2.5"
      data-testid="next-target"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="eyebrow flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block h-1.5 w-1.5 rounded-full bg-brass" />
          {t('hunt.objective')}
        </span>
        {target?.current !== undefined ? (
          <span className="number-display rounded-md border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[11px] font-bold tabular-nums text-brass-soft">
            {target.current}/{target.target}
          </span>
        ) : null}
      </div>
      <p className="t-caption font-medium text-white/80">{message}</p>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
        <div
          className="h-full rounded-full bg-gradient-to-r from-accent via-brass to-amber-300"
          style={{
            width: `${Math.max(progress * 100, 4)}%`,
            transition: reduced ? 'none' : `width ${DURATION.slide}s ${EASE.out}`,
          }}
        />
      </div>
    </div>
  );
}

export { formatCountdown };
export const OBJECTIVE_SPRING = SPRING.settle;
