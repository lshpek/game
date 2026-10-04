import { AnimatePresence, motion } from 'framer-motion';
import { RARITY_COLORS, formatCoins } from '@/lib/format';
import { useI18n } from '@/i18n';
import type { ContainerOpenResult, Rarity } from '@/types';
import { RarityBadge } from './RarityBadge';
import { ValueCounter } from './ValueCounter';

interface NumberOpenOverlayProps {
  open: boolean;
  result: ContainerOpenResult | null;
  onClose: () => void;
  onConvert: () => void;
  converting: boolean;
}

/** Reveal dialog for legacy box opens (4-digit numbers), distinct from plate rolls. */
export function NumberOpenOverlay({ open, result, onClose, onConvert, converting }: NumberOpenOverlayProps) {
  const { t } = useI18n();
  const number = result?.number ?? null;
  const rarity = (number?.rarity ?? 'COMMON') as Rarity;
  const color = RARITY_COLORS[rarity] ?? RARITY_COLORS.COMMON;

  return (
    <AnimatePresence>
      {open && number && result ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/85 p-5 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-label={t('result.aria')}
          data-testid="result-overlay"
        >
          <motion.div
            className="relative w-full max-w-sm overflow-hidden rounded-3xl border p-6 text-center"
            style={{
              borderColor: `${color}66`,
              background: `radial-gradient(circle at 50% 0%, ${color}33, #0b0e1a 70%)`,
            }}
            initial={{ scale: 0.86, y: 24, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 260, damping: 22 }}
            onClick={(event) => event.stopPropagation()}
          >
            {result.is_duplicate ? (
              <p className="mb-1 text-xs font-bold uppercase tracking-[0.3em] text-amber-300/90">
                {t('result.duplicate')}
              </p>
            ) : null}

            <motion.div
              key={number.number}
              className="number-display my-3 text-[4.25rem] leading-none"
              style={{ color, textShadow: `0 0 34px ${color}80` }}
              initial={{ scale: 0.7, opacity: 0, rotateX: 60 }}
              animate={{ scale: 1, opacity: 1, rotateX: 0 }}
              transition={{ type: 'spring', stiffness: 220, damping: 16, delay: 0.05 }}
              data-testid="result-number"
            >
              {number.number}
            </motion.div>

            <div className="flex justify-center">
              <RarityBadge rarity={rarity} size="lg" />
            </div>

            <p className="number-display mt-4 text-3xl" style={{ color }}>
              <ValueCounter value={number.value} suffix=" 🪙" />
            </p>

            {number.story ? (
              <p className="mt-3 text-sm leading-relaxed text-white/70">{number.story}</p>
            ) : null}

            <div className="mt-6 grid gap-2">
              {result.is_duplicate ? (
                <button type="button" className="btn-ghost" onClick={onConvert} disabled={converting}>
                  {t('result.convert', { coins: formatCoins(result.conversion_value) })}
                </button>
              ) : null}
              <button type="button" className="btn-primary" onClick={onClose}>
                {t('result.continue')}
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
