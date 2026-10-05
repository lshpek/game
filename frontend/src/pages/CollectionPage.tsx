import { useMemo, useState } from 'react';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { CollectibleDetails, DetailSheet } from '@/components/CollectibleDetails';
import { CollectionList } from '@/components/CollectionList';
import { ProgressBar } from '@/components/GameCard';
import { EmptyState, ErrorState, SkeletonRow } from '@/components/States';
import { useI18n } from '@/i18n';
import { ApiError, makeIdempotencyKey } from '@/lib/api';
import { formatCoins, rarityColor } from '@/lib/format';
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
  'min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm outline-none placeholder:text-white/35 focus:border-accent/60';

/**
 * The collection, as a garage.
 *
 * The hierarchy is COUNTRY → SET → PHYSICAL ITEM. The country comes from the server's
 * stored selection, the set is the completion progress for that country, and the items
 * are the physical objects themselves - each row leads with a real plate or a real SIM
 * card, big enough to recognise without reading.
 *
 * Filters cover everything a collector actually browses by: country, rarity, kind,
 * region, operator, duplicates, favourites, new finds and search. The list pages through
 * an infinite query, so a large collection never ships in one payload or one DOM.
 */
export function CollectionPage() {
  useRouteBackButton();
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const profile = useAuthStore((state) => state.profile);
  const applyProfile = useAuthStore((state) => state.applyProfile);
  const [saleError, setSaleError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
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

  // The collection follows the player's active country, which the server owns.
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

  /**
   * Sell duplicates.
   *
   * `copies` is the real duplicate count. The action is only rendered when that count is
   * greater than zero, and the mutation refuses anything else, so the client can never
   * construct the invalid `sell(..., max(1, 0))` request a single-copy find used to
   * send. The idempotency key makes a double tap safe.
   */
  const sell = useMutation({
    mutationFn: ({ plateId, copies }: { plateId: number; copies: number }) => {
      if (copies <= 0) throw new ApiError('NO_DUPLICATES', t('sell.noDuplicates'), 422);
      return game.sell(plateId, copies, makeIdempotencyKey('sell'));
    },
    onSuccess: (result) => {
      if (profile) applyProfile({ ...profile, coins: result.balance });
      setSaleError(null);
      void queryClient.invalidateQueries({ queryKey: ['collection'] });
      void queryClient.invalidateQueries({ queryKey: ['garage'] });
      void queryClient.invalidateQueries({ queryKey: ['user'] });
      setExpanded(null);
    },
    onError: (error) => {
      // A failed sale is always visible and actionable.
      setSaleError(
        error instanceof ApiError ? error.message : t('sell.failed'),
      );
    },
  });

  const sellAll = useMutation({
    mutationFn: () => game.sellDuplicates(makeIdempotencyKey('sell-all')),
    onSuccess: (result) => {
      if (profile) applyProfile({ ...profile, coins: result.balance });
      setSaleError(null);
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

  // Regions and operators come from the country card, so the filter row costs nothing
  // extra and a new country needs no frontend change.
  const regionOptions = useMemo(
    () => (activeQuery.data?.country as { regions?: Array<{ code: string }> } | undefined)?.regions ?? [],
    [activeQuery.data],
  );
  const providerOptions = activeQuery.data?.country?.sim?.providers ?? [];

  const resetFilters = () => {
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
      {/* Country context, always visible: the collection belongs to one world. */}
      <header className="flex items-center justify-between gap-3" data-testid="collection-country">
        <div className="flex min-w-0 items-center gap-2">
          <span aria-hidden className="text-2xl leading-none">
            {activeCountry?.flag ?? '\u{1F30D}'}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-black tracking-tight text-white">{countryLabel}</p>
            <p className="text-[9px] font-bold uppercase tracking-[0.2em] text-white/35">
              {activeCode ?? t('country.world')}
            </p>
          </div>
        </div>
        <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.18em] text-white/35">
          {t('collection.title')}
        </span>
      </header>

      {/* The set: how far into this country the player is. */}
      {activeQuery.data?.country?.completion ? (
        <div className="glass space-y-2 p-3">
          <div className="flex items-center justify-between text-[11px]">
            <span className="font-bold uppercase tracking-[0.16em] text-white/45">
              {t('collection.completionTitle')}
            </span>
            <span className="tabular-nums text-white/60">
              {activeQuery.data.country.completion.collected} /{' '}
              {activeQuery.data.country.completion.total}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
            {activeQuery.data.country.completion.sections.map((section) => (
              <button
                key={section.code}
                type="button"
                onClick={() => {
                  setPage(1);
                  setTerm('');
                }}
                className="rounded-lg border border-white/8 bg-white/[0.03] px-2 py-1.5 text-left"
              >
                <span className="block truncate text-[10px] uppercase tracking-[0.12em] text-white/40">
                  {lang === 'ru' ? section.name_ru : section.name_en}
                </span>
                <span
                  className={`number-display block text-xs ${section.completed ? 'text-emerald-300' : 'text-white/70'}`}
                >
                  {section.collected}/{section.total}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <p className="text-xs text-white/45">
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

      {saleError ? (
        <p
          role="alert"
          className="rounded-xl border border-rose-400/25 bg-rose-500/10 px-3 py-2 text-xs text-rose-200"
        >
          {saleError}
        </p>
      ) : null}

      {meta && meta.duplicates_count > 0 ? (
        <button
          type="button"
          className="btn-ghost w-full !text-sm"
          disabled={sellAll.isPending}
          onClick={() => sellAll.mutate()}
        >
          {t('collection.sellAll', {
            count: meta.duplicates_count,
            coins: formatCoins(meta.total_dealer_value),
          })}
        </button>
      ) : null}

      <div className="space-y-2">
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

        {/* Kind tabs: ALL / PLATES / SIM, exactly the two collectible kinds. */}
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
                  setKind(tab.key);
                  setPage(1);
                }}
                className={`min-h-[36px] flex-1 rounded-xl border px-2 text-[11px] font-bold uppercase tracking-[0.16em] transition ${
                  active
                    ? 'border-white/25 bg-white/[0.12] text-white'
                    : 'border-white/8 bg-white/[0.03] text-white/45'
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
                setRarity(code);
                setPage(1);
              }}
              className={`shrink-0 rounded-full border px-3 py-1.5 text-[11px] font-semibold uppercase ${
                rarity === code ? 'border-accent/70 bg-accent/25' : 'border-white/10 bg-white/5 text-white/55'
              }`}
              style={rarity === code && code !== 'ALL' ? { color: rarityColor(code as Rarity) } : undefined}
            >
              {code === 'ALL' ? t('common.all') : code}
            </button>
          ))}
        </div>

        {/* Regions, only when this country has them. */}
        {regionOptions.length ? (
          <div className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
            <FilterChip active={region === null} onClick={() => { setRegion(null); setPage(1); }}>
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

        {/* Operators, only for the SIM line. */}
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

        {/* Ownership toggles. */}
        <div className="flex flex-wrap gap-1.5">
          <FilterChip active={duplicatesOnly} onClick={() => { setDuplicatesOnly(!duplicatesOnly); setPage(1); }}>
            {t('collection.onlyDuplicates')}
          </FilterChip>
          <FilterChip active={favoritesOnly} onClick={() => { setFavoritesOnly(!favoritesOnly); setPage(1); }}>
            {t('collection.onlyFavorites')}
          </FilterChip>
          <FilterChip active={newOnly} onClick={() => { setNewOnly(!newOnly); setPage(1); }}>
            {t('collection.onlyNew')}
          </FilterChip>
          <FilterChip active={false} onClick={resetFilters}>
            {t('collection.resetFilters')}
          </FilterChip>
        </div>

        <div className="flex gap-1.5">
          {SORTS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setSort(option)}
              className={`flex-1 rounded-lg border px-2 py-1.5 text-[11px] capitalize ${
                sort === option
                  ? 'border-white/25 bg-white/10'
                  : 'border-white/10 bg-transparent text-white/45'
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
        <EmptyState icon="\u{1F4DA}" title={t('collection.empty')} hint={t('collection.emptyHint')} />
      ) : null}

      <CollectionList
        items={items}
        expanded={expanded}
        onToggle={setExpanded}
        onOpen={setDetail}
        selling={sell.isPending}
        onSell={(item) => sell.mutate({ plateId: item.id, copies: item.duplicate_count })}
      />

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
          <span className="text-xs text-white/50">
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
      onClick={onClick}
      aria-pressed={active}
      className={`shrink-0 rounded-full border px-3 py-1.5 text-[11px] font-semibold uppercase transition ${
        active
          ? 'border-white/30 bg-white/[0.12] text-white'
          : 'border-white/10 bg-white/5 text-white/50'
      }`}
      style={active && accent ? { color: accent, borderColor: `${accent}66` } : undefined}
    >
      {children}
    </button>
  );
}

export default CollectionPage;