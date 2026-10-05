import { useCallback, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';

import { CountrySelector } from '@/components/CountrySelector';
import Reveal from '@/components/Reveal';
import { CollectiblePreview } from '@/components/CollectiblePreview';
import { NextTargetLine, RollBalanceLine } from '@/components/RollEconomy';
import RollButton from '@/components/RollButton';
import { KindSelector } from '@/components/Selectors';
import { useT } from '@/i18n';
import { trackCollectionOpened, trackSellClicked } from '@/lib/analytics';
import { ApiError, makeIdempotencyKey } from '@/lib/api';
import { formatCoins } from '@/lib/format';
import { EASE, SPRING, useReducedMotion } from '@/lib/motion';
import { hapticCue } from '@/lib/telegram';
import { countries as countriesApi, game } from '@/services/api';
import { useActiveCountry } from '@/store/activeCountry';
import { useAuthStore } from '@/store/auth';
import type {
  CollectibleKind,
  CountryCompletion,
  CountrySummary,
  PlateCard,
  PlateRollResult,
  RollBalance,
} from '@/types';

/**
 * The hunt screen: the core loop, and the reason the app exists.
 *
 * The reading order *is* the loop:
 *
 * ```
 * COUNTRY → WHAT TO HUNT → ROLL → REVEAL → KEEP / SHARE / SELL → ROLL AGAIN
 * ```
 *
 * ### Visual hierarchy
 *
 * The screen has exactly one primary action, and everything else is deliberately quieter:
 *
 * 1. **Where you are** - the country, one row, one tap.
 * 2. **What you are hunting** - three segments, not a settings list.
 * 3. **The button** - the brightest surface in the app, with the bank directly above it.
 * 4. **The last find** - the physical object, at a size you recognise instantly.
 * 5. **Progress** - one bar, with the count.
 * 6. Nothing else. There is no ranking teaser, no mission block, no social prompt.
 *
 * That last point is the change from the previous layout, which put six equally-weighted
 * cards on one screen and made the roll button one of many things to look at.
 *
 * ### Invariants this screen owns
 *
 * * **One roll per press.** A double tap is swallowed by a synchronous ref *and* by the
 *   server's idempotency key, so the two layers together make a double roll impossible.
 * * **One result experience.** The reveal is the shared `Reveal` component, and the
 *   result screen can start the next roll without ever being closed first.
 */

interface Props {
  onOpenCollection?: () => void;
  onOpenCountry?: (code: string) => void;
}

/**
 * Two windows. A press on the roll button is a *deliberate* action; this stops one
 * enthusiastic double tap from being read as two rolls.
 */
const ROLL_COOLDOWN_MS = 400;

export default function HuntPage({ onOpenCollection, onOpenCountry }: Props) {
  const t = useT();
  const reduced = useReducedMotion();
  const queryClient = useQueryClient();
  const applyProfile = useAuthStore((state) => state.applyProfile);
  const profile = useAuthStore((state) => state.profile);
  const applyCountry = useActiveCountry((state) => state.apply);

  const [kind, setKind] = useState<CollectibleKind | null>(null);
  const [result, setResult] = useState<PlateRollResult | null>(null);
  const [notice, setNotice] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null);
  // A synchronous guard: `isPending` only flips after a re-render, so two taps inside
  // one frame would both pass a state-based check.
  const rollingRef = useRef(false);
  const lastRollRef = useRef(0);

  // The atlas is cached hard: 250 countries do not change during a session.
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
  // One request for the hero: the recent find as a *physical object*, the next
  // objective and the authoritative roll economy all come from `/garage`.
  const garage = useQuery({
    queryKey: ['garage'],
    queryFn: () => game.garage(),
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
      for (const key of ['countries', 'collection', 'world', 'garage', 'roll-history']) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      hapticCue('success');
    },
    onError: (error) => {
      hapticCue('error');
      // Never leave the sheet on a country the backend refused.
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
    // No country is sent: the server uses the country it stored for this player, so the
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
      hapticCue('error');
      setNotice({ tone: 'error', text: errorMessage(error, t('hunt.rollFailed')) });
      if (error instanceof ApiError) invalidate();
    },
  });

  const handleRoll = useCallback(() => {
    // Two layers guard the economy, because either alone has a gap: the synchronous ref
    // swallows a second press *inside one frame*, and the cooldown swallows a fast
    // double tap that lands after the first roll has already resolved. The server's
    // idempotency key is the third layer.
    const now = Date.now();
    if (rollingRef.current || now - lastRollRef.current < ROLL_COOLDOWN_MS) return;
    lastRollRef.current = now;
    rollingRef.current = true;
    setNotice(null);
    roll.mutate(makeIdempotencyKey('roll'));
  }, [roll, t]);

  /**
   * Sell duplicates from the reveal.
   *
   * Only ever called when `duplicate_count > 0` - the action does not exist otherwise,
   * so the client cannot construct the invalid `sell(..., max(1, 0))` request that used to
   * be sent on every single-copy find.
   */
  const handleSell = useCallback(async () => {
    const card = result?.plate;
    if (!card) return;
    const duplicates = card.duplicate_count;
    if (duplicates <= 0) {
      setNotice({ tone: 'error', text: t('sell.noDuplicates') });
      return;
    }
    trackSellClicked(card.id, duplicates);
    try {
      const sale = await game.sell(card.id, duplicates, makeIdempotencyKey('sell'));
      if (profile) applyProfile({ ...profile, coins: sale.balance });
      setResult((current) =>
        current
          ? {
              ...current,
              balance: sale.balance,
              plate: { ...current.plate, duplicate_count: sale.duplicates_left },
            }
          : current,
      );
      setNotice({ tone: 'ok', text: t('sell.success', { n: sale.numora_gained }) });
      hapticCue('success');
      invalidate();
    } catch (error) {
      // A failed sale must be visible and actionable, never a silent no-op.
      hapticCue('error');
      setNotice({ tone: 'error', text: errorMessage(error, t('sell.failed')) });
    }
  }, [applyProfile, invalidate, profile, result, t]);

  const handleShare = useCallback(async () => {
    const card = result?.plate;
    if (!card) return;
    try {
      const share = await game.share(card.id);
      window.open(
        `https://t.me/share/url?url=${encodeURIComponent(share.mini_app_link)}&text=${encodeURIComponent(
          share.share_text_en || share.share_text_ru || share.plate_text,
        )}`,
        '_blank',
        'noopener',
      );
      void queryClient.invalidateQueries({ queryKey: ['user'] });
    } catch (error) {
      hapticCue('error');
      setNotice({ tone: 'error', text: errorMessage(error, t('share.failed')) });
    }
  }, [queryClient, result, t]);

  const openCollection = useCallback(() => {
    trackCollectionOpened('hunt');
    onOpenCollection?.();
  }, [onOpenCollection]);

  const recentCard: PlateCard | null = garage.data?.recent ?? null;
  const rolls: RollBalance | null =
    result?.rolls ?? garage.data?.rolls ?? profileToRollBalance(profile?.rolls_remaining);
  const nextTarget = result?.next_target ?? garage.data?.next_target ?? null;
  const completion: CountryCompletion | null = garage.data?.country_progress ?? null;
  const coins = result?.balance ?? profile?.coins ?? 0;
  const busy = roll.isPending;
  const activeCountryName =
    list.find((item) => item.code === activeCode) ??
    (garage.data?.hunt_country
      ? {
          code: garage.data.hunt_country,
          name_en: garage.data.hunt_country_name_en ?? '',
          flag: garage.data.hunt_country_flag ?? '',
        }
      : undefined);

  return (
    <div className="flex flex-col gap-[var(--section-gap)]" data-testid="hunt-page">
      <Reveal
        card={result?.plate ?? null}
        loading={busy}
        // Synthetic previews the reel scrolls through. Generated and returned by the
        // backend in the same response as the real result, and never persisted - the
        // reel settles on `plate`, which was committed before these existed.
        reel={result?.reel ?? []}
        isFirstDiscovery={Boolean(result?.is_first_discovery)}
        onClose={() => setResult(null)}
        onRollAgain={handleRoll}
        canRollAgain={(rolls?.rolls_remaining ?? 0) > 0}
        rolling={busy}
        onKeep={() => setResult(null)}
        onShare={handleShare}
        onSellDuplicates={handleSell}
        onOpenCollection={() => {
          trackCollectionOpened('reveal');
          setResult(null);
          openCollection();
        }}
      />

      {/* 1. WHERE. */}
      <section className="flex flex-col gap-2" aria-label={t('hunt.aria')}>
        <div className="flex items-center justify-between">
          <h2 className="eyebrow">{t('hunt.title')}</h2>
          {activeCode ? (
            <button
              type="button"
              className="t-micro text-white/40 transition active:scale-95"
              onClick={() => onOpenCountry?.(activeCode)}
            >
              {activeCountryName?.flag} {activeCode}
            </button>
          ) : null}
        </div>
        {countryList.isLoading ? (
          <div className="h-[62px] animate-pulse rounded-[18px] bg-white/[0.04]" />
        ) : (
          <CountrySelector
            value={activeCode}
            onChange={(code) => switchCountry.mutate(code)}
            countries={list}
            disabled={busy || switchCountry.isPending}
          />
        )}
      </section>

      {/* 2. WHAT TO HUNT. */}
      <section aria-label={t('category.aria')}>
        <KindSelector value={kind} onChange={setKind} disabled={busy} />
      </section>

      {/* Errors are always visible and actionable. A silent failure here is worse than
          the error itself: the button would simply stop working. */}
      {(switchCountry.isError || notice?.tone === 'error') && (
        <p
          role="alert"
          className="rounded-xl border border-rose-400/25 bg-rose-500/10 px-3 py-2 t-caption text-rose-200"
        >
          {notice?.tone === 'error'
            ? notice.text
            : errorMessage(switchCountry.error, t('country.switchFailed'))}
        </p>
      )}

      {/* 3. THE BUTTON. Bank and count on one line, then the control. */}
      <section className="flex flex-col items-center gap-2.5">
        <div className="flex w-full items-center justify-between rounded-2xl border border-white/[0.07] bg-white/[0.03] px-3.5 py-2.5">
          <div className="flex min-w-0 flex-col">
            <span className="eyebrow">{t('hunt.wallet')}</span>
            <span className="number-display text-[17px] font-bold text-white">
              {formatCoins(coins)}
            </span>
          </div>
          <RollBalanceLine rolls={rolls} compact />
        </div>

        <RollButton
          rolls={rolls}
          onRoll={handleRoll}
          rolling={busy}
          locked={rollingRef.current}
          className="max-w-[420px]"
        />

        <NextTargetLine target={nextTarget} />
      </section>

      {/* SUCCESS FEEDBACK. A sale must be acknowledged where the player is looking. */}
      <AnimatePresence>
        {notice?.tone === 'ok' && (
          <motion.p
            role="status"
            className="rounded-xl border border-emerald-400/25 bg-emerald-500/10 px-3 py-2 text-center t-caption text-emerald-200"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.24, ease: EASE.out }}
          >
            {notice.text}
          </motion.p>
        )}
      </AnimatePresence>

      {/* 4. THE LAST FIND. The physical object, because that is what they just got. */}
      <section className="flex flex-col gap-2" aria-label={t('hunt.recentFind')}>
        <h2 className="eyebrow">{t('hunt.recentFind')}</h2>
        {garage.isLoading ? (
          <div className="h-44 animate-pulse rounded-[22px] bg-white/[0.04]" />
        ) : recentCard ? (
          <motion.div
            initial={reduced ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...SPRING.settle, duration: 0.4 }}
          >
            <CollectiblePreview card={recentCard} scale={0.66} onOpen={openCollection} />
          </motion.div>
        ) : (
          <p className="stage px-4 py-8 text-center t-caption text-white/35">{t('hunt.empty')}</p>
        )}
      </section>

      {/* 5. PROGRESS. One bar, one count. */}
      {completion ? <CountryProgressStrip completion={completion} /> : null}

      <p className="text-center text-[11px] leading-relaxed text-white/25">
        {t('hunt.syntheticNote')}
      </p>
    </div>
  );
}

/** Country completion, as a quiet progress bar with the count that matters. */
function CountryProgressStrip({ completion }: { completion: CountryCompletion }) {
  const t = useT();
  const percent = Math.round(completion.progress * 100);
  return (
    <div className="flex w-full items-center gap-3">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.07]">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-accent/70 to-brass/70"
          initial={false}
          animate={{ width: `${percent}%` }}
          transition={{ ...SPRING.settle, duration: 0.5 }}
        />
      </div>
      <span className="shrink-0 text-[11px] tabular-nums text-white/40">
        {completion.collected} / {completion.total}
      </span>
      <span className="sr-only-number">
        {t('collection.completion', { collected: completion.collected, total: completion.total })}
      </span>
    </div>
  );
}

/**
 * Turn a failed request into something the player can act on.
 */
function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

/**
 * A roll balance for a session that has not loaded `/garage` yet.
 *
 * Only the count is known, so the cap is left unset and no countdown is invented: a
 * missing piece of server data is shown as absent rather than guessed at.
 */
function profileToRollBalance(remaining: number | undefined): RollBalance | null {
  if (remaining === undefined) return null;
  return {
    rolls_remaining: remaining,
    normal_rolls: remaining,
    bonus_rolls: 0,
    daily_allowance: remaining,
    bank_cap: remaining,
    resets_at: '',
    next_roll_at: null,
    seconds_to_next_roll: 0,
    regen_minutes: 45,
  };
}
export { HuntPage };
