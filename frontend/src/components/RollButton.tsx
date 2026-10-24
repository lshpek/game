import { motion } from 'framer-motion';
import clsx from 'clsx';

import { useI18n } from '../i18n';
import { EASE, SPRING, useReducedMotion } from '../lib/motion';
import { playRollStart } from '../lib/sound';
import { hapticCue } from '../lib/telegram';
import { CountdownPill } from './RollEconomy';
import type { RollBalance } from '../types';

interface Props {
  /** The authoritative bank, or `null` while it is still loading. */
  rolls: RollBalance | null;
  onRoll: () => void;
  rolling?: boolean;
  disabled?: boolean;
  size?: 'lg' | 'md';
  className?: string;
  /** Set while a roll request is in flight, to swallow a double tap. */
  locked?: boolean;
}

export default function RollButton({
  rolls,
  onRoll,
  rolling = false,
  disabled = false,
  size = 'lg',
  className = '',
  locked = false,
}: Props) {
  const { t } = useI18n();
  const reduced = useReducedMotion();

  const unknown = rolls === null;
  const total = rolls?.rolls_remaining ?? 0;
  const cap = rolls?.bank_cap ?? 0;
  const empty = !unknown && total <= 0;
  const blocked = disabled || rolling || locked || empty;

  const handleClick = () => {
    if (blocked) return;
    hapticCue('tap');
    playRollStart();
    onRoll();
  };

  const fill = cap > 0 ? Math.max(0, Math.min(1, total / cap)) : 0;

  const label = rolling
    ? t('hunt.rolling')
    : empty
      ? t('hunt.noRollsShort')
      : unknown
        ? t('hunt.roll')
        : t('hunt.roll');

  const status = unknown
    ? t('hunt.rollBankLoading')
    : empty
      ? t('hunt.rollUnavailable')
      : t('hunt.rollWithCount', { n: total });

  const statusLine = (
    <span className="flex items-center justify-center gap-1.5 text-[11px] font-semibold leading-tight tabular-nums text-ink-950/65">
      {empty ? (
        <>
          <CountdownPill rolls={rolls} className="font-semibold tracking-normal" />
          <span className="truncate">{t('hunt.rollUnavailable')}</span>
        </>
      ) : (
        <>
          <span>{unknown ? t('hunt.rollBankLoading') : t('hunt.rollsCount', { n: total })}</span>
          {!unknown ? (
            <CountdownPill rolls={rolls} className="font-semibold tracking-normal" />
          ) : null}
        </>
      )}
    </span>
  );

  return (
    <motion.div
      className={clsx('relative w-full select-none', className)}
      animate={reduced || !rolling ? { scale: 1 } : { scale: [1, 0.978, 1] }}
      transition={rolling ? { duration: 0.65, repeat: Infinity, ease: EASE.continuous } : SPRING.tap}
    >
      {/* Ambient brass aura behind the button when ready */}
      {!blocked && !reduced && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute -inset-1 -z-10 rounded-[24px] opacity-60 blur-lg transition-opacity"
          style={{
            background:
              'linear-gradient(90deg, rgba(125,162,255,0.28), rgba(212,175,106,0.45), rgba(125,162,255,0.28))',
          }}
        />
      )}

      <button
        type="button"
        className={clsx(
          'relative isolate block w-full overflow-hidden rounded-[22px] font-display font-bold',
          'border border-white/80 bg-gradient-to-b from-[#fffdf8] via-[#f3ecdd] to-[#dbcdb4] text-ink-950',
          'transition duration-150 active:translate-y-[2px] active:scale-[0.99] disabled:cursor-not-allowed',
          size === 'lg' ? 'min-h-[72px]' : 'min-h-[56px]',
          blocked && !rolling && 'opacity-55 saturate-[0.55]',
        )}
        style={{
          boxShadow:
            blocked && !rolling
              ? 'inset 0 1px 0 rgba(255,255,255,0.5), inset 0 -1px 0 rgba(0,0,0,0.2), 0 2px 0 #6e5b38'
              : 'inset 0 1.5px 0 rgba(255,255,255,0.95), inset 0 -2px 0 rgba(140,115,70,0.35), 0 4px 0 #8a7042, 0 18px 34px -12px rgba(0,0,0,0.95)',
        }}
        onClick={handleClick}
        disabled={blocked}
        aria-busy={rolling}
        aria-label={rolling ? t('hunt.rolling') : status}
        data-testid="roll-button"
        data-state={rolling ? 'rolling' : empty ? 'empty' : unknown ? 'unknown' : 'ready'}
      >
        {/* Continuous roll-bank fuel bar inside the pedal */}
        {!empty && cap > 0 && (
          <span
            aria-hidden
            className="absolute inset-y-0 left-0 -z-10 bg-gradient-to-r from-amber-500/[0.14] to-amber-600/[0.06]"
            style={{
              width: `${fill * 100}%`,
              transition: 'width 500ms cubic-bezier(0.16,0.84,0.28,1)',
            }}
          />
        )}

        {/* Specular metallic shimmer pass */}
        {!blocked && !reduced && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 -skew-x-12 bg-gradient-to-r from-transparent via-white/55 to-transparent animate-shimmer"
          />
        )}

        <span className="relative flex h-full w-full flex-col items-center justify-center gap-0.5 px-4">
          <span
            className={clsx(
              'flex items-center gap-2 leading-tight',
              rolling ? 'text-[17px] tracking-[0.1em]' : 'text-[20px] tracking-[0.14em]',
            )}
          >
            <span aria-hidden="true" className="text-[15px] text-amber-700">
              {rolling ? '◎' : empty ? '⏳' : '⚡'}
            </span>
            <span>{label}</span>
          </span>
          {statusLine}
        </span>
      </button>
    </motion.div>
  );
}
export { RollButton };
