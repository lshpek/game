import { useMemo } from 'react';
import clsx from 'clsx';
import { useI18n, type DictKey } from '@/i18n';
import { haptic } from '@/lib/telegram';
import type { CollectibleKind } from '@/types';

/**
 * Kind picker: a game-mode selector, not a form field.
 *
 * NUMORA has exactly two kinds, so the three states are ALL / PLATES / SIM. They sit
 * in one row so switching costs a single tap - hunting is the loop, and a player
 * should never walk through screens to change what they are hunting.
 */

const KIND_ORDER: Array<CollectibleKind | 'ALL'> = ['ALL', 'VEHICLE_PLATE', 'SIM_CARD'];

const KIND_LABEL: Record<CollectibleKind | 'ALL', DictKey> = {
  ALL: 'category.all',
  VEHICLE_PLATE: 'category.plate',
  SIM_CARD: 'category.sim',
};

const KIND_ICON: Record<CollectibleKind | 'ALL', string> = {
  ALL: '\u{1F30D}',
  VEHICLE_PLATE: '\u{1F699}',
  SIM_CARD: '\u{1F4F7}',
};

interface KindSelectorProps {
  value: CollectibleKind | null;
  onChange: (value: CollectibleKind | null) => void;
  disabled?: boolean;
  counts?: Partial<Record<CollectibleKind, number>>;
  className?: string;
}

export function KindSelector({ value, onChange, disabled = false, counts, className }: KindSelectorProps) {
  const { t } = useI18n();

  const items = useMemo(
    () =>
      KIND_ORDER.map((key) => ({
        key,
        label: t(KIND_LABEL[key]),
        icon: KIND_ICON[key],
        count: key === 'ALL' ? undefined : counts?.[key],
      })),
    [counts, t],
  );

  return (
    <div
      className={clsx('no-scrollbar flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none]', className)}
      role="tablist"
      aria-label={t('category.aria')}
      data-testid="kind-selector"
    >
      {items.map((item) => {
        const active = (value ?? 'ALL') === item.key;
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={disabled}
            onClick={() => {
              haptic('light');
              onChange(item.key === 'ALL' ? null : item.key);
            }}
            className={clsx(
              'flex min-h-[40px] shrink-0 items-center gap-1.5 rounded-xl border px-3 text-[11px] font-bold uppercase tracking-[0.14em] transition active:scale-[0.97]',
              active
                ? 'border-white/25 bg-white/[0.12] text-white shadow-[0_0_24px_-8px_rgba(255,255,255,0.5)]'
                : 'border-white/8 bg-white/[0.03] text-white/45',
              disabled && 'opacity-50',
            )}
            data-testid={`kind-${item.key}`}
          >
            <span aria-hidden>{item.icon}</span>
            {item.label}
            {item.count !== undefined ? (
              <span className="rounded-full bg-white/10 px-1.5 text-[9px]">{item.count}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/** Compatibility alias so older imports keep working. */
export const CategorySelector = KindSelector;