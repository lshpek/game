import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { compactCoins } from '@/lib/format';
import { leaderboard } from '@/services/api';
import { GameCard } from '@/components/GameCard';
import { EmptyState, ErrorState, LoadingSpinner } from '@/components/States';
import { useI18n } from '@/i18n';

const PERIODS = ['daily', 'weekly', 'alltime'] as const;

const CATEGORIES = ['COLLECTION', 'COUNTRIES', 'FIRST_DISCOVERIES', 'RARITY', 'ROLLS'] as const;

export function RankingPage() {
  const { t } = useI18n();
  const [period, setPeriod] = useState('daily');
  const [category, setCategory] = useState('COLLECTION');

  const board = useQuery({
    queryKey: ['leaderboard', category, period],
    queryFn: () => leaderboard.board(category, period, 25),
  });

  return (
    <div className="space-y-4">
      {/* The bottom-nav label already names the screen, so only the
          server-provided board caption is shown here. */}
      {board.data?.label ? (
        <p className="text-xs text-white/45">{board.data.label}</p>
      ) : null}

      <div className="grid grid-cols-3 gap-1.5">
        {PERIODS.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setPeriod(value)}
            className={`rounded-xl border px-2 py-2 text-xs font-semibold ${
              period === value
                ? 'border-accent/60 bg-accent/20'
                : 'border-white/10 bg-white/5 text-white/55'
            }`}
          >
            {t(`ranking.period.${value}`)}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        {CATEGORIES.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setCategory(value)}
            className={`rounded-xl border px-2 py-2 text-xs font-semibold ${
              category === value
                ? 'border-white/25 bg-white/10'
                : 'border-white/10 bg-white/5 text-white/55'
            }`}
          >
            {t(`ranking.cat.${value}`)}
          </button>
        ))}
      </div>

      {board.isLoading ? <LoadingSpinner label={t('ranking.loading')} /> : null}
      {board.isError ? (
        <ErrorState message={t('ranking.error')} onRetry={() => void board.refetch()} />
      ) : null}

      {board.data && board.data.entries.length === 0 ? (
        <EmptyState
          icon="🏆"
          title={t('ranking.empty')}
          hint={t('ranking.emptyHint')}
        />
      ) : null}

      <GameCard className="divide-y divide-white/5 !p-2">
        {(board.data?.entries ?? []).map((entry, index) => {
          const isMe = board.data?.you === index + 1;
          return (
            <div
              key={entry.user_id}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 ${isMe ? 'bg-accent/15' : ''}`}
            >
              <span
                className={`w-6 text-center text-sm font-bold ${
                  index < 3 ? 'text-amber-300' : 'text-white/35'
                }`}
              >
                {index + 1}
              </span>
              {entry.photo_url ? (
                <img src={entry.photo_url} alt="" className="h-8 w-8 rounded-full object-cover" />
              ) : (
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-xs">
                  {(entry.username ?? entry.display_name).charAt(0).toUpperCase()}
                </span>
              )}
              <span className="min-w-0 flex-1 truncate text-sm">
                {entry.username ? `@${entry.username}` : entry.display_name}
                {isMe ? (
                  <span className="ml-1.5 text-[10px] text-accent-soft">{t('common.you')}</span>
                ) : null}
              </span>
              <span className="text-sm font-semibold tabular-nums">{compactCoins(entry.score)}</span>
            </div>
          );
        })}
      </GameCard>

      {board.data?.you ? (
        <p className="text-center text-xs text-white/45">
          {t('ranking.position', { place: board.data.you })}
        </p>
      ) : null}
    </div>
  );
}
