import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { compactCoins } from '@/lib/format';
import { leaderboard } from '@/services/api';
import { GameCard } from '@/components/GameCard';
import { EmptyState, ErrorState, LoadingSpinner } from '@/components/States';

const PERIODS = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'alltime', label: 'All time' },
];

const CATEGORIES = [
  { value: 'VALUE', label: '💎 Value' },
  { value: 'RARITY', label: '✦ Rarest' },
  { value: 'COLLECTION', label: '📚 Collection' },
  { value: 'ROLLS', label: '🎲 Rolls' },
];

export function RankingPage() {
  const [period, setPeriod] = useState('daily');
  const [category, setCategory] = useState('VALUE');

  const board = useQuery({
    queryKey: ['leaderboard', category, period],
    queryFn: () => leaderboard.board(category, period, 25),
  });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="font-display text-2xl font-bold">Ranking</h1>
        <p className="text-xs text-white/45">{board.data?.label ?? ''}</p>
      </header>

      <div className="grid grid-cols-3 gap-1.5">
        {PERIODS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setPeriod(option.value)}
            className={`rounded-xl border px-2 py-2 text-xs font-semibold ${
              period === option.value
                ? 'border-accent/60 bg-accent/20'
                : 'border-white/10 bg-white/5 text-white/55'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        {CATEGORIES.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setCategory(option.value)}
            className={`rounded-xl border px-2 py-2 text-xs font-semibold ${
              category === option.value
                ? 'border-white/25 bg-white/10'
                : 'border-white/10 bg-white/5 text-white/55'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {board.isLoading ? <LoadingSpinner label="Loading ranking…" /> : null}
      {board.isError ? <ErrorState message="Could not load the ranking." onRetry={() => void board.refetch()} /> : null}

      {board.data && board.data.entries.length === 0 ? (
        <EmptyState icon="🏆" title="Nobody here yet" hint="Be the first to climb the board." />
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
                {isMe ? <span className="ml-1.5 text-[10px] text-accent-soft">YOU</span> : null}
              </span>
              <span className="text-sm font-semibold tabular-nums">{compactCoins(entry.score)}</span>
            </div>
          );
        })}
      </GameCard>

      {board.data?.you ? (
        <p className="text-center text-xs text-white/45">Your position: #{board.data.you}</p>
      ) : null}
    </div>
  );
}
