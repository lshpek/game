import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError } from '@/lib/api';
import { playCoinJingle } from '@/lib/sound';
import { haptic } from '@/lib/telegram';
import { formatCoins, formatRelativeTime, rarityLabel } from '@/lib/format';
import { game } from '@/services/api';
import { useAuthStore } from '@/store/auth';
import { GameCard, ProgressBar, Section } from '@/components/GameCard';
import { RollBalanceLine } from '@/components/RollEconomy';
import { SocialPanel } from '@/components/SocialPanel';
import { ErrorState, LoadingSpinner } from '@/components/States';
import { useI18n } from '@/i18n';
import { useRouteBackButton } from '@/lib/useRouteBackButton';
import type { DailyStatus, RollBalance } from '@/types';

function rollBalanceFrom(status: DailyStatus | undefined): RollBalance | null {
  if (!status) return null;
  return {
    rolls_remaining: status.rolls_remaining,
    normal_rolls: status.normal_rolls,
    bonus_rolls: status.bonus_rolls,
    daily_allowance: status.daily_allowance,
    bank_cap: status.daily_allowance,
    resets_at: status.resets_at,
    next_roll_at: status.next_roll_at,
    seconds_to_next_roll: status.seconds_to_next_roll,
    regen_minutes: status.regen_minutes,
  };
}

export function ProfilePage() {
  useRouteBackButton();
  const { lang, t } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const profile = useAuthStore((state) => state.profile);
  const startContext = useAuthStore((state) => state.startContext);
  const refreshProfile = useAuthStore((state) => state.refreshProfile);
  const applyProfile = useAuthStore((state) => state.applyProfile);
  const [claimError, setClaimError] = useState<string | null>(null);

  const daily = useQuery({ queryKey: ['daily'], queryFn: game.daily });
  const achievements = useQuery({ queryKey: ['achievements'], queryFn: game.achievements });
  const seasons = useQuery({ queryKey: ['seasons'], queryFn: game.seasons });

  const claim = useMutation({
    mutationFn: game.claimDaily,
    onSuccess: async (result) => {
      setClaimError(null);
      if (profile) applyProfile({ ...profile, coins: result.balance });
      playCoinJingle();
      for (const key of ['daily', 'achievements', 'user', 'referrals']) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      await refreshProfile();
      haptic();
    },
    onError: (error) => {
      setClaimError(error instanceof ApiError ? error.message : t('common.tryAgain'));
    },
  });

  if (!profile) {
    return <ErrorState message={t('app.profileUnavailable')} onRetry={() => void refreshProfile()} />;
  }

  const unlocked = achievements.data?.filter((item) => item.unlocked).length ?? 0;
  const activeSeason = seasons.data?.find((item) => item.is_active);

  return (
    <div className="space-y-5">
      {/* Collector Vault Identity Banner */}
      <header className="stage flex items-center gap-3.5 p-4">
        {profile.photo_url ? (
          <img
            src={profile.photo_url}
            alt=""
            className="h-16 w-16 shrink-0 rounded-2xl object-cover ring-2 ring-brass/45 shadow-brass"
          />
        ) : (
          <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl border border-brass/40 bg-gradient-to-br from-brass/25 to-ink-900 font-display text-[22px] font-black text-brass-soft shadow-brass">
            {profile.display_name.charAt(0).toUpperCase()}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h1 className="truncate t-h1 text-white">
              {profile.username ? `@${profile.username}` : profile.display_name}
            </h1>
          </div>
          <p className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="rounded-md border border-brass/35 bg-brass/15 px-2 py-0.5 font-display text-[10px] font-bold tracking-[0.06em] text-brass-soft">
              LVL {profile.collector_level?.level ?? 1}
            </span>
            {profile.premium ? (
              <span className="rounded-md border border-amber-300/40 bg-amber-300/15 px-2 py-0.5 text-[9.5px] font-bold tracking-[0.06em] text-amber-200">
                ★ PRO
              </span>
            ) : null}
            {profile.is_admin ? (
              <span className="rounded-md border border-white/20 bg-white/[0.08] px-2 py-0.5 text-[9.5px] font-bold tracking-[0.06em] text-white/75">
                ADMIN
              </span>
            ) : null}
            <span className="text-[11px] text-white/45">
              {t('profile.joined', { when: formatRelativeTime(profile.created_at, t) })}
            </span>
          </p>
        </div>
      </header>

      {/* Six tactile stat cells */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { value: formatCoins(profile.coins), label: t('common.coins'), tone: 'text-brass-soft' },
          { value: profile.total_rolls, label: t('common.rolls'), tone: 'text-white' },
          { value: profile.plates_count, label: t('common.plates'), tone: 'text-white' },
          { value: profile.countries_count, label: t('common.countries'), tone: 'text-white' },
          { value: profile.first_discoveries_count, label: t('common.discoveries'), tone: 'text-amber-200' },
          { value: `🔥 ${profile.current_streak}`, label: t('common.streak'), tone: 'text-amber-300' },
        ].map((stat) => (
          <div key={stat.label} className="stat">
            <span className={`number-display text-[19px] font-bold ${stat.tone}`}>{stat.value}</span>
            <span className="t-micro truncate text-white/45">{stat.label}</span>
          </div>
        ))}
      </div>

      {/* Collector Rank & XP Progress */}
      <GameCard className="space-y-2.5">
        <div className="flex items-baseline justify-between gap-2">
          <span className="t-body font-semibold text-white/75">
            {t('profile.level', { level: profile.collector_level?.level ?? 1 })}
          </span>
          <span className="t-caption font-bold text-brass-soft">
            {lang === 'ru' ? profile.collector_level?.title_ru : profile.collector_level?.title_en}
          </span>
        </div>
        <ProgressBar
          value={profile.collector_level?.xp_into_level ?? 0}
          max={profile.collector_level?.xp_for_level ?? 1}
          label={`${profile.collector_level?.xp_into_level ?? 0} / ${profile.collector_level?.xp_for_level ?? 0} XP`}
        />
        {profile.best_plate_text ? (
          <p className="t-caption text-white/55">
            {t('profile.bestPlate')}{' '}
            <span className="number-display rounded border border-brass/30 bg-brass/10 px-1.5 py-0.5 font-bold text-brass-soft">
              {profile.best_plate_text}
            </span>
          </p>
        ) : null}
      </GameCard>

      <GameCard>
        <ProgressBar
          value={profile.plates_count}
          max={profile.collection_target}
          label={t('profile.rarestFind', { rarity: rarityLabel(profile.best_rarity, lang) })}
          trailing={`${formatCoins(profile.best_collector_value)} 🪙`}
        />
      </GameCard>

      {claimError ? (
        <p
          role="alert"
          className="rounded-xl border border-rose-400/30 bg-rose-500/15 px-3.5 py-2.5 t-caption text-rose-200"
        >
          {claimError}
        </p>
      ) : null}

      {/* Daily Streak Vault */}
      {daily.data?.can_claim ? (
        <GameCard accent="#fbbf24" className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="font-display text-sm font-bold text-amber-200">
              🎁 {t('profile.dailyReward')}
            </p>
            <p className="number-display text-sm font-bold text-amber-200">
              +{formatCoins(daily.data.claim_reward_coins)} 🪙
            </p>
          </div>
          <button
            type="button"
            className="btn-primary w-full"
            disabled={claim.isPending}
            onClick={() => claim.mutate()}
          >
            {t('profile.claimStreak', { days: daily.data.streak })}
          </button>
        </GameCard>
      ) : (
        <GameCard className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-white/60">{t('profile.rollsRemaining')}</span>
            <span className="number-display font-bold text-white">
              ⚡ {daily.data?.rolls_remaining ?? 0}
            </span>
          </div>
          <RollBalanceLine rolls={rollBalanceFrom(daily.data)} compact />
        </GameCard>
      )}

      {/* Legacy 4-Digit Boxes Vault */}
      <button
        type="button"
        className="glass-interactive flex w-full items-center gap-3.5 px-4 py-3.5 text-left"
        onClick={() => navigate('/legacy')}
      >
        <span aria-hidden className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-[20px] leading-none">
          {t('boxes.icon')}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block t-body font-bold text-white">{t('boxes.title')}</span>
          <span className="block t-micro text-white/45">{t('boxes.subtitle')}</span>
        </span>
        <span aria-hidden className="shrink-0 text-[15px] text-brass-soft">
          ›
        </span>
      </button>

      <SocialPanel />

      {/* Collector Medals & Achievements */}
      <Section
        title={t('profile.achievements', {
          unlocked,
          total: achievements.data?.length ?? 0,
        })}
      >
        {achievements.isLoading ? <LoadingSpinner /> : null}
        <GameCard className="divide-y divide-white/[0.06] !p-2">
          {(achievements.data ?? []).map((item) => (
            <div key={item.code} className="flex items-center gap-3 px-2.5 py-2.5">
              <span
                className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl border text-base ${
                  item.unlocked
                    ? 'border-amber-300/35 bg-amber-300/15 shadow-brass'
                    : 'border-white/10 bg-white/[0.03] opacity-50'
                }`}
                aria-hidden
              >
                {item.unlocked ? '🏅' : '🔒'}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-white/90">
                  {item.name}
                </span>
                <span className="block truncate text-[11px] text-white/50">
                  {item.description}
                </span>
              </span>
              <span className="font-mono text-[11px] font-bold tabular-nums text-brass-soft">
                {item.progress}/{item.threshold}
              </span>
            </div>
          ))}
        </GameCard>
      </Section>

      {activeSeason ? (
        <Section title={t('profile.season')}>
          <GameCard>
            <p className="font-display text-sm font-bold text-brass-soft">{activeSeason.name}</p>
            <p className="mt-1 text-xs text-white/60">{activeSeason.description}</p>
            <p className="mt-2 font-mono text-[11px] text-white/45">
              {t('profile.specialNumbers', { numbers: activeSeason.special_numbers.join(', ') })}
            </p>
          </GameCard>
        </Section>
      ) : null}

      {startContext?.shared_plate_id || startContext?.shared_number ? (
        <GameCard accent="#22d3ee">
          <p className="text-sm">{t('profile.sharedNumber')}</p>
          <p className="number-display mt-1 text-3xl text-cyan-300">
            #{startContext.shared_plate_id ?? startContext.shared_number}
          </p>
        </GameCard>
      ) : null}
    </div>
  );
}

export default ProfilePage;
