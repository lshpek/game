import { useCallback, useMemo, useState } from 'react';
import clsx from 'clsx';

import { BottomSheet } from '@/components/BottomSheet';
import { useI18n, type DictKey } from '@/i18n';
import { haptic } from '@/lib/telegram';
import type { CountrySummary } from '@/types';

/**
 * The world picker.
 *
 * The full ISO 3166-1 list is ~250 entries, so this has to search, filter by region and
 * distinguish a playable country from one that is still coming soon - and all three of
 * those controls must be reachable without scrolling, on a 360px phone. A one-handed
 * scroll through 250 rows is not a selector, it is a chore.
 *
 * Everything is a real `<button>`: a locked country is `disabled` rather than merely
 * dimmed, so assistive tech and a keyboard both report the same state the eye does.
 */

const PAGE_SIZE = 40;

const REGION_ORDER = [
  'ALL',
  'EUROPE',
  'CIS',
  'AMERICAS',
  'ASIA',
  'MIDEAST',
  'AFRICA',
  'OCEANIA',
  'ANTARCTIC',
] as const;

type RegionCode = (typeof REGION_ORDER)[number];

const REGION_LABELS: Record<RegionCode, DictKey> = {
  ALL: 'country.regionAll',
  EUROPE: 'country.regionEurope',
  CIS: 'country.regionCis',
  AMERICAS: 'country.regionAmericas',
  ASIA: 'country.regionAsia',
  MIDEAST: 'country.regionMideast',
  AFRICA: 'country.regionAfrica',
  OCEANIA: 'country.regionOceania',
  ANTARCTIC: 'country.regionAntarctic',
};

const REGION_FLAGS: Record<RegionCode, string> = {
  ALL: '\u{1F30D}',
  EUROPE: '\u{1F1EA}\u{1F1FA}',
  CIS: '\u{1F1F7}\u{1F1FA}',
  AMERICAS: '\u{1F1FA}\u{1F1F8}',
  ASIA: '\u{1F1F0}\u{1F1F7}',
  MIDEAST: '\u{1F1F6}\u{1F1EA}',
  AFRICA: '\u{1F1FF}\u{1F1E6}',
  OCEANIA: '\u{1F1F0}\u{1F1FA}',
  ANTARCTIC: '\u{1F6F2}',
};

export interface CountrySelectorProps {
  value: string | null;
  onChange: (code: string | null) => void;
  countries: CountrySummary[];
  /** When the list is paged from the API, this fetches the next window. */
  onLoadMore?: () => void;
  hasMore?: boolean;
  loading?: boolean;
  disabled?: boolean;
  className?: string;
}

/**
 * The current country as a single tappable summary.
 *
 * This is the whole selector on the hunt screen: one row that says where you are
 * hunting and opens the sheet. A flag, the name, and the code - no instructions, no
 * "Change" button competing with the row itself.
 */
export function ActiveCountryButton({
  country,
  onOpen,
  disabled = false,
  className,
}: {
  country: CountrySummary | null;
  onOpen: () => void;
  disabled?: boolean;
  className?: string;
}) {
  const { t, lang } = useI18n();
  return (
    <button
      type="button"
      onClick={onOpen}
      disabled={disabled}
      data-testid="active-country"
      aria-haspopup="dialog"
      aria-label={t('country.changeAria')}
      className={clsx(
        'glass-interactive flex w-full items-center gap-3 px-3.5 py-3 text-left',
        disabled && 'pointer-events-none opacity-50',
        className,
      )}
    >
      <span aria-hidden className="text-[26px] leading-none">
        {country?.flag ?? '\u{1F30D}'}
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate t-h2 text-white">
          {country ? (lang === 'ru' ? country.name_ru : country.name_en) : t('country.world')}
        </span>
        <span className="truncate t-micro text-white/40">
          {country
            ? `${country.code}${country.calling_code ? ` · ${country.calling_code}` : ''}`
            : t('country.anywhere')}
        </span>
      </span>
      <span
        aria-hidden
        className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-white/10 bg-white/[0.04] text-[13px] text-white/50"
      >
        ⌄
      </span>
    </button>
  );
}

export function CountrySelector({
  value,
  onChange,
  countries,
  onLoadMore,
  hasMore = false,
  loading = false,
  disabled = false,
  className,
}: CountrySelectorProps) {
  const { t, lang } = useI18n();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [region, setRegion] = useState<RegionCode>('ALL');
  const [lockedOnly, setLockedOnly] = useState(false);
  const [visible, setVisible] = useState(PAGE_SIZE);

  const regions = useMemo(() => {
    const present = new Set(countries.map((item) => item.region_group));
    return REGION_ORDER.filter((code) => code === 'ALL' || present.has(code));
  }, [countries]);

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return countries.filter((item) => {
      if (region !== 'ALL' && item.region_group !== region) return false;
      if (lockedOnly && item.is_playable) return false;
      if (!needle) return true;
      // Code, both ISO forms, the calling code and both display names, so "ru",
      // "rus", "russia" and the local name all find the same country.
      return (
        item.code.toLowerCase().includes(needle) ||
        (item.iso_alpha2 ?? '').toLowerCase().includes(needle) ||
        (item.calling_code ?? '').includes(needle) ||
        item.name_en.toLowerCase().includes(needle) ||
        item.name_ru.toLowerCase().includes(needle)
      );
    });
  }, [countries, lockedOnly, query, region]);

  const shown = matches.slice(0, visible);
  const active = countries.find((item) => item.code === value) ?? null;
  const label = (item: CountrySummary) => (lang === 'ru' ? item.name_ru : item.name_en);
  const playableCount = countries.filter((item) => item.is_playable).length;

  const close = useCallback(() => {
    setOpen(false);
    setQuery('');
    setRegion('ALL');
    setLockedOnly(false);
    setVisible(PAGE_SIZE);
  }, []);

  const choose = useCallback(
    (code: string | null) => {
      haptic('light');
      onChange(code);
      close();
    },
    [close, onChange],
  );

  // Page in more rows as the player scrolls, instead of mounting 250 nodes at once.
  const loadMore = useCallback(() => {
    if (visible < matches.length) {
      setVisible((current) => current + PAGE_SIZE);
      return;
    }
    if (hasMore && !loading) onLoadMore?.();
  }, [hasMore, loading, matches.length, onLoadMore, visible]);

  /*
   * Fires on the sheet's real scroll container, close to the bottom.
   *
   * A 200px threshold means the next page is already in flight while the last few rows
   * are still visible, which is what stops the list from stuttering when it reaches the
   * end. `visible >= matches.length` is the guard that keeps it from re-requesting a
   * page the server already gave us.
   */
  const handleScroll = useCallback(
    (metrics: { scrollTop: number; clientHeight: number; scrollHeight: number }) => {
      if (metrics.scrollTop + metrics.clientHeight < metrics.scrollHeight - 200) return;
      loadMore();
    },
    [loadMore],
  );

  return (
    <>
      <ActiveCountryButton
        country={active}
        onOpen={() => setOpen(true)}
        disabled={disabled}
        className={className}
      />

      <BottomSheet
        open={open}
        onClose={close}
        label={t('country.picker')}
        title={t('country.picker')}
        subtitle={t('country.playableCount', { count: playableCount })}
        onScroll={handleScroll}
      >
        <div className="sticky top-0 z-10 space-y-2.5 bg-ink-900/95 px-[var(--gutter)] pb-3 pt-1 backdrop-blur">
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setVisible(PAGE_SIZE);
            }}
            placeholder={t('country.search')}
            aria-label={t('country.search')}
            inputMode="search"
            autoComplete="off"
            className="min-h-[46px] w-full rounded-2xl border border-white/10 bg-white/[0.05] px-4 text-body text-white outline-none placeholder:text-white/30 focus:border-accent/60"
            data-testid="country-search"
          />

          {/*
            The region row scrolls sideways and *only* sideways.

            `touch-pan-x` gives the gesture budget to this element horizontally and
            refuses it vertically, so the sheet's own list keeps the vertical swipe and
            the page never picks up a stray horizontal pan.
          */}
          <div
            className="no-scrollbar -mx-1 flex touch-pan-x gap-1.5 overflow-x-auto overflow-y-hidden px-1"
            data-testid="country-region-row"
          >
            {regions.map((code) => (
              <button
                key={code}
                type="button"
                onClick={() => {
                  haptic('light');
                  setRegion(code);
                  setVisible(PAGE_SIZE);
                }}
                data-testid={`country-region-${code}`}
                aria-pressed={region === code}
                className={clsx(
                  'flex min-h-[36px] shrink-0 items-center gap-1.5 rounded-full border px-3 t-micro transition active:scale-95',
                  region === code
                    ? 'border-white/25 bg-white/[0.12] text-white'
                    : 'border-white/8 bg-white/[0.02] text-white/45',
                )}
              >
                <span aria-hidden>{REGION_FLAGS[code]}</span>
                {t(REGION_LABELS[code])}
              </button>
            ))}
          </div>

          <div className="flex gap-1.5">
            <button
              type="button"
              onClick={() => choose(null)}
              data-testid="country-option-WORLD"
              aria-pressed={value === null}
              className={clsx(
                'flex min-h-[42px] flex-1 items-center justify-center gap-2 rounded-xl border t-micro transition active:scale-[0.98]',
                value === null
                  ? 'border-white/25 bg-white/[0.12] text-white'
                  : 'border-white/8 bg-white/[0.02] text-white/50',
              )}
            >
              <span aria-hidden>{REGION_FLAGS.ALL}</span>
              {t('country.all')}
            </button>
            <button
              type="button"
              onClick={() => setLockedOnly((current) => !current)}
              aria-pressed={lockedOnly}
              data-testid="country-toggle-locked"
              className={clsx(
                'flex min-h-[42px] items-center justify-center rounded-xl border px-3 t-micro transition active:scale-[0.98]',
                lockedOnly
                  ? 'border-amber-300/40 bg-amber-300/10 text-amber-200'
                  : 'border-white/8 bg-white/[0.02] text-white/45',
              )}
            >
              {t('country.soon')}
            </button>
          </div>
        </div>

        {/*
          The list is *not* the scroll container - the sheet's own area is, and it is what
          reports scrolling to `handleScroll`. A `touch-pan-y` row keeps the vertical
          gesture here so momentum and pull-to-refresh-style overscroll stay inside the
          sheet.
        */}
        <ul className="touch-pan-y space-y-1 px-2 pb-4">
          {shown.map((item) => {
            const selected = item.code === value;
            const locked = !item.is_playable;
            return (
              <li key={item.code}>
                <button
                  type="button"
                  disabled={locked}
                  onClick={() => choose(item.code)}
                  data-testid={`country-option-${item.code}`}
                  data-locked={locked}
                  aria-current={selected}
                  className={clsx(
                    'flex min-h-[54px] w-full items-center gap-3 rounded-2xl border px-3 text-left transition active:scale-[0.99]',
                    selected
                      ? 'border-white/25 bg-white/[0.10]'
                      : 'border-transparent bg-white/[0.02] active:bg-white/[0.06]',
                    locked && 'opacity-50',
                  )}
                >
                  <span aria-hidden className="text-[22px] leading-none">
                    {item.flag}
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate t-body font-semibold text-white">{label(item)}</span>
                    <span className="truncate t-micro text-white/35">
                      {item.code}
                      {item.iso_alpha2 ? ` · ${item.iso_alpha2}` : ''}
                      {item.calling_code ? ` · ${item.calling_code}` : ''}
                    </span>
                  </span>
                  {locked ? (
                    <span className="shrink-0 rounded-full border border-amber-300/30 px-2 py-0.5 t-micro text-amber-200/80">
                      {t('country.locked')}
                    </span>
                  ) : item.total > 0 ? (
                    <span className="shrink-0 t-micro tabular-nums text-white/35">
                      {item.collected}/{item.total}
                    </span>
                  ) : null}
                  {selected ? (
                    <span aria-hidden className="shrink-0 text-[13px] text-emerald-300">
                      ✓
                    </span>
                  ) : null}
                </button>
              </li>
            );
          })}

          {!loading && shown.length === 0 ? (
            <li className="px-4 py-10 text-center t-caption text-white/35">{t('country.empty')}</li>
          ) : null}

          {loading ? (
            <li className="px-4 py-6 text-center t-micro text-white/30">{t('common.loading')}</li>
          ) : null}
        </ul>
      </BottomSheet>
    </>
  );
}

export default CountrySelector;
