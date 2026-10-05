import { useEffect, useMemo, useState } from 'react';

import { useT } from '@/i18n';
import { DURATION, EASE, SPRING, formatCountdown, useReducedMotion } from '@/lib/motion';
import type { NextTarget, RollBalance } from '@/types';

/**
 * The bank, rendered from the server's authoritative state.
 *
 * The contract is simple and strict: this component only ever *displays* the bank the
 * backend returned. It does not compute a refill time, does not decrement a counter on a
 * timer, and does not guess how many rolls the player has. If the server says there are
 * 18 rolls, this shows 18; if it says the next arrives at `next_roll_at`, this counts down
 * to that instant and nothing else.
 *
 * That distinction is the whole point. A locally invented refill time means the number on
 * the hunt screen can disagree with the number the next request would honour - the kind of
 * discrepancy a player notices immediately and reads as a bug in the economy.
 */

/**
 * Seconds until the next roll, from the server's own timestamp.
 *
 * Derived from `next_roll_at` rather than from a local interval, so a player who leaves
 * the app open and comes back sees the number the server would quote.
 */
function secondsUntil(rolls: RollBalance | null): number | null {
  if (!rolls?.next_roll_at) return null;
  const target = new Date(rolls.next_roll_at).getTime();
  if (Number.isNaN(target)) return null;
  const delta = Math.round((target - Date.now()) / 1000);
  return delta > 0 ? delta : 0;
}

/**
 * A live countdown to the next passive roll.
 *
 * Ticks once a second through a single interval and writes to state only when the
 * displayed string actually changes - so 59 seconds of ticking cost 60 renders, not 3000.
 */
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
        // No re-render for an unchanged string.
        return formatted === current ? current : formatted;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [rolls]);

  return display;
}

/** A one-line read of the bank: how many rolls, and when the next one arrives. */
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
    // Absent data reads as absent, never as zero.
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
      {/* The count, in words, so it reads as "18 rolls" rather than a bare numeral. */}
      <span className="number-display text-[15px] font-bold text-white">
        {t('hunt.rollsCount', { n: rolls.rolls_remaining })}
      </span>
      {/* A bonus bank is a distinct thing from the normal one, so it is labelled rather
          than silently merged into the main number. */}
      {rolls.bonus_rolls > 0 ? (
        <span className="t-micro text-brass">+{rolls.bonus_rolls} {t('hunt.bonusRolls')}</span>
      ) : null}
      {countdown ? (
        <span className="t-micro tabular-nums text-white/30" data-testid="roll-countdown">
          {t('hunt.nextRollIn')} {countdown}
        </span>
      ) : null}
    </div>
  );
}

/**
 * The countdown, for use inside a control.
 *
 * Rendered only when the server actually said when the next roll arrives. Inventing a
 * refill time would put a number on screen the economy does not honour.
 */
export function CountdownPill({ rolls, className = '' }: { rolls: RollBalance | null; className?: string }) {
  const countdown = useRefillCountdown(rolls);
  if (!countdown) return null;
  return (
    <span className={`t-micro tabular-nums ${className}`} aria-hidden>
      {countdown}
    </span>
  );
}

/**
 * The single next objective.
 *
 * A goal, a count and a progress bar - one line, always. The backend sends one objective
 * at a time on purpose: a screenful of missions is a to-do list, and the hunt screen needs
 * one thing to pull towards.
 */
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
    <div className="flex w-full flex-col gap-1.5" data-testid="next-target">
      <div className="flex items-center gap-2">
        <span className="eyebrow">{t('hunt.objective')}</span>
        {target?.current !== undefined ? (
          <span className="number-display text-[11px] tabular-nums text-white/40">
            {target.current}/{target.target}
          </span>
        ) : null}
      </div>
      <p className="t-caption text-white/60">{message}</p>
      <div className="h-1 overflow-hidden rounded-full bg-white/[0.07]">
        <div
          className="h-full rounded-full bg-gradient-to-r from-accent/60 to-brass/60"
          style={{
            width: `${Math.max(progress * 100, 2)}%`,
            transition: reduced
              ? 'none'
              : `width ${DURATION.slide}s ${EASE.out}`,
          }}
        />
      </div>
    </div>
  );
}

export { formatCountdown };

/** Kept so the spring vocabulary for the objective bar stays in one place. */
export const OBJECTIVE_SPRING = SPRING.settle;
