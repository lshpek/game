import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

import { createPortal } from 'react-dom';

import { useI18n } from '../i18n';
import { trackRevealShown, trackRevealSkipped, trackRollAgain } from '../lib/analytics';
import { DURATION, EASE, SPRING, revealDuration, useReducedMotion } from '../lib/motion';
import { hapticCue } from '../lib/telegram';
import type { PlateCard, ReelFrame } from '../types';
import RarityBadge from './RarityBadge';
import PriceDisplay from './PriceDisplay';
import SimCardVisual from './SimCardVisual';
import SymbolReel from './SymbolReel';
import CollectorBioPanel from './CollectorBioPanel';
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
 * ### The staging
 *
 * ```
 * PRESS → DIM → ENTER → TRAVEL → DECELERATE → LOCK → SETTLE → RARITY → VALUE → ACTIONS
 * ```
 *
 * Each stage is a separate, timed transition rather than one long keyframe animation.
 * That is what makes the motion read as a physical object rather than as a video: a
 * rotation that accelerates on a symmetric curve and then bleeds off on a long ease-out,
 * a single spring to the lock, and a two-frame settle instead of a bounce.
 *
 * The whole sequence lives on one DOM node that is never remounted, which is what removes
 * the popping that a remount-based reveal produces inside a Telegram WebView.
 *
 * ### Performance
 *
 * Only compositor-friendly properties animate. `transform` and `opacity` everywhere; the
 * specular pass across the plate is a CSS animation on its own layer. There is no
 * animated `filter: blur()` over the object and no full-screen `backdrop-filter`, both of
 * which are the usual causes of a reveal dropping frames on a mid-range Android phone.
 *
 * Timing scales with rarity (`revealDuration`) and is always skippable.
 */

type Stage = 'press' | 'dim' | 'enter' | 'travel' | 'decelerate' | 'lock' | 'settled';

/** Rarity tiers that get the heavier, more cinematic staging. */
const CINEMATIC = new Set(['EPIC', 'LEGENDARY', 'MYTHIC', 'SECRET']);

interface Props {
  /** The already-decided collectible. `null` while a roll is in flight. */
  card: PlateCard | null;
  loading: boolean;
  /**
   * Synthetic frames for the reel, generated server-side and never persisted.
   *
   * The reel scrolls through these and settles on `card`. Nothing here decides anything:
   * the backend has already committed the result before these exist.
   */
  reel?: ReelFrame[];
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
  reel = [],
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
  const { t, lang } = useI18n();
  const reduced = useReducedMotion();
  const [stage, setStage] = useState<Stage>('press');
  const lockedRef = useRef(false);

  const rarity = (card?.rarity ?? 'COMMON').toUpperCase();
  const isCinematic = CINEMATIC.has(rarity);
  const duplicates = card?.duplicate_count ?? 0;
  /** The sale action only exists when there is genuinely something to sell. */
  const canSell = duplicates > 0 && typeof onSellDuplicates === 'function';

  const duration = revealDuration(card?.rarity);

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
    /*
     * With a reel in front of it, the object only has to settle - the reel has already
     * done the anticipation, and running the full staged sequence behind it as well would
     * put two animations on the same object and make it stutter.
     */
    const marks: Array<[Stage, number]> =
      reel.length > 0
        ? [
            ['dim', 120],
            ['enter', 420],
            ['decelerate', Math.round(duration * 0.55)],
            ['lock', Math.round(duration * 0.78)],
            ['settled', duration],
          ]
        : [
            ['dim', 90],
            ['enter', 300],
            ['travel', 520],
            ['decelerate', Math.round(duration * 0.55)],
            ['lock', Math.round(duration * 0.78)],
            ['settled', duration],
          ];
    const timers = marks.map(([next, at]) => window.setTimeout(() => setStage(next), at));
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [card, duration, reduced, reel.length]);

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
  /*
   * The readout waits for the reel. Showing a rarity while numbers are still scrolling
   * past would tell the player the answer before the reel landed on it.
   */
  const showReadout = settled && (reel.length === 0 || stage === 'settled');

  // Escape closes. A dialog the player cannot leave is a dead end in a Mini App.
  useEffect(() => {
    if (!visible) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [visible, onClose]);

  /*
   * The result's own entrance. With a reel in front of it, the object no longer needs a
   * long staged sequence - the reel *is* the anticipation - so this only runs the last
   * part: the reel has landed, and now the answer settles into place.
   */
  const focus = stage === 'dim' ? 4 : 0;
  const lift = reel.length > 0 ? 0 : stage === 'enter' ? 26 : 8;

  if (typeof document === 'undefined') return null;

  return createPortal(
    <AnimatePresence>
      {visible && (
        <motion.div
          key="reveal-root"
          className="fixed inset-0 z-[70] flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: DURATION.fade, ease: EASE.out }}
          role="dialog"
          aria-modal="true"
          aria-label={t('reveal.dialogLabel')}
          data-testid="reveal"
        >
          {/*
            The dim. A plain scrim with no backdrop-filter: blurring a full-screen layer
            behind an animating 3D object is the single most expensive thing this UI could
            do, and it is invisible at this opacity anyway. The focus effect is applied to
            the object below instead, where it is visible.
          */}
          <motion.div
            className="absolute inset-0 bg-ink-950"
            initial={{ opacity: 0 }}
            animate={{ opacity: card ? 0.96 : 0.72 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.slide, ease: EASE.out }}
            onClick={onClose}
            aria-hidden="true"
          />

          <div
            className="relative z-10 mx-auto flex max-h-full w-full max-w-[min(94%,var(--content-max))] flex-col items-center gap-[clamp(12px,3vh,20px)] overflow-y-auto overscroll-contain px-4"
            style={{
              paddingTop: 'calc(var(--tg-safe-top) + 16px)',
              paddingBottom: 'calc(var(--tg-safe-bottom) + 16px)',
            }}
            onClick={(event) => event.stopPropagation()}
          >
            {loading && !card && (
              <div className="flex flex-col items-center gap-3">
                <div className="h-7 w-7 animate-spin rounded-full border-2 border-white/15 border-t-white/70" />
                <span className="t-micro text-white/40">{t('reveal.searching')}</span>
              </div>
            )}

            {card && (
              <motion.div
                className="flex w-full flex-col items-center gap-5"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: DURATION.fade, ease: EASE.out }}
              >
                {/*
                  The object - or, before it, the reel.

                  The flow is exactly: the physical object appears, its printed number
                  area spins symbol by symbol, each position locks in turn left to right,
                  and the result is the real backend collectible. The object never leaves
                  the screen during the spin - the reels live inside its printed area.
                */}
                <SymbolReel
                  frames={reel}
                  settled={settled}
                  onSettled={() => setStage('settled')}
                  finalLabel={card.plate_text}
                  kind={card.kind ?? 'VEHICLE_PLATE'}
                  visual={card.visual}
                  plateText={card.plate_text}
                  displaySegments={card.display_segments}
                  displaySegmentGaps={card.display_segment_gaps}
                  displaySegmentKinds={card.display_segment_kinds}
                  countryCode={card.country.code}
                  letterAlphabet={card.reel_alphabets?.letters}
                  digitAlphabet={card.reel_alphabets?.digits}
                  final={
                    <motion.div
                      className="w-full"
                      initial={{ opacity: 0, rotateX: 40, y: lift, scale: 0.92 }}
                      animate={{
                        opacity: 1,
                        rotateX: 0,
                        y: 0,
                        scale: 1,
                        // Focus is a brightness falloff, not a blur: blurring this element
                        // would repaint the whole plate every frame of the entrance.
                        filter: focus ? `brightness(${1 - focus / 100})` : 'none',
                      }}
                      transition={
                        settled
                          ? { ...SPRING.settle, duration: DURATION.lock }
                          : {
                              rotateX: { duration: 0.42, ease: EASE.out },
                              y: { duration: 0.4, ease: EASE.out },
                              scale: { duration: 0.42, ease: EASE.out },
                              opacity: { duration: DURATION.fade, ease: EASE.out },
                              filter: { duration: 0.3, ease: EASE.out },
                            }
                      }
                      style={{ perspective: 1100, transformStyle: 'preserve-3d' }}
                    >
                      <motion.button
                        type="button"
                        className="block w-full"
                        onClick={onPlateClick}
                        aria-label={card.plate_text}
                        animate={
                          settled && isCinematic && !reduced
                            ? { scaleY: [1, 0.968, 1], scaleX: [1, 1.01, 1] }
                            : { scaleY: 1, scaleX: 1 }
                        }
                        transition={{ duration: 0.44, ease: EASE.lock, times: [0, 0.4, 1] }}
                      >
                        {card.kind === 'SIM_CARD' ? (
                          <SimCardVisual
                            details={card.details}
                            config={card.sim_config ?? null}
                            rarity={rarity}
                            className="mx-auto"
                          />
                        ) : (
                          <VehiclePlateVisual
                            visual={card.visual}
                            plateText={card.plate_text}
                            displaySegments={card.display_segments}
                            displaySegmentGaps={card.display_segment_gaps}
                            displaySegmentKinds={card.display_segment_kinds}
                            regionName={card.region?.name_en ?? card.region?.name_ru ?? null}
                            regionCode={card.region?.code ?? null}
                            className="mx-auto"
                            sweep={!settled && !reduced}
                          />
                        )}
                      </motion.button>
                    </motion.div>
                  }
                />

                <AnimatePresence>
                  {showReadout && (
                    <motion.div
                      key="readout"
                      className="flex w-full flex-col items-center gap-3.5 text-center"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.32, ease: EASE.out }}
                    >
                      {/* 1. Rarity */}
                      <RarityBadge rarity={rarity} size="lg" pulse={isCinematic && !reduced} />

                      {/* 2. Country, then the specific thing it is */}
                      <div className="space-y-0.5">
                        <div className="t-body font-semibold text-white/80">
                          <span aria-hidden>{card.country.flag}</span>{' '}
                          {/* The player's language, never the catalogue's. */}
                          {lang === 'ru' ? card.country.name_ru : card.country.name_en}
                        </div>
                        <div className="t-micro text-white/40">
                          {card.kind === 'SIM_CARD'
                            ? (card.details
                                ? lang === 'ru' && card.details.operator_local
                                  ? card.details.operator_local
                                  : card.details.operator
                                : t('category.sim'))
                            : // A plate prints its own country's name on itself, so for a
                              // vehicle the *printed* region name is what belongs here -
                              // but only when the plate has one at all.
                              (card.region
                                ? lang === 'ru'
                                  ? card.region.name_ru
                                  : card.region.name_en
                                : card.plate_type)}
                        </div>
                      </div>

                      {/* 3. One main value. Everything secondary belongs in Details, so
                          the reveal never dumps competing prices on the player. */}
                      {/*
                        One main value, in the player's chosen display currency. The
                        canonical figure is NUMORA; the picker changes only how it is
                        printed, never what is stored or what the roll is worth.
                      */}
                      <div className="flex flex-col items-center gap-0.5">
                        <PriceDisplay value={card.dealer_value} prefix="+" size="lg" />
                        <span className="t-micro text-white/35">
                          {t('reveal.result.numora')}
                        </span>
                      </div>

                      {/* 4. One or two traits: why this one is worth anything. */}
                      {card.reason_labels?.length ? (
                        <div className="flex flex-wrap items-center justify-center gap-1.5">
                          {card.reason_labels.slice(0, 2).map((label) => (
                            <span
                              key={label}
                              className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-white/60"
                            >
                              {label}
                            </span>
                          ))}
                        </div>
                      ) : null}

                      <CollectorBioPanel bio={card.collector_bio} />

                      {/* 5. First discovery: a status on the card, never a feed. */}
                      {isFirstDiscovery && (
                        <motion.div
                          className="rounded-2xl border border-amber-300/25 bg-amber-300/10 px-4 py-2"
                          initial={{ opacity: 0, scale: 0.96 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ duration: DURATION.slide, ease: EASE.lock }}
                        >
                          <span className="t-micro text-amber-200">
                            {t('reveal.firstDiscovery')}
                          </span>
                        </motion.div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>

                {showReadout && (
                  <motion.div
                    key="actions"
                    className="w-full space-y-2"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.26, ease: EASE.out, delay: 0.05 }}
                  >
                    {onRollAgain && (
                      <button
                        type="button"
                        className="btn-primary w-full"
                        disabled={!canRollAgain || rolling}
                        onClick={() => {
                          if (card) trackRollAgain(card.id);
                          onRollAgain?.();
                        }}
                      >
                        {rolling ? t('reveal.rolling') : t('reveal.rollAgain')}
                      </button>
                    )}

                    <div className="grid grid-cols-2 gap-2">
                      {onKeep && (
                        <button type="button" className="btn-ghost t-body" onClick={onKeep}>
                          {t('reveal.keep')}
                        </button>
                      )}
                      {onShare && (
                        <button type="button" className="btn-ghost t-body" onClick={onShare}>
                          {t('reveal.share')}
                        </button>
                      )}
                      {canSell && (
                        <button
                          type="button"
                          className="btn-ghost col-span-2 t-body"
                          onClick={onSellDuplicates}
                        >
                          {t('reveal.sellDuplicates')}
                          <PriceDisplay
                            value={card.sale_value}
                            prefix="+"
                            size="sm"
                            tone="#c9a86b"
                            readOnly
                          />
                        </button>
                      )}
                      {onOpenCollection && (
                        <button
                          type="button"
                          className="btn-ghost col-span-2 t-body"
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
                className="absolute right-4 t-micro text-white/35 transition active:scale-95"
                style={{ top: 'calc(var(--tg-safe-top) + 14px)' }}
                onClick={skip}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: DURATION.fade, ease: EASE.out, delay: 0.5 }}
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
