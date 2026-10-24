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
import { playCoinJingle } from '@/lib/sound';
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

interface Props {
  onOpenCollection?: () => void;
  onOpenCountry?: (code: string) => void;
}

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
  const rollingRef = useRef(false);
  const lastRollRef = useRef(0);

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
    const now = Date.now();
    if (rollingRef.current || now - lastRollRef.current < ROLL_COOLDOWN_MS) return;
    lastRollRef.current = now;
    rollingRef.current = true;
    setNotice(null);
    roll.mutate(makeIdempotencyKey('roll'));
  }, [roll]);

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
      playCoinJingle();
      hapticCue('success');
      invalidate();
    } catch (error) {
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

      {/* 1. COCKPIT CONTROLS: WHERE & WHAT TO HUNT */}
      <section className="flex flex-col gap-2.5" aria-label={t('hunt.aria')}>
        <div className="flex items-center justify-between">
          <h2 className="eyebrow flex items-center gap-1.5">
            <span aria-hidden="true" className="text-brass">
              ◆
            </span>
            {t('hunt.title')}
          </h2>
          {activeCode ? (
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-0.5 t-micro text-white/65 transition hover:border-white/20 active:scale-95"
              onClick={() => onOpenCountry?.(activeCode)}
            >
              <span>{activeCountryName?.flag}</span>
              <span>{activeCode}</span>
            </button>
          ) : null}
        </div>

        {countryList.isLoading ? (
          <div className="h-[62px] animate-pulse rounded-[20px] bg-white/[0.04]" />
        ) : (
          <CountrySelector
            value={activeCode}
            onChange={(code) => switchCountry.mutate(code)}
            countries={list}
            disabled={busy || switchCountry.isPending}
          />
        )}

        <div aria-label={t('category.aria')}>
          <KindSelector value={kind} onChange={setKind} disabled={busy} />
        </div>

        {completion ? <CountryProgressStrip completion={completion} /> : null}
      </section>

      {(switchCountry.isError || notice?.tone === 'error') && (
        <p
          role="alert"
          className="rounded-xl border border-rose-400/30 bg-rose-500/15 px-3.5 py-2.5 t-caption font-medium text-rose-200 shadow-lift"
        >
          {notice?.tone === 'error'
            ? notice.text
            : errorMessage(switchCountry.error, t('country.switchFailed'))}
        </p>
      )}

      {/* 2. SHOWROOM PEDESTAL: THE LAST FIND (Elevated to Center Stage) */}
      <section className="flex flex-col gap-2" aria-label={t('hunt.recentFind')}>
        <div className="flex items-center justify-between">
          <h2 className="eyebrow">{t('hunt.recentFind')}</h2>
          {recentCard ? (
            <span className="t-micro text-white/35">3D · Tap to inspect</span>
          ) : null}
        </div>
        {garage.isLoading ? (
          <div className="h-44 animate-pulse rounded-[24px] bg-white/[0.04]" />
        ) : recentCard ? (
          <motion.div
            initial={reduced ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...SPRING.settle, duration: 0.4 }}
          >
            <CollectiblePreview card={recentCard} scale={0.82} onOpen={openCollection} />
          </motion.div>
        ) : (
          <div className="stage flex flex-col items-center justify-center gap-2 px-4 py-8 text-center">
            <span aria-hidden="true" className="text-2xl opacity-60">
              🚘 · 💳
            </span>
            <p className="t-caption text-white/50">{t('hunt.empty')}</p>
          </div>
        )}
      </section>

      {/* 3. PRIMARY IGNITION CONSOLE: WALLET, ROLL PEDAL & RADAR TARGET */}
      <section className="mx-auto flex w-full max-w-[520px] flex-col items-center gap-2.5">
        <div className="glass flex w-full items-center justify-between gap-3 px-4 py-2.5">
          <div className="flex min-w-0 flex-col">
            <span className="eyebrow">{t('hunt.wallet')}</span>
            <span className="number-display flex items-center gap-1.5 truncate text-[clamp(16px,4.5vw,18px)] font-bold text-brass-soft">
              <span aria-hidden="true" className="text-[14px]">
                🪙
              </span>
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
          className="w-full"
        />

        <NextTargetLine target={nextTarget} />
      </section>

      <AnimatePresence>
        {notice?.tone === 'ok' && (
          <motion.p
            role="status"
            className="rounded-xl border border-emerald-400/30 bg-emerald-500/15 px-3.5 py-2.5 text-center t-caption font-medium text-emerald-200 shadow-lift"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.24, ease: EASE.out }}
          >
            {notice.text}
          </motion.p>
        )}
      </AnimatePresence>

      <p className="text-center text-[11px] leading-relaxed text-white/30">
        {t('hunt.syntheticNote')}
      </p>
    </div>
  );
}

function CountryProgressStrip({ completion }: { completion: CountryCompletion }) {
  const t = useT();
  const percent = Math.round(completion.progress * 100);
  return (
    <div className="flex w-full items-center gap-3 px-1">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.08]">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-accent via-brass to-amber-300"
          initial={false}
          animate={{ width: `${percent}%` }}
          transition={{ ...SPRING.settle, duration: 0.5 }}
        />
      </div>
      <span className="shrink-0 font-mono text-[11px] font-bold tabular-nums text-white/55">
        {completion.collected} / {completion.total}
      </span>
      <span className="sr-only-number">
        {t('collection.completion', { collected: completion.collected, total: completion.total })}
      </span>
    </div>
  );
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

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
