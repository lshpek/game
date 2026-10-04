import clsx from 'clsx';
import type { PlateCard } from '@/types';

interface PlateVisualProps {
  plate: PlateCard;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  /** Adds the flip-in entrance animation used by the roll reveal. */
  reveal?: boolean;
}

/**
 * Renders a plate the way a real one looks: country band, region badge and
 * the registered segments - all driven by the server-provided visual recipe,
 * so adding a country needs no frontend change.
 */
export function PlateVisual({ plate, size = 'md', className, reveal = false }: PlateVisualProps) {
  const visual = plate.visual;
  const segments = plate.display_segments.length ? plate.display_segments : [plate.plate_text];

  const sizes = {
    sm: { frame: 'px-2 py-1.5 gap-1.5', text: 'text-sm', band: 'w-2' },
    md: { frame: 'px-3 py-2 gap-2', text: 'text-xl', band: 'w-3' },
    lg: { frame: 'px-4 py-3 gap-2.5', text: 'text-3xl sm:text-4xl', band: 'w-4' },
  } as const;
  const scale = sizes[size];

  return (
    <div
      className={clsx('plate-frame relative w-full overflow-hidden rounded-xl border shadow-plate', scale.frame, className)}
      style={{
        aspectRatio: String(visual.aspect),
        background: visual.background,
        borderColor: visual.border,
        color: visual.text,
        letterSpacing: visual.letter_spacing,
        ...(reveal ? { animation: 'plate-reveal 0.55s cubic-bezier(0.22, 1, 0.36, 1) both' } : {}),
      }}
      data-testid="plate-visual"
      data-plate={plate.plate_text}
      role="img"
      aria-label={plate.plate_text}
    >
      {visual.band_color ? (
        <span
          aria-hidden
          className="absolute inset-y-0 left-0"
          style={{ width: `${Math.max(visual.band_width * 100, 4)}%`, background: visual.band_color }}
        />
      ) : null}

      {visual.gloss ? <span aria-hidden className="plate-gloss" /> : null}

      <div className="relative flex h-full w-full items-center justify-center gap-2 pl-[8%]">
        {visual.header || (visual.show_flag && plate.country.flag) ? (
          <span
            className="absolute left-[10%] top-1 flex items-center gap-1 text-[9px] font-bold uppercase tracking-widest"
            style={{ color: visual.muted, justifyContent: visual.header_align }}
          >
            {visual.show_flag ? <span aria-hidden>{plate.country.flag}</span> : null}
            {visual.header ? <span>{visual.header}</span> : null}
          </span>
        ) : null}

        <div className="flex items-center justify-center gap-1.5">
          {segments.map((segment, index) => (
            <span
              key={`${segment}-${index}`}
              className={clsx('number-display whitespace-nowrap', scale.text)}
              style={{ color: visual.text }}
            >
              {segment}
            </span>
          ))}
        </div>

        {visual.region_badge && plate.region && size !== 'sm' ? (
          <span
            className="absolute bottom-1 right-2 rounded px-1 text-[9px] font-bold"
            style={{ color: visual.muted, background: `${visual.muted}22` }}
          >
            {plate.region.code}
          </span>
        ) : null}
      </div>
    </div>
  );
}
