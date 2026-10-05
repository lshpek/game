import { motion } from 'framer-motion';
import clsx from 'clsx';

import { useT } from '../i18n';
import { EASE, SPRING, useReducedMotion } from '../lib/motion';
import { hapticCue } from '../lib/telegram';
import { CountdownPill } from './RollEconomy';
import type { RollBalance } from '../types';

/**
 * ROLL: the most important control in NUMORA.
 *
 * The button carries its own state so the player never has to guess whether a tap will
 * do anything: the roll count, the rolling state, the unavailable state and the refill
 * countdown are all on the control itself.
 *
 * It is a real `<button>`, so it is keyboard reachable and announces its disabled state.
 * The `onDoubleTapGuard` guard below is the client's half of the double-tap protection;
 * the server's roll idempotency key is the other half.
 */

interface Props {
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
  const t = useT();
  const reduced = useReducedMotion();

  const total = rolls?.rolls_remaining ?? 0;
  const cap = rolls?.bank_cap ?? 20;
  const empty = total <= 0;
  const blocked = disabled || rolling || locked || empty;

  const handleClick = () => {
    if (blocked) return;
    hapticCue('tap');
    onRoll();
  };

  const fill = cap > 0 ? Math.max(0, Math.min(1, total / cap)) : 0;

  return (
    <motion.div
      className={clsx('relative w-full select-none', className)}
      animate={reduced || !rolling ? { scale: 1 } : { scale: [1, 0.975, 1] }}
      transition={
        rolling
          ? { duration: 0.7, repeat: Infinity, ease: EASE.continuous }
          : SPRING.tap
      }
    >
      <button
        type="button"
        className={clsx(
          'relative w-full overflow-hidden rounded-3xl font-display font-bold uppercase tracking-[0.18em]',
          'bg-gradient-to-br from-accent to-fuchsia-500 text-white shadow-glow',
          'transition active:scale-[0.985] disabled:cursor-not-allowed',
          size === 'lg' ? 'min-h-[68px] text-xl' : 'min-h-[52px] text-base',
          blocked && 'opacity-55',
        )}
        onClick={handleClick}
        disabled={blocked}
        aria-busy={rolling}
        aria-label={
          rolling
            ? t('hunt.rolling')
            : empty
              ? t('hunt.rollUnavailable')
              : t('hunt.rollWithCount', { n: total })
        }
      >
        {/* The bank fill: a quiet, continuous read of how much is left. */}
        {!empty && (
          <span
            aria-hidden
            className="absolute inset-y-0 left-0 bg-white/10 transition-[width] duration-500"
            style={{ width: `${fill * 100}%`, transitionTimingFunction: 'cubic-bezier(0.16,0.84,0.28,1)' }}
          />
        )}

        <span className="relative z-10 flex flex-col items-center justify-center leading-tight">
          {rolling ? (
            <span>{t('hunt.rolling')}</span>
          ) : empty ? (
            <span className="text-base">{t('hunt.noRollsShort')}</span>
          ) : (
            <span>{t('hunt.roll')}</span>
          )}
          <CountdownPill
            rolls={empty ? null : rolls}
            className="mt-0.5 normal-case tracking-normal text-white/75"
          />
        </span>
      </button>
    </motion.div>
  );
}
export { RollButton };