import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import clsx from 'clsx';
import { CountrySelector } from '@/components/Selectors';
import { EmptyState, LoadingSpinner } from '@/components/States';
import { useI18n, type I18nValue } from '@/i18n';
import { useNavigate } from 'react-router-dom';
import { game } from '@/services/api';
import { formatCoins } from '@/lib/format';

interface CountryProgress {
  code: string;
  flag: string;
  name_en: string;
  name_ru: string;
  discovered: number;
  total: number;
  by_category: Record<string, { discovered: number; total: number }>;
  rarest: { plate_text: string; rarity: string } | null;
  is_secret_found: boolean;
}

/**
 * The world screen: country completion across the whole Number Universe.
 *
 * The design goal is a reason to come back, so every card answers the same three
 * questions: how close am I, what is left, and what am I missing. A country that is
 * 91% complete with three items left reads as a nearly finished job; a bare "12/120"
 * does not.
 */
export function WorldPage() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ['world'],
    queryFn: () => game.world(),
    staleTime: 60_000,
  });

  const countries = useMemo<CountryProgress[]>(() => {
    const raw = (query.data?.countries ?? []) as unknown as Array<Record<string, unknown>>;
    return raw
      .map((item) => {
        const config = (item.config ?? {}) as Record<string, unknown>;
        return {
          code: String(item.code ?? ''),
          flag: String(item.flag ?? ''),
          name_en: String(item.name_en ?? item.code ?? ''),
          name_ru: String(item.name_ru ?? item.code ?? ''),
          discovered: Number(item.discovered ?? config.discovered ?? 0),
          total: Number(item.total ?? config.total ?? 0),
          by_category: (config.by_category ?? {}) as CountryProgress['by_category'],
          rarest: (config.rarest ?? null) as CountryProgress['rarest'],
          is_secret_found: Boolean(config.is_secret_found),
        };
      })
      .filter((entry) => entry.code !== '')
      .sort((left, right) => right.discovered / Math.max(right.total, 1) - left.discovered / Math.max(left.total, 1));
  }, [query.data]);

  const visible = useMemo(
    () => (filter ? countries.filter((entry) => entry.code === filter) : countries),
    [countries, filter],
  );

  const chips = countries.map((entry) => ({
    code: entry.code,
    flag: entry.flag,
    name_en: entry.name_en,
    name_ru: entry.name_ru,
    discovered: entry.discovered,
    total: entry.total,
  }));

  const overall = Number(query.data?.progress ?? 0);

  if (query.isLoading) return <LoadingSpinner label={t('common.loading')} />;

  return (
    <div className="flex flex-col gap-4 pb-28" data-testid="world-page">
      <header className="flex flex-col gap-1 px-1">
        <h1 className="text-lg font-black uppercase tracking-[0.24em] text-white">
          {t('nav.world')}
        </h1>
        <p className="text-xs text-white/45">
          {t('world.overall')} {Math.round(overall)}% · {query.data?.total_collected ?? 0}/
          {query.data?.total_plates ?? 0}
        </p>
      </header>

      {countries.length ? (
        <CountrySelector value={filter} onChange={setFilter} countries={chips} />
      ) : null}

      {visible.length === 0 ? (
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
        <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {visible.map((country) => (
            <CountryCard
              key={country.code}
              country={country}
              name={lang === 'ru' ? country.name_ru : country.name_en}
              t={t}
              onHunt={() => navigate('/')}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function CountryCard({
  country,
  name,
  t,
  onHunt,
}: {
  country: CountryProgress;
  name: string;
  t: I18nValue['t'];
  onHunt: () => void;
}) {
  const percent = country.total ? Math.round((country.discovered / country.total) * 100) : 0;
  const left = Math.max(0, country.total - country.discovered);

  // Completion hooks, strongest first. These are what pull the player back.
  const hook = (() => {
    if (country.total && left === 0) return { text: t('world.complete'), tone: 'gold' as const };
    if (left > 0 && left <= 5) {
      return {
        text: t('world.almost', { count: left }),
        tone: 'hot' as const,
      };
    }
    if (percent >= 80) {
      return { text: t('world.close', { percent }), tone: 'warm' as const };
    }
    if (country.is_secret_found) return { text: t('world.secretFound'), tone: 'accent' as const };
    return null;
  })();

  return (
    <motion.li
      className="relative overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03] p-4"
      whileTap={{ scale: 0.98 }}
      data-testid={`world-country-${country.code}`}
    >
      <div className="flex items-center gap-3">
        <span className="text-2xl" aria-hidden>
          {country.flag}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-bold uppercase tracking-[0.12em] text-white">{name}</p>
          <p className="text-[11px] text-white/40">
            {country.discovered} / {country.total} · {percent}%
          </p>
        </div>
        {country.rarest ? (
          <span className="shrink-0 rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-white/60">
            {country.rarest.rarity}
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
            hook?.tone === 'accent' && 'text-sky-300',
            !hook && 'text-white/30',
          )}
        >
          {hook?.text ?? `${percent}%`}
        </span>
        <button
          type="button"
          onClick={onHunt}
          className="min-h-[32px] rounded-full border border-white/12 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-white/70 active:scale-95"
        >
          {t('world.hunt')}
        </button>
      </div>

      {country.rarest ? (
        <p className="mt-1 truncate text-[11px] text-white/35">
          {t('world.rarest')}: <span className="number-display text-white/60">{country.rarest.plate_text}</span>
        </p>
      ) : (
        <p className="mt-1 text-[11px] text-white/25">{t('world.nothingYet')}</p>
      )}
      <span className="sr-only">{formatCoins(country.discovered)}</span>
    </motion.li>
  );
}

export default WorldPage;