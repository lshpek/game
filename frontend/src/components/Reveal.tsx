import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { createPortal } from 'react-dom';

import { useI18n } from '../i18n';
import { trackRevealShown, trackRevealSkipped, trackRollAgain } from '../lib/analytics';
import { rarityColor } from '../lib/format';
import { DURATION, EASE, SPRING, revealDuration, useReducedMotion } from '../lib/motion';
import { playRevealFanfare } from '../lib/sound';
import { hapticCue } from '../lib/telegram';
import type { PlateCard, ReelFrame } from '../types';
import RarityBadge from './RarityBadge';
import PriceDisplay from './PriceDisplay';
import SimCardVisual from './SimCardVisual';
import SymbolReel from './SymbolReel';
import CollectorBioPanel from './CollectorBioPanel';
import VehiclePlateVisual from './VehiclePlateVisual';

type Stage = 'press' | 'dim' | 'enter' | 'travel' | 'decelerate' | 'lock' | 'settled';

const CINEMATIC = new Set(['EPIC', 'LEGENDARY', 'MYTHIC', 'SECRET']);
const HIGH_RARITY = new Set(['RARE', 'EPIC', 'LEGENDARY', 'MYTHIC', 'SECRET']);

const SPARK_OFFSETS = [
  { x: -115, y: -55, delay: 0.02, size: 6 },
  { x: 120, y: -48, delay: 0.08, size: 5 },
  { x: -95, y: 52, delay: 0.12, size: 4 },
  { x: 108, y: 58, delay: 0.05, size: 6 },
  { x: -35, y: -76, delay: 0.15, size: 5 },
  { x: 42, y: 74, delay: 0.1, size: 4 },
];

interface Props {
  card: PlateCard | null;
  loading: boolean;
  reel?: ReelFrame[];
  onClose: () => void;
  onRollAgain?: () => void;
  canRollAgain?: boolean;
  rolling?: boolean;
  onKeep?: () => void;
  onShare?: () => void;
  onSellDuplicates?: () => void;
  onOpenCollection?: () => void;
  onPlateClick?: () => void;
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
  const fanfareRef = useRef(false);

  const rarity = (card?.rarity ?? 'COMMON').toUpperCase();
  const tierColor = rarityColor(rarity);
  const isCinematic = CINEMATIC.has(rarity);
  const isHighRarity = HIGH_RARITY.has(rarity);
  const duplicates = card?.duplicate_count ?? 0;
  const canSell = duplicates > 0 && typeof onSellDuplicates === 'function';

  const duration = revealDuration(card?.rarity);
  const hasReel = reel.length > 0;

  useEffect(() => {
    lockedRef.current = false;
    fanfareRef.current = false;
    if (!card) {
      setStage('press');
      return;
    }
    if (reduced) {
      setStage('settled');
      return;
    }
    setStage('press');
    const marks: Array<[Stage, number]> = hasReel
      ? [
          ['dim', 120],
          ['enter', 420],
          ['decelerate', Math.round(duration * 0.55)],
          ['lock', Math.round(duration * 0.78)],
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
  }, [card, duration, hasReel, reduced]);

  useEffect(() => {
    if (!card) return;
    if (stage === 'enter') hapticCue('roll');
    if (stage === 'settled') {
      trackRevealShown(card.id, rarity);
      if (!fanfareRef.current) {
        fanfareRef.current = true;
        playRevealFanfare(rarity);
      }
    }
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
  const showReadout = settled && (reel.length === 0 || stage === 'settled');

  useEffect(() => {
    if (!visible) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [visible, onClose]);

  const settleFromReel = useCallback(() => {
    setStage((previous) => (previous === 'settled' ? previous : 'settled'));
  }, []);

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
          {/* Ambient theatre scrim + rarity spotlight cone */}
          <motion.div
            className="absolute inset-0 bg-ink-950"
            style={{
              backgroundImage: settled
                ? `radial-gradient(85% 55% at 50% 28%, ${tierColor}33 0%, transparent 68%)`
                : 'radial-gradient(70% 45% at 50% 30%, rgba(125,162,255,0.14) 0%, transparent 65%)',
            }}
            initial={{ opacity: 0 }}
            animate={{ opacity: card ? 0.96 : 0.78 }}
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
              <div className="flex flex-col items-center gap-3.5 py-12">
                <div className="relative grid h-14 w-14 place-items-center">
                  <div className="absolute inset-0 animate-ping rounded-full border border-brass/30" />
                  <div className="h-9 w-9 animate-spin rounded-full border-2 border-white/15 border-t-brass" />
                </div>
                <span className="eyebrow text-brass-soft">{t('reveal.searching')}</span>
              </div>
            )}

            {card && (
              <motion.div
                className="flex w-full flex-col items-center gap-5"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: DURATION.fade, ease: EASE.out }}
              >
                <div className="relative flex w-full flex-col items-center justify-center py-2">
                  {/* Expanding rarity shockwave & halo on settlement */}
                  {settled && !reduced && isHighRarity && (
                    <motion.div
                      aria-hidden="true"
                      className="pointer-events-none absolute h-44 w-72 rounded-full blur-2xl"
                      style={{
                        background: `radial-gradient(circle, ${tierColor}66 0%, ${tierColor}18 55%, transparent 75%)`,
                      }}
                      initial={{ scale: 0.65, opacity: 0 }}
                      animate={{ scale: [0.85, 1.18, 1.04], opacity: [0, 0.9, 0.6] }}
                      transition={{ duration: 0.75, ease: EASE.out }}
                    />
                  )}

                  {/* Luminous spark burst on EPIC / LEGENDARY / MYTHIC / SECRET */}
                  {settled && !reduced && isCinematic && (
                    <div aria-hidden="true" className="pointer-events-none absolute inset-0 flex items-center justify-center">
                      {SPARK_OFFSETS.map((spark, index) => (
                        <motion.span
                          key={index}
                          className="absolute rounded-full"
                          style={{
                            width: spark.size,
                            height: spark.size,
                            background: tierColor,
                            boxShadow: `0 0 10px ${tierColor}`,
                          }}
                          initial={{ x: 0, y: 0, scale: 0, opacity: 1 }}
                          animate={{
                            x: spark.x,
                            y: spark.y,
                            scale: [0, 1.35, 0],
                            opacity: [1, 1, 0],
                          }}
                          transition={{
                            duration: 0.85,
                            delay: spark.delay,
                            ease: EASE.out,
                          }}
                        />
                      ))}
                    </div>
                  )}

                  <SymbolReel
                    frames={reel}
                    settled={settled}
                    onSettled={settleFromReel}
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
                              ? { scaleY: [1, 0.962, 1], scaleX: [1, 1.018, 1] }
                              : { scaleY: 1, scaleX: 1 }
                          }
                          transition={{ duration: 0.44, ease: EASE.lock, times: [0, 0.4, 1] }}
                        >
                          {card.kind === 'SIM_CARD' ? (
                            <SimCardVisual
                              details={card.details}
                              config={card.sim_config ?? null}
                              rarity={rarity}
                              animate={settled}
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
                              rarity={rarity}
                              className="mx-auto"
                              sweep={! reduced}
                            />
                          )}
                        </motion.button>
                      </motion.div>
                    }
                  />
                </div>

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

                      {/* 2. Country & region/operator */}
                      <div className="space-y-0.5">
                        <div className="t-body font-bold text-white/90">
                          <span aria-hidden>{card.country.flag}</span>{' '}
                          {lang === 'ru' ? card.country.name_ru : card.country.name_en}
                        </div>
                        <div className="t-micro text-white/50">
                          {card.kind === 'SIM_CARD'
                            ? card.details
                              ? lang === 'ru' && card.details.operator_local
                                ? card.details.operator_local
                                : card.details.operator
                              : t('category.sim')
                            : card.region
                              ? lang === 'ru'
                                ? card.region.name_ru
                                : card.region.name_en
                              : card.plate_type}
                        </div>
                      </div>

                      {/* 3. Main NUMORA value */}
                      <div className="glass flex flex-col items-center gap-0.5 px-5 py-2.5">
                        <PriceDisplay value={card.dealer_value} prefix="+" size="lg" />
                        <span className="t-micro text-white/45">{t('reveal.result.numora')}</span>
                      </div>

                      {/* 4. Trait chips */}
                      {card.reason_labels?.length ? (
                        <div className="flex flex-wrap items-center justify-center gap-1.5">
                          {card.reason_labels.slice(0, 3).map((label) => (
                            <span
                              key={label}
                              className="rounded-full border border-brass/30 bg-brass/10 px-3 py-1 text-[11px] font-semibold text-brass-soft"
                            >
                              ✦ {label}
                            </span>
                          ))}
                        </div>
                      ) : null}

                      <CollectorBioPanel bio={card.collector_bio} />

                      {/* 5. First discovery golden seal */}
                      {isFirstDiscovery && (
                        <motion.div
                          className="flex items-center gap-2 rounded-2xl border border-amber-300/40 bg-gradient-to-r from-amber-400/20 via-amber-300/10 to-amber-400/20 px-4 py-2 shadow-brass"
                          initial={{ opacity: 0, scale: 0.94 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ duration: DURATION.slide, ease: EASE.lock }}
                        >
                          <span aria-hidden="true" className="text-sm">
                            🏆
                          </span>
                          <span className="t-micro font-bold text-amber-200">
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
                          className="btn-ghost col-span-2 border-brass/30 bg-brass/10 t-body text-brass-soft hover:border-brass/50"
                          onClick={onSellDuplicates}
                        >
                          {t('reveal.sellDuplicates')}
                          <PriceDisplay
                            value={card.sale_value}
                            prefix="+"
                            size="sm"
                            tone="#d4af6a"
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

                    {duplicates === 0 && (
                      <p className="pt-1 text-center text-[11px] text-white/35">
                        {t('reveal.noDuplicates')}
                      </p>
                    )}
                  </motion.div>
                )}
              </motion.div>
            )}

            {card && !settled && (
              <motion.button
                type="button"
                className="absolute right-4 rounded-full border border-white/15 bg-white/[0.06] px-3 py-1 t-micro text-white/60 transition hover:text-white active:scale-95"
                style={{ top: 'calc(var(--tg-safe-top) + 14px)' }}
                onClick={skip}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: DURATION.fade, ease: EASE.out, delay: 0.4 }}
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
