import { AnimatePresence, motion } from 'framer-motion';
import { RARITY_COLORS, formatCoins } from '@/lib/format';
import type { AchievementBadge, PlateRollResult, Rarity } from '@/types';
import { useI18n } from '@/i18n';
import { CollectibleVisual } from './CollectibleVisual';
import { RarityBadge, TraitChip } from './RarityBadge';
import { ValueCounter } from './ValueCounter';

interface ResultOverlayProps {
  open: boolean;
  result: PlateRollResult | null;
  onClose: () => void;
  onShare: () => void;
  onSell: () => void;
}

/** The compact reveal: the object flips in, the value counts up, the story explains why. */
export function ResultOverlay({ open, result, onClose, onShare, onSell }: ResultOverlayProps) {
  const { lang, t } = useI18n();
  const plate = result?.plate ?? null;
  const rarity = (result?.rarity ?? 'COMMON') as Rarity;
  const color = RARITY_COLORS[rarity] ?? RARITY_COLORS.COMMON;
  const isSecret = rarity === 'SECRET' || rarity === 'MYTHIC';
  const achievements: AchievementBadge[] = result?.unlocked_achievements ?? [];

  return (
    <AnimatePresence>
      {open && plate && result ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-ink-950/85 p-5 backdrop-blur-sm"
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
            className="relative my-auto w-full max-w-sm overflow-hidden rounded-3xl border p-6 text-center"
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
                {result.is_first_discovery ? t('result.secretDiscovered') : t('result.secretFound')}
              </motion.p>
            ) : null}

            {result.is_first_discovery && !isSecret ? (
              <p className="mb-1 text-xs font-bold uppercase tracking-[0.3em] text-amber-300/90">
                {t('result.firstDiscovery')}
              </p>
            ) : null}

            {result.is_duplicate ? (
              <p className="mb-1 text-xs font-bold uppercase tracking-[0.3em] text-amber-300/90">
                {t('result.duplicate')}
              </p>
            ) : null}

            <motion.div
              key={plate.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2, delay: 0.05 }}
              className="my-3"
              data-testid="result-plate"
            >
              <CollectibleVisual collectible={plate} size="lg" reveal accent={color} />
            </motion.div>

            <div className="flex flex-wrap items-center justify-center gap-1.5">
              <RarityBadge rarity={rarity} size="lg" />
              {result.is_new_country ? (
                <TraitChip code="new_country" label={t('result.newCountry')} />
              ) : null}
              {result.is_new_region ? <TraitChip code="new_region" label={t('result.newRegion')} /> : null}
            </div>

            {/* Dealer value counts up - authoritative NUMORA amount. */}
            <p className="number-display mt-4 text-3xl" style={{ color }}>
              <ValueCounter value={result.sale_value} suffix=" NUMORA" />
            </p>
            <p className="mt-1 text-xs text-white/55">
              {t('result.collectorValue', {
                value: `${plate.currency_symbol}${formatCoins(plate.collector_value)}`,
              })}
            </p>
            {plate.story ? (
              <p className="mt-3 text-sm leading-relaxed text-white/70">{plate.story}</p>
            ) : null}

            {plate.reason_labels.length ? (
              <div className="mt-3 flex flex-wrap justify-center gap-1.5">
                {plate.reason_labels.slice(0, 4).map((label, index) => (
                  <TraitChip key={plate.reasons[index] ?? label} code={plate.reasons[index] ?? ''} label={label} />
                ))}
              </div>
            ) : null}

            {result.numora_awarded > 0 ? (
              <p className="mt-3 text-sm font-semibold text-emerald-300">
                {t('result.coinsAwarded', { coins: formatCoins(result.numora_awarded) })}
              </p>
            ) : null}

            {result.missions_completed.length ? (
              <p className="mt-2 text-xs font-semibold text-cyan-300">
                {t('result.missionsDone', {
                  names: result.missions_completed
                    .map((mission) => mission[lang === 'ru' ? 'name_ru' : 'name_en'] ?? mission.code)
                    .join(', '),
                })}
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
              {result.is_duplicate ? (
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={onSell}
                  disabled={result.sale_value <= 0}
                  data-testid="sell-button"
                >
                  {t('result.sell', { coins: formatCoins(result.sale_value) })}
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
