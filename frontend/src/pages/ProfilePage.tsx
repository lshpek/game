import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@/lib/api';
import { haptic } from '@/lib/telegram';
import { formatCoins, formatRelativeTime, rarityLabel } from '@/lib/format';
import { game } from '@/services/api';
import { useAuthStore } from '@/store/auth';
import { GameCard, ProgressBar, Section } from '@/components/GameCard';
import { SocialPanel } from '@/components/SocialPanel';
import { ErrorState, LoadingSpinner } from '@/components/States';
import { useI18n } from '@/i18n';

export function ProfilePage() {
  const { lang, t } = useI18n();
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
      <header className="flex items-center gap-3">
        {profile.photo_url ? (
          <img src={profile.photo_url} alt="" className="h-14 w-14 rounded-full object-cover" />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-accent/30 text-xl">
            {profile.display_name.charAt(0).toUpperCase()}
          </div>
        )}
        <div className="min-w-0">
          <h1 className="truncate font-display text-xl font-bold">
            {profile.username ? `@${profile.username}` : profile.display_name}
          </h1>
          <p className="text-xs text-white/45">
            {t('profile.joined', { when: formatRelativeTime(profile.created_at, t) })}
          </p>
        </div>
      </header>

      <GameCard className="grid grid-cols-2 gap-3 text-center">
        {[
          { value: formatCoins(profile.coins), label: t('common.coins'), tone: 'text-amber-200' },
          { value: profile.total_rolls, label: t('common.rolls'), tone: '' },
          { value: profile.unique_numbers, label: t('common.numbers'), tone: '' },
          { value: `🔥 ${profile.current_streak}`, label: t('common.streak'), tone: '' },
        ].map((stat) => (
          <div key={stat.label}>
            <p className={`number-display text-2xl ${stat.tone}`}>{stat.value}</p>
            <p className="text-[11px] uppercase tracking-wider text-white/45">{stat.label}</p>
          </div>
        ))}
      </GameCard>

      <GameCard>
        <ProgressBar
          value={profile.unique_numbers}
          max={profile.collection_target}
          label={t('profile.rarestFind', { rarity: rarityLabel(profile.best_rarity, lang) })}
          trailing={`${formatCoins(profile.best_value)} 🪙`}
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
        <GameCard className="flex items-center justify-between text-sm">
          <span className="text-white/55">{t('profile.rollsRemaining')}</span>
          <span className="tabular-nums font-semibold">{daily.data?.rolls_remaining ?? 0}</span>
        </GameCard>
      )}

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

      {startContext?.shared_number ? (
        <GameCard accent="#22d3ee">
          <p className="text-sm">{t('profile.sharedNumber')}</p>
          <p className="number-display mt-1 text-3xl text-cyan-300">#{startContext.shared_number}</p>
        </GameCard>
      ) : null}
    </div>
  );
}
