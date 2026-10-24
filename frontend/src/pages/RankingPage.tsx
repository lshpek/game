import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { EmptyState, ErrorState, LoadingSpinner } from '@/components/States';
import { useI18n } from '@/i18n';
import { compactCoins } from '@/lib/format';
import { playTap } from '@/lib/sound';
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

  const entries = board.data?.entries ?? [];
  const topThree = entries.slice(0, 3);

  return (
    <div className="flex flex-col gap-4" data-testid="ranking-page">
      {board.data?.label ? (
        <div className="flex items-center justify-between px-1">
          <span className="eyebrow">🏆 HALL OF FAME</span>
          <p className="t-caption font-medium text-white/60">{board.data.label}</p>
        </div>
      ) : null}

      {/* Period segmented selector */}
      <div
        className="no-scrollbar flex gap-1 overflow-x-auto rounded-2xl border border-white/[0.09] bg-white/[0.03] p-1"
        role="tablist"
        aria-label={t('ranking.title')}
      >
        {PERIODS.map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={period === value}
            onClick={() => {
              playTap();
              setPeriod(value);
            }}
            className={`min-h-[40px] flex-1 shrink-0 rounded-xl px-3 font-display text-[13px] font-bold transition active:scale-[0.97] ${
              period === value
                ? 'border border-brass/35 bg-gradient-to-b from-brass/25 to-white/[0.08] text-white shadow-hairline'
                : 'text-white/50 hover:text-white/80'
            }`}
          >
            {t(`ranking.period.${value}`)}
          </button>
        ))}
      </div>

      {/* Category pills */}
      <div
        className="no-scrollbar flex gap-1.5 overflow-x-auto"
        role="tablist"
        aria-label={t('ranking.title')}
      >
        {CATEGORIES.map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={category === value}
            onClick={() => {
              playTap();
              setCategory(value);
            }}
            className={`min-h-[38px] shrink-0 rounded-full border px-3.5 text-[12px] font-semibold transition active:scale-[0.97] ${
              category === value
                ? 'border-brass/45 bg-brass/15 text-brass-soft'
                : 'border-white/[0.08] bg-white/[0.025] text-white/50'
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

      {board.data && entries.length === 0 ? (
        <EmptyState icon="🏆" title={t('ranking.empty')} hint={t('ranking.emptyHint')} />
      ) : null}

      {/* Top-3 Champions Podium Showcase */}
      {topThree.length >= 3 ? (
        <div
          className="stage grid grid-cols-3 items-end gap-2 px-3 pb-3.5 pt-5"
          aria-hidden="true"
        >
          {[
            { item: topThree[1], rank: 2, medal: '🥈', height: 'h-24', accent: 'border-slate-300/30 bg-slate-300/10' },
            { item: topThree[0], rank: 1, medal: '👑 🥇', height: 'h-32', accent: 'border-amber-300/45 bg-amber-300/15 shadow-brass' },
            { item: topThree[2], rank: 3, medal: '🥉', height: 'h-20', accent: 'border-amber-600/35 bg-amber-600/10' },
          ].map(({ item, rank, medal, height, accent }) =>
            item ? (
              <div key={item.user_id} className="flex min-w-0 flex-col items-center gap-1.5">
                <span className="text-xs font-bold">{medal}</span>
                <span className="max-w-full truncate text-[11px] font-semibold text-white/85">
                  {item.username ? `@${item.username}` : item.display_name}
                </span>
                <div
                  className={`flex w-full flex-col items-center justify-center rounded-t-2xl border-x border-t px-1.5 ${height} ${accent}`}
                >
                  <span className="font-display text-lg font-black text-white">#{rank}</span>
                  <span className="number-display text-[12px] font-bold text-brass-soft">
                    {compactCoins(item.score)}
                  </span>
                </div>
              </div>
            ) : null,
          )}
        </div>
      ) : null}

      {/* Full Leaderboard Table */}
      <div className="glass overflow-hidden">
        {entries.map((entry, index) => {
          const isMe = board.data?.you === index + 1;
          const medal = ['🥇', '🥈', '🥉'][index];
          return (
            <div
              key={entry.user_id}
              className={`flex items-center gap-3 px-3.5 py-3 transition-colors ${
                index > 0 ? 'border-t border-white/[0.06]' : ''
              } ${isMe ? 'bg-brass/[0.12]' : 'hover:bg-white/[0.02]'}`}
            >
              <span
                className={`grid h-7 w-7 shrink-0 place-items-center rounded-lg text-[13px] font-bold ${
                  index < 3
                    ? 'bg-white/[0.06]'
                    : 'number-display text-[13px] text-white/40'
                }`}
              >
                {medal ?? index + 1}
              </span>
              {entry.photo_url ? (
                <img
                  src={entry.photo_url}
                  alt=""
                  className="h-9 w-9 shrink-0 rounded-full object-cover ring-1 ring-white/15"
                />
              ) : (
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.08] font-display text-[12px] font-bold text-white/80">
                  {(entry.username ?? entry.display_name).charAt(0).toUpperCase()}
                </span>
              )}
              <span className="min-w-0 flex-1 truncate t-body font-medium text-white/90">
                {entry.username ? `@${entry.username}` : entry.display_name}
                {isMe ? (
                  <span className="ml-1.5 rounded bg-brass/20 px-1.5 py-0.5 t-micro text-brass-soft">
                    {t('common.you')}
                  </span>
                ) : null}
              </span>
              <span className="number-display shrink-0 text-[14px] font-bold text-brass-soft">
                {compactCoins(entry.score)}
              </span>
            </div>
          );
        })}
      </div>

      {board.data?.you ? (
        <div className="stage flex items-center justify-between px-4 py-3">
          <span className="t-caption font-semibold text-white/65">
            {t('ranking.position', { place: '' }).trim()}
          </span>
          <span className="number-display text-[2rem] font-black leading-none text-brass-soft">
            #{board.data.you}
          </span>
        </div>
      ) : null}
    </div>
  );
}

export default RankingPage;
