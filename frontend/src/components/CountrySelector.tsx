import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import clsx from 'clsx';
import { useI18n, type DictKey } from '@/i18n';
import { haptic } from '@/lib/telegram';
import type { CountrySummary } from '@/types';

/**
 * The world selector.
 *
 * A premium mobile world picker, not an HTML `<select>`: the full ISO 3166-1 list is
 * ~250 entries, so it has to search, paginate and distinguish a playable country
 * from one that is still coming soon. Three things must always be visible without
 * scrolling on a 360px phone - the search field, the region rail and the current
 * selection - because a one-handed scroll through 250 rows is not a selector, it is
 * a chore.
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

/** The current country, rendered as the single tappable summary. */
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
  const { t } = useI18n();
  return (
    <button
      type="button"
      onClick={onOpen}
      disabled={disabled}
      data-testid="active-country"
      aria-haspopup="dialog"
      aria-label={t('country.change')}
      className={clsx(
        'group flex w-full items-center gap-3 rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.10] to-white/[0.02] px-4 py-3 text-left transition active:scale-[0.99]',
        disabled && 'opacity-50',
        className,
      )}
      style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.12), 0 12px 30px -20px rgba(0,0,0,0.9)' }}
    >
      <span aria-hidden className="text-3xl leading-none">
        {country?.flag ?? '\u{1F30D}'}
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-[15px] font-black tracking-tight text-white">
          {country ? country.name_en : t('country.world')}
        </span>
        <span className="truncate text-[10px] font-bold uppercase tracking-[0.22em] text-white/40">
          {country ? `${country.code} · ${country.calling_code ?? ''}`.replace(/ · $/, '') : t('country.anywhere')}
        </span>
      </span>
      <span className="flex shrink-0 items-center gap-1 text-[10px] font-bold uppercase tracking-[0.18em] text-white/45">
        {t('country.change')}
        <span aria-hidden className="text-sm leading-none transition group-hover:translate-x-0.5">
          ›
        </span>
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
  const searchRef = useRef<HTMLInputElement | null>(null);

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

  const close = useCallback(() => {
    setOpen(false);
    setQuery('');
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

  // Open from the keyboard, reset the list, and never scroll-lock the page behind
  // the sheet - a stuck body scroll in a Mini App is unrecoverable for the player.
  useEffect(() => {
    if (!open) return;
    setVisible(PAGE_SIZE);
    const id = window.setTimeout(() => searchRef.current?.focus(), 120);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.clearTimeout(id);
      document.body.style.overflow = previous;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [close, open]);

  // Page in more rows as the player scrolls, instead of mounting 250 nodes at once.
  const loadMore = useCallback(() => {
    if (visible < matches.length) {
      setVisible((current) => current + PAGE_SIZE);
      return;
    }
    if (hasMore && !loading) onLoadMore?.();
  }, [hasMore, loading, matches.length, onLoadMore, visible]);

  return (
    <>
      <ActiveCountryButton
        country={active}
        onOpen={() => setOpen(true)}
        disabled={disabled}
        className={className}
      />

      <AnimatePresence>
        {open ? (
          <motion.div
            className="fixed inset-0 z-50 flex items-end sm:items-center sm:justify-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            data-testid="country-sheet"
          >
            <button
              type="button"
              aria-label={t('country.close')}
              className="absolute inset-0 bg-black/70 backdrop-blur-sm"
              onClick={close}
            />
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-label={t('country.picker')}
              className={clsx(
                'relative flex max-h-[86vh] w-full flex-col overflow-hidden rounded-t-3xl border border-white/10 bg-[#080a11] sm:max-w-md sm:rounded-3xl',
              )}
              style={{ boxShadow: '0 -20px 60px -20px rgba(0,0,0,0.9)' }}
              initial={{ y: 40, opacity: 0, scale: 0.98 }}
              animate={{ y: 0, opacity: 1, scale: 1 }}
              exit={{ y: 30, opacity: 0, scale: 0.98 }}
              transition={{ type: 'spring', stiffness: 260, damping: 26 }}
              onScroll={(event) => {
                const node = event.currentTarget;
                if (node.scrollTop + node.clientHeight >= node.scrollHeight - 120) loadMore();
              }}
            >
              <header className="flex items-center gap-3 border-b border-white/8 px-4 pb-3 pt-4">
                <span aria-hidden className="text-xl">
                  🌍
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-black uppercase tracking-[0.2em] text-white">
                    {t('country.picker')}
                  </p>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/35">
                    {t('country.playableCount', { count: countries.filter((c) => c.is_playable).length })}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={close}
                  aria-label={t('country.close')}
                  className="grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/5 text-white/60"
                >
                  ✕
                </button>
              </header>

              <div className="space-y-2.5 px-4 pb-2 pt-3">
                <input
                  ref={searchRef}
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setVisible(PAGE_SIZE);
                  }}
                  placeholder={t('country.search')}
                  aria-label={t('country.search')}
                  inputMode="search"
                  autoComplete="off"
                  className="min-h-[44px] w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-sm text-white outline-none placeholder:text-white/30 focus:border-accent/60"
                  data-testid="country-search"
                />

                <div className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1">
                  {regions.map((code) => (
                    <button
                      key={code}
                      type="button"
                      onClick={() => {
                        setRegion(code);
                        setVisible(PAGE_SIZE);
                      }}
                      data-testid={`country-region-${code}`}
                      className={clsx(
                        'flex min-h-[34px] shrink-0 items-center gap-1.5 rounded-full border px-3 text-[11px] font-bold uppercase tracking-[0.12em] transition',
                        region === code
                          ? 'border-white/25 bg-white/[0.12] text-white'
                          : 'border-white/8 bg-white/[0.02] text-white/40',
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
                    className={clsx(
                      'flex min-h-[40px] flex-1 items-center justify-center gap-2 rounded-xl border text-[11px] font-bold uppercase tracking-[0.16em]',
                      value === null
                        ? 'border-white/25 bg-white/[0.12] text-white'
                        : 'border-white/8 bg-white/[0.02] text-white/45',
                    )}
                  >
                    <span aria-hidden>🌍</span>
                    {t('country.all')}
                  </button>
                  <button
                    type="button"
                    onClick={() => setLockedOnly((current) => !current)}
                    aria-pressed={lockedOnly}
                    data-testid="country-toggle-locked"
                    className={clsx(
                      'flex min-h-[40px] items-center justify-center rounded-xl border px-3 text-[11px] font-bold uppercase tracking-[0.16em]',
                      lockedOnly
                        ? 'border-amber-300/40 bg-amber-300/10 text-amber-200'
                        : 'border-white/8 bg-white/[0.02] text-white/40',
                    )}
                  >
                    {t('country.soon')}
                  </button>
                </div>
              </div>

              <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto overscroll-contain px-3 pb-6 pt-1">
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
                          'flex min-h-[52px] w-full items-center gap-3 rounded-2xl border px-3 text-left transition active:scale-[0.99]',
                          selected
                            ? 'border-white/25 bg-white/[0.10]'
                            : 'border-transparent bg-white/[0.02] hover:bg-white/[0.05]',
                          locked && 'opacity-55',
                        )}
                        style={
                          selected
                            ? { boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.12)' }
                            : undefined
                        }
                      >
                        <span aria-hidden className="text-2xl leading-none">
                          {item.flag}
                        </span>
                        <span className="flex min-w-0 flex-1 flex-col">
                          <span className="truncate text-sm font-bold text-white">{label(item)}</span>
                          <span className="truncate text-[10px] font-semibold uppercase tracking-[0.16em] text-white/35">
                            {item.code}
                            {item.iso_alpha2 ? ` · ${item.iso_alpha2}` : ''}
                            {item.calling_code ? ` · ${item.calling_code}` : ''}
                          </span>
                        </span>
                        {locked ? (
                          <span className="shrink-0 rounded-full border border-amber-300/30 px-2 py-0.5 text-[9px] font-black uppercase tracking-[0.16em] text-amber-200/80">
                            {t('country.locked')}
                          </span>
                        ) : item.total > 0 ? (
                          <span className="shrink-0 text-[10px] font-bold tabular-nums text-white/35">
                            {item.collected}/{item.total}
                          </span>
                        ) : null}
                        {selected ? (
                          <span aria-hidden className="shrink-0 text-sm text-emerald-300">
                            ✓
                          </span>
                        ) : null}
                      </button>
                    </li>
                  );
                })}

                {!loading && shown.length === 0 ? (
                  <li className="px-4 py-10 text-center text-sm text-white/35">{t('country.empty')}</li>
                ) : null}

                {loading ? (
                  <li className="px-4 py-6 text-center text-xs uppercase tracking-[0.2em] text-white/30">
                    {t('common.loading')}
                  </li>
                ) : null}
              </ul>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </>
  );
}

export default CountrySelector;