import { useEffect, useMemo, useRef } from 'react';
import clsx from 'clsx';
import { useT } from '@/i18n';
import { haptic } from '@/lib/telegram';
import { COLLECTIBLE_CATEGORIES, type CollectibleCategory } from '@/types';

/**
 * Category picker: a game-mode selector, not a form field.
 *
 * The four states are ALL / PLATES / PHONES / SIM. They are laid out as one row so
 * switching costs a single tap - hunting is the loop, and a player should never
 * have to walk through screens to change what they are hunting.
 */

const CATEGORY_ORDER: Array<CollectibleCategory | 'ALL'> = [
  'ALL',
  'VEHICLE_PLATE',
  'PHONE_NUMBER',
  'SIM_CARD',
];

interface CategorySelectorProps {
  value: CollectibleCategory | null;
  onChange: (value: CollectibleCategory | null) => void;
  disabled?: boolean;
  counts?: Partial<Record<CollectibleCategory, number>>;
  className?: string;
}

export function CategorySelector({
  value,
  onChange,
  disabled = false,
  counts,
  className,
}: CategorySelectorProps) {
  const t = useT();

  const items = useMemo(
    () =>
      CATEGORY_ORDER.map((key) => {
        const label =
          key === 'ALL'
            ? t('category.all')
            : key === 'VEHICLE_PLATE'
              ? t('category.plate')
              : key === 'PHONE_NUMBER'
                ? t('category.phone')
                : t('category.sim');
        const icon =
          key === 'ALL' ? '🌍' : key === 'VEHICLE_PLATE' ? '🚘' : key === 'PHONE_NUMBER' ? '📱' : '💳';
        const count = key === 'ALL' ? undefined : counts?.[key];
        return { key, label, icon, count };
      }),
    [counts, t],
  );

  return (
    <div
      className={clsx('flex gap-1.5 overflow-x-auto pb-1', className)}
      role="tablist"
      aria-label={t('category.aria')}
      data-testid="category-selector"
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
            data-testid={`category-${item.key}`}
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

/**
 * Country picker: horizontally scrolling chips.
 *
 * "World" is the first chip and the default, so a player who never touches this
 * still gets the full hunt. The selection is a *filter* the server applies; the
 * client never pretends to know what the roll will produce.
 */

interface CountryOption {
  code: string;
  flag: string;
  name_en: string;
  name_ru: string;
  discovered?: number;
  total?: number;
}

interface CountrySelectorProps {
  value: string | null;
  onChange: (code: string | null) => void;
  countries: CountryOption[];
  disabled?: boolean;
  className?: string;
}

export function CountrySelector({
  value,
  onChange,
  countries,
  disabled = false,
  className,
}: CountrySelectorProps) {
  const t = useT();
  const { lang } = { lang: 'en' as const };
  void lang;
  const scroller = useRef<HTMLDivElement | null>(null);

  // Keep the active chip in view when the selection changes from elsewhere.
  useEffect(() => {
    const node = scroller.current?.querySelector<HTMLElement>('[data-active="true"]');
    node?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
  }, [value]);

  const chips: Array<{ code: string | null; label: string; flag: string; option?: CountryOption }> = [
    { code: null, label: t('country.all'), flag: '🌍' },
    ...countries.map((option) => ({
      code: option.code,
      flag: option.flag,
      label: t('country.name') === 'Страна' ? option.name_ru : option.name_en,
      option,
    })),
  ];

  return (
    <div
      ref={scroller}
      className={clsx(
        'flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden',
        className,
      )}
      role="tablist"
      aria-label={t('country.aria')}
      data-testid="country-selector"
    >
      {chips.map((chip) => {
        const active = (value ?? null) === chip.code;
        return (
          <button
            key={chip.code ?? 'ALL'}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={disabled}
            data-active={active}
            onClick={() => {
              haptic('light');
              onChange(chip.code);
            }}
            className={clsx(
              'flex min-h-[38px] shrink-0 items-center gap-1.5 rounded-full border px-3 text-[11px] font-semibold uppercase tracking-[0.1em] transition active:scale-[0.97]',
              active
                ? 'border-white/25 bg-white/[0.12] text-white'
                : 'border-white/8 bg-white/[0.03] text-white/50',
              disabled && 'opacity-50',
            )}
            data-testid={`country-${chip.code ?? 'WORLD'}`}
          >
            <span aria-hidden>{chip.flag}</span>
            <span className="whitespace-nowrap">{chip.label}</span>
            {chip.option?.total ? (
              <span className="text-[9px] text-white/30">
                {chip.option.discovered ?? 0}/{chip.option.total}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export { COLLECTIBLE_CATEGORIES };