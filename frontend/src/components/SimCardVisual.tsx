import { motion } from 'framer-motion';
import clsx from 'clsx';
import type { PlateCard, SimCardDetails } from '@/types';

export type PhysicalSize = 'sm' | 'md' | 'lg' | 'hero';

interface SimCardVisualProps {
  collectible: PlateCard;
  size?: PhysicalSize;
  className?: string;
  accent?: string;
  reveal?: boolean;
  /** Pauses the idle shimmer while the reveal cycles previews. */
  still?: boolean;
}

/**
 * A collectible SIM card as a *physical object*.
 *
 * This is deliberately not a smartphone mockup and not a phone UI: it is a plastic
 * card with the real 2FF (25.0 mm x 15.0 mm) proportions, a gold contact module,
 * bevelled edges, a printed operator brand, a printed series and the synthetic
 * number. The number is data the backend generated - the client only prints it.
 */

const SIZES: Record<PhysicalSize, Record<string, string>> = {
  sm: { body: 'p-2.5', chip: 'h-8 w-11', number: 'text-[13px]', brand: 'text-[9px]', meta: 'text-[7px]' },
  md: { body: 'p-4', chip: 'h-12 w-16', number: 'text-lg', brand: 'text-[11px]', meta: 'text-[8px]' },
  lg: { body: 'p-6', chip: 'h-16 w-22', number: 'text-2xl', brand: 'text-sm', meta: 'text-[10px]' },
  hero: { body: 'p-8', chip: 'h-20 w-28', number: 'text-3xl sm:text-4xl', brand: 'text-base', meta: 'text-xs' },
};

/** 2FF SIM card ratio (25.0 x 15.0 mm), the physical standard for the form. */
const CARD_RATIO = 25 / 15;

export function SimCardVisual({
  collectible,
  size = 'md',
  className,
  accent = '#c9a227',
  reveal = false,
  still = false,
}: SimCardVisualProps) {
  const scale = SIZES[size];
  const details = (collectible.details ?? fallbackDetails(collectible)) as SimCardDetails;
  const number = details.synthetic_number || collectible.plate_text;

  return (
    <motion.div
      className={clsx(
        'sim-body relative w-full overflow-hidden rounded-[14px] border border-white/12',
        scale.body,
        className,
      )}
      style={{
        aspectRatio: String(CARD_RATIO),
        boxShadow: `0 22px 48px -22px ${accent}88, inset 0 1px 0 rgba(255,255,255,0.22), inset 0 -2px 8px rgba(0,0,0,0.55)`,
      }}
      data-testid="sim-card-visual"
      data-kind="SIM_CARD"
      data-plate={number}
      role="img"
      aria-label={`SIM card ${details.operator} ${number}`}
      initial={reveal ? { scale: 1.08, opacity: 0, rotateY: -18 } : false}
      animate={reveal ? { scale: 1, opacity: 1, rotateY: 0 } : undefined}
      transition={{ type: 'spring', stiffness: 200, damping: 18 }}
    >
      {/* Plastic body: a warm frosted core with a diagonal sheen, like real PET. */}
      <span
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            'linear-gradient(155deg, rgba(255,255,255,0.20) 0%, rgba(255,255,255,0.04) 32%, rgba(6,8,14,0.55) 78%), linear-gradient(200deg, #20242f 0%, #10131b 55%, #07080d 100%)',
        }}
      />
      {/* Notched contact module - the one detail that reads instantly as "SIM". */}
      <span aria-hidden className={clsx('sim-contact', scale.chip)} />
      {!still ? <span aria-hidden className="pointer-events-none absolute inset-0 sim-sheen" /> : null}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-[14px]"
        style={{ boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.08), inset 0 0 40px rgba(0,0,0,0.35)' }}
      />

      <div className="relative flex h-full flex-col justify-between gap-1 pl-1">
        <header className="flex items-start justify-between gap-2">
          <div className="flex min-w-0 flex-col">
            <span
              className={clsx('number-display truncate font-black tracking-[0.12em] text-white/95', scale.brand)}
            >
              {details.operator}
            </span>
            {size !== 'sm' ? (
              <span className={clsx('truncate font-bold uppercase tracking-[0.24em] text-white/40', scale.meta)}>
                {collectible.country.flag} {collectible.country.code}
              </span>
            ) : null}
          </div>
          {size !== 'sm' ? (
            <span
              className={clsx('shrink-0 rounded-full border px-2 py-0.5 font-bold uppercase tracking-[0.18em]', scale.meta)}
              style={{ borderColor: `${accent}66`, color: accent }}
            >
              {details.edition}
            </span>
          ) : null}
        </header>

        <div className="flex flex-col gap-0.5">
          <span className={clsx('truncate font-bold uppercase tracking-[0.2em] text-white/35', scale.meta)}>
            {t_syn}
          </span>
          <span
            className={clsx('number-display truncate font-semibold tracking-[0.04em] text-amber-50', scale.number)}
            data-testid="sim-card-number"
          >
            {number}
          </span>
        </div>

        <footer className="flex items-center justify-between gap-2">
          <span className={clsx('font-bold uppercase tracking-[0.22em] text-white/35', scale.meta)}>
            {details.series}
          </span>
          <span className={clsx('font-bold uppercase tracking-[0.22em] text-white/25', scale.meta)}>
            {collectible.currency_code}
          </span>
        </footer>
      </div>
    </motion.div>
  );
}

/** Fixed English micro-label; the synthetic marker must never be ambiguous. */
const t_syn = 'SYNTHETIC GAME NUMBER';

/**
 * Read the payload a cached or legacy card carries.
 *
 * Older cards have no ``details`` at all. Deriving from the template code keeps them
 * renderable without inventing anything the backend did not send.
 */
function fallbackDetails(collectible: PlateCard): SimCardDetails {
  const parts = collectible.template.code.split('_');
  return {
    operator_code: parts[2] ?? '',
    operator: (parts[2] ?? '').toUpperCase(),
    operator_local: '',
    series: '',
    edition: parts[parts.length - 2]?.toUpperCase() ?? '',
    synthetic_number: collectible.plate_text,
    calling_code: '',
    synthetic: true,
  };
}

export default SimCardVisual;