import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { EmptyState, ErrorState, LoadingSpinner } from '@/components/States';
import { useI18n } from '@/i18n';
import { compactCoins } from '@/lib/format';
import { leaderboard } from '@/services/api';
import { useRouteBackButton } from '@/lib/useRouteBackButton';

const PERIODS = ['daily', 'weekly', 'alltime'] as const;

const CATEGORIES = ['COLLECTION', 'COUNTRIES', 'FIRST_DISCOVERIES', 'RARITY', 'ROLLS'] as const;

export function RankingPage() {
  useRouteBackButton();
  const { t } = useI18n();
  const [period, setPeriod] = useState('daily');
  const [category, setCategory] = useState('COLLECTION');

  const board = useQuery({
    queryKey: ['leaderboard', category, period],
    queryFn: () => leaderboard.board(category, period, 25),
  });

  return (
    <div className="flex flex-col gap-4" data-testid="ranking-page">
      {/* The bottom-nav label already names the screen, so only the
          server-provided board caption is shown here. */}
      {board.data?.label ? <p className="t-caption text-white/45">{board.data.label}</p> : null}

      {/*
        Segmented controls rather than a grid of buttons. A 2x3 grid of small chips for
        five categories wasted half the width on every row and read as a form; a single
        segmented row reads as one choice.
      */}
      <div
        className="no-scrollbar flex gap-1 overflow-x-auto rounded-2xl border border-white/[0.06] bg-white/[0.025] p-1"
        role="tablist"
        aria-label={t('ranking.title')}
      >
        {PERIODS.map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={period === value}
            onClick={() => setPeriod(value)}
            className={`min-h-[40px] flex-1 shrink-0 rounded-xl px-3 text-[13px] font-semibold transition active:scale-[0.97] ${
              period === value
                ? 'bg-white/[0.1] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]'
                : 'text-white/45'
            }`}
          >
            {t(`ranking.period.${value}`)}
          </button>
        ))}
      </div>

      <div className="no-scrollbar flex gap-1 overflow-x-auto" role="tablist" aria-label={t('ranking.title')}>
        {CATEGORIES.map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={category === value}
            onClick={() => setCategory(value)}
            className={`min-h-[38px] shrink-0 rounded-full border px-3.5 text-[12px] font-medium transition active:scale-[0.97] ${
              category === value
                ? 'border-white/25 bg-white/[0.1] text-white'
                : 'border-white/[0.08] bg-white/[0.02] text-white/45'
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

      {/*
        A leaderboard is a table, not a stack of cards: rows share dividers so the eye can
        track a column of numbers down the screen without re-reading each line.
      */}
      <div className="overflow-hidden rounded-[18px] border border-white/[0.06] bg-white/[0.02]">
        {(board.data?.entries ?? []).map((entry, index) => {
          const isMe = board.data?.you === index + 1;
          const medal = ['🥇', '🥈', '🥉'][index];
          return (
            <div
              key={entry.user_id}
              className={`flex items-center gap-3 px-3 py-2.5 ${
                index > 0 ? 'border-t border-white/[0.05]' : ''
              } ${isMe ? 'bg-accent/[0.08]' : ''}`}
            >
              <span
                className={`grid h-6 w-6 shrink-0 place-items-center text-[13px] ${
                  index < 3 ? '' : 'number-display text-[13px] text-white/30'
                }`}
              >
                {medal ?? index + 1}
              </span>
              {entry.photo_url ? (
                <img src={entry.photo_url} alt="" className="h-8 w-8 shrink-0 rounded-full object-cover" />
              ) : (
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/[0.08] text-[11px] text-white/70">
                  {(entry.username ?? entry.display_name).charAt(0).toUpperCase()}
                </span>
              )}
              <span className="min-w-0 flex-1 truncate t-body text-white/85">
                {entry.username ? `@${entry.username}` : entry.display_name}
                {isMe ? (
                  <span className="ml-1.5 t-micro text-accent-soft">{t('common.you')}</span>
                ) : null}
              </span>
              <span className="number-display shrink-0 text-[13px] font-bold text-white/80">
                {compactCoins(entry.score)}
              </span>
            </div>
          );
        })}
      </div>

      {board.data?.you ? (
        /* A large number, not a card: the player's own position is the reason
           someone opens this screen at all. */
        <div className="flex items-end justify-center gap-3 px-1">
          <span className="number-display text-[2.5rem] leading-none text-brass">
            {board.data.you}
          </span>
          <span className="pb-1.5 t-caption text-white/45">
            {t('ranking.position', { place: '' }).trim()}
          </span>
        </div>
      ) : null}
    </div>
  );
}
