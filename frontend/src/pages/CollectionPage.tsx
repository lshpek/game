import { useMemo, useState } from 'react';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { CollectibleDetails, DetailSheet } from '@/components/CollectibleDetails';
import { CollectionGrid, CollectionList } from '@/components/CollectionList';
import { ProgressBar } from '@/components/GameCard';
import { EmptyState, ErrorState, SkeletonRow } from '@/components/States';
import { useI18n } from '@/i18n';
import { ApiError, makeIdempotencyKey } from '@/lib/api';
import { formatCoins, rarityColor } from '@/lib/format';
import { playCoinJingle, playTap } from '@/lib/sound';
import { useRouteBackButton } from '@/lib/useRouteBackButton';
import { countries as countriesApi, game } from '@/services/api';
import { useAuthStore } from '@/store/auth';
import { RARITY_ORDER } from '@/types';
import type { CollectibleKind, CountrySummary, Rarity } from '@/types';

const SORTS = ['recent', 'value', 'rarest', 'name'] as const;

const KIND_TABS: Array<{
  key: CollectibleKind | null;
  label: 'collection.kindAll' | 'collection.kindPlates' | 'collection.kindSim';
}> = [
  { key: null, label: 'collection.kindAll' },
  { key: 'VEHICLE_PLATE', label: 'collection.kindPlates' },
  { key: 'SIM_CARD', label: 'collection.kindSim' },
];

const INPUT =
  'min-w-0 flex-1 rounded-xl border border-white/12 bg-white/[0.05] px-3.5 py-2.5 text-sm text-white outline-none placeholder:text-white/35 focus:border-brass/60';

export function CollectionPage() {
  useRouteBackButton();
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const profile = useAuthStore((state) => state.profile);
  const applyProfile = useAuthStore((state) => state.applyProfile);
  const [saleError, setSaleError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const [kind, setKind] = useState<CollectibleKind | null>(null);
  const [rarity, setRarity] = useState('ALL');
  const [sort, setSort] = useState('recent');
  const [search, setSearch] = useState('');
  const [term, setTerm] = useState('');
  const [region, setRegion] = useState<string | null>(null);
  const [provider, setProvider] = useState<string | null>(null);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [duplicatesOnly, setDuplicatesOnly] = useState(false);
  const [newOnly, setNewOnly] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [detail, setDetail] = useState<number | null>(null);

  const activeQuery = useQuery({
    queryKey: ['countries', 'active'],
    queryFn: countriesApi.active,
    staleTime: 60_000,
  });
  const activeCode = activeQuery.data?.code ?? null;
  const activeCountry: CountrySummary | null = activeQuery.data?.country ?? null;

  const query = useInfiniteQuery({
    queryKey: [
      'collection',
      page,
      kind,
      rarity,
      sort,
      term,
      activeCode,
      region,
      provider,
      favoritesOnly,
      duplicatesOnly,
      newOnly,
    ],
    queryFn: () =>
      game.collection({
        page,
        pageSize: 30,
        rarity,
        sort,
        search: term,
        kind: kind ?? undefined,
        region: region ?? undefined,
        provider: provider ?? undefined,
        favoritesOnly,
        duplicatesOnly,
        newOnly,
      }),
    initialPageParam: page,
    getNextPageParam: (last) => (last.has_more ? last.page + 1 : undefined),
  });

  const sell = useMutation({
    mutationFn: ({ plateId, copies }: { plateId: number; copies: number }) => {
      if (copies <= 0) throw new ApiError('NO_DUPLICATES', t('sell.noDuplicates'), 422);
      return game.sell(plateId, copies, makeIdempotencyKey('sell'));
    },
    onSuccess: (result) => {
      if (profile) applyProfile({ ...profile, coins: result.balance });
      setSaleError(null);
      playCoinJingle();
      void queryClient.invalidateQueries({ queryKey: ['collection'] });
      void queryClient.invalidateQueries({ queryKey: ['garage'] });
      void queryClient.invalidateQueries({ queryKey: ['user'] });
      setExpanded(null);
    },
    onError: (error) => {
      setSaleError(error instanceof ApiError ? error.message : t('sell.failed'));
    },
  });

  const sellAll = useMutation({
    mutationFn: () => game.sellDuplicates(makeIdempotencyKey('sell-all')),
    onSuccess: (result) => {
      if (profile) applyProfile({ ...profile, coins: result.balance });
      setSaleError(null);
      playCoinJingle();
      void queryClient.invalidateQueries({ queryKey: ['collection'] });
      void queryClient.invalidateQueries({ queryKey: ['garage'] });
      void queryClient.invalidateQueries({ queryKey: ['user'] });
    },
    onError: (error) => {
      setSaleError(error instanceof ApiError ? error.message : t('sell.failed'));
    },
  });

  const meta = query.data?.pages[0];
  const items = useMemo(() => query.data?.pages.flatMap((entry) => entry.items) ?? [], [query.data]);
  const detailCard = useMemo(() => items.find((item) => item.id === detail) ?? null, [detail, items]);
  const countryLabel = activeCountry
    ? lang === 'ru'
      ? activeCountry.name_ru
      : activeCountry.name_en
    : t('country.all');

  const regionOptions = useMemo(
    () => (activeQuery.data?.country as { regions?: Array<{ code: string }> } | undefined)?.regions ?? [],
    [activeQuery.data],
  );
  const providerOptions = activeQuery.data?.country?.sim?.providers ?? [];

  const resetFilters = () => {
    playTap();
    setRarity('ALL');
    setKind(null);
    setRegion(null);
    setProvider(null);
    setFavoritesOnly(false);
    setDuplicatesOnly(false);
    setNewOnly(false);
    setPage(1);
  };

  return (
    <div className="space-y-4">
      {/* Garage Showroom Header with View Mode Switcher */}
      <header
        className="stage flex items-center justify-between gap-3 px-4 py-3.5"
        data-testid="collection-country"
      >
        <div className="flex min-w-0 items-center gap-3">
          <span aria-hidden className="text-3xl leading-none">
            {activeCountry?.flag ?? '🌍'}
          </span>
          <div className="min-w-0">
            <span className="eyebrow block">{t('collection.title')}</span>
            <p className="truncate font-display text-base font-bold tracking-tight text-white">
              {countryLabel}
            </p>
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-white/45">
              {activeCode ?? t('country.world')}
            </p>
          </div>
        </div>

        {/* Shelf List vs Showroom Wall Grid Switcher */}
        <div className="flex shrink-0 items-center gap-1 rounded-xl border border-white/10 bg-black/30 p-1">
          <button
            type="button"
            onClick={() => {
              playTap();
              setViewMode('list');
            }}
            aria-pressed={viewMode === 'list'}
            className={`grid h-8 w-8 place-items-center rounded-lg text-xs font-bold transition ${
              viewMode === 'list' ? 'bg-white/15 text-brass-soft' : 'text-white/45 hover:text-white'
            }`}
            title="List view"
          >
            ☰
          </button>
          <button
            type="button"
            onClick={() => {
              playTap();
              setViewMode('grid');
            }}
            aria-pressed={viewMode === 'grid'}
            className={`grid h-8 w-8 place-items-center rounded-lg text-xs font-bold transition ${
              viewMode === 'grid' ? 'bg-white/15 text-brass-soft' : 'text-white/45 hover:text-white'
            }`}
            title="Wall grid view"
          >
            ⊞
          </button>
        </div>
      </header>

      {/* Country Completion Matrix */}
      {activeQuery.data?.country?.completion ? (
        <div className="glass space-y-2.5 p-3.5">
          <div className="flex items-center justify-between">
            <span className="eyebrow">{t('collection.completionTitle')}</span>
            <span className="number-display text-[13px] font-bold text-brass-soft">
              {activeQuery.data.country.completion.collected}
              <span className="text-white/30">/{activeQuery.data.country.completion.total}</span>
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {activeQuery.data.country.completion.sections.map((section) => (
              <button
                key={section.code}
                type="button"
                onClick={() => {
                  setPage(1);
                  setTerm('');
                }}
                className="stat !items-start !px-3 text-left transition hover:border-white/15"
              >
                <span className="w-full truncate t-micro text-white/50">
                  {lang === 'ru' ? section.name_ru : section.name_en}
                </span>
                <span
                  className={`number-display text-[14px] font-bold ${
                    section.completed ? 'text-emerald-300' : 'text-white/85'
                  }`}
                >
                  {section.collected}
                  <span className="text-white/30">/{section.total}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="glass space-y-2 p-3.5">
        <p className="t-caption font-medium text-white/65">
          {meta
            ? t('collection.count', {
                count: meta.total,
                total: meta.target.toLocaleString(),
              })
            : t('common.loading')}
        </p>

        <ProgressBar
          value={profile?.plates_count ?? 0}
          max={profile?.collection_target ?? meta?.target ?? 1}
          label={t('collection.progress')}
          trailing={`${((meta?.progress ?? 0) * 100).toFixed(2)}%`}
        />
      </div>

      {saleError ? (
        <p
          role="alert"
          className="rounded-xl border border-rose-400/30 bg-rose-500/15 px-3.5 py-2.5 t-caption text-rose-200"
        >
          {saleError}
        </p>
      ) : null}

      {/* NUMORA Dealer Buyback Desk */}
      {meta && meta.duplicates_count > 0 ? (
        <button
          type="button"
          className="btn-primary w-full !text-sm"
          disabled={sellAll.isPending}
          onClick={() => sellAll.mutate()}
        >
          <span>🪙</span>
          <span>
            {t('collection.sellAll', {
              count: meta.duplicates_count,
              coins: formatCoins(meta.total_dealer_value),
            })}
          </span>
        </button>
      ) : null}

      <div className="flex flex-col gap-2.5">
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setTerm(search.trim());
          }}
        >
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t('collection.search')}
            aria-label={t('collection.searchAria')}
            className={INPUT}
          />
          <button type="submit" className="btn-ghost !px-4" aria-label={t('collection.searchAria')}>
            🔍
          </button>
        </form>

        <div className="flex gap-1.5" role="tablist" aria-label={t('category.aria')}>
          {KIND_TABS.map((tab) => {
            const active = kind === tab.key;
            return (
              <button
                key={tab.label}
                type="button"
                role="tab"
                aria-selected={active}
                data-testid={`collection-kind-${tab.key ?? 'ALL'}`}
                onClick={() => {
                  playTap();
                  setKind(tab.key);
                  setPage(1);
                }}
                className={`min-h-[42px] flex-1 rounded-xl border px-2 t-caption font-semibold transition ${
                  active
                    ? 'border-brass/40 bg-brass/15 text-white'
                    : 'border-white/[0.08] bg-white/[0.03] text-white/50'
                }`}
              >
                {t(tab.label)}
              </button>
            );
          })}
        </div>

        <div className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
          {['ALL', ...RARITY_ORDER].map((code) => (
            <button
              key={code}
              type="button"
              onClick={() => {
                playTap();
                setRarity(code);
                setPage(1);
              }}
              className={`flex min-h-[38px] shrink-0 items-center gap-1.5 rounded-full border px-3.5 t-micro transition active:scale-[0.97] ${
                rarity === code
                  ? 'border-white/30 bg-white/[0.14] text-white'
                  : 'border-white/[0.08] bg-white/[0.025] text-white/50'
              }`}
              style={
                rarity === code && code !== 'ALL' ? { color: rarityColor(code as Rarity) } : undefined
              }
            >
              {code !== 'ALL' ? (
                <span
                  aria-hidden
                  className="inline-block h-1.5 w-1.5 rounded-full"
                  style={{ background: rarityColor(code as Rarity) }}
                />
              ) : null}
              {code === 'ALL' ? t('common.all') : code}
            </button>
          ))}
        </div>

        {regionOptions.length ? (
          <div className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
            <FilterChip
              active={region === null}
              onClick={() => {
                setRegion(null);
                setPage(1);
              }}
            >
              {t('common.all')}
            </FilterChip>
            {regionOptions.map((option) => (
              <FilterChip
                key={option.code}
                active={region === option.code}
                onClick={() => {
                  setRegion(region === option.code ? null : option.code);
                  setPage(1);
                }}
              >
                {option.code}
              </FilterChip>
            ))}
          </div>
        ) : null}

        {providerOptions.length ? (
          <div className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
            <FilterChip
              active={provider === null}
              onClick={() => {
                setProvider(null);
                setPage(1);
              }}
            >
              {t('collection.allOperators')}
            </FilterChip>
            {providerOptions.map((option) => (
              <FilterChip
                key={option.code}
                active={provider === option.code}
                accent={option.accent}
                onClick={() => {
                  setProvider(provider === option.code ? null : option.code);
                  setKind('SIM_CARD');
                  setPage(1);
                }}
              >
                {option.brand}
              </FilterChip>
            ))}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-1.5">
          <FilterChip
            active={duplicatesOnly}
            onClick={() => {
              setDuplicatesOnly(!duplicatesOnly);
              setPage(1);
            }}
          >
            {t('collection.onlyDuplicates')}
          </FilterChip>
          <FilterChip
            active={favoritesOnly}
            onClick={() => {
              setFavoritesOnly(!favoritesOnly);
              setPage(1);
            }}
          >
            {t('collection.onlyFavorites')}
          </FilterChip>
          <FilterChip
            active={newOnly}
            onClick={() => {
              setNewOnly(!newOnly);
              setPage(1);
            }}
          >
            {t('collection.onlyNew')}
          </FilterChip>
          <FilterChip active={false} onClick={resetFilters}>
            {t('collection.resetFilters')}
          </FilterChip>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {SORTS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => {
                playTap();
                setSort(option);
              }}
              aria-pressed={sort === option}
              className={`min-h-[38px] flex-1 rounded-xl border px-2.5 t-caption capitalize transition active:scale-[0.97] ${
                sort === option
                  ? 'border-brass/40 bg-brass/15 text-white'
                  : 'border-white/[0.08] bg-white/[0.025] text-white/50'
              }`}
            >
              {t(`collection.sort.${option}`)}
            </button>
          ))}
        </div>
      </div>

      {query.isLoading ? (
        <div className="space-y-2">
          <SkeletonRow />
          <SkeletonRow />
        </div>
      ) : null}

      {query.isError ? (
        <ErrorState message={t('collection.error')} onRetry={() => void query.refetch()} />
      ) : null}

      {!query.isLoading && items.length === 0 ? (
        <EmptyState icon="📚" title={t('collection.empty')} hint={t('collection.emptyHint')} />
      ) : null}

      {viewMode === 'grid' ? (
        <CollectionGrid items={items} onOpen={setDetail} />
      ) : (
        <CollectionList
          items={items}
          expanded={expanded}
          onToggle={setExpanded}
          onOpen={setDetail}
          selling={sell.isPending}
          onSell={(item) => sell.mutate({ plateId: item.id, copies: item.duplicate_count })}
        />
      )}

      {query.data && query.data.pages.length > 1 ? (
        <div className="flex items-center justify-center gap-2 py-3">
          <button
            type="button"
            className="btn-ghost !min-h-[42px] !px-4"
            disabled={page <= 1}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            ←
          </button>
          <span className="font-mono text-xs text-white/60">
            {t('common.page')} {page}
          </span>
          <button
            type="button"
            className="btn-ghost !min-h-[42px] !px-4"
            disabled={!query.hasNextPage}
            onClick={() => setPage((current) => current + 1)}
          >
            →
          </button>
        </div>
      ) : null}

      <DetailSheet open={Boolean(detailCard)} onClose={() => setDetail(null)}>
        {detailCard ? <CollectibleDetails collectible={detailCard} /> : null}
      </DetailSheet>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  accent,
  children,
}: {
  active: boolean;
  onClick: () => void;
  accent?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={() => {
        playTap();
        onClick();
      }}
      aria-pressed={active}
      className={`flex min-h-[38px] shrink-0 items-center rounded-full border px-3.5 t-micro transition active:scale-[0.97] ${
        active
          ? 'border-white/30 bg-white/[0.14] text-white'
          : 'border-white/[0.08] bg-white/[0.025] text-white/50'
      }`}
      style={active && accent ? { color: accent, borderColor: `${accent}66` } : undefined}
    >
      {children}
    </button>
  );
}

export default CollectionPage;