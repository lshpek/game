import { motion } from 'framer-motion';
import clsx from 'clsx';

import { useI18n } from '../i18n';
import { EASE, SPRING, useReducedMotion } from '../lib/motion';
import { hapticCue } from '../lib/telegram';
import { CountdownPill } from './RollEconomy';
import type { RollBalance } from '../types';

/**
 * ROLL: the primary action in NUMORA.
 *
 * The states are the contract, and there are exactly five:
 *
 * ```
 * unknown → КРУТИТЬ → КРУТИМ… → (result) → КРУТИТЬ СНОВА
 *                     ↘ 0 rolls → countdown, not a dead button
 * ```
 *
 * ### Why it looked unclickable
 *
 * `rolls === null` means the bank has not loaded *yet*. It does not mean the player has
 * zero rolls. The old control computed `empty = rolls_remaining <= 0` and then
 * `disabled = empty`, which meant the button was **dead for the whole time the bank was
 * loading** - and permanently dead if that request ever failed, because the screen would
 * sit there refusing taps forever with no explanation.
 *
 * So absence of data is now absence of an opinion: `unknown` disables nothing. The
 * server is authoritative anyway, and it will refuse a roll it cannot honour with a real
 * error the player can act on.
 *
 * ### Nothing sticks out
 *
 * Every element - the label, the count, the countdown, the fill - lives inside the
 * button's own bounds. There is no absolutely-positioned badge hanging off the top edge:
 * on a screen whose whole premise is a *physical object*, a number floating off the
 * control is exactly the kind of thing that makes the interface feel unfinished.
 *
 * ### Double-tap protection
 *
 * Two layers, because either alone has a gap: the synchronous ref on the hunt screen
 * swallows a second press inside one frame, and the server's idempotency key is the
 * backstop. `locked` carries the first layer into the control's own disabled state, so
 * the button never looks pressable while a roll is already in flight.
 *
 * It is a real `<button>`, so it is keyboard reachable and announces its state.
 */

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

  /*
   * Three states, not two.
   *
   * `unknown` - the bank has not arrived. The button works; we simply do not claim to
   * know how many rolls there are.
   * `empty`  - the server said zero. The button is disabled *and says why*, with the
   *            countdown that will change it.
   * `ready`  - the normal case.
   */
  const unknown = rolls === null;
  const total = rolls?.rolls_remaining ?? 0;
  const cap = rolls?.bank_cap ?? 0;
  const empty = !unknown && total <= 0;
  const blocked = disabled || rolling || locked || empty;

  const handleClick = () => {
    if (blocked) return;
    hapticCue('tap');
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

  /*
   * The line under the label.
   *
   * The count, and - when the server said when the next roll arrives - the countdown to
   * it. At zero rolls the countdown *replaces* the count, because "0 rolls" tells the
   * player nothing while "next in 4:05" tells them everything. A full bank cannot be
   * waiting on a refill, so nothing is lost by showing both in the normal case.
   */
  const statusLine = (
    <span className="flex items-center justify-center gap-1.5 text-[11px] font-medium leading-tight tabular-nums text-ink-950/55">
      {empty ? (
        <>
          <CountdownPill rolls={rolls} className="font-medium tracking-normal" />
          <span className="truncate">{t('hunt.rollUnavailable')}</span>
        </>
      ) : (
        <>
          <span>{unknown ? t('hunt.rollBankLoading') : t('hunt.rollsCount', { n: total })}</span>
          {!unknown ? (
            <CountdownPill rolls={rolls} className="font-medium tracking-normal" />
          ) : null}
        </>
      )}
    </span>
  );

  return (
    <motion.div
      className={clsx('w-full select-none', className)}
      animate={reduced || !rolling ? { scale: 1 } : { scale: [1, 0.978, 1] }}
      transition={rolling ? { duration: 0.7, repeat: Infinity, ease: EASE.continuous } : SPRING.tap}
    >
      <button
        type="button"
        className={clsx(
          // `overflow-hidden` plus `isolate`: the fill, the label and the countdown are
          // all inside these bounds, and nothing can paint outside them.
          'relative isolate block w-full overflow-hidden rounded-[20px] font-display font-bold',
          'bg-gradient-to-b from-[#f4f1ea] to-[#dcd5c8] text-ink-950',
          'transition duration-150 active:scale-[0.985] disabled:cursor-not-allowed',
          size === 'lg' ? 'min-h-[68px]' : 'min-h-[54px]',
          blocked && !rolling && 'opacity-55 saturate-[0.6]',
        )}
        style={{
          boxShadow: blocked && !rolling
            ? 'inset 0 1px 0 rgba(255,255,255,0.5), inset 0 -1px 0 rgba(0,0,0,0.2)'
            : 'inset 0 1px 0 rgba(255,255,255,0.8), inset 0 -1px 0 rgba(0,0,0,0.22), 0 14px 28px -16px rgba(0,0,0,0.95)',
        }}
        onClick={handleClick}
        disabled={blocked}
        aria-busy={rolling}
        aria-label={rolling ? t('hunt.rolling') : status}
        data-testid="roll-button"
        data-state={rolling ? 'rolling' : empty ? 'empty' : unknown ? 'unknown' : 'ready'}
      >
        {/*
          The bank fill. A quiet, continuous read of how much is left, drawn from the
          server's own cap so it can never claim a proportion the economy does not have.
        */}
        {!empty && cap > 0 && (
          <span
            aria-hidden
            className="absolute inset-y-0 left-0 -z-10 bg-ink-950/[0.07]"
            style={{
              width: `${fill * 100}%`,
              transition: 'width 500ms cubic-bezier(0.16,0.84,0.28,1)',
            }}
          />
        )}

        {/* The count sits *inside* the control, on its own line under the label. */}
        <span className="relative flex h-full w-full flex-col items-center justify-center gap-0.5 px-4">
          <span
            className={clsx(
              'leading-tight',
              rolling ? 'text-[17px] tracking-[0.1em]' : 'text-[19px] tracking-[0.12em]',
            )}
          >
            {label}
          </span>
          {statusLine}
        </span>
      </button>
    </motion.div>
  );
}
export { RollButton };
