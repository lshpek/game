import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import clsx from 'clsx';
import { CollectibleVisual, resolveKind } from '@/components/CollectibleVisual';
import { RarityBadge } from '@/components/RarityBadge';
import { ValueCounter } from '@/components/ValueCounter';
import { haptic, hapticSuccess } from '@/lib/telegram';
import { RARITY_COLORS } from '@/lib/format';
import { useT } from '@/i18n';
import type { CollectibleKind, PlateCard, PlateRollResult, Rarity } from '@/types';

/**
 * The cinematic reveal - the single most important moment in the game.
 *
 * The sequence is deliberately staged so the player watches a *collectible*, never
 * the request that produced it:
 *
 *   press → darken → chamber → fast previews → decelerate → country flash →
 *   lock → impact → rarity → hero object → value → traits → extras → actions
 *
 * Three rules this component never breaks:
 *
 * 1. **The animation never decides anything.** The server has already returned the
 *    result; the reveal only presents it. A player who skips, or who has
 *    `prefers-reduced-motion` set, sees the same collectible and the same rewards.
 * 2. **The final frame is built for a vertical clip.** Rarity on top, the object
 *    huge in the centre, country and value underneath, actions last - so a screen
 *    recording of this screen is the share asset.
 * 3. **It always terminates.** Every stage is timer-driven and the whole thing is
 *    skippable, so a roll can never leave the screen stuck in "rolling forever".
 */

export type RevealStage =
  | 'idle'
  | 'darken'
  | 'chamber'
  | 'preview'
  | 'decelerate'
  | 'country'
  | 'lock'
  | 'impact'
  | 'rarity'
  | 'hero'
  | 'value'
  | 'traits'
  | 'actions';

const SEQUENCE: RevealStage[] = [
  'darken',
  'chamber',
  'preview',
  'decelerate',
  'country',
  'lock',
  'impact',
  'rarity',
  'hero',
  'value',
  'traits',
  'actions',
];

/** Stage durations in ms. The preview stage is deliberately long and busy. */
const STAGE_MS: Record<Exclude<RevealStage, 'idle' | 'actions'>, number> = {
  darken: 220,
  chamber: 380,
  preview: 1250,
  decelerate: 420,
  country: 460,
  lock: 200,
  impact: 260,
  rarity: 420,
  hero: 260,
  value: 900,
  traits: 420,
};

/** How often a preview swaps while cycling, in ms. */
const PREVIEW_INTERVAL = 110;
/** How often a preview swaps while decelerating, in ms. */
const DECEL_INTERVAL = 240;

/** Fake previews shown while cycling. Never presented as a result. */
const CYCLE_COUNTRIES = ['RUS', 'USA', 'JPN', 'DEU', 'GBR', 'ARE', 'FRA', 'ITA', 'KAZ', 'CAN', 'ARM', 'GEO'];
const CYCLE_SERIALS = ['777', '012', '404', '088', '101', '777', '666', '313', '246', '909', '404', '515'];
const CYCLE_KINDS: CollectibleKind[] = ['VEHICLE_PLATE', 'SIM_CARD'];

interface RevealProps {
  result: PlateRollResult | null;
  /** Null while the request is in flight - the anticipation belongs to the roll. */
  pending: boolean;
  onClose: () => void;
  onShare?: () => void;
  onSell?: () => void;
  onViewCollection?: () => void;
}

/** A cheap, plausible placeholder used only while cycling. */
function buildCycleCard(source: PlateCard, index: number): PlateCard {
  const country = CYCLE_COUNTRIES[index % CYCLE_COUNTRIES.length] ?? 'RUS';
  const serial = CYCLE_SERIALS[index % CYCLE_SERIALS.length] ?? '777';
  const kind: CollectibleKind = CYCLE_KINDS[index % CYCLE_KINDS.length] ?? 'VEHICLE_PLATE';
  const text =
    kind === 'SIM_CARD'
      ? `+${index % 90 + 1} ${serial} ${serial} ${serial}`
      : `${String.fromCharCode(65 + (index % 26))}${serial}${serial}AA`;
  return {
    ...source,
    plate_text: text,
    display_segments: text.split(' '),
    kind,
    plate_type: kind === 'SIM_CARD' ? 'SIM' : 'VEHICLE',
    country: { ...source.country, code: country, flag: '' },
  };
}

export function Reveal({ result, pending, onClose, onShare, onSell, onViewCollection }: RevealProps) {
  const t = useT();
  const reduced = useReducedMotion();
  const [stage, setStage] = useState<RevealStage>('idle');
  const [cycle, setCycle] = useState(0);
  const timer = useRef<number | null>(null);
  const cycleTimer = useRef<number | null>(null);

  const plate = result?.plate ?? null;
  const rarity = (result?.rarity ?? 'COMMON') as Rarity;
  const accent = RARITY_COLORS[rarity] ?? RARITY_COLORS.COMMON;
  const category = plate ? resolveKind(plate) : 'VEHICLE_PLATE';

  const isCinematic = rarity === 'MYTHIC' || rarity === 'SECRET' || rarity === 'LEGENDARY';

  const clearTimers = useCallback(() => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    if (cycleTimer.current !== null) window.clearTimeout(cycleTimer.current);
    timer.current = null;
    cycleTimer.current = null;
  }, []);

  /** Jump straight to the final frame. Always available - the result is known. */
  const skip = useCallback(() => {
    clearTimers();
    setStage('actions');
  }, [clearTimers]);

  // Drive the stage machine.
  useEffect(() => {
    if (!result && !pending) {
      setStage('idle');
      return undefined;
    }
    if (!pending && !result) return undefined;

    clearTimers();
    if (pending) {
      setStage('darken');
      return undefined;
    }

    if (reduced) {
      // Reduced motion still gets a legible reveal: stages collapse, the object
      // and the numbers appear immediately and nothing moves.
      setStage('actions');
      return undefined;
    }

    let index = 0;
    const advance = () => {
      const next = SEQUENCE[index] ?? 'actions';
      setStage(next);
      index += 1;
      if (index < SEQUENCE.length) {
        timer.current = window.setTimeout(advance, STAGE_MS[next as Exclude<RevealStage, 'idle' | 'actions'>]);
      }
    };
    setStage('darken');
    timer.current = window.setTimeout(advance, STAGE_MS.darken);
    return clearTimers;
  }, [result, pending, reduced, clearTimers]);

  // Cycle the preview object while the reveal is spinning.
  useEffect(() => {
    if (stage !== 'preview' && stage !== 'decelerate') return undefined;
    const interval = stage === 'preview' ? PREVIEW_INTERVAL : DECEL_INTERVAL;
    cycleTimer.current = window.setInterval(() => setCycle((value) => value + 1), interval);
    return () => {
      if (cycleTimer.current !== null) window.clearInterval(cycleTimer.current);
      cycleTimer.current = null;
    };
  }, [stage]);

  // Haptics: one on the press, one on the lock, a stronger burst on a cinematic.
  useEffect(() => {
    if (stage === 'lock') {
      haptic('heavy');
    }
    if (stage === 'rarity' && isCinematic) {
      hapticSuccess();
    }
  }, [stage, isCinematic]);

  useEffect(() => () => clearTimers(), [clearTimers]);

  const showActions = stage === 'actions';
  const revealStage = stage !== 'idle' && stage !== 'darken' ? stage : null;
  const cycling = stage === 'preview' || stage === 'decelerate';

  const shownCard: PlateCard | null = useMemo(() => {
    if (!plate) return null;
    if (cycling) return buildCycleCard(plate, cycle);
    return plate;
  }, [plate, cycling, cycle]);

  if (!pending && !result) return null;

  const closing = () => {
    haptic('light');
    onClose();
  };

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-ink-950/92 p-4 backdrop-blur-md"
        initial={{ opacity: 0 }}
        animate={{ opacity: pending || stage !== 'idle' ? 1 : 0 }}
        exit={{ opacity: 0 }}
        role="dialog"
        aria-modal="true"
        aria-label={t('result.aria')}
        data-testid="reveal"
        data-stage={stage}
        data-rarity={rarity}
        onClick={revealStage && !showActions ? skip : undefined}
      >
        {/* Cinematic backdrop: a soft pool of light behind the object. */}
        <motion.span
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background: `radial-gradient(circle at 50% 42%, ${accent}2e, transparent 62%)`,
            opacity: revealStage ? 1 : 0,
          }}
          animate={isCinematic && stage !== 'idle' && !reduced ? { opacity: [0.7, 1, 0.7] } : { opacity: 1 }}
          transition={{ duration: 2.4, repeat: isCinematic ? Infinity : 0 }}
        />

        <div className="relative flex w-full max-w-md flex-col items-center gap-5">
          {/* Top: rarity. Kept above everything so a clip always reads. */}
          <AnimatePresence>
            {(stage === 'rarity' || stage === 'hero' || stage === 'value' || stage === 'traits' || showActions) && plate ? (
              <motion.div
                key="rarity"
                initial={{ opacity: 0, y: -14, scale: 0.9 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ type: 'spring', stiffness: 320, damping: 18 }}
              >
                <RarityBadge rarity={rarity} size={isCinematic ? 'lg' : 'md'} />
              </motion.div>
            ) : null}
          </AnimatePresence>

          {/* Extras: first discovery, new country, secret. */}
          <AnimatePresence>
            {plate && (stage === 'hero' || stage === 'value' || stage === 'traits' || showActions) ? (
              <motion.div
                key="extras"
                className="flex flex-wrap items-center justify-center gap-2"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.12 }}
              >
                {result?.is_first_discovery ? <ExtraBadge label={t('reveal.result.firstDiscovery')} tone="gold" /> : null}
                {result?.is_new_country ? <ExtraBadge label={t('reveal.result.newCountry')} tone="accent" /> : null}
                {result?.is_duplicate ? <ExtraBadge label={t('reveal.result.duplicate')} tone="muted" /> : null}
                {plate.is_secret ? <ExtraBadge label={t('reveal.result.secret')} tone="secret" /> : null}
              </motion.div>
            ) : null}
          </AnimatePresence>

          {/* Centre: the object. */}
          <div className="relative flex w-full items-center justify-center">
            {pending ? (
              <Chamber reduced={Boolean(reduced)} accent={accent} />
            ) : shownCard ? (
              <motion.div
                key={cycling ? `cycle-${cycle}` : 'final'}
                className="w-full"
                animate={
                  cycling && !reduced
                    ? { scale: [0.97, 1.02], opacity: [0.75, 1] }
                    : { scale: 1, opacity: 1 }
                }
                transition={
                  cycling && !reduced
                    ? { duration: 0.16, repeat: Infinity, ease: 'easeInOut' }
                    : { type: 'spring', stiffness: 240, damping: 20 }
                }
              >
                <CollectibleVisual
                  collectible={shownCard}
                  size={showActions || stage === 'hero' || stage === 'value' || stage === 'traits' ? 'hero' : 'lg'}
                  accent={accent}
                  reveal={stage === 'lock' || stage === 'impact' || showActions}
                  still={cycling}
                />
              </motion.div>
            ) : null}

            {/* Impact flash on the lock. */}
            {stage === 'impact' && !reduced ? (
              <motion.span
                aria-hidden
                className="pointer-events-none absolute inset-0 rounded-2xl"
                style={{ background: `radial-gradient(circle, ${accent}cc, transparent 65%)` }}
                initial={{ opacity: 0.9, scale: 0.8 }}
                animate={{ opacity: 0, scale: 1.25 }}
                transition={{ duration: 0.42, ease: 'easeOut' }}
              />
            ) : null}
          </div>

          {/* Country flash just before the lock. */}
          <AnimatePresence>
            {stage === 'country' && plate && !reduced ? (
              <motion.div
                key="country"
                className="pointer-events-none absolute inset-x-0 top-1/3 flex flex-col items-center gap-1"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 1.06 }}
                transition={{ duration: 0.24 }}
              >
                <span className="text-5xl leading-none" aria-hidden>
                  {plate.country.flag}
                </span>
                <span
                  className="text-xl font-black uppercase tracking-[0.3em]"
                  style={{ color: accent }}
                >
                  {plate.country.code}
                </span>
              </motion.div>
            ) : null}
          </AnimatePresence>

          {/* Under the object: country, then the reward. */}
          <div className="flex min-h-[68px] flex-col items-center gap-2 text-center">
            {plate && (stage === 'hero' || stage === 'value' || stage === 'traits' || showActions) ? (
              <motion.div
                key="country-line"
                className="flex items-center gap-2 text-sm font-bold uppercase tracking-[0.22em] text-white/70"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <span aria-hidden>{plate.country.flag}</span>
                <span>
                  {category === 'SIM_CARD' ? t('category.sim') : t('category.plate')}
                </span>
                <span className="h-3 w-px bg-white/15" />
                <span className="text-white/50">{plate.country.code}</span>
              </motion.div>
            ) : null}

            {result && (stage === 'value' || stage === 'traits' || showActions) ? (
              <motion.div
                key="value"
                className="flex flex-col items-center gap-1"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <ValueCounter
                  value={result.numora_awarded}
                  label={t('reveal.result.numora')}
                  className="text-2xl font-black tracking-tight text-emerald-300"
                />
                <span className="text-[10px] uppercase tracking-[0.24em] text-white/35">
                  {t('reveal.result.collectorValue')} {plate ? `${plate.currency_symbol}${plate.collector_value.toLocaleString()}` : ''}
                </span>
              </motion.div>
            ) : null}
          </div>

          {/* Trait chips. */}
          {plate && (stage === 'traits' || showActions) && plate.traits.length ? (
            <motion.div
              key="traits"
              className="flex max-w-[min(92vw,26rem)] flex-wrap items-center justify-center gap-1.5"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
            >
              {plate.reason_labels.slice(0, 4).map((label) => (
                <span
                  key={label}
                  className="rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em]"
                  style={{ borderColor: `${accent}55`, color: `${accent}`, background: `${accent}14` }}
                >
                  {label}
                </span>
              ))}
            </motion.div>
          ) : null}

          {/* Actions last, and never more than four. */}
          {showActions ? (
            <motion.div
              key="actions"
              className="mt-1 grid w-full grid-cols-4 gap-2"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <ActionButton onClick={closing}>{t('reveal.result.keep')}</ActionButton>
              <ActionButton onClick={() => { onShare?.(); }} accent={accent}>
                {t('reveal.result.share')}
              </ActionButton>
              <ActionButton onClick={() => { onSell?.(); }}>
                {t('reveal.result.sell')}
              </ActionButton>
              <ActionButton onClick={() => { onViewCollection?.(); }}>
                {t('reveal.result.collection')}
              </ActionButton>
            </motion.div>
          ) : (
            <button
              type="button"
              onClick={skip}
              className="mt-1 rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-white/40 transition hover:text-white/70"
              data-testid="reveal-skip"
            >
              {t('reveal.skip')}
            </button>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

/** The anticipation object: a dark chamber that breathes while the roll runs. */
function Chamber({ reduced, accent }: { reduced: boolean; accent: string }) {
  return (
    <div
      className="relative flex h-40 w-full items-center justify-center overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-b from-[#0d1017] to-[#04050a]"
      data-testid="reveal-chamber"
    >
      <motion.span
        aria-hidden
        className="absolute inset-x-0 h-24"
        style={{ background: `linear-gradient(180deg, transparent, ${accent}22, transparent)` }}
        animate={reduced ? undefined : { y: [-40, 40, -40] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.span
        aria-hidden
        className="h-10 w-10 rounded-full border-2"
        style={{ borderColor: accent }}
        animate={reduced ? undefined : { scale: [0.7, 1.15, 0.7], opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 1.3, repeat: Infinity, ease: 'easeInOut' }}
      />
      <span className="absolute bottom-4 text-[10px] font-bold uppercase tracking-[0.3em] text-white/30">
        hunting
      </span>
    </div>
  );
}

function ExtraBadge({ label, tone }: { label: string; tone: 'gold' | 'accent' | 'muted' | 'secret' }) {
  const styles: Record<string, string> = {
    gold: 'border-amber-300/50 bg-amber-300/10 text-amber-200',
    accent: 'border-sky-300/40 bg-sky-300/10 text-sky-200',
    muted: 'border-white/15 bg-white/5 text-white/60',
    secret: 'border-fuchsia-400/50 bg-fuchsia-400/10 text-fuchsia-200',
  };
  return (
    <span
      className={clsx(
        'rounded-md border px-2 py-1 text-[10px] font-black uppercase tracking-[0.2em]',
        styles[tone],
      )}
    >
      {label}
    </span>
  );
}

function ActionButton({
  children,
  onClick,
  accent,
}: {
  children: React.ReactNode;
  onClick: () => void;
  accent?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="min-h-[44px] rounded-xl border border-white/12 bg-white/[0.06] px-2 py-2.5 text-[11px] font-bold uppercase tracking-[0.14em] text-white/80 transition active:scale-[0.97]"
      style={accent ? { borderColor: `${accent}55`, color: accent } : undefined}
    >
      {children}
    </button>
  );
}

export default Reveal;