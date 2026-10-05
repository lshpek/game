import { motion } from 'framer-motion';

import { formatCoins, rarityColor } from '@/lib/format';
import { SPRING, useReducedMotion } from '@/lib/motion';
import { useI18n } from '@/i18n';
import CollectibleVisual from './CollectibleVisual';
import { RarityBadge, TraitChip } from './RarityBadge';
import type { PlateCard } from '@/types';

interface CollectionListProps {
  items: PlateCard[];
  expanded: number | null;
  onToggle: (plateId: number) => void;
  selling: boolean;
  onSell: (plate: PlateCard) => void;
  /** Opens the full detail sheet. */
  onOpen?: (plateId: number) => void;
}

/**
 * The garage: a row per physical object.
 *
 * Each entry leads with the *object itself*, large enough to identify at a glance - a
 * real plate or a real SIM card, drawn from the country recipe - because that is what
 * the player recognises. Around it sit the four facts that matter while collecting:
 * rarity, country, duplicates and value. The provider is shown on a SIM card, because
 * "collect two different operators" is a real goal.
 *
 * The list only draws. Every write (sell, open) is delegated to the page, which owns the
 * mutation and its invalidation.
 */
export function CollectionList({
  items,
  expanded,
  onToggle,
  selling,
  onSell,
  onOpen,
}: CollectionListProps) {
  const { lang, t } = useI18n();
  const reduced = useReducedMotion();

  return (
    <ul className="space-y-2">
      {items.map((item, index) => {
        const color = rarityColor(item.rarity);
        const isOpen = expanded === item.id;
        const kindLabel = item.kind === 'SIM_CARD' ? t('category.sim') : t('category.plate');
        return (
          <motion.li
            key={item.id}
            initial={reduced ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...SPRING.settle, duration: 0.28, delay: Math.min(index, 8) * 0.02 }}
          >
            <div
              className="glass p-3"
              style={{
                borderColor: isOpen ? `${color}55` : undefined,
                background: `linear-gradient(120deg, ${color}0d, transparent 55%)`,
              }}
            >
              <button
                type="button"
                className="flex w-full items-center gap-3 text-left"
                onClick={() => onToggle(item.id)}
                aria-expanded={isOpen}
                aria-label={t('collection.ariaPlate', { plate: item.plate_text })}
                data-testid="collection-row"
                data-kind={item.kind ?? 'VEHICLE_PLATE'}
              >
                {/* The object, big enough to recognise without reading a single word. */}
                <span className="w-[132px] shrink-0">
                  <CollectibleVisual card={item} scale={0.52} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-1.5">
                    <RarityBadge rarity={item.rarity} size="sm" />
                    <span className="rounded-md border border-white/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.14em] text-white/40">
                      {kindLabel}
                    </span>
                    {item.is_new && (
                      <span className="rounded-md border border-emerald-300/30 bg-emerald-300/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.14em] text-emerald-200">
                        {t('collection.new')}
                      </span>
                    )}
                  </span>
                  <span className="mt-1 block truncate text-xs text-white/55">
                    {item.country.flag} {lang === 'ru' ? item.country.name_ru : item.country.name_en}
                    {item.region
                      ? ` · ${lang === 'ru' ? item.region.name_ru : item.region.name_en}`
                      : ''}
                  </span>
                  {item.kind === 'SIM_CARD' && item.details ? (
                    <span className="mt-0.5 flex items-center gap-1.5 truncate text-[11px] text-white/40">
                      <span
                        aria-hidden
                        className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ background: item.details.operator_accent }}
                      />
                      {item.details.operator}
                      {item.details.edition ? ` · ${item.details.edition}` : ''}
                    </span>
                  ) : null}
                </span>
                <span className="shrink-0 text-right">
                  <span className="number-display block text-sm text-emerald-300">
                    +{formatCoins(item.dealer_value)}
                  </span>
                  <span className="text-[10px] text-white/45">
                    {item.currency_symbol}
                    {formatCoins(item.collector_value)}
                  </span>
                  {item.duplicate_count > 0 ? (
                    <span className="block text-[10px] text-amber-300/80">
                      ×{item.duplicate_count} {t('collection.duplicates')}
                    </span>
                  ) : null}
                </span>
              </button>

              {isOpen ? (
                <div className="mt-3 space-y-3 border-t border-white/10 pt-3">
                  {item.story ? (
                    <p className="text-sm leading-relaxed text-white/70">{item.story}</p>
                  ) : null}
                  <div className="flex flex-wrap gap-1.5">
                    {item.reason_labels.map((label, traitIndex) => (
                      <TraitChip
                        key={item.reasons[traitIndex] ?? label}
                        code={item.reasons[traitIndex] ?? ''}
                        label={label}
                      />
                    ))}
                  </div>
                  <p className="text-[11px] text-white/40">
                    {t('collection.discovered', {
                      count: item.discovery_count,
                      date: item.first_discovered_at
                        ? new Date(item.first_discovered_at).toLocaleDateString()
                        : '—',
                    })}
                  </p>
                  <div className="flex gap-2">
                    {onOpen ? (
                      <button
                        type="button"
                        className="btn-ghost flex-1 !text-sm"
                        onClick={() => onOpen(item.id)}
                        data-testid="collection-open-detail"
                      >
                        {t('details.title')}
                      </button>
                    ) : null}
                    {/* Only offered when there is genuinely a duplicate to sell. */}
                    {item.duplicate_count > 0 ? (
                      <button
                        type="button"
                        className="btn-ghost flex-1 !text-sm"
                        disabled={selling}
                        onClick={() => onSell(item)}
                        aria-label={t('collection.sellAria')}
                      >
                        {t('collection.sell', {
                          coins: formatCoins((item.sale_value ?? 0) * item.duplicate_count),
                        })}
                      </button>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          </motion.li>
        );
      })}
    </ul>
  );
}

export default CollectionList;