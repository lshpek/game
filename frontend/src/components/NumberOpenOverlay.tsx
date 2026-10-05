import { motion } from 'framer-motion';

import { useI18n } from '@/i18n';
import { formatCoins, rarityColor } from '@/lib/format';
import { DURATION, EASE, SPRING, useReducedMotion } from '@/lib/motion';
import { RarityBadge } from './RarityBadge';
import type { ContainerOpenResult, Rarity } from '@/types';

/**
 * The legacy four-digit reveal.
 *
 * This is the *old* game's result dialog - rolling four digits out of a box. It is
 * deliberately distinct from the atlas reveal: different shape, different pacing, no
 * physical object, and no attempt to look like a collectible. The two experiences are
 * separate on purpose, because a player should be able to tell at a glance which game
 * they are in.
 *
 * It is not the product's reveal and does not pretend to be. `Reveal.tsx` owns that, and
 * it is the only screen the player reaches from a roll.
 */
interface NumberOpenOverlayProps {
  open: boolean;
  result: ContainerOpenResult | null;
  onClose: () => void;
  onConvert: () => void;
  converting: boolean;
}

export function NumberOpenOverlay({
  open,
  result,
  onClose,
  onConvert,
  converting,
}: NumberOpenOverlayProps) {
  const { t } = useI18n();
  const reduced = useReducedMotion();
  const number = result?.number ?? null;
  const rarity = (number?.rarity ?? 'COMMON') as Rarity;
  const color = rarityColor(rarity);

  if (!open || !result || !number) return null;

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center p-5"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: DURATION.fade, ease: EASE.out }}
      role="dialog"
      aria-modal="true"
      aria-label={t('result.aria')}
      data-testid="result-overlay"
    >
      <motion.button
        type="button"
        className="scrim"
        aria-label={t('country.close')}
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      />

      <motion.div
        className="relative w-full max-w-[380px] overflow-hidden rounded-[26px] border border-white/[0.08] bg-ink-900 p-5"
        style={{
          paddingBottom: 'calc(var(--tg-safe-bottom) + 20px)',
          boxShadow: '0 30px 70px -30px rgba(0,0,0,0.95)',
        }}
        initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.94, y: 24 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 12 }}
        transition={reduced ? { duration: DURATION.fade } : SPRING.settle}
        onClick={(event) => event.stopPropagation()}
      >
        {result?.is_duplicate ? (
          <p className="mb-1 text-center t-micro uppercase text-amber-300/90">
            {t('result.duplicate')}
          </p>
        ) : null}

        {/* The digits. The hero of this screen, as they always were. */}
        <motion.div
          className="number-display my-2 text-center text-[3.5rem] leading-none"
          style={{ color, textShadow: `0 0 30px ${color}55` }}
          initial={reduced ? false : { scale: 0.86, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ ...SPRING.settle, duration: DURATION.lock }}
          data-testid="result-number"
        >
          {number.number}
        </motion.div>

        <div className="flex justify-center">
          <RarityBadge rarity={rarity} size="md" />
        </div>

        <p className="number-display mt-4 text-center text-[26px] font-bold text-brass">
          {formatCoins(number.value)}
        </p>

        {number?.story ? (
          <p className="mt-3 text-center t-caption leading-relaxed text-white/55">{number.story}</p>
        ) : null}

        <div className="mt-5 grid gap-2">
          {/* The conversion action exists only for a duplicate, which is the only case
              where converting it loses nothing. */}
          {result?.is_duplicate ? (
            <button type="button" className="btn-ghost" disabled={converting} onClick={onConvert}>
              {t('result.convert', { coins: formatCoins(result.conversion_value) })}
            </button>
          ) : null}
          <button type="button" className="btn-primary" onClick={onClose}>
            {t('result.continue')}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

export default NumberOpenOverlay;
