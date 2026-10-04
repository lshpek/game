import { motion } from 'framer-motion';
import clsx from 'clsx';
import type { PlateCard } from '@/types';
import type { PhysicalSize } from './SimCardVisual';

interface VehiclePlateVisualProps {
  collectible: PlateCard;
  size?: PhysicalSize;
  className?: string;
  /** Rarity accent, supplied by the caller so plate and reveal stay consistent. */
  accent?: string;
  reveal?: boolean;
  /** Pauses the idle shimmer while the reveal cycles previews. */
  still?: boolean;
}

const SIZES: Record<PhysicalSize, Record<string, string>> = {
  sm: { frame: 'px-2 py-1.5', text: 'text-sm', side: 'text-[7px]' },
  md: { frame: 'px-3 py-2', text: 'text-xl', side: 'text-[9px]' },
  lg: { frame: 'px-4 py-3', text: 'text-3xl sm:text-4xl', side: 'text-[10px]' },
  hero: { frame: 'px-5 py-4', text: 'text-4xl sm:text-6xl', side: 'text-[11px]' },
};

/**
 * A vehicle registration plate rendered as a physical object.
 *
 * The plate is the hero: a metal frame with a bevel, a recessed face, a gloss pass
 * and a drop shadow, sized to the country's own aspect ratio. Everything is driven
 * by the server-provided visual recipe, so a new country needs no frontend change.
 */
export function VehiclePlateVisual({
  collectible,
  size = 'md',
  className,
  accent = '#8b93a7',
  reveal = false,
  still = false,
}: VehiclePlateVisualProps) {
  const visual = collectible.visual;
  const segments = collectible.display_segments.length
    ? collectible.display_segments
    : [collectible.plate_text];
  const scale = SIZES[size];

  return (
    <motion.div
      className={clsx(
        'plate-frame relative w-full overflow-hidden rounded-xl shadow-plate',
        scale.frame,
        className,
      )}
      style={{
        aspectRatio: String(visual.aspect),
        background: visual.background,
        borderColor: visual.border,
        color: visual.text,
        letterSpacing: visual.letter_spacing,
        boxShadow: `0 18px 40px -18px ${accent}aa, inset 0 1px 0 rgba(255,255,255,0.14), inset 0 -2px 6px rgba(0,0,0,0.45)`,
      }}
      data-testid="vehicle-plate-visual"
      data-kind="VEHICLE_PLATE"
      data-plate={collectible.plate_text}
      role="img"
      aria-label={collectible.plate_text}
      initial={reveal ? { scale: 1.12, opacity: 0, rotateX: 22 } : false}
      animate={reveal ? { scale: 1, opacity: 1, rotateX: 0 } : undefined}
      transition={{ type: 'spring', stiffness: 220, damping: 20 }}
    >
      {visual.band_color ? (
        <span
          aria-hidden
          className="absolute inset-y-0 left-0"
          style={{ width: `${Math.max(visual.band_width * 100, 4)}%`, background: visual.band_color }}
        />
      ) : null}
      {visual.gloss ? <span aria-hidden className="plate-gloss" /> : null}
      {!still && size !== 'sm' ? (
        <span
          aria-hidden
          className="absolute inset-x-0 top-0 h-px"
          style={{ background: `linear-gradient(90deg, transparent, ${accent}88, transparent)` }}
        />
      ) : null}

      <div className="relative flex h-full w-full items-center justify-center gap-2 pl-[8%]">
        {visual.header || (visual.show_flag && collectible.country.flag) ? (
          <span
            className="absolute left-[10%] top-1 flex items-center gap-1 font-bold uppercase tracking-widest"
            style={{ color: visual.muted, justifyContent: visual.header_align, fontSize: scale.side }}
          >
            {visual.show_flag ? <span aria-hidden>{collectible.country.flag}</span> : null}
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

        {visual.region_badge && collectible.region && size !== 'sm' ? (
          <span
            className="absolute bottom-1 right-2 rounded px-1 font-bold"
            style={{ color: visual.muted, background: `${visual.muted}22`, fontSize: scale.side }}
          >
            {collectible.region.code}
          </span>
        ) : null}
      </div>
    </motion.div>
  );
}

export default VehiclePlateVisual;