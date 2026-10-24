import clsx from 'clsx';

import { formatCoins, rarityColor } from '@/lib/format';
import { PriceDisplay } from '@/components/PriceDisplay';
import { playTap } from '@/lib/sound';
import { useI18n } from '@/i18n';
import CollectibleVisual from './CollectibleVisual';
import CollectorBioPanel from './CollectorBioPanel';
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
    <ul className="space-y-2">
      {items.map((item) => {
        const color = rarityColor(item.rarity);
        const isOpen = expanded === item.id;
        const kindLabel = item.kind === 'SIM_CARD' ? t('category.sim') : t('category.plate');
        const localizedStory =
          lang === 'ru' && (item as { story_ru?: string }).story_ru
            ? (item as { story_ru?: string }).story_ru
            : item.story;

        return (
          <li
            key={item.id}
            className={clsx(
              'glass overflow-hidden transition-colors',
              isOpen ? 'bg-white/[0.065]' : 'hover:bg-white/[0.04]',
            )}
            style={{ borderColor: isOpen ? `${color}55` : `${color}22` }}
          >
            <div className="flex items-center gap-3 p-3">
              <button
                type="button"
                className="flex min-w-0 flex-1 items-center gap-3 text-left"
                onClick={() => {
                  playTap();
                  onToggle(item.id);
                }}
                aria-expanded={isOpen}
                aria-label={t('collection.ariaPlate', { plate: item.plate_text })}
                data-testid="collection-row"
                data-kind={item.kind ?? 'VEHICLE_PLATE'}
              >
                <span className="w-[112px] shrink-0">
                  <CollectibleVisual card={item} scale={0.42} interactiveTilt={false} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-1.5">
                    <RarityBadge rarity={item.rarity} size="sm" />
                    {item.is_new ? (
                      <span className="rounded-md border border-emerald-300/35 bg-emerald-300/15 px-1.5 py-0.5 text-[9px] font-bold tracking-[0.06em] text-emerald-200">
                        {t('collection.new')}
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-1 block truncate t-caption font-semibold text-white/80">
                    <span aria-hidden>{item.country.flag}</span>{' '}
                    {lang === 'ru' ? item.country.name_ru : item.country.name_en}
                    {item.region
                      ? ` · ${lang === 'ru' ? item.region.name_ru : item.region.name_en}`
                      : ''}
                  </span>
                  {item.kind === 'SIM_CARD' && item.details ? (
                    <span className="mt-0.5 flex items-center gap-1.5 truncate text-[11px] text-white/45">
                      <span
                        aria-hidden
                        className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ background: item.details.operator_accent }}
                      />
                      {item.details.operator}
                      {item.details.edition ? ` · ${item.details.edition}` : ''}
                    </span>
                  ) : (
                    <span className="mt-0.5 block truncate text-[11px] text-white/40">{kindLabel}</span>
                  )}
                </span>
              </button>

              <span className="flex shrink-0 flex-col items-end">
                <PriceDisplay value={item.dealer_value} prefix="+" size="sm" />
                <PriceDisplay
                  value={item.collector_value}
                  size="sm"
                  readOnly
                  tone="rgba(255,255,255,0.4)"
                />
                {item.duplicate_count > 0 ? (
                  <span className="mt-0.5 rounded bg-brass/15 px-1.5 py-0.5 text-[10px] font-bold text-brass-soft">
                    ×{item.duplicate_count} {t('collection.duplicates')}
                  </span>
                ) : null}
              </span>
            </div>

            {isOpen ? (
              <div className="space-y-3 border-t border-white/[0.08] bg-black/20 px-3.5 pb-3.5 pt-3">
                {localizedStory ? (
                  <p className="t-caption leading-relaxed text-white/75">{localizedStory}</p>
                ) : null}
                <CollectorBioPanel bio={item.collector_bio} />
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
                <p className="text-[11px] text-white/45">
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
                  {item.duplicate_count > 0 ? (
                    <button
                      type="button"
                      className="btn-primary flex-1 !text-sm"
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
    <ul className={clsx('grid grid-cols-2 gap-3 sm:grid-cols-3', className)}>
      {items.map((item) => {
        const color = rarityColor(item.rarity);
        return (
          <li
            key={item.id}
            className="stage flex flex-col items-center px-2.5 py-3.5 transition hover:border-white/25"
            style={
              {
                borderColor: `${color}35`,
                '--stage-glow': `${color}28`,
              } as React.CSSProperties
            }
          >
            <button
              type="button"
              onClick={() => {
                playTap();
                onOpen(item.id);
              }}
              className="flex w-full min-w-0 flex-col items-center gap-2"
              aria-label={item.plate_text}
            >
              <CollectibleVisual card={item} scale={0.36} interactiveTilt={false} />
              <RarityBadge rarity={item.rarity} size="sm" />
              <PriceDisplay value={item.dealer_value} prefix="+" size="sm" compact readOnly />
              <span className="t-micro truncate text-white/50">
                <span aria-hidden>{item.country.flag}</span> {item.country.code}
                {item.duplicate_count > 0 ? ` · ×${item.duplicate_count + 1}` : ''}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export default CollectionList;
