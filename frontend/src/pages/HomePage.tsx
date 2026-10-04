import { useCallback, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ApiError, makeIdempotencyKey } from '@/lib/api';
import { haptic, hapticError, hapticSuccess, shareToChat } from '@/lib/telegram';
import { compactCoins, formatCoins } from '@/lib/format';
import { game, leaderboard, social } from '@/services/api';
import { useAuthStore } from '@/store/auth';
import type { PlateRollResult } from '@/types';
import { GameCard, ProgressBar, Section } from '@/components/GameCard';
import { PlateVisual } from '@/components/PlateVisual';
import { RarityBadge } from '@/components/RarityBadge';
import { ResultOverlay } from '@/components/ResultOverlay';
import { RollButton } from '@/components/RollButton';
import { ErrorState } from '@/components/States';
import { useI18n } from '@/i18n';

export function HomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { lang, t } = useI18n();
  const profile = useAuthStore((state) => state.profile);
  const applyProfile = useAuthStore((state) => state.applyProfile);

  const [result, setResult] = useState<PlateRollResult | null>(null);

  const daily = useQuery({ queryKey: ['daily'], queryFn: game.daily, refetchOnWindowFocus: false });
  const garage = useQuery({ queryKey: ['garage'], queryFn: game.garage, refetchOnWindowFocus: false });
  const board = useQuery({
    queryKey: ['leaderboard', 'COLLECTION', 'daily'],
    queryFn: () => leaderboard.board('COLLECTION', 'daily', 5),
    refetchOnWindowFocus: false,
  });
  const referrals = useQuery({ queryKey: ['referrals'], queryFn: social.referrals });
  const challenges = useQuery({ queryKey: ['challenges'], queryFn: social.challenges });

  const invalidate = useCallback(() => {
    for (const key of ['daily', 'garage', 'collection', 'leaderboard', 'referrals', 'challenges', 'user']) {
      void queryClient.invalidateQueries({ queryKey: [key] });
    }
  }, [queryClient]);

  const roll = useMutation({
    mutationFn: (key: string) => game.roll(key),
    onSuccess: (data) => {
      setResult(data);
      if (profile) {
        applyProfile({ ...profile, coins: data.balance, rolls_remaining: data.rolls_remaining });
      }
      invalidate();
      hapticSuccess();
    },
    onError: (error) => {
      hapticError();
      if (error instanceof ApiError) {
        invalidate();
      }
    },
  });

  const handleRoll = useCallback(() => {
    haptic('medium');
    roll.mutate(makeIdempotencyKey('roll'));
  }, [roll]);

  const handleSell = useCallback(async () => {
    if (!result) return;
    try {
      const copies = Math.max(1, result.plate.duplicate_count);
      const sale = await game.sell(result.plate.id, copies);
      if (profile) applyProfile({ ...profile, coins: sale.balance });
      setResult(null);
      invalidate();
      hapticSuccess();
    } catch (error) {
      if (error instanceof ApiError) window.alert(error.message);
    }
  }, [applyProfile, invalidate, profile, result]);

  const handleShare = useCallback(async () => {
    if (!result) return;
    try {
      const share = await game.share(result.plate.id);
      shareToChat(share.mini_app_link, (lang === 'ru' ? share.share_text_ru : share.share_text_en) || share.plate_text);
      invalidate();
    } catch (error) {
      if (error instanceof ApiError) window.alert(error.message);
    }
  }, [invalidate, lang, result]);

  const pendingChallenge = challenges.data?.find(
    (item) => item.status === 'PENDING' && item.challenger?.username !== profile?.username,
  );

  const rollsLeft = daily.data?.rolls_remaining ?? profile?.rolls_remaining ?? 0;

  return (
    <div className="space-y-5">
      <section className="flex flex-col items-center gap-3 pt-2">
        {daily.data?.can_claim ? (
          <GameCard accent="#fbbf24" className="w-full space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-amber-200">{t('home.dailyReady')}</span>
              <span className="font-semibold text-amber-200">
                +{formatCoins(daily.data.claim_reward_coins)} 🪙
              </span>
            </div>
            <p className="text-xs text-white/55">{t('home.dailyRewardHint', { coins: formatCoins(daily.data.claim_reward_coins) })}</p>
          </GameCard>
        ) : null}

        <RollButton rollsLeft={rollsLeft} rolling={roll.isPending} onRoll={handleRoll} />
        {rollsLeft <= 0 && !daily.data?.can_claim ? (
          <p className="text-sm text-white/55">{t('home.noRolls')}</p>
        ) : null}
      </section>

      {roll.isError ? (
        <ErrorState
          message={roll.error instanceof ApiError ? roll.error.message : t('home.rollFailed')}
          onRetry={() => roll.mutate(makeIdempotencyKey('roll'))}
        />
      ) : null}
      {/* Garage hero: the most recent find, then the best find stats. */}
      {garage.data?.recent ? (
        <Section
          title={t('home.bestFind')}
          action={
            <button type="button" className="text-xs text-accent-soft" onClick={() => navigate('/collection')}>
              {t('home.view')}
            </button>
          }
        >
          <GameCard className="space-y-3">
            <PlateVisual plate={garage.data.recent} size="md" />
            <div className="flex items-center justify-between">
              <RarityBadge rarity={garage.data.recent.rarity} size="sm" />
              <span className="text-xs text-white/50">
                {garage.data.recent.country.flag}{' '}
                {lang === 'ru' ? garage.data.recent.country.name_ru : garage.data.recent.country.name_en}
              </span>
            </div>
          </GameCard>
        </Section>
      ) : null}

      {garage.data ? (
        <Section title={t('collection.title')}>
          <GameCard className="space-y-3">
            <ProgressBar
              value={garage.data.plates_count}
              max={Math.max(garage.data.plates_count / Math.max(garage.data.world_progress, 0.0001), 1)}
              label={t('profile.level', { level: garage.data.level.level })}
              trailing={`${Math.round(garage.data.world_progress * 100)}%`}
            />
            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div>
                <p className="number-display text-lg">{garage.data.plates_count}</p>
                <p className="text-white/45">{t('common.plates')}</p>
              </div>
              <div>
                <p className="number-display text-lg">{garage.data.countries_count}</p>
                <p className="text-white/45">{t('common.countries')}</p>
              </div>
              <div>
                <p className="number-display text-lg">{garage.data.first_discoveries}</p>
                <p className="text-white/45">{t('common.discoveries')}</p>
              </div>
            </div>
          </GameCard>
        </Section>
      ) : null}

      {pendingChallenge ? (
        <Section title={t('social.challenge')}>
          <GameCard accent="#f472b6" className="space-y-3">
            <p className="text-sm">
              {t('home.challengedYou', {
                name: pendingChallenge.challenger?.username ?? pendingChallenge.challenger?.display_name ?? '',
              })}
            </p>
            <p className="number-display text-2xl">{pendingChallenge.challenger_plate_text}</p>
            <button type="button" className="btn-primary w-full" onClick={() => navigate('/profile')}>
              {t('home.acceptChallenge')}
            </button>
          </GameCard>
        </Section>
      ) : null}

      <Section title={t('home.todayRanking')}>
        <GameCard className="divide-y divide-white/5">
          {(board.data?.entries ?? []).map((entry, index) => (
            <div key={entry.user_id} className="flex items-center gap-3 py-2.5">
              <span className="w-5 text-center text-xs font-bold text-white/40">{index + 1}</span>
              <span className="flex-1 truncate text-sm">
                {entry.username ? `@${entry.username}` : entry.display_name}
              </span>
              <span className="text-sm font-semibold tabular-nums">{compactCoins(entry.score)}</span>
            </div>
          ))}
          {!board.data?.entries.length ? (
            <p className="py-3 text-center text-sm text-white/45">{t('home.noRollsYet')}</p>
          ) : null}
        </GameCard>
      </Section>

      <Section
        title={t('home.inviteFriends')}
        action={
          <button type="button" className="text-xs text-accent-soft" onClick={() => navigate('/profile')}>
            {t('home.view')}
          </button>
        }
      >
        <GameCard className="flex items-center justify-between text-sm">
          <span>
            {t('home.activated')}: <span className="font-semibold">{referrals.data?.activated ?? 0}</span>
          </span>
          <span className="text-white/50">
            {t('home.eachCoins', { coins: formatCoins(referrals.data?.reward_coins ?? 0) })}
          </span>
        </GameCard>
      </Section>

      <ResultOverlay
        open={Boolean(result)}
        result={result}
        onClose={() => setResult(null)}
        onShare={handleShare}
        onSell={handleSell}
      />
    </div>
  );
}
