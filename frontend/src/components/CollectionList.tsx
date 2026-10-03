import { formatCoins, rarityColor, traitLabel } from '@/lib/format';
import { useI18n } from '@/i18n';
import type { NumberCard } from '@/types';
import { RarityBadge, TraitChip } from './RarityBadge';

interface CollectionListProps {
  items: NumberCard[];
  expanded: string | null;
  onToggle: (value: string) => void;
  converting: boolean;
  onConvert: (value: string) => void;
}

export function CollectionList({
  items,
  expanded,
  onToggle,
  converting,
  onConvert,
}: CollectionListProps) {
  const { lang, t } = useI18n();
  return (
    <ul className="space-y-2">
      {items.map((item) => {
        const color = rarityColor(item.rarity);
        const isOpen = expanded === item.number;
        return (
          <li key={item.number}>
            <div className="glass p-3" style={isOpen ? { borderColor: `${color}55` } : undefined}>
              <button
                type="button"
                className="flex w-full items-center gap-3 text-left"
                onClick={() => onToggle(item.number)}
                aria-expanded={isOpen}
                aria-label={t('collection.ariaNumber', { number: item.number })}
              >
                <span className="number-display w-[4.5rem] shrink-0 text-center text-2xl" style={{ color }}>
                  {item.number}
                </span>
                <span className="min-w-0 flex-1">
                  <RarityBadge rarity={item.rarity} size="sm" />
                  <span className="mt-1 block truncate text-xs text-white/45">{item.story}</span>
                </span>
                <span className="shrink-0 text-right">
                  <span className="number-display block text-base">{formatCoins(item.value)}</span>
                  {item.duplicate_count > 0 ? (
                    <span className="text-[10px] text-amber-300/80">
                      {t('collection.dup', { count: item.duplicate_count })}
                    </span>
                  ) : null}
                </span>
              </button>

              {isOpen ? (
                <div className="mt-3 space-y-3 border-t border-white/10 pt-3">
                  <p className="text-sm leading-relaxed text-white/70">{item.story}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {item.traits.map((code) => (
                      <TraitChip key={code} code={code} label={traitLabel(code, lang)} />
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
                      disabled={converting}
                      onClick={() => onConvert(item.number)}
                    >
                      {t('collection.convert')}
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
