import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import { useT } from '../i18n';
import { trackRevealShown, trackRevealSkipped, trackRollAgain } from '../lib/analytics';
import { formatCoins } from '../lib/format';
import { DURATION, EASE, SPRING, revealDuration, useReducedMotion } from '../lib/motion';
import { hapticCue } from '../lib/telegram';
import type { PlateCard } from '../types';
import RarityBadge from './RarityBadge';
import SimCardVisual from './SimCardVisual';
import VehiclePlateVisual from './VehiclePlateVisual';

/**
 * The one authoritative result experience.
 *
 * There is a single reveal in NUMORA and this is it. Every screen that shows a result
 * shows it through this component, so a roll looks and behaves identically whether it
 * was started from the hunt screen, a deep link or a challenge.
 *
 * **This component never decides anything.** The backend has already drawn the
 * collectible, its rarity, its value and its rewards before this mounts. It presents
 * them and nothing else. Specifically, there is:
 *
 * * no fake probability and no RNG;
 * * no cycling through plausible numbers;
 * * no "almost had it" flicker or near-miss;
 * * no result that changes while the animation plays;
 * * no decorative particles that could be mistaken for a result.
 *
 * **The staging.**
 * `PRESS → DIM → ENTER → BUILD → DECELERATE → LOCK → SETTLE → RARITY → VALUE → ACTIONS`
 *
 * Each stage is a separate, timed transition instead of one long keyframe animation.
 * That is what makes the motion read as a physical object rather than as a video: a
 * rotation that accelerates on a symmetric curve and then bleeds off on a long ease-out,
 * a single spring to the lock, and a two-frame settle instead of a bounce.
 *
 * The whole sequence lives on one DOM node that is never remounted, which is what removes
 * the popping that a remount-based reveal produces inside a Telegram WebView.
 *
 * Timing scales with rarity (`revealDuration`) and is always skippable.
 */

type Stage = 'press' | 'dim' | 'enter' | 'build' | 'decelerate' | 'lock' | 'settled';

/** Rarity tiers that get the heavier, more cinematic staging. */
const CINEMATIC = new Set(['EPIC', 'LEGENDARY', 'MYTHIC', 'SECRET']);

interface Props {
  /** The already-decided collectible. `null` while a roll is in flight. */
  card: PlateCard | null;
  loading: boolean;
  onClose: () => void;
  /** Start the next roll without closing the result: roll, reveal, roll again. */
  onRollAgain?: () => void;
  canRollAgain?: boolean;
  rolling?: boolean;
  onKeep?: () => void;
  onShare?: () => void;
  onSellDuplicates?: () => void;
  onOpenCollection?: () => void;
  /** Called when the player taps the object itself. */
  onPlateClick?: () => void;
  /** First discovery is a property of the roll, not of the card. */
  isFirstDiscovery?: boolean;
}

export default function Reveal({
  card,
  loading,
  onClose,
  onRollAgain,
  canRollAgain = false,
  rolling = false,
  onKeep,
  onShare,
  onSellDuplicates,
  onOpenCollection,
  onPlateClick,
  isFirstDiscovery = false,
}: Props) {
  const t = useT();
  const reduced = useReducedMotion();
  const [stage, setStage] = useState<Stage>('press');
  const lockedRef = useRef(false);

  const duration = useMemo(() => revealDuration(card?.rarity), [card?.rarity]);
  const rarity = (card?.rarity ?? 'COMMON').toUpperCase();
  const isCinematic = CINEMATIC.has(rarity);
  const duplicates = card?.duplicate_count ?? 0;
  /** The sale action only exists when there is genuinely something to sell. */
  const canSell = duplicates > 0 && typeof onSellDuplicates === 'function';

  // Stage timing: one timer chain, fully cancelled on every change, so a fast sequence
  // of rolls can never leave a stale stage running against a new card.
  useEffect(() => {
    lockedRef.current = false;
    if (!card) {
      setStage('press');
      return;
    }
    if (reduced) {
      // Reduced motion keeps the whole read-out order, just without the travel.
      setStage('settled');
      return;
    }
    setStage('press');
    const marks: Array<[Stage, number]> = [
      ['dim', DURATION.press * 1000],
      ['enter', DURATION.press * 1000 + 240],
      ['build', DURATION.press * 1000 + 520],
      ['decelerate', duration * 0.56],
      ['lock', duration * 0.8],
      ['settled', duration],
    ];
    const timers = marks.map(([next, at]) =>
      window.setTimeout(() => setStage(next), Math.round(at)),
    );
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [card, duration, reduced]);

  // Haptics: roll on entry, one escalating cue at the lock. Never more than two per
  // reveal, so a legendary find feels different without feeling like a machine gun.
  useEffect(() => {
    if (!card) return;
    if (stage === 'enter') hapticCue('roll');
    if (stage === 'settled') trackRevealShown(card.id, rarity);
    if (stage === 'lock' && !lockedRef.current) {
      lockedRef.current = true;
      if (isCinematic) hapticCue('legendary');
      else if (rarity === 'RARE' || rarity === 'EPIC') hapticCue('rare');
      else hapticCue('lock');
    }
  }, [stage, card, rarity, isCinematic]);

  const skip = () => {
    if (card) trackRevealSkipped(card.id);
    setStage('settled');
  };

  const settled = stage === 'settled' || reduced;
  const visible = Boolean(card) || loading;

  // The spin is one monotonic rotation whose angle is a function of the stage, so it
  // accelerates and then decelerates without ever reversing or jittering.
  const spin = stage === 'build' ? 200 : stage === 'decelerate' ? 430 : 0;
  const blur = stage === 'enter' ? 7 : stage === 'build' ? 3.5 : stage === 'decelerate' ? 1 : 0;

  if (typeof document === 'undefined') return null;

  return createPortal(
    <AnimatePresence>
      {visible && (
        <motion.div
          key="reveal-root"
          className="fixed inset-0 z-[70] flex items-center justify-center px-5"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18, ease: EASE.out }}
          role="dialog"
          aria-modal="true"
          aria-label={t('reveal.dialogLabel')}
        >
          {/* The dim. Blur is deliberately capped at 3px: a heavier blur is the single
              biggest cause of dropped frames in a Telegram WebView. */}
          <motion.div
            className="absolute inset-0 bg-ink-950"
            initial={{ opacity: 0 }}
            animate={{ opacity: card ? 0.93 : 0.6 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.26, ease: EASE.out }}
            style={{ backdropFilter: 'blur(3px)' }}
            onClick={onClose}
            aria-hidden="true"
          />

          <div
            className="relative z-10 flex max-h-full w-full max-w-md flex-col items-center gap-6 overflow-y-auto py-10"
            onClick={(event) => event.stopPropagation()}
          >
            {loading && !card && (
              <div className="flex flex-col items-center gap-3">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-white/70" />
                <span className="text-[11px] uppercase tracking-[0.22em] text-white/40">
                  {t('reveal.searching')}
                </span>
              </div>
            )}

            {card && (
              <motion.div
                className="flex w-full flex-col items-center gap-5"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2, ease: EASE.out }}
              >
                {/* The object. A single persistent node: never remounted, never
                    teleported, so the motion is continuous frame to frame. */}
                <motion.div
                  className="w-full"
                  initial={{ opacity: 0, rotateX: 58, scale: 0.9 }}
                  animate={
                    settled
                      ? { opacity: 1, rotateX: 0, rotate: 0, scale: 1 }
                      : { opacity: 1, rotateX: 0, rotate: spin, scale: 1 }
                  }
                  transition={
                    settled
                      ? { ...SPRING.settle, duration: DURATION.lock }
                      : {
                          rotate: { duration: 0.5, ease: EASE.continuous },
                          scale: { duration: 0.42, ease: EASE.out },
                          opacity: { duration: 0.24, ease: EASE.out },
                        }
                  }
                  style={{
                    filter: reduced ? 'none' : `blur(${blur}px)`,
                    perspective: 900,
                    transformStyle: 'preserve-3d',
                  }}
                >
                  <motion.button
                    type="button"
                    className="block w-full"
                    onClick={onPlateClick}
                    aria-label={card.plate_text}
                    animate={
                      settled && isCinematic && !reduced
                        ? { scaleY: [1, 0.965, 1], scaleX: [1, 1.012, 1] }
                        : { scaleY: 1, scaleX: 1 }
                    }
                    transition={{ duration: 0.46, ease: EASE.lock, times: [0, 0.4, 1] }}
                  >
                    {card.kind === 'SIM_CARD' ? (
                      <SimCardVisual details={card.details} rarity={rarity} className="mx-auto" />
                    ) : (
                      <VehiclePlateVisual
                        visual={card.visual}
                        plateText={card.plate_text}
                        displaySegments={card.display_segments}
                        displaySegmentGaps={card.display_segment_gaps}
                        displaySegmentKinds={card.display_segment_kinds}
                        regionName={card.region?.name_en ?? card.region?.name_ru ?? null}
                        className="mx-auto"
                      />
                    )}
                  </motion.button>
                </motion.div>

                <AnimatePresence>
                  {settled && (
                    <motion.div
                      key="readout"
                      className="flex w-full flex-col items-center gap-4 text-center"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.34, ease: EASE.out }}
                    >
                      {/* 1. Rarity */}
                      <RarityBadge rarity={rarity} size="lg" pulse={isCinematic && !reduced} />

                      {/* 2. Country, then the specific thing it is */}
                      <div className="space-y-0.5">
                        <div className="text-sm font-semibold tracking-wide text-white/80">
                          {card.country.flag} {card.country.name_en.toUpperCase()}
                        </div>
                        <div className="text-[11px] uppercase tracking-[0.2em] text-white/40">
                          {card.kind === 'SIM_CARD'
                            ? card.details?.operator
                            : (card.region?.name_en ?? card.plate_type)}
                        </div>
                      </div>

                      {/* 3. One main value. Everything secondary belongs in Details, so
                          the reveal never dumps competing prices on the player. */}
                      <div className="space-y-1">
                        <div className="number-display text-4xl text-emerald-300">
                          +{formatCoins(card.dealer_value)}
                        </div>
                        <div className="text-[10px] uppercase tracking-[0.2em] text-white/40">
                          NUMORA
                        </div>
                      </div>

                      {/* 4. One or two traits: why this one is worth anything. */}
                      {card.reason_labels?.length ? (
                        <div className="flex flex-wrap items-center justify-center gap-2">
                          {card.reason_labels.slice(0, 2).map((label) => (
                            <span
                              key={label}
                              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-medium text-white/60"
                            >
                              {label}
                            </span>
                          ))}
                        </div>
                      ) : null}

                      {/* 5. First discovery: a status on the card, never a feed. */}
                      {isFirstDiscovery && (
                        <motion.div
                          className="rounded-2xl border border-amber-300/25 bg-amber-300/10 px-4 py-2"
                          initial={{ opacity: 0, scale: 0.96 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ duration: 0.32, ease: EASE.lock }}
                        >
                          <span className="text-[11px] font-bold uppercase tracking-[0.22em] text-amber-200">
                            {t('reveal.firstDiscovery')}
                          </span>
                        </motion.div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>

                {settled && (
                  <motion.div
                    key="actions"
                    className="w-full space-y-2.5"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.28, ease: EASE.out, delay: 0.06 }}
                  >
                    {onRollAgain && (
                      <button
                        type="button"
                        className="btn-primary w-full text-base"
                        disabled={!canRollAgain || rolling}
                        onClick={() => {
                          if (card) trackRollAgain(card.id);
                          onRollAgain?.();
                        }}
                      >
                        {rolling ? t('reveal.rolling') : t('reveal.rollAgain')}
                      </button>
                    )}

                    <div className="grid grid-cols-2 gap-2.5">
                      {onKeep && (
                        <button type="button" className="btn-ghost text-sm" onClick={onKeep}>
                          {t('reveal.keep')}
                        </button>
                      )}
                      {onShare && (
                        <button type="button" className="btn-ghost text-sm" onClick={onShare}>
                          {t('reveal.share')}
                        </button>
                      )}
                      {canSell && (
                        <button
                          type="button"
                          className="btn-ghost col-span-2 text-sm"
                          onClick={onSellDuplicates}
                        >
                          {t('reveal.sellDuplicates')}
                          <span className="text-emerald-300">
                            +{formatCoins(card.sale_value)}
                          </span>
                        </button>
                      )}
                      {onOpenCollection && (
                        <button
                          type="button"
                          className="btn-ghost col-span-2 text-sm"
                          onClick={onOpenCollection}
                        >
                          {t('reveal.collection')}
                        </button>
                      )}
                    </div>

                    {/* When there is nothing to sell, say why instead of showing a
                        button that would be refused. */}
                    {duplicates === 0 && (
                      <p className="pt-1 text-center text-[11px] text-white/30">
                        {t('reveal.noDuplicates')}
                      </p>
                    )}
                  </motion.div>
                )}
              </motion.div>
            )}

            {/* Skip: present, reachable, deliberately quiet. */}
            {card && !settled && (
              <motion.button
                type="button"
                className="absolute right-4 top-4 rounded-full px-3 py-1.5 text-[11px] uppercase tracking-[0.18em] text-white/35 transition hover:text-white/70"
                onClick={skip}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.24, ease: EASE.out, delay: 0.6 }}
              >
                {t('reveal.skip')}
              </motion.button>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
export { Reveal };