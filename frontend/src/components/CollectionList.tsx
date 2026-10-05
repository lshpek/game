import clsx from 'clsx';

import { formatCoins, rarityColor } from '@/lib/format';
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
 * real plate or a real SIM card, drawn from the country recipe - because that is what the
 * player recognises. Around it sit the three facts that matter while collecting: rarity,
 * country and value. The provider is shown on a SIM card, because "collect two different
 * operators" is a real goal.
 *
 * A row is deliberately *not* a card with the same chrome as every other surface on the
 * app: it is a flat row with a left-hand object well, so a page of twenty of them reads as
 * a shelf rather than as a stack of identical boxes.
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

  return (
    <ul className="space-y-1.5">
      {items.map((item) => {
        const color = rarityColor(item.rarity);
        const isOpen = expanded === item.id;
        const kindLabel = item.kind === 'SIM_CARD' ? t('category.sim') : t('category.plate');
        return (
          <li
            key={item.id}
            className={clsx(
              'overflow-hidden rounded-[16px] border transition-colors',
              isOpen ? 'bg-white/[0.05]' : 'bg-white/[0.025]',
            )}
            style={{ borderColor: isOpen ? `${color}44` : 'rgba(255,255,255,0.06)' }}
          >
            <button
              type="button"
              className="flex w-full items-center gap-3 p-2.5 text-left"
              onClick={() => onToggle(item.id)}
              aria-expanded={isOpen}
              aria-label={t('collection.ariaPlate', { plate: item.plate_text })}
              data-testid="collection-row"
              data-kind={item.kind ?? 'VEHICLE_PLATE'}
            >
              {/* The object, big enough to recognise without reading a single word. */}
              <span className="w-[108px] shrink-0">
                <CollectibleVisual card={item} scale={0.42} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-1.5">
                  <RarityBadge rarity={item.rarity} size="sm" />
                  {item.is_new ? (
                    <span className="rounded-md border border-emerald-300/30 bg-emerald-300/10 px-1.5 py-0.5 text-[9px] font-bold tracking-[0.06em] text-emerald-200">
                      {t('collection.new')}
                    </span>
                  ) : null}
                </span>
                <span className="mt-1 block truncate t-caption text-white/60">
                  <span aria-hidden>{item.country.flag}</span>{' '}
                  {lang === 'ru' ? item.country.name_ru : item.country.name_en}
                  {item.region
                    ? ` · ${lang === 'ru' ? item.region.name_ru : item.region.name_en}`
                    : ''}
                </span>
                {item.kind === 'SIM_CARD' && item.details ? (
                  <span className="mt-0.5 flex items-center gap-1.5 truncate text-[11px] text-white/35">
                    <span
                      aria-hidden
                      className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ background: item.details.operator_accent }}
                    />
                    {item.details.operator}
                    {item.details.edition ? ` · ${item.details.edition}` : ''}
                  </span>
                ) : (
                  <span className="mt-0.5 block truncate text-[11px] text-white/30">{kindLabel}</span>
                )}
              </span>
              <span className="shrink-0 text-right">
                <span className="number-display block text-[13px] font-bold text-brass">
                  +{formatCoins(item.dealer_value)}
                </span>
                <span className="block text-[10px] text-white/35">
                  {item.currency_symbol}
                  {formatCoins(item.collector_value)}
                </span>
                {item.duplicate_count > 0 ? (
                  <span className="mt-0.5 block text-[10px] text-brass/80">
                    ×{item.duplicate_count} {t('collection.duplicates')}
                  </span>
                ) : null}
              </span>
            </button>

            {isOpen ? (
              <div className="space-y-3 border-t border-white/[0.07] px-3 pb-3 pt-3">
                {item.story ? (
                  <p className="t-caption leading-relaxed text-white/65">{item.story}</p>
                ) : null}
                {item.reason_labels.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {item.reason_labels.map((label, traitIndex) => (
                      <TraitChip
                        key={item.reasons[traitIndex] ?? label}
                        code={item.reasons[traitIndex] ?? ''}
                        label={label}
                      />
                    ))}
                  </div>
                ) : null}
                <p className="text-[11px] text-white/35">
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
          </li>
        );
      })}
    </ul>
  );
}

/**
 * A grid of collectibles at a larger size, for the atlas view.
 *
 * Split out from the list because the two have genuinely different jobs: a grid is about
 * *shape comparison* - you scan the silhouettes - while a list is about reading facts. Forcing
 * both into one component is what made the collection feel like a single undifferentiated
 * stream.
 */
export function CollectionGrid({
  items,
  onOpen,
  className,
}: {
  items: PlateCard[];
  onOpen: (plateId: number) => void;
  className?: string;
}) {
  return (
    <ul className={clsx('grid grid-cols-2 gap-2.5 sm:grid-cols-3', className)}>
      {items.map((item) => (
        <li
          key={item.id}
          className="stage flex flex-col items-center px-2 py-3"
          style={{ borderColor: `${rarityColor(item.rarity)}22` }}
        >
          <button
            type="button"
            onClick={() => onOpen(item.id)}
            className="flex w-full min-w-0 flex-col items-center gap-2"
            aria-label={item.plate_text}
          >
            <CollectibleVisual card={item} scale={0.34} />
            <RarityBadge rarity={item.rarity} size="sm" />
            <span className="number-display text-[12px] font-bold text-brass">
              +{formatCoins(item.dealer_value)}
            </span>
            <span className="t-micro truncate text-white/35">
              <span aria-hidden>{item.country.flag}</span>{' '}
              {item.country.code}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export default CollectionList;
