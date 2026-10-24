import { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';

import { EASE } from '@/lib/motion';
import { playColumnLock, playReelTick } from '@/lib/sound';
import { hapticCue } from '@/lib/telegram';
import { useT } from '@/i18n';
import type { PlateVisual, ReelFrame } from '@/types';
import { REEL_SECONDS, SPIN_WINDOW, symbolStops } from './reelTiming';

const CYCLE = 9;
const FALLBACK_LETTERS = 'ABCDEFGHJKLMNPRSTUVWXYZ';
const FALLBACK_DIGITS = '0123456789';

interface Column {
  target: string;
  cycle: string[];
  digit: boolean;
  gap: boolean;
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
  frames: ReelFrame[];
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
  const [lockedCount, setLockedCount] = useState(0);

  const columns = useMemo(
    () =>
      buildColumns(
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
    setLockedCount(0);
    reported.current = false;

    const totalSteps = Math.ceil((REEL_SECONDS * 1000) / 90);
    const timers: number[] = [
      ...Array.from({ length: totalSteps }, (_, index) =>
        window.setTimeout(() => {
          setFrame(index);
          if (index % 2 === 0) playReelTick(index);
        }, index * 90),
      ),
      ...stops.map((stopMs, colIndex) =>
        window.setTimeout(() => {
          setLockedCount((prev) => Math.max(prev, colIndex + 1));
          playColumnLock(colIndex, columns.length);
          hapticCue('tap');
        }, Math.max(80, Math.round(stopMs * 0.96))),
      ),
      window.setTimeout(() => {
        setDone(true);
        if (!reported.current) {
          reported.current = true;
          onSettled?.();
        }
      }, REEL_SECONDS * 1000),
    ];
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [columns.length, onSettled, settled, stops]);

  if (columns.length === 0 || settled) return <>{final}</>;

  const progressRatio = columns.length > 0 ? lockedCount / columns.length : 0;

  return (
    <div
      className="relative flex w-full flex-col items-center gap-3"
      role="status"
      aria-live="polite"
      aria-label={done ? finalLabel : t('reel.spinning')}
      data-testid="symbol-reel"
    >
      {/* Escalating anticipation glow as columns lock in one by one */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -inset-6 -z-10 rounded-full blur-2xl transition-opacity duration-300"
        style={{
          opacity: 0.25 + progressRatio * 0.55,
          background:
            progressRatio > 0.65
              ? 'radial-gradient(circle, rgba(251,191,36,0.45) 0%, rgba(168,85,247,0.22) 50%, transparent 72%)'
              : 'radial-gradient(circle, rgba(125,162,255,0.38) 0%, rgba(212,175,106,0.18) 55%, transparent 72%)',
        }}
      />

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

function objectWidth(visual: PlateVisual): string {
  return `${Math.round(visual.width_mm)}px`;
}

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
    '--plate-rail': '3.5px',
    '--plate-raise': String(visual.relief ?? 0.35),
    '--plate-grain': String(visual.grain ?? 0.16),
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
        <span className="plate-bolts" />
        <span className="plate-gloss" />
      </div>
    </div>
  );
}

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

function SimSurfaceChrome() {
  return (
    <div className="sim-body" aria-hidden="true">
      <span className="sim-notch" />
      <span className="sim-brand-bar" />
      <span className="sim-cutlines" />
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
        fontFamily: 'var(--plate-font, "Oswald", "Roboto Condensed", inherit)',
        fontWeight: 700,
        fontSize: compact ? 'clamp(13px,5.2cqw,20px)' : 'clamp(11px,7.4cqw,40px)',
        letterSpacing: 'var(--plate-letter-spacing, 0.05em)',
      }}
    >
      {columns.map((column, index) => (
        <span key={index} className="flex items-center">
          {column.gap ? <span className="reel-gap" aria-hidden="true" /> : null}
          <ReelColumn column={column} stopAt={stops[index] ?? 0} />
        </span>
      ))}
    </div>
  );
}

function ReelColumn({ column, stopAt }: { column: Column; stopAt: number }) {
  if (column.fixed || column.cycle.length === 0) {
    return (
      <span className="reel-column reel-column-fixed" data-testid="reel-column" aria-hidden="true">
        <span className="reel-symbol">{column.target}</span>
      </span>
    );
  }

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

export function buildColumns(
  text: string,
  kinds: string[],
  segments: string[],
  gaps: boolean[] = [],
  letterAlphabet = FALLBACK_LETTERS,
  digitAlphabet = FALLBACK_DIGITS,
): Column[] {
  const chars: Array<{ char: string; kind: string; gap: boolean }> = [];
  if (segments.length > 0) {
    segments.forEach((segment, index) => {
      const kind = kinds[index] ?? 'digit';
      const gap = index > 0 && (gaps[index] ?? true);
      let firstCharacter = true;
      for (const char of segment) {
        chars.push({ char, kind, gap: chars.length > 0 && gap && firstCharacter });
        firstCharacter = false;
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
    const digit = kind === 'digit' || kind === 'mixed' || kind === 'region' ? /\d/.test(char) : false;
    const alphabet = digit ? digitAlphabet : letterAlphabet;
    const spinner = alphabet.includes(char);
    if (!spinner) {
      return { target: char, cycle: [], digit, gap, fixed: true };
    }
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
