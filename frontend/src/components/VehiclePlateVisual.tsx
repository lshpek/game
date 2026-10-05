import { useMemo } from 'react';

import { formatCoins } from '../lib/format';
import type { PlateCard, PlateVisual, PlateSegmentKind } from '../types';

/**
 * A real vehicle registration plate, rendered from the server's country recipe.
 *
 * The component owns *how a plate is drawn* - a metal frame, a bevelled face, mounting
 * bolts, a country identifier band, a separated region block and a controlled
 * reflection. It owns **nothing** about how any country looks: proportions, surface
 * colours, typography, letter spacing, digit sizes, the band, the region placement and
 * the bolt count all arrive in `visual` from the backend. Adding a country therefore
 * needs no change here at all.
 *
 * What it deliberately does not do: use a giant flag emoji as an identifier. The country
 * code is printed small inside a proper side band - the EU blue band with the country's
 * own alpha-2 code where the country uses one.
 */

interface Props {
  visual: PlateVisual;
  plateText: string;
  displaySegments?: string[];
  displaySegmentGaps?: boolean[];
  displaySegmentKinds?: PlateSegmentKind[];
  regionName?: string | null;
  /** Multiplies the printed size. 1 renders at the recipe's natural size. */
  scale?: number;
  className?: string;
  /** Accessible description; defaults to the plate text itself. */
  ariaLabel?: string;
}

/** A CSS custom-property bag, typed once. */
type StyleVars = Record<string, string | number>;

const SEGMENT_CLASS: Record<PlateSegmentKind, string> = {
  letter: 'opacity-95',
  digit: '',
  region: '',
  mixed: '',
  mark: 'opacity-60',
};

/**
 * Normalise a segment list.
 *
 * The stored groups plus their gaps reconstruct `plateText` exactly. When a payload
 * predates the grouped segments (or a caller passes plain text) we fall back to
 * character runs, so the plate still prints its real value rather than a guess.
 */
function useSegments(
  plateText: string,
  displaySegments?: string[],
  displaySegmentGaps?: boolean[],
  displaySegmentKinds?: PlateSegmentKind[],
): Array<{ text: string; gap: boolean; kind: PlateSegmentKind }> {
  return useMemo(() => {
    if (displaySegments?.length) {
      return displaySegments.map((text, index) => ({
        text,
        gap: displaySegmentGaps?.[index] ?? index > 0,
        kind: displaySegmentKinds?.[index] ?? 'digit',
      }));
    }
    const out: Array<{ text: string; gap: boolean; kind: PlateSegmentKind }> = [];
    let cursor = 0;
    for (const char of plateText) {
      if (char === ' ') {
        cursor = 1;
        continue;
      }
      const kind: PlateSegmentKind = /\d/.test(char) ? 'digit' : 'letter';
      const previous = out[out.length - 1];
      if (previous && !cursor && previous.kind === kind) {
        previous.text += char;
      } else {
        out.push({ text: char, gap: cursor === 1, kind });
        cursor = 0;
      }
    }
    return out;
  }, [plateText, displaySegments, displaySegmentGaps, displaySegmentKinds]);
}

export default function VehiclePlateVisual({
  visual,
  plateText,
  displaySegments,
  displaySegmentGaps,
  displaySegmentKinds,
  regionName,
  scale = 1,
  className = '',
  ariaLabel,
}: Props) {
  const segments = useSegments(
    plateText,
    displaySegments,
    displaySegmentGaps,
    displaySegmentKinds,
  );

  const recipeVars = useMemo<StyleVars>(
    () => ({
      '--plate-radius': visual.radius,
      '--plate-border': visual.border_width,
      '--plate-border-color': visual.border,
      '--plate-bg': visual.background,
      '--plate-bg-alt': visual.background_alt,
      '--plate-text': visual.text,
      '--plate-font': visual.font_stack,
      '--plate-letter-spacing': visual.letter_spacing,
      '--plate-gap': visual.group_gap,
      '--plate-digit-weight': visual.digit_weight,
      '--plate-band-color': visual.band_color ?? '#003399',
      '--plate-band-text-color': visual.band_text_color,
      '--plate-header-color': visual.header_color || visual.muted,
      '--plate-sheen': String(visual.gloss ? Math.min(1, visual.sheen) : 0.12),
      '--plate-bolt-color': visual.mount_color,
      '--plate-rail': `${Math.max(2, Math.round(4 * scale))}px`,
    }),
    [visual, scale],
  );

  const frameVars = useMemo<StyleVars>(
    () => ({
      ...recipeVars,
      aspectRatio: `${visual.aspect}`,
      width: `${Math.round(520 * scale)}px`,
      maxWidth: '100%',
    }),
    [recipeVars, visual.aspect, scale],
  );

  const faceVars = useMemo<StyleVars>(
    () => ({
      width: '100%',
      height: '100%',
      gap: `${visual.band_position === 'left' || visual.band_position === 'right' ? 0 : 1}%`,
      justifyContent:
        visual.band_position === 'right'
          ? 'flex-end'
          : visual.band_position === 'left'
            ? 'flex-start'
            : 'center',
      paddingLeft: visual.band_position === 'left' ? '1.5%' : '3%',
      paddingRight: visual.band_position === 'right' ? '1.5%' : '3%',
    }),
    [visual.band_position],
  );

  const hasBand =
    visual.band_position !== 'none' &&
    Boolean(visual.band_color) &&
    (Boolean(visual.band_text) || visual.band_flag || visual.band_stars);
  const bandWidth = `${Math.max(3, visual.band_width * 100).toFixed(1)}%`;

  /**
   * Printed type size.
   *
   * Derived from how much has to fit and expressed in `cqw`, so a short US serial and a
   * long EU serial both end up with the same *relative* weight on their own plate
   * instead of the same pixel size. The numeric base is kept for the secondary blocks
   * (region, header), which are sized as a fraction of it.
   */
  const { fontSize, baseFontPx } = useMemo(() => {
    const longest = Math.max(1, plateText.replace(/\s/g, '').length);
    const min = Math.round(9 * scale);
    const max = Math.round(58 * scale);
    return {
      baseFontPx: max,
      fontSize: `clamp(${min}px, ${(100 / (longest * 0.72)).toFixed(2)}cqw, ${max}px)`,
    };
  }, [plateText, scale]);

  const header = resolveHeader(visual, regionName);
  const bolts = resolveBolts(visual.bolts);

  return (
    <div
      className={`plate-frame plate-texture ${className}`}
      style={{ ...frameVars, containerType: 'inline-size' } as React.CSSProperties}
      role="img"
      aria-label={ariaLabel ?? plateText}
    >
      <div
        className="plate-face"
        style={faceVars as React.CSSProperties}
      >
        {hasBand && visual.band_position === 'left' && (
          <div
            className="plate-band"
            style={{ width: bandWidth }}
            aria-hidden="true"
          >
            {visual.band_stars && <span className="plate-stars" />}
            {/* A national emblem, kept small: a plate identifier is a printed mark,
                not a flag pasted over the object. */}
            {visual.band_flag && <span style={{ fontSize: '0.6em' }}>★</span>}
            {visual.band_text && (
              <span style={{ fontSize: '0.72em' }}>{visual.band_text}</span>
            )}
          </div>
        )}

        {header && (
          <div
            className="plate-header"
            style={{
              top: visual.header_align === 'center' ? '7%' : '6%',
              textAlign: (visual.header_align === 'left'
                ? 'left'
                : visual.header_align === 'right'
                  ? 'right'
                  : 'center') as React.CSSProperties['textAlign'],
              padding: '0 4%',
              fontSize: header.fontSize,
            }}
          >
            {header.text}
          </div>
        )}

        {visual.emblem && (
          <span
            className="plate-emblem"
            style={{
              bottom: '6%',
              left: '4%',
              fontSize: '0.42em',
              color: visual.muted,
            }}
            aria-hidden="true"
          >
            {emblemGlyph(visual.emblem)}
          </span>
        )}

        <div
          className="plate-print"
          style={{ fontSize, gap: visual.group_gap }}
        >
          {segments.map((segment, index) => (
            <span
              key={`${segment.text}-${index}`}
              className={SEGMENT_CLASS[segment.kind]}
              style={{
                fontSize:
                  segment.kind === 'digit'
                    ? `${visual.digit_scale}em`
                    : `${visual.letter_scale}em`,
                fontWeight: segment.kind === 'letter' ? 600 : undefined,
                letterSpacing: segment.gap ? undefined : '0.02em',
              }}
            >
              {/* The gap is a real character, not just spacing: the printed object must
                  read back as exactly `plateText` for assistive tech and for copying. */}
              {segment.gap ? ' ' : null}
              {segment.text}
            </span>
          ))}
        </div>

        {usesRegionBlock(segments, visual.region_position) && regionName && (
          <div
            className="plate-region-block"
            style={{
              fontSize: `${Math.round(0.52 * baseFontPx)}px`,
              minWidth: '11%',
            }}
            aria-hidden="true"
          >
            <span>{regionName}</span>
          </div>
        )}

        {hasBand && visual.band_position === 'right' && (
          <div
            className="plate-band"
            style={{ width: bandWidth }}
            aria-hidden="true"
          >
            {visual.band_stars && <span className="plate-stars" />}
            {visual.band_text && (
              <span style={{ fontSize: '0.66em' }}>{visual.band_text}</span>
            )}
          </div>
        )}
      </div>

      {bolts.map((position, index) => (
        <span
          key={index}
          className="plate-bolt"
          style={position}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

/**
 * Whether the region is already printed as part of the serial.
 *
 * Some layouts put the region inside the serial (``KZ``'s region template), others keep
 * it in a separate right-hand compartment (``RU``). Printing it twice would be wrong, so
 * the compartment is only drawn when the serial does not already carry it.
 */
function usesRegionBlock(
  segments: Array<{ kind: PlateSegmentKind }>,
  regionPosition: string,
): boolean {
  return (
    regionPosition === 'right' && !segments.some((segment) => segment.kind === 'region')
  );
}

/**
 * The printed header.
 *
 * `header_source: "region"` is what gives a US plate its state-specific identity: the
 * header carries the state's own name, so no two states read the same. Everything else
 * uses the country's own printed wordmark.
 */
function resolveHeader(
  visual: PlateVisual,
  regionName?: string | null,
): { text: string; fontSize: string } | null {
  if (visual.header_source === 'region') {
    if (!regionName) return null;
    return { text: regionName, fontSize: '0.42em' };
  }
  if (visual.header_source === 'none' || !visual.header) return null;
  return { text: visual.header, fontSize: '0.34em' };
}

/** Bolt positions as percentages of the frame. Four on a car plate, two on a US plate. */
function resolveBolts(count: number): Array<Record<string, string>> {
  if (count === 2) {
    return [
      { left: '1.2%', top: '50%', transform: 'translateY(-50%)' },
      { right: '1.2%', top: '50%', transform: 'translateY(-50%)' },
    ];
  }
  if (count !== 4) return [];
  return [
    { left: '1.2%', top: '14%' },
    { right: '1.2%', top: '14%' },
    { left: '1.2%', bottom: '14%' },
    { right: '1.2%', bottom: '14%' },
  ];
}

/**
 * A small printed corner mark.
 *
 * Drawn as text rather than an emoji so it stays monochrome and follows the plate's own
 * type colour instead of looking like a sticker.
 */
function emblemGlyph(emblem: string): string {
  switch (emblem) {
    case 'flag':
      return '★';
    case 'green_mark':
      return '品';
    case 'state_tag':
      return '';
    case 'crest':
      return '◆';
    default:
      return '';
  }
}

/** Convenience wrapper so callers can render straight from a collectible payload. */
export function PlateObject({
  card,
  scale = 1,
  className = '',
  showValue = false,
}: {
  card: PlateCard;
  scale?: number;
  className?: string;
  showValue?: boolean;
}) {
  return (
    <div className={`flex flex-col items-center gap-2 ${className}`}>
      <VehiclePlateVisual
        visual={card.visual}
        plateText={card.plate_text}
        displaySegments={card.display_segments}
        displaySegmentGaps={card.display_segment_gaps}
        displaySegmentKinds={card.display_segment_kinds}
        regionName={card.region?.name_en ?? card.region?.name_ru ?? null}
        scale={scale}
      />
      {showValue && (
        <span className="text-xs font-semibold text-white/70">
          {card.currency_symbol}
          {formatCoins(card.collector_value)}
        </span>
      )}
    </div>
  );
}
export { VehiclePlateVisual };