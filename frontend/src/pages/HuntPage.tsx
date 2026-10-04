import { useCallback, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import clsx from 'clsx';
import { CountrySelector } from '@/components/CountrySelector';
import { Reveal } from '@/components/Reveal';
import { KindSelector } from '@/components/Selectors';
import { LoadingSpinner } from '@/components/States';
import { useI18n } from '@/i18n';
import { ApiError, makeIdempotencyKey } from '@/lib/api';
import { RARITY_COLORS, formatCoins } from '@/lib/format';
import { haptic, hapticError, hapticSuccess } from '@/lib/telegram';
import { countries as countriesApi, game, leaderboard } from '@/services/api';
import { useActiveCountry } from '@/store/activeCountry';
import { useAuthStore } from '@/store/auth';
import type { CollectibleKind, CountrySummary, PlateRollResult } from '@/types';

/**
 * The hunt screen - the game's home, and the loop the player repeats.
 *
 * Reading order is deliberate and matches what the player is actually doing:
 * country (where) → kind (what) → wallet (what it costs) → **the button** → recent
 * find. Everything else is secondary and lives below the fold on a 390px screen.
 *
 * The active country is the one the server stores; this screen mirrors it, so a
 * refresh always lands on the same world. Changing it is a validated write, not a
 * local toggle.
 */
export function HuntPage({ onOpenCollection }: { onOpenCollection?: () => void }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const applyProfile = useAuthStore((state) => state.applyProfile);
  const profile = useAuthStore((state) => state.profile);
  const applyCountry = useActiveCountry((state) => state.apply);

  const [kind, setKind] = useState<CollectibleKind | null>(null);
  const [result, setResult] = useState<PlateRollResult | null>(null);
  // Guards the in-flight roll against a double tap inside a single frame.
  const rollingRef = useRef(false);

  // The atlas is cached for five minutes: 250 countries never change during a session.
  const countryList = useQuery({
    queryKey: ['countries', 'selector'],
    queryFn: () => countriesApi.list({ limit: 250 }),
    staleTime: 300_000,
  });
  const activeCountry = useQuery({
    queryKey: ['countries', 'active'],
    queryFn: countriesApi.active,
    staleTime: 60_000,
  });

  const historyQuery = useQuery({
    queryKey: ['roll-history'],
    queryFn: () => game.rollHistory(4),
    staleTime: 15_000,
  });

  const list: CountrySummary[] = useMemo(
    () => (countryList.data?.items ?? []) as CountrySummary[],
    [countryList.data],
  );
  const activeCode = activeCountry.data?.code ?? null;

  const switchCountry = useMutation({
    mutationFn: (code: string | null) => countriesApi.setActive(code),
    onSuccess: (data) => {
      applyCountry(data);
      void queryClient.invalidateQueries({ queryKey: ['countries'] });
      void queryClient.invalidateQueries({ queryKey: ['collection'] });
      void queryClient.invalidateQueries({ queryKey: ['world'] });
      void queryClient.invalidateQueries({ queryKey: ['garage'] });
      hapticSuccess();
    },
    onError: (error) => {
      hapticError();
      // Never leave the sheet showing a country the backend refused.
      if (error instanceof ApiError) {
        void queryClient.invalidateQueries({ queryKey: ['countries', 'active'] });
      }
    },
  });

  const invalidate = useCallback(() => {
    for (const key of ['world', 'roll-history', 'garage', 'collection', 'user', 'daily', 'countries']) {
      void queryClient.invalidateQueries({ queryKey: [key] });
    }
  }, [queryClient]);

  const roll = useMutation({
    // No country is sent: the server uses the active country it stored, so the
    // client can never point a roll at a country the backend has not validated.
    mutationFn: (key: string) => game.roll(key, { kind }),
    onSuccess: (data) => {
      rollingRef.current = false;
      setResult(data);
      if (profile) {
        applyProfile({ ...profile, coins: data.balance, rolls_remaining: data.rolls_remaining });
      }
      invalidate();
    },
    onError: (error) => {
      rollingRef.current = false;
      hapticError();
      if (error instanceof ApiError) invalidate();
    },
  });

  const handleRoll = useCallback(() => {
    // A double tap must not become two rolls. `isPending` only flips after a
    // re-render, so two taps inside one frame would both pass the disabled check
    // and the player would silently pay two rolls for one press.
    if (rollingRef.current) return;
    rollingRef.current = true;
    haptic('medium');
    roll.mutate(makeIdempotencyKey('roll'));
  }, [roll]);

  const handleSell = useCallback(async () => {
    if (!result) return;
    try {
      const sale = await game.sell(result.plate.id, Math.max(1, result.plate.duplicate_count));
      if (profile) applyProfile({ ...profile, coins: sale.balance });
      setResult(null);
      invalidate();
      hapticSuccess();
    } catch {
      hapticError();
    }
  }, [applyProfile, invalidate, profile, result]);

  const handleShare = useCallback(async () => {
    if (!result) return;
    try {
      const share = await game.share(result.plate.id);
      window.open(
        `https://t.me/share/url?url=${encodeURIComponent(share.mini_app_link)}&text=${encodeURIComponent(
          share.share_text_en || share.share_text_ru || share.plate_text,
        )}`,
        '_blank',
        'noopener',
      );
    } catch {
      hapticError();
    }
  }, [result]);

  const recent = historyQuery.data?.[0];
  const rollsLeft = profile?.rolls_remaining ?? 0;
  const coins = profile?.coins ?? 0;
  const busy = roll.isPending || switchCountry.isPending;
  const outOfRolls = !busy && !result && rollsLeft <= 0;
  const activeCountryName = list.find((item) => item.code === activeCode);
  const kindLabel = kind ? t(kind === 'SIM_CARD' ? 'category.sim' : 'category.plate') : t('category.all');

  return (
    <div className="flex flex-col gap-4 pb-28" data-testid="hunt-page">
      <Reveal
        result={result}
        pending={busy}
        onClose={() => {
          rollingRef.current = false;
          setResult(null);
        }}
        onShare={handleShare}
        onSell={handleSell}
        onViewCollection={() => {
          setResult(null);
          onOpenCollection?.();
        }}
      />

      {/* Where, then what. */}
      <section className="flex flex-col gap-2" aria-label={t('hunt.aria')}>
        <div className="flex items-center justify-between px-1">
          <h2 className="text-[10px] font-black uppercase tracking-[0.32em] text-white/35">
            {t('hunt.title')}
          </h2>
          <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/35">
            {activeCountryName?.flag} {activeCode ?? t('hunt.world')} · {kindLabel}
          </span>
        </div>
        {countryList.isLoading ? (
          <div className="h-[58px] animate-pulse rounded-2xl bg-white/[0.04]" />
        ) : (
          <CountrySelector
            value={activeCode}
            onChange={(code) => switchCountry.mutate(code)}
            countries={list}
            disabled={busy}
          />
        )}
        <KindSelector value={kind} onChange={setKind} disabled={busy} />
      </section>

      {/* Wallet. */}
      <section className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3">
        <div className="flex flex-col">
          <span className="text-[9px] font-bold uppercase tracking-[0.28em] text-white/35">
            {t('hunt.wallet')}
          </span>
          <span className="number-display text-lg font-black tracking-tight text-white">
            {formatCoins(coins)}
          </span>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-[9px] font-bold uppercase tracking-[0.28em] text-white/35">
            {t('hunt.rollsLeft')}
          </span>
          <span className="number-display text-lg font-black tracking-tight text-emerald-300">
            {rollsLeft}
          </span>
        </div>
      </section>

      {/* The button. */}
      <section className="flex flex-col items-center gap-2">
        <motion.button
          type="button"
          onClick={handleRoll}
          disabled={busy}
          whileTap={busy ? undefined : { scale: 0.94 }}
          className={clsx(
            'relative flex h-[86px] w-full max-w-sm items-center justify-center overflow-hidden rounded-3xl',
            'text-xl font-black uppercase tracking-[0.28em] text-white',
            'shadow-[0_24px_60px_-20px_rgba(255,255,255,0.45)] transition active:scale-[0.98]',
            busy && 'opacity-70',
          )}
          style={{
            background:
              'linear-gradient(160deg, rgba(255,255,255,0.22), rgba(255,255,255,0.06) 42%, rgba(0,0,0,0.35))',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.5), 0 26px 60px -22px rgba(120,180,255,0.55)',
            backdropFilter: 'blur(8px)',
          }}
          data-testid="roll-button"
          aria-label={t('hunt.rollNow')}
        >
          <span
            aria-hidden
            className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-white/70 to-transparent"
          />
          {busy ? t('hunt.rolling') : outOfRolls ? t('hunt.outOfRolls') : t('hunt.rollNow')}
        </motion.button>
        <p className="text-center text-[11px] text-white/35">
          {outOfRolls ? t('hunt.backTomorrow') : t('hunt.syntheticNote')}
        </p>
      </section>

      {/* Recent find. */}
      <section className="flex flex-col gap-2" aria-label={t('hunt.recentFind')}>
        <h3 className="px-1 text-[10px] font-black uppercase tracking-[0.32em] text-white/35">
          {t('hunt.recentFind')}
        </h3>
        {historyQuery.isLoading ? (
          <LoadingSpinner />
        ) : !recent ? (
          <p className="rounded-2xl border border-white/8 bg-white/[0.02] px-4 py-6 text-center text-sm text-white/35">
            {t('hunt.empty')}
          </p>
        ) : (
          <div
            className="rounded-2xl border border-white/8 bg-white/[0.03] p-4"
            style={{ borderColor: `${RARITY_COLORS[(recent.rarity as never) ?? 'COMMON'] ?? '#8b93a7'}33` }}
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/35">
                {recent.rarity}
              </span>
              <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/35">
                {recent.country_code}
              </span>
            </div>
            <span className="number-display block text-center text-2xl text-white">{recent.plate_text}</span>
          </div>
        )}
      </section>

      <SocialStrip />
    </div>
  );
}

/** A single quiet row of social proof - never a popup, never above the roll. */
function SocialStrip() {
  const { t } = useI18n();
  const board = useQuery({
    queryKey: ['leaderboard', 'COLLECTION', 'daily'],
    queryFn: () => leaderboard.board('COLLECTION', 'daily', 3),
    staleTime: 60_000,
  });
  const entries = board.data?.entries ?? [];
  if (!entries.length) return null;

  return (
    <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
      <h3 className="mb-2 text-[10px] font-black uppercase tracking-[0.32em] text-white/35">
        {t('nav.ranking')}
      </h3>
      <div className="flex flex-col gap-1">
        {entries.map((entry) => (
          <div key={entry.user_id} className="flex items-center justify-between text-xs">
            <span className="text-white/60">
              {entry.display_name || (entry.username ? `@${entry.username}` : `#${entry.user_id}`)}
            </span>
            <span className="number-display text-white/80">{formatCoins(entry.score)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export default HuntPage;