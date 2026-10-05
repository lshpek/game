import { useMemo } from 'react';

import { formatCoins } from '../lib/format';
import type { PlateCard, PlateVisual, PlateSegmentKind } from '../types';

/**
 * A real vehicle registration plate, rendered from the server's country recipe.
 *
 * The component owns *how a plate is drawn* - a metal frame, a bevelled face, mounting
 * hardware, a country identifier band, a separated region compartment and a controlled
 * reflection. It owns **nothing** about how any country looks: the real physical size,
 * the surface colours, typography, letter spacing, digit sizes, the band, the region
 * compartment and the mounting hardware all arrive in `visual` from the backend. Adding
 * a country therefore needs no change here at all.
 *
 * ### The physical model
 *
 * A plate is a pressed metal rectangle with a printed face. Seven layers, in order:
 *
 * 1. **Frame** - the metal rim the plate is pressed into, with a highlight along its top
 *    edge and a dark line along the bottom.
 * 2. **Face** - the printed field, with an inner bevel top and bottom.
 * 3. **Grain** - a very low-contrast horizontal texture, so a large light field is not
 *    flat paper.
 * 4. **Wear** - three hairline scratches. Real plates are used.
 * 5. **Print** - the serial, its groups, raised lettering.
 * 6. **Gloss** - one controlled diagonal reflection whose strength comes from the recipe.
 * 7. **Edge** - a clean pressed-metal rim with no decorative mounting circles.
 *
 * Order matters: the gloss sits *over* the print because that is how a reflective face
 * behaves, and the wear sits under it for the same reason.
 *
 * ### Proportions
 *
 * `visual.aspect` is the server's `width_mm / height_mm` for the country's real format -
 * 4.64 for the Russian 520x112 plate, 4.73 for an EU long plate, 2.01 for a US plate.
 * The renderer never invents a ratio, because a plate at the wrong ratio is the single
 * clearest tell that it is a card with text on it rather than a physical object.
 */

interface Props {
  visual: PlateVisual;
  plateText: string;
  displaySegments?: string[];
  displaySegmentGaps?: boolean[];
  displaySegmentKinds?: PlateSegmentKind[];
  regionName?: string | null;
  /** The region's own code, which is what a plate actually prints. */
  regionCode?: string | null;
  /** Multiplies the printed size. 1 renders at the recipe's natural size. */
  scale?: number;
  className?: string;
  /** Accessible description; defaults to the plate text itself. */
  ariaLabel?: string;
  /**
   * Marks the object as decorative - a reel frame passing by, for instance.
   *
   * A decorative object is hidden from assistive tech and from the tab order, which
   * matters most inside the reel: twenty-six frames in a scrolling strip would otherwise
   * be announced as twenty-six separate collectibles.
   */
  decorative?: boolean;
  /** Runs the one-shot specular sweep. Only the reveal should pass this. */
  sweep?: boolean;
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
  regionCode,
  scale = 1,
  className = '',
  ariaLabel,
  decorative = false,
  sweep = false,
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
      '--plate-sheen': String(visual.gloss ? Math.min(1, visual.sheen) : 0.08),
      '--plate-rail': `${Math.max(2, Math.round(3 * scale))}px`,
      '--plate-raise': String(Math.max(0, Math.min(1, visual.relief ?? 0.35))),
      '--plate-grain': String(Math.max(0, Math.min(1, visual.grain ?? 0.16))),
    }),
    [visual, scale],
  );

  /*
   * The frame is sized from the recipe's own millimetres, scaled: a 520mm plate at
   * scale 1 is 520 CSS px wide, which is exactly the physical size on a 1:1 display and
   * behaves predictably at every other one. `max-width: 100%` is the only thing standing
   * between the object and a horizontal overflow on a 320px screen.
   */
  const frameVars = useMemo<StyleVars>(
    () => ({
      ...recipeVars,
      aspectRatio: `${visual.aspect}`,
      width: `${Math.round(visual.width_mm * scale)}px`,
      maxWidth: '100%',
    }),
    [recipeVars, visual.aspect, visual.width_mm, scale],
  );

  const regionText = (regionCode ?? '').trim() || (regionName ?? '').trim();

  /*
   * A two-compartment plate owns the region segment.
   *
   * On the Russian format the registration is `<letter><3 digits><2 letters>` and the
   * region code lives in its own right-hand compartment. The stored `plate_text` still
   * contains both, because that is what makes the text searchable - so the renderer has
   * to *move* the region group into the compartment rather than print it twice. Printing
   * both was the old behaviour, and a plate with "777" appearing twice reads as a mistake
   * because on a real plate it appears once.
   */
  const hasRegionCompartment = visual.region_position === 'right' && Boolean(regionText);
  const hasRegionBadge = visual.region_position === 'badge' && Boolean(regionText);
  const printed = hasRegionCompartment
    ? segments.filter((segment) => segment.kind !== 'region')
    : segments;

  const faceVars = useMemo<StyleVars>(() => {
    const bandOnLeft = visual.band_position === 'left';
    const bandOnRight = visual.band_position === 'right';
    // A two-compartment plate sets its registration left of centre, because the
    // compartment occupies the right-hand space.
    const compartment = hasRegionCompartment;
    return {
      width: '100%',
      height: '100%',
      gap: bandOnLeft || bandOnRight ? 0 : '1%',
      justifyContent: bandOnRight ? 'flex-end' : bandOnLeft || compartment ? 'flex-start' : 'center',
      // Inner margins of the printed field. A real plate keeps a generous border so the
      // registration never runs into the frame.
      paddingLeft: bandOnLeft ? '1.2%' : compartment ? '3%' : '4%',
      paddingRight: bandOnRight
        ? '1.2%'
        : hasRegionBadge
          ? `calc(${Math.max(4, visual.region_width * 100)}% + 2%)`
          : compartment
            ? '2%'
            : '4%',
      /*
       * Containment, and this is load-bearing rather than decorative.
       *
       * A plate is a *physical object*: nothing printed on it can run past its edge, and
       * a serial wider than the field has to shrink rather than spill. `min-width: 0` on
       * the print block is what allows the flex child to shrink below its content width,
       * which is what prevents the classic long-plate horizontal overflow. The `cqw`
       * sizing of the type then fills whatever room is left.
       */
      minWidth: 0,
      overflow: 'hidden',
    };
  }, [visual.band_position, visual.region_width, hasRegionBadge, hasRegionCompartment]);

  const hasBand =
    visual.band_position !== 'none' &&
    Boolean(visual.band_color) &&
    (Boolean(visual.band_text) || visual.band_stars || Boolean(visual.band_flag));
  const bandWidth = `${Math.max(3, visual.band_width * 100).toFixed(1)}%`;

  /**
   * Printed type size.
   *
   * Derived from how much has to fit and expressed in `cqw`, so a short US serial and a
   * long EU serial both end up with the same *relative* weight on their own plate
   * instead of the same pixel size.
   *
   * The `0.62` is the average glyph advance of a condensed grotesque as a fraction of
   * the type size, plus the tracking the recipe asks for. It is the single number that
   * decides whether a serial fits its field - too small and it shrinks unnecessarily,
   * too large and the plate would overflow, so it is deliberately conservative and the
   * face clips rather than spills.
   */
  const { fontSize, baseFontPx } = useMemo(() => {
    const longest = Math.max(1, plateText.replace(/\s/g, '').length);
    const min = Math.round(6 * scale);
    const max = Math.round(52 * scale);
    return {
      baseFontPx: max,
      fontSize: `clamp(${min}px, ${(100 / (longest * 0.62)).toFixed(2)}cqw, ${max}px)`,
    };
  }, [plateText, scale]);

  const header = resolveHeader(visual, regionName);
  return (
    <div
      className={`plate-frame plate-texture plate-wear ${className}`}
      style={{ ...frameVars, containerType: 'inline-size' } as React.CSSProperties}
      // A decorative object is not announced and carries no label; a real one is an image
      // whose alt text is the value it shows, so the two agree.
      role={decorative ? 'presentation' : 'img'}
      aria-hidden={decorative || undefined}
      aria-label={decorative ? undefined : (ariaLabel ?? plateText)}
      tabIndex={decorative ? -1 : undefined}
      data-plate-theme={visual.theme}
      data-mount={visual.mount}
    >
      <div className="plate-face" style={faceVars as React.CSSProperties}>
        {hasBand && visual.band_position === 'left' && (
          <PlateBand visual={visual} width={bandWidth} />
        )}

        {header && (
          <div
            className="plate-header"
            style={{
              top: `${Math.round((visual.header_offset ?? 0.08) * 100)}%`,
              textAlign: visual.header_align as React.CSSProperties['textAlign'],
              padding: '0 4%',
              fontSize: header.fontSize,
            }}
          >
            {header.text}
          </div>
        )}

        {visual.emblem && visual.emblem !== 'state_tag' ? (
          <span
            className="plate-emblem"
            style={{
              bottom: '7%',
              left: '5%',
              fontSize: '0.4em',
              color: visual.muted,
            }}
            aria-hidden="true"
          >
            {emblemGlyph(visual.emblem)}
          </span>
        ) : null}

        {/*
          The printed serial. On a two-compartment plate this block is left-aligned so
          the registration sits beside the rule rather than centred across the whole
          face, which is how the format actually reads.
        */}
        <div
          className="plate-print"
          style={{
            fontSize,
            gap: visual.group_gap,
            justifyContent: hasRegionCompartment ? 'flex-start' : undefined,
            textAlign: hasRegionCompartment ? 'left' : undefined,
          }}
        >
          {printed.map((segment, index) => (
            <span
              key={`${segment.text}-${index}`}
              className={SEGMENT_CLASS[segment.kind]}
              style={{
                fontSize:
                  segment.kind === 'digit'
                    ? `${visual.digit_scale}em`
                    : `${visual.letter_scale}em`,
                fontWeight: segment.kind === 'letter' ? 600 : undefined,
                letterSpacing: segment.gap ? undefined : '0.015em',
              }}
            >
              {/* The gap is a real character, not just spacing: the printed object must
                  read back as exactly `plateText` for assistive tech and for copying. */}
              {segment.gap ? ' ' : null}
              {segment.text}
            </span>
          ))}
        </div>

        {hasRegionCompartment ? (
          <div
            className="plate-region-block"
            style={{
              fontSize: `${Math.round(0.46 * baseFontPx)}px`,
              width: `${Math.round((visual.region_width || 0.13) * 100)}%`,
              boxSizing: 'border-box',
              minWidth: 0,
              padding: '0 0.25em',
            }}
          >
            {/* The Russian format prints the flag, the RUS legend, and the region code
                beneath them - three printed elements, not one string. */}
            {visual.region_flag ? (
              <PlateFlag
                flag="ru"
                className="!mb-[0.25em]"
                style={{ width: '2.1em', height: '1.3em' }}
              />
            ) : null}
            {visual.region_flag || visual.region_text ? (
              <span className="plate-region-legend">
                {visual.region_text}
              </span>
            ) : null}
            <span>{regionText}</span>
          </div>
        ) : null}

        {hasRegionBadge ? (
          <div
            className="plate-region-badge"
            style={{
              top: 0,
              right: 0,
              bottom: 0,
              width: `${Math.max(4, visual.region_width * 100)}%`,
              background: visual.band_color || visual.accent,
              color: visual.band_color ? visual.band_text_color : '#ffffff',
            }}
            aria-hidden="true"
          >
            {regionText}
          </div>
        ) : null}

        {hasBand && visual.band_position === 'right' && (
          <PlateBand visual={visual} width={bandWidth} />
        )}

        {/* Wear sits under the gloss: both are surface effects on top of the print. */}
        {sweep ? <span className="plate-sweep plate-sweep-run" aria-hidden="true" /> : null}
        <span className="plate-gloss" aria-hidden="true" />
      </div>

    </div>
  );
}

/**
 * A printed national flag inside a plate's identifier band, drawn as vectors.
 *
 * Only the two formats NUMORA reproduces literally are supported. Both are instantly
 * recognisable and both are what makes their country's plate read correctly - the Russian
 * tricolour with its `RUS` legend, and the Georgian cross with `GE` in a blue block.
 * Everything else stays a printed code, because a pasted-on flag would read as a sticker
 * rather than as part of the plate.
 */
function PlateFlag({
  flag,
  className = '',
  style,
}: {
  flag: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  if (flag === 'ru') return <span className={`plate-flag-ru ${className}`} style={style} aria-hidden="true" />;
  if (flag === 'ge') return <span className={`plate-flag-ge ${className}`} style={style} aria-hidden="true" />;
  return null;
}

/** The country identifier band: a printed code block with stars and a flag. */
function PlateBand({ visual, width }: { visual: PlateVisual; width: string }) {
  return (
    <div className="plate-band" style={{ width }} aria-hidden="true">
      {visual.band_stars && <span className="plate-stars" />}
      {visual.band_flag ? <PlateFlag flag={visual.band_flag} style={{ width: '2em' }} /> : null}
      {visual.band_text && (
        <span style={{ fontSize: '0.6em', letterSpacing: '0.03em' }}>{visual.band_text}</span>
      )}
    </div>
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
    return { text: regionName, fontSize: '0.4em' };
  }
  if (visual.header_source === 'none' || !visual.header) return null;
  return { text: visual.header, fontSize: '0.3em' };
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
        regionCode={card.region?.code ?? null}
        scale={scale}
      />
      {showValue && (
        <span className="t-caption font-semibold text-white/70">
          {card.currency_symbol}
          {formatCoins(card.collector_value)}
        </span>
      )}
    </div>
  );
}
export { VehiclePlateVisual };
