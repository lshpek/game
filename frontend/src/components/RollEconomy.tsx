import { useEffect, useMemo, useState } from 'react';

import { useI18n, useT } from '../i18n';
import { DURATION, EASE, useReducedMotion } from '../lib/motion';
import type { DailyStatus, NextTarget, RollBalance } from '../types';

/**
 * Roll-economy presentation.
 *
 * The numbers all come from the server: the normal bank, the bonus bank, the cap and
 * the instant the next passive roll lands. This file only *renders* them and counts the
 * seconds down. It never grants a roll, never recomputes the cap, and never decides the
 * economy - the countdown is a display convenience, and the server settles every roll
 * against its own clock.
 */

/** Local mirror of the server's countdown, re-synced whenever the server value changes. */
function useCountdown(target: string | null, serverSeconds: number): number | null {
  const [remaining, setRemaining] = useState<number | null>(serverSeconds || null);

  useEffect(() => {
    if (!target) {
      setRemaining(null);
      return;
    }
    const until = Date.parse(target);
    if (Number.isNaN(until)) {
      setRemaining(serverSeconds || null);
      return;
    }
    const tick = () => {
      const left = Math.max(0, Math.round((until - Date.now()) / 1000));
      setRemaining(left);
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [target, serverSeconds]);

  return remaining;
}

/** `1h 04m` / `32m` / `0:07` - short enough for a button, precise enough to be honest. */
export function formatCountdown(seconds: number): string {
  if (seconds <= 0) return '0:00';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, '0')}m`;
  if (minutes > 0) return `${minutes}m`;
  return `0:${String(rest).padStart(2, '0')}`;
}

/**
 * Normalise either economy payload.
 *
 * The hunt screen reads `/garage`, the profile reads `/daily`, and both describe the
 * same server-authoritative economy. Normalising here means the two screens can never
 * drift apart in what they show the player.
 */
function toBalance(
  rolls: RollBalance | DailyStatus | null,
): RollBalance | null {
  if (!rolls) return null;
  if ('bank_cap' in rolls) return rolls;
  return {
    rolls_remaining: rolls.rolls_remaining,
    normal_rolls: rolls.normal_rolls,
    bonus_rolls: rolls.bonus_rolls,
    daily_allowance: rolls.daily_allowance,
    bank_cap: rolls.daily_allowance,
    resets_at: rolls.resets_at,
    next_roll_at: rolls.next_roll_at,
    seconds_to_next_roll: rolls.seconds_to_next_roll,
    regen_minutes: rolls.regen_minutes,
  };
}

/**
 * The roll balance, as the player reads it.
 *
 * `18 ROLLS` and, when a passive roll is pending, `+1 IN 32 MIN`. Bonus rolls are shown
 * separately and only when there are any, so the normal bank never looks inflated.
 */
export function RollBalanceLine({
  rolls,
  className = '',
  compact = false,
}: {
  rolls: RollBalance | DailyStatus | null;
  className?: string;
  compact?: boolean;
}) {
  const t = useT();
  const balance = toBalance(rolls);
  const remaining = useCountdown(balance?.next_roll_at ?? null, balance?.seconds_to_next_roll ?? 0);

  if (!balance) return null;
  const total = balance.rolls_remaining;
  const empty = total <= 0;

  return (
    <div className={`space-y-0.5 text-center ${className}`}>
      <div
        className={`font-display font-bold tracking-[0.16em] ${
          empty ? 'text-rose-300' : 'text-white/85'
        } ${compact ? 'text-xs' : 'text-sm'}`}
      >
        {total} {t('hunt.rolls')}
      </div>
      {remaining !== null && remaining > 0 && (
        <div className="text-[11px] tracking-wide text-white/45">
          +1 {t('hunt.nextRollIn')} {formatCountdown(remaining)}
        </div>
      )}
      {balance.bonus_rolls > 0 && (
        <div className="text-[11px] font-semibold tracking-wide text-accent-soft">
          +{balance.bonus_rolls} {t('hunt.bonus')}
        </div>
      )}
      {empty && (
        <div className="text-[11px] tracking-wide text-white/45">{t('hunt.noRolls')}</div>
      )}
    </div>
  );
}

/** The compact form used inside the roll button. */
export function CountdownPill({
  rolls,
  className = '',
}: {
  rolls: RollBalance | null;
  className?: string;
}) {
  const t = useT();
  const remaining = useCountdown(rolls?.next_roll_at ?? null, rolls?.seconds_to_next_roll ?? 0);
  if (!rolls || remaining === null || remaining <= 0) return null;
  return (
    <span className={`text-[11px] font-semibold tracking-wide ${className}`}>
      +1 {t('hunt.in')} {formatCountdown(remaining)}
    </span>
  );
}

/**
 * The single next objective.
 *
 * Exactly one sentence, assembled from the machine-readable code the backend sent. All
 * the copy lives in i18n, so the sentence is localised and the backend never has to know
 * about language.
 */
export function NextTargetLine({
  target,
  className = '',
}: {
  target: NextTarget | null | undefined;
  className?: string;
}) {
  const { lang } = useI18n();
  const t = useT();
  const reduced = useReducedMotion();

  const text = useMemo(() => {
    if (!target) return '';
    switch (target.code) {
      case 'country_set': {
        const section =
          (lang === 'ru' ? target.section_name_ru : target.section_name_en) ?? (target.section_code ?? '');
        return t('goal.countrySet', { n: target.remaining, section, country: target.country_flag });
      }
      case 'country_region':
        return target.remaining === 1
          ? t('goal.firstRegion', { country: target.country_flag })
          : t('goal.moreRegions', { n: target.remaining, country: target.country_flag });
      case 'country_operator':
        return t('goal.operators', { n: target.remaining });
      case 'mission':
        return t('goal.mission', { n: target.remaining });
      case 'album':
        return t('goal.album', { n: target.remaining });
      case 'rarity':
        return t('goal.findRarity', { rarity: target.rarity ?? 'RARE' });
      case 'first_discovery':
        return t('goal.firstDiscovery');
      case 'collection':
        return t('goal.firstCollectible');
      default:
        return t('goal.keepRolling');
    }
  }, [target, t, lang]);

  if (!text) return null;

  return (
    <p
      className={`flex items-center justify-center gap-1.5 text-center text-[11px] leading-snug tracking-wide text-white/50 ${className}`}
      style={{ transition: reduced ? undefined : `opacity ${DURATION.fade}s ${EASE.out}` }}
    >
      <span aria-hidden className="text-accent-soft">
        ◆
      </span>
      {text}
    </p>
  );
}

export default RollBalanceLine;