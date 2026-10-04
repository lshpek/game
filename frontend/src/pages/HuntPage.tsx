import { useCallback, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { LoadingSpinner } from '@/components/States';
import clsx from 'clsx';
import { RarityBadge } from '@/components/RarityBadge';
import { Reveal } from '@/components/Reveal';
import { CategorySelector, CountrySelector } from '@/components/Selectors';
import { useI18n } from '@/i18n';
import { makeIdempotencyKey } from '@/lib/api';
import { RARITY_COLORS, formatCoins } from '@/lib/format';
import { haptic, hapticError, hapticSuccess } from '@/lib/telegram';
import { game, leaderboard } from '@/services/api';
import { useAuthStore } from '@/store/auth';
import type { CollectibleCategory, PlateRollResult } from '@/types';

interface CountryOption {
  code: string;
  flag: string;
  name_en: string;
  name_ru: string;
  discovered?: number;
  total?: number;
}

/**
 * The hunt screen - the game's home, and the loop the player repeats.
 *
 * Reading order is deliberate and matches what the player is actually doing:
 * category (what am I hunting) → country (where) → wallet (what it costs) →
 * **the button** → recent find. Everything else is secondary and lives below the
 * fold on a 390px screen.
 *
 * The roll button is the largest touch target in the app and is the only element
 * that gets a glow. Everything about the outcome is decided by the server; this
 * screen only sends the two filters it was given.
 */
export function HuntPage({ onOpenCollection }: { onOpenCollection?: () => void }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const applyProfile = useAuthStore((state) => state.applyProfile);
  const profile = useAuthStore((state) => state.profile);

  const [category, setCategory] = useState<CollectibleCategory | null>(null);
  const [country, setCountry] = useState<string | null>(null);
  const [result, setResult] = useState<PlateRollResult | null>(null);

  const worldQuery = useQuery({
    queryKey: ['world'],
    queryFn: () => game.world(),
    staleTime: 60_000,
  });
  const historyQuery = useQuery({
    queryKey: ['roll-history'],
    queryFn: () => game.rollHistory(4),
    staleTime: 15_000,
  });

  const countries = useMemo<CountryOption[]>(() => {
    const raw = (worldQuery.data?.countries ?? []) as Array<Record<string, unknown>>;
    return raw
      .map((entry) => {
        const item = entry;
        const config = (item.config ?? {}) as Record<string, unknown>;
        return {
          code: String(item.code ?? ''),
          flag: String(item.flag ?? ''),
          name_en: String(item.name_en ?? item.code ?? ''),
          name_ru: String(item.name_ru ?? item.code ?? ''),
          discovered: Number(item.discovered ?? config.discovered ?? 0),
          total: Number(item.total ?? config.total ?? 0),
        };
      })
      .filter((entry) => entry.code !== '');
  }, [worldQuery.data]);

  const invalidate = useCallback(() => {
    for (const key of ['world', 'roll-history', 'garage', 'collection', 'user', 'daily']) {
      void queryClient.invalidateQueries({ queryKey: [key] });
    }
  }, [queryClient]);

  const roll = useMutation({
    mutationFn: (key: string) => game.roll(key, { category, country_code: country }),
    onSuccess: (data) => {
      setResult(data);
      if (profile) {
        applyProfile({ ...profile, coins: data.balance, rolls_remaining: data.rolls_remaining });
      }
      invalidate();
    },
    onError: (error) => {
      hapticError();
      if (error instanceof Error && 'code' in error) invalidate();
    },
  });

  const handleRoll = useCallback(() => {
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
      const link = share.mini_app_link;
      const text = (share.share_text_en || share.share_text_ru || share.plate_text) ?? '';
      window.open(
        `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`,
        '_blank',
        'noopener',
      );
    } catch {
      hapticError();
    }
  }, [result]);

  const recent = historyQuery.data?.[0] as
    | { roll_id: number; plate_text: string; rarity: string; value: number; country_code?: string }
    | undefined;
  const rollsLeft = profile?.rolls_remaining ?? 0;
  const coins = profile?.coins ?? 0;
  const busy = roll.isPending;
  const outOfRolls = !busy && !result && rollsLeft <= 0;

  const huntLabel = category
    ? category === 'PHONE_NUMBER'
      ? t('category.phone')
      : category === 'SIM_CARD'
        ? t('category.sim')
        : t('category.plate')
    : t('hunt.world');

  return (
    <div className="flex flex-col gap-4 pb-28" data-testid="hunt-page">
      <Reveal
        result={result}
        pending={busy}
        onClose={() => setResult(null)}
        onShare={handleShare}
        onSell={handleSell}
        onViewCollection={() => {
          setResult(null);
          onOpenCollection?.();
        }}
      />

      {/* Current hunt: what and where. */}
      <section className="flex flex-col gap-2" aria-label={t('hunt.aria')}>
        <div className="flex items-center justify-between px-1">
          <h2 className="text-[10px] font-black uppercase tracking-[0.32em] text-white/35">
            {t('hunt.title')}
          </h2>
          <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/35">
            {huntLabel}
            {country ? ` · ${country}` : ''}
          </span>
        </div>
        <CategorySelector value={category} onChange={setCategory} disabled={busy} />
        {worldQuery.isLoading ? (
          <div className="h-[38px] animate-pulse rounded-full bg-white/[0.04]" />
        ) : (
          <CountrySelector
            value={country}
            onChange={setCountry}
            countries={countries}
            disabled={busy}
          />
        )}
      </section>

      {/* Wallet. */}
      <section className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3">
        <div className="flex flex-col">
          <span className="text-[9px] font-bold uppercase tracking-[0.28em] text-white/35">
            {t('hunt.wallet')}
          </span>
          <span className="text-lg font-black tracking-tight text-white">{formatCoins(coins)}</span>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-[9px] font-bold uppercase tracking-[0.28em] text-white/35">
            {t('hunt.rollsLeft')}
          </span>
          <span className="text-lg font-black tracking-tight text-emerald-300">{rollsLeft}</span>
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
              <RarityBadge rarity={recent.rarity} size="sm" />
              <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/35">
                {recent.country_code}
              </span>
            </div>
            <span className="number-display block text-center text-2xl text-white">
              {recent.plate_text}
            </span>
          </div>
        )}
      </section>

      {/* Social preview, deliberately compact. */}
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
        {entries.map((raw) => {
          const entry = raw as unknown as {
            user_id: number;
            username?: string | null;
            display_name?: string | null;
            score?: number | null;
          };
          return (
            <div key={entry.user_id} className="flex items-center justify-between text-xs">
              <span className="text-white/60">
                {entry.display_name || (entry.username ? `@${entry.username}` : `#${entry.user_id}`)}
              </span>
              <span className="number-display text-white/80">{formatCoins(Number(entry.score ?? 0))}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default HuntPage;