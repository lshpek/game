import { motion } from 'framer-motion';
import clsx from 'clsx';

import { useT } from '../i18n';
import { EASE, SPRING, useReducedMotion } from '../lib/motion';
import { hapticCue } from '../lib/telegram';
import { CountdownPill } from './RollEconomy';
import type { RollBalance } from '../types';

/**
 * ROLL: the primary action in NUMORA.
 *
 * The control carries its own state, so the player never has to guess whether a tap will
 * do anything: the roll count, the rolling state, the unavailable state and the refill
 * countdown are all on the control itself.
 *
 * ### Why it looks like an ivory key rather than a coloured button
 *
 * The old treatment was a purple-to-magenta gradient with a 32px coloured glow. That is
 * the visual language of a casino floor, and it is also the loudest thing on a screen
 * whose entire point is that a *physical plate* is the hero. So the primary control is
 * the brightest surface in the app - a warm off-white plate with a real top highlight and
 * a hard bottom shadow - and nothing else on the screen is allowed to compete with it.
 *
 * ### Double-tap protection
 *
 * Two layers, because either alone has a gap: the synchronous ref on the hunt screen
 * swallows a second press inside one frame, and the server's idempotency key is the
 * backstop. The `locked` prop carries the first layer into the control's own disabled
 * state so the button never looks pressable while a roll is already in flight.
 *
 * It is a real `<button>`, so it is keyboard reachable and announces its disabled state.
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
      animate={reduced || !rolling ? { scale: 1 } : { scale: [1, 0.978, 1] }}
      transition={rolling ? { duration: 0.7, repeat: Infinity, ease: EASE.continuous } : SPRING.tap}
    >
      <button
        type="button"
        className={clsx(
          'relative w-full overflow-hidden rounded-[20px] font-display font-bold',
          'bg-gradient-to-b from-[#f4f1ea] to-[#dcd5c8] text-ink-950',
          'transition duration-150 active:scale-[0.985] disabled:cursor-not-allowed',
          size === 'lg' ? 'min-h-[64px]' : 'min-h-[52px]',
          blocked && 'opacity-50 saturate-[0.6]',
        )}
        style={{
          boxShadow: blocked
            ? 'inset 0 1px 0 rgba(255,255,255,0.5), inset 0 -1px 0 rgba(0,0,0,0.2)'
            : 'inset 0 1px 0 rgba(255,255,255,0.8), inset 0 -1px 0 rgba(0,0,0,0.22), 0 14px 28px -16px rgba(0,0,0,0.95)',
        }}
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
            className="absolute inset-y-0 left-0 bg-ink-950/[0.07] transition-[width] duration-500"
            style={{
              width: `${fill * 100}%`,
              transitionTimingFunction: 'cubic-bezier(0.16,0.84,0.28,1)',
            }}
          />
        )}

        <span className="relative z-10 flex flex-col items-center justify-center leading-tight">
          {rolling ? (
            <span className="text-[17px] tracking-[0.1em]">{t('hunt.rolling')}</span>
          ) : empty ? (
            <span className="text-[15px] tracking-[0.06em]">{t('hunt.noRollsShort')}</span>
          ) : (
            <span className="text-[19px] tracking-[0.12em]">{t('hunt.roll')}</span>
          )}
          <CountdownPill
            rolls={empty ? null : rolls}
            className="mt-0.5 text-[11px] font-medium tracking-normal text-ink-950/55"
          />
        </span>
      </button>

      {/* The count, outside the button: it is information, not a label. */}
      {!empty && !blocked ? (
        <span
          className="pointer-events-none absolute -top-2.5 right-3 rounded-full border border-white/12 bg-ink-900 px-2 py-0.5 text-[11px] font-bold tabular-nums text-white/80"
          aria-hidden
        >
          {total}
        </span>
      ) : null}
    </motion.div>
  );
}
export { RollButton };
