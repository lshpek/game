import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import clsx from 'clsx';

import { CountrySelector } from '@/components/CountrySelector';
import { RarityBadge } from '@/components/RarityBadge';
import { EmptyState, LoadingSpinner } from '@/components/States';
import { useI18n, type I18nValue } from '@/i18n';
import { rarityColor } from '@/lib/format';
import { SPRING, useReducedMotion } from '@/lib/motion';
import { playTap } from '@/lib/sound';
import { useRouteBackButton } from '@/lib/useRouteBackButton';
import { useNavigate } from 'react-router-dom';
import { countries as countriesApi, game } from '@/services/api';
import { useActiveCountry } from '@/store/activeCountry';
import type { CountrySummary } from '@/types';

const PAGE_SIZE = 60;

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
    playTap();
    try {
      const data = await countriesApi.setActive(code);
      applyCountry(data);
      navigate('/');
    } catch {
      void activeQuery.refetch();
    }
  };

  if (query.isLoading) return <LoadingSpinner label={t('common.loading')} />;

  return (
    <div className="flex flex-col gap-4" data-testid="world-page">
      {/* Collector's Global Passport Header Card */}
      <header className="stage flex flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <span className="eyebrow flex items-center gap-1.5">
              <span aria-hidden="true">🌍</span>
              GLOBAL ATLAS
            </span>
            <h1 className="mt-0.5 t-h1 text-white">{t('nav.world')}</h1>
          </div>
          <div className="rounded-2xl border border-brass/30 bg-brass/10 px-3 py-1.5 text-right">
            <span className="number-display block text-[18px] font-bold leading-none text-brass-soft">
              {Math.round(overall)}%
            </span>
            <span className="mt-0.5 block text-[10px] font-semibold uppercase tracking-wider text-white/50">
              {query.data?.total_collected ?? 0}/{query.data?.total_plates ?? 0}
            </span>
          </div>
        </div>

        <div className="h-2 overflow-hidden rounded-full bg-white/[0.08]">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-accent via-brass to-amber-300"
            initial={{ width: 0 }}
            animate={{ width: `${Math.max(overall, 2)}%` }}
            transition={SPRING.settle}
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-white/55">
          <span>
            🟢 <strong className="text-white/85">{query.data?.playable_total ?? 0}</strong>{' '}
            {t('country.playableCount', { count: '' }).trim()}
          </span>
          <span>
            🔒 <strong className="text-white/70">{query.data?.locked_total ?? 0}</strong>{' '}
            {t('world.comingSoon')}
          </span>
        </div>
      </header>

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
          icon="🌍"
          title={t('world.empty')}
          hint={t('world.emptyHint')}
          action={
            <button type="button" className="btn-primary" onClick={() => navigate('/')}>
              {t('nav.roll')}
            </button>
          }
        />
      ) : (
        <ul className="flex flex-col gap-2.5">
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
        <div className="flex items-center justify-center gap-2 pt-1">
          <button
            type="button"
            className="btn-ghost !min-h-[42px] !px-4"
            disabled={page <= 0}
            onClick={() => setPage((current) => Math.max(0, current - 1))}
          >
            ←
          </button>
          <span className="font-mono text-xs text-white/60">
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
  const completed = !locked && country.total > 0 && left === 0;
  const bestColor = country.best_rarity ? rarityColor(country.best_rarity) : undefined;

  const hook = (() => {
    if (locked) return { text: t('world.comingSoon'), tone: 'muted' as const };
    if (completed) return { text: `✓ ${t('world.complete')}`, tone: 'gold' as const };
    if (left > 0 && left <= 5) return { text: t('world.almost', { count: left }), tone: 'hot' as const };
    if (percent >= 80) return { text: t('world.close', { percent }), tone: 'warm' as const };
    return null;
  })();

  return (
    <motion.li
      className={clsx(
        'glass relative flex flex-col gap-3 overflow-hidden p-3.5',
        locked && 'opacity-55 saturate-50',
        boosted && !locked && 'border-amber-300/35',
        completed && 'border-emerald-400/35',
      )}
      style={
        bestColor && !locked
          ? {
              borderColor: `${bestColor}33`,
            }
          : undefined
      }
      whileTap={locked || reduced ? undefined : { scale: 0.99 }}
      data-testid={`world-country-${country.code}`}
      data-locked={locked}
    >
      <div className="flex items-start gap-3">
        {/* Tactile Passport Stamp / Flag Emblem */}
        <div className="relative grid h-12 w-12 shrink-0 place-items-center rounded-2xl border border-white/10 bg-white/[0.04] text-[28px] leading-none shadow-inner">
          <span aria-hidden>{country.flag}</span>
          <span className="absolute -bottom-1 rounded bg-ink-950 px-1 py-[1px] font-mono text-[8px] font-bold tracking-wider text-white/65 ring-1 ring-white/15">
            {country.iso_alpha2 || country.code}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate t-h2 text-white">{name}</p>
            {boosted ? (
              <span className="shrink-0 rounded-full border border-amber-300/40 bg-amber-300/15 px-2 py-0.5 font-mono text-[10px] font-bold text-amber-200">
                🔥 ×{eventMultiplier?.toFixed(1)}
              </span>
            ) : null}
          </div>

          <p className="mt-0.5 truncate t-caption text-white/55">
            {locked
              ? `${country.code} · ${t('world.comingSoon')}`
              : `${country.collected} / ${country.total} · ${percent}%`}
          </p>

          {!locked ? (
            <p className="mt-0.5 truncate text-[11px] text-white/40">
              {t('world.formats', { count: country.total })}
              <span className="text-white/20"> · </span>
              {t('world.regions', {
                found: country.regions_collected,
                total: country.regions_total,
              })}
            </p>
          ) : null}
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1.5">
          {locked ? (
            <span className="rounded-lg border border-amber-300/25 bg-amber-300/[0.06] px-2 py-0.5 text-[9.5px] font-semibold tracking-[0.06em] text-amber-200/75">
              🔒 {t('country.locked')}
            </span>
          ) : country.best_rarity ? (
            <RarityBadge rarity={country.best_rarity} size="sm" />
          ) : null}
        </div>
      </div>

      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.07]">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-accent via-brass to-amber-300"
          initial={reduced ? false : { width: 0 }}
          animate={{ width: `${Math.max(percent, 2)}%` }}
          transition={SPRING.settle}
        />
      </div>

      <div className="flex items-center justify-between gap-2">
        <span
          className={clsx(
            't-micro font-bold',
            hook?.tone === 'gold' && 'text-emerald-300',
            hook?.tone === 'hot' && 'text-rose-300',
            hook?.tone === 'warm' && 'text-amber-300',
            hook?.tone === 'muted' && 'text-amber-200/60',
            !hook && 'text-white/40',
          )}
        >
          {hook?.text ?? `${percent}%`}
        </span>
        {!locked && (
          <button
            type="button"
            onClick={onHunt}
            className="min-h-[36px] rounded-xl border border-brass/35 bg-gradient-to-b from-brass/20 to-brass/10 px-3.5 font-display text-[11px] font-bold tracking-[0.05em] text-brass-soft transition hover:border-brass/60 active:scale-95"
          >
            🎯 {t('world.huntThisCountry')}
          </button>
        )}
      </div>
    </motion.li>
  );
}

export default WorldPage;