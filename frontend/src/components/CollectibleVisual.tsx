import { motion } from 'framer-motion';
import clsx from 'clsx';
import type { CollectibleCategory, PlateCard } from '@/types';

interface CollectibleVisualProps {
  collectible: PlateCard;
  size?: 'sm' | 'md' | 'lg' | 'hero';
  className?: string;
  /** Rarity accent, supplied by the caller so plate and reveal stay consistent. */
  accent?: string;
  /** Adds the entrance animation used by the roll reveal. */
  reveal?: boolean;
  /** Pauses the idle shimmer - used while the reveal is cycling previews. */
  still?: boolean;
}

/**
 * The hero object of the whole game.
 *
 * One component renders every collectible kind so the Number Universe reads as a
 * single game: a vehicle plate is a physical object with a metal frame, a phone
 * number is a typographic hero on a dark telecom card, and a SIM is a gold-edged
 * chip card. The kind is decided by the server (`category`); the client only
 * decides how to *draw* it.
 *
 * Everything is driven by data the backend already sends - the visual recipe, the
 * country's flag and the accent colour - so a new country or category needs no
 * frontend change.
 */
export function resolveCategory(collectible: PlateCard): CollectibleCategory {
  const declared = collectible.category;
  if (declared === 'PHONE_NUMBER' || declared === 'SIM_CARD') return declared;
  // Older payloads (and cached cards) have no `category`; fall back to the type.
  if (collectible.plate_type === 'PHONE') return 'PHONE_NUMBER';
  if (collectible.plate_type === 'SIM') return 'SIM_CARD';
  return 'VEHICLE_PLATE';
}

export type CollectibleSize = 'sm' | 'md' | 'lg' | 'hero';
type SizeKey = CollectibleSize;

/** Props for the three renderers. The size is always resolved by the wrapper. */
interface VisualProps {
  collectible: PlateCard;
  size: SizeKey;
  className?: string;
  accent?: string;
  reveal?: boolean;
  still?: boolean;
}

const SIZES: Record<SizeKey, Record<string, string>> = {
  sm: { plate: 'text-sm', hero: 'text-2xl', sim: 'text-base', frame: 'px-2 py-1.5', card: 'p-4' },
  md: { plate: 'text-xl', hero: 'text-4xl', sim: 'text-2xl', frame: 'px-3 py-2', card: 'p-6' },
  lg: { plate: 'text-3xl sm:text-4xl', hero: 'text-6xl sm:text-7xl', sim: 'text-4xl', frame: 'px-4 py-3', card: 'p-8' },
  hero: { plate: 'text-4xl sm:text-6xl', hero: 'text-6xl sm:text-8xl', sim: 'text-5xl sm:text-6xl', frame: 'px-5 py-4', card: 'p-10' },
};

export function CollectibleVisual({
  collectible,
  size = 'md',
  className,
  accent = '#8b93a7',
  reveal = false,
  still = false,
}: CollectibleVisualProps) {
  const category = resolveCategory(collectible);
  if (category === 'PHONE_NUMBER') {
    return <PhoneVisual collectible={collectible} size={size} className={className} accent={accent} reveal={reveal} still={still} />;
  }
  if (category === 'SIM_CARD') {
    return <SimVisual collectible={collectible} size={size} className={className} accent={accent} reveal={reveal} still={still} />;
  }
  return <PlateObject collectible={collectible} size={size} className={className} accent={accent} reveal={reveal} still={still} />;
}

/** A vehicle plate as a physical object: metal frame, bevel, gloss and shadow. */
function PlateObject({
  collectible,
  size,
  className,
  accent,
  reveal,
  still,
}: VisualProps) {
  const visual = collectible.visual;
  const accentColor = accent ?? '#8b93a7';
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
        boxShadow: `0 18px 40px -18px ${accentColor}aa, inset 0 1px 0 rgba(255,255,255,0.14), inset 0 -2px 6px rgba(0,0,0,0.45)`,
      }}
      data-testid="collectible-visual"
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
          style={{ background: `linear-gradient(90deg, transparent, ${accentColor}88, transparent)` }}
        />
      ) : null}

      <div className="relative flex h-full w-full items-center justify-center gap-2 pl-[8%]">
        {visual.header || (visual.show_flag && collectible.country.flag) ? (
          <span
            className="absolute left-[10%] top-1 flex items-center gap-1 text-[9px] font-bold uppercase tracking-widest"
            style={{ color: visual.muted, justifyContent: visual.header_align }}
          >
            {visual.show_flag ? <span aria-hidden>{collectible.country.flag}</span> : null}
            {visual.header ? <span>{visual.header}</span> : null}
          </span>
        ) : null}

        <div className="flex items-center justify-center gap-1.5">
          {segments.map((segment, index) => (
            <span
              key={`${segment}-${index}`}
              className={clsx('number-display whitespace-nowrap', scale.plate)}
              style={{ color: visual.text }}
            >
              {segment}
            </span>
          ))}
        </div>

        {visual.region_badge && collectible.region && size !== 'sm' ? (
          <span
            className="absolute bottom-1 right-2 rounded px-1 text-[9px] font-bold"
            style={{ color: visual.muted, background: `${visual.muted}22` }}
          >
            {collectible.region.code}
          </span>
        ) : null}
      </div>
    </motion.div>
  );
}

/**
 * A phone number as a telecom hero card.
 *
 * These are synthetic game numbers. The card says so, in both locales, because a
 * number that looks real must never be mistaken for somebody's line.
 */
function PhoneVisual({ collectible, size, className, accent, reveal, still }: VisualProps) {
  const scale = SIZES[size];
  const groups = collectible.display_segments.length
    ? collectible.display_segments
    : [collectible.plate_text];

  return (
    <motion.div
      className={clsx(
        'relative w-full overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-b from-[#10141f] to-[#05070d]',
        scale.card,
        className,
      )}
      style={{ boxShadow: `0 24px 60px -24px ${accent}, inset 0 1px 0 rgba(255,255,255,0.08)` }}
      data-testid="collectible-visual"
      data-kind="PHONE_NUMBER"
      data-plate={collectible.plate_text}
      role="img"
      aria-label={collectible.plate_text}
      initial={reveal ? { scale: 1.1, opacity: 0, y: 16 } : false}
      animate={reveal ? { scale: 1, opacity: 1, y: 0 } : undefined}
      transition={{ type: 'spring', stiffness: 210, damping: 19 }}
    >
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-px"
        style={{ background: `linear-gradient(90deg, transparent, ${accent}, transparent)` }}
      />
      {!still ? (
        <span aria-hidden className="pointer-events-none absolute inset-0 opacity-40 phone-scan" />
      ) : null}

      <div className="relative flex flex-col items-center gap-3">
        <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.28em] text-white/45">
          <span aria-hidden>{collectible.country.flag}</span>
          <span>{collectible.country.code}</span>
          <span className="h-3 w-px bg-white/15" />
          <span>SIM · GAME</span>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1">
          {groups.map((group, index) => (
            <span
              key={`${group}-${index}`}
              className={clsx('number-display whitespace-nowrap text-white', scale.hero)}
              style={{ textShadow: `0 0 22px ${accent}55` }}
            >
              {group}
            </span>
          ))}
        </div>

        <span className="text-[9px] uppercase tracking-[0.2em] text-white/30">
          synthetic game number
        </span>
      </div>
    </motion.div>
  );
}

/** A SIM card as a collectible trading object: chip, foil, serial and edition. */
function SimVisual({ collectible, size, className, accent, reveal, still }: VisualProps) {
  const scale = SIZES[size];
  const serial = collectible.template.pattern.split(' ')[0] || collectible.numbers.join('');
  const edition = collectible.template.code.split('_').pop() ?? '';
  const operator = collectible.template.code.split('_')[2] ?? '';

  return (
    <motion.div
      className={clsx(
        'relative w-full overflow-hidden rounded-xl border border-amber-200/20 bg-gradient-to-br from-[#2a2416] via-[#141118] to-[#0a0a10]',
        scale.card,
        className,
      )}
      style={{ boxShadow: `0 24px 60px -24px ${accent}, inset 0 1px 0 rgba(255,255,255,0.1)` }}
      data-testid="collectible-visual"
      data-kind="SIM_CARD"
      data-plate={collectible.plate_text}
      role="img"
      aria-label={collectible.plate_text}
      initial={reveal ? { scale: 1.1, opacity: 0, rotateY: -18 } : false}
      animate={reveal ? { scale: 1, opacity: 1, rotateY: 0 } : undefined}
      transition={{ type: 'spring', stiffness: 200, damping: 18 }}
    >
      <span aria-hidden className="absolute inset-0 opacity-30 sim-foil" />
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-px"
        style={{ background: `linear-gradient(90deg, transparent, ${accent}, transparent)` }}
      />

      <div className="relative flex items-start gap-4">
        <span aria-hidden className="sim-chip" />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.24em] text-amber-200/70">
            <span aria-hidden>{collectible.country.flag}</span>
            <span>{operator.toUpperCase()}</span>
          </div>
          <span className={clsx('number-display text-amber-50', scale.sim)}>{serial}</span>
          <span className="truncate text-[10px] uppercase tracking-[0.22em] text-white/35">
            {edition} edition
          </span>
        </div>
      </div>

      {!still && size !== 'sm' ? (
        <span
          aria-hidden
          className="absolute bottom-2 right-3 text-[9px] font-bold uppercase tracking-[0.3em]"
          style={{ color: accent }}
        >
          SIM
        </span>
      ) : null}
    </motion.div>
  );
}

export default CollectibleVisual;