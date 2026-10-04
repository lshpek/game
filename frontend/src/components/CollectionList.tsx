import { formatCoins, rarityColor } from '@/lib/format';
import { useI18n } from '@/i18n';
import type { PlateCard } from '@/types';
import { PlateVisual } from './PlateVisual';
import { RarityBadge, TraitChip } from './RarityBadge';

interface CollectionListProps {
  items: PlateCard[];
  expanded: number | null;
  onToggle: (plateId: number) => void;
  selling: boolean;
  onSell: (plate: PlateCard) => void;
}

export function CollectionList({ items, expanded, onToggle, selling, onSell }: CollectionListProps) {
  const { lang, t } = useI18n();
  return (
    <ul className="space-y-2">
      {items.map((item) => {
        const color = rarityColor(item.rarity);
        const isOpen = expanded === item.id;
        return (
          <li key={item.id}>
            <div className="glass p-3" style={isOpen ? { borderColor: `${color}55` } : undefined}>
              <button
                type="button"
                className="flex w-full items-center gap-3 text-left"
                onClick={() => onToggle(item.id)}
                aria-expanded={isOpen}
                aria-label={t('collection.ariaPlate', { plate: item.plate_text })}
                data-testid="collection-row"
              >
                <span className="w-32 shrink-0">
                  <PlateVisual plate={item} size="sm" />
                </span>
                <span className="min-w-0 flex-1">
                  <RarityBadge rarity={item.rarity} size="sm" />
                  <span className="mt-1 block truncate text-xs text-white/45">
                    {item.country.flag} {lang === 'ru' ? item.country.name_ru : item.country.name_en}
                  </span>
                </span>
                <span className="shrink-0 text-right">
                  <span className="number-display block text-sm text-emerald-300">
                    +{formatCoins(item.dealer_value)}
                  </span>
                  <span className="text-[10px] text-white/45">{item.currency_symbol}{formatCoins(item.collector_value)}</span>
                  {item.duplicate_count > 0 ? (
                    <span className="block text-[10px] text-amber-300/80">
                      {t('collection.dup', { count: item.duplicate_count })}
                    </span>
                  ) : null}
                </span>
              </button>

              {isOpen ? (
                <div className="mt-3 space-y-3 border-t border-white/10 pt-3">
                  <p className="text-sm leading-relaxed text-white/70">{item.story}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {item.reason_labels.map((label, index) => (
                      <TraitChip
                        key={item.reasons[index] ?? label}
                        code={item.reasons[index] ?? ''}
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
                  {item.duplicate_count > 0 ? (
                    <button
                      type="button"
                      className="btn-ghost w-full !text-sm"
                      disabled={selling}
                      onClick={() => onSell(item)}
                      aria-label={t('collection.sellAria')}
                    >
                      {t('collection.sell', { coins: formatCoins(item.dealer_value * item.duplicate_count) })}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
