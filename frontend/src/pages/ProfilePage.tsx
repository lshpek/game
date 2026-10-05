import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError } from '@/lib/api';
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

/**
 * Project the daily status onto the shared roll-balance shape.
 *
 * The two endpoints overlap but are not identical: `/api/daily` reports the daily streak
 * as well as the bank, and has no `bank_cap`. Rather than loosening `RollBalance` - which
 * is the authoritative roll contract - the narrower payload is projected onto it, using the
 * daily allowance as the cap, which is exactly what a cap is.
 */
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

  const daily = useQuery({ queryKey: ['daily'], queryFn: game.daily });
  const achievements = useQuery({ queryKey: ['achievements'], queryFn: game.achievements });
  const seasons = useQuery({ queryKey: ['seasons'], queryFn: game.seasons });

  const claim = useMutation({
    mutationFn: game.claimDaily,
    onSuccess: async (result) => {
      if (profile) applyProfile({ ...profile, coins: result.balance });
      for (const key of ['daily', 'achievements', 'user', 'referrals']) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      await refreshProfile();
      haptic();
    },
    onError: (error) => {
      if (error instanceof ApiError) window.alert(error.message);
    },
  });

  if (!profile) {
    return <ErrorState message={t('app.profileUnavailable')} onRetry={() => void refreshProfile()} />;
  }

  const unlocked = achievements.data?.filter((item) => item.unlocked).length ?? 0;
  const activeSeason = seasons.data?.find((item) => item.is_active);

  return (
    <div className="space-y-5">
      {/*
        Identity. A bare row rather than a card: the profile is a list of things, and an
        avatar block wrapped in the same chrome as everything else just becomes one more
        item competing with them.
      */}
      <header className="flex items-center gap-3.5 px-1 pt-1">
        {profile.photo_url ? (
          <img
            src={profile.photo_url}
            alt=""
            className="h-14 w-14 shrink-0 rounded-full object-cover ring-1 ring-white/10"
          />
        ) : (
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-[18px] font-bold text-white/70">
            {profile.display_name.charAt(0).toUpperCase()}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <h1 className="truncate t-h1 text-white">
            {profile.username ? `@${profile.username}` : profile.display_name}
          </h1>
          <p className="mt-0.5 flex flex-wrap items-center gap-1.5">
            {profile.premium ? (
              <span className="rounded-md border border-amber-300/30 bg-amber-300/10 px-1.5 py-0.5 text-[9px] font-bold tracking-[0.06em] text-amber-200">
                PREMIUM
              </span>
            ) : null}
            {profile.is_admin ? (
              <span className="rounded-md border border-white/15 bg-white/[0.06] px-1.5 py-0.5 text-[9px] font-bold tracking-[0.06em] text-white/60">
                ADMIN
              </span>
            ) : null}
            <span className="text-[11px] text-white/35">
              {t('profile.joined', { when: formatRelativeTime(profile.created_at, t) })}
            </span>
          </p>
        </div>
      </header>

      {/*
        Six stats in a 3x2 grid rather than one card with six numbers crammed inside it:
        each number now gets its own touch-sized cell, which is what makes the grid
        readable at 360px.
      */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { value: formatCoins(profile.coins), label: t('common.coins'), tone: 'text-brass' },
          { value: profile.total_rolls, label: t('common.rolls'), tone: 'text-white' },
          { value: profile.plates_count, label: t('common.plates'), tone: 'text-white' },
          { value: profile.countries_count, label: t('common.countries'), tone: 'text-white' },
          { value: profile.first_discoveries_count, label: t('common.discoveries'), tone: 'text-white' },
          { value: `🔥 ${profile.current_streak}`, label: t('common.streak'), tone: 'text-white' },
        ].map((stat) => (
          <div key={stat.label} className="stat">
            <span className={`number-display text-[19px] font-bold ${stat.tone}`}>{stat.value}</span>
            <span className="t-micro truncate text-white/35">{stat.label}</span>
          </div>
        ))}
      </div>

      <GameCard className="space-y-2.5">
        <div className="flex items-baseline justify-between gap-2">
          <span className="t-body text-white/60">
            {t('profile.level', { level: profile.collector_level?.level ?? 1 })}
          </span>
          <span className="t-caption font-semibold text-white/70">
            {lang === 'ru' ? profile.collector_level?.title_ru : profile.collector_level?.title_en}
          </span>
        </div>
        <ProgressBar
          value={profile.collector_level?.xp_into_level ?? 0}
          max={profile.collector_level?.xp_for_level ?? 1}
          label={`${profile.collector_level?.xp_into_level ?? 0} / ${profile.collector_level?.xp_for_level ?? 0} XP`}
        />
        {profile.best_plate_text ? (
          <p className="t-caption text-white/45">
            {t('profile.bestPlate')}{' '}
            <span className="number-display font-semibold text-brass">
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

      {daily.data?.can_claim ? (
        <GameCard accent="#fbbf24" className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-amber-200">{t('profile.dailyReward')}</p>
            <p className="text-sm font-bold text-amber-200">
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
            <span className="text-white/55">{t('profile.rollsRemaining')}</span>
            <span className="tabular-nums font-semibold">{daily.data?.rolls_remaining ?? 0}</span>
          </div>
          {/* The same economy the hunt screen shows: the normal bank, the bonus bank
              and when the next passive roll arrives. */}
          <RollBalanceLine rolls={rollBalanceFrom(daily.data)} compact />
        </GameCard>
      )}

      {/*
        The legacy four-digit line. It is *not* in the bottom navigation any more - the
        product is a physical collectible atlas, and a rolling-four-digits game sitting in
        the primary nav told the player otherwise. It stays reachable from here so nothing
        production-side was removed.
      */}
      <button
        type="button"
        className="glass-interactive flex w-full items-center gap-3 px-3.5 py-3 text-left"
        onClick={() => navigate('/legacy')}
      >
        <span aria-hidden className="text-[20px] leading-none">
          {t('boxes.icon')}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block t-body font-semibold text-white">{t('boxes.title')}</span>
          <span className="block t-micro text-white/35">{t('boxes.subtitle')}</span>
        </span>
        <span aria-hidden className="shrink-0 text-[13px] text-white/35">
          ›
        </span>
      </button>

      <SocialPanel />

      <Section
        title={t('profile.achievements', {
          unlocked,
          total: achievements.data?.length ?? 0,
        })}
      >
        {achievements.isLoading ? <LoadingSpinner /> : null}
        <GameCard className="divide-y divide-white/5 !p-2">
          {(achievements.data ?? []).map((item) => (
            <div key={item.code} className="flex items-center gap-3 px-2 py-2">
              <span className="text-lg" aria-hidden>
                {item.unlocked ? '🏅' : '🔒'}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{item.name}</span>
                <span className="block truncate text-[11px] text-white/45">{item.description}</span>
              </span>
              <span className="text-[11px] tabular-nums text-white/50">
                {item.progress}/{item.threshold}
              </span>
            </div>
          ))}
        </GameCard>
      </Section>

      {activeSeason ? (
        <Section title={t('profile.season')}>
          <GameCard>
            <p className="text-sm font-semibold">{activeSeason.name}</p>
            <p className="mt-1 text-xs text-white/50">{activeSeason.description}</p>
            <p className="mt-2 text-[11px] text-white/40">
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
