import { useState } from 'react';
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@/lib/api';
import { rarityColor } from '@/lib/format';
import { game } from '@/services/api';
import { useAuthStore } from '@/store/auth';
import { RARITY_ORDER } from '@/types';
import type { Rarity } from '@/types';
import { ProgressBar } from '@/components/GameCard';
import { CollectionList } from '@/components/CollectionList';
import { EmptyState, ErrorState, SkeletonRow } from '@/components/States';
import { useI18n } from '@/i18n';

const SORTS = ['recent', 'value', 'number', 'duplicates'] as const;
const INPUT =
  'min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm outline-none placeholder:text-white/35 focus:border-accent/60';

export function CollectionPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const profile = useAuthStore((state) => state.profile);
  const applyProfile = useAuthStore((state) => state.applyProfile);

  const [page, setPage] = useState(1);
  const [rarity, setRarity] = useState('ALL');
  const [sort, setSort] = useState('recent');
  const [search, setSearch] = useState('');
  const [term, setTerm] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);

  const query = useInfiniteQuery({
    queryKey: ['collection', page, rarity, sort, term],
    queryFn: () => game.collection({ page, pageSize: 30, rarity, sort, search: term }),
    initialPageParam: page,
    getNextPageParam: (last) => (last.has_more ? last.page + 1 : undefined),
  });

  const convert = useMutation({
    mutationFn: (value: string) => game.convertDuplicate(value),
    onSuccess: (result) => {
      if (profile) applyProfile({ ...profile, coins: result.balance });
      void queryClient.invalidateQueries({ queryKey: ['collection'] });
      void queryClient.invalidateQueries({ queryKey: ['user'] });
    },
    onError: (error) => {
      if (error instanceof ApiError) window.alert(error.message);
    },
  });

  const meta = query.data?.pages[0];
  const items = query.data?.pages.flatMap((entry) => entry.items) ?? [];

  return (
    <div className="space-y-4">
      <p className="text-xs text-white/45">
        {meta
          ? t('collection.count', {
              count: meta.total,
              total: meta.target.toLocaleString(),
            })
          : t('common.loading')}
      </p>

      <ProgressBar
        value={profile?.unique_numbers ?? 0}
        max={profile?.collection_target ?? 10_000}
        label={t('collection.progress')}
        trailing={`${((meta?.progress ?? 0) * 100).toFixed(2)}%`}
      />

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
        <EmptyState icon="📚" title={t('collection.empty')} hint={t('collection.emptyHint')} />
      ) : null}

      <CollectionList
        items={items}
        expanded={expanded}
        onToggle={setExpanded}
        converting={convert.isPending}
        onConvert={(value) => convert.mutate(value)}
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
    </div>
  );
}
