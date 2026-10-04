import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import clsx from 'clsx';
import { CountrySelector } from '@/components/CountrySelector';
import { EmptyState, LoadingSpinner } from '@/components/States';
import { useI18n, type I18nValue } from '@/i18n';
import { useNavigate } from 'react-router-dom';
import { countries as countriesApi, game } from '@/services/api';
import { useActiveCountry } from '@/store/activeCountry';
import type { CountrySummary } from '@/types';

const PAGE_SIZE = 60;

/**
 * The world screen: country completion across the whole planet.
 *
 * The design goal is a reason to come back, so every card answers the same three
 * questions: how close am I, what is left, and what am I missing. A country that is
 * 91% complete with three items left reads as a nearly finished job; a bare "12/120"
 * does not.
 *
 * The atlas pages: the ISO list is ~250 entries, so shipping them all in one payload
 * and one DOM would cost more than the screen can afford on a phone.
 */
export function WorldPage() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const applyCountry = useActiveCountry((state) => state.apply);
  const [page, setPage] = useState(0);

  const query = useQuery({
    queryKey: ['world', page],
    queryFn: () => game.world({ limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    staleTime: 60_000,
  });

  const activeQuery = useQuery({
    queryKey: ['countries', 'active'],
    queryFn: countriesApi.active,
    staleTime: 60_000,
  });

  // Every country for the selector, cached once for the whole session.
  const selectorQuery = useQuery({
    queryKey: ['countries', 'selector'],
    queryFn: () => countriesApi.list({ limit: 250 }),
    staleTime: 300_000,
  });

  const countries = useMemo<CountrySummary[]>(
    () => (query.data?.countries ?? []) as CountrySummary[],
    [query.data],
  );
  const selectorCountries = useMemo<CountrySummary[]>(
    () => (selectorQuery.data?.items ?? []) as CountrySummary[],
    [selectorQuery.data],
  );

  const overall = Number(query.data?.progress ?? 0);
  const totalPages = Math.max(1, Math.ceil((query.data?.countries_total ?? 0) / PAGE_SIZE));

  const select = async (code: string | null) => {
    if (code === null) return;
    try {
      const data = await countriesApi.setActive(code);
      applyCountry(data);
      navigate('/');
    } catch {
      // The backend refused; nothing changes and the player stays where they are.
      void activeQuery.refetch();
    }
  };

  if (query.isLoading) return <LoadingSpinner label={t('common.loading')} />;

  return (
    <div className="flex flex-col gap-4 pb-28" data-testid="world-page">
      <header className="flex flex-col gap-1 px-1">
        <h1 className="text-lg font-black uppercase tracking-[0.24em] text-white">{t('nav.world')}</h1>
        <p className="text-xs text-white/45">
          {t('world.overall')} {Math.round(overall)}% · {query.data?.total_collected ?? 0}/
          {query.data?.total_plates ?? 0}
        </p>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/30">
          {query.data?.playable_total ?? 0} {t('country.playableCount', { count: '' }).trim()} ·{' '}
          {query.data?.locked_total ?? 0} {t('world.comingSoon')}
        </p>
      </header>

      {selectorCountries.length ? (
        <CountrySelector
          value={activeQuery.data?.code ?? null}
          onChange={(code) => void select(code)}
          countries={selectorCountries}
          loading={activeQuery.isFetching}
        />
      ) : null}

      {countries.length === 0 ? (
        <EmptyState
          icon="\u{1F30D}"
          title={t('world.empty')}
          hint={t('world.emptyHint')}
          action={
            <button type="button" className="btn-primary" onClick={() => navigate('/')}>
              {t('nav.roll')}
            </button>
          }
        />
      ) : (
        <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {countries.map((country) => (
            <CountryCard
              key={country.code}
              country={country}
              name={lang === 'ru' ? country.name_ru : country.name_en}
              t={t}
              onSelect={() => void select(country.code)}
            />
          ))}
        </ul>
      )}

      {totalPages > 1 ? (
        <div className="flex items-center justify-center gap-2">
          <button
            type="button"
            className="btn-ghost !min-h-[42px] !px-4"
            disabled={page <= 0}
            onClick={() => setPage((current) => Math.max(0, current - 1))}
          >
            ←
          </button>
          <span className="text-xs text-white/50">
            {t('common.page')} {page + 1} / {totalPages}
          </span>
          <button
            type="button"
            className="btn-ghost !min-h-[42px] !px-4"
            disabled={page + 1 >= totalPages}
            onClick={() => setPage((current) => current + 1)}
          >
            →
          </button>
        </div>
      ) : null}
    </div>
  );
}

function CountryCard({
  country,
  name,
  t,
  onSelect,
}: {
  country: CountrySummary;
  name: string;
  t: I18nValue['t'];
  onSelect: () => void;
}) {
  const locked = !country.is_playable;
  const percent = country.total ? Math.round((country.collected / country.total) * 100) : 0;
  const left = Math.max(0, country.total - country.collected);

  // Completion hooks, strongest first. These are what pull the player back.
  const hook = (() => {
    if (locked) return { text: t('world.comingSoon'), tone: 'muted' as const };
    if (country.total && left === 0) return { text: t('world.complete'), tone: 'gold' as const };
    if (left > 0 && left <= 5) return { text: t('world.almost', { count: left }), tone: 'hot' as const };
    if (percent >= 80) return { text: t('world.close', { percent }), tone: 'warm' as const };
    return null;
  })();

  return (
    <motion.li
      className={clsx(
        'relative overflow-hidden rounded-2xl border bg-white/[0.03] p-4',
        locked ? 'border-white/5 opacity-60' : 'border-white/8',
      )}
      whileTap={locked ? undefined : { scale: 0.98 }}
      data-testid={`world-country-${country.code}`}
      data-locked={locked}
    >
      <div className="flex items-center gap-3">
        <span className="text-2xl" aria-hidden>
          {country.flag}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-bold uppercase tracking-[0.12em] text-white">{name}</p>
          <p className="text-[11px] text-white/40">
            {locked ? `${country.code} · ${t('world.comingSoon')}` : `${country.collected} / ${country.total} · ${percent}%`}
          </p>
        </div>
        {locked ? (
          <span className="shrink-0 rounded-md border border-amber-300/25 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.14em] text-amber-200/70">
            {t('country.locked')}
          </span>
        ) : country.best_rarity ? (
          <span className="shrink-0 rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-white/60">
            {country.best_rarity}
          </span>
        ) : null}
      </div>

      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.07]">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-white/40 to-white/80"
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(percent, 2)}%` }}
          transition={{ type: 'spring', stiffness: 120, damping: 22 }}
          style={{ width: `${Math.max(percent, 2)}%` }}
        />
      </div>

      <div className="mt-2 flex items-center justify-between">
        <span
          className={clsx(
            'text-[10px] font-bold uppercase tracking-[0.18em]',
            hook?.tone === 'gold' && 'text-amber-300',
            hook?.tone === 'hot' && 'text-rose-300',
            hook?.tone === 'warm' && 'text-emerald-300',
            hook?.tone === 'muted' && 'text-amber-200/60',
            !hook && 'text-white/30',
          )}
        >
          {hook?.text ?? `${percent}%`}
        </span>
        {!locked ? (
          <button
            type="button"
            onClick={onSelect}
            className="min-h-[32px] rounded-full border border-white/12 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-white/70 active:scale-95"
          >
            {t('world.selectCountry')}
          </button>
        ) : null}
      </div>
    </motion.li>
  );
}

export default WorldPage;