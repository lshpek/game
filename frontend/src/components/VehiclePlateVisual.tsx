
import { useMemo } from 'react';

import { formatCoins } from '../lib/format';
import type { PlateCard, PlateVisual, PlateSegmentKind } from '../types';

interface Props {
  visual: PlateVisual;
  plateText: string;
  displaySegments?: string[];
  displaySegmentGaps?: boolean[];
  displaySegmentKinds?: PlateSegmentKind[];
  regionName?: string | null;
  regionCode?: string | null;
  scale?: number;
  className?: string;
  ariaLabel?: string;
  decorative?: boolean;
  sweep?: boolean;
  // TEMPORARY frontend-only visual override for video recording.
  // Replaces the plate text/region without touching the API, backend,
  // inventory or shared data. Remove after recording.
  temporaryPlateOverride?: {
    plateText: string;
    regionCode?: string | null;
    regionName?: string | null;
    displaySegments?: string[];
    displaySegmentGaps?: boolean[];
    displaySegmentKinds?: PlateSegmentKind[];
  };
}

type StyleVars = Record<string, string | number>;

type Segment = {
  text: string;
  gap: boolean;
  kind: PlateSegmentKind;
};

const SEGMENT_CLASS: Record<PlateSegmentKind, string> = {
  letter: 'opacity-95',
  digit: '',
  region: '',
  mixed: '',
  mark: 'opacity-60',
};

function inferKind(value: string): PlateSegmentKind {
  const text = value.trim();

  if (/^\d+$/.test(text)) return 'digit';
  if (/^[a-z]+$/i.test(text)) return 'letter';
  if (/^[^a-z\d]+$/i.test(text)) return 'mark';

  return 'mixed';
}

function splitCharacters(text: string): Segment[] {
  const result: Segment[] = [];
  let pendingGap = false;

  for (const char of text) {
    if (/\s/.test(char)) {
      pendingGap = true;
      continue;
    }

    const kind = inferKind(char);
    const lastIndex = result.length - 1;
    const last = result[lastIndex];

    if (last && !pendingGap && last.kind === kind) {
      result[lastIndex] = {
        ...last,
        text: last.text + char,
      };
    } else {
      result.push({
        text: char,
        gap: pendingGap,
        kind,
      });
    }

    pendingGap = false;
  }

  return result;
}

function buildSegments(
  plateText: string,
  displaySegments: string[] | undefined,
  displaySegmentGaps: boolean[] | undefined,
  displaySegmentKinds: PlateSegmentKind[] | undefined,
  regionCode: string,
  hasRegionCompartment: boolean,
): Segment[] {
  let result: Segment[];

  if (displaySegments?.length) {
    result = displaySegments.map(
      (text, index): Segment => ({
        text,
        gap: Boolean(displaySegmentGaps?.[index] ?? (index > 0)),
        kind: displaySegmentKinds?.[index] ?? inferKind(text),
      }),
    );
  } else {
    result = splitCharacters(plateText);
  }

  if (
    !hasRegionCompartment ||
    !regionCode ||
    displaySegmentKinds?.length ||
    result.length === 0
  ) {
    return result;
  }

  const lastIndex = result.length - 1;
  const last = result[lastIndex];

  // TypeScript: protect against an absent last element.
  if (!last) {
    return result;
  }

  const lastText = last.text.trim();

  if (lastText === regionCode) {
    return result.map((segment, index): Segment =>
      index === lastIndex
        ? { ...segment, kind: 'region' }
        : segment,
    );
  }

  if (
    lastText.endsWith(regionCode) &&
    lastText.length > regionCode.length
  ) {
    const prefix = lastText.slice(0, -regionCode.length);

    return [
      ...result.slice(0, lastIndex),
      {
        ...last,
        text: prefix,
        kind: inferKind(prefix),
      },
      {
        text: regionCode,
        gap: true,
        kind: 'region',
      },
    ];
  }

  // Older payloads may include the region code in plateText
  // without providing a separate region segment.
  const normalizedText = plateText.trimEnd();

  if (normalizedText.endsWith(regionCode)) {
    const mainText = normalizedText
      .slice(0, -regionCode.length)
      .trimEnd();

    return splitCharacters(mainText);
  }

  return result;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
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
  temporaryPlateOverride,
}: Props) {
  // TEMPORARY frontend-only visual override for video recording.
  // Applies to this plate instance only; nothing is saved or shared.
  const override = temporaryPlateOverride;

  const effectivePlateText = override?.plateText ?? plateText;
  const effectiveRegionCode = (override?.regionCode ?? regionCode ?? '').trim();
  const effectiveRegionName = override?.regionName ?? regionName;
  const effectiveDisplaySegments = override?.displaySegments ?? displaySegments;
  const effectiveDisplaySegmentGaps =
    override?.displaySegmentGaps ?? displaySegmentGaps;
  const effectiveDisplaySegmentKinds =
    override?.displaySegmentKinds ?? displaySegmentKinds;

  const code = effectiveRegionCode;

  const hasRegionCompartment =
    visual.region_position === 'right' && Boolean(code);

  const hasRegionBadge =
    visual.region_position === 'badge' && Boolean(code);

  const segments = useMemo(
    () =>
      buildSegments(
        effectivePlateText,
        effectiveDisplaySegments,
        effectiveDisplaySegmentGaps,
        effectiveDisplaySegmentKinds,
        code,
        hasRegionCompartment,
      ),
    [
      effectivePlateText,
      effectiveDisplaySegments,
      effectiveDisplaySegmentGaps,
      effectiveDisplaySegmentKinds,
      code,
      hasRegionCompartment,
    ],
  );

  const printed = hasRegionCompartment
    ? segments.filter((segment) => segment.kind !== 'region')
    : segments;

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
      '--plate-sheen': String(
        visual.gloss ? clamp(visual.sheen, 0, 1) : 0.08,
      ),
      '--plate-rail': `${Math.max(2, Math.round(3 * scale))}px`,
      '--plate-raise': String(clamp(visual.relief ?? 0.35, 0, 1)),
      '--plate-grain': String(clamp(visual.grain ?? 0.16, 0, 1)),
    }),
    [visual, scale],
  );

  const frameVars = useMemo<StyleVars>(
    () => ({
      ...recipeVars,
      aspectRatio: `${visual.aspect}`,
      width: `${Math.round(visual.width_mm * scale)}px`,
      maxWidth: '100%',
    }),
    [recipeVars, visual.aspect, visual.width_mm, scale],
  );

  const faceVars = useMemo<StyleVars>(
    () => ({
      width: '100%',
      height: '100%',
      gap:
        visual.band_position === 'left' ||
        visual.band_position === 'right'
          ? 0
          : '1%',
      justifyContent:
        visual.band_position === 'right'
          ? 'flex-end'
          : visual.band_position === 'left' || hasRegionCompartment
            ? 'space-between'
            : 'center',
      paddingLeft:
        visual.band_position === 'left'
          ? '1.2%'
          : hasRegionCompartment
            ? '3%'
            : '4%',
      paddingRight:
        visual.band_position === 'right'
          ? '1.2%'
          : hasRegionBadge
            ? `calc(${Math.max(4, visual.region_width * 100)}% + 2%)`
            : hasRegionCompartment
              ? '2%'
              : '4%',
      minWidth: 0,
      overflow: 'hidden',
    }),
    [
      visual.band_position,
      visual.region_width,
      hasRegionBadge,
      hasRegionCompartment,
    ],
  );

  const hasBand =
    visual.band_position !== 'none' &&
    Boolean(visual.band_color) &&
    (Boolean(visual.band_text) ||
      visual.band_stars ||
      Boolean(visual.band_flag));

  const bandWidth = `${Math.max(3, visual.band_width * 100).toFixed(1)}%`;

  const { fontSize, baseFontPx } = useMemo(() => {
    const characterCount = Math.max(
      1,
      printed.reduce(
        (total, segment) => total + segment.text.length,
        0,
      ),
    );

    const min = Math.max(6, Math.round(6 * scale));
    const max = Math.max(min, Math.round(52 * scale));

    return {
      baseFontPx: max,
      fontSize: `clamp(${min}px, ${(100 / (characterCount * 0.62)).toFixed(2)}cqw, ${max}px)`,
    };
  }, [printed, scale]);

  const header = resolveHeader(visual, effectiveRegionName);

  return (
    <div
      className={`plate-frame plate-texture plate-wear ${override ? 'temp-recording-plate' : ''} ${className}`}
      style={
        { ...frameVars, containerType: 'inline-size' } as React.CSSProperties
      }
      role={decorative ? 'presentation' : 'img'}
      aria-hidden={decorative || undefined}
      aria-label={decorative ? undefined : (ariaLabel ?? plateText)}
      tabIndex={decorative ? -1 : undefined}
      data-plate-theme={visual.theme}
      data-plate-family={visual.plate_family}
      data-plate-mount={visual.mount}
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

        {visual.emblem && visual.emblem !== 'state_tag' && (
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
        )}

        <div
          className="plate-print"
          style={{
            fontSize,
            gap: visual.group_gap,
            justifyContent: hasRegionCompartment ? 'space-between' : undefined,
            textAlign: hasRegionCompartment ? 'center' : undefined,
            minWidth: 0,
            maxWidth: '100%',
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
              {segment.gap ? ' ' : null}
              {segment.text}
            </span>
          ))}
        </div>

        {hasRegionCompartment && (
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
            {visual.region_flag && (
              <PlateFlag
                flag={visual.band_flag ?? 'ru'}
                className="!mb-[0.25em]"
                style={{ width: '2.1em', height: '1.3em' }}
              />
            )}

            {(visual.region_flag || visual.region_text) && (
              <span className="plate-region-legend">
                {visual.region_text}
              </span>
            )}

            <span>{code}</span>
          </div>
        )}

        {hasRegionBadge && (
          <div
            className="plate-region-badge"
            style={{
              top: 0,
              right: 0,
              bottom: 0,
              width: `${Math.max(4, visual.region_width * 100)}%`,
              background: visual.band_color || visual.accent,
              color: visual.band_color
                ? visual.band_text_color
                : '#ffffff',
            }}
            aria-hidden="true"
          >
            {code}
          </div>
        )}

        {hasBand && visual.band_position === 'right' && (
          <PlateBand visual={visual} width={bandWidth} />
        )}

        {sweep && (
          <span
            className="plate-sweep plate-sweep-run"
            aria-hidden="true"
          />
        )}

        <span className="plate-gloss" aria-hidden="true" />
      </div>
    </div>
  );
}

function PlateFlag({
  flag,
  className = '',
  style,
}: {
  flag: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  if (flag === 'ru') {
    return (
      <span
        className={`plate-flag-ru ${className}`}
        style={style}
        aria-hidden="true"
      />
    );
  }

  if (flag === 'ge') {
    return (
      <span
        className={`plate-flag-ge ${className}`}
        style={style}
        aria-hidden="true"
      />
    );
  }

  return null;
}

function PlateBand({
  visual,
  width,
}: {
  visual: PlateVisual;
  width: string;
}) {
  return (
    <div className="plate-band" style={{ width }} aria-hidden="true">
      {visual.band_stars && <span className="plate-stars" />}

      {visual.band_flag && (
        <PlateFlag
          flag={visual.band_flag}
          style={{ width: '2em' }}
        />
      )}

      {visual.band_text && (
        <span
          style={{
            fontSize: '0.6em',
            letterSpacing: '0.03em',
          }}
        >
          {visual.band_text}
        </span>
      )}
    </div>
  );
}

function resolveHeader(
  visual: PlateVisual,
  regionName?: string | null,
): { text: string; fontSize: string } | null {
  if (visual.header_source === 'region') {
    if (!regionName) return null;

    return {
      text: regionName,
      fontSize: '0.4em',
    };
  }

  if (visual.header_source === 'none' || !visual.header) {
    return null;
  }

  return {
    text: visual.header,
    fontSize: '0.3em',
  };
}

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
