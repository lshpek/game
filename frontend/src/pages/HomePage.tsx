import { useCallback, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ApiError, makeIdempotencyKey } from '@/lib/api';
import { haptic, hapticError, hapticSuccess, shareToChat } from '@/lib/telegram';
import { compactCoins, formatCoins } from '@/lib/format';
import { game, leaderboard, social, user } from '@/services/api';
import { useAuthStore } from '@/store/auth';
import type { RollResult } from '@/types';
import { GameCard, ProgressBar, Section } from '@/components/GameCard';
import { RarityBadge } from '@/components/RarityBadge';
import { ResultOverlay } from '@/components/ResultOverlay';
import { RollButton } from '@/components/RollButton';
import { ShareCard } from '@/components/ShareCard';
import { ErrorState } from '@/components/States';

export function HomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const profile = useAuthStore((state) => state.profile);
  const applyProfile = useAuthStore((state) => state.applyProfile);

  const [result, setResult] = useState<RollResult | null>(null);
  const [showShare, setShowShare] = useState(false);

  const daily = useQuery({ queryKey: ['daily'], queryFn: game.daily, refetchOnWindowFocus: false });
  const top = useQuery({ queryKey: ['user-top'], queryFn: user.top, refetchOnWindowFocus: false });
  const board = useQuery({
    queryKey: ['leaderboard', 'VALUE', 'daily'],
    queryFn: () => leaderboard.board('VALUE', 'daily', 5),
    refetchOnWindowFocus: false,
  });
  const referrals = useQuery({ queryKey: ['referrals'], queryFn: social.referrals });
  const challenges = useQuery({ queryKey: ['challenges'], queryFn: social.challenges });

  const roll = useMutation({
    mutationFn: (key: string) => game.roll(key),
    onSuccess: (data) => {
      setResult(data);
      if (profile) {
        applyProfile({ ...profile, coins: data.balance, rolls_remaining: data.rolls_remaining });
      }
      for (const key of ['daily', 'user-top', 'collection', 'leaderboard', 'referrals', 'challenges']) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      hapticSuccess();
    },
    onError: (error) => {
      hapticError();
      if (error instanceof ApiError) {
        for (const key of ['daily', 'user']) void queryClient.invalidateQueries({ queryKey: [key] });
      }
    },
  });

  const handleRoll = useCallback(() => {
    haptic('medium');
    roll.mutate(makeIdempotencyKey('roll'));
  }, [roll]);

  const handleConvert = useCallback(async () => {
    if (!result) return;
    try {
      const conversion = await game.convertDuplicate(result.number.number);
      if (profile) applyProfile({ ...profile, coins: conversion.balance });
      setResult(null);
      void queryClient.invalidateQueries({ queryKey: ['collection'] });
      void queryClient.invalidateQueries({ queryKey: ['user'] });
      hapticSuccess();
    } catch (error) {
      if (error instanceof ApiError) window.alert(error.message);
    }
  }, [applyProfile, profile, queryClient, result]);

  const handleShare = useCallback(async () => {
    if (!result) return;
    try {
      const share = await game.share(result.number.number);
      setShowShare(true);
      shareToChat(
        share.mini_app_link,
        `I rolled #${share.number} (${share.rarity}) - can you beat ${formatCoins(share.value)} Coins?`,
      );
    } catch (error) {
      if (error instanceof ApiError) window.alert(error.message);
    }
  }, [result]);

  if (!profile) return <ErrorState message="Profile unavailable." />;

  const rollsLeft = daily.data?.rolls_remaining ?? profile.rolls_remaining;
  const lastNumber = top.data?.rarest?.[0] as { number: string; rarity: string } | undefined;
  const pendingChallenge = challenges.data?.find((item) => item.status === 'PENDING');

  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          {profile.photo_url ? (
            <img src={profile.photo_url} alt="" className="h-10 w-10 rounded-full object-cover" />
          ) : (
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent/30 text-lg">
              {profile.display_name.charAt(0).toUpperCase()}
            </div>
          )}
          <div className="leading-tight">
            <p className="text-sm font-semibold">{profile.display_name}</p>
            <p className="text-xs text-white/45">Streak 🔥 {profile.current_streak}</p>
          </div>
        </div>
        <div className="rounded-2xl border border-amber-300/25 bg-amber-300/10 px-3 py-1.5 text-sm font-bold tabular-nums text-amber-200">
          {compactCoins(profile.coins)} 🪙
        </div>
      </header>

      {daily.data?.can_claim ? (
        <GameCard accent="#fbbf24" className="flex items-center justify-between gap-3 !py-3">
          <div>
            <p className="text-sm font-semibold text-amber-200">Daily reward ready</p>
            <p className="text-xs text-white/55">
              +{formatCoins(daily.data.claim_reward_coins)} Coins and a fresh roll stack
            </p>
          </div>
          <button type="button" className="btn-ghost !min-h-[40px] !px-4 !text-sm" onClick={() => navigate('/profile')}>
            CLAIM
          </button>
        </GameCard>
      ) : null}

      <div className="flex justify-center py-2">
        <RollButton
          rollsLeft={rollsLeft}
          rolling={roll.isPending}
          disabled={rollsLeft <= 0}
          onRoll={handleRoll}
        />
      </div>

      {roll.isError ? (
        <ErrorState
          message={roll.error instanceof ApiError ? roll.error.message : 'Roll failed. Try again.'}
          onRetry={handleRoll}
        />
      ) : null}

      {rollsLeft <= 0 ? (
        <p className="text-center text-sm text-white/55">
          No rolls left today. They refill at midnight UTC — or buy a Box.
        </p>
      ) : null}

      <GameCard>
        <ProgressBar
          value={profile.unique_numbers}
          max={profile.collection_target}
          accent="#7c5cff"
          label="Collection progress"
          trailing={`${profile.unique_numbers} / ${profile.collection_target}`}
        />
        {profile.premium.active ? <p className="mt-3 text-xs font-semibold text-amber-200">PRO member</p> : null}
      </GameCard>

      <div className="grid grid-cols-2 gap-3">
        <button type="button" className="btn-ghost flex-col !min-h-[64px]" onClick={() => navigate('/containers')}>
          <span className="text-xl" aria-hidden>
            📦
          </span>
          <span className="text-xs">Boxes</span>
        </button>
        <button type="button" className="btn-ghost flex-col !min-h-[64px]" onClick={() => navigate('/collection')}>
          <span className="text-xl" aria-hidden>
            📚
          </span>
          <span className="text-xs">Collection</span>
        </button>
      </div>

      {lastNumber ? (
        <Section title="Best find">
          <GameCard className="flex items-center justify-between">
            <div>
              <p className="number-display text-3xl">{lastNumber.number}</p>
              <RarityBadge rarity={lastNumber.rarity} size="sm" className="mt-1" />
            </div>
            <p className="number-display text-xl text-white/80">{formatCoins(profile.best_value)} 🪙</p>
          </GameCard>
        </Section>
      ) : null}

      {pendingChallenge ? (
        <Section title="Open challenge">
          <GameCard accent="#f472b6" className="space-y-3">
            <p className="text-sm">
              @{pendingChallenge.challenger?.username ?? pendingChallenge.challenger?.display_name} challenged you.
            </p>
            <p className="number-display text-2xl">#{pendingChallenge.challenger_number}</p>
            <button type="button" className="btn-primary w-full" onClick={() => navigate('/profile')}>
              ACCEPT CHALLENGE
            </button>
          </GameCard>
        </Section>
      ) : null}

      <Section title="Today's ranking">
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
            <p className="py-3 text-center text-sm text-white/45">No rolls yet today. Be the first.</p>
          ) : null}
        </GameCard>
      </Section>

      <Section
        title="Invite friends"
        action={
          <button type="button" className="text-xs text-accent-soft" onClick={() => navigate('/profile')}>
            View
          </button>
        }
      >
        <GameCard className="flex items-center justify-between text-sm">
          <span>
            Activated: <span className="font-semibold">{referrals.data?.activated ?? 0}</span>
          </span>
          <span className="text-white/50">+{formatCoins(referrals.data?.reward_coins ?? 0)} 🪙 each</span>
        </GameCard>
      </Section>

      <ResultOverlay
        open={Boolean(result)}
        number={result?.number ?? null}
        rarity={result?.rarity ?? null}
        isDuplicate={result?.is_duplicate ?? false}
        isFirstDiscovery={result?.is_first_discovery ?? false}
        conversionValue={result?.conversion_value ?? 0}
        coinsAwarded={result?.coins_awarded ?? 0}
        achievements={result?.unlocked_achievements ?? []}
        onClose={() => {
          setResult(null);
          setShowShare(false);
        }}
        onShare={handleShare}
        onConvert={handleConvert}
      />

      {showShare && result ? (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-ink-950/90 p-6"
          onClick={() => setShowShare(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Share card"
        >
          <div onClick={(event) => event.stopPropagation()}>
            <ShareCard
              number={result.number}
              ownerName={profile.display_name}
              ownerUsername={profile.username}
            />
            <button type="button" className="btn-ghost mt-4 w-full" onClick={() => setShowShare(false)}>
              CLOSE
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
