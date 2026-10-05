import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import clsx from 'clsx';

import { CountrySelector } from '@/components/CountrySelector';
import { EmptyState, LoadingSpinner } from '@/components/States';
import { useI18n, type I18nValue } from '@/i18n';
import { SPRING, useReducedMotion } from '@/lib/motion';
import { useRouteBackButton } from '@/lib/useRouteBackButton';
import { useNavigate } from 'react-router-dom';
import { countries as countriesApi, game } from '@/services/api';
import { useActiveCountry } from '@/store/activeCountry';
import type { CountrySummary } from '@/types';

const PAGE_SIZE = 60;

/**
 * The world: a collector's atlas, not a table of countries.
 *
 * Each entry answers the questions a collector actually has about a country - how far in
 * I am, how many formats exist, what my best find there is, how many regions I have
 * touched, whether I can hunt it yet, and whether an event is boosting it right now.
 *
 * The call to action is phrased as an intention, not a filter: **HUNT THIS COUNTRY**.
 * The player should read the screen as "I'm going to hunt Japan", not "I am setting a
 * filter to JPN".
 *
 * The atlas pages. The ISO list is ~250 entries, so shipping them all in one payload and
 * one DOM would cost more than the screen can afford on a phone.
 */
export function WorldPage() {
  useRouteBackButton();
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

  // One payload for the selector, cached for the whole session.
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
  const eventMultipliers = query.data?.event?.country_multipliers ?? {};

  const hunt = async (code: string | null) => {
    if (code === null) return;
    try {
      const data = await countriesApi.setActive(code);
      applyCountry(data);
      navigate('/');
    } catch {
      // The backend refused: nothing changes and the player stays where they are.
      void activeQuery.refetch();
    }
  };

  if (query.isLoading) return <LoadingSpinner label={t('common.loading')} />;

  return (
    <div className="flex flex-col gap-4" data-testid="world-page">
      {/*
        The atlas header. A title, one number that matters, and nothing else: this screen's
        job is to let the player scan 250 countries, so the header must not cost them a
        row of the list.
      */}
      <header className="flex flex-col gap-0.5">
        <h1 className="t-h1 text-white">{t('nav.world')}</h1>
        <p className="t-caption text-white/50">
          {t('world.overall')} <span className="font-bold text-white/80">{Math.round(overall)}%</span>
          <span className="text-white/25"> · </span>
          {query.data?.total_collected ?? 0}/{query.data?.total_plates ?? 0}
        </p>
        <p className="t-micro text-white/30">
          {query.data?.playable_total ?? 0} {t('country.playableCount', { count: '' }).trim()}
          <span className="text-white/20"> · </span>
          {query.data?.locked_total ?? 0} {t('world.comingSoon')}
        </p>
      </header>

      {/* A single progress bar: the atlas's own completion, in the place you look for it. */}
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-accent/70 to-brass/70"
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(overall, 1)}%` }}
          transition={SPRING.settle}
        />
      </div>

      {selectorCountries.length ? (
        <CountrySelector
          value={activeQuery.data?.code ?? null}
          onChange={(code) => void hunt(code)}
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
        /*
          One column on every phone width. A two-column grid on a 360px screen gives each
          country 160px, which is not enough for a flag, a name and a progress bar -
          so the grid only ever appears when there is genuinely room for it.
        */
        <ul className="flex flex-col gap-2">
          {countries.map((country) => (
            <CountryCard
              key={country.code}
              country={country}
              name={lang === 'ru' ? country.name_ru : country.name_en}
              eventMultiplier={eventMultipliers[country.code]}
              t={t}
              onHunt={() => void hunt(country.code)}
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
  eventMultiplier,
  t,
  onHunt,
}: {
  country: CountrySummary;
  name: string;
  eventMultiplier: number | undefined;
  t: I18nValue['t'];
  onHunt: () => void;
}) {
  const reduced = useReducedMotion();
  const locked = !country.is_playable;
  const percent = country.total ? Math.round((country.collected / country.total) * 100) : 0;
  const left = Math.max(0, country.total - country.collected);
  const boosted = Boolean(eventMultiplier && eventMultiplier > 1);

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
        'relative flex flex-col gap-2.5 overflow-hidden rounded-[16px] border bg-white/[0.025] p-3',
        locked ? 'border-white/[0.04] opacity-60' : 'border-white/[0.07]',
        boosted && !locked && 'border-amber-300/25',
      )}
      whileTap={locked || reduced ? undefined : { scale: 0.99 }}
      data-testid={`world-country-${country.code}`}
      data-locked={locked}
    >
      <div className="flex items-start gap-3">
        <span className="text-[28px] leading-none" aria-hidden>
          {country.flag}
        </span>
        <div className="min-w-0 flex-1">
          {/* Case is kept: a country name is a proper noun, and uppercasing a 20-character
              Russian name at 0.2em tracking is what made the old atlas look sparse. */}
          <p className="truncate t-h2 text-white">{name}</p>
          <p className="mt-0.5 truncate t-caption text-white/45">
            {locked
              ? `${country.code} · ${t('world.comingSoon')}`
              : `${country.collected} / ${country.total} · ${percent}%`}
          </p>
          {!locked ? (
            <p className="mt-0.5 truncate text-[11px] text-white/30">
              {t('world.formats', { count: country.total })}
              <span className="text-white/20"> · </span>
              {t('world.regions', {
                found: country.regions_collected,
                total: country.regions_total,
              })}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {boosted ? (
            <span className="rounded-md border border-amber-300/30 bg-amber-300/10 px-1.5 py-0.5 text-[9px] font-bold text-amber-200">
              ×{eventMultiplier?.toFixed(1)}
            </span>
          ) : null}
          {locked ? (
            <span className="rounded-md border border-amber-300/25 px-1.5 py-0.5 text-[9px] font-semibold tracking-[0.06em] text-amber-200/70">
              {t('country.locked')}
            </span>
          ) : country.best_rarity ? (
            <span className="rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-white/55">
              {country.best_rarity}
            </span>
          ) : null}
        </div>
      </div>

      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-accent/70 to-brass/70"
          initial={reduced ? false : { width: 0 }}
          animate={{ width: `${Math.max(percent, 2)}%` }}
          transition={SPRING.settle}
        />
      </div>

      <div className="flex items-center justify-between gap-2">
        <span
          className={clsx(
            't-micro',
            hook?.tone === 'gold' && 'text-amber-300',
            hook?.tone === 'hot' && 'text-rose-300',
            hook?.tone === 'warm' && 'text-emerald-300',
            hook?.tone === 'muted' && 'text-amber-200/60',
            !hook && 'text-white/30',
          )}
        >
          {hook?.text ?? `${percent}%`}
        </span>
        {!locked && (
          <button
            type="button"
            onClick={onHunt}
            className="min-h-[36px] rounded-full border border-white/12 bg-white/[0.04] px-3.5 text-[11px] font-semibold tracking-[0.04em] text-white/80 transition active:scale-95"
          >
            {t('world.huntThisCountry')}
          </button>
        )}
      </div>
    </motion.li>
  );
}

export default WorldPage;