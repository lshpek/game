import { AnimatePresence, motion } from 'framer-motion';
import { RARITY_COLORS } from '@/lib/format';
import { formatCoins, traitLabel } from '@/lib/format';
import type { AchievementBadge, NumberCard, Rarity } from '@/types';
import { RarityBadge, TraitChip } from './RarityBadge';
import { useI18n } from '@/i18n';

interface ResultOverlayProps {
  open: boolean;
  number: NumberCard | null;
  rarity: Rarity | null;
  isDuplicate: boolean;
  isFirstDiscovery: boolean;
  conversionValue: number;
  coinsAwarded: number;
  achievements: AchievementBadge[];
  onClose: () => void;
  onShare: () => void;
  onConvert: () => void;
}

export function ResultOverlay({
  open,
  number,
  rarity,
  isDuplicate,
  isFirstDiscovery,
  conversionValue,
  coinsAwarded,
  achievements,
  onClose,
  onShare,
  onConvert,
}: ResultOverlayProps) {
  const { t } = useI18n();
  const color = rarity ? RARITY_COLORS[rarity] : '#7c5cff';
  const isSecret = rarity === 'SECRET' || rarity === 'MYTHIC';

  return (
    <AnimatePresence>
      {open && number ? (
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
            {isSecret ? (
              <motion.p
                className="mb-1 text-xs font-bold uppercase tracking-[0.3em]"
                style={{ color }}
                animate={{ opacity: [0.6, 1, 0.6] }}
                transition={{ duration: 1.8, repeat: Infinity }}
              >
                {isFirstDiscovery ? t('result.secretDiscovered') : t('result.secretFound')}
              </motion.p>
            ) : null}

            {isDuplicate ? (
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
              <RarityBadge rarity={rarity ?? 'COMMON'} size="lg" />
            </div>

            <p className="number-display mt-4 text-3xl" style={{ color }}>
              {formatCoins(number.value)} <span className="text-base opacity-70">🪙</span>
            </p>

            {number.story ? (
              <p className="mt-3 text-sm leading-relaxed text-white/70">{number.story}</p>
            ) : null}

            {number.traits.length ? (
              <div className="mt-3 flex flex-wrap justify-center gap-1.5">
                {number.traits.slice(0, 4).map((code) => (
                  <TraitChip key={code} code={code} label={traitLabel(code)} />
                ))}
              </div>
            ) : null}

            {coinsAwarded > 0 ? (
              <p className="mt-3 text-sm font-semibold text-emerald-300">
              {t('result.coinsAwarded', { coins: formatCoins(coinsAwarded) })}
            </p>
            ) : null}

            {achievements.length ? (
              <ul className="mt-4 space-y-1.5">
                {achievements.map((achievement) => (
                  <li
                    key={achievement.code}
                    className="rounded-xl border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-sm"
                  >
                    🏅 {achievement.name}
                    <span className="block text-xs text-white/55">{achievement.description}</span>
                  </li>
                ))}
              </ul>
            ) : null}

            <div className="mt-6 grid gap-2">
              <button type="button" className="btn-primary" onClick={onShare} data-testid="share-button">
                {t('result.share')}
              </button>
              {isDuplicate ? (
                <button type="button" className="btn-ghost" onClick={onConvert}>
                  {t('result.convert', { coins: formatCoins(conversionValue) })}
                </button>
              ) : null}
              <button type="button" className="btn-ghost" onClick={onClose}>
                {t('result.continue')}
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
