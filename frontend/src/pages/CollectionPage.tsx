import { useMemo, useState } from 'react';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@/lib/api';
import { formatCoins, rarityColor } from '@/lib/format';
import { countries as countriesApi, game } from '@/services/api';
import { useAuthStore } from '@/store/auth';
import { RARITY_ORDER } from '@/types';
import type { CollectibleKind, CountrySummary, Rarity } from '@/types';
import { ProgressBar } from '@/components/GameCard';
import { CollectibleDetails, DetailSheet } from '@/components/CollectibleDetails';
import { CollectionList } from '@/components/CollectionList';
import { EmptyState, ErrorState, SkeletonRow } from '@/components/States';
import { useI18n } from '@/i18n';

const SORTS = ['recent', 'value', 'rarest', 'name'] as const;

const KIND_TABS: Array<{ key: CollectibleKind | null; label: 'collection.kindAll' | 'collection.kindPlates' | 'collection.kindSim' }> = [
  { key: null, label: 'collection.kindAll' },
  { key: 'VEHICLE_PLATE', label: 'collection.kindPlates' },
  { key: 'SIM_CARD', label: 'collection.kindSim' },
];

const INPUT =
  'min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm outline-none placeholder:text-white/35 focus:border-accent/60';

export function CollectionPage() {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const profile = useAuthStore((state) => state.profile);
  const applyProfile = useAuthStore((state) => state.applyProfile);

  const [page, setPage] = useState(1);
  const [kind, setKind] = useState<CollectibleKind | null>(null);
  const [rarity, setRarity] = useState('ALL');
  const [sort, setSort] = useState('recent');
  const [search, setSearch] = useState('');
  const [term, setTerm] = useState('');
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
    queryKey: ['collection', page, kind, rarity, sort, term, activeCode],
    queryFn: () =>
      game.collection({ page, pageSize: 30, rarity, sort, search: term, kind: kind ?? undefined }),
    initialPageParam: page,
    getNextPageParam: (last) => (last.has_more ? last.page + 1 : undefined),
  });

  const sell = useMutation({
    mutationFn: ({ plateId, copies }: { plateId: number; copies: number }) => game.sell(plateId, copies),
    onSuccess: (result) => {
      if (profile) applyProfile({ ...profile, coins: result.balance });
      void queryClient.invalidateQueries({ queryKey: ['collection'] });
      void queryClient.invalidateQueries({ queryKey: ['garage'] });
      void queryClient.invalidateQueries({ queryKey: ['user'] });
      setExpanded(null);
    },
    onError: (error) => {
      if (error instanceof ApiError) window.alert(error.message);
    },
  });

  const sellAll = useMutation({
    mutationFn: () => game.sellDuplicates(),
    onSuccess: (result) => {
      if (profile) applyProfile({ ...profile, coins: result.balance });
      void queryClient.invalidateQueries({ queryKey: ['collection'] });
      void queryClient.invalidateQueries({ queryKey: ['garage'] });
      void queryClient.invalidateQueries({ queryKey: ['user'] });
    },
    onError: (error) => {
      if (error instanceof ApiError) window.alert(error.message);
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
          <button type="submit" className="btn-ghost !px-4" aria-label="Search">
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
        onSell={(item) => sell.mutate({ plateId: item.id, copies: Math.max(1, item.duplicate_count) })}
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

export default CollectionPage;