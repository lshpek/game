import { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';

import { EASE } from '@/lib/motion';
import { useT } from '@/i18n';
import type { PlateVisual, ReelFrame } from '@/types';
import { REEL_SECONDS, SPIN_WINDOW, symbolStops } from './reelTiming';

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

/** How many distinct symbols each column cycles through before reaching its target. */
const CYCLE = 9;

/** The letters and digits a column may show, in a fixed order so a spin reads as cycling. */
const FALLBACK_LETTERS = 'ABCDEFGHJKLMNPRSTUVWXYZ';
const FALLBACK_DIGITS = '0123456789';

/** One reel column's worth of state. */
interface Column {
  /** The character this position locks on - the real result's character. */
  target: string;
  /** The symbols it passes through before it gets there. Empty for a fixed character. */
  cycle: string[];
  /** True when the position holds a digit, which decides its symbol set. */
  digit: boolean;
  /** True when a printed group gap precedes this character. */
  gap: boolean;
  /** True when the character does not spin - a mark the plate prints as it stands. */
  fixed: boolean;
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
  countryCode,
  letterAlphabet,
  digitAlphabet,
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
  countryCode: string;
  letterAlphabet?: string;
  digitAlphabet?: string;
}) {
  const t = useT();
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
    () => buildColumns(
      plateText,
      displaySegmentKinds,
      displaySegments,
      displaySegmentGaps,
      letterAlphabet,
      digitAlphabet,
    ),
    [plateText, displaySegmentKinds, displaySegments, displaySegmentGaps, letterAlphabet, digitAlphabet],
  );
  const stops = useMemo(() => symbolStops(columns.length), [columns.length]);

  // The preview object behind the reels. It advances while the reels are still spinning,
  // so the country design keeps changing - and it freezes the instant the first column
  // locks, so the object never changes underneath a settled number.
  const preview: ReelFrame | null =
    frames.length > 0 ? frames[Math.min(frame, frames.length - 1)] ?? null : null;
  const surface = !done && preview?.country_code === countryCode ? preview.visual : visual;

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
        The physical object, with the reels inside it.

        One element carries the object's own dimensions and the reels are positioned inside
        its printed area. Keeping them in a single box is what guarantees a symbol can never
        sit outside the plate - there is no second box to drift from the first.

        While spinning, the plate's frame, border, band, mounts and finish belong to the
        *preview* frame's country recipe, so the object on screen keeps being a real plate
        from a real country and changes as the reel runs. The moment the reels lock it
        becomes the real result's, so the plate never changes under a settled number.
      */}
      {kind === 'SIM_CARD' ? (
        <SimReelSurface
          columns={columns}
          stops={stops}
          done={done}
          number={plateText}
          final={final}
        />
      ) : (
        <div className="relative mx-auto w-full max-w-full" style={{ width: objectWidth(visual) }}>
          <PlateSurface visual={surface} done={done} final={final} />
          {!done ? (
            <div
              className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center"
              data-testid="reel-columns"
            >
              <ReelColumns columns={columns} stops={stops} />
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

/** The object's own width, capped to the viewport. Never wider than the screen. */
function objectWidth(visual: PlateVisual): string {
  return `${Math.round(visual.width_mm)}px`;
}

/**
 * The plate's chrome while the reels are hot, and the real object once they
 * have locked.
 *
 * While spinning, the frame, border and finish belong to the *preview* frame's
 * country recipe - so the object on screen keeps being a real plate from a
 * real country, changing as the reel runs. The moment the reels lock, the real
 * result takes the stage: the very component the rest of the app renders a
 * collectible with, label and all, so the settled object is announced as the
 * find it is rather than as a decorative picture of one.
 */
function PlateSurface({
  visual,
  done,
  final,
}: {
  visual: PlateVisual;
  done: boolean;
  final: React.ReactNode;
}) {
  if (done) return <>{final}</>;

  const vars = {
    '--plate-radius': visual.radius,
    '--plate-border': visual.border_width,
    '--plate-border-color': visual.border,
    '--plate-bg': visual.background,
    '--plate-bg-alt': visual.background_alt,
    '--plate-rail': '3px',
    '--plate-raise': String(visual.relief ?? 0.3),
    '--plate-grain': String(visual.grain ?? 0.15),
    aspectRatio: `${visual.aspect}`,
    width: '100%',
    maxWidth: '100%',
    containerType: 'inline-size',
  } as React.CSSProperties;

  return (
    <div className="plate-frame plate-texture" style={vars} aria-hidden="true">
      <div
        className="plate-face"
        style={{ width: '100%', height: '100%', minWidth: 0, overflow: 'hidden' }}
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
  final,
}: {
  columns: Column[];
  stops: number[];
  done: boolean;
  number: string;
  final: React.ReactNode;
}) {
  return (
    <div className="relative mx-auto w-full max-w-[min(100%,320px)]">
      {done ? (
        final
      ) : (
        <>
          <SimSurfaceChrome />
          {/*
            Inside the card's printed number area: the SIM keeps its chip, its moulded edge
            and its brand, and only the number spins.
          */}
          <div
            className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center px-[26%] pt-[14%] pb-[22%]"
            data-testid="reel-columns"
          >
            <ReelColumns columns={columns} stops={stops} compact />
          </div>
        </>
      )}
      <span className="sr-only-number">{number}</span>
    </div>
  );
}

/** The SIM's physical body, without its printed number. */
function SimSurfaceChrome() {
  return (
    <div className="sim-body" aria-hidden="true">
      <span className="sim-notch" />
      <span className="sim-brand-bar" />
      <span className="sim-contact" />
      <span className="sim-pad">
        <span />
        <span />
        <span />
        <span />
      </span>
      <span className="sim-sheen" />
    </div>
  );
}

/**
 * The row of reel columns.
 *
 * A printed group gap is real spacing between columns, not a spinning character - a
 * separator that itself flailed would look broken, and a real plate separates its groups
 * with a space.
 */
function ReelColumns({
  columns,
  stops,
  compact = false,
}: {
  columns: Column[];
  stops: number[];
  compact?: boolean;
}) {
  return (
    <div
      className="flex max-w-full items-center justify-center"
      style={{
        fontFamily: 'var(--plate-font, inherit)',
        fontWeight: 700,
        fontSize: compact ? 'clamp(13px,5.2cqw,20px)' : 'clamp(11px,7.4cqw,40px)',
        letterSpacing: 'var(--plate-letter-spacing, 0.05em)',
      }}
    >
      {columns.map((column, index) => (
        <span key={index} className="flex items-center">
          {column.gap ? (
            <span className="reel-gap" aria-hidden="true" />
          ) : null}
          <ReelColumn column={column} stopAt={stops[index] ?? 0} />
        </span>
      ))}
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
 * Everything here is compositor work: one `transform`, one `opacity`, no layout, no filter,
 * no `textContent` write. A Telegram WebView on a mid-range phone runs this without dropping
 * a frame.
 */
function ReelColumn({ column, stopAt }: { column: Column; stopAt: number }) {
  // A character that does not spin - a mark the plate prints as it stands - is shown as
  // it is, and takes no part in the lock sequence.
  if (column.fixed || column.cycle.length === 0) {
    return (
      <span className="reel-column reel-column-fixed" data-testid="reel-column" aria-hidden="true">
        <span className="reel-symbol">{column.target}</span>
      </span>
    );
  }

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
          // The duration is this position's own run. Early positions finish early, later
          // ones run longer - which is exactly what sequential lock looks like, and why
          // nothing ever stops at the same moment.
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
  gaps: boolean[] = [],
  letterAlphabet = FALLBACK_LETTERS,
  digitAlphabet = FALLBACK_DIGITS,
): Column[] {
  /*
   * Expand the grouped segments back into per-character positions.
   *
   * The server sends gaps *per group* - "this group is separated from the last" - so the
   * flag has to be lifted to the first character of each group after the first. That flag
   * is what keeps a reel faithful to the printed layout: `AB 12345` reels as two groups,
   * with a real gap between them, instead of seven columns butted together.
   */
  const chars: Array<{ char: string; kind: string; gap: boolean }> = [];
  if (segments.length > 0) {
    segments.forEach((segment, index) => {
      const kind = kinds[index] ?? 'digit';
      const gap = index > 0 && (gaps[index] ?? true);
      for (const char of segment) {
        chars.push({ char, kind, gap: chars.length > 0 && gap });
      }
    });
  } else {
    let pending = false;
    for (const char of text) {
      if (char === ' ') {
        pending = true;
        continue;
      }
      chars.push({
        char,
        kind: /\d/.test(char) ? 'digit' : 'letter',
        gap: pending && chars.length > 0,
      });
      pending = false;
    }
  }

  return chars.map(({ char, kind, gap }) => {
    // A position holding a non-alphanumeric mark (a separator the server already
    // excluded, a `+` on a phone number) keeps its own character and does not spin.
    const digit = kind === 'digit' || kind === 'mixed' || kind === 'region' ? /\d/.test(char) : false;
    const alphabet = digit ? digitAlphabet : letterAlphabet;
    const spinner = alphabet.includes(char);
    if (!spinner) {
      return { target: char, cycle: [], digit, gap, fixed: true };
    }
    // The cycle walks the target's own alphabet forward to land on it, so the reel never
    // has to jump backwards at the end - a backwards jump is the tell that an odometer is
    // faked rather than driven.
    const start = alphabet.indexOf(char);
    const offset = start >= 0 ? start : 0;
    const cycle: string[] = [];
    for (let step = 1; step <= CYCLE; step += 1) {
      cycle.push(alphabet[(offset + step) % alphabet.length] ?? char);
    }
    return { target: char, cycle, digit, gap, fixed: false };
  });
}

export { CYCLE, FALLBACK_DIGITS, FALLBACK_LETTERS, REEL_SECONDS, SPIN_WINDOW, symbolStops };
export default SymbolReel;
