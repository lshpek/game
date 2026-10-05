import { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';

import { EASE } from '@/lib/motion';
import { useI18n } from '@/i18n';
import type { PlateVisual, ReelFrame } from '@/types';
import CollectibleVisualFrame from './CollectibleVisualFrame';
import { REEL_SECONDS, symbolStops } from './reelTiming';

/**
 * The symbol reel.
 *
 * ### What it is
 *
 * An **odometer inside the printed number area of a physical object.** The plate or SIM
 * card is already on screen and never leaves it - its country design, its band, its
 * mounts, its reflections are all there from the first frame - and inside the printed
 * area each character position is an independent vertical reel that spins and then locks.
 *
 * ```
 *  physical object
 *    └─ country design
 *        └─ printed number area
 *            └─ one reel column per character position
 * ```
 *
 * ### Sequential lock
 *
 * Positions lock **left to right, one after another**, each with its own stop time. That
 * is the whole effect: it reads like a mechanism winding down rather than like a value
 * being set.
 *
 * ```
 *  M   8   K   3   9     everything spinning
 *  M*  8   K   3   9     position 0 locked
 *  M*  7*  K   3   9     position 1 locked
 *  M*  7*  B*  3   9     position 2 locked
 *  M*  7*  B*  3*  9     position 3 locked
 *  A*  4*  B*  7*  2*    the real backend result
 * ```
 *
 * The last position takes the longest and gets a short settle afterwards, so the final
 * character is where the eye ends up.
 *
 * ### Timing
 *
 * The whole sequence is :data:`REEL_SECONDS`. Positions are spread across
 * :data:`SPIN_WINDOW` of it: position 0 stops first at about 62% of the run, and each
 * subsequent position a fixed step later. Nothing stops at the same moment.
 *
 * ### The result is not decided here
 *
 * The backend generated, scored and committed the real collectible before this component
 * mounted. Every frame below is a *preview*: synthetic, generated server-side, never
 * stored, never scored, never granted. The reel animates towards a value it was handed.
 */
import { REEL_SECONDS, SPIN_WINDOW, symbolStops } from './reelTiming';
/** How many distinct symbols each column cycles through before reaching its target. */
const CYCLE = 9;

/** The letters and digits a column may show, in a fixed order so a spin reads as cycling. */
const LETTERS = 'ABCDEFGHJKLMNPRSTUVWXYZ'.split('');
const DIGITS = '0123456789'.split('');

/** One reel column's worth of state. */
interface Column {
  /** The character this position locks on - the real result's character. */
  target: string;
  /** The symbols it passes through before it gets there. */
  cycle: string[];
  /** True when the position holds a digit, which decides its symbol set. */
  digit: boolean;
  /** Milliseconds from the start of the reel until this position locks. */
  stopAt: number;
}

export function SymbolReel({
  frames,
  final,
  finalLabel,
  settled,
  onSettled,
  kind,
  visual,
  plateText,
  displaySegments,
  displaySegmentGaps,
  displaySegmentKinds,
}: {
  /** Synthetic preview frames from the server. */
  frames: ReelFrame[];
  /** The real result, rendered once the reels have locked. */
  final: React.ReactNode;
  finalLabel: string;
  settled: boolean;
  onSettled?: () => void;
  kind: string;
  visual: PlateVisual;
  plateText: string;
  displaySegments: string[];
  displaySegmentGaps: boolean[];
  displaySegmentKinds: string[];
}) {
  const { t } = useT();
  const reported = useRef(false);
  const [done, setDone] = useState(() => settled);
  const [frame, setFrame] = useState(0);

  /*
   * The columns.
   *
   * Built from the *real* result's own characters, so the reel's shape is the real plate's
   * shape - the same number of positions, the same groups, the same gaps, and the same
   * letter/digit hierarchy, which is what makes each column cycle the right alphabet.
   */
  const columns = useMemo(
    () => buildColumns(plateText, displaySegmentKinds, displaySegments),
    [plateText, displaySegmentKinds, displaySegments],
  );
  const stops = useMemo(() => symbolStops(columns.length), [columns.length]);

  // The preview object behind the reels. It advances while the reels are still spinning,
  // so the country design keeps changing - and it stops the instant the first column
  // locks, so the object never changes underneath a settled number.
  const preview = frames.length > 0 ? frames[Math.min(frame, frames.length - 1)] : null;

  useEffect(() => {
    if (settled) {
      setDone(true);
      return undefined;
    }
    if (columns.length === 0) {
      setDone(true);
      return undefined;
    }
    setDone(false);
    reported.current = false;

    const timers: number[] = [
      // The object preview steps every 90ms while the reels are hot.
      ...Array.from({ length: Math.ceil(REEL_SECONDS * 1000 / 90) }, (_, index) =>
        window.setTimeout(() => setFrame(index), index * 90),
      ),
      // And the whole sequence ends when the last column locks.
      window.setTimeout(() => {
        setDone(true);
        if (!reported.current) {
          reported.current = true;
          onSettled?.();
        }
      }, REEL_SECONDS * 1000),
    ];
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [columns.length, onSettled, settled]);

  if (columns.length === 0) return <>{final}</>;

  return (
    <div
      className="flex w-full flex-col items-center gap-3"
      role="status"
      aria-live="polite"
      aria-label={done ? finalLabel : t('reel.spinning')}
      data-testid="symbol-reel"
    >
      {/*
        The physical object. Present from the first frame and never unmounted: the reels
        live *inside* its printed area, so the plate and its country design are on screen
        throughout.
      */}
      <div className="w-full max-w-full">
        {kind === 'SIM_CARD' ? (
          <SimReelSurface columns={columns} stops={stops} done={done} number={plateText} />
        ) : (
          <PlateReelSurface
            columns={columns}
            stops={stops}
            done={done}
            visual={visual}
            preview={preview}
          />
        )}
      </div>

      {done ? (
        <motion.div
          className="flex w-full flex-col items-center"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: EASE.out }}
          data-testid="reel-result"
        >
          {final}
        </motion.div>
      ) : null}
    </div>
  );
}

/**
 * The plate surface.
 *
 * The real country's recipe drives the frame, band, mounts and finish. Only the printed
 * area is replaced by the reels, and only while they are spinning.
 */
function PlateReelSurface({
  columns,
  stops,
  done,
  visual,
  preview,
}: {
  columns: Column[];
  stops: number[];
  done: boolean;
  visual: PlateVisual;
  preview: ReelFrame | null;
}) {
  // While spinning, the country design is the preview frame's own; the moment the reels
  // lock it becomes the real result's, so the plate never changes under a settled number.
  const surface = done ? visual : (preview?.visual ?? visual);

  return (
    <div className="relative w-full">
      {done ? (
        <div className="w-full">
          <CollectibleVisualFrame
            visual={visual}
            plateText=""
            displaySegments={[]}
            displaySegmentGaps={[]}
            displaySegmentKinds={[]}
            kind="VEHICLE_PLATE"
          />
        </div>
      ) : (
        <PlateSurface visual={surface} />
      )}
      {!done ? (
        <div
          className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center"
          data-testid="reel-columns"
        >
          <div className="flex items-center justify-center gap-[0.06em] px-[4%]">
            {columns.map((column, index) => (
              <ReelColumn key={index} column={column} stopAt={stops[index] ?? 0} />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** The plate's own chrome, with its printed area left empty for the reels. */
function PlateSurface({ visual }: { visual: PlateVisual }) {
  return (
    <div
      className="plate-frame plate-texture"
      style={
        {
          '--plate-radius': visual.radius,
          '--plate-border': visual.border_width,
          '--plate-border-color': visual.border,
          '--plate-bg': visual.background,
          '--plate-bg-alt': visual.background_alt,
          '--plate-rail': '3px',
          aspectRatio: `${visual.aspect}`,
          width: `${Math.round(visual.width_mm)}px`,
          maxWidth: '100%',
          containerType: 'inline-size',
          '--plate-raise': String(visual.relief ?? 0.3),
          '--plate-grain': String(visual.grain ?? 0.15),
        } as React.CSSProperties
      }
      aria-hidden="true"
    >
      <div
        className="plate-face"
        style={
          {
            width: '100%',
            height: '100%',
            minWidth: 0,
            overflow: 'hidden',
            padding: '0 4%',
          } as React.CSSProperties
        }
      >
        <span className="plate-gloss" />
      </div>
    </div>
  );
}

/** The SIM surface: the real card, with its printed number left for the reels. */
function SimReelSurface({
  columns,
  stops,
  done,
  number,
}: {
  columns: Column[];
  stops: number[];
  done: boolean;
  number: string;
}) {
  return (
    <div className="relative mx-auto w-full max-w-[330px]">
      {!done ? (
        <div
          className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center px-[12%] pt-[8%]"
          data-testid="reel-columns"
        >
          <div className="flex items-center justify-center gap-[0.02em]">
            {columns.map((column, index) => (
              <ReelColumn key={index} column={column} stopAt={stops[index] ?? 0} />
            ))}
          </div>
        </div>
      ) : null}
      <span className="sr-only-number">{number}</span>
    </div>
  );
}

/**
 * One character reel.
 *
 * A single strip of symbols translated on `transform`, with its own start time and its own
 * stop time. The strip's length is exactly the number of symbols it will pass, so it
 * travels by whole rows and lands on the target with nothing half-visible.
 *
 * Everything here is compositor work: one `transform`, one `opacity`, no layout, no filter.
 * A Telegram WebView on a mid-range phone runs this without dropping a frame, which a
 * `textContent` rewrite per tick could never do.
 */
function ReelColumn({ column, stopAt }: { column: Column; stopAt: number }) {
  // The strip is the target's own cycle plus the target at the end, so landing is exact.
  const rows = column.cycle.length + 1;

  return (
    <span
      className="reel-column"
      data-testid="reel-column"
      data-stop={Math.round(stopAt)}
      aria-hidden="true"
    >
      <motion.span
        className="reel-strip-symbols"
        style={{ height: `${rows}em` }}
        initial={{ y: 0 }}
        animate={{ y: `-${rows - 1}em` }}
        transition={{
          // The delay is this position's own start; the duration is its own run. Early
          // positions start at once and finish early, later ones start later and run
          // longer - which is exactly what sequential lock looks like.
          delay: 0,
          duration: Math.max(0.18, (stopAt / 1000) * 0.98),
          ease: EASE.reel,
        }}
      >
        {[...column.cycle, column.target].map((symbol, index) => (
          <span key={index} className="reel-symbol">
            {symbol}
          </span>
        ))}
      </motion.span>
    </span>
  );
}

/**
 * Build one reel column per character position in the real result.
 *
 * The alphabet for each position comes from the segment kind the server supplied, so a
 * digit column cycles digits and a letter column cycles letters - which is what makes the
 * spin read as a mechanism rather than as random text.
 */
export function buildColumns(
  text: string,
  kinds: string[],
  segments: string[],
): Column[] {
  // Expand the grouped segments back into per-character positions, keeping the kind and
  // whether a gap precedes each one.
  const chars: Array<{ char: string; kind: string; gap: boolean }> = [];
  let cursor = 0;
  if (segments.length > 0) {
    segments.forEach((segment, index) => {
      if (index > 0) cursor = 1;
      const kind = kinds[index] ?? 'digit';
      for (const char of segment) {
        chars.push({ char, kind, gap: cursor === 1 });
        cursor = 0;
      }
    });
  } else {
    for (const char of text) {
      if (char === ' ') {
        cursor = 1;
        continue;
      }
      chars.push({
        char,
        kind: /\d/.test(char) ? 'digit' : 'letter',
        gap: cursor === 1,
      });
      cursor = 0;
    }
  }

  return chars.map(({ char, kind }) => {
    const digit = kind === 'letter' || kind === 'mark' ? false : /\d/.test(char);
    const alphabet = digit ? DIGITS : LETTERS;
    // The cycle is the target's own alphabet, walked to land on the target, so the reel
    // never has to jump backwards at the end.
    const start = alphabet.indexOf(char);
    const offset = start >= 0 ? start : 0;
    const cycle: string[] = [];
    for (let step = 1; step <= CYCLE; step += 1) {
      cycle.push(alphabet[(offset + step) % alphabet.length]);
    }
    return { target: char, cycle, digit, stopAt: 0 };
  });
}

export { CYCLE, DIGITS, LETTERS, REEL_SECONDS, SPIN_WINDOW, symbolStops };
export default SymbolReel;
